# vim: set ts=8 sts=2 sw=2 tw=99 et:
#
# This file is part of AMBuild.
# 
# AMBuild is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# AMBuild is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with AMBuild. If not, see <http://www.gnu.org/licenses/>.
import traceback
import select, os, sys
import multiprocessing as mp
from . import process
from . import posix_proc
from ipc.process import ProcessHost, Channel, Error, Special

# BSD multiprocess support is implemented using kqueue() on top of Python's
# Pipe object, which itself uses Unix domain sockets.

# Work around Python 3 bug on Darwin, it seems to translate KQ_NOTE_EXIT wrong.
KQ_NOTE_EXIT = select.KQ_NOTE_EXIT
if KQ_NOTE_EXIT == 0x80000000:
  KQ_NOTE_EXIT = -0x80000000

class MessagePump(process.MessagePump):
  def __init__(self):
    self.kq = select.kqueue()
    self.fdmap = {}
    self.pidmap = {}

  def close(self):
    super(MessagePump, self).close()
    self.kq.close()

  def addChannel(self, channel, listener):
    assert channel.fd not in self.fdmap

    event = select.kevent(
      ident=channel.fd,
      filter=select.KQ_FILTER_READ,
      flags=select.KQ_EV_ADD
    )
    self.fdmap[channel.fd] = (channel, listener)
    self.kq.control([event], 0)

  def dropChannel(self, channel):
    event = select.kevent(
      ident=channel.fd,
      filter=select.KQ_FILTER_READ,
      flags=select.KQ_EV_DELETE
    )
    self.kq.control([event], 0)
    del self.fdmap[channel.fd]

  def createChannel(self, name, listener):
    parent, child = posix_proc.SocketChannel.pair(name)
    return parent, child

  def addPid(self, pid, channel, listener):
    event = select.kevent(
      ident=pid,
      filter=select.KQ_FILTER_PROC,
      flags=select.KQ_EV_ADD,
      fflags=KQ_NOTE_EXIT
    )
    self.pidmap[pid] = (channel, listener)
    self.kq.control([event], 0)

  def dropPid(self, pid):
    assert pid in self.pidmap
    try:
      event = select.kevent(
        ident=pid,
        filter=select.KQ_FILTER_PROC,
        flags=select.KQ_EV_DELETE,
        fflags=select.KQ_NOTE_EXIT
      )
      self.kq.control([event], 0)
    except:
      # We could have already pulled the process death out and it's sitting
      # in our poll list; kqueue has removed it.
      pass
    del self.pidmap[pid]

  def shouldProcessEvents(self):
    return (len(self.pidmap) + len(self.fdmap)) and \
           super(MessagePump, self).shouldProcessEvents()

  def processEvents(self):
    max_events = len(self.pidmap) + len(self.fdmap)

    events = self.kq.control(None, max_events, None)

    # Process reads first.
    next_events = []
    for event in events:
      if not self.shouldProcessEvents():
        return

      if event.filter != select.KQ_FILTER_READ:
        next_events.append(event)
        continue

      channel, listener = self.fdmap[event.ident]

      # We can receive EOF even if there are more bytes to read, so we always
      # attempt a message read anyway.
      try:
        message = channel.recv()
      except:
        traceback.print_exc()
        self.handle_channel_error(channel, listener, Error.EOF)
        continue

      if not message:
        self.handle_channel_error(channel, listener, Error.Closed)
        continue

      if message == Special.Closing:
        self.handle_channel_error(channel, listener, Error.NormalShutdown)
        continue

      try:
        listener.receiveMessage(channel, message)
      except Exception as exn:
        traceback.print_exc()
        self.handle_channel_error(channel, listener, Error.User)

      if event.flags & select.KQ_EV_EOF:
        self.handle_channel_error(channel, listener, Error.EOF)

    # Now handle pid death.
    for event in next_events:
      if not self.shouldProcessEvents():
        return

      assert event.filter == select.KQ_FILTER_PROC
      # We could have pulled this event out earlier, and decided to drop the
      # PID in between. To account for this, we check the map first. It might
      # be cleaner to pre-process PID events earlier?
      if event.ident not in self.pidmap:
        continue

      channel, listener = self.pidmap[event.ident]
      listener.receiveError(channel, Error.Killed)
      del self.pidmap[event.ident]

  def handle_channel_error(self, channel, listener, error):
    self.dropChannel(channel)
    listener.receiveError(channel, error)

class ProcessManager(process.ProcessManager):
  def __init__(self, pump):
    super(ProcessManager, self).__init__(pump)

  def create_process_and_pipe(self, id, listener):
    # Create pipes.
    parent, child = posix_proc.SocketChannel.pair(listener.name)

    # Watch for changes on the parent channel.
    self.pump.addChannel(parent, listener)

    # Spawn the process.
    proc = posix_proc.Process.spawn(child)

    # Unlike Linux, BSD systems have an old bug where if a descriptor is only
    # alive because it is in a message queue, it can be garbage collected in
    # the kernel. This doesn't make much sense, but we deal by waiting for an
    # ACK from the child process to close the child fds.
    #
    # This also means there is a race condition, where the child process could
    # die before it sends its ACK, and therefore the pipe will never be closed
    # and we'll wait forever on it.
    #
    # To address this, we watch for PID death via kqueue.
    #
    # NB: This comment really only applies to descriptors sent over sockets
    # using sendmsg(msg_control + SCM_RIGHTS). For the actual primary channel,
    # we use dup2(), which should be safe? But just in case, we wait for the
    # ACK.
    self.pump.addPid(proc.pid, parent, listener)

    return posix_proc.PosixHost(id, proc, parent, child)

  def close_process(self, host):
    # There should be nothing open for this channel, since we wait for process death.
    assert host.channel.fd not in self.pump.fdmap
    if host.closing != Error.Killed:
      self.pump.dropPid(host.pid)
    host.shutdown()

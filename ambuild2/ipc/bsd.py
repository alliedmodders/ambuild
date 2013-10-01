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
import select, os, sys
import multiprocessing as mp
from ipc.process import ProcessHost, ProcessManager, Channel, MessagePump, Error
from ipc.process import ChildWrapperListener, Special

# BSD multiprocess support is implemented using kqueue() on top of Python's
# Pipe object, which itself uses Unix domain sockets.

class PipeChannel(Channel):
  def __init__(self, reader, writer):
    super(PipeChannel, self).__init__()
    self.reader = reader
    self.writer = writer

  def close(self):
    self.reader.close()
    self.writer.close()

  def send(self, message):
    self.writer.send(message)

def ChildMain(channel, listener_type, *args):
  print('Spawned child process: ' + str(os.getpid()))
  # Create a process manager.
  bmp = BSDMessagePump()
  listener = listener_type(bmp)
  listener = ChildWrapperListener(listener)
  bmp.addChannel(channel, listener)
  channel.send(Special.Connected)
  bmp.pump()

class BSDMessagePump(MessagePump):
  def __init__(self):
    self.kq = select.kqueue()
    self.fdmap = {}
    self.pidmap = {}

  def close(self):
    super(BSDMessagePump, self).close()
    self.kq.close()

  def addChannel(self, channel, listener):
    fd = channel.reader.fileno()
    event = select.kevent(
      ident=fd,
      filter=select.KQ_FILTER_READ,
      flags=select.KQ_EV_ADD
    )
    self.fdmap[fd] = (channel, listener)
    self.kq.control([event], 0)

  def dropChannel(self, channel):
    fd = channel.reader.fileno()
    event = select.kevent(
      ident=fd,
      filter=select.KQ_FILTER_READ,
      flags=select.KQ_EV_DELETE
    )
    self.kq.control([event], 0)
    del self.fdmap[fd]

  def addPid(self, pid, channel, listener):
    event = select.kevent(
      ident=pid,
      filter=select.KQ_FILTER_PROC,
      flags=select.KQ_EV_ADD,
      fflags=select.KQ_NOTE_EXIT
    )
    self.pidmap[pid] = (channel, listener)
    self.kq.control([event], 0)

  def dropPid(self, pid):
    event = select.kevent(
      ident=pid,
      filter=select.KQ_FILTER_PROC,
      flags=select.KQ_EV_DELETE,
      fflags=select.KQ_NOTE_EXIT
    )
    del self.pidmap[pid]
    self.kq.control([event], 0)

  def shouldProcessEvents(self):
    return len(self.pidmap) + len(self.fdmap)

  def processEvents(self):
    max_events = len(self.pidmap) + len(self.fdmap)

    events = self.kq.control(None, max_events, None)

    # Process reads first.
    next_events = []
    for event in events:
      if event.filter != select.KQ_FILTER_READ:
        next_events.append(event)
        continue

      channel, listener = self.fdmap[event.ident]

      # We can receive EOF even if there are more bytes to read, so we always
      # attempt a message read anyway.
      try:
        message = channel.reader.recv()
      except:
        listener.receiveError(channel, Error.EOF)
        continue

      try:
        listener.receiveMessage(channel, message)
      except Exception as exn:
        listener.receiveError(channel, Error.User)

      if event.flags & select.KQ_EV_EOF:
        listener.receiveError(channel, Error.EOF)

    # Now handle pid death.
    for event in next_events:
      assert event.filter == select.KQ_FILTER_PROC
      channel, listener = self.pidmap[event.ident]
      listener.receiveError(channel, Error.Killed)
      del self.pidmap[event.ident]

class BSDHost(ProcessHost):
  def __init__(self, id, proc, channel, child_channel):
    super(BSDHost, self).__init__(id, proc, channel)
    self.child_channel = child_channel

  def receiveConnected(self):
    super(BSDHost, self).receiveConnected()
    self.child_channel.close()
    self.child_channel = None

  def close(self):
    super(BSDHost, self).close()
    if self.child_channel:
      self.child_channel.close()

class BSDProcessManager(ProcessManager):
  def __init__(self, pump):
    super(BSDProcessManager, self).__init__(pump)

  def create_process_and_pipe(self, id, listener, child_type, args):
    # Create pipes.
    child_read, parent_write = mp.Pipe(duplex=False)
    parent_read, child_write = mp.Pipe(duplex=False)

    channel = PipeChannel(parent_read, parent_write)
    child_channel = PipeChannel(child_read, child_write)

    # Watch for changes on the parent channel.
    self.pump.addChannel(channel, listener)

    # Spawn the process.
    proc = mp.Process(
      target=ChildMain,
      args=(child_channel, child_type) + args
    )
    proc.start()

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
    self.pump.addPid(proc.pid, channel, listener)

    return BSDHost(id, proc, channel, child_channel)

  def close_process(self, host, error):
    self.pump.dropChannel(host.channel)
    if error != Error.Killed:
      self.pump.dropPid(host.pid)
    host.close()

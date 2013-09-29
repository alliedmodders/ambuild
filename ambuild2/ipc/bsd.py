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
from ipc.process import ProcessHost, ProcessManager, Channel

# BSD multiprocess support is implemented using kqueue() on top of Python's
# Pipe object, which itself uses Unix domain sockets.

class PipeChannel(Channel):
  def __init__(self, reader, writer, listener=None):
    super(PipeChannel, self).__init__(listener)
    self.reader = reader
    self.writer = writer

  def close(self):
    self.reader.close()
    self.writer.close()

  def send(self, message):
    self.writer.send(message)

def ChildMain(reader, writer, child_type):
  print('Spawned child process: ' + str(os.getpid()))
  # Create a process manager.
  channel = PipeChannel(reader, writer)
  manager = BSDProcessManager(channel)
  channel.listener = child_type(manager)
  manager.pump()

class BSDHost(ProcessHost):
  def __init__(self, id, parent_listener, child_type):
    super(BSDHost, self).__init__(id)

    # Create pipes.
    child_read, parent_write = mp.Pipe(duplex=False)
    parent_read, child_write = mp.Pipe(duplex=False)

    self.proc = mp.Process(
      target=ChildMain,
      args=(child_read, child_write, child_type)
    )
    self.proc.start()

    # Unlike Linux, BSD systems have an old bug where if a descriptor is only
    # alive because it is in a message queue, it can be garbage collected in
    # the kernel. This doesn't make much sense, but we deal. The optimal
    # solution would be waiting for an ACK from the child; here we just keep
    # the descriptors alive until the process is dead.
    self.child_channel = PipeChannel(child_read, child_write, None)

    # Instantiate the parent listener and channel.
    self.channel = PipeChannel(parent_read, parent_write, parent_listener)

  def close(self):
    self.child_channel.close()
    super(BSDHost, self).close()

class BSDProcessManager(ProcessManager):
  def __init__(self, parent=None):
    super(BSDProcessManager, self).__init__(parent)
    self.kq = select.kqueue()
    self.fdmap = {}
    self.pidmap = {}
    if parent:
      self.registerChannel(None, parent)

  def close(self):
    if self.parent:
      self.unregisterChannel(self.parent)
    super(BSDProcessManager, self).close()
    self.kq.close()

  def spawn_internal(self, id, parent_listener, child_type):
    return BSDHost(id, parent_listener, child_type)

  def registerHost(self, host):
    self.registerChannel(host, host.channel)

  def registerChannel(self, host, channel):
    fd = channel.reader.fileno()
    events = [
      select.kevent(
        ident=fd,
        filter=select.KQ_FILTER_READ,
        flags=select.KQ_EV_ADD|select.KQ_EV_ENABLE
      )
    ]
    if host:
      events.append(select.kevent(
        ident=host.pid,
        filter=select.KQ_FILTER_PROC,
        flags=select.KQ_EV_ADD|select.KQ_EV_ENABLE,
        fflags=select.KQ_NOTE_EXIT
      ))
      self.pidmap[host.pid] = host
    self.fdmap[fd] = (host, channel)
    r = self.kq.control(events, 0)

  def unregisterHost(self, host):
    self.unregisterChannel(host, host.channel)

  def unregisterChannel(self, host, channel):
    fd = channel.reader.fileno()
    del self.fdmap[fd]
    events = [
      select.kevent(
        ident=fd,
        filter=select.KQ_FILTER_READ,
        flags=select.KQ_EV_DELETE
      )
    ]
    if host:
      # Note: Darwin appears to automatically remove the event once the exit
      # event has been delivered, so we don't remove it here.
      del self.pidmap[host.pid]
    self.kq.control(events, 0)

  def handleEOF(self, host, channel):
    if not host:
      sys.stderr.write('Received EOF from parent process, exiting...\n')
      sys.exit(1)

    # If the process didn't die, but we received EOF, we have to be careful.
    # Calling join() could deadlock since the process could have closed the
    # pipe but then locked up. To get around these, we terminate(), and wait
    # for the process signal.
    if not host.closing:
      host.listener.receiveError(host, 'eof')
      host.terminate()

  def poll(self):
    max_events = 0
    if self.parent:
      max_events = 1
    max_events += len(self.children)

    events = self.kq.control(None, max_events, None)

    # Process reads first.
    next_events = []
    for event in events:
      if event.filter != select.KQ_FILTER_READ:
        next_events.append(event)
        continue

      host, channel = self.fdmap[event.ident]

      # We can receive EOF even if there are more bytes to read, so we always
      # attempt a message read anyway.
      try:
        message = channel.reader.recv()
      except:
        self.handleEOF(host, host.channel)
        continue

      try:
        channel.listener.receiveMessage(host, message)
      except Exception as exn:
        self.handleError(host, channel, exn)

      if event.flags & select.KQ_EV_EOF:
        self.handleEOF(host, host.channel)

    # Now handle pid death.
    for event in next_events:
      assert event.filter == select.KQ_FILTER_PROC
      host = self.pidmap[event.ident]
      self.handleDead(host, host.channel)


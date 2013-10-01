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
import select, os
import multiprocessing as mp
from ipc.process import ProcessHost, ProcessManager, Channel, MessagePump, Error
from ipc.process import ChildWrapperListener

# Linux multiprocess support is implemented using epoll() on top of Python's
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
  lmp = LinuxMessagePump()
  listener = listener_type(lmp)
  listener = ChildWrapperListener(listener)
  lmp.addChannel(channel, listener)
  lmp.pump()

class LinuxMessagePump(MessagePump):
  def __init__(self):
    super(LinuxMessagePump, self).__init__()
    self.ep = select.epoll()
    self.fdmap = {}

  def close(self):
    self.ep.close()

  def addChannel(self, channel, listener):
    fd = channel.reader.fileno()
    events = select.EPOLLIN | select.EPOLLERR | select.EPOLLHUP

    self.ep.register(fd, events)
    self.fdmap[fd] = (channel, listener)

  def dropChannel(self, channel):
    fd = channel.reader.fileno()
    self.ep.unregister(fd)
    del self.fdmap[fd]

  def shouldProcessEvents(self):
    return len(self.fdmap)

  def processEvents(self):
    for fd, event in self.ep.poll():
      channel, listener = self.fdmap[fd]
      if event & (select.EPOLLERR | select.EPOLLHUP):
        listener.receiveError(channel, Error.EOF)
        continue

      message = channel.reader.recv()
      try:
        listener.receiveMessage(channel, message)
      except Exception as exn:
        listener.receiveError(channel, Error.User)

class LinuxProcessManager(ProcessManager):
  def __init__(self, pump):
    super(LinuxProcessManager, self).__init__(pump)

  def create_process_and_pipe(self, id, listener, child_type, args):
    # Create pipes.
    child_read, parent_write = mp.Pipe(duplex=False)
    parent_read, child_write = mp.Pipe(duplex=False)

    # Create the parent listener channel and register it.
    channel = PipeChannel(parent_read, parent_write)
    self.pump.addChannel(channel, listener)

    # Create the child channel.
    child_channel = PipeChannel(child_read, child_write)

    # Spawn the process.
    proc = mp.Process(
      target=ChildMain,
      args=(child_channel, child_type) + args
    )
    proc.start()

    # We don't need the child descriptors anymore.
    child_channel.close()

    return ProcessHost(id, proc, channel)

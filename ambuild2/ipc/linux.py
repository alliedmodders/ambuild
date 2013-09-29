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
from ipc.process import ProcessHost, ProcessManager, Channel

class LinuxChannel(Channel):
  def __init__(self, reader, writer, listener=None):
    super(LinuxChannel, self).__init__(listener)
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
  channel = LinuxChannel(reader, writer)
  manager = LinuxProcessManager(channel)
  channel.listener = child_type(manager)
  manager.pump()

class LinuxHost(ProcessHost):
  def __init__(self, id, parent_listener, child_type):
    super(LinuxHost, self).__init__(id)

    # Create pipes.
    child_read, parent_write = mp.Pipe(duplex=False)
    parent_read, child_write = mp.Pipe(duplex=False)

    self.proc = mp.Process(
      target=ChildMain,
      args=(child_read, child_write, child_type)
    )
    self.proc.start()

    # We don't need the child descriptors anymore.
    child_read.close()
    child_write.close()

    # Instantiate the parent listener and channel.
    self.channel = LinuxChannel(parent_read, parent_write, parent_listener)

class LinuxProcessManager(ProcessManager):
  def __init__(self, parent=None):
    super(LinuxProcessManager, self).__init__(parent)
    self.ep = select.epoll()
    self.fdmap = {}
    if parent:
      self.registerChannel(None, parent)

  def close(self):
    if self.parent:
      self.unregisterChannel(self.parent)
    super(LinuxProcessManager, self).close()

  def spawn_internal(self, id, parent_listener, child_type):
    return LinuxHost(id, parent_listener, child_type)

  def registerHost(self, host):
    self.registerChannel(host, host.channel)

  def registerChannel(self, host, channel):
    fd = channel.reader.fileno()
    events = select.EPOLLIN | select.EPOLLERR | select.EPOLLHUP
    self.fdmap[fd] = (host, channel)
    self.ep.register(fd, events)

  def unregisterHost(self, host):
    self.ep.unregister(host.channel.reader)

  def unregisterChannel(self, channel):
    fd = channel.reader.fileno()
    del self.fdmap[fd]
    self.ep.unregister(fd)

  def pump(self):
    while self.shouldPoll():
      self.poll()

  def poll(self):
    for fd, event in self.ep.poll():
      host, channel = self.fdmap[fd]
      if event & (select.EPOLLERR | select.EPOLLHUP):
        self.handleDead(host, channel)
      else:
        message = channel.reader.recv()
        try:
          channel.listener.receiveMessage(host, message)
        except Exception as exn:
          self.handleError(host, exn)

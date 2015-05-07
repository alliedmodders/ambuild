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
import errno
import traceback
import socket
import select
from . import process
from . import posix_proc
from . process import Error, Special

# Generic POSIX multiprocess support, implemented using poll().

class MessagePump(process.LinuxMessagePumpMixin, posix_proc.PosixMessagePump):
  def __init__(self):
    super(MessagePump, self).__init__()
    self.ep = select.poll()

  def addChannel(self, channel, listener):
    events = select.POLLIN | select.POLLERR | select.POLLHUP

    self.ep.register(channel.fd, events)
    self.fdmap[channel.fd] = (channel, listener)

  def processEvents(self):
    for fd, event in self.ep.poll():
      if not self.shouldProcessEvents():
        return

      channel, listener = self.fdmap[fd]
      if event & select.POLLIN:
        # Linux seems to have two failure modes for failing to read from a
        # unix domain socket: it can receive 0 bytes (which we handle in
        # posix_proc, and return None for), or it can throw ECONNRESET. In
        # either case, we treat it as an EOF, and don't throw an exception.
        #
        # If it was a legitimate error, we'll throw it later on.
        message = None
        try:
          message = channel.recv()
        except socket.error as exn:
          if not (exn.errno == errno.ECONNRESET and (event & select.POLLHUP)):
            traceback.print_exc()
        except Exception as exn:
          traceback.print_exc()

        if not message:
          self.handle_channel_error(channel, listener, Error.EOF)
          continue

        if message == Special.Closing:
          self.handle_channel_error(channel, listener, Error.NormalShutdown)
          continue

        try:
          listener.receiveMessage(channel, message)
        except Exception as exn:
          traceback.print_exc()
          self.handle_channel_error(channel, listener, Error.User)
          continue

      if event & (select.POLLERR | select.POLLHUP):
        self.handle_channel_error(channel, listener, Error.EOF)


class ProcessManager(process.ProcessManager):
  def create_process_and_pipe(self, id, listener):
    # Create pipes.
    parent, child = posix_proc.SocketChannel.pair(listener.name)

    # Watch for changes on the parent channel.
    self.pump.addChannel(parent, listener)

    # Spawn the process.
    proc = posix_proc.Process.spawn(child)

    return posix_proc.PosixHost(id, proc, parent, child)

  def close_process(self, host):
    # There should be nothing open for this channel, since we wait for process death.
    assert host.channel.fd not in self.pump.fdmap
    host.shutdown()

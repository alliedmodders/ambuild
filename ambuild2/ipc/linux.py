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
from . import generic_poll
from . import posix_proc
from . process import Error, Special

# Linux multiprocess support is implemented using epoll().

class MessagePump(process.LinuxMessagePumpMixin, posix_proc.PosixMessagePump):
  def __init__(self):
    super(MessagePump, self).__init__()
    self.ep = select.epoll()

  def addChannel(self, channel, listener):
    events = select.EPOLLIN | select.EPOLLERR | select.EPOLLHUP

    self.ep.register(channel.fd, events)
    self.fdmap[channel.fd] = (channel, listener)

  def processEvents(self):
    for fd, event in self.ep.poll():
      if not self.shouldProcessEvents():
        return

      channel, listener = self.fdmap[fd]
      if event & select.EPOLLIN:
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
          if not (exn.errno == errno.ECONNRESET and (event & select.EPOLLHUP)):
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

      if event & (select.EPOLLERR | select.EPOLLHUP):
        self.handle_channel_error(channel, listener, Error.EOF)

# There is a race condition where if the child dies before sending an ACK,
# we will never close the parent process's fildes for the child socket.
# epoll() will then deadlock since no EOF will be delivered. I don't see
# an easy way to solve this yet, so we just cross our fingers.
#
# On BSD this is not a problem since kqueue() can watch pids.
ProcessManager = generic_poll.ProcessManager

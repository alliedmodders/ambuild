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
import os, sys
from . import process
from ambuild2 import util

if util.IsWindows():
  from . import windows as ipc_impl
elif util.IsLinux():
  from . import linux as ipc_impl
elif util.IsBSD():
  from . import bsd as ipc_impl
else:
  raise Exception('Unknown platform: ' + util.Platform())

ProcessManager = ipc_impl.ProcessManager
MessagePump = ipc_impl.MessagePump

if util.IsWindows():
  from . windows import NamedPipe as Channel
else:
  from . posix_proc import SocketChannel as Channel

class ChildWrapperListener(process.MessageListener):
  def __init__(self, mp, channel):
    super(ChildWrapperListener, self).__init__()
    self.mp = mp
    self.channel = channel
    self.listener = None

  def receiveMessage(self, channel, message):
    if message == process.Special.Close:
      self.listener.receiveClose(channel)
      return

    if message['id'] == '__start__':
      listener_type = message['listener_type']
      args = message['args']
      channels = ()
      if 'channels' in message:
        channels = message['channels']
      
      self.listener = listener_type(self.mp, self.channel, *(args + channels))
      return

    self.listener.receiveMessage(channel, message)

  def receiveError(self, channel, error):
    if self.listener:
      self.listener.receiveError(error)
    else:
      sys.stderr.write('[{0}] Parent process died, terminating...\n'.format(os.getpid()))
    sys.exit(1)

def child_main(channel):
  mp = MessagePump()
  listener = ChildWrapperListener(mp, channel)
  mp.addChannel(channel, listener)
  try:
    mp.pump()
  except:
    print('>>>>>>>>>>>>>>>>>>>>>EXITING', os.getpid(), '!!!!!!!!!!!!!!!!!!')
    raise
  sys.stdout.write('[{0}] Child process terminating normally.\n'.format(os.getpid()))

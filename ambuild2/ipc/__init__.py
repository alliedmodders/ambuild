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
import util
from ipc.process import ParentListener, ChildListener

__all__ = ['ProcessManager', 'MessagePump', 'ParentListener', 'ChildListener']

if util.IsWindows():
  from ipc.windows import WindowsProcessManager as ProcessManager
elif util.IsLinux():
  from ipc.linux import LinuxProcessManager as ProcessManager
  from ipc.linux import LinuxMessagePump as MessagePump
elif util.IsBSD():
  from ipc.bsd import BSDProcessManager as ProcessManager
  from ipc.bsd import BSDMessagePump as MessagePump
else:
  raise Exception('Unknown platform: ' + util.Platform())

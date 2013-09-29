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
import sys
import multiprocessing as mp

class Channel(object):
  def __init__(self, listener=None):
    super(Channel, self).__init__()
    self.listener = listener

  def send(self, message):
    raise Exception('must be implemented')

class ProcessHost(object):
  def __init__(self, id):
    super(ProcessHost, self).__init__()
    self.id = id
    self.closing = False
    self.proc = None
    self.channel = None

  def send(self, message):
    self.channel.send(message)

  def close(self):
    self.proc.join()
    self.channel.close()

class ProcessManager(object):
  def __init__(self, channel=None):
    self.children = set()
    self.parent = channel

  def close(self):
    if self.parent:
      self.parent.close()

  # The parent_type is instantiated with its ProcessHost as an argument.
  # When the child process is spawned, it will instantiate a child_type
  # with a ProcessManager as its argument.
  def spawn(self, parent_type, child_type):
    id = len(self.children)
    child = self.spawn_internal(id, parent_type, child_type)
    self.children.add(child)
    self.registerHost(child)

  ## Internal functions.

  def cleanup(self, host):
    self.children.remove(host)
    self.unregisterHost(host)
    host.close()

  def handleDead(self, host, channel):
    if not host:
      assert channel == self.parent
      
      # Our parent crashed or something. Just exit.
      sys.stderr.write('Parent process died, exiting.\n')
      sys.exit(1)
    else:
      # One of our children died.
      if not host.closing:
        channel.listener.receiveError('process died')
      self.cleanup(host)

  def pump(self):
    raise Exception('must be implemented!')

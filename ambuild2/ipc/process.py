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

# A channel is two-way IPC connection; it has a read and write pipe. The read
# pipe is multiplexed by the ProcessManager and automatically forwarded to
# the listener object. The send() function can access the write pipe directly.
class Channel(object):
  def __init__(self, listener=None):
    super(Channel, self).__init__()
    self.listener = listener

  def send(self, message):
    raise Exception('must be implemented')

# A ProcessHost is the parent process's view of a child process. It
# encapsulates the process ID, various state, and an IPC channel.
class ProcessHost(object):
  def __init__(self, id):
    super(ProcessHost, self).__init__()
    self.id = id
    self.closing = False
    self.terminating = False
    self.proc = None
    self.channel = None

  @property
  def listener(self):
    return self.channel.listener

  @property
  def pid(self):
    return self.proc.pid

  def send(self, message):
    self.channel.send(message)

  def close(self):
    if self.proc.is_alive():
      # To avoid a potential deadlock, we terminate the process before joining.
      self.proc.terminate()
    self.proc.join()
    self.channel.close()

  # An abrupt termination.
  def terminate(self):
    if self.terminating:
      return
    self.closing = True
    self.terminating = True
    self.proc.terminate()

# A ChildListener listens for events in a child process, that come from the
# parent process. Although it is derived, it is never explicitly instantiated.
# Rather, the derived type is given to ProcessManager.spawn(), and a singleton
# is automatically created in the child process.
class ChildListener(object):
  def __init__(self, manager):
    super(ChildListener, self).__init__()
    self.manager = manager

  # Called when a message is received from the parent process.
  def receiveMessage(self, message):
    raise Exception('Unhandled message: ' + str(message))

  # Called when the parent connection has died; this will result in the
  # child process terminating.
  def receiveError(self, error):
    pass

# A ParentListener listens for child process messages sent to a parent process.
# The lisener must handle incoming messages; if for any reason it fails to
# process a message, the child process is killed and an error is reported.
# ParentListeners are instantiated manually and given directly to spawn() -
# one listener can be re-used many times.
class ParentListener(object):
  def __init__(self):
    super(ParentListener, self).__init__()

  # Called when a connection is being established.
  def receiveConnect(self, child):
    pass

  # Called when a message has been received. The child is a ProcessHost
  # object corresponding to the parent side of the child process's connection.
  def receiveMessage(self, child, message):
    raise Exception('Unhandled message: ' + str(message))

  # Called when an error has occurred and the channel will be closed.
  def receiveError(self, child, error):
    raise Exception('Unhandled error: ' + error)

# A process manager handles multiplexing IPC communication. It also owns the
# set of child processes. There should only be one ProcessManager per process.
class ProcessManager(object):
  def __init__(self, channel=None):
    self.children = set()
    self.parent = channel

  def close(self):
    children = [child for child in self.children]
    for child in children:
      self.kill(child)
    if self.parent:
      self.parent.close()

  # The parent_type is instantiated with its ProcessHost as an argument.
  # When the child process is spawned, it will instantiate a child_type
  # with a ProcessManager as its argument.
  def spawn(self, parent_type, child_type):
    id = len(self.children)
    child = self.spawn_internal(id, parent_type, child_type)
    child.listener.receiveConnect(child)
    self.children.add(child)
    self.registerHost(child)

  ## Internal functions.

  def cleanup(self, host):
    self.children.remove(host)
    self.unregisterHost(host)
    host.close()

  def handleError(self, host, channel, exn):
    if host:
      host.terminate()

  def handleDead(self, host, channel):
    if not host:
      assert channel == self.parent
      
      # Our parent crashed or something. Just exit.
      channel.listener.receiveError('process died')
      sys.stderr.write('Parent process died, exiting.\n')
      sys.exit(1)
    else:
      # One of our children died.
      if not host.closing:
        channel.listener.receiveError(host, 'process died')
      self.cleanup(host)

  def pump(self):
    while self.shouldPoll():
      self.poll()

  def shouldPoll(self):
    if not self.parent and not len(self.children):
      return False
    return True

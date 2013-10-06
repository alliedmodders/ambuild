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

class Error:
  EOF = 'eof'
  User = 'badmsg'
  Killed = 'killed'

class Special:
  Connected = 'ack!'

# A channel is two-way IPC connection; it has a read and write pipe. The read
# pipe is multiplexed by a MessagePump. The send() function can access the
# write pipe directly.
#
# Channels must have at most one reader and at most one writer. Attempt to
# have multiple writers or readers could corrupt the pipe.
class Channel(object):
  def __init__(self):
    super(Channel, self).__init__()

  # Only dictionaries should ever be sent; dictionaries can contain
  # arbitrary items, however, non-dictionary values for |message|
  # are reserved by the implementation.
  #
  # The optional channels parameter may be used to send Channels with the
  # resulting message. On the receiving end, the channel list will be
  # attached as a special 'channels' entry on the message dictionary.
  def send(self, message, channels=None):
    raise Exception('must be implemented')

# The interface for a raw message listener.
class MessageListener(object):
  def __init__(self):
    super(MessageListener, self).__init__()

  def receiveMessage(self, channel, message):
    pass

  def receiveError(self, channel, error):
    pass

# A ChildListener listens for events in a child process, that come from the
# parent process. Although it is derived, it is never explicitly instantiated.
# Rather, the derived type is given to ProcessManager.spawn(), and a singleton
# is automatically created in the child process.
#
# The incoming value to ChildListener() is the message pump.
class ChildListener(object):
  def __init__(self, pump):
    super(ChildListener, self).__init__()
    self.pump = pump
    self.channel = None

  def receiveConnected(self, channel):
    self.channel = channel

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

  # Called when a connection has successfully been established.
  def receiveConnected(self, child):
    pass

  # Called when a message has been received. The child is a ProcessHost
  # object corresponding to the parent side of the child process's connection.
  def receiveMessage(self, child, message):
    raise Exception('Unhandled message: ' + str(message))

  # Called when an error has occurred and the channel will be closed.
  def receiveError(self, child, error):
    raise Exception('Unhandled error: ' + error)

# A MessagePump handles multiplexing IPC communication.
class MessagePump(object):
  def __init__(self):
    super(MessagePump, self).__init__()

  def close(self):
    pass

  def pump(self):
    while self.shouldProcessEvents():
      self.processEvents()

  def processEvents(self):
    raise Exception('must be implemented!')

  # Creates an IPC channel and automatically registers it. When teh channel
  # is closed it is automatically unregistered.
  def createChannel(self, listener):
    raise Exception('must be implemented!')

  # Drops a registered IRC channel.
  def dropChannel(self, channel):
    raise Exception('must be implemented!')

# A ProcessHost is the parent process's view of a child process. It
# encapsulates the process ID, various state, and an IPC channel.
class ProcessHost(object):
  def __init__(self, id, proc, channel):
    super(ProcessHost, self).__init__()
    self.id = id
    self.closing = False      # Indicates intent to terminate.
    self.terminating = False  # Indicates forceful termination.
    self.proc = proc
    self.channel = channel

  @property
  def pid(self):
    return self.proc.pid

  def send(self, message):
    self.channel.send(message)

  def receiveConnected(self):
    pass

  def close(self):
    if self.proc.is_alive() and not self.closing:
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

class ParentWrapperListener(MessageListener):
  def __init__(self, procman, listener):
    super(ParentWrapperListener, self).__init__()
    self.procman = procman
    self.child = None
    self.listener = listener

  def receiveConnect(self, child):
    self.child = child
    self.listener.receiveConnect(child)

  def receiveMessage(self, channel, message):
    if message == Special.Connected:
      self.child.receiveConnected()
      self.listener.receiveConnected(self.child)
    else:
      self.listener.receiveMessage(self.child, message)

  def receiveError(self, channel, error):
    if not self.child.closing:
      self.listener.receiveError(self.child, error)
    self.procman.cleanup(self.child, error)

# A process manager handles multiplexing IPC communication. It also owns the
# set of child processes. There should only be one ProcessManager per process.
class ProcessManager(object):
  def __init__(self, pump):
    self.pump = pump
    self.children = set()
    self.last_id_ = 1

  def close(self):
    children = [child for child in self.children]
    for child in children:
      child.close()

  # On the parent side, the listener object should be a ParentListener that
  # will receive incoming notifications. On the child side, child_type will
  # be used to instantiate a singleton object that listens for messages
  # from the parent process.
  def spawn(self, listener, child_type, args=(), channels=None):
    # We wrap the listener in one that lets us pre-empt errors.
    listener = ParentWrapperListener(self, listener)

    # Create the child process.
    child = self.create_process_and_pipe(
      id=self.last_id_,
      listener=listener
    )
    self.children.add(child)

    self.last_id_ += 1

    # Send the start message to the child.
    message = {
      'id': '__start__',
      'args': args,
      'listener_type': child_type
    }
    child.channel.send(message, channels)

    # Tell the listener that we've probably connected.
    listener.receiveConnect(child)
    return child

  ## Internal functions.

  def cleanup(self, host, error):
    self.children.remove(host)
    self.close_process(host, error)

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
import time
import logging
import os, sys
import traceback
import multiprocessing as mp

class Error:
  NormalShutdown = 'normal'
  EOF = 'eof'
  Closed = 'closed'
  User = 'badmsg'
  Killed = 'killed'

class Special:
  Connected = 'ack!'
  Close = 'die'
  Closing = 'closing'

# A channel is two-way IPC connection; it has a read and write pipe. The read
# pipe is multiplexed by a MessagePump. The send() function can access the
# write pipe directly.
#
# Channels must have at most one reader and at most one writer. Attempt to
# have multiple writers or readers could corrupt the pipe.
class Channel(object):
  def __init__(self, name):
    super(Channel, self).__init__()
    self.name = name

  # Only dictionaries should ever be sent; dictionaries can contain
  # arbitrary items, however, non-dictionary values for |message|
  # are reserved by the implementation.
  #
  # If channels is a tuple of Channel objects, they will be attached to the
  # message dictionary to a 'channels' key, and reconstructed on the other
  # side.
  def send(self, message, channels=()):
    self.send_impl(message, channels)
    self.log_send(message, channels)

  def recv(self):
    message = self.recv_impl()
    self.log_recv(message)
    return message

  # When manually passing pipes around, connect() should be explicitly called
  # to ensure the other end knows that the pipe is ready.
  def connect(self, name):
    self.name = name
    self.send(Special.Connected)
  
  # Sends a special message to the other end that the channel is about to
  # close.
  def finished(self):
    self.send(Special.Closing)

  def log_recv(self, message):
    if not __debug__:
      return
    msgid = Channel.formatMessage(message)
    logging.info('[{0}:{1}] {2} received message: {3}'.format(
      os.getpid(),
      time.time(),
      self.name,
      msgid
    ))

  def log_send(self, message, channels=()):
    if not __debug__:
      return
    msgid = Channel.formatMessage(message)
    logging.info('[{0}:{1}] {2} sent message: {3} ({4} channels)'.format(
      os.getpid(),
      time.time(),
      self.name,
      msgid,
      len(channels))
    )

  @staticmethod
  def formatMessage(message):
    if type(message) == dict:
      return message['id']
    return str(message)

  # Implementation of send().
  def send_impl(self, message, channels=()):
    raise Exception('must be implemented')

  # For debugging.
  def closed(self):
    raise Exception('must be implemented')

# The interface for a raw message listener.
class MessageListener(object):
  def __init__(self, close_on_ack=None):
    super(MessageListener, self).__init__()
    self.messageMap = {}
    self.close_on_ack = close_on_ack

  def receiveConnected(self, channel):
    pass

  def receiveMessage(self, channel, message):
    if message == Special.Connected:
      if self.close_on_ack:
        self.close_on_ack.close()
        self.close_on_ack = None
      return self.receiveConnected(channel)

    if message['id'] in self.messageMap:
      return self.messageMap[message['id']](channel, message)

    raise Exception('Unhandled message: ' + str(message['id']))

  def receiveError(self, channel, error):
    pass

# A ChildListener listens for events in a child process, that come from the
# parent process. Although it is derived, it is never explicitly instantiated.
# Rather, the derived type is given to ProcessManager.spawn(), and a singleton
# is automatically created in the child process.
#
# The incoming value to ChildListener() is the message pump.
class ChildProcessListener(object):
  def __init__(self, pump):
    super(ChildProcessListener, self).__init__()
    self.pump = pump
    self.channel = None
    self.messageMap = {}

  def receiveConnected(self, channel):
    self.channel = channel

  # Called when a message is received from the parent process.
  def receiveMessage(self, channel, message):
    if message['id'] in self.messageMap:
      return self.messageMap[message['id']](channel, message)
    raise Exception('Unhandled message: ' + str(message['id']))

  # Called when the parent process requests safe shutdown.
  def receiveClose(self, channel):
    self.channel.send(Special.Closing)
    self.pump.cancel()

  # Called when the parent connection has died; this will result in the
  # child process terminating.
  def receiveError(self, error):
    pass

# A ParentListener listens for child process messages sent to a parent process.
# The lisener must handle incoming messages; if for any reason it fails to
# process a message, the child process is killed and an error is reported.
# ParentListeners are instantiated manually and given directly to spawn() -
# one listener can be re-used many times.
class ParentProcessListener(object):
  def __init__(self, name):
    super(ParentProcessListener, self).__init__()
    self.name = name
    self.messageMap = {}

  # Called when a connection is being established.
  def receiveConnect(self, child):
    pass

  # Called when a connection has successfully been established.
  def receiveConnected(self, child):
    pass

  # Called when a message has been received. The child is a ProcessHost
  # object corresponding to the parent side of the child process's connection.
  def receiveMessage(self, child, message):
    if message['id'] in self.messageMap:
      return self.messageMap[message['id']](child, message)
    raise Exception('Unhandled message: ' + str(message['id']))

  # Called when an error has occurred and the channel will be closed.
  def receiveError(self, child, error):
    if error != Error.NormalShutdown:
      raise Exception('Unhandled error: ' + error)

# A MessagePump handles multiplexing IPC communication.
class MessagePump(object):
  def __init__(self):
    super(MessagePump, self).__init__()
    self.running = True

    if 'LOG' in os.environ:
      import logging
      logging.basicConfig(level=logging.INFO)

  def close(self):
    pass

  def cancel(self):
    self.running = False

  def shouldProcessEvents(self):
    return self.running

  def pump(self):
    self.running = True
    while self.shouldProcessEvents():
      self.processEvents()

  def processEvents(self):
    raise Exception('must be implemented!')

  # Creates an IPC channel and automatically registers it. When teh channel
  # is closed it is automatically unregistered.
  def createChannel(self, name, listener):
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
    self.closing = None       # not-None Indicates intent to terminate.
    self.proc = proc
    self.channel = channel

  @property
  def pid(self):
    return self.proc.pid

  def send(self, message):
    self.channel.send(message)

  def receiveConnected(self):
    pass

  def is_alive(self):
    return self.proc.is_alive()

  def shutdown(self):
    assert not self.closing is None
    if self.closing != Error.NormalShutdown:
      self.proc.terminate()
    self.proc.join()
    self.channel.close()

# We wrap a listener in between process channels, so we can pass the child
# object instead of the channel. We could probably simplify a bit here by
# using MessageListener's close_on_ack feature.
class ParentWrapperListener(MessageListener):
  def __init__(self, procman, listener):
    super(ParentWrapperListener, self).__init__()
    self.procman = procman
    self.child = None
    self.listener = listener

  @property
  def name(self):
    return self.listener.name

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
      self.child.closing = error
    try:
      self.listener.receiveError(self.child, error)
    except:
      traceback.print_exc()
    self.procman.cleanup(self.child)

# A process manager handles multiplexing IPC communication. It also owns the
# set of child processes. There should only be one ProcessManager per process.
class ProcessManager(object):
  def __init__(self, pump):
    self.pump = pump
    self.children = set()
    self.last_id_ = 1

  def shutdown(self):
    for child in self.children:
      self.close(child)

  # This does not close a process, but requests that it shutdown
  # asynchronously.
  def close(self, child):
    if not child.closing:
      child.channel.send(Special.Close)
      child.closing = Error.NormalShutdown

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

  def cleanup(self, host):
    self.children.remove(host)
    self.close_process(host)

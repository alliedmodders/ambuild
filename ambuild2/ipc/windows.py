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
import struct
import ctypes
import os, sys
import traceback
from collections import deque
from . import process
from . import winapi
from . process import Channel, Error, Special
from ambuild2 import util

def child_main():
  if 'LOG' in os.environ:
    import logging
    logging.basicConfig(level=logging.INFO)

  for index, arg in enumerate(sys.argv):
    if arg == '--name':
      name = sys.argv[index + 1]
    if arg == '--pipe':
      pipe = sys.argv[index + 1]

  # Cygwin seems to lose the initial \ in translation or something.
  if pipe.startswith('\\.\\'):
    pipe = '\\\\.\\' + pipe

  proxy = NamedPipeProxy(name, pipe)
  channel = NamedPipe.from_proxy(proxy)

  from . import impl
  channel.send(Special.Connected)
  impl.child_main(channel)

class NamedPipeProxy(object):
  def __init__(self, name, path):
    self.name = name
    self.path = path

  def close(self):
    pass

kPrefixLength = 4
kChannelsKey = 'channels'

class NamedPipe(Channel):
  def __init__(self, name, handle, path):
    super(NamedPipe, self).__init__(name)
    self.handle = handle
    self.path = path
    self.read_op = winapi.Overlapped()
    self.write_op = None

    # False if nothing is posted to the IOCP
    self.waiting_input = False

    # False if we're not yet connected to the other side.
    self.connected = False

    # Used for receiving data in chunks.
    self.input_buffer = bytearray(4096)
    self.input_obj = (ctypes.c_byte * 4096).from_buffer(self.input_buffer)
    self.input_overflow = bytearray()

  def close(self):
    if self.waiting_input:
      winapi.CancelIo(self.handle)
    if self.write_op:
      winapi.CloseHandle(self.write_op.event())
    winapi.CloseHandle(self.handle)

  def send_impl(self, obj, channels=()):
    if channels and len(channels) and type(obj) is not dict:
      raise Exception('must have dictionary message to send channels')

    if channels:
      assert kChannelsKey not in obj

      # Unlike posix we can cheat here and just send the paths for the pipes.
      proxies = []
      for channel in channels:
        assert type(channel) is NamedPipeProxy
        proxies.append(channel)
      obj[kChannelsKey] = proxies

    # Sends in AMBuild IPC are synchronous, so we must always wait for IO to
    # complete. 
    if not self.write_op:
      self.write_op = winapi.Overlapped()
      self.write_op.hEvent = winapi.CreateEvent(manual=True, initial=False)
      self.write_op.quiet()
    else:
      # Reset the event just in case...? Though in theory it should be reset
      # automatically by WriteFile() if it immediately succeeds.
      winapi.ResetEvent(self.write_op.hEvent)

    # Prepare the data to send. Pad with 4 bytes since bytearray() needs to be
    # at least 8 due to a ctypes bug, and we're going to prepend 4 bytes.
    data = util.pickle.dumps(obj)
    data_bytes = bytearray(data)
    while len(data_bytes) < 8 - kPrefixLength:
      data.append(0)

    prefix = struct.pack('i', len(data))
    data = bytearray(prefix) + data

    buffer = (ctypes.c_byte * len(data)).from_buffer(data)
    nwritten = ctypes.c_int()

    result = winapi.fnWriteFile(
      self.handle,
      ctypes.cast(buffer, ctypes.c_void_p),
      len(data),
      ctypes.byref(nwritten),
      ctypes.cast(ctypes.pointer(self.write_op), ctypes.c_void_p)
    )
    if not result:
      if winapi.GetLastError() != winapi.ERROR_IO_PENDING:
        raise winapi.WinError()

      if not winapi.WaitForSingleObject(self.write_op.hEvent, winapi.INFINITE):
        raise Exception('unexpected return value from WaitForSingleObject()')

    # Done.
    return

  def complete_connection(self, nbytes):
    if not self.waiting_input:
      # We could already be connected, if we're on the child or if the parent
      # has used connect_sync().
      if not self.connected:
        assert nbytes == 0
        if not self.connect_async():
          # Connection hasn't occurred yet, so just keep waiting.
          return False

    # If we got here, we're definitely connected.
    if not self.connected:
      assert nbytes == 0
      self.connected = True
      self.waiting_input = False

    # If we're already waiting for input, but we got 0 bytes, just ignore
    # this event (it's probably faked from our own code).
    if self.waiting_input and not nbytes:
      return False

    self.waiting_input = False
    return True

  def post_read(self):
    bytes_read = ctypes.c_int()
    result = winapi.fnReadFile(
      self.handle,
      ctypes.cast(self.input_obj, ctypes.c_void_p),
      len(self.input_buffer),
      ctypes.byref(bytes_read),
      ctypes.cast(ctypes.pointer(self.read_op), ctypes.c_void_p)
    )

    if not result:
      if winapi.GetLastError() == winapi.ERROR_IO_PENDING:
        self.waiting_input = True
        return None
      raise winapi.WinError()

    # Even if the ReadFile() succeeds, and we have data immediately
    # available, Windows still posts to the IOCP. This makes very little
    # sense to me, but the IOCP API is awful in general. We just return
    # immediately if this is the case, to avoid reading the data twice.
    self.waiting_input = True

  # Respond to a GetQueuedCompletionStatus().
  def complete_incoming_io(self, nbytes):
    if not self.complete_connection(nbytes):
      return []

    if not nbytes:
      self.post_read()
      return []

    messages = []

    message = self.receive_bytes(nbytes)
    if message:
      messages.append(message)
      while True:
        message = self.seek_remaining_message()
        if not message:
          break
        messages.append(message)

    if not self.waiting_input:
      self.post_read()

    # We should always be awaiting input again, otherwise, we'll never receive
    # more events from the IO Completion Port.
    assert self.waiting_input
    return messages

  # Shorthand for complete_incoming_io(0)
  def initiate_io(self):
    if not self.complete_connection(0):
      return
    self.post_read()

  # Process newly received bytes.
  def receive_bytes(self, nbytes):
    total_length = len(self.input_overflow) + nbytes

    # Do we have enough for a message prefix?
    if total_length < 4:
      self.input_overflow += self.input_buffer
      return None

    # Get the message prefix.
    msg_prefix = self.input_overflow[0:kPrefixLength]
    if len(msg_prefix) < kPrefixLength:
      start = len(msg_prefix)
      end = kPrefixLength - start
      msg_prefix = self.input_buffer[start:end]

    # See if we have enough bytes to cover the message.
    msg_size, = struct.unpack('i', bytes(msg_prefix))
    if total_length - kPrefixLength < msg_size:
      self.input_overflow += self.input_buffer
      return None

    # This is a horrible amount of copying... maybe consider using a deque
    # of bytes or something if it's a performance problem.
    if not len(self.input_overflow):
      message = util.pickle.loads(
          bytes(self.input_buffer[kPrefixLength : kPrefixLength + msg_size])
      )
      self.input_overflow += self.input_buffer[kPrefixLength + msg_size : nbytes]
    else:
      # Steal remaining bytes from the input buffer, if needed.
      if len(self.input_overflow) < kPrefixLength + msg_size:
        msg_remaining = kPrefixLength + msg_size - len(self.input_overflow)
        self.input_overflow += self.input_buffer[:msg_remaining]
      else:
        msg_remaining = 0

      message = util.pickle.loads(
        bytes(self.input_overflow[kPrefixLength : kPrefixLength + msg_size])
      )

      # Adjust the input buffer.
      del self.input_overflow[0 : kPrefixLength + msg_size]
      self.input_overflow += self.input_buffer[msg_remaining : nbytes]

    return message

  # Process any remaining messages.
  def seek_remaining_message(self):
    if len(self.input_overflow) < kPrefixLength:
      return None

    msg_size, = struct.unpack('i', bytes(self.input_overflow[0:kPrefixLength]))
    if len(self.input_overflow) < kPrefixLength + msg_size:
      return None

    message = util.pickle.loads(
      bytes(self.input_overflow[kPrefixLength : kPrefixLength + msg_size])
    )
    del self.input_overflow[0 : kPrefixLength + msg_size]

    return message

  def connect_async(self):
    result = winapi.fnConnectNamedPipe(self.handle, ctypes.byref(self.read_op))
    assert not result # MSDN says this is impossible with async pipes

    gle = winapi.GetLastError()
    if gle == winapi.ERROR_PIPE_CONNECTED:
      assert not self.waiting_input
      return True

    if gle != winapi.ERROR_IO_PENDING:
      raise winapi.WinError()

    return False

  def connect_sync(self, proc_handle):
    event = winapi.CreateEvent(manual=True, initial=False)

    # Suppress completion status posting, since this overlapped is temporary.
    overlapped = winapi.Overlapped(event)
    overlapped.quiet()

    try:
      result = winapi.fnConnectNamedPipe(self.handle, ctypes.byref(overlapped))
      assert not result # MSDN says this is impossible with async pipes

      gle = winapi.GetLastError()
      if gle != winapi.ERROR_PIPE_CONNECTED:
        if gle != winapi.ERROR_IO_PENDING:
          raise winapi.WinError()


        # We need to wait for either process death or for pipe connection.
        result = winapi.WaitForMultipleObjects(
          handles=[overlapped.hEvent, proc_handle],
          wait_all=False,
          wait=winapi.INFINITE
        )

        if result != winapi.WAIT_OBJECT_0:
          if result == winapi.WAIT_OBJECT_0 + 1:
            raise Exception('child process died before connecting to pipe')
          raise Exception('unexpected WaitForMultipleObjects return code: {0}'.format(result))
    finally:
      winapi.CloseHandle(event)

    # Fake this to true so we don't try to connect asynchronously.
    self.connected = True
    self.initiate_io()

  @classmethod
  def from_proxy(cls, proxy):
    handle = winapi.OpenPipe(proxy.path)
    pipe = cls(proxy.name, handle, proxy.path)
    pipe.connected = True
    return pipe

  @classmethod
  def connect(cls, channel, name):
    pipe = cls.from_proxy(channel)
    pipe.name = name
    pipe.send(Special.Connected)
    return pipe

  @classmethod
  def new(cls, name):
    pipe, path = winapi.CreateNamedPipe()
    parent = cls(name, pipe, path)
    child = NamedPipeProxy(name, path)
    return parent, child

class MessagePump(process.MessagePump):
  def __init__(self):
    super(MessagePump, self).__init__()
    self.port = winapi.CreateIoCompletionPort()
    self.listeners = {}
    self.channels = {}
    self.next_key = 0
    self.pending = deque()

  def close(self):
    super(MessagePump, self).close()
    winapi.CloseHandle(self.port)

  def shouldProcessEvents(self):
    if not super(MessagePump, self).shouldProcessEvents():
      return False
    return len(self.channels) or len(self.pending)

  def createChannel(self, name):
    return NamedPipe.new(name)

  def registerChannel(self, channel, listener):
    assert channel.handle.value not in self.channels

    key = self.next_key
    self.next_key += 1

    winapi.RegisterIoCompletion(self.port, channel.handle, key)
    self.listeners[key] = channel, listener
    self.channels[channel.handle.value] = key
    return key

  def addChannel(self, channel, listener):
    key = self.registerChannel(channel, listener)

    # On Windows, we must initiate a recv() that would block in order to
    # receive io completion events. Since that could return actual data,
    # we enqueue these back into the message loop.
    channel.initiate_io()

  def dropChannel(self, channel):
    key = self.channels[channel.handle.value]
    del self.channels[channel.handle.value]
    del self.listeners[key]

  def processMessage(self, message, channel, listener):
    if message == Special.Closing:
      self.handle_channel_error(channel, listener, Error.NormalShutdown)
      return

    try:
      listener.receiveMessage(channel, message)
    except Exception as exn:
      traceback.print_exc()
      self.handle_channel_error(channel, listener, Error.User)

  def processEvents(self):
    if not self.pending:
      if not self.poll_io_port():
        return

    if not self.pending:
      return

    key, message = self.pending.popleft()
    if key not in self.listeners:
      return

    channel, listener = self.listeners[key]
    self.processMessage(message, channel, listener)

  def poll_io_port(self):
    result, nbytes, key, overlapped = winapi.GetQueuedCompletionStatus(self.port, winapi.INFINITE)

    # There is no way to remove a file from a completion port, so just as a
    # precaution, we check this.
    if key.value not in self.listeners:
      return False

    address = ctypes.addressof(overlapped)
    channel, listener = self.listeners[key.value]

    # We only care about read events, so if we're receiving some kind of white
    # hot lie, assert.
    if ctypes.addressof(channel.read_op) != address:
      raise Exception('unexpected IO completion on {0}'.format(listener.name))

    if not result:
      self.handle_channel_error(channel, listener, Error.EOF)
      return False

    messages = None
    try:
      messages = channel.complete_incoming_io(nbytes=nbytes.value)
    except WindowsError as exn:
      if exn.winerror != winapi.ERROR_BROKEN_PIPE:
        traceback.print_exc()
    except Exception as exn:
      traceback.print_exc()

    if messages is None:
      self.handle_channel_error(channel, listener, Error.EOF)
      return

    for message in messages:
      self.pending.append((key.value, message))

    # Finished processing this status change.
    return True

  def handle_channel_error(self, channel, listener, error):
    self.dropChannel(channel)
    listener.receiveError(channel, error)

class ProcessHost(process.ProcessHost):
  def __init__(self, id, proc, channel):
    super(ProcessHost, self).__init__(id, proc, channel)

class ProcessManager(process.ProcessManager):
  def __init__(self, pump):
    super(ProcessManager, self).__init__(pump)

  def create_process_and_pipe(self, id, listener):
    # Create pipes.
    parent, child = NamedPipe.new(listener.name)

    # Spawn the process.
    proc = winapi.Process.spawn(child)

    # Watch for changes on the parent channel. We don't use addChannel(), since
    # that will try to asynchronously connect. We want synchronous connections.
    self.pump.registerChannel(parent, listener)

    # Require synchronous connection or process death.
    parent.connect_sync(proc.handle)

    return ProcessHost(id, proc, parent)

  def close_process(self, host):
    pass

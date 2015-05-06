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
import socket
import signal
import os, sys, fcntl
from ambuild2 import util
from . process import Channel, ProcessHost, Special, MessagePump

kStartFd = 3

class iovec_t(ctypes.Structure):
  _fields_ = [
    ('iov_base', ctypes.c_void_p),
    ('iov_len', ctypes.c_size_t)
  ]

# Note that msg_socklen_t is not really socklen_t. Darwin uses socklen_t but
# Linux uses size_t, so we alias that.

def Align(n, a):
  return (n + a - 1) & ~(a - 1)

if util.IsMac():
  sLibC = ctypes.CDLL('libc.dylib', use_errno=True)

  posix_spawn_file_actions_t = ctypes.c_void_p
  pid_t = ctypes.c_int
  msg_socklen_t = ctypes.c_uint
  SOL_SOCKET = 0xffff
  SCM_RIGHTS = 1
  MSG_NOSIGNAL = 0  # Not supported.
  MSG_CTRUNC = 0x20

  def CMSG_NXTHDR(msg, cmsg):
    cmsg_len = cmsg.contents.cmsg_len
    if cmsg_len < ctypes.sizeof(cmsghdr_base_t):
      return None
    
    cmsg_len = Align(cmsg_len, ctypes.sizeof(ctypes.c_uint))
    addr = ctypes.addressof(cmsg.contents) + cmsg_len
    check = addr + Align(ctypes.sizeof(cmsghdr_base_t), ctypes.sizeof(ctypes.c_uint))
    if check > msg.msg_control + msg.msg_controllen:
      return None

    return ctypes.cast(addr, cmsghdr_base_t_p)

elif util.IsLinux():
  sLibC = ctypes.CDLL('libc.so.6', use_errno=True)

  pid_t = ctypes.c_int
  msg_socklen_t = ctypes.c_size_t
  SOL_SOCKET = 1
  SCM_RIGHTS = 1
  MSG_NOSIGNAL = 0x4000
  MSG_CTRUNC = 0x8

  class posix_spawn_file_actions_t(ctypes.Structure):
    _fields_ = [
      ('allocated', ctypes.c_int),
      ('used', ctypes.c_int),
      ('spawn_action', ctypes.c_void_p),
      ('pad', ctypes.c_int * 16)
    ]

  def CMSG_NXTHDR(msg, cmsg):
    cmsg_len = cmsg.contents.cmsg_len
    if cmsg_len < ctypes.sizeof(cmsghdr_base_t):
      return None
    
    cmsg_len = Align(cmsg_len, ctypes.sizeof(ctypes.c_size_t))
    addr = ctypes.addressof(cmsg.contents) + cmsg_len
    if addr + ctypes.sizeof(cmsghdr_base_t) > msg.msg_control + msg.msg_controllen:
      return None

    cmsg = ctypes.cast(addr, cmsghdr_base_t_p)
    if addr + cmsg.contents.cmsg_len > msg.msg_control + msg.msg_controllen:
      return None

    return cmsg

elif util.IsFreeBSD():
  sLibC = ctypes.CDLL('libc.so.7', use_errno=True)
  if not sLibC:
    sLibC = ctypes.CDLL('libc.so.6', use_errno=True)
  if not sLibC:
    raise Exception('Could not find a suitable libc binary')

  posix_spawn_file_actions_t = ctypes.c_void_p
  pid_t = ctypes.c_int
  msg_socklen_t = ctypes.c_uint
  SOL_SOCKET = 0xffff
  SCM_RIGHTS = 1
  MSG_NOSIGNAL = 0x20000
  MSG_CTRUNC = 0x20

  def CMSG_NXTHDR(msg, cmsg):
    cmsg_len = cmsg.contents.cmsg_len
    cmsg_len = Align(cmsg_len, ctypes.sizeof(ctypes.c_uint))

    addr = ctypes.addressof(cmsg.contents) + cmsg_len
    check = addr + Align(ctypes.sizeof(cmsghdr_base_t), ctypes.sizeof(ctypes.c_uint))
    if check > msg.msg_control + msg.msg_controllen:
      return None

    return ctypes.cast(addr, cmsghdr_base_t_p)

elif util.IsOpenBSD():
  for lib in os.listdir('/usr/lib'):
    if not lib.startswith('libc.so'):
      continue
    sLibC = ctypes.CDLL(lib, use_errno=True)
    if sLibC:
      break
  if not sLibC:
    raise Exception('Could not find a suitable libc binary')

  posix_spawn_file_actions_t = ctypes.c_void_p
  pid_t = ctypes.c_int
  msg_socklen_t = ctypes.c_uint
  SOL_SOCKET = 0xffff
  SCM_RIGHTS = 1
  MSG_NOSIGNAL = 0x400
  MSG_CTRUNC = 0x20

  def CMSG_NXTHDR(msg, cmsg):
    cmsg_len = cmsg.contents.cmsg_len
    cmsg_len = Align(cmsg_len, ctypes.sizeof(ctypes.c_size_t))

    addr = ctypes.addressof(cmsg.contents) + cmsg_len
    check = addr + Align(ctypes.sizeof(cmsghdr_base_t), ctypes.sizeof(ctypes.c_size_t))
    if check > msg.msg_control + msg.msg_controllen:
      return None

    return ctypes.cast(addr, cmsghdr_base_t_p)

elif util.IsSolaris():
  sLibC = ctypes.CDLL('libc.so', use_errno=True)

  class posix_spawn_file_actions_t(ctypes.Structure):
    _fields_ = [
      ('__file_attrp', ctypes.c_void_p),
    ]

  pid_t = ctypes.c_int
  msg_socklen_t = ctypes.c_uint
  SOL_SOCKET = 0xffff
  SCM_RIGHTS = 0x1010
  MSG_NOSIGNAL = 0
  MSG_CTRUNC = 0x10

  def CMSG_NXTHDR(msg, cmsg):
    cmsg_len = cmsg.contents.cmsg_len

    addr = ctypes.addressof(cmsg.contents)
    check = Align(addr + cmsg_len + ctypes.sizeof(cmsghdr_base_t), ctypes.sizeof(ctypes.c_int))
    if check > msg.msg_control + msg.msg_controllen:
      return None

    return ctypes.cast(Align(addr + cmsg_len, ctypes.sizeof(ctypes.c_int)), cmsghdr_base_t_p)

elif util.IsNetBSD():
  sLibC = None
  for lib in os.listdir('/usr/lib'):
    if not lib.startswith('libc.so'):
      continue
    sLibC = ctypes.CDLL(lib, use_errno=True)
    if sLibC:
      break
  if not sLibC:
    raise Exception('Could not find a suitable libc binary')

  posix_spawn_file_actions_t = ctypes.c_void_p
  pid_t = ctypes.c_int
  msg_socklen_t = ctypes.c_uint
  SOL_SOCKET = 0xffff
  SCM_RIGHTS = 1
  MSG_NOSIGNAL = 0x400
  MSG_CTRUNC = 0x20

  __ALIGNBYTES = ctypes.sizeof(ctypes.c_size_t)
  def __CMSG_ALIGN(n):
    return (n + __ALIGNBYTES) & ~__ALIGNBYTES

  def CMSG_NXTHDR(msg, cmsg):
    cmsg_len = __CMSG_ALIGN(cmsg.contents.cmsg_len)
    cmsg_hdr_size = __CMSG_ALIGN(ctypes.sizeof(cmsghdr_base_t))
    addr = ctypes.addressof(cmsg.contents)

    if addr + cmsg_len + cmsg_hdr_size > msg.msg_control + msg.msg_controllen:
      return None

    return ctypes.cast(addr + cmsg_len, cmsghdr_base_t_p)

if hasattr(ctypes, 'c_ssize_t'):
  ssize_t = ctypes.c_ssize_t
else:
  if ctypes.sizeof(ctypes.c_size_t) == 8:
    ssize_t = ctypes.c_longlong
  else:
    ssize_t = ctypes.c_int

posix_spawnp = sLibC.posix_spawnp
posix_spawnp.argtypes = [
  ctypes.c_void_p, # pid_t *pid
  ctypes.c_char_p, # const char *file
  ctypes.c_void_p, # const posix_spawn_file_actions_t *file_actions
  ctypes.c_void_p, # const posix_spawnttr_t *attrp,
  ctypes.c_void_p, # char *const argv[],
  ctypes.c_void_p  # char *const envp[]
]
posix_spawnp.restype = ctypes.c_int

posix_spawn_file_actions_init = sLibC.posix_spawn_file_actions_init
posix_spawn_file_actions_init.argtypes = [ctypes.c_void_p]
posix_spawn_file_actions_init.restype = ctypes.c_int
posix_spawn_file_actions_destroy = sLibC.posix_spawn_file_actions_destroy
posix_spawn_file_actions_destroy.argtypes = [ctypes.c_void_p]
posix_spawn_file_actions_destroy.restype = ctypes.c_int
posix_spawn_file_actions_adddup2 = sLibC.posix_spawn_file_actions_adddup2
posix_spawn_file_actions_adddup2.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int]
posix_spawn_file_actions_adddup2.restype = ctypes.c_int

def check_errno(res):
  if res < 0:
    n = ctypes.get_errno()
    raise OSError(n, os.strerror(n))

def SetNonBlocking(fd):
  fcntl.fcntl(fd, fcntl.F_SETFL, os.O_NONBLOCK)

def SetCloseOnExec(fd):
  flags = fcntl.fcntl(fd, fcntl.F_GETFD)
  fcntl.fcntl(fd, fcntl.F_SETFD, flags|fcntl.FD_CLOEXEC)

class msghdr_t(ctypes.Structure):
  _fields_ = [
    ('msg_name', ctypes.c_void_p),
    ('msg_namelen', ctypes.c_int),
    ('msg_iov', ctypes.POINTER(iovec_t)),
    ('msg_iovlen', msg_socklen_t),
    ('msg_control', ctypes.c_void_p),
    ('msg_controllen', msg_socklen_t),
    ('msg_flags', ctypes.c_int)
  ]

  def __init__(self):
    super(msghdr_t, self).__init__()

class cmsghdr_base_t(ctypes.Structure):
  _fields_ = [
    ('cmsg_len', msg_socklen_t),
    ('cmsg_level', ctypes.c_int),
    ('cmsg_type', ctypes.c_int)
  ]

  def __init__(self):
    super(cmsghdr_base_t, self).__init__()

cmsghdr_base_t_p = ctypes.POINTER(cmsghdr_base_t)

def cmsghdr_type_for_n(n):
  class cmsghdr_t(ctypes.Structure):
    _fields_ = cmsghdr_base_t._fields_ + [
      ('cmsg_data', ctypes.c_int * n)
    ]

    def __init__(self):
      super(cmsghdr_t, self).__init__()

  size = 0
  for name, type in cmsghdr_t._fields_:
    size += ctypes.sizeof(type)
  return cmsghdr_t, size

def cmsghdr_t(n):
  cmsghdr, cmsg_len = cmsghdr_type_for_n(n)
  cmsg = cmsghdr()
  cmsg.cmsg_level = SOL_SOCKET
  cmsg.cmsg_type = SCM_RIGHTS
  cmsg.cmsg_len = cmsg_len
  return cmsg

if util.IsSolaris():
  sendmsg = sLibC._so_sendmsg
else:
  sendmsg = sLibC.sendmsg
sendmsg.argtypes = [
  ctypes.c_int,             # sockfd
  ctypes.POINTER(msghdr_t), # msg
  ctypes.c_int              # flags
]
sendmsg.restype = ssize_t

if util.IsSolaris():
  recvmsg = sLibC._so_recvmsg
else:
  recvmsg = sLibC.recvmsg
recvmsg.argtypes = [
  ctypes.c_int,             # sockfd
  ctypes.POINTER(msghdr_t), # msg
  ctypes.c_int              # flags
]
recvmsg.restype = ssize_t

class SocketChannel(Channel):
  def __init__(self, name, sock):
    super(SocketChannel, self).__init__(name)
    self.sock = sock
    SetCloseOnExec(self.sock.fileno())

  @classmethod
  def connect(cls, channel, name):
    channel.name = name
    channel.send(Special.Connected)
    return channel

  # On POSIX, recv() is synchronous.
  def recv(self):
    message = self.recv_impl()
    self.log_recv(message)
    return message

  def close(self):
    #print('{0} Closing socket: {1}'.format(os.getpid(), self.sock.fileno()))
    #traceback.print_stack()
    self.sock.close()

  def closed(self):
    return self.sock.fileno() == -1

  def recv_all(self, nbytes):
    b = bytes()
    while len(b) < nbytes:
      new_bytes = self.sock.recv(nbytes - len(b))
      if len(new_bytes) == 0:
        if len(b) == 0:
          return None
        raise Exception('socket closed')
      b += new_bytes
    return b

  def send_impl(self, obj, channels=None):
    data = util.pickle.dumps(obj)

    # If no channels, just send the data.
    if not channels:
      self.sock.sendall(struct.pack('ii', len(data), 0))
      self.sock.sendall(data)
      return

    # Construct the actual message.
    buf = bytearray(data)
    while len(buf) < 8:
      # Work around a Python bug where we need at least 8 bytes.
      buf.append(0)

    # Send the data length and # of channels.
    self.sock.sendall(struct.pack('ii', len(buf), len(channels)))

    cmsg = cmsghdr_t(len(channels))
    for index, channel in enumerate(channels):
      cmsg.cmsg_data[index] = channel.fd

    buffer_t = ctypes.c_byte * len(buf)
    iov_base = buffer_t.from_buffer(buf)

    iovec = iovec_t()
    iovec.iov_base = ctypes.addressof(iov_base)
    iovec.iov_len = len(buf)

    msg = msghdr_t()
    msg.msg_name = None
    msg.msg_namelen = 0
    msg.msg_iov = ctypes.pointer(iovec)
    msg.msg_iovlen = 1
    msg.msg_control = ctypes.addressof(cmsg)
    msg.msg_controllen = cmsg.cmsg_len
    msg.msg_flags = 0

    res = sendmsg(self.sock.fileno(), ctypes.pointer(msg), MSG_NOSIGNAL)
    check_errno(res)

    # On Linux, it's now safe to close all the channels we just sent.
    if util.IsLinux():
      for channel in channels:
        channel.close()

  def recv_impl(self):
    header = self.recv_all(8)
    if header == None:
      return None

    size, nfds = struct.unpack('ii', header)
    if nfds == 0:
      data = self.recv_all(size)
      return util.pickle.loads(data)

    iov_base = (ctypes.c_byte * size)()

    iovec = iovec_t()

    msg = msghdr_t()
    msg.msg_iov = ctypes.pointer(iovec)
    msg.msg_iovlen = 1

    # Construct a buffer for the ancillary data. This is pretty arbitrary.
    cmsg_base = (ctypes.c_byte * 512)()
    msg.msg_control = ctypes.cast(cmsg_base, ctypes.c_void_p)

    channels = []

    received = 0
    while received < size:
      iovec.iov_base = ctypes.addressof(iov_base) + received
      iovec.iov_len = size - received
      msg.msg_controllen = len(cmsg_base)

      res = recvmsg(self.sock.fileno(), ctypes.pointer(msg), 0)
      check_errno(res)

      received += res

      if msg.msg_flags & MSG_CTRUNC:
        raise Exception('message control or ancillary data was truncated')

      # Min struct size is 12.
      if msg.msg_controllen >= 12:
        cmsg = ctypes.cast(msg.msg_control, cmsghdr_base_t_p)
        while cmsg:
          if cmsg.contents.cmsg_level == SOL_SOCKET and cmsg.contents.cmsg_type == SCM_RIGHTS:
            # Grab the file descriptors.
            wire_fds = (cmsg.contents.cmsg_len - ctypes.sizeof(cmsg.contents)) // 4
            cmsg_t, cmsg_len = cmsghdr_type_for_n(wire_fds)
            cmsg_t_p = ctypes.POINTER(cmsg_t)
            cmsg = ctypes.cast(ctypes.addressof(cmsg.contents), cmsg_t_p)
            for i in range(wire_fds):
              fd = cmsg.contents.cmsg_data[i]
              channel = SocketChannel.fromfd('<recvd-unknown>', fd)
              channels.append(channel)
            
          cmsg = CMSG_NXTHDR(msg, cmsg)

    if nfds != len(channels):
      raise Exception('expected ' + str(nfds) + ' channels, received ' + str(len(channels)))

    if bytes == str:
      message = util.Unpickle(ctypes.cast(iov_base, ctypes.c_char_p).value)
    else:
      message = util.Unpickle(bytes(iov_base))
    message['channels'] = tuple(channels)
    return message

  @property
  def fd(self):
    return self.sock.fileno()

  @classmethod
  def fromfd(cls, name, fd):
    sock = socket.fromfd(fd, socket.AF_UNIX, socket.SOCK_STREAM)
    os.close(fd)
    return SocketChannel(name, sock)

  @classmethod
  def pair(cls, name):
    parent, child = socket.socketpair(socket.AF_UNIX, socket.SOCK_STREAM)

    # We don't set non-blocking (right now), it shouldn't be needed because
    # communication tends to be modal for a given pipe, and we wait until
    # reads would not block to begin reading.
    return SocketChannel(name + 'Parent', parent), SocketChannel(name + 'Child', child)

def child_main(name):
  if 'LOG' in os.environ:
    import logging
    logging.basicConfig(level=logging.INFO)

  from . import impl
  channel = SocketChannel.fromfd(name, kStartFd)
  channel.send(Special.Connected)
  impl.child_main(channel)

# We keep the child's socket fd alive until we get an ACK, since fork() is
# asynchronous and we need to keep the fd alive.
class PosixHost(ProcessHost):
  def __init__(self, id, proc, parent, child):
    super(PosixHost, self).__init__(id, proc, parent)
    self.child_channel = child

  def receiveConnected(self):
    super(PosixHost, self).receiveConnected()
    if self.child_channel:
      self.child_channel.close()
      self.child_channel = None

  def shutdown(self):
    super(PosixHost, self).shutdown()
    if self.child_channel:
      self.child_channel.close()
      self.child_channel = None

class Process(object):
  def __init__(self, pid):
    self.pid = pid
    self.returncode = None

  def is_alive(self):
    if self.returncode != None:
      return False

    pid, rc = os.waitpid(self.pid, os.WNOHANG)
    if pid != self.pid:
      return True

    self.returncode = rc
    return False

  def terminate(self):
    if not self.returncode is None:
      return

    os.kill(self.pid, signal.SIGTERM)

  def join(self):
    if self.returncode != None:
      return
    pid, rc = os.waitpid(self.pid, 0)
    assert pid == self.pid
    self.returncode = rc

  @classmethod
  def spawn(cls, channel):
    pid = pid_t()
    file_actions = ctypes.pointer(posix_spawn_file_actions_t())
    res = posix_spawn_file_actions_init(file_actions)
    check_errno(res)

    exe = ctypes.c_char_p(util.str2b(sys.executable))

    # Bind 
    remap = (
      (channel.fd, kStartFd),
    )
    for fromfd, tofd in remap:
      res = posix_spawn_file_actions_adddup2(file_actions, fromfd, tofd)
      check_errno(res)

    envp = (ctypes.c_char_p * (len(os.environ) + 1))()
    for index, key in enumerate(os.environ.keys()):
      export = key + '=' + os.environ[key]
      envp[index] = ctypes.c_char_p(util.str2b(export))
    envp[len(os.environ)] = None

    # Create argv.
    argv = [
      sys.executable,
      '-c',
      'import sys; from ambuild2.ipc.posix_proc import child_main; child_main("{0}")'.format(channel.name)
    ]

    c_argv = (ctypes.c_char_p * (len(argv) + 1))()
    for index, arg in enumerate(argv):
      c_argv[index] = ctypes.c_char_p(util.str2b(arg))
    c_argv[len(argv)] = None

    res = posix_spawnp(
      ctypes.pointer(pid),
      exe,
      file_actions,
      None,
      ctypes.cast(c_argv, ctypes.c_void_p),
      ctypes.cast(envp, ctypes.c_void_p)
    )
    check_errno(res)

    posix_spawn_file_actions_destroy(file_actions)

    return cls(pid.value)


class PosixMessagePump(MessagePump):
  def __init__(self):
    self.fdmap = {}
    super(PosixMessagePump, self).__init__()

  def createChannel(self, name):
    parent, child = SocketChannel.pair(name)
    return parent, child

  def handle_channel_error(self, channel, listener, error):
    self.dropChannel(channel)
    listener.receiveError(channel, error)

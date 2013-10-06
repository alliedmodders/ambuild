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
import struct
import ctypes
import socket
import signal
from .process import Channel 
import os, sys, fcntl

kStartFd = 3

if util.IsMac():
  sLibC = ctypes.CDLL('libc.dylib', use_errno=True)
  posix_spawn_file_actions_t = ctypes.c_void_p
  pid_t = ctypes.c_int
elif util.IsLinux():
  sLibC = ctypes.CDLL('libc.so.6', use_errno=True)
  class posix_spawn_file_actions_t(ctypes.Structure):
    def __init__(self):
      super(posix_spawn_file_actions_t, self).__init__()
  posix_spawn_file_actions_t._fields_ = [
    ('allocated', ctypes.c_int),
    ('used', ctypes.c_int),
    ('spawn_action', ctypes.c_void_p),
    ('pad', ctypes.c_int * 16)
  ]
  pid_t = ctypes.c_int

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

class SocketChannel(Channel):
  def __init__(self, sock):
    super(SocketChannel, self).__init__()
    self.sock = sock
    SetCloseOnExec(self.sock.fileno())

  def close(self):
    self.sock.close()

  def recv_all(self, nbytes):
    b = bytes()
    while len(b) < nbytes:
      b += self.sock.recv(nbytes - len(b))
    return b

  def send(self, obj, channels=None):
    assert not channels
    data = util.pickle.dumps(obj)
    self.sock.sendall(struct.pack('i', len(data)))
    self.sock.sendall(data)

  def recv(self):
    header = self.recv_all(4)
    size, = struct.unpack('i', header)
    data = self.recv_all(size)
    return util.pickle.loads(data)

  @property
  def fd(self):
    return self.sock.fileno()

  @classmethod
  def fromfd(cls, fd):
    sock = socket.fromfd(fd, socket.AF_UNIX, socket.SOCK_STREAM)
    os.close(fd)
    return SocketChannel(sock)

  @classmethod
  def pair(cls):
    parent, child = socket.socketpair(socket.AF_UNIX, socket.SOCK_STREAM)

    # We don't set non-blocking (right now), it shouldn't be needed because
    # communication tends to be modal for a given pipe, and we wait until
    # reads would not block to begin reading.
    return SocketChannel(parent), SocketChannel(child)

def child_main():
  from . import impl
  channel = SocketChannel.fromfd(kStartFd)
  impl.child_main(channel)

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
    if self.returncode is None:
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

    exe = ctypes.c_char_p(bytes(sys.executable, 'utf8'))

    # Bind 
    res = posix_spawn_file_actions_adddup2(file_actions, channel.fd, kStartFd)
    check_errno(res)
    envp = (ctypes.c_char_p * (len(os.environ) + 1))()
    for index, key in enumerate(os.environ.keys()):
      export = key + '=' + os.environ[key]
      envp[index] = ctypes.c_char_p(bytes(export, 'utf8'))
    envp[len(os.environ)] = None

    # Create argv.
    argv = [sys.executable, '-c', 'from ipc.posix_proc import child_main; child_main()']

    c_argv = (ctypes.c_char_p * (len(argv) + 1))()
    for index, arg in enumerate(argv):
      c_argv[index] = ctypes.c_char_p(bytes(arg, 'utf8'))
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

if __name__ == '__main__':
  parent, child = SocketChannel.pair()
  parent.send('egg')
  Process.spawn(child)
  while True:
    pass

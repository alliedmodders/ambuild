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
import ctypes
import os, sys
from ambuild2 import util

handle_t = ctypes.c_void_p
handlep_t = ctypes.POINTER(handle_t)
if ctypes.sizeof(handle_t) == 4:
  INVALID_HANDLE_VALUE = 0xffffffff
elif ctypes.sizeof(handle_t) == 8:
  INVALID_HANDLE_VALUE = 0xffffffffffffffff
INVALID_HANDLE = handle_t(INVALID_HANDLE_VALUE)

LANG_NEUTRAL = 0x00
SUBLANG_DEFAULT = 0x01

def MAKELANGID(primary, sub):
  return (sub << 10) | primary

if sys.platform != 'cygwin':
  from ctypes import WinError
  WINDLL = ctypes.windll

  def sys_executable():
    return sys.executable
else:
  import subprocess

  WINDLL = ctypes.cdll

  sys_executable_ = None
  def sys_executable():
    global sys_executable_
    if not sys_executable_:
      output = subprocess.check_output(['cygpath', '-w', sys.executable])
      sys_executable_ = output.strip() + '.exe'
    return sys_executable_

  class WindowsError(Exception):
    def __init__(self, errno, message):
      self.winerror = errno
      Exception.__init__(self, message)

  def WinError():
    error = GetLastError()
    buffer = ctypes.create_string_buffer(4096)

    rval = fnFormatMessage(
      FORMAT_MESSAGE_FROM_SYSTEM | FORMAT_MESSAGE_IGNORE_INSERTS,
      None,
      error,
      MAKELANGID(LANG_NEUTRAL, SUBLANG_DEFAULT),
      ctypes.cast(buffer, ctypes.c_void_p),
      ctypes.sizeof(buffer),
      None
    )
    if rval == 0:
      raise Exception('system error {0} while reporting system error {1}'.format(GetLastError(), error))

    raise WindowsError(error, buffer.value)

fnCreateNamedPipeA = WINDLL.kernel32.CreateNamedPipeA
fnCreateNamedPipeA.argtypes = [
  ctypes.c_char_p,          # LPCTSTR lpName
  ctypes.c_int,             # DWORD dwOpenMode
  ctypes.c_int,             # DWORD dwPipeMode
  ctypes.c_int,             # DWORD nMaxInstances
  ctypes.c_int,             # DWORD nOutBufferSize
  ctypes.c_int,             # DWORD nInBufferSize,
  ctypes.c_int,             # DWORD nDefaultTimeOut
  ctypes.c_void_p           # LPSECURITY_ATTRIBUTES lpSecurityAttributes
]
fnCreateNamedPipeA.restype = handle_t

fnCreateFileA = WINDLL.kernel32.CreateFileA
fnCreateFileA.argtypes = [
  ctypes.c_char_p,          # LPCTSTR lpFileName
  ctypes.c_int,             # DWORD dwDesiredAccess
  ctypes.c_int,             # DWORD dwShareMode
  ctypes.c_void_p,          # LPSECURITY_ATTRIBUTES lpSecurityAttributes
  ctypes.c_int,             # DWORD dwCreationDisposition
  ctypes.c_int,             # DWORD dwFlagsAndAttributes
  handle_t                  # HANDLE hTempateFile
]
fnCreateFileA.restype = handle_t

fnCloseHandle = WINDLL.kernel32.CloseHandle
fnCloseHandle.argtypes = [ handle_t ]
fnCloseHandle.restype = ctypes.c_int

class Overlapped(ctypes.Structure):
  _fields_ = [
    ('Internal',      ctypes.c_void_p),
    ('InternalHigh',  ctypes.c_void_p),

    # This is technically a union of 8 bytes and a pointer, so it's always
    # 8 bytes on every platform.
    ('Offset',        ctypes.c_int),
    ('OffsetHigh',    ctypes.c_int),

    ('hEvent',        handle_t)
  ]

  def __init__(self, event=handle_t()):
    super(Overlapped, self).__init__()
    self.hEvent = event

  def quiet(self):
    # This prevents notifying IO completion ports.
    self.hEvent = ctypes.cast(ctypes.c_void_p(self.hEvent | 1), handle_t)

  def event(self):
    return ctypes.cast(ctypes.c_void_p((self.hEvent.value >> 1) << 1), handle_t)

# Given the occasional shitfest that is ctypes, it doesn't work to byref() a
# struct. We have to keep the POINTER type around and use from_address.
LPOVERLAPPED = ctypes.POINTER(Overlapped)

fnCreateIoCompletionPort = WINDLL.kernel32.CreateIoCompletionPort
fnCreateIoCompletionPort.argtypes = [
  handle_t,                 # HANDLE FileHandle
  handle_t,                 # HANDLE ExistingCompletionPort
  ctypes.c_size_t,          # ULONG_PTR CompletionKey
  ctypes.c_int              # DWORD NumberOfConcurrentThreads
]
fnCreateIoCompletionPort.restype = handle_t

fnGetQueuedCompletionStatus = WINDLL.kernel32.GetQueuedCompletionStatus
fnGetQueuedCompletionStatus.argtypes = [
  handle_t,                         # HANDLE CompletionPort
  ctypes.POINTER(ctypes.c_int),     # LPDWORD
  ctypes.POINTER(ctypes.c_size_t),  # PULONG_PTR lpCompletionKey
  ctypes.POINTER(ctypes.c_void_p),  # LPOVERLAPPED *lpOverlapped
  ctypes.c_int                      # DWORD
]
fnGetQueuedCompletionStatus.restype = ctypes.c_int

fnCreateProcessA = WINDLL.kernel32.CreateProcessA
fnCreateProcessA.argtypes = [
  ctypes.c_char_p,          # LPCTSTR lpApplicationName
  ctypes.c_char_p,          # LPTSTR lpCommandLine
  ctypes.c_void_p,          # LPSECURITY_ATTRIBUTES lpProcessAttributes
  ctypes.c_void_p,          # LPSECURITY_ATTRIBUTES lpThreadAttributes
  ctypes.c_int,             # BOOL bInheritHandles
  ctypes.c_int,             # DWORD dwCreationFlags
  ctypes.c_void_p,          # lpEnvironment
  ctypes.c_char_p,          # lpCurrentDirectory
  ctypes.c_void_p,          # lpStartupInfo
  ctypes.c_void_p           # LPPROCESS_INFORMATION lpProcessInformation
]
fnCreateProcessA.restype = ctypes.c_int

fnDuplicateHandle = WINDLL.kernel32.DuplicateHandle
fnDuplicateHandle.argtypes = [
  handle_t,                 # hSourceProcessHandle
  handle_t,                 # hSourceHandle,
  handle_t,                 # hTargetProcessHandle
  handlep_t,                # lpTargetHandle,
  ctypes.c_int,             # dwDesiredAccess
  ctypes.c_int,             # bInheritHandle
  ctypes.c_int              # dwOptions
]
fnDuplicateHandle.restype = ctypes.c_int

fnGetCurrentProcess = WINDLL.kernel32.GetCurrentProcess
fnGetCurrentProcess.restype = handle_t

fnGetStdHandle = WINDLL.kernel32.GetStdHandle
fnGetStdHandle.argtypes = [ ctypes.c_int ]
fnGetStdHandle.restype = handle_t

fnWriteFile = WINDLL.kernel32.WriteFile
fnWriteFile.argtypes = [
  handle_t,                         # HANDLE hFile,
  ctypes.c_void_p,                  # LPCVOID lpBuffer
  ctypes.c_int,                     # DWORD nNumberOfBytesToWrite
  ctypes.POINTER(ctypes.c_int),     # LPDWORD lpNumberOfBytesWritten
  ctypes.c_void_p                   # LPOVERLAPPED lpOverlapped
]
fnWriteFile.restype = ctypes.c_int

fnReadFile = WINDLL.kernel32.ReadFile
fnReadFile.argtypes = [
  handle_t,                         # HANDLE hFile,
  ctypes.c_void_p,                  # LPVOID lpBuffer,
  ctypes.c_int,                     # DWORD lpNumberOfBytesRead,
  ctypes.POINTER(ctypes.c_int),     # LPDWORD lpNumberOfBytesWritten,
  ctypes.c_void_p                   # LPOVERLAPPED lpOverlapped
]
fnReadFile.restype = ctypes.c_int

fnCreateEvent = WINDLL.kernel32.CreateEventA
fnCreateEvent.argtypes = [
  ctypes.c_void_p,          # LPSECURITY_ATTRIBUTES lpEventAttributes
  ctypes.c_int,             # BOOL bManualReset
  ctypes.c_int,             # BOOL bInitialState
  ctypes.c_char_p           # LPCTSTR lpName
]
fnCreateEvent.restype = handle_t

fnResetEvent = WINDLL.kernel32.ResetEvent
fnResetEvent.argtypes = [ handle_t ]
fnResetEvent.restype = ctypes.c_int

fnGetLastError = WINDLL.kernel32.GetLastError
fnGetLastError.restype = ctypes.c_int

fnWaitForSingleObject = WINDLL.kernel32.WaitForSingleObject
fnWaitForSingleObject.argtypes = [ handle_t, ctypes.c_int ]
fnWaitForSingleObject.restype = ctypes.c_int

fnWaitForMultipleObjects = WINDLL.kernel32.WaitForMultipleObjects
fnWaitForMultipleObjects.argptypes = [
  ctypes.c_int,                     # DWORD nCount
  ctypes.POINTER(handle_t),         # const HANDLE *lpHandles
  ctypes.c_int,                     # BOOL bWaitAll
  ctypes.c_int                      # DWORD dwMilliseconds
]
fnWaitForMultipleObjects.restype = ctypes.c_int

fnConnectNamedPipe = WINDLL.kernel32.ConnectNamedPipe
fnConnectNamedPipe.argtypes = [ handle_t, ctypes.POINTER(Overlapped) ]
fnConnectNamedPipe.restype = ctypes.c_int

fnGetExitCodeProcess = WINDLL.kernel32.GetExitCodeProcess
fnGetExitCodeProcess.argtypes = [ handle_t, ctypes.POINTER(ctypes.c_int) ]
fnGetExitCodeProcess.restype = ctypes.c_int

fnFormatMessage = WINDLL.kernel32.FormatMessageA
fnFormatMessage.argtypes = [
  ctypes.c_int,                     # DWORD dwFlags
  ctypes.c_void_p,                  # LPCVOID lpSource
  ctypes.c_int,                     # DWORD dwMessageId
  ctypes.c_int,                     # DWRD dwLanguageId
  ctypes.c_void_p,                  # LPTSTR lpBuffer
  ctypes.c_int,                     # DWORD nSize
  ctypes.c_void_p                   # va_list *Arguments
]
fnFormatMessage.restype = ctypes.c_int

fnSetConsoleTextAttribute = WINDLL.kernel32.SetConsoleTextAttribute
fnSetConsoleTextAttribute.argtypes = [ handle_t, ctypes.c_short ]
fnSetConsoleTextAttribute.restype = ctypes.c_int


PIPE_ACCESS_DUPLEX =              0x00000003
PIPE_TYPE_BYTE =                  0x00000000
PIPE_TYPE_READMODE_BYTE =         0x00000000
FILE_FLAG_FIRST_PIPE_INSTANCE =   0x00080000
FILE_FLAG_OVERLAPPED =            0x40000000
GENERIC_READ =                    0x80000000
GENERIC_WRITE =                   0x40000000
OPEN_EXISTING =                   3
DUPLICATE_SAME_ACCESS =           0x00000002
STARTF_USESTDHANDLES =            0x00000100
STD_INPUT_HANDLE =                -10
STD_OUTPUT_HANDLE =               -11
STD_ERROR_HANDLE =                -12
INFINITE =                        -1
WAIT_ABANDONED =                  0x00000080
WAIT_OBJECT_0 =                   0x00000000
WAIT_TIMEOUT =                    0x00000102
WAIT_FAILED =                     -1
STILL_ACTIVE =                    259
FORMAT_MESSAGE_ALLOCATE_BUFFER =  0x00000100
FORMAT_MESSAGE_IGNORE_INSERTS =   0x00000200
FORMAT_MESSAGE_FROM_SYSTEM =      0x00001000
ERROR_BROKEN_PIPE =               109
ERROR_PIPE_CONNECTED =            535
ERROR_IO_PENDING =                997

pipe_counter_ = 0

class StartupInfo(ctypes.Structure):
  def __init__(self):
    super(StartupInfo, self).__init__()
    self.cb = ctypes.sizeof(StartupInfo)

  _fields_ = [
    ('cb',              ctypes.c_int),
    ('lpReserved',      ctypes.c_char_p),
    ('lpDesktop',       ctypes.c_char_p),
    ('lpTitle',         ctypes.c_char_p),
    ('dwX',             ctypes.c_int),
    ('dwY',             ctypes.c_int),
    ('dwXSize',         ctypes.c_int),
    ('dwYSize',         ctypes.c_int),
    ('dwXCountChars',   ctypes.c_int),
    ('dwYCountChars',   ctypes.c_int),
    ('dwFillAttribute', ctypes.c_int),
    ('dwFlags',         ctypes.c_int),
    ('wShowWindow',     ctypes.c_short),
    ('cbReserved2',     ctypes.c_short),
    ('lpReserved2',     ctypes.c_void_p),
    ('hStdInput',       handle_t),
    ('hStdOutput',      handle_t),
    ('hStdError',       handle_t)
  ]

class ProcessInformation(ctypes.Structure):
  def __init__(self):
    super(ProcessInformation, self).__init__()

  _fields_ = [
    ('hProcess',        handle_t),
    ('hThread',         handle_t),
    ('dwProcessId',     ctypes.c_int),
    ('dwThreadId',      ctypes.c_int)
  ]

def CreateEvent(manual, initial):
  rval = fnCreateEvent(None, int(manual), int(initial), None)
  if not rval:
    raise WinError()

  return handle_t(rval)

def ResetEvent(handle):
  if not fnResetEvent(handle):
    raise WinError()

def CreateNamedPipe():
  global pipe_counter_

  pipe_name = r'\\.\pipe\ambuild-{0}-{1}'.format(os.getpid(), pipe_counter_)
  pipe_counter_ += 1

  flags = PIPE_ACCESS_DUPLEX | FILE_FLAG_OVERLAPPED | FILE_FLAG_FIRST_PIPE_INSTANCE

  rval = fnCreateNamedPipeA(
    util.str2b(pipe_name),
    flags,
    PIPE_TYPE_BYTE | PIPE_TYPE_READMODE_BYTE,
    1,
    4096,
    4096,
    5000,
    None
  )
  if rval == INVALID_HANDLE_VALUE:
    raise WinError()
  return handle_t(rval), pipe_name

def OpenPipe(path):
  rval = fnCreateFileA(
    util.str2b(path),
    GENERIC_READ | GENERIC_WRITE,
    0,
    None,
    OPEN_EXISTING,
    FILE_FLAG_OVERLAPPED,
    None
  )
  if rval == INVALID_HANDLE_VALUE:
    raise WinError()
  return handle_t(rval)

def CloseHandle(handle):
  fnCloseHandle(handle)

def WaitForSingleObject(handle, wait):
  result = fnWaitForSingleObject(handle, wait)
  if result == WAIT_FAILED:
    raise WinError()
  return result == WAIT_OBJECT_0

def WaitForMultipleObjects(handles, wait_all, wait):
  nhandles = len(handles)
  array = (handle_t * nhandles)()
  for index, handle in enumerate(handles):
    array[index] = handle
  
  result = fnWaitForMultipleObjects(
    nhandles,
    array,
    int(wait_all),
    wait
  )

  if result == WAIT_FAILED:
    raise WinError()

  return result

def CreateIoCompletionPort():
  rval = fnCreateIoCompletionPort(
    INVALID_HANDLE,
    None,
    0,
    1
  )
  if not rval:
    raise WinError()
  return handle_t(rval)

def RegisterIoCompletion(port, handle, key):
  rval = fnCreateIoCompletionPort(
    handle,
    port,
    key,
    1
  )
  if not rval:
    raise WinError()
  assert rval == port.value

def GetQueuedCompletionStatus(port, wait):
  nbytes = ctypes.c_int()
  key = ctypes.c_size_t()
  poverlapped = ctypes.c_void_p()

  result = fnGetQueuedCompletionStatus(
    port,
    ctypes.byref(nbytes),
    ctypes.byref(key),
    ctypes.byref(poverlapped),
    wait
  )

  if not poverlapped.value:
    overlapped = None
  else:
    overlapped = ctypes.cast(poverlapped.value, LPOVERLAPPED)
    overlapped = overlapped.contents

  if not result:
    if not poverlapped:
      return False, 0, -1, overlapped
    return False, 0, key, overlapped

  return True, nbytes, key, overlapped


def GetCurrentProcess():
  return handle_t(fnGetCurrentProcess())

def GetStdHandle(n):
  rval = fnGetStdHandle(n)
  if rval == INVALID_HANDLE_VALUE:
    raise WinError()
  return handle_t(rval)

def SetConsoleTextAttribute(handle, color):
  rval = fnSetConsoleTextAttribute(handle, color)
  if not rval:
    raise WinError()

def GetLastError():
  return fnGetLastError()

def DuplicateHandle(handle):
  current = GetCurrentProcess()
  target = handle_t()
  rval = fnDuplicateHandle(
    current,
    handle,
    current,
    ctypes.pointer(target),
    0, # dwDesiredAccess (ignored)
    1, # bInheritHandle
    DUPLICATE_SAME_ACCESS
  )
  if not rval:
    raise WinError()
  return target

class Process(object):
  def __init__(self, handle, pid):
    self.handle = handle
    self.pid = pid
    self.returncode = None

  def is_alive(self):
    if self.returncode != None:
      return False

    status = ctypes.c_int()
    rval = fnGetExitCodeProcess(self.handle, ctypes.byref(status))
    if not rval:
      raise WinError()

    if status.value == 259:
      return True

    self.returncode = status.value
    return False

  @classmethod
  def spawn(cls, channel):
    eval = 'from ambuild2.ipc.windows import child_main; child_main()'
    argv = [sys.executable, '-c', eval]
    argv += ['--name', '{0}'.format(channel.name)]

    # This is pretty hacky. Maybe we should just pass in the pipe name instead.
    argv += ['--pipe', '{0}'.format(channel.path)]

    cmdline = ' '.join(['"{0}"'.format(arg) for arg in argv])
    cmdline = util.str2b(cmdline)
    cmdline_buffer = ctypes.create_string_buffer(cmdline)

    startup_info = StartupInfo()
    startup_info.dwFlags |= STARTF_USESTDHANDLES
    startup_info.hStdOutput = GetStdHandle(STD_OUTPUT_HANDLE)
    startup_info.hStdError = GetStdHandle(STD_ERROR_HANDLE)
    startup_info.hStdInput = GetStdHandle(STD_INPUT_HANDLE)

    proc_info = ProcessInformation()

    executable = sys_executable()

    rval = fnCreateProcessA(
      util.str2b(executable),
      cmdline_buffer,
      None,
      None,
      1,    # bInheritHandles
      0,    # dwCreationFlags
      None, # lpEnvironment
      None, # lpCurrentDirectory
      ctypes.pointer(startup_info),
      ctypes.pointer(proc_info)
    )
    if not rval:
      raise WinError()

    CloseHandle(proc_info.hThread)

    return cls(proc_info.hProcess, proc_info.dwProcessId)

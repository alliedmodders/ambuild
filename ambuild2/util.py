# vim: set sts=2 ts=8 sw=2 tw=99 et: 
import errno
import subprocess
import re, os, sys, locale
import multiprocessing
try:
  import __builtin__ as builtins
except:
  import builtins
try:
  import cPickle as pickle
except:
  import pickle

def Platform():
  if IsWindows():
    return 'windows'
  if IsMac():
    return 'mac'
  if IsLinux():
    return 'linux'
  if IsFreeBSD():
    return 'freebsd'
  if IsOpenBSD():
    return 'openbsd'
  if IsNetBSD():
    return 'netbsd'
  if IsSolaris():
    return 'solaris'
  if IsCygwin():
    return 'cygwin'
  return 'unknown'

def IsLinux():
  return sys.platform[0:5] == 'linux'

def IsFreeBSD():
  return sys.platform[0:7] == 'freebsd'

def IsNetBSD():
  return sys.platform[0:6] == 'netbsd'

def IsOpenBSD():
  return sys.platform[0:7] == 'openbsd'

def IsWindows():
  return sys.platform == 'win32'

def IsCygwin():
  return sys.platform == 'cygwin'

def IsMac():
  return sys.platform == 'darwin' or sys.platform[0:6] == 'Darwin'

def IsSolaris():
  return sys.platform[0:5] == 'sunos'

def IsUnixy():
  return not IsWindows()

def IsBSD():
  return IsMac() or IsFreeBSD() or IsOpenBSD() or IsNetBSD()

def ExecutableSuffix():
  if IsWindows():
    return '.exe'
  else:
    return ''

def SharedLibSuffix():
  if IsWindows():
    return '.dll'
  elif sys.platform == 'darwin':
    return '.dylib'
  else:
    return '.so'

def StaticLibSuffix():
  if IsUnixy():
    return '.a'
  return '.lib'

def StaticLibPrefix():
  if IsWindows():
    return ''
  else:
    return 'lib'

def WaitForProcess(process):
  out, err = process.communicate()
  process.stdoutText = DecodeConsoleText(sys.stdout, process.stdout, out)
  process.stderrText = DecodeConsoleText(sys.stderr, process.stderr, err)
  return process.returncode

def CreateProcess(argv, executable = None):
  pargs = { 'args': argv }
  pargs['stdout'] = subprocess.PIPE
  pargs['stderr'] = subprocess.PIPE
  if executable != None:
    pargs['executable'] = executable
  try:
    process = subprocess.Popen(**pargs)
  except:
    return None
  return process

def MakePath(*list):
  path = os.path.join(*list)
  if IsWindows():
    path = path.replace('\\\\', '\\')
  return path

def RemoveFolderAndContents(path):
  for file in os.listdir(path):
    subpath = os.path.join(path, file)
    try:
      if os.path.isfile(subpath) or os.path.islink(subpath):
        os.unlink(subpath)
      elif os.path.isdir(subpath):
        RemoveFolderAndContents(subpath)
    except:
      pass
  os.rmdir(path)

class FolderChanger:
  def __init__(self, folder):
    self.old = os.getcwd()
    self.new = folder

  def __enter__(self):
    if self.new:
      os.chdir(self.new)

  def __exit__(self, type, value, traceback):
    os.chdir(self.old)

class Guard:
  def __init__(self, obj):
    self.obj = obj

  def __enter__(self):
    return self.obj

  def __exit__(self, type, value, traceback):
    self.obj.close()

def Execute(argv, shell=False):
  p = subprocess.Popen(
      args=argv,
      stdout=subprocess.PIPE,
      stderr=subprocess.PIPE,
      shell=shell
  )
  stdout, stderr = p.communicate()
  out = stdout.decode('utf8')
  err = stderr.decode('utf8')
  return p, out, err

def typeof(x):
  return builtins.type(x)

if str == bytes:
  # Python 2.7. sqlite blob is buffer
  BlobType = buffer
else:
  BlobType = bytes

def Unpickle(blob):
  if type(blob) != bytes:
    blob = bytes(blob)
  return pickle.loads(blob)

# We don't want to dump Python 3 pickle format since then ambuild couldn't
# run it if you using Python 2.
PICKLE_PROTOCOL = min(2, pickle.HIGHEST_PROTOCOL)

def DiskPickle(obj, fp):
  return pickle.dump(obj, fp, PICKLE_PROTOCOL)

def CompatPickle(obj):
  return pickle.dumps(obj, PICKLE_PROTOCOL)

def str2b(s):
  if bytes is str:
    return s
  return bytes(s, 'utf8')

sReadIncludes = 0
sLookForIncludeGuard = 1
sFoundIncludeGuard = 2
sIgnoring = 3
def ParseGCCDeps(text):
  deps = set()
  strip = False
  new_text = ''

  state = sReadIncludes
  for line in re.split('\n+', text):
    if state == sReadIncludes:
      m = re.match('\.+\s+(.+)\s*$', line)
      if m == None:
        state = sLookForIncludeGuard
      else:
        name = m.groups()[0]
        if os.path.exists(name):
          strip = True
          deps.add(name)
        else:
          state = LookForIncludeGuard
    if state == sLookForIncludeGuard:
      if line.startswith('Multiple include guards may be useful for:'):
        state = sFoundIncludeGuard
        strip = True
      else:
        state = sReadIncludes
        strip = False
    elif state == sFoundIncludeGuard:
      if not line in deps:
        strip = False
        state = sIgnoring
    if not strip and len(line):
      new_text += line + '\n'
  return new_text, deps

def ParseMSVCDeps(out):
  deps = []
  new_text = ''
  out = out.replace('\r\n', '\n')
  out = out.replace('\r', '\n')
  for line in out.split('\n'):
    m = re.match('Note: including file:\s+(.+)$', line)
    if m != None:
      file = m.groups()[0].strip()
      deps.append(file)
    else:
      new_text += line + '\n'
  return new_text, deps

def ParseSunDeps(text):
  deps = set()
  new_text = ''

  for line in re.split('\n+', text):
    name = line.lstrip()
    if os.path.isfile(name):
      deps.add(name)
    else:
      new_text += line + '\n'
  return new_text.strip(), deps

if hasattr(os, 'symlink'):
  def symlink(target, link):
    os.symlink(target, link)
    return 0, '', ''
elif IsWindows():
  def symlink(target, link):
    argv = [
      'mklink',
      '"{0}"'.format(link),
      '"{0}"'.format(target)
    ]
    p, out, err = Execute(argv, shell=True)
    return p.returncode, out, err

if IsUnixy():
  ConsoleGreen = lambda fp: fp.write('\033[92m')
  ConsoleRed = lambda fp: fp.write('\033[91m')
  ConsoleNormal = lambda fp: fp.write('\033[0m')
  ConsoleBlue = lambda fp: fp.write('\033[94m')
  ConsoleHeader = lambda fp: fp.write('\033[95m')
elif IsWindows():
  def SwitchColor(fp, color):
    from ambuild2.ipc import winapi

    std = None
    if fp == sys.stdout:
      std = winapi.STD_OUTPUT_HANDLE
    elif fp == sys.stdin:
      std = winapi.STD_ERROR_HANDLE
    if std is None:
      return

    handle = winapi.GetStdHandle(std)
    winapi.SetConsoleTextAttribute(handle, color)

  ConsoleGreen = lambda fp: SwitchColor(fp, 0xA)
  ConsoleRed = lambda fp: SwitchColor(fp, 0xC)
  ConsoleNormal = lambda fp: SwitchColor(fp, 0x7)
  ConsoleBlue = lambda fp: SwitchColor(fp, 0x9)
  ConsoleHeader = lambda fp: SwitchColor(fp, 0xD)
else:
  ConsoleGreen = ''
  ConsoleRed = ''
  ConsoleNormal = ''
  ConsoleBlue = ''
  ConsoleHeader = ''

def IsColor(text):
  return IsLambda(text)

sConsoleColorsEnabled = True
def DisableConsoleColors():
  global sConsoleColorsEnabled
  sConsoleColorsEnabled = False

def con_print(fp, args):
  for arg in args:
    if IsColor(arg):
      arg(fp)
    else:
      fp.write(arg)
  fp.write('\n')

def con_print_simple(fp, args):
  for arg in args:
    if IsColor(arg):
      continue
    fp.write(arg)
  fp.write('\n')

def con_out(*args):
  if sys.stdout.isatty():
    con_print(sys.stdout, args)
  else:
    con_print_simple(sys.stdout, args)

def con_err(*args):
  if sys.stderr.isatty():
    con_print(sys.stderr, args)
  else:
    con_print_simple(sys.stderr, args)

LambdaType = type(lambda: None)

def IsLambda(v):
  return type(v) == LambdaType

if str == bytes:
  def IsString(v):
    return type(v) == str or type(v) == unicode
else:
  def IsString(v):
    return type(v) == str

class Expando(object):
  pass

def rm_path(path):
  assert not os.path.isabs(path)

  if os.path.exists(path):
    con_out(ConsoleHeader, 'Removing old output: ',
            ConsoleBlue, '{0}'.format(path),
            ConsoleNormal)

  try:
    os.unlink(path)
  except OSError as exn:
    if exn.errno != errno.ENOENT:
      con_err(ConsoleRed, 'Could not remove file: ',
              ConsoleBlue, '{0}'.format(path),
              ConsoleNormal, '\n',
              ConsoleRed, '{0}'.format(exn),
              ConsoleNormal)
      raise

def try_decode_with_pipe(pipe, text):
  try:
    if hasattr(pipe, 'encoding') and pipe.encoding:
      return text.decode(pipe.encoding, 'replace')
  except:
    return None

def DecodeConsoleText(origin, pipe, text):
  result = try_decode_with_pipe(pipe, text)
  if result is None:
    result = try_decode_with_pipe(origin, text)
    if result is None:
      try:
        result = text.decode(locale.getpreferredencoding(), 'replace')
      except:
        result = text
  return result.encode('utf8')

def WriteEncodedText(fd, text):
  if not hasattr(fd, 'encoding') or fd.encoding == None:
    text = text.encode(locale.getpreferredencoding(), 'replace')
  fd.write(text)

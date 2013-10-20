# vim: set sts=2 ts=8 sw=2 tw=99 et: 
import errno
import subprocess
import re, os, sys
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
  return sys.platform == 'win32' or sys.platform == 'cygwin'

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
  process.stdoutText = out.decode()
  process.stderrText = err.decode()
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

  out = (' '.join([i for i in argv])) + '\n' + out
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
  for line in out.split('\n'):
    m = re.match('Note: including file:\s+(.+)$', line)
    if m != None:
      file = m.groups()[0].strip()
      deps.append(file)
    else:
      new_text += line
  return new_text, deps

if hasattr(os, 'symlink'):
  def symlink(target, link):
    os.symlink(target, link)
    stdout = 'ln -s "{0}" "{1}"'.format(target, link)
    stderr = ''
    return 0, stdout, stderr
elif IsWindows():
  def symlink(target, link):
    argv = [
      'mklink',
      '"{0}"'.format(link),
      '"{0}"'.format(target)
    ]
    p, out, err = Execute(argv, shell=True)
    return p.returncode, out, err

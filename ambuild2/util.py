# vim: set sts=2 ts=8 sw=2 tw=99 et: 
import os
import sys
import subprocess
import multiprocessing

def Platform():
  if IsWindows():
    return 'windows'
  if IsMac():
    return 'mac'
  if sys.platform[0:5] == 'linux':
    return 'linux'
  return 'unknown'

def IsWindows():
  return sys.platform == 'win32' or sys.platform == 'cygwin'

def IsMac():
  return sys.platform == 'darwin'

def IsUnixy():
  return sys.platform[0:5] == 'linux' or IsMac()

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

def Execute(argv):
  p = subprocess.Popen(
      args=argv,
      stdout=subprocess.PIPE,
      stderr=subprocess.PIPE,
      shell=False
  )
  stdout, stderr = p.communicate()
  out = stdout.decode()
  err = stderr.decode()

  out = (' '.join([i for i in argv])) + out
  return p, out, err

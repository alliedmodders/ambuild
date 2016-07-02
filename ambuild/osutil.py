# vim: set ts=2 sw=2 tw=99 noet: 
import os
import sys
import locale
import subprocess
import multiprocessing

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

def DecodeConsoleText(origin, text):
	try:
		if origin.encoding:
			return text.decode(origin.encoding, 'replace')
	except:
		pass
	try:
		return text.decode(locale.getpreferredencoding(), 'replace')
	except:
		pass
	return text.decode('utf8', 'replace')

def WaitForProcess(process):
	out, err = process.communicate()
	process.stdoutText = DecodeConsoleText(sys.stdout, out)
	process.stderrText = DecodeConsoleText(sys.stderr, err)
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

Folders = []
def PushFolder(path):
	Folders.append(os.path.abspath(os.getcwd()))
	os.chdir(path)

def PopFolder():
	os.chdir(Folders.pop())

def NumberOfCPUs():
	return multiprocessing.cpu_count()

def FileExists(file):
	if os.path.isfile(file):
		GetFileTime(file)
		return True
	return False

def GetFileTime(file):
	time = os.path.getmtime(file)
	return time

def IsFileNewer(this, that):
	this = GetFileTime(this)
	if type(that) == str:
		that = GetFileTime(that)
	return this > that


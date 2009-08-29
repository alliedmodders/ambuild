# vim: set ts=2 sw=2 tw=99 noet: 
import os
import sys
import subprocess

def IsWindows():
	return sys.platform == 'win32' or sys.platform == 'cygwin'

def IsUnixy():
	return sys.platform[0:5] == 'linux' or sys.platform == 'darwin'

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

Folders = []
def PushFolder(path):
	Folders.append(os.path.abspath(os.getcwd()))
	os.chdir(path)

def PopFolder():
	os.chdir(Folders.pop())

#from http://codeliberates.blogspot.com/2008/05/detecting-cpuscores-in-python.html
def NumberOfCPUs():
	# Linux, Unix and MacOS:
	if hasattr(os, "sysconf"):
		if 'SC_NPROCESSORS_ONLN' in os.sysconf_names:
			# Linux & Unix:
			ncpus = os.sysconf("SC_NPROCESSORS_ONLN")
			if isinstance(ncpus, int) and ncpus > 0:
				return ncpus
		else: # OSX:
			return int(os.popen2("sysctl -n hw.ncpu")[1].read())
	# Windows:
	if 'NUMBER_OF_PROCSSORS' in os.environ:
		ncpus = int(os.environ["NUMBER_OF_PROCESSORS"]);
		if ncpus > 0:
			return ncpus
	return 1 # Default

FILE_CACHE = { }

def FileExists(file):
	if file in FILE_CACHE:
		return True
	if os.path.isfile(file):
		GetFileTime(file)
		return True
	return False

def GetFileTime(file):
	if file in FILE_CACHE:
		return FILE_CACHE[file]
	time = os.path.getmtime(file)
	FILE_CACHE[file] = time
	return time

def IsFileNewer(this, that):
	this = GetFileTime(this)
	if type(that) == str:
		that = GetFileTime(that)
	return this > that


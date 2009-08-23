# vim: set ts=2 sw=2 tw=99 noet: 
import os
import sys
import subprocess

def IsWindows():
	return sys.platform == 'win32' or sys.platform == 'cygwin'

def IsUnixy():
	return sys.platform[0:5] == 'linux' or sys.platform == 'darwin'

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


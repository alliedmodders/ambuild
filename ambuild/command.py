# vim: set ts=2 sw=2 tw=99 noet: 
import os
import sys
import shutil
import subprocess
import ambuild.osutil as osutil

class Command:
	def __init__(self):
		self.stderr = None
		self.stdout = None
		self.failureIsFatal = True
	def run(self, master, job):
		pass
	def spew(self, runner):
		if self.stdout != None and len(self.stdout) > 0:
			runner.PrintOut(self.stdout)
		if self.stderr != None and len(self.stderr) > 0:
			runner.PrintOut(self.stderr)

class SymlinkCommand(Command):
	def __init__(self, link, target):
		Command.__init__(self)
		self.link = link
		self.target = target
	def run(self, master, job):
		master.PrintOut('symlinking {0} as {1}'.format(self.target, self.link))
		try:
			os.symlink(self.target, self.link)
		except:
			master.PrintOut('symlinking failed; copying instead, {0} as {1}'.format(self.target, self.link))
			shutil.copyfile(self.target, self.link)

class ShellCommand(Command):
	def __init__(self, cmdstring, failureIsFatal = True):
		Command.__init__(self)
		self.cmdstring = cmdstring
		self.failureIsFatal = failureIsFatal
	def run(self, master, job):
		master.PrintOut(self.cmdstring)
		args = { 'args':	 self.cmdstring,
		         'stdout': subprocess.PIPE,
		         'stderr': subprocess.PIPE,
			       'shell':  True }
		p = subprocess.Popen(**args)
		stdout, stderr = p.communicate()
		self.stdout = osutil.DecodeConsoleText(sys.stdout, stdout)
		self.stderr = osutil.DecodeConsoleText(sys.stderr, stderr)
		if p.returncode != 0:
			raise Exception('terminated with non-zero exitcode {0}'.format(p.returncode))

class DirectCommand(Command):
	def __init__(self, argv, exe = None, failureIsFatal = True, env = None):
		Command.__init__(self)
		self.exe = exe
		self.argv = argv
		self.failureIsFatal = failureIsFatal
		self.env = env
	def run(self, runner, job):
		runner.PrintOut(' '.join(['"' + i + '"' for i in self.argv]))
		args = { 'args':	 self.argv,
			       'stdout': subprocess.PIPE,
			       'stderr': subprocess.PIPE,
		         'shell':  False }
		if self.env != None:
			args['env'] = self.env
		if self.exe != None:
			args['executable'] = self.exe
		p = subprocess.Popen(**args)
		stdout, stderr = p.communicate()
		self.stdout = osutil.DecodeConsoleText(sys.stdout, stdout)
		self.stderr = osutil.DecodeConsoleText(sys.stderr, stderr)
		if p.returncode != 0:
			raise Exception('failure: program terminated with non-zero exitcode {0}'.format(p.returncode))

def RunDirectCommand(runner, argv, exe = None):
	runner.PrintOut(' '.join([i for i in argv]))
	args = {'args':   argv,
          'stdout': subprocess.PIPE,
          'stderr': subprocess.PIPE,
          'shell':  False}
	if exe != None:
		argv['executable'] = exe
	p = subprocess.Popen(**args)
	stdout, stderr = p.communicate()
	p.stdoutText = osutil.DecodeConsoleText(sys.stdout, stdout)
	p.stderrText = osutil.DecodeConsoleText(sys.stderr, stderr)
	p.realout = stdout
	p.realerr = stderr
	return p


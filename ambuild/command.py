# vim: set ts=2 sw=2 tw=99 noet: 
import subprocess

class Command:
	def __init__(self):
		self.stderr = None
		self.stdout = None
		self.failureIsFatal = True
	def run(self, master, job):
		pass
	def spew(self, runner):
		if len(self.stdout) > 0:
			runner.PrintOut(self.stdout)
		if len(self.stderr) > 0:
			runner.PrintOut(self.stderr)

class ShellCommand(Command):
	def __init__(self, cmdstring, failureIsFatal = True):
		Command.__init__(self)
		self.cmdstring = cmdstring
		self.failureIsFatal = failureIsFatal
	def run(self, master, job):
		builder.PrintOut(self.cmdstring)
		args = { 'args':	 self.cmdstring,
		         'stdout': subprocess.PIPE,
		         'stderr': subprocess.PIPE,
			       'shell':  True }
		p = subprocess.Popen(**args)
		stdout, stderr = p.communicate()
		self.stdout = stdout.decode()
		self.stderr = stderr.decode()
		if p.returncode != 0:
			raise Exception('terminated with non-zero exitcode {0}'.format(p.returncode))

class DirectCommand(Command):
	def __init__(self, argv, exe = None, failureIsFatal = True):
		Command.__init__(self)
		self.exe = exe
		self.argv = argv
		self.failureIsFatal = failureIsFatal
	def run(self, runner, job):
		runner.PrintOut(' '.join([i for i in self.argv]))
		args = { 'args':	 self.argv,
			       'stdout': subprocess.PIPE,
			       'stderr': subprocess.PIPE,
		         'shell':  False }
		if self.exe != None:
			args['executable'] = self.exe
		p = subprocess.Popen(**args)
		stdout, stderr = p.communicate()
		self.stdout = stdout.decode()
		self.stderr = stderr.decode()
		if p.returncode != 0:
			raise Exception('failure: program terminated with non-zero exitcode {0}'.format(p.returncode))


# vim: set ts=2 sw=2 tw=99 noet: 
import subprocess

class Command:
	def __init__(self):
		self.stderr = None
		self.stdout = None
		self.failureIsFatal = True
	def run(self, master, job):
		pass

class CommandException(Exception):
	def __init__(self, value):
		Exception.__init__(self, value)
	def __str__(self):
		return repr(self.value)

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
			raise CommandException('terminated with non-zero exitcode {0}'.format(p.returncode))

class DirectCommand(Command):
	def __init__(self, exe, argv, failureIsFatal = True):
		Command.__init__(self)
		self.exe = exe
		self.argv = argv
		self.failureIsFatal = failureIsFatal
	def run(self, master, job):
		builder.printOut(self.exe + ' ' + ' '.join(['"' + i + '"' for i in argv]))
		args = { 'args':	 self.argv,
			       'stdout': subprocess.PIPE,
			       'stdout': subprocess.PIPE,
		         'shell':  False }
		p = subprocess.Popen(**args)
		stdout, stderr = p.communicate()
		self.stdout = stdout.decode()
		self.stderr = stderr.decode()
		if p.returncode != 0:
			raise CommandException('terminated with non-zero exitcode {0}'.format(p.returncode))


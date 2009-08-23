# vim: set ts=2 sw=2 tw=99 noet: 
from ambuild.command import Command

class TaskGroup:
	def __init__(self, cmds, mustBeSerial = True):
		self.cmds = cmds
		self.mustBeSerial = mustBeSerial

class Job:
	def __init__(self, name, workFolder = None):
		self.tasks = []
		self.name = name
		if workFolder == None:
			self.workFolder = name
		else:
			self.workFolder = workFolder
	def AddCommand(self, cmd):
		if not isinstance(cmd, Command):
			raise Exception('task is not a Command')
		self.tasks.append(TaskGroup([cmd]))
	def AddCommandGroup(self, cmds, mustBeSerial = True):
		if not isinstance(cmds, list):
			raise Exception('tasks are not in a list')
		self.tasks.append(TaskGroup(cmds, mustBeSerial))
	def run(self, master):
		for group in self.tasks:
			for task in group.cmds:
				try:
					task.run(master, self)
					task.spew(master)
				except Exception as e:
					task.spew(master)
					raise e


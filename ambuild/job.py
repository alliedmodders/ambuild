# vim: set ts=2 sw=2 tw=99 noet: 
from commands import Command

class TaskGroup:
	def __init__(self, cmds, mustBeSerial = True):
		self.cmds = cmds
		self.mustBeSerial = mustBeSerial

class Job:
	def __init__(self, name, workfolder = None):
		self.tasks = []
		self.name = name
		if workfolder == None:
			self.workfolder = name
		else
			self.workfolder = workfolder
	def AddCommand(self, command):
		if not isinstance(command, Command):
			raise Exception('task is not a Command')
		self.tasks.append(TaskGroup([task]))
	def AddCommandGroup(self, commands, mustBeSerial = True):
		if not isinstance(commands, list):
			raise Exception('tasks are not in a list')
		self.tasks.append(Task(commands, mustBeSerial))
	def run(self, master):
		for group in self.tasks:
			for task in group:
				task.run(builder, master, job)


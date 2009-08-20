# vim: set ts=2 sw=2 tw=99 noet: 
from commands import Command

class TaskGroup:
	def __init__(self, cmds, mustBeSerial = True):
		self.cmds = cmds
		self.mustBeSerial = mustBeSerial

class Job(Command):
	def __init__(self, name):
		Command.__init__(self)
		self.tasks = []
		self.name = name
	def AddCommand(self, command):
		if not isinstance(command, Command):
			raise Exception('task is not a Command')
		self.tasks.append(TaskGroup([task]))
	def AddCommandGroup(self, commands, mustBeSerial = True):
		if not isinstance(tasks, list):
			raise Exception('tasks are not in a list')
		self.tasks.append(Task(tasks, mustBeSerial))
	def run(self, builder):
		for group in self.tasks:
			for task in group:
				task.run(builder)


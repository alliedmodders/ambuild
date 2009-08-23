# vim: set ts=2 sw=2 tw=99 noet:
import sys
import os
import osutil
from optparse import OptionParser

class Runner:
	def Configure(self):
		self.mode = 'config'
		parser = OptionParser()
		(options, args) = parser.parse_args()
		if len(args) == 0:
			raise Exception('usage: amconfig.py <folder>')
		self.sourceFolder = os.path.abspath(args[0])
		self.outputFolder = os.path.abspath(os.getcwd())
		cache = os.path.join(self.outputFolder, '.ambuild')
		if os.path.isdir(cache):
			osutil.RemoveFolderAndContents(cache)
		os.mkdir(cache)
		if not os.path.isdir(cache):
			raise Exception('could not create .ambuild folder')
		self.LoadFile(os.path.join(self.sourceFolder, 'ambuild'))
	def Include(self, path, xtras = None):
		self.LoadFile(os.path.join(self.sourceFolder, path), xtras)
	def LoadFile(self, path, xtras = None):
		globals = {
			'AMBuild': self
		}
		if xtras != None:
			globals.update(xtras)
		execfile(path, globals)

# vim: set ts=2 sw=2 tw=99 noet:
import sys
import os
import osutil
import job
import cache
import cpp
from optparse import OptionParser

def _execfile(file, globals, locals):
	exec(compile(open(file).read(), file, 'exec'), globals, locals)

class Runner:
	def Build(self):
		self.mode = 'build'
		parser = OptionParser()
		(options, args) = parser.parse_args()
#		if len(args) == 0:
#			raise Exception('usage: ambuild.py')
		self.outputFolder = os.path.abspath(os.getcwd())
		cacheFolder = os.path.join(self.outputFolder, '.ambuild')
		if not os.path.isdir(cacheFolder):
			raise Exception('could not find .ambuild folder')
		cacheFile = os.path.join(cacheFolder, 'cache')
		if not os.path.isfile(cacheFile):
			raise Exception('could not find .ambuild cache file')
		self.cache = cache.Cache(cacheFile)
		self.cache.LoadCache()
		self.sourceFolder = self.cache['sourceFolder']
		self.LoadFile(os.path.join(self.sourceFolder, 'ambuild'))
	def Configure(self):
		self.mode = 'config'
		parser = OptionParser()
		(options, args) = parser.parse_args()
		if len(args) == 0:
			raise Exception('usage: amconfig.py <folder>')
		self.sourceFolder = os.path.abspath(args[0])
		self.outputFolder = os.path.abspath(os.getcwd())
		cacheFolder = os.path.join(self.outputFolder, '.ambuild')
		if os.path.isdir(cacheFolder):
			osutil.RemoveFolderAndContents(cacheFolder)
		os.mkdir(cacheFolder)
		if not os.path.isdir(cacheFolder):
			raise Exception('could not create .ambuild folder')
		self.cache = cache.Cache(os.path.join(cacheFolder, 'cache'))
		self.cache.CacheVariable('sourceFolder', self.sourceFolder)
		self.LoadFile(os.path.join(self.sourceFolder, 'ambuild'))
		self.cache.WriteCache()
	def Include(self, path, xtras = None):
		self.LoadFile(os.path.join(self.sourceFolder, path), xtras)
	def LoadFile(self, path, xtras = None):
		globals = {
			'AMBuild': self,
			'Job':     job.Job,
			'Cpp':     cpp
		}
		if xtras != None:
			globals.update(xtras)
		_execfile(path, globals, {})


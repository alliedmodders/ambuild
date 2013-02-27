# vim: set ts=2 sw=2 tw=99 noet:
from __future__ import print_function
import sys
import os
import ambuild.osutil as osutil
from ambuild.job import Job
import ambuild.cache as cache
import ambuild.cpp as cpp
from optparse import OptionParser

def _execfile(file, globals):
	exec(compile(open(file).read(), file, 'exec'), globals)

class Runner:
	def __init__(self):
		self.jobs = []
		self.options = OptionParser()
		self.target = { }
		self.numCPUs = osutil.NumberOfCPUs()
		self.quietAdd = False
		if osutil.IsWindows():
			self.target['platform'] = 'windows'
		elif sys.platform.startswith('linux'):
			self.target['platform'] = 'linux'
		elif sys.platform.startswith('darwin'):
			self.target['platform'] = 'darwin'

	def PrintOut(self, text):
		print(text)

	def AddJob(self, name, workFolder = None):
		if not self.quietAdd:
			print('Adding job {0}.'.format(name))
		job = Job(self, name, workFolder)
		self.jobs.append(job)
		return job

	def ListJobs(self):
		print("Listing {0} jobs...".format(len(self.jobs)))
		for job in self.jobs:
			print(job.name)

	def RunJobs(self, jobs):
		for job in jobs:
			print('Running job: {0}...'.format(job.name))
			if job.workFolder != None:
				workFolder = os.path.join(self.outputFolder, job.workFolder)
				if not os.path.isdir(workFolder):
					os.makedirs(workFolder)
				osutil.PushFolder(workFolder)
				try:
					job.run(self)
				except Exception as e:
					print('Job failed: {0}'.format(str(e)))
					sys.exit(1)
				if job.workFolder != None:
					osutil.PopFolder()
				print('Completed job: {0}.'.format(job.name))

	def CallerScript(self, num = 1):
		return sys._getframe(num).f_code.co_filename

	def Build(self):
		self.mode = 'build'
		(options, args) = self.options.parse_args()
		argn = len(args)
		self.quietAdd = options.list == True or argn > 0
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
		self.LoadFile(os.path.join(self.sourceFolder, 'AMBuildScript'))
		if options.list:
			self.ListJobs()
			return
		jobs = []
		if argn > 0:
			# Run jobs in order specified on command line
			for j in args:
				validJob = False
				for job in self.jobs:
					if job.name == j:
						jobs.append(job)
						validJob = True
						break
				if not validJob:
					raise Exception('{0} is not a valid job name'.format(j))
		else:
			jobs = self.jobs
		self.RunJobs(jobs)

	def Configure(self, folder):
		self.mode = 'config'
		(options, args) = self.options.parse_args()
		self.options = options
		self.args = args
		self.sourceFolder = os.path.abspath(folder)
		self.outputFolder = os.path.abspath(os.getcwd())
		cacheFolder = os.path.join(self.outputFolder, '.ambuild')
		if os.path.isdir(cacheFolder):
			osutil.RemoveFolderAndContents(cacheFolder)
		os.mkdir(cacheFolder)
		if not os.path.isdir(cacheFolder):
			raise Exception('could not create .ambuild folder')
		self.cache = cache.Cache(os.path.join(cacheFolder, 'cache'))
		self.cache.CacheVariable('sourceFolder', self.sourceFolder)
		self.LoadFile(os.path.join(self.sourceFolder, 'AMBuildScript'))
		self.cache.WriteCache()
		f = open(os.path.join(self.outputFolder, 'build.py'), 'w')
		f.write("""
# vim: set ts=2 sw=2 tw=99 noet:
import sys
import ambuild.runner as runner

run = runner.Runner()
run.options.usage = '%prog [options] [job list]'
run.options.add_option('-l', '--list-jobs', action='store_true', dest='list', help='print list of jobs')
run.Build()
		""")

	def Include(self, path, xtras = None):
		self.LoadFile(os.path.join(self.sourceFolder, path), xtras)

	def LoadFile(self, path, xtras = None):
		globals = {
			'AMBuild': self,
			'Cpp':     cpp
		}
		if xtras != None:
			globals.update(xtras)
		_execfile(path, globals)


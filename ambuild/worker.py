# vim: set ts=2 sw=2 tw=99 noet: 
import threading

class Worker:
	def __call__(self):
		while len(self.jobs):
			try:
				job = self.jobs.pop()
				job.run()
			except KeyboardInterrupt as ki:
				return
			except Exception as e:
				self.e = e
				self.failedJob = job

class WorkerPool:
	def __init__(self, numWorkers):
		self.numWorkers = numWorkers
		self.workers = []
		for i in range(0, self.numWorkers):
			self.workers.append(Worker())

	def RunJobs(self, jobs):
		for w in self.workers:
			w.failedJob = None
			w.e = None
			w.jobs = []
			w.thread = threading.Thread(target = w)

		#Divvy up jobs
		num = 0
		for i in jobs:
			self.workers[num].jobs.append(i)
			num = num + 1
			if num == self.numWorkers:
				num = 0

		#Start up each thread
		for w in self.workers:
			w.thread.start()

		#Wait for threads to finish
		failed = []
		for w in self.workers:
			w.thread.join()
			if w.failedJob != None or w.e != None:
				failed.append({'job': w.failedJob, 'e': w.e})

		return failed


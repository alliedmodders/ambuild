# vim: set ts=2 sw=2 tw=99 noet:
import os
import cPickle as pickle

class Cache:
	def __init__(self):
		self.vars = { }
	def Initialize(self):
		os.mkdir('.ambuild')
	def CacheVariable(self, name, value):
		self.vars[name] = value
	def WriteCache(self):
		f = open(osutil.MakePath('.ambuild', 'cache'), 'w')
		try:
			pickle.dump(self.vars)
		except(Exception e):
			f.close()
			raise e
		f.close
	def LoadCache(self):
		f = open(osutil.MakePath('.ambuild', 'cache'), 'r')
		try:
			self.vars = pickle.load(f)
		except(Exception e):
			f.close()
			raise e
		f.close()
	def __getitem__(self, key):
		return self.vars[key]


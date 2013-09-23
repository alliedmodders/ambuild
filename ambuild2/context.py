# vim: set ts=8 sts=2 sw=2 tw=99 et:
import os
import sys
import imp
import database
import cpp, graph, util
from damage import Damage
from builder import Builder
from optparse import OptionParser
try:
  import cPickle as pickle
except:
  import pickle

class Context(object):
  def __init__(self, sourcePath, buildPath):
    self.sourcePath = sourcePath
    self.buildPath = buildPath
    self.cacheFolder = os.path.join(buildPath, '.ambuild2')
    self.server = None
    self.graph = None
    self.openFromCache()

  def __enter__(self):
    return self

  def __exit__(self, type, value, traceback):
    self.close()

  def close(self):
    if self.server:
      self.server.close()

  def openFromCache(self):
    #with open(os.path.join(self.cacheFolder, 'cx'), 'rb') as fp:
    #  vars = pickle.load(fp)
    dbPath = os.path.join(self.cacheFolder, 'db')
    self.server = database.DatabaseParent(dbPath)
    self.graph = graph.GraphProxy(self.server)

  def Build(self):
    return self.build_internal()

  def build_internal(self):
    parser = OptionParser("usage: %prog [options]")
    parser.add_option("--show-graph", dest="show_graph", action="store_true", default=False,
                      help="Show the dependency graph and then exit.")
    parser.add_option("--show-damage", dest="show_damage", action="store_true", default=False,
                      help="Show the computed change graph and then exit.")
    parser.add_option("--show-steps", dest="show_steps", action="store_true", default=False,
                      help="Show the computed build steps and then exit.")
    parser.add_option("-j", "--jobs", dest="jobs", type="int", default=0,
                      help="Number of worker processes. Minimum number is 1; default is #cores * 1.5.")
    options, args = parser.parse_args()

    if options.show_graph:
      self.graph.printGraph()
      return True

    if options.show_damage:
      damage = Damage(self.graph)
      damage.printChanges()
      return True

    builder = Builder(self)
    if options.show_steps:
      builder.printSteps()
      return True
    return builder.build(options.jobs)


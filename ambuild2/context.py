# vim: set ts=8 sts=2 sw=2 tw=99 et:
import os
import sys
import imp
import time
import database
import util
from damage import Damage
from builder import Builder
from optparse import OptionParser

class Context(object):
  def __init__(self, buildPath):
    self.buildPath = buildPath
    self.cacheFolder = os.path.join(buildPath, '.ambuild2')
    self.dbpath = os.path.join(self.cacheFolder, 'graph')
    with open(os.path.join(self.cacheFolder, 'vars'), 'rb') as fp:
      self.vars = util.pickle.load(fp)
    self.db = database.Database(self.dbpath)
    self.db.connect()

  def __enter__(self):
    return self

  def __exit__(self, type, value, traceback):
    self.db.close()

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
      self.db.printGraph()
      return True

    # If we get here, we have to compute damage.
    if options.show_damage:
      damage = Damage(self.db)
      damage.printDamage()
      return True
    
    builder = Builder(self)
    if options.show_steps:
      builder.printSteps()
      return True
    return builder.build(options.jobs)

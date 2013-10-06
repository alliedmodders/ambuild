# vim: set ts=8 sts=2 sw=2 tw=99 et:
#
# This file is part of AMBuild.
# 
# AMBuild is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# AMBuild is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with AMBuild. If not, see <http://www.gnu.org/licenses/>.
import time
import os, sys, imp
import util, database, damage
from builder import Builder
from ipc import ProcessManager, MessagePump
from optparse import OptionParser

class Context(object):
  def __init__(self, buildPath):
    self.buildPath = buildPath
    self.cacheFolder = os.path.join(buildPath, '.ambuild2')
    self.dbpath = os.path.join(self.cacheFolder, 'graph')
    with open(os.path.join(self.cacheFolder, 'vars'), 'rb') as fp:
      try:
        self.vars = util.pickle.load(fp)
      except ValueError as exn:
        sys.stderr.write('Build was configured with Python 3; use python3 instead.\n')
        sys.exit(1)
    self.db = database.Database(self.dbpath)
    self.db.connect()
    self.messagePump = MessagePump()
    self.procman = ProcessManager(self.messagePump)

  def __enter__(self):
    return self

  def __exit__(self, type, value, traceback):
    self.procman.close()
    self.db.close()

  def Build(self):
    return self.build_internal()

  def build_internal(self):
    parser = OptionParser("usage: %prog [options]")
    parser.add_option("--show-graph", dest="show_graph", action="store_true", default=False,
                      help="Show the dependency graph and then exit.")
    parser.add_option("--show-damage", dest="show_damage", action="store_true", default=False,
                      help="Show the computed change graph and then exit.")
    parser.add_option("--show-commands", dest="show_commands", action="store_true", default=False,
                      help="Show the computed command graph and then exit.")
    parser.add_option("--show-steps", dest="show_steps", action="store_true", default=False,
                      help="Show the computed build steps and then exit.")
    parser.add_option("-j", "--jobs", dest="jobs", type="int", default=0,
                      help="Number of worker processes. Minimum number is 1; default is #cores * 1.5.")
    self.options, self.args = parser.parse_args()

    if self.options.show_graph:
      self.db.printGraph()
      return True

    dmg_graph = damage.ComputeDamageGraph(self.db)

    # If we get here, we have to compute damage.
    if self.options.show_damage:
      dmg_graph.printGraph()
      return True

    if self.options.show_commands:
      dmg_graph.printCommands()
      return True
    
    builder = Builder(self, dmg_graph)
    if self.options.show_steps:
      builder.printSteps()
      return True
    return builder.update()

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
      except Exception as exn:
        if os.path.exists(os.path.join(self.cacheFolder, 'vars')):
          sys.stderr.write('There does not appear to be a build configured here.\n')
        else:
          sys.stderr.write('The build configured here looks corrupt; you will have to delete your objdir.\n')
        sys.exit(1)
    self.db = database.Database(self.dbpath)
    self.messagePump = MessagePump()
    self.procman = ProcessManager(self.messagePump)
    self.db.connect()

  def __enter__(self):
    return self

  def __exit__(self, type, value, traceback):
    self.procman.shutdown()
    self.db.close()

  def reconfigure(self):
    # See if we need to reconfigure.
    files = []
    reconfigure_needed = False
    self.db.query_scripts(lambda row,path,stamp: files.append((path, stamp)))
    for path, stamp in files:
      if not os.path.exists(path) or os.path.getmtime(path) > stamp:
        reconfigure_needed = True
        break

    if not reconfigure_needed:
      return True

    util.con_out(
      util.ConsoleHeader,
      'Reparsing build scripts.',
      util.ConsoleNormal
    )

    from ambuild2.frontend.amb2.gen import Generator
    gen = Generator(
      self.vars['sourcePath'],
      self.vars['buildPath'],
      self.vars['options'],
      self.vars['args'],
      self.db
    )
    try:
      gen.generate()
    except:
      traceback.print_exc()
      util.con_err(
        util.ConsoleRed,
        'Failed to reparse build scripts.',
        util.ConsoleNormal
      )
      return False

    # We flush the node cache after this, since database.py expects to get
    # never-before-seen items at the start. We could change this and make
    # nodes individually import, which might be cleaner.
    self.db.flush_caches()

    return True

  def Build(self):
    if not self.reconfigure():
      return False

    return self.build_internal()

  def build_internal(self):
    parser = OptionParser("usage: %prog [options]")
    parser.add_option("--no-color", dest="no_color", action="store_true", default=False,
                      help="Disable console colors.")
    parser.add_option("--show-graph", dest="show_graph", action="store_true", default=False,
                      help="Show the dependency graph and then exit.")
    parser.add_option("--show-changed", dest="show_changed", action="store_true", default=False,
                      help="Show the list of dirty nodes and then exit.")
    parser.add_option("--show-damage", dest="show_damage", action="store_true", default=False,
                      help="Show the computed change graph and then exit.")
    parser.add_option("--show-commands", dest="show_commands", action="store_true", default=False,
                      help="Show the computed command graph and then exit.")
    parser.add_option("--show-steps", dest="show_steps", action="store_true", default=False,
                      help="Show the computed build steps and then exit.")
    parser.add_option("-j", "--jobs", dest="jobs", type="int", default=0,
                      help="Number of worker processes. Minimum number is 1; default is #cores * 1.25.")
    self.options, self.args = parser.parse_args()

    # This doesn't completely work yet because it's not communicated to child
    # processes. We'll have to send a message down or up to fix this.
    if self.options.no_color:
      util.DisableConsoleColors()

    if self.options.show_graph:
      self.db.printGraph()
      return True

    if self.options.show_changed:
      dmg_list = damage.ComputeDamageGraph(self.db, only_changed=True)
      for entry in dmg_list:
        if not entry.isFile():
          continue
        print(entry.format())
      return True

    dmg_graph = damage.ComputeDamageGraph(self.db)
    if not dmg_graph:
      return False

    # If we get here, we have to compute damage.
    if self.options.show_damage:
      dmg_graph.printGraph()
      return True

    dmg_graph.filter_commands()

    if self.options.show_commands:
      dmg_graph.printGraph()
      return True
    
    builder = Builder(self, dmg_graph)
    if self.options.show_steps:
      builder.printSteps()
      return True

    if not builder.update():
      util.con_err(
        util.ConsoleHeader,
        'Build failed.',
        util.ConsoleNormal
      )
      return False

    util.con_out(
      util.ConsoleHeader,
      'Build succeeded.',
      util.ConsoleNormal
    )
    return True

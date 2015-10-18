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
import traceback
import os, sys, imp
from ambuild2 import util, database, damage
from ambuild2.builder import Builder
from ambuild2.ipc import ProcessManager, MessagePump
from optparse import OptionParser

class Context(object):
  def __init__(self, buildPath, options, args):
    self.buildPath = buildPath
    self.options = options
    self.args = args
    self.cacheFolder = os.path.join(buildPath, '.ambuild2')
    self.dbpath = os.path.join(self.cacheFolder, 'graph')

    # This doesn't completely work yet because it's not communicated to child
    # processes. We'll have to send a message down or up to fix this.
    if self.options.no_color:
      util.DisableConsoleColors()

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
        raise
        sys.exit(1)

    self.restore_environment()

    self.db = database.Database(self.dbpath)
    self.messagePump = MessagePump()
    self.procman = ProcessManager(self.messagePump)
    self.db.connect()

  def __enter__(self):
    return self

  def __exit__(self, type, value, traceback):
    self.procman.shutdown()
    self.db.close()

  # Restore important environment properties that were present when this
  # build was configured.
  def restore_environment(self):
    if 'env' not in self.vars:
      return

    env = self.vars['env']
    for key in env:
      os.environ[key] = env[key]

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

    # The database should be upgraded here, so we should always have an
    # API version set.
    api_version = self.db.query_var('api_version')
    assert api_version is not None

    if api_version == '2.0':
      from ambuild2.frontend.v2_0.amb2.gen import Generator

    gen = Generator.FromVars(self.vars, self.db, self.options.refactor)
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

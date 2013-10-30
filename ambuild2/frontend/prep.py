# vim: set ts=8 sts=2 sw=2 tw=99 et:
#
# This file is part of AMBuild.
# 
# AMBuild is free software: you can Headeristribute it and/or modify
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
import os, sys
import platform
from ambuild2 import util
from optparse import OptionParser

class Preparer(object):
  def __init__(self, sourcePath, buildPath):
    self.sourcePath = sourcePath
    self.buildPath = buildPath
    self.host_platform = util.Platform()

    self.options = OptionParser("usage: %prog [options]")
    self.options.add_option("-g", "--gen", type="string", dest="generator", default="ambuild2",
                            help="Build system generator to use. See --list-gen")
    self.options.add_option("--list-gen", action="store_true", dest="list_gen", default=False,
                            help="List available build system generators, then exit.")
    self.options.add_option("--make-scripts", action="store_true", dest="make_scripts", default=False,
                            help="Generate extra command-line files for building (build.py, Makefile).")

  @staticmethod
  def default_build_folder(prep):
    return 'obj-' + util.Platform() + '-' + platform.machine()

  def Configure(self): 
    options, args = self.options.parse_args()

    if options.list_gen:
      print('Available build system generators:')
      print('  {0:24} - AMBuild 2 (default)'.format('ambuild2'))
      print('  {0:24} - Visual Studio project files'.format('vcxproj'))
      sys.exit(0)

    source_abspath = os.path.normpath(os.path.abspath(self.sourcePath))
    build_abspath = os.path.normpath(os.path.abspath(self.buildPath))
    if source_abspath == build_abspath:
      if type(self.default_build_folder) is str:
        objfolder = self.default_build_folder
      else:
        objfolder = self.default_build_folder(self)
      new_buildpath = os.path.join(self.buildPath, objfolder)

      util.con_err(
        util.ConsoleHeader,
        'Warning: build is being configured in the source tree.',
        util.ConsoleNormal
      )
      if os.path.exists(os.path.join(new_buildpath, '.ambuild2')):
        util.con_err(
          util.ConsoleHeader,
          'Re-using build folder: ',
          util.ConsoleBlue,
          '{0}'.format(objfolder),
          util.ConsoleNormal
        )
      elif os.path.exists(os.path.join(new_buildpath)) and len(os.listdir(new_buildpath)):
        sys.stderr.write('Tried to use "{0}" as a build folder, but it is not empty!\n'.format(objfolder))
        sys.exit(1)
      else:
        util.con_err(
          util.ConsoleHeader,
          'Creating "',
          util.ConsoleBlue,
          '{0}'.format(objfolder),
          util.ConsoleHeader,
          '" as a build folder.',
          util.ConsoleNormal
        )
        os.mkdir(new_buildpath)
      self.buildPath = new_buildpath

    if options.generator == 'ambuild2':
      from . amb2 import gen
      builder = gen.Generator(self.sourcePath, self.buildPath, options, args)
    elif options.generator == 'vcxproj':
      from frontend import vcxproj_gen
      builder = vcxproj_gen.Generator(self.sourcePath, self.buildPath, options, args)
    else:
      sys.stderr.write('Unrecognized build generator: ' + options.generator + '\n')
      sys.exit(1)

    with util.FolderChanger(self.buildPath):
      if not builder.Generate():
        sys.stderr.write('Configure failed.\n')
        sys.exit(1)

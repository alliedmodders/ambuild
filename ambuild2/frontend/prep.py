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
import sys
from optparse import OptionParser

class Preparer(object):
  def __init__(self, sourcePath, buildPath):
    self.sourcePath = sourcePath
    self.buildPath = buildPath

    self.options = OptionParser("usage: %prog [options]")
    self.options.add_option("-g", "--gen", type="string", dest="generator", default="ambuild2",
                            help="Build system generator to use. See --list-gen")
    self.options.add_option("--list-gen", action="store_true", dest="list_gen", default=False,
                            help="List available build system generators, then exit.")

  def Configure(self): 
    options, args = self.options.parse_args()

    if options.list_gen:
      print('Available build system generators:')
      print('  {0:24} - AMBuild 2 (default)'.format('ambuild2'))
      print('  {0:24} - Visual Studio project files'.format('vcxproj'))
      sys.exit(0)

    if options.generator == 'ambuild2':
      from . amb2 import gen
      builder = gen.Generator(self.sourcePath, self.buildPath, options, args)
    elif options.generator == 'vcxproj':
      from frontend import vcxproj_gen
      builder = vcxproj_gen.Generator(self.sourcePath, self.buildPath, options, args)
    else:
      sys.stderr.write('Unrecognized build generator: ' + options.generator + '\n')
      sys.exit(1)

    if not builder.Generate():
      sys.stderr.write('Configure failed.\n')
      sys.exit(1)

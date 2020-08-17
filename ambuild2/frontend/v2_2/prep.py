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
# along wi, systh AMBuild. If not, see <http://www.gnu.org/licenses/>.
import argparse
import os
import sys
import platform
import traceback
from ambuild2 import util
from ambuild2.frontend.system import System

class Preparer(object):
    def __init__(self, sourcePath, buildPath):
        self.sourcePath = sourcePath
        self.buildPath = buildPath
        self.host = System.Host

        self.options = argparse.ArgumentParser()
        self.options.add_argument("-g",
                                  "--gen",
                                  type = str,
                                  dest = "generator",
                                  default = "ambuild2",
                                  help = "Build system generator to use. See --list-gen")
        self.options.add_argument("--list-gen",
                                  action = "store_true",
                                  dest = "list_gen",
                                  default = False,
                                  help = "List available build system generators, then exit.")
        self.options.add_argument(
            "--make-scripts",
            action = "store_true",
            dest = "make_scripts",
            default = False,
            help = "Generate extra command-line files for building (build.py, Makefile).")
        self.options.add_argument("--no-color",
                                  action = "store_true",
                                  dest = "no_color",
                                  default = False,
                                  help = "Disable color output in the terminal.")
        self.options.add_argument(
            "--symbol-files",
            action = "store_true",
            dest = "symbol_files",
            default = False,
            help = "Split debugging symbols from binaries into separate symbol files.")

        # Generator specific options.
        self.options.add_argument("--vs-version", type = str, dest = "vs_version", default = "14")
        self.options.add_argument("--vs-split",
                                  action = 'store_true',
                                  dest = "vs_split",
                                  default = False)

    @staticmethod
    def default_build_folder(prep):
        return 'objdir'

    def Configure(self):
        args = self.options.parse_args()

        # In order to support pickling, we need to rewrite |options| to not use
        # optparse.Values, since its implementation changes across Python versions.
        options = util.Expando()
        for attr in vars(args):
            setattr(options, attr, getattr(args, attr))

        if options.list_gen:
            print('Available build system generators:')
            print('  {0:24} - AMBuild 2 (default)'.format('ambuild2'))
            print('  {0:24} - Visual Studio'.format('vs'))
            print('')
            print('Extra options:')
            print('  --vs-version=N        Visual Studio: IDE version (2015 or 14 default)')
            print(
                '  --vs-split            Visual Studio: generate one project file per configuration'
            )
            sys.exit(0)

        if options.no_color:
            util.DisableConsoleColors()

        source_abspath = os.path.normpath(os.path.abspath(self.sourcePath))
        build_abspath = os.path.normpath(os.path.abspath(self.buildPath))
        if source_abspath == build_abspath:
            if util.IsString(self.default_build_folder):
                objfolder = self.default_build_folder
            else:
                objfolder = self.default_build_folder(self)
            new_buildpath = os.path.join(self.buildPath, objfolder)

            util.con_err(util.ConsoleHeader,
                         'Warning: build is being configured in the source tree.',
                         util.ConsoleNormal)
            if os.path.exists(os.path.join(new_buildpath)):
                has_amb2 = os.path.exists(os.path.join(new_buildpath, '.ambuild2'))
                if not has_amb2 and len(
                        os.listdir(new_buildpath)) and options.generator == 'ambuild2':
                    util.con_err(util.ConsoleRed, 'Tried to use ', util.ConsoleBlue, objfolder,
                                 util.ConsoleRed, ' as a build folder, but it is not empty!',
                                 util.ConsoleNormal)
                    raise Exception('build folder has unrecognized files')

                util.con_err(util.ConsoleHeader, 'Re-using build folder: ', util.ConsoleBlue,
                             '{0}'.format(objfolder), util.ConsoleNormal)
            else:
                util.con_err(util.ConsoleHeader, 'Creating "', util.ConsoleBlue,
                             '{0}'.format(objfolder), util.ConsoleHeader, '" as a build folder.',
                             util.ConsoleNormal)
                os.mkdir(new_buildpath)
            self.buildPath = new_buildpath

        from ambuild2.frontend.v2_2.context_manager import ContextManager

        cm = ContextManager(self.sourcePath, self.buildPath, os.getcwd(), options, args)

        with util.FolderChanger(self.buildPath):
            try:
                if not cm.generate(options.generator):
                    sys.stderr.write('Configure failed.\n')
                    sys.exit(1)
            except Exception as e:
                traceback.print_exc()
                util.con_err(util.ConsoleRed, 'Configure failed: {}'.format(e), util.ConsoleNormal)

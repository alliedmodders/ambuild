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
import os
from ambuild2 import util
from ambuild2.frontend.v2_1.cpp.vendor import Vendor

class GCCLookalike(Vendor):
    def __init__(self, version):
        super(GCCLookalike, self).__init__(version)

    @property
    def behavior(self):
        return 'gcc'

    @property
    def definePrefix(self):
        return '-D'

    @property
    def objSuffix(self):
        return '.o'

    @property
    def debugInfoArgv(self):
        return []

    def parseDebugInfoType(self, debuginfo):
        return debuginfo

    def formatInclude(self, outputPath, includePath):
        return ['-I', os.path.normpath(includePath)]

    def objectArgs(self, sourceFile, objFile):
        return ['-H', '-c', sourceFile, '-o', objFile]

    def staticLinkArgv(self, files, outputFile):
        return ['ar', 'rcs', outputFile] + files

    def programLinkArgv(self, cmd_argv, files, linkFlags, symbolFile, outputFile):
        return cmd_argv + files + linkFlags + ['-o', outputFile]

    def libLinkArgv(self, cmd_argv, files, linkFlags, symbolFile, outputFile):
        argv = cmd_argv + files + linkFlags
        if util.IsMac():
            argv += ['-dynamiclib']
        else:
            argv += ['-shared']
        argv += ['-o', outputFile]
        return argv

    def preprocessArgv(self, sourceFile, outFile):
        return ['-H', '-E', sourceFile, '-o', outFile]

    @staticmethod
    def IncludePath(outputPath, includePath):
        return includePath

class GCC(GCCLookalike):
    def __init__(self, version):
        super(GCC, self).__init__(version)

    @property
    def name(self):
        return 'gcc'

    @property
    def family(self):
        return 'gcc'

    def like(self, name):
        return name == 'gcc'

class Clang(GCCLookalike):
    def __init__(self, version, vendor_prefix = None):
        # Set this first, since the constructor will need it.
        self.vendor_name = 'clang'
        if vendor_prefix is not None:
            self.vendor_name = '{0}-clang'.format(vendor_prefix)
        super(Clang, self).__init__(version)

    @property
    def name(self):
        return self.vendor_name

    @property
    def family(self):
        return 'clang'

    def like(self, name):
        return name == 'gcc' or name == 'clang' or name == self.name

    @property
    def debugInfoArgv(self):
        return ['-g3']

class Emscripten(Clang):
    def __init__(self, version):
        # Set this first, since the constructor will need it.
        super(Emscripten, self).__init__(version, 'emscripten')

    def nameForExecutable(self, name):
        return name + '.js'

    def nameForSharedLibrary(self, name):
        return name + '.bc'

    def nameForStaticLibrary(self, name):
        return util.StaticLibPrefix + name + '.a'

    @property
    def name(self):
        return 'emscripten'

    @property
    def family(self):
        return 'emscripten'

    def like(self, name):
        return name == 'gcc' or name == 'clang' or name == 'emscripten-clang' or name == 'emscripten'

    @property
    def debugInfoArgv(self):
        return []

    def staticLinkArgv(self, files, outputFile):
        return ['emar', 'rcs', outputFile] + files

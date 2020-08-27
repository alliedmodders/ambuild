# vim: set ts=8 sts=4 sw=4 tw=99 et:
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
from ambuild2.frontend.v2_2.cpp.deptypes import PchNodes
from ambuild2.frontend.v2_2.cpp.vendor import Vendor

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

    @property
    def pch_needs_source_file(self):
        return False

    def formatInclude(self, build_root, output_path, include):
        return ['-I', os.path.normpath(include)]

    # We could use -MF -, but trying to parse something as idiosyncratic as Make
    # is probably best done when absolutely nothing else might be interspersed.
    def emits_dependency_file(self):
        return True

    def dependencyArgv(self, out_file):
        return ['-MD', '-MF', out_file]

    def objectArgs(self, sourceFile, objFile):
        return ['-c', sourceFile, '-o', objFile]

    def makePchArgv(self, source_file, obj_file, source_type):
        return ['-c', '-x', source_type + '-header', source_file, '-o', obj_file]

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

    @property
    def pch_needs_strong_deps(self):
        return False

    def nameForPch(self, source_file):
        return source_file + '.gch'

    def formatPchInclude(self, build_root, output_path, pch):
        local_path = os.path.relpath(pch.header_file.path, output_path)
        return ['-include', local_path, '-I', os.path.split(local_path)[0]]

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

    def nameForPch(self, source_file):
        return source_file + '.pch'

    def formatPchInclude(self, build_root, output_path, pch):
        pch_path = os.path.relpath(pch.pch_file.path, output_path)
        return ['-include-pch', pch_path, '-I', os.path.split(pch_path)[0]]

    @property
    def pch_needs_strong_deps(self):
        return True

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

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
from ambuild2.frontend.version import Version

class Vendor(object):
    def __init__(self, name, version, behavior, command, objSuffix):
        self.name = name
        self.version = version
        self.behavior = behavior
        self.command = command
        self.objSuffix = objSuffix
        self.debuginfo_argv = []
        self.extra_props = {}
        self.versionObject = Version('{0}-{1}'.format(name, self.version))

    def nameForExecutable(self, name):
        return name + util.ExecutableSuffix

    def nameForSharedLibrary(self, name):
        return name + util.SharedLibSuffix

    def nameForStaticLibrary(self, name):
        return util.StaticLibPrefix + name + util.StaticLibSuffix

class MSVC(Vendor):
    def __init__(self, command, version):
        super(MSVC, self).__init__('msvc', version, 'msvc', command, '.obj')
        self.definePrefix = '/D'
        self.debuginfo_argv = ['/Zi']
        if int(self.version) >= 1800:
            self.debuginfo_argv += ['/FS']

    def like(self, name):
        return name == 'msvc'

    def parse_debuginfo(self, debuginfo):
        if debuginfo == 'bundled':
            return 'separate'
        return debuginfo

    @staticmethod
    def IncludePath(outputPath, includePath):
        # Hack - try and get a relative path because CL, with either
        # /Zi or /ZI, combined with subprocess, apparently tries and
        # looks for paths like c:\bleh\"c:\bleh" <-- wtf
        # .. this according to Process Monitor
        outputPath = os.path.normcase(outputPath)
        includePath = os.path.normcase(includePath)
        outputDrive = os.path.splitdrive(outputPath)[0]
        includeDrive = os.path.splitdrive(includePath)[0]
        if outputDrive == includeDrive:
            return os.path.relpath(includePath, outputPath)
        return includePath

    def formatInclude(self, outputPath, includePath):
        return ['/I', self.IncludePath(outputPath, includePath)]

    def preprocessArgs(self, sourceFile, outFile):
        return ['/showIncludes', '/nologo', '/P', '/c', sourceFile, '/Fi' + outFile]

    def objectArgs(self, sourceFile, objFile):
        return ['/showIncludes', '/nologo', '/c', sourceFile, '/Fo' + objFile]

class CompatGCC(Vendor):
    def __init__(self, name, command, version):
        super(CompatGCC, self).__init__(name, version, 'gcc', command, '.o')
        parts = version.split('.')
        self.majorVersion = int(parts[0])
        self.minorVersion = int(parts[1])
        self.definePrefix = '-D'

    def formatInclude(self, outputPath, includePath):
        return ['-I', os.path.normpath(includePath)]

    def objectArgs(self, sourceFile, objFile):
        return ['-H', '-c', sourceFile, '-o', objFile]

    def parse_debuginfo(self, debuginfo):
        return debuginfo

class GCC(CompatGCC):
    def __init__(self, command, version):
        super(GCC, self).__init__('gcc', command, version)
        self.debuginfo_argv = ['-g3', '-ggdb3']

    def like(self, name):
        return name == 'gcc'

class Clang(CompatGCC):
    def __init__(self, vendor_name, command, version):
        super(Clang, self).__init__(vendor_name, command, version)
        self.name = 'clang'  # Rewrite name to just 'clang' to make things easier.
        self.vendor_name = vendor_name
        self.debuginfo_argv = ['-g3']

    def like(self, name):
        return name == 'gcc' or name == 'clang' or name == self.vendor_name

class Emscripten(Clang):
    def __init__(self, command, version):
        super(Emscripten, self).__init__('emscripten', command, version)
        self.name = 'emscripten'

    def like(self, name):
        if name == 'emscripten':
            return True
        return super(Emscripten, self).like(name)

    def nameForExecutable(self, name):
        return name + '.js'

class SunPro(Vendor):
    def __init__(self, command, version):
        super(SunPro, self).__init__('sun', version, 'sun', command, '.o')
        self.definePrefix = '-D'
        self.debuginfo_argv = ['-g3']

    def formatInclude(self, outputPath, includePath):
        return ['-I', os.path.normpath(includePath)]

    def objectArgs(self, sourceFile, objFile):
        return ['-H', '-c', sourceFile, '-o', objFile]

    def like(self, name):
        return name == 'sun'

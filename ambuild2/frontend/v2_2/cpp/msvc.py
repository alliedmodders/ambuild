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
import re
from ambuild2 import util
from ambuild2.frontend.v2_2.cpp.deptypes import PchNodes
from ambuild2.frontend.v2_2.cpp.vendor import Vendor

# Microsoft Visual C++
class MSVC(Vendor):
    def __init__(self, version):
        super(MSVC, self).__init__(version)

    @property
    def name(self):
        return 'msvc'

    @property
    def behavior(self):
        return 'msvc'

    @property
    def family(self):
        return 'msvc'

    def like(self, name):
        return name == 'msvc'

    @property
    def definePrefix(self):
        return '/D'

    @property
    def objSuffix(self):
        return '.obj'

    @property
    def debugInfoArgv(self):
        return ['/Z7']

    def makePchArgv(self, source_file, pch_file, source_type):
        return ['/showIncludes', '/nologo', '/Yc', '/c', source_file, '/Fp' + pch_file]

    def parseDebugInfoType(self, debuginfo):
        if debuginfo == 'bundled':
            return 'separate'
        return debuginfo

    def objectArgs(self, sourceFile, objFile):
        return ['/showIncludes', '/nologo', '/c', sourceFile, '/Fo' + objFile]

    def staticLinkArgv(self, files, outputFile):
        return ['lib', '/OUT:' + outputFile] + files

    def programLinkArgv(self, cmd_argv, files, linkFlags, symbolFile, outputFile):
        argv = cmd_argv + files
        argv += ['/link']
        argv += linkFlags
        argv += [
            '/OUT:' + outputFile,
            '/nologo',
        ]
        if symbolFile:
            argv += ['/DEBUG', '/PDB:"' + symbolFile + '.pdb"']
        return argv

    def libLinkArgv(self, cmd_argv, files, linkFlags, symbolFile, outputFile):
        argv = cmd_argv + files
        argv += ['/link']
        argv += linkFlags
        argv += [
            '/OUT:' + outputFile,
            '/nologo',
            '/DLL',
        ]
        if symbolFile:
            argv += ['/DEBUG', '/PDB:"' + symbolFile + '.pdb"']
        return argv

    def preprocessArgv(self, sourceFile, outFile):
        return ['/showIncludes', '/nologo', '/P', '/c', sourceFile, '/Fi' + outFile]

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
        if outputDrive and includeDrive and outputDrive != includeDrive:
            return includePath
        return os.path.relpath(includePath, outputPath)

    @staticmethod
    def RcIncludePath(outputPath, includePath):
        # Same as IncludePath, but prefer absolute paths because it breaks on
        # relative ones...
        outputPath = os.path.normcase(outputPath)
        includePath = os.path.normcase(includePath)
        outputDrive = os.path.splitdrive(outputPath)[0]
        includeDrive = os.path.splitdrive(includePath)[0]
        if outputDrive != includeDrive:
            return includePath
        return os.path.relpath(includePath, outputPath)

    def formatInclude(self, output_path, include):
        return ['/I', MSVC.IncludePath(output_path, include)]

    def formatPchInclude(self, output_path, pch):
        folder, header_name = os.path.split(pch.header_file.path)
        argv = [
            '/Fp' + MSVC.IncludePath(output_path, pch.pch_file.path),
            '/Yu' + header_name,
            '/I',
            MSVC.IncludePath(output_path, folder),
        ]
        return argv

    ##
    # MSVC-specific properties.
    ##
    @property
    def shared_pdb_name(self):
        cl_version = int(self.version_string)

        # Truncate down to the major version then correct the offset
        # There is some evidence that the first digit of the minor version can be used for the PDB, but I can't reproduce it
        cl_version = int(cl_version / 100) - 6

        # Microsoft introduced a discontinuity with vs2015
        if cl_version >= 13:
            cl_version += 1

        # Pad it back out again
        cl_version *= 10

        return 'vc{0}.pdb'.format(cl_version)

    @property
    def pch_needs_strong_deps(self):
        return True

    @property
    def pch_needs_source_file(self):
        return True

    @property
    def shared_pdb_flags(self):
        return set(['/Zi', '/ZI'])

    def nameForPch(self, source_file):
        return os.path.splitext(source_file)[0] + '.pch'

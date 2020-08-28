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
    def IncludePath(output_path, include_path):
        assert os.path.isabs(output_path)

        output_path = os.path.normcase(output_path)

        if not os.path.isabs(include_path):
            abs_include_path = os.path.join(output_path, include_path)
        else:
            abs_include_path = include_path
        abs_include_path = os.path.normcase(abs_include_path)

        # Hack - try and get a relative path because CL, with either
        # /Zi or /ZI, combined with subprocess, apparently tries and
        # looks for paths like c:\bleh\"c:\bleh" <-- wtf
        # .. this according to Process Monitor
        output_drive, _ = os.path.splitdrive(output_path)
        include_drive, _ = os.path.splitdrive(abs_include_path)
        if output_drive != include_drive:
            return os.path.normcase(include_path)
        return os.path.relpath(abs_include_path, output_path)

    def formatInclude(self, build_root, output_path, include):
        return ['/I', MSVC.IncludePath(output_path, include)]

    def formatPchInclude(self, build_root, output_path, pch):
        folder, header_name = os.path.split(pch.header_file.path)

        # Include path calculation expects a path relative to output_path, so
        # we need to transform it.
        pch_rel_folder = os.path.relpath(os.path.join(build_root, pch.pch_file.path), output_path)
        argv = [
            '/Fp' + MSVC.IncludePath(output_path, pch_rel_folder),
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

    # cl.exe /showIncludes does not show anything at all for precompiled headers,
    # so the only way we can build a proper dependency is by rebuilding every
    # source file that *might* use the PCH, whether or not it actually does.
    @property
    def pch_needs_strong_deps(self):
        return True

    # cl.exe precompiles source files, technically, not headers. So we need to
    # link against something.
    @property
    def pch_needs_source_file(self):
        return True

    @property
    def shared_pdb_flags(self):
        return set(['/Zi', '/ZI'])

    def nameForPch(self, source_file):
        return os.path.splitext(source_file)[0] + '.pch'

    @property
    def emits_dependency_file(self):
        return False

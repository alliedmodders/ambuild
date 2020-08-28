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
from ambuild2.frontend.version import Version

class Vendor(object):
    def __init__(self, version):
        super(Vendor, self).__init__()
        self.version_string = version
        self.version = Version('{0}-{1}'.format(self.name, version))
        self.extra_props = {}

    def nameForExecutable(self, name):
        return name + util.ExecutableSuffix

    def nameForSharedLibrary(self, name):
        return name + util.SharedLibSuffix

    def nameForStaticLibrary(self, name):
        return util.StaticLibPrefix + name + util.StaticLibSuffix

    def equals(self, other):
        return self.name == other.name and \
               self.version == other.version and \
               self.extra_props == other.extra_props

    def __str__(self):
        return '{0}-{1}'.format(self.name, self.version_string)

    @property
    def behavior(self):
        raise Exception("Must be implemented")

    @property
    def name(self):
        raise Exception("Must be implemented")

    @property
    def family(self):
        raise Exception("Must be implemented")

    def like(self, name):
        raise Exception("Must be implemented")

    @property
    def definePrefix(self):
        raise Exception("Must be implemented")

    @property
    def objSuffix(self):
        raise Exception("Must be implemented")

    @property
    def debug_info_argv(self):
        raise Exception("Must be implemented")

    def parseDebugInfoType(self, debuginfo):
        raise Exception("Must be implemented")

    def formatInclude(self, outputPath, includePath):
        raise Exception("Must be implemented")

    def formatPchInclude(self, output_path, pch):
        raise Exception("Must be implemented")

    def objectArgs(self, sourceFile, objFile):
        raise Exception("Must be implemented")

    # Note: this should return a complete initial argv, not partial.
    # AMBuild does not detect AR/LIB separately yet.
    def staticLinkArgv(self, files, outputFile):
        raise Exception("Must be implemented")

    # For this and libLinkArgv(), the symbolFile should not have an extension.
    # The vendor chooses the extension if it supports symbol files at all.
    def programLinkArgv(self, cmd_argv, files, linkFlags, symbolFile, outputFile):
        raise Exception("Must be implemented")

    def libLinkArgv(self, cmd_argv, files, linkFlags, symbolFile, outputFile):
        raise Exception("Must be implemented")

    def nameForPrecompiledHeader(self, name):
        raise Exception("Must be implemented")

    @property
    def pch_needs_source_file(self):
        raise Exception("Must be implemented")

    @property
    def shared_pdb_flags(self):
        return set()

    def nameForPch(self, source_file):
        raise Exception("Must be implemented")

    @property
    def emits_dependency_file(self):
        raise Exception("Must be implemented")

    # If emits_dependency_file is True, this must be implemented.
    def dependencyArgv(self, out_file):
        raise Exception("Must be implemented")

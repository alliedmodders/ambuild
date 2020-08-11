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

class SunPro(Vendor):
    def __init__(self, version):
        super(SunPro, self).__init__(version)

    @property
    def name(self):
        return 'sun'

    @property
    def behavior(self):
        return 'sun'

    @property
    def family(self):
        return 'sun'

    def like(self, name):
        return name == 'sun'

    @property
    def definePrefix(self):
        return '/D'

    @property
    def objSuffix(self):
        return '.o'

    @property
    def debugInfoArgv(self):
        return ['-g3']

    def parseDebugInfoType(self, debuginfo):
        return debuginfo

    def objectArgs(self, sourceFile, objFile):
        return ['-H', '-c', sourceFile, '-o', objFile]

    def formatInclude(self, outputPath, includePath):
        return ['-I', os.path.normpath(includePath)]

    def staticLinkArgv(self, files, outputFile):
        return ['ar', 'rcs', outputFile] + files

    def programLinkArgv(self, cmd_argv, files, linkFlags, symbolFile, outputFile):
        return cmd_argv + files + linkFlags + ['-o', outputFile]

    def libLinkArgv(self, cmd_argv, files, linkFlags, symbolFile, outputFile):
        return cmd_argv + files + linkFlags + ['-o', outputFile]

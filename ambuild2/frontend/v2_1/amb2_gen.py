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
from ambuild2.frontend import amb2
from ambuild2.frontend.v2_1.cpp import detect

class Generator(amb2.Generator):
    def __init__(self, cm):
        super(Generator, self).__init__(cm)

    def detectCompilers(self, options):
        if options is None:
            options = {}
        if not self.compiler:
            with util.FolderChanger(self.cacheFolder):
                self.base_compiler = detect.AutoDetectCxx(self.cm.target, self.cm.options, options)
                if self.base_compiler is None:
                    raise Exception('Could not detect a suitable C/C++ compiler')
                self.compiler = self.base_compiler.clone()

        return self.compiler

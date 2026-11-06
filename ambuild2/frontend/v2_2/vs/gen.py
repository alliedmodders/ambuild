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
import ambuild2.frontend.vs.gen as vs_gen
from ambuild2.frontend.v2_2.vs import cxx
from ambuild2.frontend.v2_2.vs import export_sln

class Generator(vs_gen.Generator):
    def __init__(self, cm):
        super(Generator, self).__init__(cm)
        self.vs_version_number = cxx.Compiler.GetVersionFromVS(self.vs_version)
        self.vs_vendor = cxx.VisualStudio(self.vs_version_number)

    # Overridden.
    def postGenerate(self):
        super(Generator, self).postGenerate()

        # One solution with every project, so building it builds the libraries
        # a binary links before the binary itself.
        name = os.path.basename(os.path.normpath(self.cm.sourcePath))
        export_sln.export(self.cm, os.path.join(self.cm.buildPath, name + '.sln'), self.projects_)

    # Overridden.
    def detectCompilers(self, **kwargs):
        return cxx.Compiler(self.vs_vendor, kwargs.pop('target_arch', 'x86'))

    def newProgramProject(self, context, name):
        return cxx.Project(cxx.Program, name)

    def newLibraryProject(self, context, name):
        return cxx.Project(cxx.Library, name)

    def newStaticLibraryProject(self, context, name):
        return cxx.Project(cxx.StaticLibrary, name)

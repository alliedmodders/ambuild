# vim: set ts=8 sts=4 sw=4 tw=99 et:
#
# This file is part of AMBuild.
#
# AMBuild is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# at your option any later version.
#
# AMBuild is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with AMBuild. If not, see <http://www.gnu.org/licenses/>.

from ambuild2.frontend import amb2_gen
from ambuild2.frontend.v2_2.context import RootBuildContext, TopLevelBuildContext
from ambuild2.frontend.v2_2.context_manager import ContextManager
from ambuild2.frontend.v2_2.cpp.builders import Project
from ambuild2.frontend.v2_2.cpp.compiler import CliCompiler

class Generator(amb2_gen.Generator):
    def __init__(self, cm: ContextManager) -> None: ...
    def detectCompilers(self, **kwargs: str) -> CliCompiler: ...
    def newProgramProject(self, context: RootBuildContext | TopLevelBuildContext, name: str) -> Project: ...
    def newLibraryProject(self, context: RootBuildContext | TopLevelBuildContext, name: str) -> Project: ...
    def newStaticLibraryProject(self, context: RootBuildContext | TopLevelBuildContext, name: str) -> Project: ...

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

from abc import abstractmethod
from typing import Literal

from ambuild2.frontend.context_manager import ContextManager
from ambuild2.frontend.v2_2.context import RootBuildContext, TopLevelBuildContext
from ambuild2.nodetypes import DirtyState, Entry, EnvDataTuple

class BaseGenerator:
    cm: ContextManager
    def __init__(self, cm: ContextManager) -> None: ...
    @property
    def backend(self) -> Literal['amb2', 'vs']: ...
    def addSymlink(self, context: RootBuildContext | TopLevelBuildContext, source: Entry | str, output_path: Entry | str) -> tuple[Entry, list[Entry]]: ...
    @abstractmethod
    def addFolder(self, context: RootBuildContext | TopLevelBuildContext, folder: str) -> object: ...
    @abstractmethod
    def addCopy(self, context: RootBuildContext | TopLevelBuildContext, source: Entry | str, output_path: Entry | str) -> tuple[Entry, list[Entry]] | tuple[None, tuple[None]]: ...
    @abstractmethod
    def addShellCommand(
        self,
        context: RootBuildContext | TopLevelBuildContext,
        inputs: list[Entry],
        argv: list[str],
        outputs: list[str],
        folder: Entry | Literal[-1] | None = ...,
        dep_type: DirtyState | None = ...,
        weak_inputs: list[Entry] | None = ...,
        shared_outputs: list[Entry] | None = ...,
        env_data: EnvDataTuple | None = ...,
    ) -> tuple[Entry, list[Entry]]: ...
    @abstractmethod
    def addConfigureFile(self, context: RootBuildContext | TopLevelBuildContext | None, path: str) -> None: ...
    @abstractmethod
    def newProgramProject(self, context: RootBuildContext | TopLevelBuildContext, name: str) -> object: ...
    @abstractmethod
    def newLibraryProject(self, context: RootBuildContext | TopLevelBuildContext, name: str) -> object: ...
    @abstractmethod
    def newStaticLibraryProject(self, context: RootBuildContext | TopLevelBuildContext, name: str) -> object: ...

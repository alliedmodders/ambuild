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

import argparse
from abc import abstractmethod
from collections.abc import Callable, Mapping, MutableMapping, Sequence
from typing import Any, Literal, overload

from ambuild2.database import Database
from ambuild2.frontend.base_generator import BaseGenerator
from ambuild2.frontend.v2_2.context import RootBuildContext, TopLevelBuildContext
from ambuild2.frontend.v2_2.context_manager import ContextManager
from ambuild2.frontend.v2_2.cpp.builders import ObjectFileTaskBase
from ambuild2.frontend.v2_2.cpp.compiler import CliCompiler
from ambuild2.nodetypes import DirtyState, Entry, EnvDataTuple, NodeType
from ambuild2.util import Expando

class Generator(BaseGenerator):
    cacheFolder: str
    old_scripts_: set[str]
    old_folders_: set[Entry]
    old_commands_: set[Entry]
    rm_list_: list[str]
    bad_outputs_: set[Entry]
    symlink_support: bool
    had_symlink_fallback: bool
    db: Database
    is_bootstrap: bool
    compdb: list[MutableMapping[str, list[str] | str]] = ...

    def __init__(self, cm: ContextManager) -> None: ...
    @property
    def backend(self) -> Literal['amb2']: ...
    @property
    def refactoring(self) -> bool: ...
    def preGenerate(self) -> None: ...
    def cleanup(self) -> None: ...
    def postGenerate(self) -> None: ...
    def saveVars(self) -> None: ...
    def copyBuildVars(self, vars: Mapping[str, Expando | argparse.Namespace | dict[str, str] | str]) -> None: ...
    @overload
    @abstractmethod
    def detectCompilers(self) -> CliCompiler: ...
    @overload
    @abstractmethod
    def detectCompilers(self, **kwargs: str) -> CliCompiler: ...
    def getLocalFolder(self, context: RootBuildContext | TopLevelBuildContext) -> Entry | None: ...
    def generateFolder(self, parent: Entry | None, folder: str) -> Entry: ...
    def isValidFolderEntry(self, folder_entry: Entry) -> bool: ...
    def validateOutputFolder(self, path: str) -> Entry | None: ...
    def parseOutput(self, cwd_entry: Entry | str, path: str, kind: str) -> Entry: ...
    def parseInput(self, context: RootBuildContext | TopLevelBuildContext, source: Entry | str, only_if_exists: bool = False) -> Entry | None: ...
    def addCommand(
        self,
        context: RootBuildContext | TopLevelBuildContext,
        node_type: NodeType,
        folder: Entry,
        data: Mapping[str, list[str] | str | tuple[str, str]] | tuple[str, str],
        inputs: list[Entry | str],
        outputs: list[str],
        weak_inputs: list[Entry] | None = ...,
        shared_outputs: list[str] | None = ...,
        env_data: EnvDataTuple | None = ...,
    ) -> tuple[Entry, list[Entry]]: ...
    def parseCxxDeps(self, context: RootBuildContext | TopLevelBuildContext, binary: CliCompiler, inputs: list[str], items: Sequence[Entry | str | Callable[..., Any] | None]) -> None: ...
    def addFileOp(self, cmd: NodeType, context: RootBuildContext | TopLevelBuildContext, source: Entry | str, output_path: Entry | str) -> tuple[Entry, list[Entry]]: ...
    def addSource(self, context: RootBuildContext | TopLevelBuildContext, source_path: str) -> Entry: ...
    def addCopy(self, context: RootBuildContext | TopLevelBuildContext, source: Entry | str, output_path: Entry | str) -> tuple[Entry, list[Entry]]: ...
    def addSymlink(self, context: RootBuildContext | TopLevelBuildContext, source: Entry | str, output_path: Entry | str) -> tuple[Entry, list[Entry]]: ...
    def addFolder(self, context: RootBuildContext | TopLevelBuildContext, folder: Entry | str) -> Entry: ...
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
        dep_file: str | None = ...,
    ) -> tuple[Entry, list[Entry]]: ...
    def addOutputFile(self, context: RootBuildContext | TopLevelBuildContext, path: str, contents: bytes) -> Entry: ...
    def addConfigureFile(self, context: RootBuildContext | TopLevelBuildContext | None, path: str) -> None: ...
    def addCxxObjTask(self, cx: RootBuildContext | TopLevelBuildContext, shared_outputs: list[Entry] | None, obj: ObjectFileTaskBase) -> list[Entry]: ...
    def addCxxRcTask(self, cx: RootBuildContext | TopLevelBuildContext, obj: ObjectFileTaskBase) -> list[Entry]: ...

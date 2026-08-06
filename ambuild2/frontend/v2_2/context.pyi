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

from collections.abc import Callable, Hashable, Iterable, Mapping
from typing import Any, ClassVar, Literal

import ambuild2.frontend.vs.nodes as vs
from _typeshed import Incomplete
from ambuild2.frontend import context_manager
from ambuild2.frontend.base_generator import BaseGenerator
from ambuild2.frontend.cloneable import CloneableDict, CloneableList
from ambuild2.frontend.proxy import AttributeProxy
from ambuild2.frontend.system import System
from ambuild2.frontend.v2_2.cpp.builders import Project, StaticLibrary
from ambuild2.frontend.v2_2.cpp.compiler import CliCompiler
from ambuild2.frontend.v2_2.cpp.deptypes import CppNodes
from ambuild2.frontend.v2_2.tools.protoc import Protoc
from ambuild2.frontend.version import Version
from ambuild2.nodetypes import Entry, EnvDataTuple

class BaseContext:
    cm: context_manager.ContextManager
    generator_: BaseGenerator | None
    parent_: BaseContext | None
    script_: str
    vars_: dict[str, AttributeProxy | Hashable | list[str] | str]
    proxy_: AttributeProxy

    def __init__(self, cm: context_manager.ContextManager, parent: BaseContext | None, vars: dict[str, Any], script: str) -> None: ...
    @property
    def parent(self) -> BaseContext | None: ...
    @property
    def sourcePath(self) -> str: ...
    @property
    def options(self) -> Any: ...  # Expando
    @property
    def host(self) -> System: ...
    @property
    def originalCwd(self) -> str: ...
    @property
    def backend(self) -> Incomplete: ...
    @property
    def buildPath(self) -> str: ...
    @property
    def apiVersion(self) -> Version: ...
    def Import(self, path: str | list[str], vars: dict[str, str] | None = None) -> Any: ...
    def Eval(self, path: str, vars: dict[str, str] | None = None) -> Any: ...
    def AddConfigureFile(self, path: str) -> None: ...
    def HasFeature(self, name: str) -> bool: ...
    def CloneableDict[KT, VT](self, *args: Mapping[KT, VT] | Iterable[tuple[KT, VT]], **kwargs: VT) -> CloneableDict[KT, VT]: ...
    def CloneableList[T](self, *args: Iterable[T], **kwargs: Any) -> CloneableList[T]: ...

class EmptyContext(BaseContext):
    def __init__(self, generator: BaseGenerator | None, parent: BaseContext | None, vars: dict[str, Any], script: str) -> None: ...

class BuildContext(BaseContext):
    tools: ClassVar[Any]
    localFolder_: Any | None
    sourceFolder: str
    buildFolder: str
    currentSourcePath: str
    currentSourceFolder: str

    def __init__(
        self,
        cm: context_manager.ContextManager,
        parent: BaseContext | None,
        vars: dict[str, Any],
        script: str,
        sourceFolder: str,
        buildFolder: str,
    ) -> None: ...
    def CallBuilder(self, fun: Callable[..., Any]) -> Any: ...
    def Build(self, path: str | list[str], vars: dict[str, Hashable] | None = None) -> Any: ...
    def DetectCxx(self, **kwargs: str) -> CliCompiler: ...
    def DetectProtoc(self, **kwargs: str) -> Protoc: ...
    @property
    def ALWAYS_DIRTY(self) -> object: ...
    @property
    def localFolder(self) -> vs.FolderNode | Entry | None: ...
    def AddSource(self, source_path: str) -> Entry: ...
    def AddSymlink(self, source: str, output_path: str) -> Entry: ...
    def AddFolder(self, folder: str) -> Entry: ...
    def AddCopy(self, source: Entry | str, output_path: Entry | str) -> Entry: ...
    def AddCommand(
        self,
        inputs: Iterable[Entry | str],
        argv: list[str],
        outputs: list[str],
        folder: Entry | Literal[-1] = -1,
        dep_type: str | None = None,
        weak_inputs: list[Entry] = [],
        shared_outputs: list[str] = [],
        env_data: EnvDataTuple | None = None,
        dep_file: str | None = None,
    ) -> list[Entry]: ...
    def Context(self, name: str) -> Incomplete: ...
    def Add(self, taskbuilder: Project | StaticLibrary) -> list[CppNodes]: ...
    def SetBuildFolder(self, folder: str) -> None: ...
    def ProgramProject(self, name: str) -> Project: ...
    def LibraryProject(self, name: str) -> Project: ...
    def StaticLibraryProject(self, name: str) -> Project: ...
    def AddOutputFile(self, path: str, contents: bytes | str) -> Entry: ...

class TopLevelBuildContext(BuildContext):
    def __init__(
        self,
        cm: context_manager.ContextManager,
        parent: RootBuildContext | TopLevelBuildContext | None,
        vars: dict[str, Hashable],
        script: str,
        sourceFolder: str,
        buildFolder: str,
    ) -> None: ...

class RootBuildContext(BuildContext):
    def __init__(self, cm: context_manager.ContextManager, vars: dict[Any, Any], script: str) -> None: ...

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

from collections import OrderedDict

from ambuild2.frontend.v2_2.context import RootBuildContext, TopLevelBuildContext
from ambuild2.frontend.v2_2.cpp.builders import CustomToolCommand
from ambuild2.frontend.v2_2.cpp.deptypes import CppNodes

class ProtocRunner:
    protoc: Protoc
    builder: RootBuildContext | TopLevelBuildContext
    argv: list[str]
    seen_languages: set[str]
    languages: OrderedDict[str, str]
    gen_map: dict[str, dict[str, list[str]]]

    def __init__(self, protoc: Protoc, builder: RootBuildContext | TopLevelBuildContext, includes: list[str]) -> None: ...
    def AddOutput(self, language: str, folder: str) -> None: ...
    def AddSource(self, source_path: str) -> None: ...

class ProtocCppNode:
    lib: list[CppNodes]
    headers: list[str]

    def __init__(self, lib: list[CppNodes], headers: list[str]) -> None: ...

class Protoc:
    path: str
    name: str
    version: str
    extra_argv: list[str]
    includes: list[str]

    def __init__(self, path: str, name: str, version: str) -> None: ...
    def clone(self) -> Protoc: ...
    def Generate(self, builder: RootBuildContext | TopLevelBuildContext, sources: list[str], outputs: list[str], includes: list[str] = ...) -> dict[str, dict[str, list[str]]]: ...
    def StaticLibrary(self, name: str, builder: RootBuildContext | TopLevelBuildContext, cxx: str, sources: list[str], includes: list[str] = ...) -> ProtocCppNode: ...

FoundProtocMap: set[str] = ...

def DetectProtoc(**kwargs: dict[str, str]) -> Protoc: ...

class ProtocTool:
    def __init__(self) -> None: ...
    def evaluate(self, cmd: CustomToolCommand) -> None: ...

class ProtocJob:
    protoc: Protoc
    sources: list[str]
    tool: ProtocTool

    def __init__(self, protoc: Protoc | None = ..., sources: list[str] = ...) -> None: ...

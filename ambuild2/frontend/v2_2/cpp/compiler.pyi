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
from collections.abc import Mapping, Sequence
from typing import ClassVar, Literal

from _typeshed import Incomplete
from ambuild2.frontend.cloneable import Cloneable
from ambuild2.frontend.system import System
from ambuild2.frontend.v2_2.cpp.builders import Library, PrecompiledHeaders, Program, StaticLibrary
from ambuild2.frontend.v2_2.cpp.gcc import GCC, Clang, Emscripten, GccArchiver
from ambuild2.frontend.v2_2.cpp.msvc import MSVC, MsvcArchiver
from ambuild2.frontend.v2_2.cpp.vendor import Linker
from ambuild2.frontend.version import Version
from ambuild2.nodetypes import Entry, EnvDataTuple
from ambuild2.util import Expando

class Compiler:
    attrs_: ClassVar[list[str]]
    shallow_attrs_: ClassVar[list[str]]

    vendor: GCC | Clang | Emscripten | MSVC
    target: System
    linker: Linker
    archiver: GccArchiver | MsvcArchiver
    includes: list[str]
    cxxincludes: list[str]
    cflags: list[str]
    cxxflags: list[str]
    defines: list[str]
    cxxdefines: list[str]
    c_only_flags: list[str]
    rcdefines: list[str]
    linkflags: list[str]
    postlink: list[str]
    sourcedeps: list[Entry]
    weaklinkdeps: list[Entry]
    linkdeps: list[Entry]
    symbol_files_: Literal['separate', 'bundled']

    def __init__(self, vendor: GCC | Clang | Emscripten | MSVC, target: System, options: Expando | None = ...) -> None: ...
    def inherit(self, other: Compiler) -> None: ...
    @abstractmethod
    def clone(self) -> Compiler: ...
    def like(self, name: str) -> bool: ...
    @property
    def behavior(self) -> str: ...
    @property
    def family(self) -> str: ...
    @property
    def version(self) -> Version: ...
    @property
    def symbol_files(self) -> str | None: ...
    @symbol_files.setter
    def symbol_files(self, value: Literal['bundled', 'separate']) -> None: ...
    @abstractmethod
    def Program(self, name: str) -> object: ...
    @abstractmethod
    def Library(self, name: str) -> object: ...
    @abstractmethod
    def StaticLibrary(self, name: str) -> object: ...
    @abstractmethod
    def PrecompiledHeaders(self, name: str, source_type: str) -> object: ...
    @staticmethod
    def Dep(text: str, node: Incomplete | None = None) -> Incomplete: ...

class CliCompiler(Compiler):
    cc_argv: list[str]
    cxx_argv: list[str]
    found_pkg_config_: bool
    env_data: EnvDataTuple | None
    linker_argv: list[str] | None
    archiver_argv: list[str] | None

    def __init__(
        self,
        vendor: GCC | Clang | Emscripten | MSVC,
        target: System,
        cc_argv: list[str],
        cxx_argv: list[str],
        options: Expando | None = None,
        env_data: EnvDataTuple | None = None,
    ) -> None: ...
    def clone(self) -> CliCompiler: ...
    def inherit(self, other: Compiler) -> None: ...
    def __deepcopy__(self, memo: Mapping[int, Cloneable | list[CliCompiler]]) -> CliCompiler: ...
    def Program(self, name: str) -> Program: ...
    def Library(self, name: str) -> Library: ...
    def StaticLibrary(self, name: str) -> StaticLibrary: ...
    def PrecompiledHeaders(self, name: str, source_type: str) -> PrecompiledHeaders: ...
    @staticmethod
    def run_pkg_config(argv: Sequence[str]) -> list[str]: ...
    def pkg_config(self, pkg: str, link: str = ...) -> None: ...

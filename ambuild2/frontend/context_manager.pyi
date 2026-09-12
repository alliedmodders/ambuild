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
from types import CodeType
from typing import Literal

from _typeshed import Incomplete
from ambuild2.database import Database
from ambuild2.frontend.base_generator import BaseGenerator
from ambuild2.frontend.v2_2.context import BaseContext, EmptyContext, RootBuildContext, TopLevelBuildContext
from ambuild2.frontend.version import Version
from ambuild2.util import Expando

class ContextManager:
    sourcePath: str
    buildPath: str
    originalCwd: str
    options: Expando
    args: argparse.Namespace
    configure_failed: bool
    contextStack_: list[RootBuildContext | TopLevelBuildContext | EmptyContext]
    generator: BaseGenerator | None = None
    db: Database | None
    refactoring: bool

    def __init__(self, sourcePath: str, buildPath: str, originalCwd: str, options: Expando, args: argparse.Namespace) -> None: ...

    ALWAYS_DIRTY: object
    @property
    def apiVersion(self) -> Version: ...
    def setBackend(self, backend: str) -> None: ...
    def pushContext(self, cx: BaseContext) -> None: ...
    def popContext(self) -> None: ...
    def compileScript(self, path: str) -> CodeType: ...
    def Context(self, name: str) -> Incomplete: ...  # AutoContext: doesn't exist in version 2.2? ...
    def generateBuildFiles(self) -> None: ...
    def createGenerator(self, name: str) -> None: ...
    def generate(self, name: str | None = None) -> Literal[True]: ...
    @property
    def backend(self) -> Incomplete: ...  # Never set

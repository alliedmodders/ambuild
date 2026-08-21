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
import optparse
from types import TracebackType
from typing import Any, Self

from ambuild2.database import Database
from ambuild2.process_manager import ProcessManager
from ambuild2.util import Expando

class Context:
    buildPath: str
    options: optparse.Values
    args: list[Any]
    cacheFolder: str
    dbpath: str
    vars: dict[str, Expando | argparse.Namespace | dict[str, str] | str]
    db: Database
    procman: ProcessManager

    def __init__(self, buildPath: str, options: optparse.Values, args: list[str]) -> None: ...
    def __enter__(self) -> Self: ...
    def __exit__(self, type: type[BaseException] | None, value: BaseException | None, traceback: TracebackType | None) -> None: ...
    def restore_environment(self) -> None: ...
    def reconfigure(self) -> bool: ...
    def Build(self) -> bool: ...
    def build_internal(self) -> bool: ...

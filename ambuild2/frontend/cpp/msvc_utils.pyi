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
from typing import Any, Literal

from ambuild2.frontend.system import System
from ambuild2.frontend.version import Version

class MSVCInstall:
    version: Version
    prerelease: bool
    path: str
    vcvars: dict[Any, Any]

    def __init__(self, version: str, path: str, prerelease: bool = False) -> None: ...

class MSVCFinder:
    installs_: list[MSVCInstall]

    def __init__(self) -> None: ...
    def find_all(self) -> list[MSVCInstall]: ...
    def find_old(self) -> None: ...
    def find_new(self) -> None: ...
    def find_old_install(self, version: str) -> bool: ...
    def find_old_build_tools(self) -> Literal[True] | None: ...

def parse_env(text: str) -> dict[str, str]: ...
def find_env_changes(env1: dict[str, str], env2: dict[str, str]) -> tuple[OrderedDict[str, str], OrderedDict[str, str]]: ...
def run_batch(contents: str) -> str: ...
def DeduceEnv(vcvars_file: str, argv: list[str]) -> tuple[tuple[str, ...], ...]: ...

kArchMap: dict[str, str]

def MakeArchParam(host: System, target: System) -> str | None: ...
def DetectInclusionPattern(text: str) -> str: ...
def GetCodePage() -> str: ...

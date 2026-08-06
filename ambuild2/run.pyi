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

import optparse
from typing import Any, Final, Literal, overload

from ambuild2.frontend.v2_0.prep import Preparer as V20Preparer
from ambuild2.frontend.v2_1.prep import Preparer as V21Preparer
from ambuild2.frontend.v2_2.prep import Preparer as V22Preparer

DEFAULT_API: Final[str]
CURRENT_API: Final[str]
SampleScript: Final[str]
SampleConfigure: Final[str]

def BuildOptions() -> tuple[optparse.Values, list[Any]]: ...
def Build(buildPath: str, options: optparse.Values, argv: list[str]) -> bool: ...
def CompatBuild(buildPath: str) -> bool: ...
def PrepareBuild(sourcePath: str, buildPath: str | None = ...) -> V20Preparer: ...

class ApiVersionNotFoundException(Exception):
    def __init__(self, *args: object, **kwargs: object) -> None: ...

@overload
def PreparerForAPI(api: Literal['2.0']) -> type[V20Preparer]: ...
@overload
def PreparerForAPI(api: Literal['2.1', '2.1.0']) -> type[V21Preparer]: ...
@overload
def PreparerForAPI(api: Literal['2.2', '2.2.4']) -> type[V22Preparer]: ...
def HasAPI(api: str) -> bool: ...
@overload
def BuildParser(sourcePath: str, api: Literal['2.0'], buildPath: str | None = ...) -> V20Preparer: ...
@overload
def BuildParser(sourcePath: str, api: Literal['2.1', '2.1.0'], buildPath: str | None = ...) -> V21Preparer: ...
@overload
def BuildParser(sourcePath: str, api: Literal['2.2', '2.2.4'], buildPath: str | None = ...) -> V22Preparer: ...
@overload
def BuildParser(sourcePath: str, api: str, buildPath: str | None = ...) -> Any: ...
def cli_run() -> None: ...

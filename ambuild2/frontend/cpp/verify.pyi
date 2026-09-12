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

from collections.abc import MutableMapping
from typing import Final

class Verifier:
    family_: str
    mode_: str
    env_: dict[str, str] | None
    argv_: list[str]
    cross_compile_: bool

    def __init__(self, family: str, mode: str, argv: list[str], env: MutableMapping[str, str] | None, cross_compile: bool = False) -> None: ...
    def verify(self) -> dict[str, str | None]: ...
    def verify_native(self) -> dict[str, str | None]: ...
    def verify_cross_compile(self) -> dict[str, str | None]: ...
    def write_source(self, is_pp: bool) -> None: ...
    def parse_pp(self, text: str) -> list[str]: ...
    def build_pp_argv(self) -> list[str]: ...
    def build_link_argv(self) -> list[str]: ...
    def test_executable(self) -> list[str]: ...
    def verify_lines(self, lines: list[str]) -> None: ...

TEST_SOURCE: Final[str]

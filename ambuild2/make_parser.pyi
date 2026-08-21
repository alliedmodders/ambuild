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

from typing import TextIO

def LineHasContinuation(line: str) -> bool: ...
def Preprocess(lines: list[str]) -> str: ...

class Parser:
    chars_: str
    pos_: int

    def __init__(self, fp: TextIO) -> None: ...
    def parse(self) -> list[str]: ...
    def lex(self, stop_token: str | None = ...) -> str | None: ...
    def skip_newline(self, c: str) -> bool: ...
    def peek(self) -> str | None: ...

def ParseDependencyFile(filename: str, fp: TextIO) -> list[str]: ...

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

from types import TracebackType
from typing import TextIO

class XmlScope:
    builder_: XmlBuilder
    tag_: str
    kwargs_: dict[str, str]

    def __init__(self, builder: XmlBuilder, tag: str, **kwargs: str) -> None: ...
    def __enter__(self) -> None: ...
    def __exit__(self, type: type[BaseException] | None, value: BaseException | None, traceback: TracebackType | None) -> None: ...

class XmlBuilder:
    fp_: TextIO
    indent_: int

    def __init__(self, fp: TextIO, version: str = ..., encoding: str = ...) -> None: ...
    def block(self, tag: str, **kwargs: str) -> XmlScope: ...
    def tag(self, tag: str, contents: str | None = ..., **kwargs: str) -> None: ...
    def enter(self, tag: str, **kwargs: str) -> None: ...
    def leave(self, tag: str) -> None: ...
    def build_element(self, tag: str, **kwargs: str) -> str: ...
    def write(self, line: str) -> None: ...

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

from typing import Literal

from ambuild2.frontend.system import System
from ambuild2.nodetypes import Entry, NodeType

class CppNodes:
    binary: Entry
    debug: Entry
    type: str
    target: System
    static_binary: Entry | None

    def __init__(self, output: Entry, debug_outputs: Entry, type: NodeType, target: System, static_binary: Entry | None = None) -> None: ...

class PchNodes:
    folder: Entry
    header_file: Entry
    pch_file: Entry
    object_file: Entry
    source_type: Literal['c', 'c++']
    def __init__(self, folder: Entry, header_file: Entry, pch_file: Entry, object_file: Entry, source_type: Literal['c', 'c++']) -> None: ...

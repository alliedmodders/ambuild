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

from ambuild2.frontend.v2_2.cpp.builders import CustomToolCommand
from ambuild2.nodetypes import Entry

class FxcTool:
    output_files: list[str]
    output_nodes: list[Entry]

    def __init__(self) -> None: ...
    def evaluate(self, cmd: CustomToolCommand) -> None: ...
    def evaluate_shader(self, cmd: CustomToolCommand, shader: dict[str, str]) -> None: ...

class FxcJob:
    tool = FxcTool()
    output: str
    shaders: list[dict[str, str]]
    namespace: str
    listDefineName: bool | None

    def __init__(self, output: str, namespace: str) -> None: ...

def fxc_helper_tool() -> None: ...

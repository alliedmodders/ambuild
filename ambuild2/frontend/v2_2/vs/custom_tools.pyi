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

from ambuild2.frontend.v2_2.tools.fxc import FxcJob
from ambuild2.frontend.v2_2.tools.protoc import ProtocJob
from ambuild2.frontend.v2_2.vs.cxx import Library, StaticLibrary
from ambuild2.frontend.v2_2.vs.nodes import ProjectNode
from ambuild2.frontend.vs.xmlbuilder import XmlBuilder

def find_custom_tools(builder: Library | StaticLibrary) -> list[tuple[Literal['fxc', 'protoc'], FxcJob | ProtocJob]]: ...
def add_custom_tool_include_paths(includes: list[str], node: ProjectNode, builder: Library | StaticLibrary, custom_tools: list[tuple[Literal['fxc', 'protoc'], FxcJob | ProtocJob]]) -> list[str]: ...
def add_custom_tool_prebuild_events(xml: XmlBuilder, node: ProjectNode, builder: Library | StaticLibrary, custom_tools: list[tuple[Literal['fxc', 'protoc'], FxcJob | ProtocJob]]) -> bool: ...
def add_custom_tool_output_files(node: ProjectNode, xml: XmlBuilder, builder: Library | StaticLibrary, custom_tools: list[tuple[Literal['fxc', 'protoc'], FxcJob | ProtocJob]]) -> None: ...

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

import ambuild2.frontend.v2_2.vs.cxx as vs
from ambuild2.frontend.v2_2.context import RootBuildContext, TopLevelBuildContext

class Node:
    context: RootBuildContext | TopLevelBuildContext | None
    path: str
    children: set[Node]
    parents: set[Node]

    def __init__(self, context: RootBuildContext | TopLevelBuildContext | None, path: str) -> None: ...
    def addParent(self, parent: Node) -> None: ...

class FolderNode(Node):
    def __init__(self, path: str) -> None: ...
    @property
    def kind(self) -> Literal['folder']: ...

class ContainerNode(Node):
    def __init__(self, cx: RootBuildContext | TopLevelBuildContext) -> None: ...
    @property
    def kind(self) -> Literal['container']: ...

class OutputNode(Node):
    def __init__(self, context: RootBuildContext | TopLevelBuildContext, path: str, parent: Node) -> None: ...
    @property
    def kind(self) -> Literal['output']: ...

class ProjectNode(Node):
    project: vs.Project
    uuid: str

    def __init__(self, context: RootBuildContext | TopLevelBuildContext, path: str, project: vs.Project) -> None: ...
    @property
    def kind(self) -> Literal['project']: ...

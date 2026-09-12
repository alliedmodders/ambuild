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

from collections.abc import Callable

from _typeshed import Incomplete
from ambuild2 import nodetypes
from ambuild2.database import Database
from ambuild2.nodetypes import Entry

class GraphNode:
    entry: Entry
    incoming: set[GraphNode]
    outgoing: set[GraphNode]
    outputs: set[Incomplete]
    is_command: bool

    def __init__(self, entry: Entry) -> None: ...
    @property
    def type(self) -> nodetypes.NodeType: ...
    def isCommand(self) -> bool: ...

class Graph:
    db: Database
    node_map: dict[Entry, GraphNode] | None
    node_list: list[GraphNode]
    worklist: list[GraphNode]
    create: list[Entry]

    def __init__(self, database: Database) -> None: ...
    def importEntry(self, entry: Entry) -> GraphNode: ...
    def addEntry(self, entry: Entry) -> GraphNode: ...
    def addEdge(self, from_node: GraphNode, to_node: GraphNode) -> None: ...
    def addEdgeToEntry(self, from_node: GraphNode, to_entry: Entry) -> None: ...
    def integrate(self) -> None: ...
    def complete_ordering(self) -> None: ...
    def filter_commands(self) -> None: ...
    def finish(self) -> None: ...
    @property
    def leafs(self) -> list[GraphNode]: ...
    def for_each_child_of(self, node: GraphNode, callback: Callable[[Entry], None]) -> None: ...
    def for_each_leaf_command(self, callback: Callable[[Entry], None]) -> None: ...
    def printGraph(self) -> None: ...

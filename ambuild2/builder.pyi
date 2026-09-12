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

from collections.abc import Sequence
from typing import Any, Literal

from ambuild2.context import Context
from ambuild2.graph import Graph, GraphNode
from ambuild2.nodetypes import Entry
from ambuild2.task import Task

class TaskTreeBuilder:
    cx: Context
    worklist: list[tuple[Task, GraphNode]]
    cache: dict[GraphNode, Task]
    cmd_list: list[GraphNode]
    tree_leafs: list[Task]
    max_parallel: int

    def __init__(self, cx: Context) -> None: ...
    def buildFromGraph(self, graph: Graph) -> tuple[list[GraphNode | None], list[Task]]: ...
    def findTask(self, node: GraphNode) -> Task: ...
    def enqueueCommand(self, node: GraphNode) -> Task: ...

class Builder:
    cx: Context
    graph: Graph
    tb: TaskTreeBuilder
    commands: list[GraphNode]
    leafs: list[Task]
    max_parallel: int
    num_completed_tasks: int
    update_set: set[Entry]

    def __init__(self, cx: Context, graph: Graph) -> None: ...
    def printSteps(self) -> None: ...
    def update(self) -> tuple[Literal[0, 1, 2, 3, 4], str | None]: ...
    def lazyUpdateEntry(self, entry: Entry) -> None: ...
    def commit(self) -> None: ...
    def addDiscoveredSource(self, path: str) -> Entry | None: ...
    def discoverEntries(self, discovered_paths: Sequence[str]) -> set[Entry] | None: ...
    def findPath(self, source: Entry, target: Entry) -> bool: ...
    def ensureValidDependency(self, source: Entry, target: Entry) -> bool: ...
    def mergeDependencies(self, cmd_node: GraphNode, discovered_paths: list[str]) -> bool: ...
    def updateGraph(self, task_id: int, updates: Sequence[tuple[str, float]], message: dict[str, Any]) -> bool: ...

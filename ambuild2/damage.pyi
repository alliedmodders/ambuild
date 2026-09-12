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

from ambuild2.database import Database
from ambuild2.graph import Graph
from ambuild2.nodetypes import Entry

def ComputeSourceDirty(node: Entry) -> bool: ...
def ComputeOutputDirty(node: Entry) -> bool: ...
def ComputeDirty(node: Entry) -> bool: ...
def ComputeDamageGraph(database: Database, only_changed: bool = ...) -> Graph | list[Entry] | None: ...

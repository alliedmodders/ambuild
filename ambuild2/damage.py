# vim: set sts=8 sts=2 sw=2 tw=99 et:
#
# This file is part of AMBuild.
# 
# AMBuild is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# AMBuild is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with AMBuild. If not, see <http://www.gnu.org/licenses/>.
from graph import Graph

def ComputeDamageGraph(database):
  graph = Graph(database)

  dirty = []
  def known_dirty(node):
    dirty.append(node)

  def maybe_dirty(node):
    if ComputeDirty(node):
      dirty.append(node)

  database.query_known_dirty(known_dirty)
  database.query_maybe_dirty(maybe_dirty)

  for entry in dirty:
    graph.addEntry(entry)
  return graph

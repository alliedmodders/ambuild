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
import os
from graph import Graph

def ComputeSourceDirty(node):
  if not os.path.exists(node.path):
    return True

  return os.path.getmtime(node.path) != node.stamp

def ComputeOutputDirty(node):
  if not os.path.exists(node.path):
    return True

  # If the timestamp on the object file has changed, then one of two things
  # happened:
  #  (1) The build command completed, but the build process crashed, and we
  #      never got a chance to update the timestamp.
  #  (2) The file was modified behind our back.
  #
  # In the first case, our preceding command node will not have been undirtied,
  # so we should be able to find our incoming command in the graph. However,
  # case #2 breaks that guarantee. To be safe, if the timestamp has changed,
  # we mark the node as dirty (the dirty bit is always false for Outputs) to
  # signal to later steps that the node has been munged on the file system.
  # If its ancestor was then never added to the graph, we can warn the user
  # and manually insert the node.
  stamp = os.path.getmtime(node.path)
  if stamp == node.stamp:
    return False

  node.dirty = True
  return True

def ComputeDirty(node):
  if node.type == 'src':
    return ComputeSourceDirty(node)
  if node.type == 'out':
    return ComputeOutputDirty(node)
  if node.type == 'cpa':
    return ComputeCopyFolderDirty(node)
  raise Exception('cannot compute dirty bit for node type: ' + node.type)

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

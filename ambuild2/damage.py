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
import nodetypes
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
  # we mark the node as dirty.
  stamp = os.path.getmtime(node.path)
  return stamp != node.stamp

def ComputeDirty(node):
  if node.type == nodetypes.Source:
    dirty = ComputeSourceDirty(node)
  elif node.type == nodetypes.Output:
    dirty = ComputeOutputDirty(node)
  elif node.type == nodetypes.CopyFolder:
    dirty = ComputeCopyFolderDirty(node)
  else:
    raise Exception('cannot compute dirty bit for node type: ' + node.type)
  if dirty:
    node.dirty |= nodetypes.NewDirty
  return dirty

def ComputeDamageGraph(database):
  graph = Graph(database)

  def maybe_mkdir(node):
    if not os.path.exists(node.path):
      graph.create.append(node)
  database.query_mkdir(maybe_mkdir)

  dirty = []
  def known_dirty(node):
    dirty.append(node)

  def maybe_dirty(node):
    if ComputeDirty(node):
      dirty.append(node)

  database.query_known_dirty(known_dirty)
  database.query_maybe_dirty(maybe_dirty)

  def add_dirty(entry):
    if entry.dirty == nodetypes.NewDirty:
      # Mark this node as dirty in the DB so we don't have to check the
      # filesystem next time.
      database.mark_dirty(entry)

    graph.addEntry(entry)

  for entry in dirty:
    if (entry.type == nodetypes.Output) and (entry.dirty == nodetypes.NewDirty):
      # Ensure that our command has been marked as dirty.
      incoming = database.query_incoming(entry)

      # There should really only be one command to generate an output.
      if len(incoming) != 1:
        sys.stderr.write('Error in dependency graph: an output has multiple inputs.')
        sys.stderr.write('Output: {0}'.format(entry.format()))
        return None

      for cmd in incoming:
        add_dirty(cmd)
    else:
      add_dirty(entry)

  graph.complete()
  return graph

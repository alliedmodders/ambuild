# vim: set ts=8 sts=2 sw=2 tw=99 et:
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
import util
import os, sys
import nodetypes
from frontend.base_gen import ConfigureException

class GraphException(Exception):
  def __init__(self):
    super(GraphException, self).__init__()

class NodeBuilder(object):
  def __init__(self, type, path=None, folder=None, blob=None, generated=False):
    self.id = None
    self.type = type
    self.path = path
    self.folder = folder
    self.blob = blob
    self.generated = generated
    self.outgoing = set()
    self.incoming = set()

class GraphBuilder(object):
  def __init__(self):
    self.folders = {}
    self.files = {}
    self.commands = []
    self.edges = []

  def generateFolder(self, folder):
    if folder in self.folders:
      return self.folders[folder]

    if len(folder) == 0:
      # Don't create a node for the root folder.
      return None

    assert not os.path.isabs(folder)
    node = NodeBuilder(type=nodetypes.Mkdir, path=folder, generated=True)
    self.folders[folder] = node
    return node

  def depNodeForPath(self, path):
    if os.path.isabs(path):
      return self.addSource(path)

    if path not in self.files:
      sys.stderr.write('Tried to add a dependency on an output that doesn\'t exist.\n')
      sys.stderr.write('Path: {0}\n'.format(path))
      raise ConfigureException()

    node = self.files[path]
    if node.type != nodetypes.Output:
      sys.stderr.write('Tried to add an output dependency on node that is not an output.\n')
      sys.stderr.write('Path: {0}\n'.format(path))
      sys.stderr.write('Type: {0}\n'.format(node.type))
      raise ConfigureException()

    return node

  def addOutput(self, path):
    assert not os.path.isabs(path)
    if path in self.files:
      sys.stderr.write('The same output file has been added to the build twice.\n')
      sys.stderr.write('Path: {0}\n'.format(path))
      raise ConfigureException()

    node = NodeBuilder(type=nodetypes.Output, path=path)
    self.files[path] = node
    return node

  def addSymLink(self, context, source, folder, file):
    folder = os.path.join(context.buildFolder, folder)
    output_path = os.path.join(folder, file)
    folder = self.generateFolder(folder)

    command = self.addCommand(
      type=nodetypes.Symlink,
      folder=folder,
      path=None,
      data=(source.path, file)
    )
    output = self.addOutput(output_path)
    self.addDependency(command, source)
    self.addDependency(output, command)
    return output

  def addCommand(self, type, folder, path=None, data=None):
    assert folder is None or util.typeof(folder) is NodeBuilder

    node = NodeBuilder(type=type, path=path, folder=folder, blob=data)
    self.commands.append(node)
    return node

  def addDependency(self, outgoing, incoming):
    outgoing.incoming.add(incoming)
    incoming.outgoing.add(outgoing)
    self.edges.append((outgoing, incoming, False))

  def addSource(self, path):
    if path in self.files:
      return self.files[path]

    assert os.path.isabs(path)

    node = NodeBuilder(type=nodetypes.Source, path=path)
    self.files[path] = node
    return node

  def addCopy(self, context, source, folder):
    assert type(folder) is NodeBuilder
    if type(source) is str:
      source = self.addSource(source)

    if source.type == nodetypes.Source:
      source_path = source.path
    elif source.type == nodetypes.Output:
      source_path = os.path.join(context.buildPath, source.path)
    ignore, filename = os.path.split(source_path)

    copy = self.addCommand(
      type=nodetypes.Copy,
      folder=folder,
      path=None,
      data=(source_path, filename)
    )
    output = self.addOutput(os.path.join(folder.path, filename))
    self.addDependency(copy, source)
    self.addDependency(output, copy)
    return output

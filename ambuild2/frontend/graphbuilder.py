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
    self.group = None

class GroupBuilder(NodeBuilder):
  def __init__(self, name):
    super(GroupBuilder, self).__init__(nodetypes.Group, name)
    self.members = []

  def Add(self, node):
    if type(node) is list:
      for item in node:
        self.Add(item)
      return

    if node.type != nodetypes.Output:
      raise Exception('Only output files can be added to a group')
    if node.group:
      raise Exception('Output is already a member of group "{0}"'.format(node.group.path))
    node.group = self
    self.members.append(node)

class GraphBuilder(object):
  def __init__(self):
    self.folders = {}
    self.files = {}
    self.commands = []
    self.edges = []
    self.groups = {}

  def generateFolder(self, context, folder):
    folder = os.path.normpath(folder)
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

  def addOutput(self, context, path):
    assert not os.path.isabs(path)

    path = os.path.join(context.buildFolder, path)

    if path in self.files:
      sys.stderr.write('The same output file has been added to the build twice.\n')
      sys.stderr.write('Path: {0}\n'.format(path))
      raise Exception('duplicate output')

    node = NodeBuilder(type=nodetypes.Output, path=path)
    self.files[path] = node
    return node

  @staticmethod
  def getPathInContext(context, node): 
    if node.type == nodetypes.Source:
      assert os.path.isabs(node.path)
      return node.path

    assert not os.path.isabs(node.path)
    assert node.type == nodetypes.Output

    return os.path.relpath(node.path, context.buildFolder)

  def addFileOp(self, cmd, context, source, output_path):
    if type(source) is str:
      source = self.addSource(source)

    source_path = self.getPathInContext(context, source)

    if type(output_path) is str:
      def detect_folder(output_path):
        if output_path[-1] == os.sep:
          return output_path
        if output_path[-1] == os.altsep:
          return output_path
        if os.path.normpath(output_path) == '.':
          return '.' + os.sep
        output_folder = os.path.normpath(os.path.join(context.buildFolder, output_path))
        if output_folder in self.folders:
          return output_folder + os.sep
        return None

      folder = detect_folder(output_path)
      if folder:
        # The path is a folder, so build a new path.
        ignore, filename = os.path.split(source_path)
        output_path = folder + filename
    else:
      assert output_path.type == nodetypes.Mkdir
      ignore, filename = os.path.split(source_path)
      local_path = os.path.relpath(output_path.path, context.buildFolder)
      output_path = os.path.join(local_path, filename)

    output_path = os.path.normpath(output_path)

    command = self.addCommand(
      context=context,
      type=cmd,
      path=None,
      data=(source_path, output_path)
    )

    output = self.addOutput(context, output_path)
    self.addDependency(command, source)
    self.addDependency(output, command)
    return output

  def addCommand(self, context, type, folder=None, path=None, data=None):
    assert folder is None or util.typeof(folder) is NodeBuilder

    if not folder and len(context.buildFolder):
      folder = self.generateFolder(context, context.buildFolder)

    node = NodeBuilder(type=type, path=path, folder=folder, blob=data)
    self.commands.append(node)
    return node

  def addDependency(self, outgoing, incoming):
    # Source nodes are leaves.
    assert outgoing.type != nodetypes.Source

    # mkdir nodes are isolated.
    assert outgoing.type != nodetypes.Mkdir and incoming.type != nodetypes.Mkdir

    # Output nodes should always originate from commands or groups.
    assert outgoing.type != nodetypes.Output or \
           (nodetypes.IsCommand(incoming.type) or incoming.type == nodetypes.Group)

    # Group nodes should only depend on output files.
    assert outgoing.type != nodetypes.Group or incoming.type == nodetypes.Output

    # Command nodes should depend on groups, sources, or outputs.
    assert not nodetypes.IsCommand(outgoing.type) or \
           (incoming.type == nodetypes.Output or \
            incoming.type == nodetypes.Source or \
            incoming.type == nodetypes.Group)

    outgoing.incoming.add(incoming)
    incoming.outgoing.add(outgoing)
    self.edges.append((outgoing, incoming, False))

  # addSource() doesn't take a context since sources may be shared across
  # many build files. They are garbage collected as needed.
  def addSource(self, path):
    if path in self.files:
      return self.files[path]

    assert os.path.isabs(path)

    node = NodeBuilder(type=nodetypes.Source, path=path)
    self.files[path] = node
    return node

  def addCopy(self, context, source, folder):
    return self.addFileOp(nodetypes.Copy, context, source, folder)

  def addSymlink(self, context, source, folder):
    return self.addFileOp(nodetypes.Symlink, context, source, folder)

  def addShellCommand(self, context, inputs, argv, outputs):
    command = self.addCommand(
      context=context,
      type=nodetypes.Command,
      path=None,
      data=argv
    )
    output_nodes = []
    for output in outputs:
      output = self.addOutput(context, output)
      self.addDependency(output, command)
    for input in inputs:
      if type(input) is str:
        input = self.addSource(input)
      self.addDependency(command, input)
    return command, output_nodes

  def addGroup(self, context, name):
    if name in self.groups:
      raise Exception('Duplicate group added: {0}'.format(name))

    group = GroupBuilder(name)
    self.groups[name] = group
    return group

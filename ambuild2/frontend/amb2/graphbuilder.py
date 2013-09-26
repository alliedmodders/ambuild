# vim: set ts=8 sts=2 sw=2 tw=99 et:
import os
import util
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

  def addOutput(self, path):
    assert not os.path.isabs(path)
    assert not path in self.files

    node = NodeBuilder(type=nodetypes.Output, path=path)
    self.files[path] = node
    return node

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

    node = NodeBuilder(type=nodetypes.Source, path=path)
    self.files[path] = node
    return node

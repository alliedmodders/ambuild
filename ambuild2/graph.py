# vim: set sts=8 sts=2 sw=2 tw=99 et:
import os
import handlers
from damage import Damage

# A node proxy represents an object in the database that may not exist yet,
# or if it exists, it might have changes not yet committed to the database.
class NodeProxy(object):
  def __init__(self, handler, path, id, data, dirty=True, stamp=0.0):
    self.handler = handler
    self.path = path
    self.id = id
    self.data = data
    self.inputs = set()
    self.children = set()
    self.static_inputs = set()
    self.dynamic_inputs = set()
    self.stamp = stamp
    self.visit_id = 0
    self.dirty_ = dirty

  def dirty(self):
    if self.stamp <= 0.0 or self.dirty_:
      return True
    if not os.path.exists(self.path):
      return True
    return self.stamp < os.path.getmtime(self.path)

  def proxyId(self):
    if self.id:
      return self.id
    return self.path

  def addDependency(self, input, generated):
    NodeProxy.addEdge(self, input, generated)

  @staticmethod
  def addEdge(output, input, generated):
    if generated:
      output.dynamic_inputs.add(input)
    else:
      output.static_inputs.add(input)
    output.inputs.add(input)
    input.children.add(output)

# An object that helps build a section of the dependency graph. DepBuilders
# will only expand into actual nodes once applied to the graph, and are not
# actual nodes themselves.
class NodeBuilder(object):
  def __init__(self):
    pass

  def generate(self, cx, graph):
    raise Exception('Must override this!')

class GraphProxy(object):
  def __init__(self, server):
    self.server = server
    self.files = {}
    self.visit_number_ = 0
    self.server.importGraph(self)

  def importNode(self, node_type, path, node_id, data, dirty, stamp):
    assert not path in self.files
    
    handler = handlers.Find(node_type)
    node = NodeProxy(handler, path, node_id, data, dirty=dirty, stamp=stamp)
    self.files[path] = node
    return node

  def addNode(self, handler, path, data, dirty=True):
    # This output should not already exist.
    assert not path in self.files

    stamp = 0.0
    if not dirty:
      if os.path.exists(path):
        stamp = os.path.getmtime(path)
      else:
        dirty = True

    id = self.server.registerNode(handler.msg_type, path, data, dirty, stamp)
    node = NodeProxy(handler, path, id, data, dirty, stamp)
    self.files[node.path] = node
    return node

  def findOrAddSource(self, path, dirty=True):
    if path in self.files:
      return self.files[path]
    return self.addNode(handlers.SourceHandler, path, data=None, dirty=dirty)

  def addDependency(self, output, input, generated=False):
    # If the input is a string, then we don't have a node for it yet.
    if type(input) == str:
      path = input
      input = self.findOrAddSource(path)

    NodeProxy.addEdge(output, input, generated)

    self.server.registerEdge(
      output.proxyId(),
      input.proxyId(),
      generated
    )

  def removeDependency(self, output, input):
    self.server.unregisterEdge(
      output.proxyId(),
      input.proxyId(),
      generated=True
    )

  def updateDynamicDependencies(self, node, new_deps):
    changed = new_deps ^ node.dynamic_inputs
    for diff_node in changed:
      if diff_node in new_deps:
        self.addDependency(node, diff_node, generated=True)
      else:
        self.removeDependency(node, diff_node)

  def nextVisitId(self):
    self.visit_number_ += 1
    return self.visit_number_

  def unmarkDirty(self, node):
    if not os.path.exists(node.path):
      return
    stamp = os.path.getmtime(node.path)
    self.server.unmarkDirty(node.proxyId(), stamp)

  def commitDirty(self, nodes):
    proxy_list = [node.proxyId() for node in nodes if not node.dirty_]
    self.server.commitDirty(proxy_list)

  def commit(self):
    self.server.commit()

  def printNode(self, node, depth):
    print(('  ' * depth) + '- ' + node.path)
    for input in node.static_inputs:
      self.printNode(input, depth + 1)
    for input in node.dynamic_inputs:
      self.printNode(input, depth + 1)

  def printGraph(self):
    for path in self.files:
      node = self.files[path]
      if len(node.children):
        continue
      self.printNode(node, 1)


# vim: set ts=8 sts=2 sw=2 tw=99 et:
import os
import traceback

class CollapseEntry(object):
  def __init__(self, node):
    self.incoming = set(node.damage.dependencies)
    self.outgoing = set(node.outgoing)

  def dropIncoming(self, node):
    self.incoming.remove(node)
    if not len(self.incoming):
      self.incoming = None
      return True
    return False

class Collapser(object):
  def __init__(self, damage):
    self.commands = []
    self.worklist = []

  def enqueueLeaf(self, node):
    if node.isCommand():
      self.commands.append(node)
    else:
      self.worklist.append(node)

  def computeTaskTree(self, damage):
    # Get the initial nodes.
    for node in damage.leafs:
      self.enqueueLeaf(node)

    self.stripNonCommandLeafs()

  # Removes an incoming dependency from child, and returns true if it was
  # the last dependency. As an optimization we don't create collapse
  # information if there's a single link.
  def dropDependency(self, parent, child):
    if len(child.outgoing) == 1:
      return True
    if not child.collapse:
      child.collapse = CollapseEntry(child)
    return child.collapse.dropIncoming(node)

  def stripNonCommandLeafs(self):
    # The work queue has only non-command leaf nodes. We remove these nodes.
    # If removing any node would introduce a new leaf, we either add it to
    # the root set (if it's a command), or re-enqueue it for removal.
    while len(self.worklist):
      node = self.worklist.pop()
      assert not node.isCommand()

      for child in node.outgoing:
        if self.dropDependency(node, child):
          self.enqueueLeaf(child)

  def collapse(self):
    while len(self.worklist):
      node = self.worklist.pop()

      if node.isCommand():
        # Enqueue all children.
        for child in node.children:
          self.enqueueNode(child)
      else:
        # Remove this node's incoming edges, and replace them with edges to
        # our outgoing nodes.
        for parent in node.damage.dependencies:
          parent.collapse.outgoing.remove(node)

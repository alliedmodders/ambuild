# vim: set sts=8 sts=2 sw=2 tw=99 et:

class DamageEntry(object):
  def __init__(self, unmet=0):
    self.unmet = unmet

class Damage(object):
  def __init__(self, db):
    self.db = db
    self.dirty_queue_ = []
    self.newly_dirty = []
    self.leafs = set()

    self.computeDamage()

  def computeDamage(self):
    self.findDirty()
    self.propagateDamage()

  def findDirty(self):
    def known_dirty(node):
      self.enqueueNode(node)
    self.db.query_known_dirty(known_dirty)

    def maybe_dirty(node):
      if self.is_dirty(node):
        self.newly_dirty(node)
        self.enqueueNode(node)
    self.db.query_maybe_dirty(maybe_dirty)

  def enqueueNode(self, node):
    assert not node.damage
    node.damage = DamageEntry()
    self.leafs.add(node)
    self.dirty_queue_.append(node)

  def enqueueOutgoing(self, from_node, outgoing):
    if outgoing.damage:
      # If the node is tracked as a leaf, remove it from the leaf set.
      if outgoing.damage.unmet == 0:
        self.leafs.remove(outgoing)
      outgoing.damage.unmet += 1
    else:
      outgoing.damage = DamageEntry(unmet=1)
      self.dirty_queue_.add(outgoing)

  def propagateDamage(self):
    while len(self.dirty_queue_):
      node = self.dirty_queue_.pop()

      for outgoing in self.db.query_outgoing(node):
        self.enqueueOutgoing(node, outgoing)

  def computeBackEdges(self, collector, roots, node):
    if not len(node.outgoing):
      roots.append(node)
    for outgoing in node.outgoing:
      if outgoing in collector:
        collector[outgoing].append(node)
      else:
        collector[outgoing] = [node]
        self.computeBackEdges(collector, roots, outgoing)

  def printDamage(self):
    collector = {}
    roots = []
    for node in self.leafs:
      collector[node] = []
      self.computeBackEdges(collector, roots, node)
    def printNode(node, indent):
      print((' ' * indent) + ' - ' + node.format())
      for child in collector[node]:
        printNode(child, indent + 1)
    for node in roots:
      printNode(node, 0)

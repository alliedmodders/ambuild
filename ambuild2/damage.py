# vim: set sts=8 sts=2 sw=2 tw=99 et:
import database

class DamageNode(object):
  def __init__(self, dep):
    self.node = dep
    self.children = set()
    self.parents = set()
    self.visited = False

    # The number of dependencies that are outstanding for this node; this is
    # equal to len(children), unless modified by a later pass for traversal.
    self.unmet = 0

  def addChild(self, node):
    self.children.add(node)
    self.unmet += 1
    node.parents.add(self)

class Damage(object):
  def __init__(self, graph):
    self.graph = graph
    self.nodes = []

    # Compute the partial DAG.
    self.computeDamageGraph()

  def computeChanged(self):
    changed = set()
    for path in self.graph.files:
      node = self.graph.files[path]

      # See if the file has changed.
      if node.dirty():
        changed.add(node)

    return changed

  def computeDamageGraph(self):
    changed = self.computeChanged()

    self.seen = {}
    visit_id = self.graph.nextVisitId()
    for node in changed:
      if node.visit_id == visit_id:
        continue
      self.propagateDamage(node, visit_id)

    self.nodes = self.seen.values()
    del self.seen

  def propagateDamage(self, node, visit_id):
    node.visit_id = visit_id

    dmg_node = DamageNode(node)
    self.seen[node] = dmg_node

    for child in node.children:
      if child.visit_id == visit_id:
        parent = self.seen[child]
      else:
        parent = self.propagateDamage(child, visit_id)
      parent.addChild(dmg_node)

    return dmg_node

  def printChildren(self, dmg_node, indent):
    print((' ' * indent) + ' - ' + dmg_node.node.path)
    for child in dmg_node.children:
      self.printChildren(child, indent + 2)

  def printChanges(self):
    for node in self.nodes:
      if not len(node.parents):
        self.printChildren(node, 1)


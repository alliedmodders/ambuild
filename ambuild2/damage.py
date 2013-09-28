# vim: set sts=8 sts=2 sw=2 tw=99 et:
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

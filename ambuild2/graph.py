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
import nodetypes

class GraphNode(object):
  def __init__(self, entry):
    self.entry = entry
    self.incoming = set()
    self.outgoing = set()
    self.incoming_cmds = set()
    self.outgoing_cmds = set()
    self.is_command = entry.isCommand()

  @property
  def type(self):
    return self.entry.type

  def isCommand(self):
    return self.is_command

class Graph(object):
  def __init__(self, database):
    self.db = database
    self.leafs = set()
    self.roots = set()
    self.nodes = []
    self.outputs = []
    self.commands = []
    self.worklist = []
    self.node_map = {}

  def importEntry(self, entry):
    assert not entry.id in self.node_map
    graph_node = GraphNode(entry)
    self.node_map[entry.id] = graph_node

    self.roots.add(graph_node)
    if graph_node.isCommand():
      self.commands.append(graph_node)
    self.nodes.append(graph_node)
    if entry.type == nodetypes.Output:
      self.outputs.append(graph_node)

    self.worklist.append(graph_node)
    return graph_node

  # If the node doesn't exist in the graph, add the DAG as reachable from
  # this node.
  def addEntry(self, entry):
    if entry.id in self.node_map:
      return self.node_map[entry.id]
    graph_node = self.importEntry(entry)
    self.leafs.add(graph_node)
    self.integrate()
    return graph_node

  # Given an edge from x -> y, we want to propagate command dependencies
  # between the two. If |x| and |y| are both commands, then this is easy.
  def propagateCmdToCmd(self, from_node, to_node):
    assert from_node.isCommand() and to_node.isCommand()
    from_node.outgoing_cmds.add(to_node)
    to_node.incoming_cmds.add(from_node)

  # If the from node is not a command, we take all its incoming commands
  # and create edges to the target node.
  def propagateCmdsFromUpd(self, from_node, to_node):
    assert not from_node.isCommand()

    # Update our incoming node set. If the set does not change, then we don't
    # need to update any links.
    before_len = len(to_node.incoming_cmds)
    to_node.incoming_cmds.update(from_node.incoming_cmds)
    if before_len == len(to_node.incoming_cmds):
      return False

    # One or more incoming edges were added, so add outgoing links.
    for cmd_node in from_node.incoming_cmds:
      cmd_node.outgoing_cmds.add(to_node)
    return True

  # Same as the above, but for a single incoming command node. We process
  # the outgoing edges from |to_node| later.
  def propagateCmdToUpd(self, from_node, to_node):
    assert from_node.isCommand() and not to_node.isCommand()

    before_len = len(to_node.incoming_cmds)
    to_node.incoming_cmds.add(from_node)
    return before_len != len(to_node.incoming_cmds)

  # When propagating command edges to a non-command node, special care must
  # be taken. More edges may be added later, and if we don't propagate to all
  # update nodes, then edges added *from* those nodes will be lost.
  def propagateCommandsSlow(self, from_node, to_node):
    worklist = [(from_node, to_node)]

    while len(worklist):
      incoming, outgoing = worklist.pop()

      # Easy case, we've reached a dead-end.
      if incoming.isCommand() and outgoing.isCommand():
        self.propagateCmdToCmd(incoming, outgoing)
        continue

      if incoming.isCommand() and not outgoing.isCommand():
        updated = self.propagateCmdToUpd(incoming, outgoing)
      else:
        updated = self.propagateCmdsFromUpd(incoming, outgoing)

      # If there was no update, or the target was a command, then we can avoid
      # propagating from the to node.
      if not updated or outgoing.isCommand():
        continue

      # Otherwise, keep adding to the worklist.
      for child in outgoing.outgoing:
        worklist.append((outgoing, child))

  def propagateCommands(self, from_node, to_node):
    if from_node.isCommand() and to_node.isCommand():
      self.propagateCmdToCmd(from_node, to_node)
    elif not from_node.isCommand() and to_node.isCommand():
      self.propagateCmdsFromUpd(from_node, to_node)
    else:
      self.propagateCommandsSlow(from_node, to_node)

  # Given a source graph node, and a destination database node, construct an
  # edge between the two (adding a node for to_entry if needed).
  def addEdgeToEntry(self, from_node, to_entry):
    if not to_entry.id in self.node_map:
      self.importEntry(to_entry)
      maybe_leaf = False
    else:
      maybe_leaf = True

    to_node = self.node_map[to_entry.id]
    self.addEdge(from_node, to_node, to_maybe_leaf=maybe_leaf)

  # Given two graph nodes, construct an edge between them.
  def addEdge(self, from_node, to_node, to_maybe_leaf):
    from_node.outgoing.add(to_node)
    to_node.incoming.add(from_node)

    if to_maybe_leaf and len(to_node.incoming) == 1:
      # This node was optimistically assumed to be a leaf, but now that we've
      # discovered a first incoming edge, we know it's not. Remove it from the
      # leaf set.
      self.leafs.remove(to_node)
    if len(from_node.outgoing) == 1:
      # This node was optimistically assumed to be a root, but now that we've
      # discovered a first outgoing edge, we know it's not. Remove it from the
      # root set.
      self.roots.remove(from_node)

    self.propagateCommands(from_node, to_node)

  # Integrate the worklist into the graph.
  def integrate(self):
    while len(self.worklist):
      node = self.worklist.pop()

      for child_entry in self.db.query_outgoing(node.entry):
        self.addEdgeToEntry(node, child_entry)

  # Finish constructing the graph.
  def complete(self):
    pass

  @property
  def leaf_commands(self):
    return [node for node in self.commands if not len(node.incoming_cmds)]

  @property
  def root_commands(self):
    return [node for node in self.commands if not len(node.outgoing_cmds)]

  def printCommands(self):
    def printNode(node, indent):
      print((' ' * indent) + ' - ' + node.entry.format())
      for incoming in node.incoming_cmds:
        printNode(incoming, indent + 1)

    for node in self.root_commands:
      printNode(node, 0)

  def printGraph(self):
    def printNode(node, indent):
      print((' ' * indent) + ' - ' + node.entry.format())
      for incoming in node.incoming:
        printNode(incoming, indent + 1)

    for node in self.roots:
      printNode(node, 0)

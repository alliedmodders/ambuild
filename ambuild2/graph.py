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
from ambuild2 import nodetypes

class GraphNode(object):
    def __init__(self, entry):
        self.entry = entry
        self.incoming = set()
        self.outgoing = set()
        self.outputs = set()
        self.is_command = entry.isCommand()

    @property
    def type(self):
        return self.entry.type

    def isCommand(self):
        return self.is_command

class Graph(object):
    def __init__(self, database):
        self.db = database
        self.node_map = {}
        self.node_list = []
        self.worklist = []
        self.create = []

    def importEntry(self, entry):
        assert entry not in self.node_map

        graph_node = GraphNode(entry)
        self.node_map[entry] = graph_node
        self.node_list.append(graph_node)
        self.worklist.append(graph_node)
        return graph_node

    def addEntry(self, entry):
        if entry in self.node_map:
            return self.node_map[entry]

        return self.importEntry(entry)

    def addEdge(self, from_node, to_node):
        from_node.outgoing.add(to_node)
        to_node.incoming.add(from_node)

    def addEdgeToEntry(self, from_node, to_entry):
        if to_entry not in self.node_map:
            to_node = self.importEntry(to_entry)
        else:
            to_node = self.node_map[to_entry]
        self.addEdge(from_node, to_node)

    def integrate(self):
        while len(self.worklist):
            node = self.worklist.pop()

            for child_entry in self.db.query_outgoing(node.entry):
                self.addEdgeToEntry(node, child_entry)

    def complete_ordering(self):
        for node in self.node_list:
            if not node.isCommand():
                continue

            for weak_input in self.db.query_weak_inputs(node.entry):
                if weak_input not in self.node_map:
                    continue
                dep = self.node_map[weak_input]
                dep.outgoing.add(node)
                node.incoming.add(dep)

    # We should try to get rid of this algorithm; it's very expensive and not
    # really needed if we just include non-command nodes in the compressed
    # version of the graph.
    def filter_commands(self):
        worklist = [node for node in self.node_list if not node.isCommand()]
        for node in worklist:
            for output in node.outgoing:
                output.incoming.remove(node)
                output_delta = node.incoming - output.incoming
                output.incoming |= output_delta
                for x in output_delta:
                    x.outgoing.add(output)

            for input in node.incoming:
                input.outgoing.remove(node)
                input_delta = node.outgoing - input.outgoing
                input.outgoing |= input_delta
                for x in input_delta:
                    x.incoming.add(input)

        self.node_list = [node for node in self.node_list if node.isCommand()]

    def finish(self):
        self.integrate()
        self.complete_ordering()
        self.node_map = None

    @property
    def leafs(self):
        return [node for node in self.node_list if not len(node.incoming)]

    def for_each_child_of(self, node, callback):
        for outgoing in node.outgoing:
            if outgoing.isCommand():
                callback(outgoing.entry)
            else:
                self.for_each_child_of(outgoing, callback)

    def for_each_leaf_command(self, callback):
        for node in self.leafs:
            if node.isCommand():
                callback(node.entry)
            else:
                self.for_each_child_of(node, callback)

    def printGraph(self):
        for entry in self.create:
            print(' : ' + entry.format())

        def printNode(node, indent):
            print((' ' * indent) + ' - ' + node.entry.format())
            for incoming in node.incoming:
                printNode(incoming, indent + 1)

        for node in [node for node in self.node_list if not len(node.incoming)]:
            printNode(node, 0)

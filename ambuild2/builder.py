# vim: set ts=8 sts=2 sw=2 tw=99 et:
import util
import os, errno
import traceback
import nodetypes
from collections import deque
from task import Task, TaskMasterParent

# Given the partial command DAG, compute a task tree we can send to the task
# thread.
class TaskTreeBuilder(object):
  def __init__(self):
    self.worklist = []
    self.cache = {}
    self.cmd_list = []
    self.tree_leafs = []
    self.max_parallel = 0

  def buildFromGraph(self, graph):
    for node in graph.leaf_commands:
      leaf = self.enqueueCommand(node)
      self.tree_leafs.append(leaf)

    self.max_parallel = len(self.worklist)
    while len(self.worklist):
      task, node = self.worklist.pop()

      for outgoing in node.outgoing_cmds:
        outgoing_task = self.findTask(outgoing)
        task.addOutgoing(outgoing_task)

      if len(self.worklist) > self.max_parallel:
        self.max_parallel = len(self.worklist)

    return self.cmd_list, self.tree_leafs

  def findTask(self, node):
    if node in self.cache:
      return self.cache[node]
    return self.enqueueCommand(node)

  def enqueueCommand(self, node):
    assert node not in self.cache
    assert node.isCommand()
    outputs = [o.entry.path for o in node.outgoing if o.entry.type == nodetypes.Output]
    task = Task(len(self.cmd_list), node.entry, outputs)
    self.cache[node] = task
    self.cmd_list.append(node)
    self.worklist.append((task, node))
    return task

class Builder(object):
  def __init__(self, cx, graph):
    self.cx = cx
    self.graph = graph

    tb = TaskTreeBuilder()
    self.commands, self.leafs = tb.buildFromGraph(graph)
    self.max_parallel = tb.max_parallel

  def printSteps(self):
    counter = 0
    leafs = deque(self.leafs)
    while len(leafs):
      leaf = leafs.popleft()
      print('task ' + str(format(counter)) + ': ' + leaf.format())
      for output in leaf.outputs:
        print('  -> ' + output)

      for child in leaf.outgoing:
        child.incoming.remove(leaf)
        if not len(child.incoming):
          leafs.append(child)

      counter += 1

  def update(self):
    tm = TaskMasterParent(self.cx, self, self.leafs, self.max_parallel)

  def findTask(self, task_id):
    return self.commands[task_id]

# vim: set ts=8 sts=2 sw=2 tw=99 et:
import os
import time
import traceback
from damage import Damage
from procman import ProcessManager
import multiprocessing as mp

class Builder(object):
  def __init__(self, cx):
    self.cx = cx
    self.tasks = []
    self.steps = []
    self.visit_id_ = 0
    self.damage_graph_ = Damage(cx.db)

    self.computeSteps()

  def createTask(self, dmg_node):
    task_data = dmg_node.node.handler.createTask(self.cx, self, dmg_node.node)
    if not task_data:
      return None
    task_data['task_id'] = len(self.tasks)
    task_data['msg_type'] = dmg_node.node.handler.msg_type
    self.tasks.append(dmg_node)
    return task_data

  def computeSteps(self):
    # Commit dirty nodes.
    self.cx.graph.commitDirty([dmg_node.node for dmg_node in self.damage_graph_.nodes])

    self.visit_id_ = self.cx.graph.nextVisitId()

    # Find the set of leaf nodes in the graph - the set of nodes which have
    # no dependencies. This algorithm is not perfect; it simply peels each
    # layer of leaf nodes off the graph. It is conservative.
    leafs = []
    for dmg_node in self.damage_graph_.nodes:
      if not len(dmg_node.children):
        leafs.append(dmg_node)

    # Find each set of independent tasks in the dependency graph, and create
    # a list of such sets. This iterates to a fixpoint, and works by simulating
    # removing each set of leafs from the graph.
    while len(leafs):
      new_leafs = self.computeNextLeafSet(leafs)
      if not len(new_leafs):
        break
      leafs = new_leafs

  def computeNextLeafSet(self, current_leafs):
    tasks = []
    new_leafs = []
    while len(current_leafs):
      leaf = current_leafs.pop()
      task = self.createTask(leaf)
      if task:
        tasks.append(task)

      # Search for any parents of this node, and mark off that we computed
      # one of its dependencies.
      for parent in leaf.parents:
        assert parent.unmet > 0
        parent.unmet -= 1
        # If we're the last dependency...
        if parent.unmet == 0:
          # If the current leaf generated a task, that's a dependency, so we
          # add its parent to the *next* round of tasks.
          if task:
            new_leafs.append(parent)
          # Otherwise, the node generated no task, so we can immediately add
          # our parent to the current round of tasks.
          else:
            current_leafs.append(parent)

    if len(tasks):
      self.steps.append(tasks)
    return new_leafs

  def unmarkDirty(self, node):
    self.cx.graph.unmarkDirty(node)

  def printSteps(self):
    for index, group in enumerate(self.steps):
      print('Tasks in group ' + str(index + 1) + ':')
      for task in group:
        task_id = task['task_id']
        print(' : ' + self.tasks[task_id].node.path)

  def build(self, num_processes):
    # Early bailout if there is nothing to do.
    if not len(self.tasks):
      return True

    if num_processes <= 0:
      # Using 1 process will be strictly worse than an in-process build,
      # since we incur the additional overhead of message passing. So we
      # create two processes just because. Someday we should be able to
      # switch over to an in-process manager.
      if mp.cpu_count() == 1:
        num_processes = 2
      else:
        num_processes = int(mp.cpu_count() * 1.5)

    # Don't create more processes than we'll need.
    if len(self.tasks) < num_processes:
      num_processes = len(self.tasks)

    manager = ProcessManager(num_processes)

    build_succeeded = True
    for group in self.steps:
      if not self.sendBuildTasks(manager, group):
        build_succeeded = False
        print('Build failed.')
        break

    # Close the process manager.
    manager.close()

    # Commit any pending operations in the database.
    self.cx.graph.commit()

    return build_succeeded

  def sendBuildTasks(self, manager, group):
    expecting_replies = 0

    # Send each process an initial message to get the ball rolling.
    for process in manager.processes:
      if not len(group):
        break
      message = group.pop()
      process.send(message)
      expecting_replies += 1

    build_failed = False
    while expecting_replies or ((not build_failed) and len(group)):
      process, reply = manager.waitForReply()

      # If we don't see a reply, then all the processes died.
      if not reply:
        return False

      expecting_replies -= 1

      task_id = reply['task_id']
      dmg_node = self.tasks[task_id]
      handler = dmg_node.node.handler
      try:
        if not handler.update(self.cx, dmg_node, dmg_node.node, reply):
          build_failed = True
      except Exception as exn:
        build_failed = True
        traceback.print_exc()

      if build_failed:
        continue

      # If the build hasn't failed, try to keep building more stuff.
      if (not build_failed) and len(group):
        message = group.pop()
        process.send(message)
        expecting_replies += 1
    # End while

    if build_failed:
      return False

    return True


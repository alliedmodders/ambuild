# vim: set ts=8 sts=2 sw=2 tw=99 et:
import sys
import os, errno
import traceback
from ambuild2 import util
from ambuild2 import nodetypes
from collections import deque
from ambuild2.task import Task, TaskMaster

# Given the partial command DAG, compute a task tree we can send to the task
# thread.
class TaskTreeBuilder(object):
    def __init__(self, cx):
        self.cx = cx
        self.worklist = []
        self.cache = {}
        self.cmd_list = []
        self.tree_leafs = []
        self.max_parallel = 0

    def buildFromGraph(self, graph):
        for node in graph.leafs:
            leaf = self.enqueueCommand(node)
            self.tree_leafs.append(leaf)

        self.max_parallel = len(self.worklist)
        while len(self.worklist):
            task, node = self.worklist.pop()

            for outgoing in node.outgoing:
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
        output_list = []
        for output in self.cx.db.query_outgoing(node.entry):
            assert output.type == nodetypes.Output
            output_list.append(output.path)
        task = Task(len(self.cmd_list), node.entry, output_list)
        self.cache[node] = task
        self.cmd_list.append(node)
        self.worklist.append((task, node))
        return task

class Builder(object):
    def __init__(self, cx, graph):
        self.cx = cx
        self.graph = graph

        tb = TaskTreeBuilder(cx)
        self.commands, self.leafs = tb.buildFromGraph(graph)
        self.max_parallel = tb.max_parallel
        self.num_completed_tasks = 0

        # Set of nodes we'll mark as clean in the database.
        self.update_set = set()

    def printSteps(self):
        if not len(self.graph.create) and not len(self.leafs):
            print('Build is complete and no files changed; no steps needed.')
            return

        for entry in self.graph.create:
            print(entry.format())
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
        for entry in self.graph.create:
            if entry.type == nodetypes.Mkdir:
                util.con_out(util.ConsoleBlue, '[create] ', util.ConsoleGreen, entry.format(),
                             util.ConsoleNormal)
                # The path might already exist because we mkdir -p and don't bother
                # ordering.
                if not os.path.exists(entry.path):
                    os.makedirs(entry.path)
            else:
                raise Exception('Unknown entry type: {0}'.format(entry.type))
        if not len(self.leafs):
            return TaskMaster.BUILD_NO_CHANGES, None

        tm = TaskMaster(self.cx, self, self.leafs, self.max_parallel)
        tm.run()
        self.commit()

        if tm.succeeded() and len(self.commands) != self.num_completed_tasks:
            util.con_err(util.ConsoleRed,
                         'Build marked as completed, but some commands were not executed?!\n',
                         'Commands:', util.ConsoleNormal)
            for task in self.commands:
                if not task:
                    continue
                util.con_err(util.ConsoleBlue, ' -> ', util.ConsoleRed,
                             '{0}'.format(task.entry.format()), util.ConsoleNormal)

        return tm.status(), tm.failed_task_message

    def lazyUpdateEntry(self, entry):
        if entry.type != nodetypes.Source:
            return
        if entry.dirty:
            self.update_set.add(entry)

    def commit(self):
        # Update any dirty source file timestamps. It's important that files are
        # not modified in between being used as dependencies and the build
        # finishing; otherwise, the DAG state will be incoherent.
        for entry in self.update_set:
            if entry.dirty != nodetypes.ALWAYS_DIRTY:
                self.cx.db.unmark_dirty(entry)
        self.cx.db.commit()

    def addDiscoveredSource(self, path):
        if not os.path.isabs(path):
            util.con_err(
                util.ConsoleRed, 'Encountered an error while computing new dependencies: ',
                'A new dependent file or path was discovered that has no corresponding build entry. ',
                'This probably means a build script did not explicitly mark a generated file as an output. ',
                'The build must abort since the ordering of these two steps is undefined. ',
                util.ConsoleNormal)
            util.con_err(util.ConsoleRed, 'Path: ', util.ConsoleBlue, path, util.ConsoleNormal)
            return None

        rel_to_objdir = util.RelPathIfCommon(path, self.cx.buildPath)
        if rel_to_objdir:
            entry = self.cx.db.query_path(rel_to_objdir)
            if not entry:
                util.con_err(
                    util.ConsoleRed, 'Encountered an error while computing new dependencies: ',
                    'A new dependent file was discovered, but it exists in the output folder, and ',
                    'no corresponding command creates this file. One of the followeing might have ',
                    'occurred: \n',
                    ' (1) The file was created outside of AMBuild, which is not supported.\n',
                    ' (2) The file was created by a custom AMBuild command, but was not specified as an output.\n',
                    util.ConsoleNormal)
                util.con_err(util.ConsoleRed, 'Path: ', util.ConsoleBlue, rel_to_objdir,
                             util.ConsoleNormal)
                return None
            return entry

        return self.cx.db.add_source(path)

    def discoverEntries(self, discovered_paths):
        discovered_set = set()
        for path in discovered_paths:
            entry = self.cx.db.query_path(path)
            if not entry:
                entry = self.addDiscoveredSource(path)
                if not entry:
                    return None

            if entry.type != nodetypes.Source and entry.type != nodetypes.Output:
                util.con_err(util.ConsoleRed,
                             'Fatal error in DAG construction! Dependency is not a file input.',
                             util.ConsoleNormal)
                util.con_err(util.ConsoleRed, 'Path: ', util.ConsoleBlue, path, util.ConsoleNormal)
                return None

            discovered_set.add(entry)

        return discovered_set

    def findPath(self, source, target):
        # We search the graph from the target, since we assume there are fewer
        # predecessor links than successor links that way.
        assert source != target

        queue = set([target])
        seen = set()
        while len(queue):
            node = queue.pop()

            # Once again, exclude dynamic inputs, it doesn't seem to make sense that
            # they'd reliably participate in this algorithm.
            strong_inputs = self.cx.db.query_strong_inputs(node)
            if source in strong_inputs:
                return True
            weak_inputs = self.cx.db.query_weak_inputs(node)
            if source in weak_inputs:
                return True

            new_nodes = (strong_inputs - seen) | (weak_inputs - seen)
            seen |= new_nodes
            queue |= new_nodes

        return False

    def ensureValidDependency(self, source, target):
        # Build the set of nodes that are valid connectors for the dependency. For
        # cxx and cpa commands, the exact dependencies are determined by AMB2, so
        # we don't allow the user to attach arbitrary strong dependencies; they
        # are always weak.
        roots = set()

        inputs = self.cx.db.query_weak_inputs(target)
        if not nodetypes.HasAutoDependencies(target.type):
            # Exclude dynamic inputs since they weren't specified in the build.
            inputs |= self.cx.db.query_strong_inputs(target)

        for input in inputs:
            if input == source:
                return True

            if self.findPath(source, input):
                return True

        # There is no explicit ordering defined between these two nodes; we have
        # abort the build.
        util.con_err(
            util.ConsoleRed, 'Encountered an error while computing new dependencies: ',
            'A new dependency was discovered that exists as an output from another build step. ',
            'However, there is no explicit dependency between that path and this command. ',
            'The build must abort since the ordering of these two steps is undefined. ',
            util.ConsoleNormal)
        util.con_err(util.ConsoleRed, 'Dependency: ', util.ConsoleBlue, source.path,
                     util.ConsoleNormal)
        return False

    def mergeDependencies(self, cmd_node, discovered_paths):
        # Grab nodes for each dependency.
        discovered_set = self.discoverEntries(discovered_paths)
        if discovered_set is None:
            return False

        strong_inputs = self.cx.db.query_strong_inputs(cmd_node.entry)
        dynamic_inputs = self.cx.db.query_dynamic_inputs(cmd_node.entry)

        # Any inputs that were not inputs before, should be linked via the
        # dynamic edge table now. If the new input is an output (i.e. a
        # generated file), we have to ensure that there is a valid ordering
        # between the two.
        for added in (discovered_set - dynamic_inputs):
            # Generally the set of dynamic inputs will be larger than the set of
            # strong inputs, so perform the set difference against the larger set,
            # and strong set membership manually here.
            if added in strong_inputs:
                continue

            if added.type != nodetypes.Source:
                assert added.type == nodetypes.Output
                if not self.ensureValidDependency(added, cmd_node.entry):
                    return False

            # Add the edge.
            self.cx.db.add_dynamic_edge(added, cmd_node.entry)

        # Remove any dynamic links that are no longer needed.
        for removed in (dynamic_inputs - discovered_set):
            self.cx.db.drop_dynamic_edge(removed, cmd_node.entry)

        # Update the timestamps of the files we used.
        for entry in discovered_set:
            self.lazyUpdateEntry(entry)

        return True

    def updateGraph(self, task_id, updates, message):
        if not self.commands[task_id]:
            util.con_err(
                util.ConsoleRed,
                'Received update for task_id {0} that was already completed!\n'.format(task_id),
                util.ConsoleBlue, 'Message details:\n', util.ConsoleNormal, '{0}'.format(message))
            return False

        node = self.commands[task_id]
        self.commands[task_id] = None

        if 'deps' in message:
            if not self.mergeDependencies(node, message['deps']):
                return False

        if node.entry.dirty != nodetypes.ALWAYS_DIRTY:
            for incoming in self.cx.db.query_strong_inputs(node.entry):
                self.lazyUpdateEntry(incoming)
            for incoming in self.cx.db.query_dynamic_inputs(node.entry):
                self.lazyUpdateEntry(incoming)

            for path, stamp in updates:
                entry = self.cx.db.query_path(path)
                self.cx.db.unmark_dirty(entry, stamp)
            self.cx.db.unmark_dirty(node.entry)

        self.num_completed_tasks += 1
        return True

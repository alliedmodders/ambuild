# vim: set ts=8 sts=2 sw=2 tw=99 et:
import os
import nodetypes
import multiprocessing as mp
from ipc import ParentListener, ChildListener, ProcessManager, MessageListener, Error

class Task(object):
  def __init__(self, id, entry, outputs):
    self.id = id
    self.type = entry.type
    self.data = entry.blob
    self.outputs = outputs
    self.outgoing = []
    self.incoming = set()

  def addOutgoing(self, task):
    self.outgoing.append(task)
    task.incoming.add(self)

  def format(self):
    text = ''
    if self.type == nodetypes.Cxx:
      return '[' + self.data['type'] + ']' + ' -> ' + (' '.join([arg for arg in self.data['argv']]))
    return (' '.join([arg for arg in self.data]))

class WorkerChild(ChildListener):
  def __init__(self, pump, channels):
    super(WorkerChild, self).__init__(pump)
    print('Spawned worker (pid: ' + str(os.getpid()) + ')')
    self.resultChannel = channels[0]
    self.resultChannel.connect('WorkerIOChild')
    self.messageMap = {
      'task': lambda channel, message: self.receiveTask(channel, message)
    }

  def receiveConnected(self, channel):
    channel.send({'id': 'ready', 'finished': None})

  def receiveTask(self, channel, message):
    print(message)

# The WorkerParent is in the same process as the TaskMasterChild.
class WorkerParent(ParentListener):
  def __init__(self, taskMaster, child_channel):
    super(WorkerParent, self).__init__('Worker')
    self.taskMaster = taskMaster
    self.child_channel = child_channel
    self.messageMap = {
      'ready': lambda child, message: self.receiveReady(child, message)
    }

  def receiveConnected(self, child):
    # We're just a conduit for this pipe. Now that the child has received it,
    # it's safe to free our references to it.
    self.child_channel.close()
    self.child_channel = None

  def receiveReady(self, child, message):
    return self.taskMaster.onWorkerReady(child)

  def receiveError(self, child, error):
    self.taskMaster.onWorkerDied(child, error)

# The TaskMasterChild is in the same process as the WorkerParent.
class TaskMasterChild(ChildListener):
  def __init__(self, pump, task_graph, child_channels):
    super(TaskMasterChild, self).__init__(pump)
    print('Spawned task master (pid: ' + str(os.getpid()) + ')')

    self.task_graph = task_graph
    self.outstanding = {}
    self.ready = set()

    self.procman = ProcessManager(pump)
    for channel in child_channels:
      self.procman.spawn(WorkerParent(self, channel), WorkerChild, args=(), channels=(channel,))

  def receiveConnected(self, channel):
    self.channel = channel

  def onWorkerReady(self, child):
    if not len(self.task_graph):
      if len(self.outstanding):
        # There are still tasks left to complete, but they're waiting on
        # others to finish. Mark this process as ready and just ignore the
        # status change for now.
        self.ready.add(child)
      else:
        # There are no tasks remaining, the worker is not needed.
        self.procman.close(child)
      return

    # Send a task to the worker.
    task = self.task_graph.pop()

    message = {
      'id': 'task',
      'task_id': task.id,
      'task_type': task.type,
      'task_data': task.data,
      'task_outputs': task.outputs
    }
    child.send(message)
    self.outstanding[task.id] = (task, child)

  def onWorkerDied(self, child, error):
    if error != Error.NormalShutdown:
      for task_id in self.outstanding.keys():
        task, child = self.outstanding[task_id]
        self.onWorkerFailed(child, task, error)
        # There should be at most one outstanding task assigned to this worker.
        break

    self.ready.discard(child)
    if not self.procman.liveChildren():
      self.pump.cancel()

class WorkerIOListener(MessageListener):
  def __init__(self):
    super(WorkerIOListener, self).__init__()

class TaskMasterParent(ParentListener):
  def __init__(self, cx, task_graph, task_list):
    super(TaskMasterParent, self).__init__('TaskMaster')
    self.cx = cx

    # Figure out how many tasks to create.
    if cx.options.jobs == 0:
      # Using 1 process will be strictly worse than an in-process build,
      # since we incur the additional overhead of message passing. Instead,
      # we use two processes as the minimal number. If that turns out to be
      # bad we can create an in-process TaskMaster later.
      if mp.cpu_count() == 1:
        num_processes = 2
      else:
        num_processes = int(mp.cpu_count() * 1.5)

    # Don't create more processes than we'll need.
    if len(task_list) < num_processes:
      num_processes = len(task_list)

    # Create the list of pipes we'll be using.
    self.channels = []
    child_channels = []
    for i in range(num_processes):
      parent_channel, child_channel = cx.messagePump.createChannel('WorkerIO', self)
      listener = WorkerIOListener()
      cx.messagePump.addChannel(parent_channel, listener)
      child_channels.append(child_channel)

    # Spawn the task master.
    cx.procman.spawn(self, TaskMasterChild, args=(task_graph,), channels=child_channels)

    self.run()

  def receiveError(self, child, error):
    print('Error: ' + error)

  def run(self):
    self.cx.messagePump.pump()

# vim: set ts=8 sts=2 sw=2 tw=99 et:
import os
import nodetypes
import multiprocessing as mp
from ipc import ParentListener, ChildListener, ProcessManager

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
  def __init__(self, pump, resultChannel):
    super(WorkerChild, self).__init__(pump)
    self.resultChannel = resultChannel
    print('Spawned worker (pid: ' + str(os.getpid()) + ')')
    print('pid: ' + str(os.getpid()) + ', (' + str(resultChannel.reader.fileno()) + ', ' + str(resultChannel.writer.fileno()) + ')')

  def receiveConnected(self, channel):
    print('pidx: ' + str(os.getpid()) + ', (' + str(channel.reader.fileno()) + ', ' + str(channel.writer.fileno()) + ')')

class WorkerParent(ParentListener):
  def __init__(self, taskMaster, child_channel):
    super(WorkerParent, self).__init__()
    self.taskMaster = taskMaster
    self.child_channel = child_channel

  def recvConnected(self, child):
    # We're just a conduit for this pipe. Now that the child has received it,
    # it's safe to free our references to it.
    self.child_channel.close()
    self.child_channel = None

class TaskMasterChild(ChildListener):
  def __init__(self, pump, task_graph, child_channels):
    super(TaskMasterChild, self).__init__(pump)
    print('Spawned task master (pid: ' + str(os.getpid()) + ')')

    self.procman = ProcessManager(pump)
    for channel in child_channels:
      self.procman.spawn(WorkerParent(self, channel), WorkerChild, args=(channel,))

  def receiveConnected(self, channel):
    print('pidx: ' + str(os.getpid()) + ', (' + str(channel.reader.fileno()) + ', ' + str(channel.writer.fileno()) + ')')

class TaskMasterParent(ParentListener):
  def __init__(self, cx, task_graph, task_list):
    super(TaskMasterParent, self).__init__()
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
      parent_channel, child_channel = cx.messagePump.createChannel(self)
      self.channels.append(parent_channel)
      child_channels.append(child_channel)

    # Spawn the task master.
    cx.procman.spawn(self, TaskMasterChild, args=(task_graph), channels=child_channels)

    self.run()

  def run(self):
    self.cx.messagePump.pump()

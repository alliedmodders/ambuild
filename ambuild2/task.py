# vim: set ts=8 sts=2 sw=2 tw=99 et:
import util
import errno
import shutil
import os, sys
import nodetypes
import traceback
import multiprocessing as mp
from ipc import ParentProcessListener, ChildProcessListener
from ipc import ProcessManager, MessageListener, Error
from ipc import Channel

class Task(object):
  def __init__(self, id, entry, outputs):
    self.id = id
    self.type = entry.type
    self.data = entry.blob
    if entry.folder:
      self.folder = entry.folder.path
    else:
      self.folder = None
    self.outputs = outputs
    self.outgoing = []
    self.incoming = set()

  def addOutgoing(self, task):
    self.outgoing.append(task)
    task.incoming.add(self)

  @property
  def folder_name(self):
    if not self.folder:
      return ''
    return self.folder

  def format(self):
    text = ''
    if self.type == nodetypes.Cxx:
      return '[' + self.data['type'] + ']' + ' -> ' + (' '.join([arg for arg in self.data['argv']]))
    if self.type == nodetypes.Symlink:
      return 'ln -s "{0}" "{1}"'.format(self.data[0], os.path.join(self.folder_name, self.data[1]))
    if self.type == nodetypes.Copy:
      return 'cp "{0}" "{1}"'.format(self.data[0], os.path.join(self.folder_name, self.data[1]))
    return (' '.join([arg for arg in self.data]))

class WorkerChild(ChildProcessListener):
  def __init__(self, pump, channel, buildPath, channels):
    super(WorkerChild, self).__init__(pump, channel)
    self.buildPath = buildPath
    self.resultChannel = Channel.connect(channels[0], 'WorkerIOChild')
    self.pid = os.getpid()
    self.messageMap = {
      'task': lambda channel, message: self.receiveTask(channel, message)
    }
    self.taskMap = {
      'cxx': lambda message: self.doCompile(message),
      'cmd': lambda message: self.doCommand(message),
      'ln': lambda message: self.doSymlink(message),
      'cp': lambda message: self.doCopy(message),
    }

    # Spew! We can't print to stdout since it could race.
    self.resultChannel.send({
      'id': 'spawned',
      'pid': os.getpid()
    })

    self.channel.send({
      'id': 'ready',
      'finished': None
    })

  def receiveClose(self, channel):
    try:
      self.resultChannel.finished()
    except:
      # The channel could have been closed from the other side already, so
      # just ignore errors.
      pass
    super(WorkerChild, self).receiveClose(channel)

  def receiveTask(self, channel, message):
    # :TODO: test this.
    # sys.exit(1)
    task_id = message['task_id']
    task_type = message['task_type']
    task_folder = message['task_folder']
    if not task_folder:
      task_folder = '.'

    # Remove all outputs.
    for output in message['task_outputs']:
      try:
        os.unlink(output)
      except OSError as exn:
        if exn.errno != errno.ENOENT:
          response = {
            'ok': False,
            'cmdline': 'rm {0}'.format(output),
            'stdout': '',
            'stderr': '{0}'.format(exn)
          }
          return self.issueResponse(message, response)

    if not message['task_folder']:
      message['task_folder'] = '.'

    # Do the task.
    response = self.taskMap[task_type](message)
    return self.issueResponse(message, response)

  def issueResponse(self, message, response):
    # Send a message to the task master indicating whether we succeeded.
    self.channel.send({
      'id': 'ranTask',
      'ok': response['ok'],
      'task_id': message['task_id']
    })

    # Compute new timestamps for all command outputs.
    new_timestamps = []
    if response['ok']:
      for output in message['task_outputs']:
        new_timestamps.append((output, os.path.getmtime(output)))

    # Send a message back to the master process to update the DAG and spew
    # stdout/stderr if needed.
    response['id'] = 'results'
    response['pid'] = self.pid
    response['task_id'] = message['task_id']
    response['updates'] = new_timestamps
    try:
      self.resultChannel.send(response)
    except:
      # If we failed to send the message, it means the parent side has already
      # closed the channel due to some failure on its end.
      pass

  def doCommand(self, message):
    task_folder = message['task_folder']
    argv = message['task_data']
    with util.FolderChanger(task_folder):
      try:
        p, stdout, stderr = util.Execute(argv)
        status = p.returncode == 0
      except Exception as exn:
        status = False
        stdout = ''
        stderr = '{0}'.format(exn)

    reply = {
      'ok': status,
      'cmdline': ' '.join([arg for arg in argv]),
      'stdout': stdout,
      'stderr': stderr,
    }
    return reply

  def doSymlink(self, message):
    task_folder = message['task_folder']
    source_path, output_path = message['task_data']

    with util.FolderChanger(task_folder):
      rcode, stdout, stderr = util.symlink(source_path, output_path)

    reply = {
      'ok': rcode == 0,
      'cmdline': 'ln -s {0} {1}'.format(source_path, output_path),
      'stdout': stdout,
      'stderr': stderr,
    }
    return reply

  def doCopy(self, message):
    task_folder = message['task_folder']
    source_path, output_path = message['task_data']

    with util.FolderChanger(task_folder):
      shutil.copy(source_path, output_path)

    reply = {
      'ok': True,
      'cmdline': 'cp "{0}" "{1}"'.format(source_path, os.path.join(task_folder, output_path)),
      'stdout': '',
      'stderr': '',
    }
    return reply

  def doCompile(self, message):
    task_folder = message['task_folder']
    task_data = message['task_data']
    cc_type = task_data['type']
    argv = task_data['argv']

    with util.FolderChanger(task_folder):
      p, out, err = util.Execute(argv)
      if cc_type == 'gcc':
        err, deps = util.ParseGCCDeps(err)
      elif cc_type == 'msvc':
        out, deps = util.ParseMSVCDeps(out)
      else:
        raise Exception('unknown compiler type')
        
      # Adjust any dependencies relative to the current folder, to be relative
      # to the output folder instead.
      paths = []
      for inc_path in deps:
        if not os.path.isabs(inc_path):
          inc_path = os.path.abspath(inc_path)

        # Detect whether the include is within the build folder or not.
        build_path = self.buildPath
        if build_path[-1] != '/':
          build_path += '/'
        prefix = os.path.commonprefix([build_path, inc_path])
        if prefix == build_path:
          # The include is not a system include, i.e. it was generated, so
          # rewrite the path to be relative to the build folder.
          inc_path = os.path.relpath(inc_path, self.buildPath)

        paths.append(inc_path)

    reply = {
      'ok': p.returncode == 0,
      'cmdline': ' '.join([arg for arg in argv]),
      'stdout': out,
      'stderr': err,
      'deps': paths,
    }
    return reply

# The WorkerParent is in the same process as the TaskMasterChild.
class WorkerParent(ParentProcessListener):
  def __init__(self, taskMaster, child_channel):
    super(WorkerParent, self).__init__('Worker')
    self.taskMaster = taskMaster
    self.child_channel = child_channel
    self.messageMap = {
      'ready': lambda child, message: self.receiveReady(child, message),
      'ranTask': lambda child, message: self.receiveRanTask(child, message),
    }

  def receiveConnected(self, child):
    super(WorkerParent, self).receiveConnected(child)
    # We're just a conduit for this pipe. Now that the child has received it,
    # it's safe to free our references to it.
    self.child_channel.close()
    self.child_channel = None

  def receiveReady(self, child, message):
    self.taskMaster.onWorkerReady(child)

  def receiveRanTask(self, child, message):
    self.taskMaster.onWorkerRanTask(child, message)

  def receiveError(self, child, error):
    self.taskMaster.onWorkerDied(child, error)

# The TaskMasterChild is in the same process as the WorkerParent.
class TaskMasterChild(ChildProcessListener):
  def __init__(self, pump, channel, task_graph, buildPath, child_channels):
    super(TaskMasterChild, self).__init__(pump, channel)
    self.task_graph = task_graph
    self.outstanding = {}
    self.idle = set()
    self.build_failed = False
    self.build_completed = False

    self.procman = ProcessManager(pump)
    for channel in child_channels:
      self.procman.spawn(
        WorkerParent(self, channel),
        WorkerChild,
        args=(buildPath,),
        channels=(channel,)
      )

    self.channel.send({
      'id': 'spawned',
      'pid': os.getpid()
    })

  def buildFailed(self):
    if not self.build_failed:
      self.build_failed = True
      self.close_idle()

  def receiveClose(self, channel):
    # We received a close request, so wait for all children to finish.
    if not self.build_completed:
      # The master process might have decided we failed, in which case it'll
      # request an early shutdown. Set our own fail bit so worker processes
      # don't enqueue more tasks.
      self.build_failed = True
    self.procman.shutdown()

  def onWorkerRanTask(self, child, message):
    if not message['ok']:
      self.channel.send({
        'id': 'completed',
        'status': 'failed',
      })
      self.procman.close(child)
      self.buildFailed()
      return

    task_id = message['task_id']
    task, child = self.outstanding[task_id]
    del self.outstanding[task_id]

    # Enqueue any tasks that can be run if this was their last outstanding
    # dependency.
    for outgoing in task.outgoing:
      outgoing.incoming.remove(task)
      if len(outgoing.incoming) == 0:
        self.task_graph.append(outgoing)

    self.onWorkerReady(child)

    # If more stuff was queued, and we have idle processes, use them.
    while len(self.task_graph) and len(self.idle):
      child = self.idle.pop()
      if not self.onWorkerReady(child):
        break

  def close_idle(self):
    for child in self.idle:
      self.procman.close(child)
    self.idle = set()

  def onWorkerReady(self, child):
    # If the build failed, ignore the message.
    if self.build_failed:
      return False

    if not len(self.task_graph):
      if len(self.outstanding):
        # There are still tasks left to complete, but they're waiting on
        # others to finish. Mark this process as ready and just ignore the
        # status change for now.
        self.idle.add(child)
      else:
        # There are no tasks remaining, the worker is not needed.
        self.build_completed = True
        self.procman.close(child)
        self.close_idle()
        self.channel.send({
          'id': 'completed',
          'status': 'ok'
        })
      return False

    # Send a task to the worker.
    task = self.task_graph.pop()

    message = {
      'id': 'task',
      'task_id': task.id,
      'task_type': task.type,
      'task_data': task.data,
      'task_folder': task.folder,
      'task_outputs': task.outputs
    }
    child.send(message)
    self.outstanding[task.id] = (task, child)
    return True

  def onWorkerCrashed(self, child, task):
    self.channel.send({
      'id': 'completed',
      'status': 'crashed',
      'task_id': task.id,
    })
    self.buildFailed()

  def onWorkerDied(self, child, error):
    if error != Error.NormalShutdown:
      for task_id in self.outstanding.keys():
        task, task_child = self.outstanding[task_id]
        if task_child == child:
          # A worker failed, but crashed, so we have to tell the main process.
          self.onWorkerCrashed(child, task)
          break

    self.idle.discard(child)

    for other_child in self.procman.children:
      if other_child == child:
        continue
      if other_child.is_alive():
        return

    # If we got here, no other child processes are live, so we can quit.
    self.channel.finished()
    self.pump.cancel()

class WorkerIOListener(MessageListener):
  def __init__(self, taskMaster, close_on_ack):
    super(WorkerIOListener, self).__init__(close_on_ack)
    self.taskMaster = taskMaster
    self.messageMap = {
      'results': lambda channel, message: self.taskMaster.processResults(message),
      'spawned': lambda channel, message: self.receiveSpawned(message)
    }

  def receiveSpawned(self, message):
    util.con_out(
      util.ConsoleHeader,
      'Spawned worker (pid: {0})'.format(message['pid']),
      util.ConsoleNormal
    )

  def receiveError(self, channel, error):
    if error != Error.NormalShutdown:
      # This should only really happen if processResults throws.
      self.taskMaster.terminateBuild(graceful=True)

class TaskMasterParent(ParentProcessListener):
  def __init__(self, cx, builder, task_graph, max_parallel):
    super(TaskMasterParent, self).__init__('TaskMaster')
    self.cx = cx
    self.builder = builder
    self.build_failed = False
    self.messageMap = {
      'completed': lambda child, message: self.receiveCompleted(child, message),
      'spawned': lambda child, message: self.receiveSpawned(message),
    }

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
    else:
      num_processes = cx.options.jobs

    # Don't create more processes than we'll need.
    if num_processes > max_parallel:
      num_processes = max_parallel

    # Create the list of pipes we'll be using.
    self.channels = []
    child_channels = []
    for i in range(num_processes):
      parent_channel, child_channel = cx.messagePump.createChannel('WorkerIO')
      listener = WorkerIOListener(self, close_on_ack=child_channel)
      cx.messagePump.addChannel(parent_channel, listener)
      child_channels.append(child_channel)

    # Spawn the task master.
    cx.procman.spawn(
      self,
      TaskMasterChild,
      args=(task_graph, cx.buildPath),
      channels=child_channels
    )

  def processResults(self, message):
    if message['ok']:
      color = util.ConsoleGreen
    else:
      color = util.ConsoleRed
    util.con_out(
      util.ConsoleBlue,
      '[{0}]'.format(message['pid']),
      util.ConsoleNormal,
      ' ',
      color,
      message['cmdline'],
      util.ConsoleNormal
    )
    if len(message['stdout']):
      sys.stdout.write(message['stdout'])
      if message['stdout'][-1] != '\n':
        sys.stdout.write('\n')
    if len(message['stderr']):
      sys.stderr.write(message['stderr'])
      if message['stderr'][-1] != '\n':
        sys.stderr.write('\n')

    if not message['ok']:
      self.terminateBuild(graceful=True)
      return

    task_id = message['task_id']
    updates = message['updates']
    node = self.builder.findTask(task_id)
    if not self.builder.updateGraph(node, updates, message):
      util.con_out(
        util.ConsoleRed,
        'Failed to update node!',
        util.ConsoleNormal
      )
      self.terminateBuild(graceful=True)

  def terminateBuild(self, graceful):
    if not graceful:
      self.cx.messagePump.cancel()

    if not self.build_failed:
      self.build_failed = True
      self.cx.procman.shutdown()

  def receiveSpawned(self, message):
    util.con_out(
      util.ConsoleHeader,
      'Spawned task master (pid: {0})'.format(message['pid']),
      util.ConsoleNormal
    )

  def receiveError(self, child, error):
    if error != Error.NormalShutdown:
      sys.stderr.write('Received unexpected error from child process {0}: {1}\n'.format(child.pid, error))
      self.terminateBuild(graceful=False)

  def receiveCompleted(self, child, message):
    if message['status'] == 'crashed':
      task = self.builder.findTask(message['task_id'])
      sys.stderr.write('Crashed trying to perform update:\n')
      sys.stderr.write('  : {0}\n'.format(task.entry.format()))
      self.terminateBuild(graceful=True)
    elif message['status'] == 'failed':
      self.terminateBuild(graceful=True)
    else:
      self.cx.procman.close(child)

  def run(self):
    self.cx.messagePump.pump()
    return not self.build_failed

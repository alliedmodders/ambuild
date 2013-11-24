# vim: set ts=8 sts=2 sw=2 tw=99 et:
import errno
import shutil
import os, sys
import traceback
import multiprocessing as mp
from ambuild2 import util
from ambuild2 import nodetypes
from ambuild2.ipc import ParentProcessListener, ChildProcessListener
from ambuild2.ipc import ProcessManager, MessageListener, Error
from ambuild2.ipc import Channel

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
  def __init__(self, pump, channel, buildPath):
    super(WorkerChild, self).__init__(pump, channel)
    self.buildPath = buildPath
    self.pid = os.getpid()
    self.messageMap = {
      'task': lambda channel, message: self.receiveTask(channel, message)
    }
    self.taskMap = {
      'cxx': lambda message: self.doCompile(message),
      'cmd': lambda message: self.doCommand(message),
      'ln': lambda message: self.doSymlink(message),
      'cp': lambda message: self.doCopy(message),
      'rc': lambda message: self.doResource(message),
    }

    self.channel.send({
      'id': 'ready',
      'finished': None
    })

  def receiveTask(self, channel, message):
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
    # Compute new timestamps for all command outputs.
    new_timestamps = []
    if response['ok']:
      for output in message['task_outputs']:
        try:
          new_timestamps.append((output, os.path.getmtime(output)))
        except:
          response['ok'] = False
          response['stderr'] += 'Expected output file, but not found: {0}'.format(output)
          break

    # Send a message back to the master process to update the DAG and spew
    # stdout/stderr if needed.
    response['id'] = 'results'
    response['pid'] = self.pid
    response['task_id'] = message['task_id']
    response['updates'] = new_timestamps
    self.channel.send(response)

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
      if os.path.exists(source_path):
        shutil.copy(source_path, output_path)
        ok = True
        stderr = ''
      else:
        ok = False
        stderr = 'File not found: {0}'.format(source_path)

    reply = {
      'ok': ok,
      'cmdline': 'cp "{0}" "{1}"'.format(source_path, os.path.join(task_folder, output_path)),
      'stdout': '',
      'stderr': stderr,
    }
    return reply

  # Adjusts any dependencies relative to the current folder, to be relative to
  # the output folder instead.
  def rewriteDeps(self, deps):
    paths = []
    for inc_path in deps:
      if not os.path.isabs(inc_path):
        inc_path = os.path.abspath(inc_path)

      # Detect whether the include is within the build folder or not.
      build_path = self.buildPath
      if build_path[-1] != os.path.sep:
        build_path += os.path.sep
      prefix = os.path.commonprefix([build_path, inc_path])
      if prefix == build_path:
        # The include is not a system include, i.e. it was generated, so
        # rewrite the path to be relative to the build folder.
        inc_path = os.path.relpath(inc_path, self.buildPath)

      paths.append(inc_path)
    return paths

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
      elif cc_type == 'sun':
        err, deps = util.ParseSunDeps(err)
      else:
        raise Exception('unknown compiler type')

      paths = self.rewriteDeps(deps)

    reply = {
      'ok': p.returncode == 0,
      'cmdline': ' '.join([arg for arg in argv]),
      'stdout': out,
      'stderr': err,
      'deps': paths,
    }
    return reply

  def doResource(self, message):
    task_folder = message['task_folder']
    task_data = message['task_data']
    cl_argv = task_data['cl_argv']
    rc_argv = task_data['rc_argv']

    with util.FolderChanger(task_folder):
      # Includes go to stderr when we preprocess to stdout.
      p, out, err = util.Execute(cl_argv)
      out, deps = util.ParseMSVCDeps(err)
      paths = self.rewriteDeps(deps)

      if p.returncode == 0:
        p, out, err = util.Execute(rc_argv)
        
    reply = {
      'ok': p.returncode == 0,
      'cmdline': (' '.join([arg for arg in cl_argv]) + ' && ' + ' '.join([arg for arg in rc_argv])),
      'stdout': out,
      'stderr': err,
      'deps': paths,
    }
    return reply


# The WorkerParent is in the same process as the TaskMasterChild.
class WorkerParent(ParentProcessListener):
  def __init__(self, taskMaster):
    super(WorkerParent, self).__init__('Worker')
    self.taskMaster = taskMaster
    self.messageMap = {
      'ready': lambda child, message: self.receiveReady(child, message),
      'results': lambda child, message: self.receiveResults(child, message),
    }

  def receiveReady(self, child, message):
    self.taskMaster.onWorkerReady(child, message)

  def receiveResults(self, child, message):
    self.taskMaster.onWorkerResults(child, message)

  def receiveError(self, child, error):
    self.taskMaster.onWorkerDied(child, error)

# The TaskMasterChild is in the same process as the WorkerParent.
class TaskMasterChild(ChildProcessListener):
  def __init__(self, pump, channel, task_graph, buildPath, num_processes):
    super(TaskMasterChild, self).__init__(pump, channel)
    self.task_graph = task_graph
    self.outstanding = {}
    self.idle = set()
    self.build_failed = False
    self.build_completed = False
    self.messageMap = {
      'stop': lambda channel, message: self.receiveStop(channel, message)
    }

    self.procman = ProcessManager(pump)
    for i in range(num_processes):
      self.procman.spawn(
        WorkerParent(self),
        WorkerChild,
        args=(buildPath,)
      )

    self.channel.send({
      'id': 'spawned',
      'pid': os.getpid(),
      'type': 'taskmaster'
    })

  def receiveStop(self, channel, message):
    if not message['ok']:
      self.terminateBuild()
    self.close_idle()

  def terminateBuild(self):
    if self.build_failed:
      return

    self.build_failed = True
    self.close_idle()

  def receiveClose(self, channel):
    self.procman.shutdown()
    self.pump.cancel()

  def onWorkerResults(self, child, message):
    # Forward the results to the master process.
    self.channel.send(message)

    if not message['ok']:
      self.channel.send({
        'id': 'completed',
        'status': 'failed',
      })
      self.procman.close(child)
      self.terminateBuild()
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

    self.onWorkerReady(child, None)

    # If more stuff was queued, and we have idle processes, use them.
    while len(self.task_graph) and len(self.idle):
      child = self.idle.pop()
      if not self.onWorkerReady(child, None):
        break

  def close_idle(self):
    for child in self.idle:
      self.procman.close(child)
    self.idle = set()

  def onWorkerReady(self, child, message):
    if message and not message['finished']:
      self.channel.send({
        'id': 'spawned',
        'pid': child.pid,
        'type': 'worker'
      })

    # If the build failed, ignore the message, and shutdown the process.
    if self.build_failed:
      self.procman.close(child)
      self.maybe_request_shutdown(child)
      return

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
    self.terminateBuild()

  def onWorkerDied(self, child, error):
    if error != Error.NormalShutdown:
      for task_id in self.outstanding.keys():
        task, task_child = self.outstanding[task_id]
        if task_child == child:
          # A worker failed, but crashed, so we have to tell the main process.
          self.onWorkerCrashed(child, task)
          break

    self.idle.discard(child)
    self.maybe_request_shutdown(child)

  def maybe_request_shutdown(self, child):
    for other_child in self.procman.children:
      if other_child == child:
        continue
      if other_child.is_alive():
        return

    # If we got here, no other child processes are live, so we can ask for
    # safe shutdown. This is needed to make sure all our messages arrive,
    # since closing one end of the pipe destroys any leftover data.
    self.channel.send({
      'id': 'done'
    })

class TaskMasterParent(ParentProcessListener):
  def __init__(self, cx, builder, task_graph, max_parallel):
    super(TaskMasterParent, self).__init__('TaskMaster')
    self.cx = cx
    self.builder = builder
    self.build_failed = False
    self.messageMap = {
      'completed': lambda child, message: self.receiveCompleted(child, message),
      'spawned': lambda child, message: self.receiveSpawned(message),
      'results': lambda child, message: self.processResults(message),
      'done': lambda child, message: self.receiveDone(message),
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
        num_processes = int(mp.cpu_count() * 1.25)
    else:
      num_processes = cx.options.jobs

    # Don't create more processes than we'll need.
    if num_processes > max_parallel:
      num_processes = max_parallel

    # Spawn the task master.
    self.taskMaster = cx.procman.spawn(
      self,
      TaskMasterChild,
      args=(task_graph, cx.buildPath, num_processes)
    )

  def receiveDone(self, message):
    self.cx.procman.shutdown()

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
      self.terminateBuild()
      return

    task_id = message['task_id']
    updates = message['updates']
    if not self.builder.updateGraph(task_id, updates, message):
      util.con_out(
        util.ConsoleRed,
        'Failed to update node!',
        util.ConsoleNormal
      )
      self.terminateBuild()

  def terminateBuild(self):
    if self.build_failed:
      return
    self.build_failed = True
    self.taskMaster.send({
      'id': 'stop',
      'ok': False
    })

  def receiveSpawned(self, message):
    util.con_out(
      util.ConsoleHeader,
      'Spawned {0} (pid: {1})'.format(message['type'], message['pid']),
      util.ConsoleNormal
    )

  def receiveError(self, child, error):
    if error != Error.NormalShutdown:
      sys.stderr.write('Received unexpected error from child process {0}: {1}\n'.format(child.pid, error))
      self.terminateBuild()

  def receiveCompleted(self, child, message):
    if message['status'] == 'crashed':
      task = self.builder.commands[message['task_id']]
      sys.stderr.write('Crashed trying to perform update:\n')
      sys.stderr.write('  : {0}\n'.format(task.entry.format()))
      self.terminateBuild()
    elif message['status'] == 'failed':
      self.terminateBuild()
    else:
      self.taskMaster.send({
        'id': 'stop',
        'ok': True
      })

  def run(self):
    self.cx.messagePump.pump()
    return not self.build_failed

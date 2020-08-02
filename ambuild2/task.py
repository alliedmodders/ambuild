# vim: set ts=8 sts=2 sw=2 tw=99 et:
import errno
import multiprocessing as mp
import shutil
import os, sys
import traceback
from ambuild2 import ipc
from ambuild2 import util
from ambuild2 import nodetypes
from ambuild2 import process_manager

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

class TaskWorker(process_manager.MessageReceiver):
  def __init__(self, channel, vars):
    super(TaskWorker, self).__init__(channel)
    self.buildPath = vars['buildPath']
    self.pid = os.getpid()
    self.vars = vars
    self.messageMap = {
      'task': lambda channel, message: self.receive_task(channel, message)
    }
    self.taskMap = {
      # When updating this, add to task_argv_debug().
      'cxx': lambda message: self.doCompile(message),
      'cmd': lambda message: self.doCommand(message),
      'ln': lambda message: self.doSymlink(message),
      'cp': lambda message: self.doCopy(message),
      'rc': lambda message: self.doResource(message),
      # When updating this, add to task_argv_debug().
    }
    self.channel.send({'id': 'spawned'})

  def onShutdown(self):
    pass

  def receive_task(self, channel, message):
    try:
      return self.process_task(channel, message)
    except Exception as e:
      response = {
        'ok': False,
        'cmdline': self.task_argv_debug(message),
        'stdout': '',
        'stderr': traceback.format_exc(),
      }
      return self.issueResponse(message, response)

  def process_task(self, channel, message):
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
      'cmdline': self.task_argv_debug(message),
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
      'cmdline': self.task_argv_debug(message),
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
      'cmdline': self.task_argv_debug(message),
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
        out, deps = util.ParseMSVCDeps(self.vars, out)
      elif cc_type == 'sun':
        err, deps = util.ParseSunDeps(err)
      elif cc_type == 'fxc':
        out, deps = util.ParseFXCDeps(out)
      else:
        raise Exception('unknown compiler type')

      paths = self.rewriteDeps(deps)

    reply = {
      'ok': p.returncode == 0,
      'cmdline': self.task_argv_debug(message),
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
      out, deps = util.ParseMSVCDeps(self.vars, err)
      paths = self.rewriteDeps(deps)

      if p.returncode == 0:
        p, out, err = util.Execute(rc_argv)
        
    reply = {
      'ok': p.returncode == 0,
      'cmdline': self.task_argv_debug(message),
      'stdout': out,
      'stderr': err,
      'deps': paths,
    }
    return reply

  def task_argv_debug(self, message):
    task_data = message.get('task_data', None)
    if message['task_type'] == 'rc':
      cl_argv = task_data['cl_argv']
      rc_argv = task_data['rc_argv']
      return ' '.join([arg for arg in cl_argv]) + ' && ' + ' '.join([arg for arg in rc_argv])
    elif message['task_type'] == 'cxx':
      return ' '.join([arg for arg in task_data['argv']])
    elif message['task_type'] == 'cmd':
      return ' '.join([arg for arg in task_data])
    elif message['task_type'] in ['cp', 'ln']:
      task_folder = message['task_folder']
      if message['task_type'] == 'cp':
        cmd = 'cp'
      elif message['task_type'] == 'ln':
        cmd = 'ln -s'
      return '{} "{}" "{}"'.format(cmd, task_data[0], os.path.join(task_folder, task_data[1]))

class TaskMaster(object):
  BUILD_IN_PROGRESS = 0
  BUILD_SUCCEEDED = 1
  BUILD_NO_CHANGES = 2
  BUILD_FAILED = 3
  BUILD_INTERRUPTED = 4

  def __init__(self, cx, builder, task_graph, max_parallel):
    self.cx = cx
    self.builder = builder
    self.status_ = TaskMaster.BUILD_IN_PROGRESS
    self.messageMap = {
      'completed': lambda child, message: self.receiveCompleted(child, message),
      'spawned': lambda child, message: self.recvSpawned(child, message),
      'results': lambda child, message: self.recvTaskComplete(child, message),
      'done': lambda child, message: self.receiveDone(child, message),
    }
    self.errors_ = []
    self.task_graph = task_graph
    self.workers_ = []
    self.pending_ = {}
    self.idle_ = set()
    self.build_completed_ = False

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

    for _ in range(num_processes):
      self.startWorker()

  def spewResult(self, worker, message):
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
      util.ConsoleNormal)
    sys.stdout.flush()

    if len(message['stdout']):
      util.WriteEncodedText(sys.stdout, message['stdout'])
      if message['stdout'][-1] != '\n':
        sys.stdout.write('\n')
      sys.stdout.flush()
          
    if len(message['stderr']):
      util.WriteEncodedText(sys.stderr, message['stderr'])
      if message['stderr'][-1] != '\n':
        sys.stderr.write('\n')
      sys.stderr.flush()

  def recvTaskComplete(self, worker, message):
    message['pid'] = worker.pid
    if not message['ok']:
      self.errors_.append((worker, message))
      self.terminateBuild(TaskMaster.BUILD_FAILED)
      return

    self.spewResult(worker, message)

    task = self.pending_[worker.pid]
    del self.pending_[worker.pid]
    if message['task_id'] != task.id:
      raise Exception('Worker {} returned wrong task id (got {}, expected {})'.format(
                      worker.pid, task_id, task.id))

    updates = message['updates']
    if not self.builder.updateGraph(task.id, updates, message):
      util.con_out(util.ConsoleRed, 'Failed to update node!', util.ConsoleNormal)
      self.terminateBuild(TaskMaster.BUILD_FAILED)

    # Enqueue any tasks that can be run if this was their last outstanding
    # dependency.
    for outgoing in task.outgoing:
      outgoing.incoming.remove(task)
      if len(outgoing.incoming) == 0:
        self.task_graph.append(outgoing)

    if not len(self.task_graph) and not len(self.pending_):
      # There are no tasks remaining.
      self.status_ = TaskMaster.BUILD_SUCCEEDED

    # Add this process to the idle set.
    self.idle_.add(worker)

    # If more stuff was queued, and we have idle processes, use them.
    while len(self.task_graph) and len(self.idle_):
      worker = self.idle_.pop()
      self.issue_next_task(worker)

  def terminateBuild(self, status):
    self.status_ = status

  def startWorker(self):
    args = (self.cx.vars,)
    child = self.cx.procman.spawn(TaskWorker, args)
    self.workers_.append(child)

    util.con_out(
      util.ConsoleHeader,
      'Spawned {0} (pid: {1})'.format('worker', child.proc.pid),
      util.ConsoleNormal)

  def run(self):
    try:
      self.pump()
    except KeyboardInterrupt: # :TODO: TEST!
      self.terminateBuild(TaskMaster.BUILD_INTERRUPTED)
    for worker, message in self.errors_:
      self.spewResult(worker, message)
    return self.status_

  def onShutdown(self):
    return False

  def recvSpawned(self, worker, message):
    if self.status_ != TaskMaster.BUILD_IN_PROGRESS:
      return

    if not len(self.task_graph):
      # If there are still tasks left to complete, they're waiting on others
      # to finish. Mark this process as ready and just ignore the status
      # change for now.
      self.idle_.add(worker)
      return

    self.issue_next_task(worker)

  def issue_next_task(self, worker):
    task = self.task_graph.pop()
    message = {
      'id': 'task',
      'task_id': task.id,
      'task_type': task.type,
      'task_data': task.data,
      'task_folder': task.folder,
      'task_outputs': task.outputs
    }
    worker.channel.send(message)
    self.pending_[worker.pid] = task

  def pump(self):
    with process_manager.ChannelPoller(self.cx, self.workers_) as poller:
      while self.status_ == TaskMaster.BUILD_IN_PROGRESS:
        try:
          proc, obj = poller.poll()
          if obj['id'] not in self.messageMap:
            raise Exception('Unhandled message type: {}'.format(obj['id']))
          self.messageMap[obj['id']](proc, obj)
        except EOFError:
          # The process died. Very sad. Clean up and fail the build.
          util.con_err(util.ConsoleBlue, '[{0}]'.format(proc.pid), util.ConsoleNormal, ' ',
                       util.ConsoleRed, 'Worker unexpectedly exited.')
          self.terminateBuild(TaskMaster.BUILD_FAILED)
          break

  def status(self):
    return self.status_

  def succeeded(self):
    return self.status_ == TaskMaster.BUILD_SUCCEEDED

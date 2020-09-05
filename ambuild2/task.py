# vim: set ts=8 sts=4 sw=4 tw=99 et:
import errno
import multiprocessing as mp
import shutil
import os, sys
import traceback
from ambuild2 import make_parser
from ambuild2 import nodetypes
from ambuild2 import process_manager
from ambuild2 import util

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
        self.tools_env = entry.tools_env

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
            return '[' + self.data['type'] + ']' + ' -> ' + (' '.join(
                [arg for arg in self.data['argv']]))
        if self.type == nodetypes.Symlink:
            return 'ln -s "{0}" "{1}"'.format(self.data[0],
                                              os.path.join(self.folder_name, self.data[1]))
        if self.type == nodetypes.Copy:
            return 'cp "{0}" "{1}"'.format(self.data[0], os.path.join(self.folder_name,
                                                                      self.data[1]))
        return (' '.join([arg for arg in self.data]))

def GetMsvcInclusionPattern(vars, tools_env):
    if 'cc_inclusion_pattern' in vars:
        return vars['cc_inclusion_pattern']
    elif 'cxx_inclusion_pattern' in vars:
        return vars['cxx_inclusion_pattern']
    elif 'msvc_inclusion_pattern' in vars:
        return vars['msvc_inclusion_pattern']
    if tools_env:
        if 'inclusion_pattern' in tools_env.props:
            return tools_env.props['inclusion_pattern']
    return None

class TaskWorker(process_manager.MessageReceiver):
    def __init__(self, channel, vars):
        super(TaskWorker, self).__init__(channel)
        self.buildPath = vars['buildPath']
        self.pid = os.getpid()
        self.vars = vars
        self.messageMap = {'task': lambda channel, message: self.receive_task(channel, message)}
        self.taskMap = {
            # When updating this, add to task_argv_debug().
            'cxx': lambda message: self.doCompile(message),
            'cmd': lambda message: self.doCommand(message),
            'ln': lambda message: self.doSymlink(message),
            'cp': lambda message: self.doCopy(message),
            'rc': lambda message: self.doResource(message),
            'bin': lambda message: self.doBinaryWrite(message),
            # When updating this, add to task_argv_debug().
        }
        self.try_send({'id': 'spawned'})

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
        self.try_send(response)

    def try_send(self, message):
        try:
            self.channel.send(message)
        except OSError as e:
            if getattr(e, 'winerror', 0) == 232:
                # Parent is dead, so ignore the error.
                return
            raise

    def doCommand(self, message):
        task_folder = message['task_folder']
        tools_env = message['task_tools_env']
        argv = message['task_data']

        env = None
        if tools_env is not None:
            if tools_env.env_cmds is not None:
                env = util.BuildEnv(tools_env.env_cmds)
            if argv[0] in tools_env.tools:
                argv[0] = tools_env.tools[argv[0]]

        with util.FolderChanger(task_folder):
            try:
                p, stdout, stderr = util.Execute(argv, env = env)
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

    def doBinaryWrite(self, message):
        task_folder = message['task_folder']
        task_data = message['task_data']
        _, filename = os.path.split(task_data['path'])

        reply = {
            'ok': True,
            'cmdline': self.task_argv_debug(message),
            'stdout': '',
            'stderr': '',
        }
        with util.FolderChanger(task_folder):
            try:
                with open(filename, 'wb') as fp:
                    fp.write(task_data['contents'])
            except Exception as e:
                reply['ok'] = False
                reply['stderr'] = str(e)
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
        tools_env = message['task_tools_env']
        cc_type = task_data['type']
        argv = task_data['argv']

        if 'deps' in task_data:
            dep_type, dep_info = task_data['deps']
        else:
            dep_type = cc_type
            dep_info = None

        env = None
        if tools_env is not None:
            if tools_env.env_cmds is not None:
                env = util.BuildEnv(tools_env.env_cmds)
            if 'cl' in tools_env.tools:
                argv[0] = tools_env.tools['cl']

        with util.FolderChanger(task_folder):
            p, out, err = util.Execute(argv, env = env)
            out, err, paths = self.parseDependencies(p, tools_env, out, err, dep_type, dep_info)

        reply = {
            'ok': p.returncode == 0,
            'cmdline': self.task_argv_debug(message),
            'stdout': out,
            'stderr': err,
            'deps': paths,
        }
        return reply

    def parseDependencies(self, p, tools_env, out, err, dep_type, dep_info):
        if dep_type == 'md':
            try:
                with open(dep_info) as fp:
                    deps = make_parser.ParseDependencyFile(dep_info, fp)
            except:
                if p.returncode == 0:
                    raise
                deps = []
        elif dep_type == 'gcc':
            err, deps = util.ParseGCCDeps(err)
        elif dep_type == 'msvc':
            inclusion_pattern = GetMsvcInclusionPattern(self.vars, tools_env)
            out, deps = util.ParseMSVCDeps(out, inclusion_pattern)
        elif dep_type == 'fxc':
            out, deps = util.ParseFXCDeps(out)
        else:
            raise Exception('unknown dependency type')

        paths = self.rewriteDeps(deps)
        return out, err, paths

    def doResource(self, message):
        task_folder = message['task_folder']
        task_data = message['task_data']
        tools_env = message['task_tools_env']
        cl_argv = task_data['cl_argv']
        rc_argv = task_data['rc_argv']

        inclusion_pattern = GetMsvcInclusionPattern(self.vars, tools_env)

        env = None
        if tools_env is not None:
            if tools_env.env_cmds is not None:
                env = util.BuildEnv(tools_env.env_cmds)
            if 'cl' in tools_env.tools:
                cl_argv[0] = tools_env.tools['cl']
            if 'rc' in tools_env.tools:
                rc_argv[0] = tools_env.tools['rc']

        with util.FolderChanger(task_folder):
            # Includes go to stderr when we preprocess to stdout.
            p, out, err = util.Execute(cl_argv, env = env)
            out, deps = util.ParseMSVCDeps(err, inclusion_pattern)
            paths = self.rewriteDeps(deps)

            if p.returncode == 0:
                p, out, err = util.Execute(rc_argv, env = env)

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
        elif message['task_type'] == 'bin':
            return 'write {}'.format(message['task_data']['path'])

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
        self.failed_task_message = None

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

    def spewResult(self, worker, task, message):
        if message['ok']:
            color = util.ConsoleGreen
        else:
            color = util.ConsoleRed
        util.con_out(util.ConsoleBlue, '[{0}]'.format(message['pid']), util.ConsoleNormal, ' ',
                     color, message['cmdline'], util.ConsoleNormal)
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

        if not message['ok'] and task:
            self.failed_task_message = task.outputs[0]

    def recvTaskComplete(self, worker, message):
        task = self.pending_[worker.pid]

        message['pid'] = worker.pid
        if not message['ok']:
            self.errors_.append((worker, task, message))
            self.terminateBuild(TaskMaster.BUILD_FAILED)
            return

        self.spewResult(worker, task, message)

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

        util.con_out(util.ConsoleHeader, 'Spawned {0} (pid: {1})'.format('worker', child.proc.pid),
                     util.ConsoleNormal)

    def run(self):
        try:
            self.pump()
        except KeyboardInterrupt:  # :TODO: TEST!
            self.terminateBuild(TaskMaster.BUILD_INTERRUPTED)
        for worker, task, message in self.errors_:
            self.spewResult(worker, task, message)
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
            'task_outputs': task.outputs,
            'task_tools_env': task.tools_env,
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
                    util.con_err(util.ConsoleBlue, '[{0}]'.format(proc.pid), util.ConsoleNormal,
                                 ' ', util.ConsoleRed, 'Worker unexpectedly exited.')
                    self.terminateBuild(TaskMaster.BUILD_FAILED)
                    break

    def status(self):
        return self.status_

    def succeeded(self):
        return self.status_ == TaskMaster.BUILD_SUCCEEDED

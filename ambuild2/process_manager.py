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
import errno
import multiprocessing as mp
import multiprocessing.connection
import platform
import select
import sys
try:
    import _winapi
except:
    _winapi = None

# Inherit this to make a child process's main function.
class MessageReceiver(object):
    def __init__(self, channel):
        self.channel = channel
        self.active_ = True

    def pump(self):
        try:
            self.pump_impl()
        except KeyboardInterrupt:
            sys.exit(1)

    def pump_impl(self):
        while self.active_:
            obj = self.channel.recv()
            if obj['id'] == 'stop':
                self.onShutdown()
                return True

            if obj['id'] not in self.messageMap:
                raise Exception('Unhandled message: {}'.format(obj['id']))
            self.messageMap[obj['id']](self, obj)

    def halt_pump(self):
        self.active_ = False

class Channel(object):
    def __init__(self, sender, receiver):
        self.sender_ = sender
        self.receiver_ = receiver

    def send(self, obj):
        return self.sender_.send(obj)

    def recv(self):
        return self.receiver_.recv()

    def close(self):
        self.sender_.close()
        self.receiver_.close()

    @property
    def poll_handle(self):
        return self.receiver_.fileno()

    @property
    def poll_pipe(self):
        return self.receiver_

# Universal main for child processes.
def child_main(target, channel, *args):
    obj = target(channel, *args)
    if obj.pump():
        sys.exit(0)
    else:
        sys.exit(1)

# Wrapper around the parent process's view of a child.
class ProcessHost(object):
    def __init__(self):
        self.proc = None
        self.channel = None

    def spawn(self, target, args):
        parent_send, child_recv = mp.Pipe()
        parent_recv, child_send = mp.Pipe()

        self.channel = Channel(parent_send, parent_recv)
        child_channel = Channel(child_send, child_recv)

        full_args = (target, child_channel) + args
        self.proc = mp.Process(target = child_main, args = full_args)
        self.proc.start()

    @property
    def pid(self):
        return self.proc.pid

class ProcessManager(object):
    def __init__(self):
        self.tasks_ = mp.Queue()
        self.children_ = []

    def spawn(self, target, args):
        child = ProcessHost()
        child.spawn(target, args)
        self.children_.append(child)
        return child

    def shutdown(self):
        self.close_all_children()

    def close_all_children(self):
        for child in self.children_:
            try:
                child.channel.send({
                    'id': 'stop',
                })
                child.channel.close()
            except:
                pass

        for child in self.children_:
            child.proc.join()
        self.children_ = []

class ChannelPollerBase(object):
    def __init__(self, cx, procs):
        self.cx_ = cx
        self.procs_ = procs[:]

# If available, use native Python 3.3+ support for multiplexing.
if hasattr(mp, 'connection') and hasattr(mp.connection, 'wait'):

    class ChannelPoller(ChannelPollerBase):
        def __init__(self, cx, procs):
            super(ChannelPoller, self).__init__(cx, procs)
            self.map_ = {}
            self.pipes_ = None

        def __enter__(self):
            for proc in self.procs_:
                self.map_[proc.channel.poll_pipe] = proc
            self.pipes_ = [proc.channel.poll_pipe for proc in self.procs_]
            return self

        def poll(self):
            ready = mp.connection.wait(self.pipes_)
            proc = self.map_[ready[0]]
            return proc, proc.channel.recv()

        def __exit__(self, type, value, traceback):
            pass

# Windows does not allow WaitForMultipleObjects on a pipe, we'd need to use
# IO completion ports. I can't get ReOpenFile() to work, so we do something
# extremely gross: spawn a bunch of threads.
elif platform.system() == 'Windows':
    import collections
    import threading

    def wait_on_pipe(poller, proc):
        try:
            while True:
                obj = proc.channel.recv()
                poller.on_receive(proc, obj)
        except:
            poller.on_receive(proc, None)

    class ChannelPoller(ChannelPollerBase):
        def __init__(self, cx, procs):
            super(ChannelPoller, self).__init__(cx, procs)
            self.closing_ = False
            self.threads_ = []
            self.lock_ = threading.RLock()
            self.cv_ = threading.Condition(self.lock_)
            self.queue_ = collections.deque()

        def __enter__(self):
            for proc in self.procs_:
                thread = threading.Thread(target = wait_on_pipe,
                                          name = "Pipe Waiter",
                                          args = (self, proc))
                self.threads_.append(thread)
            for thread in self.threads_:
                thread.start()
            return self

        def poll(self):
            with self.cv_:
                while len(self.queue_) == 0:
                    self.cv_.wait()
                    continue
                proc, obj = self.queue_.popleft()

                if obj is None:
                    raise EOFError('Process {} pipe closed'.format(proc.pid))

            return proc, obj

        def on_receive(self, proc, obj):
            with self.cv_:
                if not self.closing_:
                    self.queue_.append((proc, obj))
                    self.cv_.notify_all()

        def __exit__(self, type, value, traceback):
            with self.cv_:
                self.closing_ = True

            # This is a hack, but it's the easiest way to ensure that worker
            # processes won't throw a broken pipe exception.
            self.cx_.procman.close_all_children()

            # Force pipes to close to terminate threads
            for proc in self.procs_:
                proc.channel.close()
            for thread in self.threads_:
                thread.join()

# And everywhere else use select().
else:

    class ChannelPoller(ChannelPollerBase):
        def __init__(self, cx, procs):
            super(ChannelPoller, self).__init__(cx, procs)
            self.map_ = {}
            self.rdlist_ = []

        def __enter__(self):
            for proc in self.procs_:
                self.map_[proc.channel.poll_handle] = proc
                self.rdlist_ = [key for key in self.map_]
            return self

        def poll(self):
            while True:
                try:
                    ready, _, _ = select.select(self.rdlist_, [], [])
                    if ready:
                        proc = self.map_[ready[0]]
                        return proc, proc.channel.recv()
                except select.error as e:
                    if e.args[0] == errno.EINTR:
                        continue
                    raise

        def __exit__(self, type, value, traceback):
            pass

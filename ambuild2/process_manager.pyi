# vim: set ts=8 sts=4 sw=4 tw=99 et:
#
# This file is part of AMBuild.
#
# AMBuild is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# at your option any later version.
#
# AMBuild is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with AMBuild. If not, see <http://www.gnu.org/licenses/>.

import argparse
import multiprocessing as mp
import sys

if sys.platform == 'win32':
    from multiprocessing.connection import PipeConnection as mp_Connection
else:
    from multiprocessing.connection import Connection as mp_Connection
from types import TracebackType
from typing import Any, Literal, Self

from _typeshed import Incomplete
from ambuild2.context import Context
from ambuild2.util import Expando

type _Connection = mp_Connection

class MessageReceiver:
    channel: Channel
    active_: bool

    def __init__(self, channel: Channel) -> None: ...
    def pump(self) -> None: ...
    def pump_impl(self) -> Literal[True] | None: ...
    def halt_pump(self) -> None: ...

class Channel:
    sender_: _Connection
    receiver_: _Connection

    def __init__(self, sender: _Connection, receiver: _Connection) -> None: ...
    def send(self, obj: dict[str, Any]) -> None: ...
    def recv(self) -> dict[str, Any]: ...
    def close(self) -> None: ...
    @property
    def poll_handle(self) -> int: ...
    @property
    def poll_pipe(self) -> _Connection: ...

def child_main(target: Incomplete, channel: Channel, *args: Incomplete) -> None: ...

class ProcessHost:
    proc: mp.Process | None
    channel: Channel | None
    def __init__(self) -> None: ...
    def spawn[T](self, target: type[T], args: tuple[dict[str, Expando | argparse.Namespace | dict[str, str] | str]]) -> None: ...
    @property
    def pid(self) -> int | None: ...

class ProcessManager:
    tasks_: mp.Queue[Incomplete]
    children_: list[ProcessHost]
    def __init__(self) -> None: ...
    def spawn[T](self, target: type[T], args: tuple[dict[str, Expando | argparse.Namespace | dict[str, str] | str]]) -> ProcessHost: ...
    def shutdown(self) -> None: ...
    def close_all_children(self) -> None: ...

class ChannelPollerBase:
    cx_: Context
    procs_: list[ProcessHost]
    def __init__(self, cx: Context, procs: list[ProcessHost]) -> None: ...

# if hasattr(mp, 'connection') and hasattr(mp_connection, 'wait'):
if sys.version_info >= (3, 3):
    class ChannelPoller(ChannelPollerBase):
        map_: dict[_Connection, ProcessHost]
        pipes_: list[_Connection] | None

        def __init__(self, cx: Context, procs: list[ProcessHost]) -> None: ...
        def __enter__(self) -> Self: ...
        def poll(self) -> tuple[ProcessHost, dict[str, Any]]: ...
        def __exit__(self, type: type[BaseException] | None, value: BaseException | None, traceback: TracebackType | None) -> None: ...

elif sys.platform == 'win32':
    import collections
    import threading
    def wait_on_pipe(poller: ChannelPoller, proc: mp.Process) -> None: ...

    class ChannelPoller(ChannelPollerBase):
        closing_: bool
        threads_: list[threading.Thread]
        lock_: threading.RLock
        cv_: threading.Condition
        queue_: collections.deque[mp.Process]

        def __init__(self, cx: Context, procs: list[ProcessHost]) -> None: ...
        def __enter__(self) -> Self: ...
        def poll(self) -> tuple[ProcessHost, dict[str, Any]]: ...
        def on_receive(self, proc: mp.Process, obj: dict[str, Any]) -> None: ...
        def __exit__(self, type: type[BaseException] | None, value: BaseException | None, traceback: TracebackType | None) -> None: ...

else:
    class ChannelPoller(ChannelPollerBase):
        map_: dict[int, mp.Process]
        rdlist_: list[int]

        def __init__(self, cx: Context, procs: list[ProcessHost]) -> None: ...
        def __enter__(self) -> Self: ...
        def poll(self) -> tuple[mp.Process, dict[str, Any]]: ...
        def __exit__(self, type: type[BaseException] | None, value: BaseException | None, traceback: TracebackType | None) -> None: ...

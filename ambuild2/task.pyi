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

from collections.abc import Callable, MutableMapping, Sequence
from typing import Any, Literal, Required, TypedDict

from ambuild2 import process_manager
from ambuild2.builder import Builder
from ambuild2.context import Context
from ambuild2.nodetypes import Entry, NodeType, ToolsEnv

type TaskTypes = Literal['cxx', 'cmd', 'ln', 'cp', 'rc', 'bin']
type _BuildStatus = Literal[0, 1, 2, 3, 4]

class TaskMessage(TypedDict):
    id: Literal['task']
    task_id: int
    task_type: TaskTypes
    task_data: list[str] | tuple[str, str] | dict[str, object]
    task_folder: str | None
    task_outputs: list[str]
    task_tools_env: ToolsEnv | None

class TaskReply(TypedDict, total=False):
    ok: Required[bool]
    cmdline: Required[str | None]
    stdout: Required[str]
    stderr: Required[str]
    deps: list[str]
    updates: list[tuple[str, float]]
    id: str
    task_id: int
    pid: int

class TaskSpawnMessage(TypedDict):
    id: Literal['spawned']

class Task:
    id: int
    type: NodeType
    data: Any
    folder: str | None
    outputs: list[str]
    outgoing: list[Task]
    incoming: set[Task]
    tools_env: ToolsEnv | None

    def __init__(self, id: int, entry: Entry, outputs: list[str]) -> None: ...
    def addOutgoing(self, task: Task) -> None: ...
    @property
    def folder_name(self) -> str: ...
    def format(self) -> str: ...

def GetMsvcInclusionPattern(vars: MutableMapping[str, str], tools_env: ToolsEnv | None) -> str | None: ...

class TaskWorker(process_manager.MessageReceiver):
    buildPath: str
    pid: int
    vars: dict[str, str]
    messageMap: dict[str, Callable[[process_manager.Channel, TaskMessage], TaskReply]]
    taskMap: dict[TaskTypes, Callable[[TaskMessage], TaskReply]]

    def __init__(self, channel: process_manager.Channel, vars: dict[str, str]) -> None: ...
    def onShutdown(self) -> None: ...
    def receive_task(self, channel: process_manager.Channel, message: TaskMessage) -> TaskReply: ...
    def process_task(self, channel: process_manager.Channel, message: TaskMessage) -> TaskReply: ...
    def issueResponse(self, message: TaskMessage, response: TaskReply) -> None: ...
    def try_send(self, message: TaskReply | TaskSpawnMessage | TaskMessage) -> None: ...
    def doCommand(self, message: TaskMessage) -> TaskReply: ...
    def doSymlink(self, message: TaskMessage) -> TaskReply: ...
    def doCopy(self, message: TaskMessage) -> TaskReply: ...
    def doBinaryWrite(self, message: TaskMessage) -> TaskReply: ...
    def rewriteDeps(self, deps: Sequence[str]) -> list[str]: ...
    def doCompile(self, message: TaskMessage) -> TaskReply: ...
    def parseDependencies(self, p: object, tools_env: ToolsEnv | None, out: str, err: str, dep_type: str, dep_info: str | None) -> tuple[str, str, list[str]]: ...
    def doResource(self, message: TaskMessage) -> TaskReply: ...
    def task_argv_debug(self, message: TaskMessage) -> str | None: ...

class TaskMaster:
    BUILD_IN_PROGRESS: Literal[0]
    BUILD_SUCCEEDED: Literal[1]
    BUILD_NO_CHANGES: Literal[2]
    BUILD_FAILED: Literal[3]
    BUILD_INTERRUPTED: Literal[4]

    cx: Context
    builder: Builder
    status_: _BuildStatus
    messageMap: dict[str, Callable[[process_manager.ProcessHost, TaskMessage], None]]
    errors_: list[tuple[process_manager.ProcessHost, Task, TaskReply]]
    task_graph: list[Task]
    workers_: list[process_manager.ProcessHost]
    pending_: dict[int, Task]
    idle_: set[process_manager.ProcessHost]
    build_completed_: bool
    failed_task_message: str | None

    def __init__(self, cx: Context, builder: Builder, task_graph: list[Task], max_parallel: int) -> None: ...
    def spewResult(self, worker: process_manager.ProcessHost, task: Task | None, message: TaskReply) -> None: ...
    def recvTaskComplete(self, worker: process_manager.ProcessHost, message: TaskReply) -> None: ...
    def terminateBuild(self, status: _BuildStatus) -> None: ...
    def startWorker(self) -> None: ...
    def run(self) -> int: ...
    def onShutdown(self) -> Literal[False]: ...
    def recvSpawned(self, worker: process_manager.ProcessHost, message: TaskSpawnMessage) -> None: ...
    def issue_next_task(self, worker: process_manager.ProcessHost) -> None: ...
    def pump(self) -> None: ...
    def status(self) -> _BuildStatus: ...
    def succeeded(self) -> bool: ...

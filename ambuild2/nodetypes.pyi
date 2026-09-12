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

from typing import Any, Literal, NotRequired, TypedDict

Source: Literal['src']
Command: Literal['cmd']
Output: Literal['out']
SharedOutput: Literal['sho']
Mkdir: Literal['mkd']
Copy: Literal['cp']
Symlink: Literal['ln']
Cxx: Literal['cxx']
Rc: Literal['rc']
BinWrite: Literal['bin']

type NodeType = Literal['src', 'cmd', 'out', 'sho', 'mkd', 'cp', 'ln', 'cxx', 'rc', 'bin']
type NodeName = Literal['source', 'command', 'output', 'mkdir', 'copy', 'symlink', 'c++', 'rc']

type EnvCmds = tuple[tuple[str, ...], ...]
type ToolList = tuple[tuple[Literal['cl'], str], tuple[Literal['rc'], str], tuple[Literal['lib'], str], tuple[Literal['link'], str]]
type EnvDataTuple = tuple[tuple[str, object], ...]

class EnvDataDict(TypedDict):
    env_cmds: EnvCmds
    tools: ToolList
    props: NotRequired[tuple[tuple[str, str], ...]]

NodeNames: dict[NodeType, NodeName]

def IsFile(type: NodeType) -> bool: ...
def IsCommand(type: NodeType) -> bool: ...
def HasAutoDependencies(type: NodeType) -> bool: ...

NOT_DIRTY: Literal[0]
DIRTY: Literal[1]
ALWAYS_DIRTY: Literal[2]

type DirtyState = Literal[0, 1, 2]

class Entry:
    id: int
    type: NodeType
    path: str  # | None
    blob: Any
    folder: Entry | None
    stamp: float
    dirty: DirtyState
    tools_env: ToolsEnv | None = ...
    strong_inputs: set[Entry] | None = ...
    dynamic_inputs: set[Entry] | None = ...
    weak_inputs: set[Entry] | None = ...
    outgoing: set[Entry] | None = ...

    def __init__(self, id: int, type: NodeType, path: str | None, blob: Any | None, folder: Entry | None, stamp: float, dirty: DirtyState) -> None: ...
    def isCommand(self) -> bool: ...
    def isFile(self) -> bool: ...
    @property
    def folder_name(self) -> str | Literal['']: ...
    def format(self) -> str: ...

def combine(a: Entry | str | None, b: Entry | str) -> str: ...

class ToolsEnv:
    env_id: int
    env_data: EnvDataTuple
    env_cmds: EnvCmds | None
    tools: dict[str, str]
    props: dict[str, str]

    def __init__(self, env_id: int, env_data: EnvDataTuple) -> None: ...

def IsSameEnvData(tools_env: ToolsEnv | None, env_data: EnvDataTuple | None) -> bool: ...

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
import os
from ambuild2 import util

# Source nodes are files that are leaf inputs to the build system, and are not
# generated as part of the build process.
Source = 'src'

# Command nodes have associated data in the command table, and produce some
# kind of output.
Command = 'cmd'

# Output nodes are files that have been generated as a result of a command.
# All further node types described below are conceptually output nodes,
# but they have special handling within AMBuild.
Output = 'out'

# An output node that is modified or created by multiple commands. It cannot
# be used as an input. Shared outputs are linked separately from normal
# outputs.
SharedOutput = 'sho'

# Mkdir nodes represent a folder creation action, either explicit or
# automatically generated.
Mkdir = 'mkd'

# Copy nodes represent a file copy, from a source to a destination. They do
# not have a command counterpart.
Copy = 'cp'

# Link nodes are a special command node, representing a symlink, from a source
# to a destination. On operating systems where symlinking is not available or
# unreliable, copies may be performed instead.
Symlink = 'ln'

# C++ nodes are a builtin type that are capable of performing post-processing
# on the result of the command (for example, for dependency computation). They
# are used when using AMBuild2's automated C++ builders.
Cxx = 'cxx'

# RC nodes are similar to C++ nodes, but are specific for .rc files built with
# rc.exe on Windows.
Rc = 'rc'

# Bin nodes are a helper node. They write an embedded byte sequence directly to
# a file. They have no inputs. It is a command-like node, meaning, it has an
# attached output node.
BinWrite = 'bin'

NodeNames = {
    Source: 'source',
    Command: 'command',
    Output: 'output',
    SharedOutput: 'output',
    Mkdir: 'mkdir',
    Copy: 'copy',
    Symlink: 'symlink',
    Cxx: 'c++',
    Rc: 'rc'
}

def IsFile(type):
    return type == Output or type == Source

def IsCommand(type):
    return type != Output and type != Source

def HasAutoDependencies(type):
    return type == Cxx

NOT_DIRTY = 0
DIRTY = 1
ALWAYS_DIRTY = 2

# The basic properties of a node as it exists in the database.
class Entry(object):
    def __init__(self, id, type, path, blob, folder, stamp, dirty):
        # Unique node ID (integer)
        self.id = id

        # Node type, from above.
        self.type = type

        # For source nodes, this is an absolute path to the source file.
        # For output nodes, this is a path relative to the build folder.
        # For command nodes, it is available as an arbitrary string, which is
        # included in testing node equivalency when merging graphs.
        #
        # It is expected that when paths are not NULL, they are unique.
        self.path = path

        # Command nodes may have extra data associated with them; this is
        # usually an argv serialized by Python.
        #
        # For binary nodes, it is a dictionary containing the file name and
        # file contents.
        self.blob = blob

        # For command nodes, this is a link to a 'Mkdir' node describing its
        # working directory.
        self.folder = folder

        # Last modification time.
        self.stamp = stamp

        # See the DIRTY values above.
        self.dirty = dirty

        # If not None, a ToolsEnv that has environment information for running
        # commands.
        self.tools_env = None

        #########################################
        # Remaining fields are lazily computed. #
        #########################################

        # Strong inputs are used to force updates. Dynamic inputs force updates,
        # but are added and removed as dependencies change. Weak updates do not
        # force updates, but only ordering.
        self.strong_inputs = None
        self.dynamic_inputs = None
        self.weak_inputs = None

        self.outgoing = None

    def isCommand(self):
        return IsCommand(self.type)

    def isFile(self):
        return IsFile(self.type)

    @property
    def folder_name(self):
        if not self.folder:
            return ''
        return self.folder.path

    def format(self):
        if self.type == Source or self.type == Output or self.type == SharedOutput:
            return self.path
        text = ''
        if self.type == Mkdir:
            return 'mkdir -p ' + self.path
        if self.type == Symlink:
            return 'ln -s "{0}" "{1}"'.format(self.blob[0],
                                              os.path.join(self.folder_name, self.blob[1]))
        if self.type == Copy:
            return 'cp "{0}" "{1}"'.format(self.blob[0], os.path.join(self.folder_name,
                                                                      self.blob[1]))
        if self.type == Cxx:
            return '[' + self.blob['type'] + ']' + ' -> ' + (' '.join(
                [arg for arg in self.blob['argv']]))
        if self.type == Rc:
            return ' '.join([arg for arg in self.blob['cl_argv']]) + ' && ' + ' '.join(
                [arg for arg in self.blob['rc_argv']])
        return (' '.join([arg for arg in self.blob]))

def combine(a, b):
    if type(a) is Entry:
        text_a = a.path
    else:
        text_a = a
    if type(b) is Entry:
        text_b = b.path
    else:
        if not len(b):
            return text_a
        text_b = b
    if not text_a:
        return text_b
    return os.path.join(text_a, text_b)

# Helper class for reading env_data objects in the database. This cannot modify
# the underlying environment data.
class ToolsEnv(object):
    def __init__(self, env_id, env_data):
        self.env_id = env_id
        self.env_data = env_data  # Source of truth for equality testing.
        self.env_cmds = None
        self.tools = {}
        self.props = {}

        for name, data in env_data:
            if name == 'env_cmds':
                self.env_cmds = data
            elif name == 'tools':
                self.tools = util.BuildDictFromTuple(data)
            elif name == 'props':
                self.props = util.BuildDictFromTuple(data)

# This compares a ToolsEnv to an env_data tuple. Any other combination is not
# a legal comparison.
def IsSameEnvData(tools_env, env_data):
    if tools_env is None:
        return env_data is None
    if env_data is None:
        return tools_env is None
    if id(tools_env.env_data) == id(env_data):
        return True
    return tools_env.env_data == env_data

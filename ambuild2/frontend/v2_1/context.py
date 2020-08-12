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
import sys, copy
from ambuild2.frontend.v2_1 import tools
from ambuild2.frontend.version import Version

# AMBuild 2 scripts are parsed recursively. Each script is supplied with a
# "builder" object, which maps to a Context object. Each script gets its own
# context. The context describes the parent build file generator, the local
# input and output folders, and the global compiler that was detected in the
# root script (if any).
#
# Contexts form a tree that matches the build script hierarchy. This can be
# utilized by backends for minimal reparsing and DAG updates when build
# scripts change.

class BaseContext(object):
    def __init__(self, cm, parent, vars, script):
        super(BaseContext, self).__init__()
        self.cm = cm
        self.generator_ = cm.generator
        self.parent_ = parent
        self.script_ = script

        if parent:
            self.vars_ = copy.copy(parent.vars_)
        else:
            self.vars_ = {}

        # Merge.
        for key in vars:
            self.vars_[key] = vars[key]
        self.vars_['builder'] = self

    @property
    def parent(self):
        return self.parent_

    # Root source folder.
    @property
    def sourcePath(self):
        return self.cm.sourcePath

    @property
    def options(self):
        return self.cm.options

    @property
    def target(self):
        return self.cm.target

    @property
    def host(self):
        return self.cm.host

    @property
    def originalCwd(self):
        return self.cm.originalCwd

    @property
    def backend(self):
        return self.generator_.backend

    @property
    def buildPath(self):
        return self.cm.buildPath

    @property
    def apiVersion(self):
        return Version('2.1.1')

    def Import(self, path, vars = None):
        return self.cm.importScript(self, path, vars or {})

    def Eval(self, path, vars = None):
        return self.cm.evalScript(self, path, vars or {})

    def AddConfigureFile(self, path):
        return self.generator_.addConfigureFile(self, path)

# Access to input-oriented API.
class EmptyContext(BaseContext):
    def __init__(self, generator, parent, vars, script):
        super(EmptyContext, self).__init__(generator, parent, vars, script)

# Access to input- and output-oriented API.
class BuildContext(BaseContext):
    # Provide an accessor so users don't have to import the v2_1 namespace.
    tools = tools

    def __init__(self, cm, parent, vars, script, sourceFolder, buildFolder):
        super(BuildContext, self).__init__(cm, parent, vars, script)
        self.localFolder_ = None
        self.cxx_ = None

        if parent and parent.cxx_:
            self.cxx_ = parent.cxx_.clone()

        self.sourceFolder = sourceFolder
        self.buildFolder = buildFolder
        self.currentSourcePath = os.path.join(cm.sourcePath, sourceFolder)
        self.currentSourceFolder = sourceFolder
        self.buildFolder = buildFolder

        # Make sure everything is normalized.
        self.currentSourcePath = os.path.normpath(self.currentSourcePath)
        if self.currentSourceFolder:
            self.currentSourceFolder = os.path.normpath(self.currentSourceFolder)
        if self.buildFolder:
            self.buildFolder = os.path.normpath(self.buildFolder)

    def Build(self, path, vars = None):
        return self.cm.runBuildScript(self, path, vars or {})

    # Any consumed options will be removed from the given dictionary. Callers
    # can detect unconsumed options by inspecting the dictionary after.
    def DetectCxx(self, options = {}):
        # Only the top-level build script should be detecting compilers.
        if self.cxx_ is None and self.parent_ is None:
            self.cxx_ = self.generator_.detectCompilers(options).clone()
        return self.cxx_

    @property
    def cxx(self):
        return self.cxx_

    @property
    def ALWAYS_DIRTY(self):
        return self.cm.ALWAYS_DIRTY

    # In build systems with dependency graphs, this can return a node
    # representing buildFolder. Otherwise, it returns buildFolder.
    @property
    def localFolder(self):
        if self.localFolder_ is None:
            self.localFolder_ = self.generator_.getLocalFolder(self)
        return self.localFolder_

    def AddSource(self, source_path):
        return self.generator_.addSource(self, source_path)

    def AddSymlink(self, source, output_path):
        return self.generator_.addSymlink(self, source, output_path)

    def AddFolder(self, folder):
        return self.generator_.addFolder(self, folder)

    def AddCopy(self, source, output_path):
        return self.generator_.addCopy(self, source, output_path)

    def AddCommand(self,
                   inputs,
                   argv,
                   outputs,
                   folder = -1,
                   dep_type = None,
                   weak_inputs = [],
                   shared_outputs = [],
                   env_data = None):
        return self.generator_.addShellCommand(self,
                                               inputs,
                                               argv,
                                               outputs,
                                               folder = folder,
                                               dep_type = dep_type,
                                               weak_inputs = weak_inputs,
                                               shared_outputs = shared_outputs,
                                               env_data = env_data)

    def Context(self, name):
        return self.cm.Context(name)

    def Add(self, taskbuilder):
        taskbuilder.finish(self)
        return taskbuilder.generate(self.generator_, self)

    def SetBuildFolder(self, folder):
        # Cannot set the local build folder after it has been generated.
        if self.localFolder_ is not None:
            raise Exception("Cannot set top-level build folder twice!")

        if folder == '/' or folder == '.' or folder == './':
            self.buildFolder = ''
        else:
            self.buildFolder = os.path.normpath(folder)

# Access to everything.
class TopLevelBuildContext(BuildContext):
    def __init__(self, cm, parent, vars, script, sourceFolder, buildFolder):
        super(TopLevelBuildContext, self).__init__(cm, parent, vars, script, sourceFolder,
                                                   buildFolder)

# The root build context.
class RootBuildContext(BuildContext):
    def __init__(self, cm, vars, script):
        super(RootBuildContext, self).__init__(cm = cm,
                                               parent = None,
                                               vars = vars,
                                               script = script,
                                               sourceFolder = '',
                                               buildFolder = '')

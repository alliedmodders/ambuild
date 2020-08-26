# vim: set ts=8 sts=4 sw=4 tw=99 et:
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
import copy
import os
import sys
from ambuild2.frontend.cloneable import Cloneable
from ambuild2.frontend.cloneable import CloneableDict
from ambuild2.frontend.cloneable import CloneableList
from ambuild2.frontend.proxy import AttributeProxy
from ambuild2.frontend.v2_2 import tools
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
#
# The API does not expose Context objects directly. Instead they are given a
# Proxy, which routes any unknown getattr/hasattr calls to the Context. This
# allows users to attach new attributes, which are automatically propagated
# to child build scripts.
#
# This provides a great convenience to build configs, deprecates the need to
# use global vars, which are clunky, and allows us to make API changes without
# breaking custom attributes.

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

        self.proxy_ = AttributeProxy(self)

        # Merge.
        for key in vars:
            self.vars_[key] = vars[key]
        self.vars_['builder'] = self.proxy_

        parent_attrs = []
        parent_proxy = getattr(parent, 'proxy_', None)
        if parent_proxy:
            parent_attrs = getattr(parent_proxy, '_own_attrs', [])
        for attr in parent_attrs:
            if attr.startswith('_'):
                continue
            value = getattr(parent_proxy, attr)
            if isinstance(value, Cloneable):
                value = copy.deepcopy(value)
            setattr(self.proxy_, attr, value)

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

    def HasFeature(self, name):
        return False

    def CloneableDict(self, *args, **kwargs):
        return CloneableDict(*args, **kwargs)

    def CloneableList(self, *args, **kwargs):
        return CloneableList(*args, **kwargs)

# Access to input-oriented API.
class EmptyContext(BaseContext):
    def __init__(self, generator, parent, vars, script):
        super(EmptyContext, self).__init__(generator, parent, vars, script)

# Access to input- and output-oriented API.
class BuildContext(BaseContext):
    # Provide an accessor so users don't have to import the v2_2 namespace.
    tools = tools

    def __init__(self, cm, parent, vars, script, sourceFolder, buildFolder):
        super(BuildContext, self).__init__(cm, parent, vars, script)
        self.localFolder_ = None

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

    def DetectCxx(self, **kwargs):
        return self.generator_.detectCompilers(**kwargs)

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
        _, (entry,) = self.generator_.addSymlink(self, source, output_path)
        return entry

    def AddFolder(self, folder):
        return self.generator_.addFolder(self, folder)

    def AddCopy(self, source, output_path):
        _, (entry,) = self.generator_.addCopy(self, source, output_path)
        return entry

    def AddCommand(self,
                   inputs,
                   argv,
                   outputs,
                   folder = -1,
                   dep_type = None,
                   weak_inputs = [],
                   shared_outputs = [],
                   env_data = None):
        _, entries = self.generator_.addShellCommand(self,
                                                     inputs,
                                                     argv,
                                                     outputs,
                                                     folder = folder,
                                                     dep_type = dep_type,
                                                     weak_inputs = weak_inputs,
                                                     shared_outputs = shared_outputs,
                                                     env_data = env_data)
        return entries

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

    def ProgramProject(self, name):
        return self.generator_.newProgramProject(self, name)

    def LibraryProject(self, name):
        return self.generator_.newLibraryProject(self, name)

    def StaticLibraryProject(self, name):
        return self.generator_.newStaticLibraryProject(self, name)

    def AddOutputFile(self, path, contents):
        return self.generator_.addOutputFile(self, path, contents)

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

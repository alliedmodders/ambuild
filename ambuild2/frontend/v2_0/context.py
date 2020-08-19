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
from ambuild2 import util

# AMBuild 2 scripts are parsed recursively. Each script is supplied with a
# "builder" object, which maps to a Context object. Each script gets its own
# context. The context describes the parent build file generator, the local
# input and output folders, and the global compiler that was detected in the
# root script (if any).
#
# Contexts form a tree that matches the build script hierarchy. This can be
# utilized by backends for minimal reparsing and DAG updates when build
# scripts change.

class ConfigureException(Exception):
    def __init__(self, *args, **kwargs):
        super(ConfigureException, self).__init__(*args, **kwargs)

class Context(object):
    def __init__(self, cm, parent, script):
        self.cm = cm
        self.generator = cm.generator
        self.parent = parent
        self.script = script
        self.compiler = None

        if parent:
            self.compiler = parent.compiler.clone()

        # By default, all generated files for a build script are placed in a path
        # matching its layout in the source tree.
        path, name = os.path.split(script)
        if parent:
            self.currentSourcePath = os.path.join(parent.currentSourcePath, path)
            self.currentSourceFolder = os.path.join(parent.currentSourceFolder, path)
            self.buildFolder = os.path.join(parent.buildFolder, path)
        else:
            self.currentSourcePath = self.cm.sourcePath
            self.currentSourceFolder = ''
            self.buildFolder = ''
        self.buildScript = os.path.join(self.currentSourceFolder, name)
        self.localFolder_ = self.buildFolder

    # Root source folder.
    @property
    def sourcePath(self):
        return self.cm.sourcePath

    @property
    def options(self):
        return self.cm.options

    @property
    def buildPath(self):
        return self.cm.buildPath

    # In build systems with dependency graphs, this can return a node
    # representing buildFolder. Otherwise, it returns buildFolder.
    @property
    def localFolder(self):
        return self.generator.getLocalFolder(self)

    @property
    def target_platform(self):
        return self.cm.target_platform

    @property
    def host_platform(self):
        return self.cm.host_platform

    @property
    def originalCwd(self):
        return self.cm.originalCwd

    @property
    def backend(self):
        return self.generator.backend

    def SetBuildFolder(self, folder):
        if folder == '/' or folder == '.' or folder == './':
            self.buildFolder = ''
        else:
            self.buildFolder = os.path.normpath(folder)
        self.localFolder_ = self.buildFolder

    def DetectCompilers(self):
        if not self.compiler:
            self.compiler = self.generator.detectCompilers().clone()
        return self.compiler

    def ImportScript(self, file, vars = None):
        return self.cm.importScript(self, file, vars or {})

    def RunScript(self, file, vars = None):
        return self.cm.evalScript(file, vars or {})

    def RunBuildScripts(self, files, vars = None):
        if util.IsString(files):
            self.cm.evalScript(files, vars or {})
        else:
            for script in files:
                self.cm.evalScript(script, vars)

    def Add(self, taskbuilder):
        taskbuilder.finish(self)
        return taskbuilder.generate(self.generator, self)

    def AddSource(self, source_path):
        return self.generator.addSource(self, source_path)

    def AddSymlink(self, source, output_path):
        return self.generator.addSymlink(self, source, output_path)

    def AddFolder(self, folder):
        return self.generator.addFolder(self, folder)

    def AddCopy(self, source, output_path):
        return self.generator.addCopy(self, source, output_path)

    def AddCommand(self,
                   inputs,
                   argv,
                   outputs,
                   folder = -1,
                   dep_type = None,
                   weak_inputs = [],
                   shared_outputs = []):
        return self.generator.addShellCommand(self,
                                              inputs,
                                              argv,
                                              outputs,
                                              folder = folder,
                                              dep_type = dep_type,
                                              weak_inputs = weak_inputs,
                                              shared_outputs = shared_outputs)

    def AddConfigureFile(self, path):
        return self.generator.addConfigureFile(self, path)

    def Context(self, name):
        return self.cm.Context(name)

class AutoContext(Context):
    def __init__(self, gen, parent, file):
        super(AutoContext, self).__init__(gen, parent, file)

    def __enter__(self):
        self.cm.pushContext(self)
        return self

    def __exit__(self, type, value, traceback):
        self.cm.popContext()

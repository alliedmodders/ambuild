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
from ambuild2 import util
from ambuild2.frontend import context_manager
from ambuild2.frontend import paths
from ambuild2.frontend.system import System
from ambuild2.frontend.v2_2.context import BuildContext
from ambuild2.frontend.v2_2.context import EmptyContext
from ambuild2.frontend.v2_2.context import RootBuildContext
from ambuild2.frontend.v2_2.context import TopLevelBuildContext
from ambuild2.frontend.version import Version

class ConfigureException(Exception):
    def __init__(self, *args, **kwargs):
        super(ConfigureException, self).__init__(*args, **kwargs)

class ContextManager(context_manager.ContextManager):
    def __init__(self, sourcePath, buildPath, originalCwd, options, args):
        super(ContextManager, self).__init__(sourcePath, buildPath, originalCwd, options, args)

        # Detect the target architecture.
        self.host = System.Host

    @property
    def apiVersion(self):
        return Version('2.2')

    def parseBuildScripts(self):
        root = os.path.join(self.sourcePath, 'AMBuildScript')
        self.generator.addConfigureFile(None, root)

        cx = RootBuildContext(self, {}, root)
        self.execContext(cx)

    def importScript(self, context, path, vars = None):
        if not isinstance(path, util.StringType()):
            for item in path:
                self.importScriptImpl(context, item, vars or {})
            return None
        return self.importScriptImpl(context, path, vars or {})

    def evalScript(self, context, path, vars = None):
        obj = self.importScriptImpl(context, path, vars or {})
        return getattr(obj, 'rvalue', None)

    def runBuildScript(self, context, path, vars = None):
        if not isinstance(path, util.StringType()):
            for item in path:
                self.runBuildScriptImpl(context, item, vars or {})
            return None
        return self.runBuildScriptImpl(context, path, vars or {})

    def importScriptImpl(self, parent, path, vars):
        assert isinstance(path, util.StringType())

        sourceFolder, _, scriptFile = self.computeScriptPaths(parent, path)

        # Get the absolute script path.
        scriptPath = os.path.join(self.sourcePath, scriptFile)
        self.addConfigureFile(parent, scriptPath)

        # Make the new context.
        cx = EmptyContext(self, parent, vars, scriptPath)
        scriptGlobals = self.execContext(cx)

        # Only return variables that changed.
        obj = util.Expando()
        for key in scriptGlobals:
            if (not key in cx.vars_) or (scriptGlobals[key] is not cx.vars_[key]):
                setattr(obj, key, scriptGlobals[key])
        return obj

    def runBuildScriptImpl(self, parent, path, vars):
        assert isinstance(path, util.StringType())

        if parent is not self.contextStack_[-1]:
            raise Exception('Can only create child build contexts of the currently active context')

        sourceFolder, buildFolder, scriptFile = self.computeScriptPaths(parent, path)

        # Get the absolute script path.
        scriptPath = os.path.join(self.sourcePath, scriptFile)
        self.generator.addConfigureFile(parent, scriptPath)

        # Make the new context. We allow top-level contexts in the root build
        # and otherwise for absolute paths.
        if isinstance(parent, RootBuildContext) or \
           (isinstance(parent, TopLevelBuildContext) and path.startswith('/')):
            constructor = TopLevelBuildContext
        else:
            if not paths.IsSubPath(sourceFolder, parent.sourceFolder):
                raise Exception("Nested build contexts must be within the same folder structure")
            constructor = BuildContext

        cx = constructor(cm = self,
                         parent = parent,
                         vars = vars,
                         script = scriptPath,
                         sourceFolder = sourceFolder,
                         buildFolder = buildFolder)

        scriptGlobals = self.execContext(cx)
        return scriptGlobals.get('rvalue', None)

    def execContext(self, context):
        code = self.compileScript(context.script_)

        # Copy vars so changes don't get inherited.
        scriptGlobals = copy.copy(context.vars_)

        self.pushContext(context)
        try:
            exec(code, scriptGlobals)
        except:
            self.popContext()
            raise
        self.popContext()

        return scriptGlobals

    def computeScriptPaths(self, parent, target):
        # By default, all generated files for a build script are placed in a path
        # matching its layout in the source tree.
        path, name = os.path.split(target)
        if parent:
            if path.startswith('/'):
                # Navigate relative to the source root.
                path = path.lstrip('/')

                base_folder = ''
                build_base = ''
            else:
                # Navigate based on our relative folder.
                base_folder = parent.currentSourceFolder
                build_base = parent.buildFolder

            sourceFolder = os.path.join(base_folder, path)
            buildFolder = os.path.join(build_base, path)
        else:
            sourceFolder = ''
            buildFolder = ''

        return sourceFolder, buildFolder, os.path.join(sourceFolder, name)

    def getLocalFolder(self, context):
        return context.buildFolder

    def copyCompilerVars(self, vars, compiler):
        for prop_name in compiler.vendor.extra_props:
            key = '{0}_{1}'.format(compiler.vendor.name, prop_name)
            vars[key] = compiler.vendor.extra_props[prop_name]

    def createGenerator(self, name):
        if name == 'ambuild2':
            # Different name, because pip, impressively, does not delete caches for old files, and
            # and this causes the old "amb2" directory to linger and create import problems!
            from ambuild2.frontend.v2_2.amb2_gen import Generator
            self.generator = Generator(self)
        elif name == 'vs':
            from ambuild2.frontend.v2_2.vs.gen import Generator
            self.generator = Generator(self)
        else:
            super(ContextManager, self).createGenerator(name)

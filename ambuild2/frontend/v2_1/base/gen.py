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
from ambuild2.frontend import paths
from ambuild2.frontend.system import System
from ambuild2.frontend.v2_1.base.context import \
    TopLevelBuildContext, \
    BuildContext, \
    EmptyContext, \
    RootBuildContext

class ConfigureException(Exception):
    def __init__(self, *args, **kwargs):
        super(ConfigureException, self).__init__(*args, **kwargs)

class BaseGenerator(object):
    def __init__(self, sourcePath, buildPath, originalCwd, options, args):
        super(BaseGenerator, self).__init__()
        self.sourcePath = sourcePath
        self.buildPath = os.path.normpath(buildPath)
        self.originalCwd = originalCwd
        self.options = options
        self.args = args
        self.contextStack_ = []
        self.configure_failed = False

        # Detect the target architecture.
        self.host = System.Host
        self.target = System.Host

        # Override the target architecture.
        new_arch = getattr(self.options, 'target_arch', None)
        if new_arch is not None:
            self.target = System(self.target.platform, util.NormalizeArchString(new_arch))

    def parseBuildScripts(self):
        root = os.path.join(self.sourcePath, 'AMBuildScript')
        self.addConfigureFile(None, root)

        cx = RootBuildContext(self, {}, root)
        self.execContext(cx)

    def pushContext(self, cx):
        self.contextStack_.append(cx)

    def popContext(self):
        self.contextStack_.pop()

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
        self.addConfigureFile(parent, scriptPath)

        # Make the new context. We allow top-level contexts in the root build
        # and otherwise for absolute paths.
        if isinstance(parent, RootBuildContext) or \
           (isinstance(parent, TopLevelBuildContext) and path.startswith('/')):
            constructor = TopLevelBuildContext
        else:
            if not paths.IsSubPath(sourceFolder, parent.sourceFolder):
                raise Exception("Nested build contexts must be within the same folder structure")
            constructor = BuildContext

        cx = constructor(generator = self,
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

    def compileScript(self, path):
        with open(path) as fp:
            chars = fp.read()

            # Python 2.6 can't compile() with Windows line endings?!?!!?
            chars = chars.replace('\r\n', '\n')
            chars = chars.replace('\r', '\n')

            return compile(chars, path, 'exec')

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

    def generateBuildFiles(self):
        build_py = os.path.join(self.buildPath, 'build.py')
        with open(build_py, 'w') as fp:
            fp.write("""
#!{exe}
# vim set: ts=8 sts=2 sw=2 tw=99 et:
import sys
from ambuild2 import run

if not run.CompatBuild(r"{build}"):
  sys.exit(1)
""".format(exe = sys.executable, build = self.buildPath))

        with open(os.path.join(self.buildPath, 'Makefile'), 'w') as fp:
            fp.write("""
all:
	"{exe}" "{py}"
""".format(exe = sys.executable, py = build_py))

    def generate(self):
        self.preGenerate()
        self.parseBuildScripts()
        self.postGenerate()
        if self.options.make_scripts:
            self.generateBuildFiles()
        return True

    def getLocalFolder(self, context):
        return context.buildFolder

    @property
    def backend(self):
        raise Exception('Must be implemented!')

    def addSymlink(self, context, source, output_path):
        raise Exception('Must be implemented!')

    def addFolder(self, context, folder):
        raise Exception('Must be implemented!')

    def addCopy(self, context, source, output_path):
        raise Exception('Must be implemented!')

    def addShellCommand(self,
                        context,
                        inputs,
                        argv,
                        outputs,
                        folder = -1,
                        dep_type = None,
                        weak_inputs = [],
                        shared_outputs = [],
                        env_data = None):
        raise Exception('Must be implemented!')

    def addConfigureFile(self, context, path):
        raise Exception('Must be implemented!')

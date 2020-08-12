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

class ContextManager(object):
    def __init__(self, sourcePath, buildPath, originalCwd, options, args):
        super(ContextManager, self).__init__()
        self.sourcePath = sourcePath
        self.buildPath = os.path.normpath(buildPath)
        self.originalCwd = originalCwd
        self.options = options
        self.args = args
        self.configure_failed = False
        self.contextStack_ = []
        self.generator = None
        self.db = None
        self.refactoring = False

    # Nonce.
    ALWAYS_DIRTY = object()

    @property
    def apiVersion(self):
        raise Exception('Implement me!')

    def setBackend(self, backend):
        self.backend_ = backend

    def pushContext(self, cx):
        self.contextStack_.append(cx)

    def popContext(self):
        self.contextStack_.pop()

    def compileScript(self, path):
        with open(path) as fp:
            chars = fp.read()

            # Python 2.6 can't compile() with Windows line endings?!?!!?
            chars = chars.replace('\r\n', '\n')
            chars = chars.replace('\r', '\n')

            return compile(chars, path, 'exec')

    def Context(self, name):
        return AutoContext(self, self.contextStack_[-1], name)

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

    def createGenerator(self, name):
        sys.stderr.write('Unrecognized build generator: {}\n'.format(name))
        sys.exit(1)

    # name is None when a generator is already set.
    def generate(self, name = None):
        if self.generator is None:
            self.createGenerator(name)
        self.generator.preGenerate()
        self.parseBuildScripts()
        self.generator.postGenerate()
        if self.options.make_scripts:
            self.generateBuildFiles()
        return True

    @property
    def backend(self):
        return self.backend_.backend()

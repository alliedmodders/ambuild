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
from ambuild2.frontend import context_manager
from ambuild2.frontend.v2_0.context import AutoContext
from ambuild2.frontend.v2_0.context import Context
from ambuild2.frontend.version import Version

class ContextManager(context_manager.ContextManager):
    def __init__(self, sourcePath, buildPath, originalCwd, options, args):
        super(ContextManager, self).__init__(sourcePath, buildPath, originalCwd, options, args)
        self.contextStack_.append(None)

        # This is a hack... if we ever do cross-compiling or something, we'll have
        # to change this.
        self.host_platform = util.Platform()
        self.target_platform = util.Platform()

    @property
    def apiVersion(self):
        return Version('2.0')

    def parseBuildScripts(self):
        root = os.path.join(self.sourcePath, 'AMBuildScript')
        self.evalScript(root)

    def importScript(self, context, file, vars = None):
        path = os.path.normpath(os.path.join(context.sourcePath, file))
        self.addConfigureFile(context, path)

        new_vars = copy.copy(vars or {})
        new_vars['builder'] = context

        code = self.compileScript(path)
        exec(code, new_vars)

        obj = util.Expando()
        for key in new_vars:
            setattr(obj, key, new_vars[key])
        return obj

    def Context(self, name):
        return AutoContext(self, self.contextStack_[-1], name)

    def evalScript(self, file, vars = None):
        file = os.path.normpath(file)

        cx = Context(self, self.contextStack_[-1], file)
        self.pushContext(cx)

        full_path = os.path.join(self.sourcePath, cx.buildScript)

        self.generator.addConfigureFile(cx, full_path)

        new_vars = copy.copy(vars or {})
        new_vars['builder'] = cx

        # Run it.
        rvalue = None
        code = self.compileScript(full_path)

        exec(code, new_vars)

        if 'rvalue' in new_vars:
            rvalue = new_vars['rvalue']
            del new_vars['rvalue']

        self.popContext()
        return rvalue

    def getLocalFolder(self, context):
        return context.localFolder_

    def createGenerator(self, name):
        if name == 'vs':
            from ambuild2.frontend.v2_0.vs.gen import Generator
            self.generator = Generator(self)
        elif name == 'ambuild2':
            from ambuild2.frontend.v2_0.amb2_gen import Generator
            self.generator = Generator(self)
        else:
            return super(ContextManager, self).createGenerator(name)

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
import os
from ambuild2 import nodetypes
from ambuild2 import util
from ambuild2.frontend import amb2_gen
from ambuild2.frontend.v2_0.cpp import detect

class Generator(amb2_gen.Generator):
    def __init__(self, cm):
        super(Generator, self).__init__(cm)
        self.compiler = None

    def copyBuildVars(self, vars):
        if not self.compiler:
            return

        # Save any environment variables that are relevant to the build.
        compilers = [
            ('cc', self.compiler.cc),
            ('cxx', self.compiler.cxx),
        ]
        for prefix, comp in compilers:
            for prop_name in comp.extra_props:
                key = '{0}_{1}'.format(prefix, prop_name)
                vars[key] = comp.extra_props[prop_name]

    def detectCompilers(self):
        if not self.compiler:
            with util.FolderChanger(self.cacheFolder):
                self.base_compiler = detect.DetectCxx(os.environ, self.cm.options)
                self.compiler = self.base_compiler.clone()

        return self.compiler

    def addCxxObjTask(self, cx, shared_outputs, folder, obj):
        cxxData = {'argv': obj.argv, 'type': obj.behavior}
        _, (cxxNode,) = self.addCommand(context = cx,
                                        weak_inputs = obj.sourcedeps,
                                        inputs = [obj.inputObj],
                                        outputs = [obj.outputFile],
                                        node_type = nodetypes.Cxx,
                                        folder = folder,
                                        data = cxxData,
                                        shared_outputs = shared_outputs,
                                        env_data = obj.env_data)
        return cxxNode

    def addCxxRcTask(self, cx, folder, obj):
        rcData = {
            'cl_argv': obj.cl_argv,
            'rc_argv': obj.rc_argv,
        }
        _, (_, rcNode) = self.addCommand(context = cx,
                                         weak_inputs = obj.sourcedeps,
                                         inputs = [obj.inputObj],
                                         outputs = [obj.preprocFile, obj.outputFile],
                                         node_type = nodetypes.Rc,
                                         folder = folder,
                                         data = rcData,
                                         env_data = obj.env_data)
        return rcNode

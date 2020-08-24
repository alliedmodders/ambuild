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
from ambuild2.frontend.v2_1.cpp import detect

class Generator(amb2_gen.Generator):
    def __init__(self, cm):
        super(Generator, self).__init__(cm)
        self.compiler = None

    def detectCompilers(self, options):
        if options is None:
            options = {}
        if not self.compiler:
            with util.FolderChanger(self.cacheFolder):
                self.base_compiler = detect.AutoDetectCxx(self.cm.target, self.cm.options, options)
                if self.base_compiler is None:
                    raise Exception('Could not detect a suitable C/C++ compiler')
                self.compiler = self.base_compiler.clone()

        return self.compiler

    def copyBuildVars(self, vars):
        if not self.compiler:
            return
        for prop_name in self.compiler.vendor.extra_props:
            key = '{0}_{1}'.format(self.compiler.vendor.name, prop_name)
            vars[key] = self.compiler.vendor.extra_props[prop_name]

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

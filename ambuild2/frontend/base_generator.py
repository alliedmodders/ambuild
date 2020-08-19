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
class BaseGenerator(object):
    def __init__(self, cm):
        self.cm = cm

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

    # The following methods are only needed to implement v2.2 generators.
    def newProgramProject(self, context, name):
        raise NotImplementedError()

    def newLibraryProject(self, context, name):
        raise NotImplementedError()

    def newStaticLibraryProject(self, context, name):
        raise NotImplementedError()

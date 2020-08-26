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
import os, errno
import uuid as uuids
from ambuild2 import util
from ambuild2 import nodetypes
from ambuild2.frontend import paths
from ambuild2.frontend.vs import nodes
from ambuild2.frontend.base_generator import BaseGenerator

SupportedVersions = ['10', '11', '12', '14', '15', '16']
YearMap = {
    '2010': 10,
    '2012': 11,
    '2013': 12,
    '2015': 14,
    '2017': 15,
    '2019': 16,
}

class Generator(BaseGenerator):
    def __init__(self, cm):
        super(Generator, self).__init__(cm)
        self.compiler = None
        self.vs_version = None
        self.files_ = {}
        self.projects_ = set()

        if self.cm.options.vs_version in SupportedVersions:
            self.vs_version = int(self.cm.options.vs_version)
        else:
            if self.cm.options.vs_version not in YearMap:
                util.con_err(
                    util.ConsoleRed,
                    'Unsupported Visual Studio version: {0}'.format(self.cm.options.vs_version),
                    util.ConsoleNormal)
                raise Exception('Unsupported Visual Studio version: {0}'.format(
                    self.cm.options.vs_version))
            self.vs_version = YearMap[self.cm.options.vs_version]

        self.cacheFile = os.path.join(self.cm.buildPath, '.cache')
        try:
            with open(self.cacheFile, 'rb') as fp:
                self.vars_ = util.pickle.load(fp)
        except:
            self.vars_ = {}

        if 'uuids' not in self.vars_:
            self.vars_['uuids'] = {}

        self.target_platform = 'windows'

    # Overridden.
    @property
    def backend(self):
        return 'vs'

    # Overridden.
    def preGenerate(self):
        pass

    # Overriden.
    def postGenerate(self):
        self.generateProjects()
        with open(self.cacheFile, 'wb') as fp:
            util.DiskPickle(self.vars_, fp)

    def generateProjects(self):
        for node in self.projects_:
            # We cache uuids across runs to keep them consistent.
            node.uuid = self.vars_['uuids'].get(node.path)
            if node.uuid is None:
                node.uuid = str(uuids.uuid1()).upper()
                self.vars_['uuids'][node.path] = node.uuid
            node.project.export(self.cm, node)

    # Overridden.
    #
    # We don't support reconfiguring in this frontend.
    def addConfigureFile(self, cx, path):
        pass

    def detectCompilers(self):
        raise Exception('Implement me!')

    # Overridden.
    def enterContext(self, cx):
        cx.vs_nodes = []

    # Overridden.
    def leaveContext(self, cx):
        pass

    def ensureUnique(self, path):
        if path in self.files_:
            entry = self.files_[path]
            util.con_err(util.ConsoleRed,
                         'Path {0} already exists as: {1}'.format(path,
                                                                  entry.kind), util.ConsoleNormal)
            raise Exception('Path {0} already exists as: {1}'.format(path, entry.kind))

    # Overridden.
    def getLocalFolder(self, context):
        if type(context.localFolder_) is nodes.FolderNode or context.localFolder_ is None:
            return context.localFolder_

        if not len(context.buildFolder):
            context.localFolder_ = None
        else:
            context.localFolder_ = self.addFolder(context.parent, context.buildFolder)

        return context.localFolder_

    # Overridden.
    def addFolder(self, cx, folder):
        parentFolderNode = None
        if cx is not None:
            parentFolderNode = cx.localFolder

        _, path = paths.ResolveFolder(parentFolderNode, folder)
        if path in self.files_:
            entry = self.files_[path]
            if type(entry) is not nodes.FolderNode:
                self.ensureUnique(path)  # Will always throw.
            return entry

        try:
            os.makedirs(path)
        except OSError as exn:
            if not (exn.errno == errno.EEXIST and os.path.isdir(path)):
                raise

        obj = nodes.FolderNode(path)
        self.files_[path] = obj
        return obj

    # Overridden.
    def addShellCommand(self,
                        context,
                        inputs,
                        argv,
                        outputs,
                        folder = -1,
                        dep_type = None,
                        weak_inputs = None,
                        shared_outputs = None):
        print(inputs, argv, outputs, folder, dep_type, weak_inputs, shared_outputs)

    def addOutput(self, context, path, parent):
        self.ensureUnique(path)

        node = nodes.OutputNode(context, path, parent)
        self.files_[path] = node
        return node

    def addProjectNode(self, context, project):
        self.ensureUnique(project.path)
        self.projects_.add(project)
        self.files_[project.path] = project

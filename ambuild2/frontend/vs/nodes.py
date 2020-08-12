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

class Node(object):
    def __init__(self, context, path):
        super(Node, self).__init__()
        self.context = context
        self.path = path
        self.children = set()
        self.parents = set()

    def addParent(self, parent):
        self.parents.add(parent)
        parent.children.add(self)

class FolderNode(Node):
    def __init__(self, path):
        super(FolderNode, self).__init__(None, path)

    @property
    def kind(self):
        return 'folder'

class ContainerNode(Node):
    def __init__(self, cx):
        super(ContainerNode, self).__init__(cx, None)

    @property
    def kind(self):
        return 'container'

class OutputNode(Node):
    def __init__(self, context, path, parent):
        super(OutputNode, self).__init__(context, path)
        self.addParent(parent)

    @property
    def kind(self):
        return 'output'

class ProjectNode(Node):
    def __init__(self, context, path, project):
        super(ProjectNode, self).__init__(context, path)
        self.project = project
        self.uuid = None

    @property
    def kind(self):
        return 'project'

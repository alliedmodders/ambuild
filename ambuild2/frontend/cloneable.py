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
import collections
import copy

# An object inheriting from Cloneable will be automatically shallow-copied
# when constructing child build contexts. Use copy.deepcopy to clone.
class Cloneable(object):
    def __init__(self):
        pass

class CloneableDict(collections.OrderedDict, Cloneable):
    def __init__(self, *args, **kwargs):
        super(CloneableDict, self).__init__(*args, **kwargs)

class CloneableList(list, Cloneable):
    def __init__(self, *args, **kwargs):
        super(CloneableList, self).__init__(*args, **kwargs)

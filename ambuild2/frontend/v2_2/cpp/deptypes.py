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

class CppNodes(object):
    def __init__(self, output, debug_outputs, type, target):
        self.binary = output
        self.debug = debug_outputs
        self.type = type
        self.target = target

class PchNodes(object):
    def __init__(self, folder, header_file, pch_file, object_file, source_type):
        self.folder = folder
        self.header_file = header_file
        self.pch_file = pch_file
        self.object_file = object_file
        self.source_type = source_type

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
from ambuild2 import util

# Given an optional contextual folder and a folder path, compute the full
# relative path, erroring if it's outside the build folder.
#
# The parent folder and resolved folder are returned as a tuple.
def ResolveFolder(parent, folder):
    parent_path = ''
    if parent:
        parent_path = parent.path
    path = os.path.normpath(os.path.join(parent_path, folder))

    if path.startswith('..'):
        util.con_err(util.ConsoleRed, 'Output path ', util.ConsoleBlue, path, util.ConsoleRed,
                     ' is outside the build folder!', util.ConsoleNormal)
        raise Exception('Cannot generate folders outside the build folder')

    return parent_path, path

def Join(*nodes):
    paths = []
    for node in nodes:
        if node is None:
            continue
        if util.IsString(node):
            paths.append(node)
        else:
            paths.append(node.path)
    return os.path.join(*paths)

def IsSubPath(other, folder, path_module = os.path):
    other = path_module.abspath(other)
    folder = path_module.abspath(folder)

    drive1, _ = path_module.splitdrive(other)
    drive2, _ = path_module.splitdrive(folder)
    if drive1 != drive2:
        return False

    relative = path_module.relpath(other, folder)
    if relative.startswith(
            os.pardir
    ):  # Short-circuit on '..' -OR- '../', this is always pointing outside of "folder".
        return False
    elif relative.startswith(
            os.curdir):  # Short-circuit on '.' -OR- './', this is always pointing to a child item.
        return True

    return other.startswith(folder)  # In most cases, we shouldn't ever arrive to this point.

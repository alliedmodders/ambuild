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
from ambuild2 import util

class Version(util.Orderable):
  def __init__(self, string):
    super(Version, self).__init__()
    if type(string) is int:
      self.string = str(string)
      self.components = [string]
    else:
      self.string = string
      self.components = Version.split(string)

  def __str__(self):
    return self.string

  @staticmethod
  def split(string):
    return [int(part) for part in string.split('.')]

  def __cmp__(self, other):
    if hasattr(other, 'components'):
      components = other.components
    elif type(other) is int:
      components = [other]
    else:
      components = Version.split(str(other))

    return util.compare(self.components, components)

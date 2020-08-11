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

class Version(object):
    def __init__(self, string):
        super(Version, self).__init__()
        if type(string) is int:
            self.string = str(string)
            self.vendor_name = None
            self.components = [string]
        else:
            self.string = string
            self.vendor_name, self.components = Version.split(string)

    def __str__(self):
        return self.string

    @staticmethod
    def split(string):
        vendor_pos = string.rfind('-')
        if vendor_pos != -1:
            vendor_name = string[:vendor_pos]
            version = string[vendor_pos + 1:]
        else:
            vendor_name = None
            version = string
        return vendor_name, [int(part) for part in version.split('.')]

    def __eq__(self, other):
        result = self.cmp_base(other)
        return result is not None and result == 0

    def __ne__(self, other):
        result = self.cmp_base(other)
        return result is None or result != 0

    def __le__(self, other):
        result = self.cmp_base(other)
        return result is not None and result <= 0

    def __lt__(self, other):
        result = self.cmp_base(other)
        return result is not None and result < 0

    def __gt__(self, other):
        result = self.cmp_base(other)
        return result is not None and result > 0

    def __ge__(self, other):
        result = self.cmp_base(other)
        return result is not None and result >= 0

    @staticmethod
    def parse(other):
        if hasattr(other, 'components'):
            components = other.components
            return getattr(other, 'vendor', None), other.components
        if type(other) is int:
            components = [other]
            return None, components
        return Version.split(str(other))

    def cmp_base(self, other):
        vendor_name, components = Version.parse(other)

        # If this version or the other version doesn't care about the vendor name,
        # then return an ok comparison for compatibility. Otherwise, the vendor
        # names must match.
        if vendor_name is not None and self.vendor_name is not None:
            if vendor_name != self.vendor_name:
                return None
        return util.compare(self.components, components)

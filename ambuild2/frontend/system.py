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
from ambuild2 import util

class System(object):
    def __init__(self, platform, arch, subarch = '', abi = ''):
        super(System, self).__init__()
        self.platform_ = platform
        self.arch_ = arch
        self.subarch_ = subarch
        self.abi_ = abi

    @property
    def platform(self):
        return self.platform_

    @property
    def arch(self):
        return self.arch_

    @property
    def subarch(self):
        return self.subarch_

    @property
    def abi(self):
        return self.abi_

    @property
    def triple(self):
        suffix = ''
        if self.abi:
            suffix += '-' + self.abi
        return '{}-{}{}{}'.format(self.platform, self.arch, self.subarch, suffix)

System.Host = System(util.Platform(), util.Architecture, util.SubArch, util.DetectHostAbi())

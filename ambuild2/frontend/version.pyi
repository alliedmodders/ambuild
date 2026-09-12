# vim: set ts=8 sts=4 sw=4 tw=99 et:
#
# This file is part of AMBuild.
#
# AMBuild is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# at your option any later version.
#
# AMBuild is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with AMBuild. If not, see <http://www.gnu.org/licenses/>.

class Version:
    string: str
    vendor_name: str | None
    components: list[int]

    def __init__(self, string: str) -> None: ...
    @staticmethod
    def split(string: str) -> tuple[str | None, list[int]]: ...
    def __eq__(self, other: object | Version | str | int) -> bool: ...
    def __ne__(self, other: object | Version | str | int) -> bool: ...
    def __le__(self, other: Version | str | int) -> bool: ...
    def __lt__(self, other: Version | str | int) -> bool: ...
    def __gt__(self, other: Version | str | int) -> bool: ...
    def __ge__(self, other: Version | str | int) -> bool: ...
    @staticmethod
    def parse(other: object | Version | str | int) -> tuple[str | None, list[int]]: ...
    def cmp_base(self, other: object | Version | str | int) -> int: ...

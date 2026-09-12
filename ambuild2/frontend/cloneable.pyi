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

import collections
from collections.abc import Iterable, Mapping
from typing import Any

class Cloneable:
    def __init__(self) -> None: ...

class CloneableDict[KT, VT](collections.OrderedDict[KT, VT], Cloneable):
    def __init__(self, *args: Mapping[KT, VT] | Iterable[tuple[KT, VT]], **kwargs: VT) -> None: ...

class CloneableList[T](list[T], Cloneable):
    def __init__(self, *args: Iterable[T], **kwargs: Any) -> None: ...

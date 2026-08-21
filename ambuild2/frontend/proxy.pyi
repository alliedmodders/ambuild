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

from collections.abc import Callable, Hashable
from typing import Any

from ambuild2.frontend.v2_2.context import BaseContext
from ambuild2.util import Expando

class AttributeProxy:
    _wrapped_obj: BaseContext
    _own_attrs: set[str]

    def __init__(self, wrapped_obj: BaseContext) -> None: ...
    def __getattr__(self, name: str) -> Expando | Callable[..., Hashable]: ...
    def __setattr__(self, name: str, value: Any) -> None: ...
    def __dir__(self) -> list[str]: ...

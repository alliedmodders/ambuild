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

# AttributeProxy objects will appear to have all the attributes of an inner
# object, as well as their own attributes. Locally set attributes will
# override wrapped ones. This is basically how JavaScript prototype-based
# inheritance works.
class AttributeProxy(object):
    def __init__(self, wrapped_obj):
        self._wrapped_obj = wrapped_obj
        self._own_attrs = set()

    def __getattr__(self, name):
        return getattr(self._wrapped_obj, name)

    def __setattr__(self, name, value):
        if name in ['_own_attrs_', '_wrapped_obj']:
            return object.__setattr__(self, name, value)

        own_attrs = getattr(self, '_own_attrs', None)
        if own_attrs is not None:
            own_attrs.add(name)
        return object.__setattr__(self, name, value)

    def __dir__(self):
        me = set(dir(super(AttributeProxy, self))) | set(self.__dict__.keys())
        wrapped = set(dir(self._wrapped_obj))
        return sorted(list(me | wrapped))

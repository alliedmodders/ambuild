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
import copy

DEFAULT_RULES = {
    'family==gcc': {
        'arch==x86': {
            'CFLAGS': ['-m32'],
            'platform==mac': {
                'CFLAGS': ['-arch', 'i386'],
            },
        },
        'arch==x86_64': {
            'CFLAGS': ['-m64'],
            'platform==mac': {
                'CFLAGS': ['-arch', 'x86_64'],
            },
        },
    },
}

class RulesParser(object):
    def __init__(self):
        self.rules = copy.deepcopy(DEFAULT_RULES)
        self.inputs_ = None
        self.props_ = None

    def parse(self, inputs):
        self.inputs_ = inputs
        self.props_ = {}
        for key, value in self.rules.items():
            self.parse_property(key, value)
        return self.props_

    def parse_property(self, key, value):
        if isinstance(value, dict):
            self.parse_section(key, value)
        else:
            self.add_prop(key, value)

    def add_prop(self, key, value):
        if key not in self.props_:
            self.props_[key] = value
            return
        if isinstance(value, list):
            self.props_[key].extend(value)
        else:
            self.props_[key] = value

    def parse_section(self, key, value):
        if '==' in key:
            op = lambda x, y: x == y
            parts = key.split('==')
        elif '!=' in key:
            op = lambda x, y: x != y
            parts = key.split('!=')
        else:
            raise Exception('Subsections must have an == or != operator')

        parts = [part.strip() for part in parts]
        if len(parts) != 2 or not len(parts[0]) or not len(parts[1]):
            raise Exception('Invalid operator or multiple operators, expected two components')

        if parts[0] not in self.inputs_:
            raise Exception('Unknown rule variable "{}"'.format(parts[0]))
        if not op(self.inputs_[parts[0]], parts[1]):
            return

        for sub_key, sub_value in sorted(value.items()):
            self.parse_property(sub_key, sub_value)

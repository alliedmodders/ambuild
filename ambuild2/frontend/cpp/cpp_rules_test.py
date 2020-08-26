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
import unittest
from ambuild2.frontend.cpp.cpp_rules import RulesParser

TestRules = {
    'family==gcc': {
        'arch==x86': {
            'CFLAGS': ['-m32'],
            'platform==mac': {
                'CFLAGS': ['-arch', 'i386'],
            },
        },
        'arch==x86_64': {
            'CFLAGS': ['-m64'],
        },
    }
}

class IsSubPathTests(unittest.TestCase):
    def runTest(self):
        rp = RulesParser()
        rp.rules = TestRules
        props = rp.parse({
            'family': 'gcc',
            'arch': 'x86_64',
        })
        self.assertIn('CFLAGS', props)
        self.assertEquals(props['CFLAGS'], ['-m64'])

        props = rp.parse({
            'family': 'msvc',
            'arch': 'x86_64',
        })
        self.assertEquals(props, {})

        props = rp.parse({
            'family': 'gcc',
            'arch': 'x86',
            'platform': 'mac',
        })
        self.assertIn('CFLAGS', props)
        self.assertEquals(props['CFLAGS'], ['-m32', '-arch', 'i386'])

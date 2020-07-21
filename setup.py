#!/usr/bin/env python
# vim: set ts=2 sw=2 tw=99 et: 
import sys
from distutils.core import setup

try:
  import sqlite3
except:
  raise Exception('py-sqlite3 must be installed')

scripts = [
  'scripts/ambuild'
]

if sys.platform == 'win32':
  scripts.append('scripts/ambuild.bat')
elif sys.platform == 'darwin':
  scripts.append('scripts/ambuild_dsymutil_wrapper.sh')
else:
  scripts.append('scripts/ambuild_objcopy_wrapper.sh')

setup(
  name = 'AMBuild',
  version = '2.0',
  description = 'AlliedModders Build System',
  author = 'David Anderson',
  author_email = 'dvander@alliedmods.net',
  url = 'http://www.alliedmods.net/ambuild',
  packages = [
    'ambuild',
    'ambuild2',
    'ambuild2.frontend',
    'ambuild2.ipc',
    'ambuild2.frontend.v2_0',
    'ambuild2.frontend.v2_0.amb2',
    'ambuild2.frontend.v2_0.base',
    'ambuild2.frontend.v2_0.cpp',
    'ambuild2.frontend.v2_0.vs',
    'ambuild2.frontend.v2_1',
    'ambuild2.frontend.v2_1.amb2',
    'ambuild2.frontend.v2_1.base',
    'ambuild2.frontend.v2_1.cpp',
    'ambuild2.frontend.v2_1.vs',
    'ambuild2.frontend.v2_1.tools',
  ],
  scripts = scripts
)


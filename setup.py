#!/usr/bin/env python
# vim: set ts=2 sw=2 tw=99 et: 
import sys
from setuptools import setup, find_packages

try:
  import sqlite3
except:
  raise SystemError('py-sqlite3 must be installed')
  
amb_scripts = []
if sys.platform != 'win32':
  if sys.platform == 'darwin':
    amb_scripts.append('scripts/ambuild_dsymutil_wrapper.sh')
  else:
    amb_scripts.append('scripts/ambuild_objcopy_wrapper.sh')

setup(
  name = 'AMBuild',
  version = '2.0',
  description = 'AlliedModders Build System',
  author = 'David Anderson',
  author_email = 'dvander@alliedmods.net',
  url = 'http://www.alliedmods.net/ambuild',
  packages = find_packages(),
  entry_points = {
    'console_scripts': [
      'ambuild = ambuild2.run:cli_run'
    ]
  },
  scripts=amb_scripts
)

#!/usr/bin/env python
# vim: set ts=2 sw=2 tw=99 et: 

from distutils.core import setup

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
    'ambuild2.frontend.amb2'
  ]
)



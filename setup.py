#!/usr/bin/env python
# vim: set ts=2 sw=2 tw=99 et: 
import multiprocessing as mp
import os
import sys
from setuptools import setup, find_packages

try:
  import sqlite3
except:
  raise SystemError('py-sqlite3 must be installed')

def child_main():
  import sys
  sys.path.pop(0)
  try:
    import ambuild2.util
  except:
    sys.exit(2)
  if getattr(ambuild2.util, 'INSTALLED_BY_PIP_OR_SETUPTOOLS', False):
    sys.exit(1)
  sys.exit(0)

proc = mp.Process(target = child_main)
proc.start()
proc.join()

if not proc.exitcode:
  sys.stderr.write("You have a previous installation of AMBuild. AMBuild must\n")
  sys.stderr.write("now be installed by pip (see README.md). To prevent\n")
  sys.stderr.write("conflicts, please remove the old distutils install. You can\n")
  sys.stderr.write("do this by inspecting the following locations and removing\n")
  sys.stderr.write("any ambuild folders:\n\n")
  for path in sys.path[1:]:
    candidates = [ os.path.join(path, "ambuild"), os.path.join(path, "ambuild2") ]
    found = False
    for candidate in candidates:
      if os.path.exists(candidate):
        found = True
        break
    if found:
      sys.stderr.write("\t" + path + "\n")
  sys.stderr.write("\nAborting installation.\n")
  sys.stderr.flush()
  sys.exit(1)
  
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
  scripts=amb_scripts,
  zip_safe=False
)


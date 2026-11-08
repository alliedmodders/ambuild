# vim: set sts=2 ts=8 sw=2 tw=99 et:
API_VERSION = '2.2'

import os
import shlex
import sys
try:
    from ambuild2 import run
    if not run.HasAPI(API_VERSION):
        raise Exception()
except:
    sys.stderr.write('AMBuild {0} must be installed to build this project.\n'.format(API_VERSION))
    sys.stderr.write('http://www.alliedmods.net/ambuild\n')
    sys.exit(1)

# Run C and C++ compiles through launcher.py, which defines a macro that the
# sources check for.
def launcher_command(lang):
    argv = [sys.executable, os.path.join(sys.path[0], 'launcher.py'), lang]
    return ' '.join(shlex.quote(arg.replace('\\', '/')) for arg in argv)

os.environ['CC_LAUNCHER'] = launcher_command('C')
os.environ['CXX_LAUNCHER'] = launcher_command('CXX')

builder = run.BuildParser(sourcePath = sys.path[0], api = API_VERSION)
builder.Configure()

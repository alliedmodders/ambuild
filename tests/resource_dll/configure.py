# vim: set sts=2 ts=8 sw=2 tw=99 et:
API_VERSION = '2.1.1'

import sys
try:
    from ambuild2 import run
    if not run.HasAPI(API_VERSION):
        raise Exception()
except:
    sys.stderr.write('AMBuild {0} must be installed to build this project.\n'.format(API_VERSION))
    sys.stderr.write('http://www.alliedmods.net/ambuild\n')
    sys.exit(1)

builder = run.BuildParser(sourcePath = sys.path[0], api = API_VERSION)
builder.Configure()

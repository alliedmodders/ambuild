# vim: set sts=2 ts=8 sw=2 tw=99 et:
import sys
from ambuild2 import run

builder = run.BuildParser(sourcePath = sys.path[0], api = '2.1')
builder.Configure()

# vim: set sts=2 ts=8 sw=2 tw=99 et:
import sys
from ambuild2 import run

builder = run.PrepareBuild(sourcePath = sys.path[0])
builder.Configure()

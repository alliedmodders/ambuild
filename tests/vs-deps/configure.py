# vim: set ts=8 sts=2 tw=99 et ft=python:
import sys
from ambuild2 import run

parser = run.BuildParser(sourcePath = sys.path[0], api = '2.2')
parser.Configure()

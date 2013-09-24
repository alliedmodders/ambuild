# vim: set ts=8 sts=2 sw=2 tw=99 et:
from __future__ import print_function
import util
import os, sys
from prep import Preparer
from context import Context
from optparse import OptionParser

def Build(sourcePath, buildPath):
  with Context(sourcePath=sourcePath, buildPath=buildPath) as cx:
    return cx.Build()

def PrepareBuild(sourcePath, buildPath=None):
  if buildPath == None:
    buildPath = os.path.abspath(os.getcwd())
  return Preparer(sourcePath=sourcePath, buildPath=buildPath)

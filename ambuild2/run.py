# vim: set ts=8 sts=2 sw=2 tw=99 et:
#
# This file is part of AMBuild.
# 
# AMBuild is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# AMBuild is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with AMBuild. If not, see <http://www.gnu.org/licenses/>.
from __future__ import print_function
import os, sys
from optparse import OptionParser
from ambuild2 import util
from ambuild2.frontend.prep import Preparer
from ambuild2.context import Context

def Build(buildPath):
  with util.FolderChanger(buildPath):
    with Context(buildPath=buildPath) as cx:
      return cx.Build()

def PrepareBuild(sourcePath, buildPath=None):
  if buildPath == None:
    buildPath = os.path.abspath(os.getcwd())
  return Preparer(sourcePath=sourcePath, buildPath=buildPath)

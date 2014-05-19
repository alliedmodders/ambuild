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
import os
from ambuild2 import util
from ambuild2.frontend.version import Version
from ambuild2.frontend.cpp import compilers

class CompilerShell(object):
  def __init__(self, version):
    self.version = version
    self.behavior = 'msvc'
    self.name = 'msvc'

class Compiler(compilers.Compiler):
  def __init__(self, version):
    super(Compiler, self).__init__()

    self.version = version

    # For compatibility with older build scripts.
    self.cc = CompilerShell(version)
    self.cxx = CompilerShell(version)

  def clone(self):
    cc = Compiler(self.version)
    cc.inherit(self)
    return cc

  @staticmethod
  def GetVersionFromVS(vs_version):
    return Version((vs_version * 100) + 600)

  def Library(self, name):
    return Library(self, name)

  def StaticLibrary(self, name):
    return StaticLibrary(self, name)

class BinaryBuilder(object):
  def __init__(self, compiler, name):
    super(BinaryBuilder, self).__init__()
    self.compiler = compiler.clone()
    self.name = name

  def generate(self, generator, cx):
    pass

  def Dep(self, text, node=None): 
    return Dep(text, node)

  def finish(self, cx):
    pass

class Library(BinaryBuilder):
  def __init__(self, compiler, name):
    super(Library, self).__init__(compiler, name)
    self.sources = []

  @property
  def outputFile(self):
    return '{0}.dll'.format(self.name)

class StaticLibrary(BinaryBuilder):
  def __init__(self, compiler, name):
    super(StaticLibrary, self).__init__(compiler, name)
    self.sources = []

  @property
  def outputFile(self):
    return '{0}.lib'.format(self.name)

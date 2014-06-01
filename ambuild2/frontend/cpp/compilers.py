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
import copy
from ambuild2.frontend.cpp import builders

# Base compiler object.
class Compiler(object):
  EnvVars = ['CFLAGS', 'CXXFLAGS', 'CC', 'CXX']

  attrs = [
    'includes',         # C and C++ include paths
    'cxxincludes',      # C++-only include paths
    'cflags',           # C and C++ compiler flags
    'cxxflags',         # C++-only compiler flags
    'defines',          # C and C++ #defines
    'cxxdefines',       # C++-only #defines

    'rcdefines',        # Resource Compiler (RC) defines

    # Link flags. If any members are not strings, they will be interpreted as
    # Dep entries created from BinaryBuilder.
    'linkflags',

    # An array of objects to link, after all link flags have been specified.
    # Entries may either be strings containing a path, or Dep entries created
    # from BinaryBuilder.
    'postlink',

    # An array of nodes which should be weak dependencies on each source
    # compilation command.
    'sourcedeps',
  ]

  def __init__(self, options = None):
    if getattr(options, 'symbol_files', False):
      self.debuginfo = 'separate'
    else:
      self.debuginfo = 'bundled'
    for attr in self.attrs:
      setattr(self, attr, [])

  def inherit(self, other):
    self.debuginfo = other.debuginfo
    for attr in self.attrs:
      setattr(self, attr, copy.copy(getattr(other, attr)))

  def clone(self):
    raise Exception('Must be implemented!')

  def like(self, name):
    raise Exception('Must be implemented!')

  @property
  def vendor(self):
    raise Exception('Must be implemented!')

  @property
  def version(self):
    raise Exception('Must be implemented!')

  def Program(self, name):
    raise Exception('Must be implemented!')

  def Library(self, name):
    raise Exception('Must be implemented!')

  def StaticLibrary(self, name):
    raise Exception('Must be implemented!')

  @staticmethod
  def Dep(text, node=None):
    return builders.Dep(text, node)

class CxxCompiler(Compiler):
  def __init__(self, cc, cxx, options = None):
    super(CxxCompiler, self).__init__(options)

    # Accesssing these attributes through the API is deprecated.
    self.cc = cc
    self.cxx = cxx

  def clone(self):
    cc = CxxCompiler(self.cc, self.cxx)
    cc.inherit(self)
    return cc

  def Program(self, name):
    return builders.Program(self.clone(), name)

  def Library(self, name):
    return builders.Library(self.clone(), name)

  def StaticLibrary(self, name):
    return builders.StaticLibrary(self.clone(), name)

  def ProgramProject(self, name):
    return builders.Project(builders.Program, self.clone(), name)

  def LibraryProject(self, name):
    return builders.Project(builders.Library, self.clone(), name)

  def StaticLibraryProject(self, name):
    return builders.Project(builders.StaticLibrary, self.clone(), name)

  # These functions use |cxx|, because we expect the vendors to be the same
  # across |cc| and |cxx|.

  # Returns whether this compiler acts like another compiler. Available names
  # are: msvc, gcc, icc, sun, clang
  def like(self, name):
    return self.cxx.like(name)

  # Returns the vendor name (msvc, gcc, icc, sun, clang)
  @property
  def vendor(self):
    return self.cxx.name

  # Returns the version of the compiler. The return value is an object that
  # can be compared against other versions, for example:
  #
  #  compiler.version >= '4.8.3'
  #
  @property
  def version(self):
    return self.cxx.versionObject

  # Returns a list containing the program name and arguments used to invoke the compiler.
  @property
  def argv(self):
    return self.cxx.command.split(' ')


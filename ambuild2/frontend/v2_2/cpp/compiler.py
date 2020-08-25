# vim: set ts=8 sts=4 sw=4 tw=99 et:
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
import subprocess
import sys
from ambuild2 import util
from ambuild2.frontend.cloneable import Cloneable
from ambuild2.frontend.v2_2.cpp import builders

# Base compiler object.
class Compiler(Cloneable):
    attrs_ = [
        'includes',  # C and C++ include paths
        'cxxincludes',  # C++-only include paths
        'cflags',  # C and C++ compiler flags
        'cxxflags',  # C++-only compiler flags
        'defines',  # C and C++ #defines
        'cxxdefines',  # C++-only #defines
        'c_only_flags',  # Flags for C but not C++.
        'rcdefines',  # Resource Compiler (RC) defines

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

        # An array of nodes which should be weak dependencies on each linker
        # command.
        'weaklinkdeps',
    ]

    def __init__(self, vendor, target, options = None):
        self.vendor = vendor
        self.target = target
        for attr in self.attrs_:
            setattr(self, attr, [])
        if getattr(options, 'symbol_files', False):
            self.symbol_files = 'separate'
        else:
            self.symbol_files = 'bundled'

    def inherit(self, other):
        for attr in self.attrs_:
            setattr(self, attr, copy.copy(getattr(other, attr)))

        self.symbol_files_ = other.symbol_files_

    def clone(self):
        raise Exception('Must be implemented!')

    # Returns whether this compiler acts like another compiler. Current responses
    # are:
    #
    #    msvc:        msvc
    #    gcc:         gcc
    #    clang:       gcc, clang
    #    apple-clang: gcc, clang, apple-clang
    #    sun:         sun
    #
    def like(self, name):
        return self.vendor.like(name)

    # Returns the meta family the compiler belongs to. The meta family is the
    # most generic compiler that this compiler aims to emulate.
    # Responses are one of: msvc, gcc, sun
    @property
    def behavior(self):
        return self.vendor.behavior

    # Returns the family the compiler belongs to.
    # Responses are one of: msvc, gcc, clang, sun
    @property
    def family(self):
        return self.vendor.family

    # Returns a version object representing the compiler. The version is
    # prefixed by the compiler name.
    @property
    def version(self):
        return self.vendor.version

    # Returns how symbol files are generated, either 'bundled' or 'separate'.
    @property
    def symbol_files(self):
        return self.symbol_files_

    # Sets how symbol files are generated. Must be 'bundled' or 'separate'.
    # Default is 'bundled' if the underlying compiler supports it. If the vendor
    # does not support the requested symbol file type, the value remains
    # unchanged.
    @symbol_files.setter
    def symbol_files(self, value):
        if value not in ['bundled', 'separate']:
            raise Exception("Symbol files value must be 'bundled' or 'separate'")
        self.symbol_files_ = self.vendor.parseDebugInfoType(value)

    def Program(self, name):
        raise Exception('Must be implemented!')

    def Library(self, name):
        raise Exception('Must be implemented!')

    def StaticLibrary(self, name):
        raise Exception('Must be implemented!')

    def PrecompiledHeaders(self, name, source_type):
        raise Exception('Must be implemented')

    @staticmethod
    def Dep(text, node = None):
        return builders.Dep(text, node)

class CliCompiler(Compiler):
    def __init__(self, vendor, target, cc_argv, cxx_argv, options = None, env_data = None):
        super(CliCompiler, self).__init__(vendor, target, options)
        self.cc_argv = cc_argv
        self.cxx_argv = cxx_argv
        self.found_pkg_config_ = False
        self.env_data = env_data

    def clone(self):
        cc = CliCompiler(self.vendor, self.target, self.cc_argv, self.cxx_argv)
        cc.inherit(self)
        return cc

    def inherit(self, other):
        super(CliCompiler, self).inherit(other)
        self.env_data = other.env_data

    def __deepcopy__(self, memo):
        return self.clone()

    def Program(self, name):
        return builders.Program(self.clone(), name)

    def Library(self, name):
        return builders.Library(self.clone(), name)

    def StaticLibrary(self, name):
        return builders.StaticLibrary(self.clone(), name)

    def PrecompiledHeaders(self, name, source_type):
        return builders.PrecompiledHeaders(self.clone(), name, source_type)

    @staticmethod
    def run_pkg_config(argv):
        output = subprocess.check_output(args = ['pkg-config'] + argv)
        output = util.DecodeConsoleText(sys.stdout, output)
        return [item.strip() for item in output.strip().split(' ') if item.strip() != '']

    # Helper for running pkg-config.
    def pkg_config(self, pkg, link = 'dynamic'):
        if not self.found_pkg_config_:
            try:
                self.run_pkg_config(['--version'])
                self.found_pkg_config = True
            except:
                raise Exception('failed to find pkg-config!')

        for include in self.run_pkg_config(['--cflags-only-I', pkg]):
            if include.startswith('-I'):
                self.includes += [include[2:].strip()]
            else:
                self.cflags += [include]
        self.cflags += self.run_pkg_config(['--cflags-only-other', pkg])

        if link == 'dynamic':
            self.linkflags += self.run_pkg_config(['--libs', pkg])
        elif link == 'static':
            self.linkflags += self.run_pkg_config(['--libs', '--static', pkg])

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
import util
import subprocess
import re, os, copy

class Vendor(object):
  def __init__(self, name, version, behavior, command, objSuffix):
    self.name = name
    self.version = version
    self.behavior = behavior
    self.command = command
    self.objSuffix = objSuffix

class MSVC(Vendor):
  def __init__(self, command, version):
    super(MSVC, self).__init__('msvc', version, 'msvc', command, '.obj')
    self.definePrefix = '/D'

  def formatInclude(self, outputPath, includePath):
    #Hack - try and get a relative path because CL, with either 
    #/Zi or /ZI, combined with subprocess, apparently tries and
    #looks for paths like c:\bleh\"c:\bleh" <-- wtf
    #.. this according to Process Monitor
    outputPath = os.path.normcase(outputPath)
    includePath = os.path.normcase(includePath)
    outputDrive = os.path.splitdrive(outputPath)[0]
    includeDrive = os.path.splitdrive(includePath)[0]
    if outputDrive == includeDrive:
      return ['/I', os.path.relpath(includePath, outputPath)]
    return ['/I', includePath]

  def objectArgs(self, sourceFile, objFile):
    return ['/showIncludes', '/c', sourceFile, '/Fo' + objFile]

class CompatGCC(Vendor):
  def __init__(self, name, command, version):
    super(CompatGCC, self).__init__(name, version, 'gcc', command, '.o')
    parts = version.split('.')
    self.majorVersion = int(parts[0])
    self.minorVersion = int(parts[1])
    self.definePrefix = '-D'

  def formatInclude(self, outputPath, includePath):
    return ['-I', os.path.normpath(includePath)]

  def objectArgs(self, sourceFile, objFile):
    return ['-H', '-c', sourceFile, '-o', objFile]

class GCC(CompatGCC):
  def __init__(self, command, version):
    super(GCC, self).__init__('gcc', command, version)

class Clang(CompatGCC):
  def __init__(self, command, version):
    super(Clang, self).__init__('clang', command, version)

def TryVerifyCompiler(cx, env, mode, cmd):
  if util.IsWindows():
    cc = VerifyCompiler(cx, env, mode, cmd, 'msvc')
    if cc:
      return cc
  return VerifyCompiler(cx, env, mode, cmd, 'gcc')

CompilerSearch = {
  'CC': {
    'mac': ['cc', 'clang', 'gcc', 'icc'],
    'windows': ['cl'],
    'default': ['cc', 'gcc', 'clang', 'icc']
    },
  'CXX': {
    'mac': ['c++', 'clang++', 'g++', 'icc'],
    'windows': ['cl'],
    'default': ['c++', 'g++', 'clang++', 'icc']
  }
}

def DetectCompiler(cx, env, var):
  if var in env:
    trys = [env[var]]
  else:
    if util.Platform() in CompilerSearch[var]:
      trys = CompilerSearch[var][util.Platform()]
    else:
      trys = CompilerSearch[var]['default']
  for i in trys:
    cc = TryVerifyCompiler(cx, env, var, i)
    if cc:
      return cc
  raise Exception('Unable to find a suitable ' + var + ' compiler')

def VerifyCompiler(cx, env, mode, cmd, vendor):
  args = cmd.split(' ')
  if 'CXXFLAGS' in env:
    args.extend(env['CXXFLAGS'])
  if 'CFLAGS' in env:
    args.extend(env['CFLAGS'])
  if mode == 'CXX' and 'CXXFLAGS' in env:
    args.extend(env['CXXFLAGS'])
  if mode == 'CXX':
    filename = 'test.cpp'
  else:
    filename = 'test.c'
  file = open(filename, 'w')
  file.write("""
#include <stdio.h>
#include <stdlib.h>

int main()
{
#if defined __ICC
  printf("icc %d\\n", __ICC);
#elif defined __clang__
# if defined(__clang_major__) && defined(__clang_minor__)
  printf("clang %d.%d\\n", __clang_major__, __clang_minor__);
# else
  printf("clang 1.%d\\n", __GNUC_MINOR__);
# endif
#elif defined __GNUC__
  printf("gcc %d.%d\\n", __GNUC__, __GNUC_MINOR__);
#elif defined _MSC_VER
  printf("msvc %d\\n", _MSC_VER);
#elif defined __TenDRA__
  printf("tendra 0\\n");
#else
#error "Unrecognized compiler!"
#endif
#if defined __cplusplus
  printf("CXX\\n");
#else
  printf("CC\\n");
#endif
  exit(0);
}
""")
  file.close()
  if mode == 'CC':
    executable = 'test' + util.ExecutableSuffix()
  elif mode == 'CXX':
    executable = 'testp' + util.ExecutableSuffix()

  # Make sure the exe is gone.
  if os.path.exists(executable):
    os.unlink(executable)

  if vendor == 'gcc' and mode == 'CXX':
    args.extend(['-fno-exceptions', '-fno-rtti'])
  args.extend([filename, '-o', executable])
  print('Checking {0} compiler (vendor test {1})... '.format(mode, vendor), end = '')
  print(args)
  p = util.CreateProcess(args)
  if p == None:
    print('not found')
    return False
  if util.WaitForProcess(p) != 0:
    print('failed with return code {0}'.format(p.returncode))
    return False

  exe = util.MakePath('.', executable)
  p = util.CreateProcess([executable], executable = exe)
  if p == None:
    print('failed to create executable')
    return False
  if util.WaitForProcess(p) != 0:
    print('executable failed with return code {0}'.format(p.returncode))
    return False
  lines = p.stdoutText.splitlines()
  if len(lines) != 2:
    print('invalid executable output')
    return False
  if lines[1] != mode:
    print('requested {0} compiler, found {1}'.format(mode, lines[1]))
    return False

  vendor, version = lines[0].split(' ')
  if vendor == 'gcc':
    v = GCC(cmd, version)
  elif vendor == 'clang':
    v = Clang(cmd, version)
  elif vendor == 'msvc':
    v = MSVC(cmd, version)
  else:
    print('Unknown vendor {0}'.format(vendor))
    return False

  print('found {0} version {1}'.format(vendor, version))
  return v

class Compiler(object):
  attrs = ['includes', 'cxxincludes', 'linkflags', 'cflags', 'cxxflags', 'defines', 'cxxdefines']

  def __init__(self, cc, cxx):
    self.cc = cc
    self.cxx = cxx
    for attr in Compiler.attrs:
      setattr(self, attr, [])

  def clone(self):
    cc = Compiler(self.cc, self.cxx)
    cc.cc = self.cc
    cc.cxx = self.cxx
    for attr in Compiler.attrs:
      setattr(self, attr, copy.copy(getattr(cc, attr)))
    return cc

  def Program(self, name):
    return Program(self, name)

  def Library(self, name):
    return Library(self, name)

# Environment representing a C/C++ compiler invocation. Encapsulates most
# arguments.
class CCommandEnv(object):
  def __init__(self, outputPath, config, compiler):
    args = compiler.command.split(' ')
    args += config.cflags
    if compiler == config.cxx:
      args += config.cxxflags
    args += [compiler.definePrefix + define for define in config.defines]
    if compiler == config.cxx:
      args += [compiler.definePrefix + define for define in config.cxxdefines]
    for include in config.includes:
      args += compiler.formatInclude(outputPath, include)
    if compiler == config.cxx:
      for include in config.cxxincludes:
        args += compiler.formatInclude(outputPath, include)
    self.argv_ = args
    self.compiler = compiler

  def argv(self, sourceFile, objPath):
    return self.argv_ + self.compiler.objectArgs(sourceFile, objPath)

def NameForObjectFile(file):
  return re.sub('[^a-zA-Z0-9_]+', '_', os.path.splitext(file)[0]);

class ObjectFile(object):
  def __init__(self, sourceFile, outputFile, argv):
    self.sourceFile = sourceFile
    self.outputFile = outputFile
    self.argv = argv

class BinaryBuilder(object):
  def __init__(self, compiler, name):
    super(BinaryBuilder, self).__init__()
    self.compiler = compiler.clone()
    self.name = name
    self.sources = []
    self.used_cxx = False
    self.linker = None

  def generate(self, generator, cx):
    generator.addCxxTasks(cx, self)

  def finish(self, cx):
    # Because we want to compute relative include folders for MSVC (see its
    # vendor object), we need to compute an absolute path to the build folder.
    self.outputFolder = os.path.join(cx.buildFolder, self.name)
    self.outputPath = os.path.join(cx.buildPath, self.outputFolder)
    self.default_c_env = CCommandEnv(self.outputPath, self.compiler, self.compiler.cc)
    self.default_cxx_env = CCommandEnv(self.outputPath, self.compiler, self.compiler.cxx)

    self.objfiles = [self.generateItem(cx, item) for item in self.sources]

    if not self.linker:
      if self.used_cxx:
        self.linker = self.compiler.cxx
      else:
        self.linker = self.compiler.cc

    argv = self.linker.command.split(' ')
    for objfile in self.objfiles:
      folder, name = os.path.split(objfile.outputFile)
      argv.append(name)

    name, argv = self.generateBinary(cx, argv)
    self.outputFile = os.path.join(self.outputFolder, name)
    self.argv = argv

  def generateItem(self, cx, item):
    fparts = os.path.splitext(item)

    if fparts[1] == 'c':
      cenv = self.default_c_env
    else:
      cenv = self.default_cxx_env
      self.used_cxx = True

    # Find or add node for the source input file.
    sourceFile = os.path.join(cx.sourcePath, item)
    objName = NameForObjectFile(fparts[0]) + cenv.compiler.objSuffix
    argv = cenv.argv(sourceFile, objName)
    objectFile = os.path.join(self.outputFolder, objName)
    return ObjectFile(sourceFile, objectFile, argv)

class Program(BinaryBuilder):
  def __init__(self, compiler, name):
    super(Program, self).__init__(compiler, name)

  def generateBinary(self, cx, argv):
    name = self.name + util.ExecutableSuffix()

    if isinstance(self.linker, MSVC):
      argv.append('/link')
    argv.extend(self.compiler.linkflags)
    if isinstance(self.linker, MSVC):
      argv.append('/OUT:' + name)
      argv.append('/PDB:"' + self.name + '.pdb"')
    else:
      argv.extend(['-o', name])

    return name, argv

class Library(BinaryBuilder):
  def __init__(self, compiler, name):
    super(Library, self).__init__(compiler, name)

  def generateBinary(self, cx, argv):
    name = self.name + util.SharedLibSuffix()

    argv.extend(self.compiler.linkflags)
    if isinstance(self.linker, MSVC):
      argv.append('/OUT:' + name)
      argv.append('/DLL')
      argv.append('/PDB:"' + self.name + '.pdb"')
    elif isinstance(self.linker, CompatGCC):
      if util.IsMac():
        argv.append('-dynamiclib')
      else:
        argv.append('-shared')

    return name, argv

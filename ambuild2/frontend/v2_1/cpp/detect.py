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
import os, re
import tempfile
import subprocess
from ambuild2 import util
from ambuild2.frontend.v2_1.cpp import vendor, compiler
from ambuild2.frontend.v2_1.cpp.msvc import MSVC
from ambuild2.frontend.v2_1.cpp.gcc import GCC, Clang
from ambuild2.frontend.v2_1.cpp.sunpro import SunPro

class CommandAndVendor(object):
  def __init__(self, argv, vendor):
    self.argv = argv
    self.vendor = vendor
    self.arch = None

def FindCompiler(env, mode, cmd):
  if util.IsWindows():
    result = TryVerifyCompiler(env, mode, cmd, 'msvc')
    if result is not None:
      return result
  return TryVerifyCompiler(env, mode, cmd, 'gcc')

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

def DetectCxx(target, env, options):
  cc = DetectCxxCompiler(env, 'CC')
  cxx = DetectCxxCompiler(env, 'CXX')

  # Ensure that the two compilers have the same vendor.
  if not cxx.vendor.equals(cc.vendor):
    message = 'C and C++ compiler are different: CC={0}, CXX={1}'
    message = message.format(cc.vendor, cxx.vendor)

    util.con_err(util.ConsoleRed, message, util.ConsoleNormal)
    raise Exception(message)

  if cxx.arch != cc.arch:
    message = "C architecture {0} does not match C++ architecture {1}".format(cc.arch, cxx.arch)
    util.con_err(util.ConsoleRed, message, util.ConsoleNormal)
    raise Exception(message)

  # :TODO: Check that the arch is == to target. We don't do this yet since
  # on Windows we can't use platform.architecture().

  return compiler.CliCompiler(cxx.vendor, cc.argv, cxx.argv, options)

def DetectCxxCompiler(env, var):
  if var in env:
    trys = [env[var]]
  else:
    if util.Platform() in CompilerSearch[var]:
      trys = CompilerSearch[var][util.Platform()]
    else:
      trys = CompilerSearch[var]['default']
  for i in trys:
    result = FindCompiler(env, var, i)
    if result is not None:
      return result

  raise Exception('Unable to find a suitable ' + var + ' compiler')

def TryVerifyCompiler(env, mode, cmd, assumed_family):
  try:
    return VerifyCompiler(env, mode, cmd, assumed_family)
  except Exception as e:
    util.con_out(
      util.ConsoleHeader,
      'Compiler {0} for {1} failed: '.format(cmd, mode),
      util.ConsoleRed,
      e.message,
      util.ConsoleNormal
    )
    return None

def VerifyCompiler(env, mode, cmd, assumed_family):
  argv = cmd.split()
  if 'CFLAGS' in env:
    argv.extend(env['CFLAGS'].split())
  if mode == 'CXX' and 'CXXFLAGS' in env:
    argv.extend(env['CXXFLAGS'].split())
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
#  if defined(__apple_build_version__)
    printf("apple-clang %d.%d\\n", __clang_major__, __clang_minor__);
#  else   
    printf("clang %d.%d\\n", __clang_major__, __clang_minor__);
#  endif
# else
  printf("clang 1.%d\\n", __GNUC_MINOR__);
# endif
#elif defined __GNUC__
  printf("gcc %d.%d\\n", __GNUC__, __GNUC_MINOR__);
#elif defined _MSC_VER
  printf("msvc %d\\n", _MSC_VER);
#elif defined __TenDRA__
  printf("tendra 0\\n");
#elif defined __SUNPRO_C
  printf("sun %x\\n", __SUNPRO_C);
#elif defined __SUNPRO_CC
  printf("sun %x\\n", __SUNPRO_CC);
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
    executable = 'test' + util.ExecutableSuffix
  elif mode == 'CXX':
    executable = 'testp' + util.ExecutableSuffix

  # Make sure the exe is gone.
  if os.path.exists(executable):
    os.unlink(executable)

  argv.extend([filename, '-o', executable])

  # For MSVC, we need to detect the inclusion pattern for foreign-language
  # systems.
  if assumed_family == 'msvc':
    argv += ['-nologo', '-showIncludes']

  util.con_out(
    util.ConsoleHeader,
    'Checking {0} compiler (vendor test {1})... '.format(mode, assumed_family),
    util.ConsoleBlue,
    '{0}'.format(argv),
    util.ConsoleNormal
  )
  p = util.CreateProcess(argv)
  if p == None:
    raise Exception('compiler not found')
  if util.WaitForProcess(p) != 0:
    raise Exception('compiler failed with return code {0}'.format(p.returncode))

  inclusion_pattern = None
  if assumed_family == 'msvc':
    inclusion_pattern = MSVC.DetectInclusionPattern(p.stdoutText)

  exe = util.MakePath('.', executable)
  p = util.CreateProcess([executable], executable = exe)
  if p == None:
    raise Exception('failed to create executable with {0}'.format(cmd))
  if util.WaitForProcess(p) != 0:
    raise Exception('executable failed with return code {0}'.format(p.returncode))
  lines = p.stdoutText.splitlines()
  if len(lines) != 2:
    raise Exception('invalid executable output')
  if lines[1] != mode:
    raise Exception('requested {0} compiler, found {1}'.format(mode, lines[1]))

  vendor, version = lines[0].split(' ')
  if vendor == 'gcc':
    v = GCC(version)
  elif vendor == 'apple-clang':
    v = Clang(version, 'apple')
  elif vendor == 'clang':
    v = Clang(version)
  elif vendor == 'msvc':
    v = MSVC(version)
  elif vendor == 'sun':
    v = SunPro(version)
  else:
    raise Exception('Unknown vendor {0}'.format(vendor))

  if inclusion_pattern is not None:
    v.extra_props['inclusion_pattern'] = inclusion_pattern

  util.con_out(
    util.ConsoleHeader,
    'found {0} version {1}'.format(vendor, version),
    util.ConsoleNormal
  )
  return CommandAndVendor(cmd.split(), v)

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
import os
import re
import shlex
import subprocess
import tempfile
from ambuild2 import util
from ambuild2.frontend.cpp import msvc_utils
from ambuild2.frontend.v2_1.cpp import vendor, compiler
from ambuild2.frontend.v2_1.cpp.gcc import GCC, Clang, Emscripten
from ambuild2.frontend.v2_1.cpp.msvc import MSVC
from ambuild2.frontend.v2_1.cpp.sunpro import SunPro

class CommandAndVendor(object):
    def __init__(self, argv, vendor):
        self.argv = argv
        self.vendor = vendor
        self.arch = None

class CompilerNotFoundException(Exception):
    def __init__(self, message):
        super(CompilerNotFoundException, self).__init__(message)

kClangTuple = ('clang', 'clang++', 'gcc')
kGccTuple = ('gcc', 'g++', 'gcc')
kIntelTuple = ('icc', 'icc', 'gcc')
kMsvcTuple = ('cl', 'cl', 'msvc')

def FindToolsInEnv(env, tools):
    found = {}
    paths = env.get('PATH', '').split(';')
    for path in paths:
        for tool in tools:
            if tool in found:
                continue
            candidate = os.path.join(path, tool)
            if os.path.exists(candidate):
                found[tool] = candidate
        if len(found) == len(tools):
            return found, True
    return found, False

def AutoDetectCxx(target, gen_options, detect_options):
    locator = CompilerLocator(target, gen_options, detect_options)
    return locator.detect()

class CompilerLocator(object):
    def __init__(self, target, gen_options, detect_options):
        self.target_ = target
        self.gen_options_ = gen_options
        self.detect_options_ = detect_options

    def detect(self):
        if 'CC' in os.environ or 'CXX' in os.environ:
            return self.detect_from_env()

        if util.Platform() == 'windows':
            compiler = self.detect_msvc()
            if compiler:
                return compiler

        return self.find_default_compiler()

    def detect_from_env(self):
        if 'CC' not in os.environ:
            raise Exception('CXX set in environment, but not CC')
        if 'CXX' not in os.environ:
            raise Exception('CC set in environment, but not CXX')

        cc = self.find_compiler(os.environ, 'CC', os.environ['CC'])
        if cc is None:
            raise CompilerNotFoundException('Unable to find a suitable C compiler')

        cxx = self.find_compiler(os.environ, 'CXX', os.environ['CXX'])
        if cxx is None:
            raise CompilerNotFoundException('Unable to find a suitable C++ compiler')

        return self.create_cli(cc, cxx)

    def create_cli(self, cc, cxx):
        # Ensure that the two compilers have the same vendor.
        if not cxx.vendor.equals(cc.vendor):
            message = 'C and C++ compiler are different: CC={0}, CXX={1}'
            message = message.format(cc.vendor, cxx.vendor)

            util.con_err(util.ConsoleRed, message, util.ConsoleNormal)
            raise Exception(message)

        if cxx.arch != cc.arch:
            message = "C architecture {0} does not match C++ architecture {1}".format(
                cc.arch, cxx.arch)
            util.con_err(util.ConsoleRed, message, util.ConsoleNormal)
            raise Exception(message)

        return compiler.CliCompiler(cxx.vendor, cc.argv, cxx.argv, self.gen_options_)

    def detect_msvc(self):
        # If the caller has already configured the environment, we'll expect it to
        # be always configured for us in the future.
        _, has_cl = FindToolsInEnv(os.environ, ['cl.exe'])
        if has_cl:
            return self.find_default_compiler()

        force_msvc = self.detect_options_.pop('force_msvc_version', None)

        installs = msvc_utils.MSVCFinder().find_all()
        for install in installs:
            if force_msvc and install.version != force_msvc:
                continue
            if self.target_.arch not in install.vcvars:
                continue

            compiler = self.try_msvc_install(install)
            if compiler is not None:
                return compiler

        raise CompilerNotFoundException('Unable to find a suitable C/C++ compiler')

    def try_msvc_install(self, install):
        bat_file = install.vcvars[self.target_.arch]
        try:
            env_cmds = msvc_utils.DeduceEnv(bat_file, [])
            env = util.BuildEnv(env_cmds)
        except:
            util.con_err(util.ConsoleRed, "Could not run or analyze {}".format(bat_file),
                         util.ConsoleNormal)
            return None

        necessary_tools = ['cl.exe', 'rc.exe', 'lib.exe']
        tools, _ = FindToolsInEnv(env, necessary_tools)
        for tool in necessary_tools:
            if tool not in tools:
                util.con_err(util.ConsoleRed, "Could not find {} for {}".format(tool, bat_file))
                return None

        cc, _ = self.run_compiler(env, 'CC', 'cl', 'msvc', abs_path = tools['cl.exe'])
        if not cc:
            return None
        cxx, _ = self.run_compiler(env, 'CXX', 'cl', 'msvc', abs_path = tools['cl.exe'])
        if not cxx:
            return None

        # We use tuples here so the data is hashable without going through Pickle.
        tool_list = (
            ('cl', tools['cl.exe']),
            ('rc', tools['rc.exe']),
            ('lib', tools['lib.exe']),
        )
        env_data = (
            ('env_cmds', env_cmds),
            ('tools', tool_list),
        )
        return compiler.CliCompiler(cxx.vendor,
                                    cc.argv,
                                    cxx.argv,
                                    options = self.gen_options_,
                                    env_data = env_data)

    def find_default_compiler(self):
        candidates = []
        if util.Platform() == 'windows':
            candidates.append(kMsvcTuple)
        candidates.extend([kClangTuple, kGccTuple, kIntelTuple])

        for cc_cmd, cxx_cmd, cc_family in candidates:
            cc = self.find_compiler(os.environ, 'CC', cc_cmd, cc_family)
            if cc is None:
                continue
            cxx = self.find_compiler(os.environ, 'CXX', cxx_cmd, cc_family)
            if cxx is not None:
                return self.create_cli(cc, cxx)

        raise CompilerNotFoundException('Unable to find a suitable C/C++ compiler')

    def find_compiler(self, env, mode, cmd, cc_family = None):
        families = []
        if "EMSDK" in env and cmd[:2] == 'em':
            families.append('emscripten')
        if cc_family is not None:
            families.append(cc_family)
        else:
            # On Windows, check for MSVC compatibility before checking GCC.
            if util.Platform() == 'windows':
                families.append('msvc')
            families.append('gcc')

        for family in families:
            compiler, e = self.run_compiler(env, mode, cmd, family)
            if compiler is not None:
                return compiler
            if isinstance(e, CompilerNotFoundException):
                # No reason to keep trying the same command.
                break

        return None

    def run_compiler(self, env, mode, cmd, assumed_family, abs_path = None):
        try:
            return VerifyCompiler(env, mode, cmd, assumed_family, abs_path), None
        except Exception as e:
            util.con_out(util.ConsoleHeader, 'Compiler {0} for {1} failed: '.format(cmd, mode),
                         util.ConsoleRed, str(e), util.ConsoleNormal)
            return None, e

def VerifyCompiler(env, mode, cmd, assumed_family, abs_path):
    base_argv = shlex.split(cmd)

    if 'CFLAGS' in env:
        base_argv.extend(env['CFLAGS'].split())
    if mode == 'CXX' and 'CXXFLAGS' in env:
        base_argv.extend(env['CXXFLAGS'].split())

    argv = base_argv[:]
    if abs_path is not None:
        argv[0] = abs_path
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
#elif defined(__EMSCRIPTEN__)
  printf("emscripten %d.%d\\n", __clang_major__, __clang_minor__);
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

    executable = 'test'
    if mode == 'CXX':
        executable += 'p'
    if assumed_family == 'emscripten':
        executable += '.js'
    else:
        executable += util.ExecutableSuffix

    # Make sure the exe is gone.
    if os.path.exists(executable):
        os.unlink(executable)

    argv.extend([filename, '-o', executable])

    # For MSVC, we need to detect the inclusion pattern for foreign-language
    # systems.
    if assumed_family == 'msvc':
        argv += ['-nologo', '-showIncludes']

    util.con_out(util.ConsoleHeader,
                 'Checking {0} compiler (vendor test {1})... '.format(mode, assumed_family),
                 util.ConsoleBlue, '{0}'.format(argv), util.ConsoleNormal)
    p = util.CreateProcess(argv, env = env)
    if p == None:
        raise CompilerNotFoundException('compiler not found')
    if util.WaitForProcess(p) != 0:
        raise Exception('compiler failed with return code {0}'.format(p.returncode))

    inclusion_pattern = None
    if assumed_family == 'msvc':
        inclusion_pattern = msvc_utils.DetectInclusionPattern(p.stdoutText)

    executable_argv = [executable]
    if assumed_family == 'emscripten':
        exe = 'node'
        executable_argv[0:0] = [exe]
    else:
        exe = util.MakePath('.', executable)

    p = util.CreateProcess(executable_argv, executable = exe, env = env)
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
    elif vendor == 'emscripten':
        v = Emscripten(version)
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

    util.con_out(util.ConsoleHeader, 'found {0} version {1}'.format(vendor, version),
                 util.ConsoleNormal)
    return CommandAndVendor(base_argv, v)

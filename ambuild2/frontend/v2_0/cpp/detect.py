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
from ambuild2.frontend.v2_0.cpp import vendors, compilers

def TryVerifyCompiler(env, mode, cmd):
    if util.IsWindows():
        cc = VerifyCompiler(env, mode, cmd, 'msvc')
        if cc:
            return cc
    return VerifyCompiler(env, mode, cmd, 'gcc')

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

def DetectMicrosoftInclusionPattern(text):
    for line in [raw.strip() for raw in text.split('\n')]:
        m = re.match(r'(.*)\s+([A-Za-z]:\\.*stdio\.h)$', line)
        if m is None:
            continue

        phrase = m.group(1)
        return re.escape(phrase) + r'\s+([A-Za-z]:\\.*)$'

    raise Exception('Could not find compiler inclusion pattern')

def DetectCxx(env, options):
    cc = DetectCxxCompiler(env, 'CC')
    cxx = DetectCxxCompiler(env, 'CXX')

    # Ensure that the two compilers have the same vendor.
    if type(cc) is not type(cxx):
        message = 'C and C++ compiler vendors are not the same: CC={0}, CXX={1}'
        message = message.format(cc.name, cxx.name)

        util.con_err(util.ConsoleRed, message, util.ConsoleNormal)
        raise Exception(message)

    # Ensure that the two compilers have the same version.
    if cc.version != cxx.version:
        message = 'C and C++ compilers have different versions: CC={0}-{1}, CXX={2}-{3}'
        message = message.format(cc.name, cc.version, cxx.name, cxx.version)

        util.con_err(util.ConsoleRed, message, util.ConsoleNormal)
        raise Exception(message)

    return compilers.CxxCompiler(cc, cxx, options)

def DetectCxxCompiler(env, var):
    if var in env:
        trys = [env[var]]
    else:
        if util.Platform() in CompilerSearch[var]:
            trys = CompilerSearch[var][util.Platform()]
        else:
            trys = CompilerSearch[var]['default']
    for i in trys:
        cc = TryVerifyCompiler(env, var, i)
        if cc:
            return cc

    # Try for Emscripten. This only works with an env override.
    if 'emcc' in env.get(var, ''):
        cc = DetectEmscripten(env, var)
        if cc:
            return cc

    # Fail.
    raise Exception('Unable to find a suitable ' + var + ' compiler')

def DetectEmscripten(env, var):
    cmd = env[var]
    argv = cmd.split()
    if 'CFLAGS' in env:
        argv += env.get('CFLAGS', '').split()
    if var == 'CC':
        suffix = '.c'
    elif var == 'CXX':
        argv += env.get('CXXFLAGS', '').split()
        suffix = '.cpp'

    # Run emcc -dM -E on a blank file to get preprocessor definitions.
    with tempfile.NamedTemporaryFile(suffix = suffix, delete = True) as fp:
        argv = cmd.split() + ['-dM', '-E', fp.name]
        output = subprocess.check_output(args = argv, universal_newlines = True)
    output = output.replace('\r', '')
    lines = output.split('\n')

    # Map the definitions into a dictionary.
    defs = {}
    for line in lines:
        m = re.match('#define\s+([A-Za-z_][A-Za-z0-9_]*)\s*(.*)', line)
        if m is None:
            continue
        macro = m.group(1)
        value = m.group(2)
        defs[macro] = value

    if '__EMSCRIPTEN__' not in defs:
        return None

    version = '{0}.{1}'.format(defs['__EMSCRIPTEN_major__'], defs['__EMSCRIPTEN_minor__'])
    v = vendors.Emscripten(cmd, version)

    util.con_out(util.ConsoleHeader, 'found {0} version {1}'.format('Emscripten', version),
                 util.ConsoleNormal)
    return v

def VerifyCompiler(env, mode, cmd, vendor):
    args = cmd.split()
    if 'CFLAGS' in env:
        args.extend(env['CFLAGS'].split())
    if mode == 'CXX' and 'CXXFLAGS' in env:
        args.extend(env['CXXFLAGS'].split())
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

    # Until we can better detect vendors, don't do this.
    # if vendor == 'gcc' and mode == 'CXX':
    #   args.extend(['-fno-exceptions', '-fno-rtti'])
    args.extend([filename, '-o', executable])

    # For MSVC, we need to detect the inclusion pattern for foreign-language
    # systems.
    if vendor == 'msvc':
        args += ['-nologo', '-showIncludes']

    util.con_out(util.ConsoleHeader,
                 'Checking {0} compiler (vendor test {1})... '.format(mode, vendor),
                 util.ConsoleBlue, '{0}'.format(args), util.ConsoleNormal)
    p = util.CreateProcess(args)
    if p == None:
        print('not found')
        return False
    if util.WaitForProcess(p) != 0:
        print('failed with return code {0}'.format(p.returncode))
        return False

    inclusion_pattern = None
    if vendor == 'msvc':
        inclusion_pattern = DetectMicrosoftInclusionPattern(p.stdoutText)

    exe = util.MakePath('.', executable)
    p = util.CreateProcess([executable], executable = exe)
    if p == None:
        print('failed to create executable with {0}'.format(cmd))
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
        v = vendors.GCC(cmd, version)
    elif vendor == 'apple-clang':
        v = vendors.Clang('apple-clang', cmd, version)
    elif vendor == 'clang':
        v = vendors.Clang('clang', cmd, version)
    elif vendor == 'msvc':
        v = vendors.MSVC(cmd, version)
    elif vendor == 'sun':
        v = vendors.SunPro(cmd, version)
    else:
        print('Unknown vendor {0}'.format(vendor))
        return False

    if inclusion_pattern is not None:
        v.extra_props['inclusion_pattern'] = inclusion_pattern

    util.con_out(util.ConsoleHeader, 'found {0} version {1}'.format(vendor, version),
                 util.ConsoleNormal)
    return v

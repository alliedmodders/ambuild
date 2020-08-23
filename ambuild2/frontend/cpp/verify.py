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
import os
from ambuild2 import util
from ambuild2.frontend.cpp import msvc_utils

class Verifier(object):
    def __init__(self, family, mode, argv, env, cross_compile = False):
        self.family_ = family
        self.mode_ = mode
        self.env_ = env
        self.argv_ = argv
        self.cross_compile_ = cross_compile

        if self.mode_ == 'CXX':
            self.source_filename_ = 'test.cpp'
            self.executable_ = 'test-cxx'
        else:
            self.source_filename_ = 'test.c'
            self.executable_ = 'test-c'

        if self.family_ == 'emscripten':
            self.executable_ += '.js'
        else:
            self.executable_ += util.ExecutableSuffix

    def verify(self):
        if os.path.exists(self.executable_):
            os.unlink(self.executable_)

        if self.cross_compile_:
            return self.verify_cross_compile()
        else:
            return self.verify_native()

    def verify_native(self):
        self.write_source(False)
        argv = self.build_link_argv()

        util.con_out(util.ConsoleHeader,
                     'Checking {0} compiler (vendor test {1})... '.format(self.mode_, self.family_),
                     util.ConsoleBlue, '{0}'.format(argv), util.ConsoleNormal)

        p = util.CreateProcess(argv, env = self.env_, no_raise = False)
        if util.WaitForProcess(p) != 0:
            raise Exception('Compiler failed with return code {0}'.format(p.returncode))

        inclusion_pattern = None
        if self.family_ == 'msvc':
            inclusion_pattern = msvc_utils.DetectInclusionPattern(p.stdoutText)

        lines = self.test_executable()

        return {
            'vendor': lines[0],
            'arch': lines[2],
            'inclusion_pattern': inclusion_pattern,
        }

    def verify_cross_compile(self):
        self.write_source(True)
        argv = self.build_pp_argv()

        util.con_out(util.ConsoleHeader,
                     'Checking {0} compiler (vendor test {1})... '.format(self.mode_, self.family_),
                     util.ConsoleBlue, '{0}'.format(argv), util.ConsoleNormal)

        p = util.CreateProcess(argv, env = self.env_, no_raise = False)
        if util.WaitForProcess(p) != 0:
            raise Exception('compiler failed with return code {0}'.format(p.returncode))

        lines = self.parse_pp(p.stdoutText)
        self.verify_lines(lines)

        # Execute one more time to test linkage.
        self.write_source(False)
        argv = self.build_link_argv()

        p = util.CreateProcess(argv, env = self.env_, no_raise = False)
        if util.WaitForProcess(p) != 0:
            raise Exception('compiler failed with return code {}: {}'.format(p.returncode, argv))

        inclusion_pattern = None
        if self.family_ == 'msvc':
            inclusion_pattern = msvc_utils.DetectInclusionPattern(p.stdoutText)

        return {
            'vendor': lines[0],
            'arch': lines[2],
            'inclusion_pattern': inclusion_pattern,
        }

    def write_source(self, is_pp):
        text = TEST_SOURCE.format(is_pp = int(is_pp))
        with open(self.source_filename_, 'w') as fp:
            fp.write(text)

    def parse_pp(self, text):
        lines = text.split('\n')
        results = []

        # The preprocessor will spit out lines like:
        #    AMBUILD_CATCH_THIS "gcc %d.%d\n", 9, 3;
        #
        # We chop off the prefix and semicolon, then rewrite the format string
        # and interpret in Python.
        prefix = 'AMBUILD_CATCH_THIS'
        for line in lines:
            index = line.find(prefix)
            if index == -1:
                continue
            line = line[index + len(prefix):].strip().strip(';')
            parts = [part.strip() for part in line.split(',')]
            format_string = parts[0].replace('%d', '{}')
            format_string = format_string.replace('\\n', '')
            format_string = format_string.strip('"')
            results.append(format_string.format(*parts[1:]))
        return results

    def build_pp_argv(self):
        if self.family_ in ['gcc', 'emscripten']:
            argv = self.argv_ + ['-E', self.source_filename_]
        elif self.family_ == 'msvc':
            argv = self.argv_ + ['-E', self.source_filename_, '-nologo']
        return argv

    def build_link_argv(self):
        argv = self.argv_ + [self.source_filename_, '-o', self.executable_]

        # For MSVC, we need to detect the inclusion pattern for foreign-language
        # systems.
        if self.family_ == 'msvc':
            argv += ['-nologo', '-showIncludes']

        return argv

    def test_executable(self):
        executable_argv = [self.executable_]
        if self.family_ == 'emscripten':
            exe = 'node'
            executable_argv[0:0] = [exe]
        else:
            exe = util.MakePath('.', self.executable_)

        p = util.CreateProcess(executable_argv, executable = exe, env = self.env_)
        if p == None:
            raise Exception('failed to create executable with {0}'.format(self.argv_[0]))
        if util.WaitForProcess(p) != 0:
            raise Exception('executable failed with return code {0}'.format(p.returncode))

        lines = p.stdoutText.splitlines()
        self.verify_lines(lines)

        return lines

    def verify_lines(self, lines):
        if len(lines) != 3:
            raise Exception('invalid executable output')
        if lines[1] != self.mode_:
            raise Exception('requested {0} compiler, found {1}'.format(self.mode_, lines[1]))

TEST_SOURCE = """
#if {is_pp}
# define printf(...) AMBUILD_CATCH_THIS __VA_ARGS__
#else
# include <stdio.h>
# include <stdlib.h>
#endif

int main()
{{
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
  printf("sun %d\\n", __SUNPRO_C);
#elif defined __SUNPRO_CC
  printf("sun %d\\n", __SUNPRO_CC);
#else
#error "Unrecognized compiler!"
#endif
#if defined __cplusplus
  printf("CXX\\n");
#else
  printf("CC\\n");
#endif
#if defined(__amd64__) || defined(__amd64) || defined(__x86_64__) || defined(__x86_64_) || \\
    defined(_M_X64) || defined(_M_AMD64)
  printf("x86_64\\n");
#elif defined(__aarch64__)
  printf("arm64\\n");
#elif defined(i386) || defined(__i386) || defined(__i386__) || defined(__i686__) || \\
      defined(__i386) || defined(_M_IX86)
  printf("x86\\n");
#elif defined(__aarch64__) || defined(_M_ARM64)
  printf("arm64\\n");
#elif defined(__arm__) || defined(_M_ARM)
  printf("arm\\n");
#else
  printf("unknown\\n");
#endif
  exit(0);
}}
"""

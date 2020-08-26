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
from __future__ import print_function
import os
import re
import shlex
import subprocess
import tempfile
from ambuild2 import util
from ambuild2.frontend.cpp import cpp_rules
from ambuild2.frontend.cpp import msvc_utils
from ambuild2.frontend.cpp.verify import Verifier
from ambuild2.frontend.system import System
from ambuild2.frontend.v2_2.cpp import vendor, compiler
from ambuild2.frontend.v2_2.cpp.gcc import GCC, Clang, Emscripten
from ambuild2.frontend.v2_2.cpp.msvc import MSVC

class CommandAndVendor(object):
    def __init__(self, argv, vendor, arch):
        self.argv = argv
        self.vendor = vendor
        self.arch = arch
        self.subarch = ''

class CompilerNotFoundException(Exception):
    def __init__(self, message = 'Unable to find a suitable C/C++ compiler'):
        super(CompilerNotFoundException, self).__init__(message)

kClangTuple = ('clang', 'clang++', 'gcc')
kGccTuple = ('gcc', 'g++', 'gcc')
kIntelTuple = ('icc', 'icc', 'gcc')
kMsvcTuple = ('cl', 'cl', 'msvc')

kGnuArchMap = {
    'arm64': 'aarch64',
}

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

def AutoDetectCxx(host, gen_options, **kwargs):
    locator = CompilerLocator(host, gen_options, **kwargs)
    return locator.detect()

def IsCrossCompile(host, target):
    if host.platform != target.platform:
        return True
    if host.arch != target.arch:
        if host.arch == 'x86_64' and target.arch in ['x86', 'x86_64']:
            return False
        return True
    if host.subarch != target.subarch:
        return True
    return host.abi != target.abi

class CompilerLocator(object):
    def __init__(self, host, gen_options, **kwargs):
        self.host_ = host
        self.gen_options_ = gen_options
        self.rp_ = cpp_rules.RulesParser()
        self.force_msvc_version_ = kwargs.pop('force_msvc_version', None)
        self.rules_config_ = {
            'family': 'unknown',
            'platform': self.host_.platform,
        }
        self.target_override_ = False

        arch, subarch = self.host_.arch, self.host_.subarch
        abi = self.host_.abi
        platform = None
        if 'target' in kwargs:
            target_phrase = kwargs.pop('target')
            parts = target_phrase.split('-')

            # We allow:
            #   arch
            #   platform-arch
            #   arch-abi
            #   platform-arch-abi
            if len(parts) == 1:
                arch = parts[0]
            elif len(parts) == 2:
                if parts[0] in util.ALL_PLATFORMS:
                    platform, arch = parts
                else:
                    arch, abi = parts
            elif len(parts) == 3:
                platform, arch, abi = parts
            else:
                raise Exception('Target could not be parsed: {}'.format(target_phrase))

            arch, subarch = util.DecodeArchString(arch)
            self.target_override_ = True
        else:
            if 'target_arch' in kwargs:
                arch, subarch = util.DecodeArchString(kwargs.pop('target_arch'))
                self.target_override_ = True

        self.rules_config_['arch'] = arch
        self.rules_config_['subarch'] = subarch
        self.rules_config_['abi'] = abi
        self.target_ = System(self.host_.platform, arch, subarch, abi)
        self.cross_compile_ = IsCrossCompile(self.host_, self.target_)

        # Allow specifying the environment file via the environment.
        self.vcvars_override_ = {}
        for arch in ['x86', 'x86_64', 'arm', 'arm64', 'all']:
            key = 'AMBUILD_VCVARS_{}'.format(arch.upper())
            if key not in os.environ:
                continue
            self.vcvars_override_[arch] = os.environ[key]

    def detect(self):
        if 'CC' in os.environ or 'CXX' in os.environ:
            return self.detect_from_env()

        if self.host_.platform == 'windows':
            compiler = self.detect_msvc()
            if compiler:
                return compiler

        return self.find_default_compiler()

    def detect_from_env(self):
        if 'CC' not in os.environ:
            raise Exception('CXX set in environment, but not CC')
        if 'CXX' not in os.environ:
            raise Exception('CC set in environment, but not CXX')

        cc = self.find_compiler('CC', os.environ['CC'])
        if cc is None:
            raise CompilerNotFoundException('Unable to find a suitable C compiler')

        cxx = self.find_compiler('CXX', os.environ['CXX'])
        if cxx is None:
            raise CompilerNotFoundException('Unable to find a suitable C++ compiler')

        return self.create_cli(cc, cxx)

    def create_cli(self, cc, cxx, env_data = None):
        # Ensure that the two compilers have the same vendor.
        if not cxx.vendor.equals(cc.vendor):
            message = 'C and C++ compiler are different: CC={0}, CXX={1}'
            message = message.format(cc.vendor, cxx.vendor)

            util.con_err(util.ConsoleRed, message, util.ConsoleNormal)
            raise Exception(message)

        if cxx.arch != cc.arch:
            message = "C architecture \"{0}\" does not match C++ architecture \"{1}\"".format(
                cc.arch, cxx.arch)
            util.con_err(util.ConsoleRed, message, util.ConsoleNormal)
            raise Exception(message)

        if cxx.arch != self.target_.arch and self.target_override_:
            message = "Compiler architecture \"{0}\" does not match requested architecture \"{1}\"".format(
                cxx.arch, self.target_.arch)
            util.con_err(util.ConsoleRed, message, util.ConsoleNormal)
            raise Exception(message)

        if env_data is not None:
            if cxx.vendor.extra_props:
                env_data['props'] = util.BuildTupleFromDict(cxx.vendor.extra_props)
            env_data = util.BuildTupleFromDict(env_data)

        return compiler.CliCompiler(cxx.vendor,
                                    System(self.host_.platform, cxx.arch, cxx.subarch,
                                           self.target_.abi),
                                    cc.argv,
                                    cxx.argv,
                                    options = self.gen_options_,
                                    env_data = env_data)

    def detect_msvc(self):
        # If the caller has already configured the environment, we'll expect it to
        # be always configured for us in the future.
        _, has_cl = FindToolsInEnv(os.environ, ['cl.exe'])
        if has_cl:
            return self.find_default_compiler()

        if self.target_.arch in self.vcvars_override_:
            cxx = self.try_msvc_bat(self.vcvars_override_[self.target_.arch])
            if not cxx:
                raise CompilerNotFoundException()
            return cxx

        if 'all' in self.vcvars_override_:
            cxx = self.try_msvc_bat(self.vcvars_override_['all'], pass_arch = True)
            if not cxx:
                raise CompilerNotFoundException()
            return cxx

        installs = msvc_utils.MSVCFinder().find_all()
        for install in installs:
            if self.force_msvc_version_ and install.version != self.force_msvc_version_:
                continue
            if self.target_.arch in install.vcvars:
                compiler = self.try_msvc_bat(install.vcvars[self.target_.arch])
                if compiler is not None:
                    return compiler
            if 'all' in install.vcvars:
                compiler = self.try_msvc_bat(install.vcvars['all'], pass_arch = True)
                if compiler is not None:
                    return compiler

        raise CompilerNotFoundException()

    def try_msvc_bat(self, bat_file, pass_arch = False):
        argv = []
        if pass_arch:
            argv.append(msvc_utils.MakeArchParam(self.host_, self.target_))

        try:
            env_cmds = msvc_utils.DeduceEnv(bat_file, argv)
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

        cc, _ = self.run_compiler('CC', 'cl', 'msvc', env, abs_path = tools['cl.exe'])
        if not cc:
            return None
        cxx, _ = self.run_compiler('CXX', 'cl', 'msvc', env, abs_path = tools['cl.exe'])
        if not cxx:
            return None

        # We use tuples here so the data is hashable without going through Pickle.
        tool_list = (
            ('cl', tools['cl.exe']),
            ('rc', tools['rc.exe']),
            ('lib', tools['lib.exe']),
        )
        env_data = {
            'env_cmds': env_cmds,
            'tools': tool_list,
        }
        return self.create_cli(cc, cxx, env_data)

    def find_default_compiler(self):
        candidates = []
        if self.host_.platform == 'windows':
            candidates.append(kMsvcTuple)

        if self.cross_compile_ and self.host_.platform == 'linux':
            if self.target_.abi:
                abi = self.target_.abi
            else:
                abi = 'gnu'
            arch = kGnuArchMap.get(self.target_.arch, self.target_.arch)
            cmd_prefix = '{}-linux-{}'.format(arch, abi)
            candidates += [(cmd_prefix + '-gcc', cmd_prefix + '-g++', 'gcc')]

        candidates.extend([kClangTuple, kGccTuple, kIntelTuple])

        for cc_cmd, cxx_cmd, cc_family in candidates:
            cc = self.find_compiler('CC', cc_cmd, cc_family)
            if cc is None:
                continue
            cxx = self.find_compiler('CXX', cxx_cmd, cc_family)
            if cxx is not None:
                return self.create_cli(cc, cxx)

        raise CompilerNotFoundException()

    def find_compiler(self, mode, cmd, cc_family = None):
        families = []
        if "EMSDK" in os.environ and cmd[:2] == 'em':
            families.append('emscripten')
        if cc_family is not None:
            families.append(cc_family)
        else:
            # On Windows, check for MSVC compatibility before checking GCC.
            if self.host_.platform == 'windows':
                families.append('msvc')
            families.append('gcc')

        for family in families:
            compiler, e = self.run_compiler(mode, cmd, family)
            if compiler is not None:
                return compiler
            if isinstance(e, CompilerNotFoundException):
                # No reason to keep trying the same command.
                break

        return None

    def run_compiler(self, mode, cmd, assumed_family, env = None, abs_path = None):
        self.rules_config_['family'] = assumed_family
        props = self.rp_.parse(self.rules_config_)

        flags = props.get('CFLAGS', [])
        flags += shlex.split(os.environ.get('CFLAGS', ''))
        if mode == 'CXX':
            flags.extend(shlex.split(os.environ.get('CXXFLAGS', '')))

        try:
            return self.verify_compiler(flags, mode, cmd, assumed_family, env, abs_path), None
        except Exception as e:
            util.con_out(util.ConsoleHeader, 'Compiler {0} for {1} failed: '.format(cmd, mode),
                         util.ConsoleRed, str(e), util.ConsoleNormal)
            return None, e

    def verify_compiler(self, flags, mode, cmd, assumed_family, env, abs_path):
        base_argv = shlex.split(cmd)
        base_argv.extend(flags)

        argv = base_argv[:]
        if abs_path is not None:
            argv[0] = abs_path

        verifier = Verifier(family = assumed_family,
                            env = env,
                            argv = argv,
                            mode = mode,
                            cross_compile = self.cross_compile_)
        info = verifier.verify()

        vendor, version = info['vendor'].split(' ')
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
        else:
            raise Exception('Unknown vendor {0}'.format(vendor))

        if info['inclusion_pattern'] is not None:
            v.extra_props['inclusion_pattern'] = info['inclusion_pattern']

        util.con_out(util.ConsoleHeader,
                     'found {0} version {1}, {2}'.format(vendor, version,
                                                         info['arch']), util.ConsoleNormal)
        return CommandAndVendor(base_argv, v, info['arch'])

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
import collections
import json
import os
import platform
import re
import subprocess
import sys
import tempfile
from ambuild2 import util
from ambuild2.frontend.version import Version
try:
    import winreg
except:
    try:
        import _winreg as winreg
    except:
        winreg = None

class MSVCInstall(object):
    def __init__(self, version, path):
        self.version = Version(version)
        self.path = path
        self.vcvars = {}

class MSVCFinder(object):
    def __init__(self):
        self.installs_ = []

    def find_all(self):
        if not self.find_old():
            self.find_old_build_tools()
        self.find_new()

        def sort_by_version(install):
            return install.version

        self.installs_.sort(key = sort_by_version, reverse = True)

        return self.installs_

    def find_old(self):
        kCandidates = ['14.0']
        for version in kCandidates:
            self.find_old_install(version)

    def find_new(self):
        program_files = os.environ.get('PROGRAMFILES(X86)')
        if not program_files:
            program_files = os.environ.get('PROGRAMFILES')
        if not program_files:
            return
        vswhere = os.path.join(program_files, 'Microsoft Visual Studio', 'Installer', 'vswhere.exe')
        if not os.path.exists(vswhere):
            return
        argv = [
            vswhere,
            '-format',
            'json',
            '-products',
            '*',
            '-requires',
            'Microsoft.VisualStudio.Component.VC.Tools.x86.x64',
            '-utf8',
        ]
        try:
            output = subprocess.check_output(argv)
        except:
            return
        data = json.loads(output.decode('utf-8'))
        for obj in data:
            version_parts = obj['installationVersion'].split('.')
            version = version_parts[0] + '.0'
            install_path = obj['installationPath']
            install = MSVCInstall(version, os.path.join(install_path, 'VC'))
            build_path = os.path.join(install.path, 'Auxiliary', 'Build')

            candidates = []

            cpu = util.NormalizeArchString(platform.machine())
            if cpu == 'x86':
                candidates.append(('x86', 'vcvars32.bat'))
                candidates.append(('x86_64', 'vcvarsx86_amd64.bat'))
                candidates.append(('arm', 'vcvarsx86_arm.bat'))
                candidates.append(('arm64', 'vcvarsx86_arm64.bat'))
            elif cpu == 'x86_64':
                candidates.append(('x86', 'vcvarsamd64_x86.bat'))
                candidates.append(('x86_64', 'vcvars64.bat'))
                candidates.append(('arm', 'vcvarsamd64_arm.bat'))
                candidates.append(('arm64', 'vcvarsamd64_arm64.bat'))

            for target, bat_file in candidates:
                path = os.path.join(build_path, bat_file)
                if os.path.exists(path):
                    install.vcvars[target] = path

            if len(install.vcvars):
                self.installs_.append(install)

    def find_old_install(self, version):
        path = "SOFTWARE\\Microsoft\\VisualStudio\\SxS\\VC7"
        sam = winreg.KEY_WOW64_32KEY | winreg.KEY_QUERY_VALUE
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, path, 0, sam) as key:
                path_value, reg_type = winreg.QueryValueEx(key, version)
            if reg_type != winreg.REG_SZ:
                return False
            install = MSVCInstall(version, path_value)
        except:
            return False

        candidates = []

        cpu = util.NormalizeArchString(platform.machine())
        if cpu == 'x86':
            candidates.append(('x86', 'vcvars32.bat'))
            candidates.append(('x86_64', os.path.join('x86_amd64', 'vcvarsx86_amd64.bat')))
            candidates.append(('arm', os.path.join('arm', 'vcvarsx86_arm.bat')))
        elif cpu == 'x86_64':
            candidates.append(('x86', os.path.join('amd64_x86', 'vcvarsamd64_x86.bat')))
            candidates.append(('x86_64', os.path.join('amd64', 'vcvars64.bat')))
            candidates.append(('arm', os.path.join('amd64_arm', 'vcvarsamd64_arm.bat')))

        for target, bat_file in candidates:
            path = os.path.join(path_value, 'bin', bat_file)
            if os.path.exists(path):
                install.vcvars[target] = path

        if len(install.vcvars):
            self.installs_.append(install)
        return True

    def find_old_build_tools(self):
        top = os.environ.get('ProgramFiles(x86)', r"C:\\Program Files (x86)")
        path = os.path.join(top, 'Microsoft Visual C++ Build Tools', 'vcbuildtools.bat')
        if not os.path.exists(path):
            return

        install = MSVCInstall('14.0', os.path.split(path)[0])
        install.vcvars['all'] = path
        self.installs_.append(install)
        return True

def parse_env(text):
    env = {}
    lines = text.split('\r\n')
    for line in lines:
        first_eq = line.find('=')
        if first_eq == -1:
            env[line.upper()] = ''
        else:
            key = line[0:first_eq]
            value = line[first_eq + 1:]
            env[key.upper()] = value
    return env

def find_env_changes(env1, env2):
    # Important: use OrderedDict, so that we have stable results across
    # builds. Otherwise we could accidentally invalidate.
    replace = collections.OrderedDict()
    add = collections.OrderedDict()
    for key in env2:
        if key not in env1:
            replace[key] = env2[key]
            continue
        old_value = env1[key]
        new_value = env2[key]
        if old_value == new_value:
            continue
        if not new_value.startswith(old_value):
            replace[key] = new_value
        else:
            add[key] = new_value[len(old_value):]
    return replace, add

def run_batch(contents):
    fp = tempfile.NamedTemporaryFile(suffix = '.bat', delete = False)
    try:
        fp.write(contents.encode('ascii'))
        fp.close()
        return subprocess.check_output([fp.name]).decode('utf-8')
    finally:
        os.unlink(fp.name)

def DeduceEnv(vcvars_file, argv):
    contents = "SET\n"
    env_before = parse_env(run_batch(contents))
    args = ' '.join(['"{}"'.format(arg) for arg in argv])
    contents = "@echo off\n" + \
               "CALL \"{}\" {} 1>NUL\n".format(vcvars_file, args) + \
               "@echo on\n" + \
               "SET\n"
    env_after = parse_env(run_batch(contents))

    replace, add = find_env_changes(env_before, env_after)
    env_commands = []
    for key, value in replace.items():
        env_commands.append(('replace', key, value))
    for key, value in add.items():
        env_commands.append(('add', key, value))

    # Explicitly use tuples because this object gets attached to many commands
    # and is better left immutable. This also lets us hash it for reverse
    # lookup.
    return tuple(env_commands)

kArchMap = {
    'x86_64': 'amd64',
}

def MakeArchParam(host, target):
    if host.arch == target.arch:
        return kArchMap.get(target.arch, target.arch)
    host_arch = kArchMap.get(host.arch, host.arch)
    target_arch = kArchMap.get(target.arch, target.arch)
    return '{}_{}'.format(host_arch, target_arch)

def DetectInclusionPattern(text):
    for line in [raw.strip() for raw in text.split('\n')]:
        m = re.match(r'(.*)\s+([A-Za-z]:\\.*stdio\.h)$', line)
        if m is None:
            continue

        phrase = m.group(1)
        return re.escape(phrase) + r'\s+([A-Za-z]:\\.*)$'

    raise Exception('Could not find compiler inclusion pattern')

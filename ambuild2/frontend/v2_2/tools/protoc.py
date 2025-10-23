# vim: set ts=8 sts=4 sw=4 tw=99 et:
#
# This file is part of AMBuild.
#
# AMBuild is free software: you can Headeristribute it and/or modify
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
import os
import re
import subprocess
from ambuild2 import util
from ambuild2.frontend.version import Version
from ambuild2.frontend import paths

# Helper for building AddCommand() invocations for protoc.
class ProtocRunner(object):
    def __init__(self, protoc, builder, includes):
        self.protoc = protoc
        self.builder = builder

        self.argv = [self.protoc.path] + self.protoc.extra_argv
        self.seen_languages = set()

        for include in self.protoc.includes + includes:
            if not os.path.isabs(include):
                include = os.path.join(builder.currentSourcePath, include)
            self.argv += ['--proto_path={}'.format(include)]

        self.languages = collections.OrderedDict()
        self.gen_map = {}

    def AddOutput(self, language, folder):
        if language in self.languages:
            raise Exception('Output language {} specified twice'.format(language))

        self.languages[language] = {
            'folder': folder,
        }
        self.gen_map[language] = {}

        if folder is None:
            folder_path = '.'
        else:
            folder_path = folder.path

        self.argv += ['--{}_out={}'.format(language, folder_path)]

    def AddSource(self, source_path):
        source_name = os.path.basename(source_path)
        if source_name.endswith('.proto'):
            proto_name = source_name[:-len('.proto')]
        else:
            proto_name = source_name

        gen_file_list = []
        gen_file_map = {}
        for language in self.languages:
            folder = self.languages[language]['folder']

            gen_info = gen_file_map.setdefault(language, {
                'sources': 0,
                'headers': 0,
            })
            gen_source_names = []
            gen_header_names = []

            if language == 'python':
                if '.' in proto_name:
                    # This is not supported since it complicates folder entry tracking.
                    raise Exception(
                        'Python proto files cannot contain extra "." characters: {}'.format(
                            proto_name))
                gen_source_names += ['{}_pb2.py'.format(proto_name)]
            elif language == 'cpp':
                gen_source_names += ['{}.pb.cc'.format(proto_name)]
                gen_header_names += ['{}.pb.h'.format(proto_name)]
            else:
                raise Exception('Language not supported yet: {}'.format(language))

            for file in gen_source_names + gen_header_names:
                gen_file_list += [paths.Join(folder, file)]

            gen_info['sources'] += len(gen_source_names)
            gen_info['headers'] += len(gen_header_names)

        dep_file = paths.Join(folder, '{}.d'.format(source_name))
        argv = self.argv + [
            '--dependency_out={}'.format(dep_file),
            source_path,
        ]

        argv.insert(1, '--proto_path={}'.format(os.path.dirname(source_path)))

        gen_entries = self.builder.AddCommand(inputs = [source_path],
                                              argv = argv,
                                              outputs = gen_file_list,
                                              dep_type = 'md',
                                              dep_file = dep_file,
                                              shared_outputs = [dep_file],
                                              folder = None)

        # Translate the list of generated output entries.
        cursor = 0
        for language in self.languages:
            gen_info = gen_file_map[language]
            gen_sources = gen_entries[cursor:cursor + gen_info['sources']]
            cursor += len(gen_sources)

            gen_headers = gen_entries[cursor:cursor + gen_info['headers']]
            cursor += len(gen_headers)

            self.gen_map[language].setdefault('sources', []).extend(gen_sources)
            if gen_headers:
                self.gen_map[language].setdefault('headers', []).extend(gen_headers)

        # Should be one entry remaining, for the .d file.
        assert (cursor == len(gen_entries))

# Named tuple for protoc.StaticLibrary() results.
class ProtocCppNode(object):
    def __init__(self, lib, headers):
        self.lib = lib
        self.headers = headers

# Like cpp.Compiler, but for protobufs.
class Protoc(object):
    def __init__(self, path, name, version):
        super(Protoc, self).__init__()
        self.path = path
        self.name = name
        self.version = version
        self.extra_argv = []
        self.includes = []

    def clone(self):
        clone = Protoc(self.path, self.name, self.version)
        clone.extra_argv = self.extra_argv[:]
        clone.includes = self.includes[:]
        return clone

    # Each output entry is either a language, or a tuple of (language, folder_entry).
    def Generate(self, builder, sources, outputs, includes = []):
        runner = ProtocRunner(self, builder, includes + ['.'])

        if not outputs:
            raise Exception('No output languages were specified')

        # Add outputs for each language, tracking which generated files we expect.
        for output in outputs:
            if type(output) is tuple:
                language, folder = output
            else:
                language, folder = (output, builder.localFolder)
            runner.AddOutput(language, folder)

        # Add sources. Fixup relative paths since we don't run in the source dir.
        for source in sources:
            if not os.path.isabs(source):
                source = os.path.join(builder.currentSourcePath, source)
            runner.AddSource(source)

        return runner.gen_map

    def StaticLibrary(self, name, builder, cxx, sources, includes = []):
        gen_map = self.Generate(builder, sources, ['cpp'], includes)
        binary = cxx.StaticLibrary(name)
        binary.compiler.sourcedeps += gen_map['cpp']['sources']
        binary.compiler.sourcedeps += gen_map['cpp']['headers']
        for source in gen_map['cpp']['sources']:
            binary.sources += [os.path.join(builder.buildPath, source.path)]
        out = builder.Add(binary)
        return ProtocCppNode(out, gen_map['cpp']['headers'])

FoundProtocMap = set()

def DetectProtoc(**kwargs):
    path = kwargs.pop('path', None)
    if len(kwargs):
        raise Exception('Unknown argument: {}'.format(kwargs.items()[0]))

    if path is None:
        path = 'protoc'

    argv = [path, '--version']
    p = util.CreateProcess(argv)
    if p is None:
        raise Exception('Failed to find protobuf compiler {}'.format(path))
    if util.WaitForProcess(p) != 0:
        raise Exception('Failed to run protoc: {}'.format(p.returncode))

    text = p.stdoutText.strip()
    parts = text.split(' ')
    name = parts[0]
    version = Version(parts[1])

    if path not in FoundProtocMap:
        util.con_out(util.ConsoleHeader, 'found protoc {}-{}'.format(name, version),
                     util.ConsoleNormal)
        FoundProtocMap.add(path)

    return Protoc(path, name, version)

class ProtocTool(object):
    def __init__(self):
        pass

    def evaluate(self, cmd):
        gen_map = cmd.data.protoc.Generate(builder = cmd.context,
                                           sources = cmd.data.sources,
                                           outputs = [('cpp', cmd.localFolderNode)])
        cmd.sourcedeps += gen_map['cpp']['sources']
        cmd.sourcedeps += gen_map['cpp']['headers']
        for source in gen_map['cpp']['sources']:
            cmd.sources += [os.path.join(cmd.context.buildPath, source.path)]

class ProtocJob(object):
    def __init__(self, protoc = None, sources = []):
        if protoc is None:
            self.protoc = DetectProtoc()
        else:
            self.protoc = protoc.clone()
        self.sources = sources[:]
        self.tool = ProtocTool()

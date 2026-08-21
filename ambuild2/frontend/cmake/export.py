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
from ambuild2.frontend.v2_2.cpp.deptypes import PchNodes


def _normalize_path(path):
    return path.replace('\\', '/')


def _cmake_quote(value):
    return '"{}"'.format(value.replace('\\', '/').replace('"', '\\"'))


class Exporter(object):
    def __init__(self, cm):
        self.cm = cm
        self.targets_ = []
        self.target_names_ = set()
        self.output_targets_ = {}

    def add_target(self, builder):
        target_name = self._allocate_target_name(builder)
        output_path = self._target_output_path(builder)
        self.output_targets_[os.path.normpath(output_path)] = target_name
        link_dirs, link_options, link_libraries = self._collect_link_settings(builder.compiler)
        custom_commands = self._collect_custom_commands(builder)
        target = {
            'builder': builder,
            'name': target_name,
            'output_name': builder.name_,
            'output_path': output_path,
            'type': builder.type,
            'sources': self._collect_sources(builder),
            'custom_commands': custom_commands,
            'include_dirs': self._collect_include_dirs(builder.compiler)
                            + self._collect_custom_include_dirs(builder),
            'compile_defines': self._collect_compile_defines(builder.compiler),
            'compile_options': self._collect_compile_options(builder.compiler),
            'link_dirs': link_dirs,
            'link_options': link_options,
            'link_libraries': link_libraries,
            'pch_headers': self._collect_pch_headers(builder.compiler),
        }
        target['sources'] = self._dedupe(target['sources'] + self._collect_custom_outputs(custom_commands))
        target['include_dirs'] = self._dedupe(target['include_dirs'])
        self.targets_.append(target)

    def write(self):
        if not self.targets_:
            return

        path = os.path.join(self.cm.buildPath, 'CMakeLists.txt')
        with open(path, 'w') as fp:
            fp.write(self.render())

    def render(self):
        lines = [
            'cmake_minimum_required(VERSION 3.16)',
            'project({} LANGUAGES C CXX)'.format(self._project_name()),
            '',
        ]

        lines.extend(self._render_generated_files())
        lines.extend(self._render_configure_time_copies())
        if lines[-1] != '':
            lines.append('')

        for target in self.targets_:
            lines.extend(self._render_target(target))
            lines.append('')

        return '\n'.join(lines).rstrip() + '\n'

    def _project_name(self):
        base = os.path.basename(os.path.normpath(self.cm.sourcePath))
        if not base:
            base = os.path.basename(os.path.normpath(self.cm.buildPath))
        if not base:
            return 'ambuild_generated'

        sanitized = []
        for ch in base:
            if ch.isalnum() or ch == '_':
                sanitized.append(ch)
            else:
                sanitized.append('_')
        result = ''.join(sanitized).strip('_')
        return result or 'ambuild_generated'

    def _collect_generated_files(self):
        files = []
        generated = getattr(self.cm.generator, 'cmake_generated_files', {})
        for path, contents in generated.items():
            files.append({
                'path': _normalize_path(os.path.normpath(path)),
                'dir': _normalize_path(os.path.dirname(os.path.normpath(path))),
                'contents': contents,
            })
        files.sort(key = lambda item: item['path'])
        return files

    def _cmake_bracket_quote(self, value):
        text = str(value)
        for count in range(8):
            marker = '=' * count
            closing = ']{}]'.format(marker)
            if closing not in text:
                return '[{}[{}]{}]'.format(marker, text, marker)
        return _cmake_quote(text)

    def _render_generated_files(self):
        files = self._collect_generated_files()
        if not files:
            return []

        lines = []
        for item in files:
            lines.append('file(MAKE_DIRECTORY {})'.format(_cmake_quote(item['dir'])))
            lines.append('file(WRITE {} {})'.format(
                _cmake_quote(item['path']), self._cmake_bracket_quote(item['contents'])))
        return lines

    def _collect_configure_time_copies(self):
        copies = []
        target_outputs = set(os.path.normpath(target['output_path']) for target in self.targets_)
        file_ops = getattr(self.cm.generator, 'cmake_file_ops', {})
        for file_op in file_ops.values():
            if file_op['kind'] != 'copy':
                continue

            source_path = os.path.normpath(file_op['source'])
            output_path = os.path.normpath(file_op['output'])
            if source_path in target_outputs:
                continue
            if not self._looks_like_package_output(output_path):
                continue


            copies.append({
                'source': _normalize_path(source_path),
                'output': _normalize_path(output_path),
                'dir': _normalize_path(os.path.dirname(output_path)),
            })
        return self._dedupe_copy_items(copies)

    def _dedupe_copy_items(self, copies):
        unique = []
        seen = set()
        for item in copies:
            key = (item['source'], item['output'])
            if key in seen:
                continue
            seen.add(key)
            unique.append(item)
        return unique

    def _render_configure_time_copies(self):
        copies = self._collect_configure_time_copies()
        if not copies:
            return []

        lines = []
        for item in copies:
            lines.append('file(MAKE_DIRECTORY {})'.format(_cmake_quote(item['dir'])))
            lines.append('configure_file({} {} COPYONLY)'.format(
                _cmake_quote(item['source']), _cmake_quote(item['output'])))
        return lines
    def _allocate_target_name(self, builder):
        base = builder.name_
        if base not in self.target_names_:
            self.target_names_.add(base)
            return base

        suffix = '{}_{}{}'.format(builder.compiler.target.platform, builder.compiler.target.arch,
                                  builder.compiler.target.subarch)
        if builder.compiler.target.abi:
            suffix += '_' + builder.compiler.target.abi

        name = '{}_{}'.format(base, suffix.replace('-', '_'))
        unique_name = name
        counter = 2
        while unique_name in self.target_names_:
            unique_name = '{}_{}'.format(name, counter)
            counter += 1
        self.target_names_.add(unique_name)
        return unique_name

    def _target_output_path(self, builder):
        return _normalize_path(
            os.path.normpath(os.path.join(self.cm.buildPath, builder.localFolder, builder.outputFile)))

    def _collect_sources(self, builder):
        sources = []
        seen = set()
        for module in builder.modules_:
            for entry in module.sources:
                if hasattr(entry, 'source'):
                    entry = entry.source

                path = self._resolve_source(module.context, entry)
                if path in seen:
                    continue
                seen.add(path)
                sources.append(path)
        return sources

    def _collect_custom_commands(self, builder):
        commands = []
        root_context = builder.modules_[0].context if builder.modules_ else None
        for module in builder.modules_:
            for custom in getattr(module, 'custom', []):
                protoc_commands = self._build_protoc_commands(builder, root_context, module, custom)
                commands.extend(protoc_commands)
        return commands

    def _collect_custom_outputs(self, commands):
        outputs = []
        for command in commands:
            outputs.extend(command.get('outputs', []))
        return outputs

    def _collect_post_build_commands(self, target):
        commands = []
        file_ops = getattr(self.cm.generator, 'cmake_file_ops', {})
        output_path = os.path.normpath(target['output_path'])
        has_binary_package_copy = False

        for file_op in file_ops.values():
            if file_op['kind'] != 'copy':
                continue
            if os.path.normpath(file_op['source']) != output_path:
                continue

            has_binary_package_copy = True
            dest_path = _normalize_path(os.path.normpath(file_op['output']))
            dest_dir = _normalize_path(os.path.dirname(dest_path))
            commands.append([
                '${CMAKE_COMMAND}', '-E', 'make_directory', dest_dir,
            ])
            commands.append([
                '${CMAKE_COMMAND}', '-E', 'copy_if_different', '$<TARGET_FILE:{}>'.format(
                    target['name']), dest_path,
            ])

        if not has_binary_package_copy:
            return commands

        return self._dedupe_commands(commands)

    def _dedupe_commands(self, commands):
        unique = []
        seen = set()
        for command in commands:
            key = tuple(command)
            if key in seen:
                continue
            seen.add(key)
            unique.append(command)
        return unique

    def _looks_like_package_output(self, path):
        normalized = path.lower().replace('\\', '/')
        return '/addons/' in normalized

    def _collect_custom_include_dirs(self, builder):
        include_dirs = []
        root_context = builder.modules_[0].context if builder.modules_ else None
        for module in builder.modules_:
            if not getattr(module, 'custom', None):
                continue
            _, output_path = builder.computeModuleFolders(root_context, module.context)
            include_dirs.append(_normalize_path(os.path.normpath(output_path)))
        return include_dirs

    def _build_protoc_commands(self, builder, root_context, module, custom):
        protoc = getattr(custom, 'protoc', None)
        sources = getattr(custom, 'sources', None)
        if protoc is None or sources is None:
            return []

        _, output_path = builder.computeModuleFolders(root_context, module.context)
        output_path = _normalize_path(os.path.normpath(output_path))
        include_paths = []
        for include in protoc.includes + ['.']:
            if not os.path.isabs(include):
                include = os.path.join(module.context.currentSourcePath, include)
            include_paths.append(_normalize_path(os.path.normpath(include)))
        include_paths = self._dedupe(include_paths)

        commands = []
        for source in sources:
            if not os.path.isabs(source):
                source = os.path.join(module.context.currentSourcePath, source)
            source = _normalize_path(os.path.normpath(source))

            proto_name = os.path.basename(source)
            if proto_name.endswith('.proto'):
                proto_name = proto_name[:-len('.proto')]

            protoc_command = [_normalize_path(os.path.normpath(protoc.path))]
            protoc_command.append('--proto_path={}'.format(_normalize_path(os.path.dirname(source))))
            protoc_command.extend(str(arg) for arg in getattr(protoc, 'extra_argv', []))
            protoc_command.extend(['-I={}'.format(path) for path in include_paths])
            protoc_command.append('--cpp_out={}'.format(output_path))
            protoc_command.append(source)

            commands.append({
                'kind': 'protoc',
                'outputs': [
                    '{}/{}.pb.cc'.format(output_path, proto_name),
                    '{}/{}.pb.h'.format(output_path, proto_name),
                ],
                'depends': [source],
                'commands': [
                    ['${CMAKE_COMMAND}', '-E', 'make_directory', output_path],
                    protoc_command,
                ],
            })

        return commands

    def _resolve_source(self, context, entry):
        if isinstance(entry, str):
            if os.path.isabs(entry):
                return _normalize_path(os.path.normpath(entry))
            return _normalize_path(os.path.normpath(os.path.join(context.currentSourcePath, entry)))

        path = entry.path
        if not os.path.isabs(path):
            path = os.path.join(self.cm.buildPath, path)
        return _normalize_path(os.path.normpath(path))

    def _collect_include_dirs(self, compiler):
        includes = []
        seen = set()
        for include in compiler.includes + compiler.cxxincludes:
            if isinstance(include, PchNodes):
                include = include.folder.path

            value = self._stringify_value(include)
            if value in seen:
                continue
            seen.add(value)
            includes.append(value)
        return includes

    def _collect_compile_defines(self, compiler):
        return self._dedupe(self._stringify_value(value)
                            for value in compiler.defines + compiler.cxxdefines)

    def _collect_compile_options(self, compiler):
        return self._dedupe(self._stringify_value(value)
                            for value in compiler.cflags + compiler.cxxflags + compiler.c_only_flags)

    def _collect_link_settings(self, compiler):
        link_dirs = []
        link_options = []
        link_libraries = []
        synthetic_inputs = self._collect_synthetic_link_inputs(compiler)
        for value in compiler.linkflags + compiler.postlink:
            rendered = self._stringify_value(value)
            rendered = synthetic_inputs.get(rendered, rendered)

            target_name = self.output_targets_.get(os.path.normpath(rendered))
            if rendered.startswith('-L') and len(rendered) > 2:
                link_dirs.append(rendered[2:])
            elif rendered.startswith('/LIBPATH:') and len(rendered) > 9:
                link_dirs.append(rendered[9:])
            elif rendered.startswith('-l') and len(rendered) > 2:
                link_libraries.append(rendered[2:])
            elif target_name is not None:
                link_libraries.append(target_name)
            elif self._is_library_path(rendered):
                link_libraries.append(rendered)
            elif self._is_link_flag(rendered):
                link_options.append(rendered)
            else:
                link_libraries.append(rendered)
        return (self._dedupe(link_dirs), self._dedupe(link_options),
                self._dedupe(link_libraries))

    def _collect_synthetic_link_inputs(self, compiler):
        mapping = {}
        file_ops = getattr(self.cm.generator, 'cmake_file_ops', {})
        for entry in compiler.weaklinkdeps + compiler.linkdeps:
            if not hasattr(entry, 'path'):
                continue

            path = entry.path
            if not os.path.isabs(path):
                path = os.path.join(self.cm.buildPath, path)
            path = os.path.normpath(path)

            file_op = file_ops.get(path)
            if not file_op:
                continue

            basename = os.path.basename(path)
            mapping[basename] = _normalize_path(os.path.normpath(file_op['source']))
        return mapping

    def _collect_pch_headers(self, compiler):
        headers = []
        seen = set()
        for include in compiler.includes + compiler.cxxincludes:
            if not isinstance(include, PchNodes):
                continue

            header = include.header_file.path
            if not os.path.isabs(header):
                header = os.path.join(self.cm.buildPath, header)
            header = _normalize_path(os.path.normpath(header))
            if header in seen:
                continue
            seen.add(header)
            headers.append(header)
        return headers

    def _stringify_value(self, value):
        if hasattr(value, 'path'):
            path = value.path
            if not os.path.isabs(path):
                path = os.path.join(self.cm.buildPath, path)
            return _normalize_path(os.path.normpath(path))
        return str(value)

    def _is_link_flag(self, value):
        return value.startswith('-') or value.startswith('/')

    def _is_library_path(self, value):
        lower = value.lower()
        return lower.endswith(('.a', '.so', '.lib', '.dll', '.dylib')) and ('/' in value or '\\' in value)

    def _dedupe(self, values):
        items = []
        seen = set()
        for value in values:
            if value in seen:
                continue
            seen.add(value)
            items.append(value)
        return items

    def _render_target(self, target):
        lines = []
        for custom_command in target['custom_commands']:
            lines.extend(self._render_custom_command(custom_command))

        target_type = {
            'program': 'add_executable',
            'library': 'add_library',
            'static': 'add_library',
        }[target['type']]

        type_arg = ''
        if target['type'] == 'library':
            type_arg = ' SHARED'
        elif target['type'] == 'static':
            type_arg = ' STATIC'

        lines.append('{}({}{}'.format(target_type, target['name'], type_arg))
        for source in target['sources']:
            lines.append('  {}'.format(_cmake_quote(source)))
        lines.append(')')

        properties = []
        if target['name'] != target['output_name']:
            properties.extend(['OUTPUT_NAME', _cmake_quote(target['output_name'])])
        if target['type'] == 'library':
            properties.extend(['PREFIX', _cmake_quote('')])
        if properties:
            lines.append('set_target_properties({} PROPERTIES {})'.format(
                target['name'], ' '.join(properties)))

        lines.extend(self._render_list_call('target_include_directories', target['name'], 'PRIVATE',
                                            target['include_dirs']))
        lines.extend(self._render_list_call('target_compile_definitions', target['name'], 'PRIVATE',
                                            target['compile_defines']))
        lines.extend(self._render_list_call('target_compile_options', target['name'], 'PRIVATE',
                                            target['compile_options']))
        lines.extend(self._render_list_call('target_link_directories', target['name'], 'PRIVATE',
                                            target['link_dirs']))
        lines.extend(self._render_list_call('target_link_options', target['name'], 'PRIVATE',
                                            target['link_options']))
        lines.extend(self._render_list_call('target_link_libraries', target['name'], 'PRIVATE',
                                            target['link_libraries']))
        lines.extend(self._render_list_call('target_precompile_headers', target['name'], 'PRIVATE',
                                            target['pch_headers']))
        lines.extend(self._render_post_build_commands(target))
        return lines

    def _render_post_build_commands(self, target):
        commands = self._collect_post_build_commands(target)
        if not commands:
            return []

        lines = ['add_custom_command(TARGET {} POST_BUILD'.format(target['name'])]
        for command in commands:
            lines.append('  COMMAND')
            for item in command:
                lines.append('    {}'.format(_cmake_quote(item)))
        lines.append(')')
        return lines

    def _render_custom_command(self, command):
        lines = ['add_custom_command(']
        lines.append('  OUTPUT')
        for output in command['outputs']:
            lines.append('    {}'.format(_cmake_quote(output)))
        for subcommand in command['commands']:
            lines.append('  COMMAND')
            for item in subcommand:
                lines.append('    {}'.format(_cmake_quote(item)))
        lines.append('  DEPENDS')
        for dep in command['depends']:
            lines.append('    {}'.format(_cmake_quote(dep)))
        lines.append('  VERBATIM')
        lines.append(')')
        return lines

    def _render_list_call(self, call, target_name, visibility, values):
        if not values:
            return []

        lines = ['{}({} {}'.format(call, target_name, visibility)]
        for value in values:
            lines.append('  {}'.format(_cmake_quote(value)))
        lines.append(')')
        return lines












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
import os
from ambuild2.frontend.v2_2.tools.fxc import FxcJob
from ambuild2.frontend.v2_2.tools.protoc import ProtocJob

def find_custom_tools(builder):
    """Find custom tools in the builder and return a list of (tool_type, cmd) tuples."""
    custom_tools = []

    for cmd in getattr(builder, 'custom', []):
        cmd_type = type(cmd).__name__

        if cmd_type == 'ProtocJob':
            custom_tools.append(('protoc', cmd))
        elif cmd_type == 'FxcJob':
            custom_tools.append(('fxc', cmd))
        elif hasattr(cmd, 'tool'):
            tool_data = cmd
            if hasattr(tool_data, 'data'):
                data_type = type(tool_data.data).__name__
                if data_type == 'FxcJob':
                    custom_tools.append(('fxc', tool_data))
                elif data_type == 'ProtocJob':
                    custom_tools.append(('protoc', tool_data))

    return custom_tools

def add_custom_tool_include_paths(includes, node, builder, custom_tools):
    """Add include paths for custom tools to the includes list."""
    for tool_type, tool_data in custom_tools:
        if tool_type == 'protoc':
            output_folder = os.path.join(builder.localFolder)
            if output_folder not in includes:
                includes.append(output_folder)
        elif tool_type == 'fxc':
            current_dir = node.context.buildFolder
            if current_dir not in includes:
                includes.append(current_dir)

    return includes

def add_custom_tool_prebuild_events(xml, node, builder, custom_tools):
    """Add pre-build events for custom tools to the XML."""
    if not custom_tools:
        return False

    commands = []
    for tool_type, tool_data in custom_tools:
        if tool_type == 'fxc':
            if isinstance(tool_data, FxcJob):
                fxc_data = tool_data
            else:
                fxc_data = tool_data.data

            for shader in fxc_data.shaders:
                source = shader['source']
                var_prefix = shader['variable']
                profile = shader['profile']
                entrypoint = shader.get('entry', 'main')

                sourceFile = os.path.join(node.context.currentSourcePath, source)
                output_file = '{0}.{1}.{2}.h'.format(
                    os.path.basename(source).rsplit('.', 1)[0], var_prefix, entrypoint)

                fxc_cmd = 'fxc /T {0} /E {1} /Fh "$(ProjectDir){2}" /Vn {3}_Bytes_Impl /Vi /nologo "{4}"'.format(
                    profile, entrypoint, output_file, var_prefix, sourceFile)
                commands.append(fxc_cmd)

            output_prefix = fxc_data.output
            helper_cmd = 'python "{0}" --prefix "$(ProjectDir){1}"'.format(
                os.path.join(node.context.sourcePath, 'ambuild2', 'frontend', 'v2_2', 'tools',
                             'fxc.py'), output_prefix)
            if fxc_data.namespace:
                helper_cmd += ' --namespace "{0}"'.format(fxc_data.namespace)
            if fxc_data.listDefineName:
                helper_cmd += ' --list-define-name "{0}"'.format(fxc_data.listDefineName)

            for shader in fxc_data.shaders:
                var_prefix = shader['variable']
                entrypoint = shader.get('entry', 'main')
                source = shader['source']
                output_file = '{0}.{1}.{2}.h'.format(
                    os.path.basename(source).rsplit('.', 1)[0], var_prefix, entrypoint)
                helper_cmd += ' "$(ProjectDir){0}"'.format(output_file)

            commands.append(helper_cmd)

        elif tool_type == 'protoc':
            if isinstance(tool_data, ProtocJob):
                protoc_data = tool_data
            else:
                protoc_data = tool_data.data

            protoc_path = protoc_data.protoc.path

            for source in protoc_data.sources:
                if not os.path.isabs(source):
                    source = os.path.join(node.context.currentSourcePath, source)

                include_args = [ '--proto_path="{0}"'.format(os.path.dirname(source)) ]
                for include in protoc_data.protoc.includes + ['.']:
                    if not os.path.isabs(include):
                        include = os.path.join(node.context.currentSourcePath, include)
                    include_args.append('-I="{0}"'.format(include))

                output_folder = os.path.join(builder.localFolder)

                protoc_cmd = '{0} {1} --cpp_out="$(ProjectDir){2}" "{3}"'.format(
                    protoc_path, ' '.join(include_args), output_folder, source)

                dep_file = os.path.join(output_folder, '{0}.d'.format(os.path.basename(source)))
                protoc_cmd += ' --dependency_out="$(ProjectDir){0}"'.format(dep_file)

                commands.append(protoc_cmd)

    if commands:
        with xml.block('PreBuildEvent'):
            xml.tag('Command', '\n'.join(commands))
        return True

    return False

def add_custom_tool_output_files(node, xml, builder, custom_tools):
    """Add output files from custom tools to the project."""
    if not custom_tools:
        return

    generated_files = []

    for tool_type, tool_data in custom_tools:
        if tool_type == 'fxc':
            if isinstance(tool_data, FxcJob):
                fxc_data = tool_data
            else:
                fxc_data = tool_data.data

            output_prefix = fxc_data.output
            bytecode_file = '{0}-bytecode.cxx'.format(output_prefix)
            generated_files.append(bytecode_file)

        elif tool_type == 'protoc':
            if isinstance(tool_data, ProtocJob):
                protoc_data = tool_data
            else:
                protoc_data = tool_data.data

            for source in protoc_data.sources:
                proto_name = os.path.basename(source)
                if proto_name.endswith('.proto'):
                    proto_name = proto_name[:-len('.proto')]

                output_folder = os.path.join(builder.localFolder)
                cc_file = os.path.join(output_folder, '{0}.pb.cc'.format(proto_name))
                generated_files.append(cc_file)

    if generated_files:
        with xml.block('ItemGroup'):
            for file in generated_files:
                _, ext = os.path.splitext(file)
                if ext.lower() in ['.c', '.cc', '.cpp', '.cxx']:
                    xml.tag('ClCompile', Include = file)

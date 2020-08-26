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
import os, re
from ambuild2 import util
from ambuild2.frontend import paths
from ambuild2.frontend.cpp import cpp_utils
from ambuild2.frontend.v2_2.cpp.builders import Dep
from ambuild2.frontend.version import Version
from ambuild2.frontend.vs.xmlbuilder import XmlBuilder

def export(cm, node):
    with open(node.path, 'w') as fp:
        export_fp(cm, node, fp)

def export_fp(cm, node, fp):
    xml = XmlBuilder(fp)

    version = cm.generator.vs_vendor.version
    if version >= 'msvc-1910':
        toolsVersion = '15.0'
    elif version >= 'msvc-1900':
        toolsVersion = '14.0'
    elif version >= 'msvc-1800':
        toolsVersion = '12.0'
    elif version >= 'msvc-1600':
        toolsVersion = '4.0'

    scope = xml.block('Project',
                      DefaultTargets = 'Build',
                      ToolsVersion = toolsVersion,
                      xmlns = 'http://schemas.microsoft.com/developer/msbuild/2003')
    with scope:
        export_body(cm, node, xml)

def export_body(cm, node, xml):
    with xml.block('ItemGroup', Label = 'ProjectConfigurations'):
        export_configuration_headers(node, xml)

    version = cm.generator.vs_vendor.version
    with xml.block('PropertyGroup', Label = 'Globals'):
        xml.tag('ProjectGuid', '{{{0}}}'.format(node.uuid))
        xml.tag('RootNamespace', node.project.name_)
        xml.tag('Keyword', 'Win32Proj')
        if version >= 'msvc-1910':
            xml.tag('WindowsTargetPlatformVersion',
                    os.getenv('WindowsSDKVersion', None).rstrip('\\'))

    xml.tag('Import', Project = '$(VCTargetsPath)\Microsoft.Cpp.Default.props')
    export_configuration_properties(node, xml)

    xml.tag('Import', Project = '$(VCTargetsPath)\Microsoft.Cpp.props')
    with xml.block('ImportGroup', Label = 'ExtensionSettings'):
        pass
    export_configuration_user_props(node, xml)

    with xml.block('PropertyGroup', Label = "UserMacros"):
        pass

    with xml.block('PropertyGroup'):
        export_configuration_paths(node, xml)

    for builder in node.project.builders_:
        with xml.block('ItemDefinitionGroup', Condition = condition_for(builder)):
            export_configuration_options(node, xml, builder)

    export_source_files(node, xml)

    xml.tag('Import', Project = '$(VCTargetsPath)\Microsoft.cpp.targets')
    with xml.block('ImportGroup', Label = 'ExtensionTargets'):
        pass

def condition_for(builder):
    full_tag = '{0}|Win32'.format(builder.tag_)
    return "'$(Configuration)|$(Platform)'=='{0}'".format(full_tag)

def export_configuration_headers(node, xml):
    for builder in node.project.builders_:
        full_tag = '{0}|Win32'.format(builder.tag_)
        with xml.block('ProjectConfiguration', Include = full_tag):
            xml.tag('Configuration', builder.tag_)
            xml.tag('Platform', 'Win32')

def export_configuration_properties(node, xml):
    for builder in node.project.builders_:
        condition = condition_for(builder)
        with xml.block('PropertyGroup', Condition = condition, Label = 'Configuration'):
            xml.tag('ConfigurationType', builder.configurationType)
            xml.tag('CharacterSet', 'MultiByte')
            if '/GL' in builder.compiler.cxxflags:
                xml.tag('WholeProgramOptimization', 'true')

            version = builder.compiler.version
            if version >= 'msvc-1910':
                xml.tag('PlatformToolset', 'v141')
            elif version >= 'msvc-1900':
                xml.tag('PlatformToolset', 'v140')
            elif version >= 'msvc-1800':
                xml.tag('PlatformToolset', 'v120')
            elif version >= 'msvc-1700':
                xml.tag('PlatformToolset', 'v110')

def export_configuration_user_props(node, xml):
    for builder in node.project.builders_:
        condition = condition_for(builder)
        with xml.block('ImportGroup', Condition = condition, Label = 'PropertySheets'):
            xml.tag('Import',
                    Project = "$(UserRootDir)\Microsoft.Cpp.$(Platform).user.props",
                    Condition = "exists('$(UserRootDir)\Microsoft.Cpp.$(Platform).user.props')",
                    Label = "LocalAppDataPlatform")

def export_configuration_paths(node, xml):
    for builder in node.project.builders_:
        condition = condition_for(builder)
        xml.tag('OutDir', "$(ProjectName) - $(Configuration)\\", Condition = condition)
        xml.tag('IntDir', "$(ProjectName) - $(Configuration)\\", Condition = condition)
        if '/INCREMENTAL:NO' not in builder.compiler.linkflags and '/INCREMENTAL:NO' not in builder.compiler.postlink:
            xml.tag('LinkIncremental', 'true', Condition = condition)
        xml.tag('TargetName', builder.name_, Condition = condition)

def sanitize_val_defines(defines):
    new_defines = []
    for option in defines:
        index = option.find('=')
        if index == -1:
            new_defines.append(option)
            continue

        key = option[0:index]
        val = option[index + 1:]
        if val[0] == '"' and val[-1] == '"':
            val = '\\"{0}\\"'.format(val)
        new_defines.append('{0}={1}'.format(key, val))
    return new_defines

def make_unified_header(builder, name, sources):
    path = os.path.join(builder.localFolder, name + '.h')
    guard = '_include_' + util.MakeLexicalFilename(name)
    text = cpp_utils.CreateUnifiedHeader(guard, sources)
    with open(path, 'wb') as fp:
        fp.write(text.encode('utf-8'))
    return path

def export_configuration_options(node, xml, builder):
    from ambuild2.frontend.v2_2.vs.cxx import PchNodes

    compiler = builder.compiler

    includes = ['%(AdditionalIncludeDirectories)']
    for include in compiler.includes + compiler.cxxincludes:
        if isinstance(include, PchNodes):
            path = make_unified_header(builder, include.name, include.sources)
            includes.append(os.path.split(path)[0])
        else:
            includes.append(include)

    all_defines = compiler.defines + compiler.cxxdefines
    simple_defines = ['%(PreprocessorDefinitions)'
                     ] + [option for option in all_defines if '=' not in option]
    val_defines = ['/D{0}'.format(option) for option in all_defines if '=' in option]

    with xml.block('ClCompile'):
        flags = compiler.cflags + compiler.cxxflags

        # Filter out options we handle specially.
        other_flags = val_defines + flags
        other_flags = [flag for flag in other_flags if not flag.startswith('/O')]
        other_flags = [flag for flag in other_flags if not flag.startswith('/RTC')]
        other_flags = [flag for flag in other_flags if not flag.startswith('/EH')]
        other_flags = [flag for flag in other_flags if not flag.startswith('/MT')]
        other_flags = [flag for flag in other_flags if not flag.startswith('/MD')]
        other_flags = [flag for flag in other_flags if not flag.startswith('/W')]
        other_flags = [flag for flag in other_flags if not flag.startswith('/GR')]

        if len(other_flags):
            xml.tag('AdditionalOptions', ' '.join(other_flags))

        xml.tag('AdditionalIncludeDirectories', ';'.join(includes))
        xml.tag('PreprocessorDefinitions', ';'.join(simple_defines))

        if '/Ox' in flags:
            xml.tag('Optimization', 'Full')
        elif '/O2' in flags:
            xml.tag('Optimization', 'MaxSpeed')
        elif '/O1' in flags:
            xml.tag('Optimization', 'MinSpace')
        else:
            xml.tag('Optimization', 'Disabled')

        if '/Os' in flags:
            xml.tag('FavorSizeOrSpeed', 'Size')
        elif '/Ot' in flags:
            xml.tag('FavorSizeOrSpeed', 'Speed')

        xml.tag('MinimalRebuild', 'true')

        if '/RTC1' in flags or '/RTCsu' in flags:
            xml.tag('BasicRuntimeChecks', 'EnableFastChecks')
        elif '/RTCs' in flags:
            xml.tag('BasicRuntimeChecks', 'StackFrame')
        elif '/RTCu' in flags:
            xml.tag('BasicRuntimeChecks', 'UninitVariables')

        if '/Oy-' in flags:
            xml.tag('OmitFramePointer', 'true')
        if '/EHsc' in flags:
            xml.tag('ExceptionHandling', 'Sync')

        if '/MT' in flags:
            xml.tag('RuntimeLibrary', 'MultiThreaded')
        elif '/MTd' in flags:
            xml.tag('RuntimeLibrary', 'MultiThreadedDebug')
        elif '/MD' in flags:
            xml.tag('RuntimeLibrary', 'MultiThreadedDLL')
        elif '/MDd' in flags:
            xml.tag('RuntimeLibrary', 'MultiThreadedDebugDLL')

        if '/W0' in flags:
            xml.tag('WarningLevel', 'Level0')
        elif '/W1' in flags:
            xml.tag('WarningLevel', 'Level1')
        elif '/W2' in flags:
            xml.tag('WarningLevel', 'Level2')
        elif '/W3' in flags:
            xml.tag('WarningLevel', 'Level3')
        elif '/W4' in flags:
            xml.tag('WarningLevel', 'Level4')

        if '/WX' in flags:
            xml.tag('TreatWarningAsError', 'true')

        if '/Od' in flags:
            xml.tag('DebugInformationFormat', 'EditAndContinue')
        else:
            xml.tag('DebugInformationFormat', 'ProgramDatabase')

        if '/GR-' in flags:
            xml.tag('RuntimeTypeInfo', 'false')
        elif '/GR' in flags:
            xml.tag('RuntimeTypeInfo', 'true')

        with xml.block('PrecompiledHeader'):
            pass
        xml.tag('MultiProcessorCompilation', 'true')

    with xml.block('ResourceCompile'):
        defines = ['%(PreprocessorDefinitions)'
                  ] + compiler.defines + compiler.cxxdefines + compiler.rcdefines
        defines = sanitize_val_defines(defines)
        xml.tag('PreprocessorDefinitions', ';'.join(defines))
        xml.tag('AdditionalIncludeDirectories', ';'.join(includes[1:] + includes[0:1]))

    with xml.block('Link'):
        link_flags = compiler.linkflags + compiler.postlink

        # Parse link flags.
        libs = ['%(AdditionalDependencies)']
        ignore_libs = ['%(IgnoreSpecificDefaultLibraries)']
        machine = 'X86'
        subsystem = 'Windows'
        for flag in link_flags:
            if util.IsString(flag):
                if flag == '/SUBSYSTEM:CONSOLE':
                    subsystem = 'Console'
                    continue

                if '.lib' in flag:
                    libs.append(flag)
                    continue

                m = re.match('/NODEFAULTLIB:(.+)', flag)
                if m is not None:
                    ignore_libs.append(m.group(1))
                    continue

                m = re.match('/MACHINE:(.+)', flag)
                if m is not None:
                    machine = m.group(1)
            else:
                libs.append(Dep.resolve(node.context, builder, flag))

        if '/WX' in link_flags:
            xml.tag('TreatLinkerWarningAsErrors', 'true')

        xml.tag('AdditionalDependencies', ';'.join(libs))
        xml.tag('OutputFile', '$(OutDir)$(TargetFileName)')
        xml.tag('IgnoreSpecificDefaultLibraries', ';'.join(ignore_libs))
        if compiler.symbol_files is None:
            xml.tag('GenerateDebugInformation', 'false')
        else:
            xml.tag('GenerateDebugInformation', 'true')
        if '/OPT:REF' in link_flags:
            xml.tag('OptimizeReferences', 'true')
        elif '/OPT:NOREF' in link_flags:
            xml.tag('OptimizeReferences', 'false')
        if '/OPT:ICF' in link_flags:
            xml.tag('EnableCOMDATFolding', 'true')
        elif '/OPT:NOICF' in link_flags:
            xml.tag('EnableCOMDATFolding', 'true')
        xml.tag('TargetMachine', 'Machine{0}'.format(machine))

def export_source_files(node, xml):
    files = {}
    all_builders = set()
    for builder in node.project.builders_:
        for source in builder.sources:
            file = os.path.join(node.context.currentSourcePath, source)
            builders = files.setdefault(file, set())
            builders.add(builder)
        all_builders.add(builder)

    headers = set()
    for header in node.project.include_hotlist:
        header_path = paths.Join(node.context.currentSourcePath, header)
        header_path = os.path.relpath(header_path, node.context.buildFolder)
        headers.add(header)

    def emit(file, kind):
        builders = files[file]
        excluded = all_builders - builders

        if len(excluded) == 0:
            xml.tag(kind, Include = file)
            return

        with xml.block(kind, Include = file):
            for builder in excluded:
                xml.tag('ExcludedFromBuild', 'true', Condition = condition_for(builder))

    with xml.block('ItemGroup'):
        for file in files:
            _, ext = os.path.splitext(file)
            if ext != '.rc':
                emit(file, 'ClCompile')

    with xml.block('ItemGroup'):
        for file in files:
            _, ext = os.path.splitext(file)
            if ext == '.rc':
                emit(file, 'ResourceCompile')

    with xml.block('ItemGroup'):
        for header in headers:
            xml.tag('ClInclude', Include = header)
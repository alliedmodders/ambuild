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
from ambuild2 import util
from ambuild2.frontend.v2_2.vs import export_vcxproj

# Project type GUID of a C++ (.vcxproj) project.
VcxprojTypeGuid = '8BC9CEB8-8B4A-11D0-8D11-00A0C91BC942'

def solution_header(vs_version):
    if vs_version <= 10:
        return [
            'Microsoft Visual Studio Solution File, Format Version 11.00', '# Visual Studio 2010'
        ]
    names = {
        11: '# Visual Studio 2012',
        12: '# Visual Studio 2013',
        14: '# Visual Studio 14',
        15: '# Visual Studio 15',
    }
    comment = names.get(vs_version, '# Visual Studio Version {0}'.format(vs_version))
    return ['Microsoft Visual Studio Solution File, Format Version 12.00', comment]

def full_config(builder):
    return '{0}|{1}'.format(builder.tag_, export_vcxproj.get_target_platform(builder))

def normalize_path(cm, path):
    return os.path.normcase(os.path.normpath(os.path.join(cm.buildPath, path)))

# Finds which project, and which of its binaries, each binary links against:
# output nodes in linkdeps or the link flags, or a path to one in the link flags
# (hl2sdk-manifests adds a library both ways).
class Dependencies(object):
    def __init__(self, cm, projects):
        self.cm = cm
        self.outputs = {}
        for node in projects:
            for child in node.children:
                builder = getattr(child, 'builder', None)
                if builder is None:
                    continue
                self.outputs[child] = (node, builder)
                self.outputs[normalize_path(cm, child.path)] = (node, builder)

    def of(self, builder):
        compiler = builder.compiler
        found = []
        for item in compiler.linkflags + compiler.postlink + compiler.linkdeps:
            if util.IsString(item):
                dep = self.outputs.get(normalize_path(self.cm, item))
            else:
                dep = self.outputs.get(item)
            if dep is not None and dep[1] is not builder and dep not in found:
                found.append(dep)
        return found

def export(cm, path, projects):
    projects = sorted(projects, key = lambda node: node.path)
    deps = Dependencies(cm, projects)

    configs = []
    for node in projects:
        for builder in node.project.builders_:
            config = full_config(builder)
            if config not in configs:
                configs.append(config)

    lines = solution_header(cm.generator.vs_version)
    for node in projects:
        project_path = os.path.relpath(os.path.join(cm.buildPath, node.path), os.path.dirname(path))
        lines.append('Project("{{{0}}}") = "{1}", "{2}", "{{{3}}}"'.format(
            VcxprojTypeGuid, node.project.name, project_path.replace('/', '\\'), node.uuid))

        dep_nodes = []
        for builder in node.project.builders_:
            for dep_node, _ in deps.of(builder):
                if dep_node is not node and dep_node not in dep_nodes:
                    dep_nodes.append(dep_node)
        if dep_nodes:
            lines.append('\tProjectSection(ProjectDependencies) = postProject')
            for dep_node in dep_nodes:
                lines.append('\t\t{{{0}}} = {{{0}}}'.format(dep_node.uuid))
            lines.append('\tEndProjectSection')
        lines.append('EndProject')

    lines.append('Global')
    lines.append('\tGlobalSection(SolutionConfigurationPlatforms) = preSolution')
    for config in configs:
        lines.append('\t\t{0} = {0}'.format(config))
    lines.append('\tEndGlobalSection')

    # A solution configuration builds every binary with that configuration, and
    # whatever they link from other projects in its own configuration. Projects
    # not needed by it keep a configuration of theirs but aren't built.
    lines.append('\tGlobalSection(ProjectConfigurationPlatforms) = postSolution')
    for config in configs:
        chosen = {}
        pending = [(node, builder)
                   for node in projects
                   for builder in node.project.builders_
                   if full_config(builder) == config]
        while pending:
            node, builder = pending.pop(0)
            if node in chosen:
                continue
            chosen[node] = builder
            pending += deps.of(builder)

        platform = config.split('|')[1]
        for node in projects:
            builder = chosen.get(node)
            if builder is None:
                same_platform = [
                    other for other in node.project.builders_
                    if export_vcxproj.get_target_platform(other) == platform
                ]
                builder = (same_platform or node.project.builders_)[0]
            lines.append('\t\t{{{0}}}.{1}.ActiveCfg = {2}'.format(node.uuid, config,
                                                                  full_config(builder)))
            if node in chosen:
                lines.append('\t\t{{{0}}}.{1}.Build.0 = {2}'.format(node.uuid, config,
                                                                    full_config(builder)))
    lines.append('\tEndGlobalSection')
    lines.append('\tGlobalSection(SolutionProperties) = preSolution')
    lines.append('\t\tHideSolutionNode = FALSE')
    lines.append('\tEndGlobalSection')
    lines.append('EndGlobal')

    with open(path, 'w', encoding = 'utf-8-sig', newline = '\r\n') as fp:
        fp.write('\n')
        fp.write('\n'.join(lines))
        fp.write('\n')

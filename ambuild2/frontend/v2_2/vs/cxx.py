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
import os, types
from ambuild2 import util
from ambuild2.frontend import paths
from ambuild2.frontend.system import System
from ambuild2.frontend.v2_2.cpp import compiler
from ambuild2.frontend.v2_2.cpp.builders import CppNodes
from ambuild2.frontend.v2_2.cpp.msvc import MSVC
from ambuild2.frontend.v2_2.cpp.vendor import Linker
from ambuild2.frontend.v2_2.vs import export_vcxproj
from ambuild2.frontend.v2_2.vs import nodes
from ambuild2.frontend.version import Version

def GetProjectFileSuffix(version):
    # Assume the compiler version is related to the IDE version.
    if version >= 'msvc-1600':
        return '.vcxproj'
    if version >= 'msvc-1300':
        return '.vcproj'
    raise Exception('Unhandled version: {0}'.format(version))

class Project(object):
    def __init__(self, ctor, name):
        self.ctor_ = ctor
        self.name = name
        self.sources = []
        self.include_hotlist = []
        self.builders_ = []

    def Configure(self, compiler, name, tag):
        builder = self.ctor_(self, compiler.clone(), name, tag)
        builder.sources = self.sources[:]
        builder.include_hotlist = self.include_hotlist[:]
        self.builders_ += [builder]
        return builder

    def default(self, compiler):
        # Attach finish/generate methods to this builder, so it generates a
        # projeet file. This is a wrapper around the older API which does not
        # wrap binaries in projects.
        builder = self.Configure(compiler, self.name, 'Default')
        builder.finish = self.finish
        builder.generate = lambda generator, cx: self.generate(generator, cx)[0]
        return builder

    def finish(self, cx):
        pass

    def generate(self, generator, cx):
        if generator.cm.options.vs_split:
            return self.generate_split(generator, cx)
        return self.generate_combined(generator, cx)

    def generate_split(self, generator, cx):
        outputs = []
        for builder in self.builders_:
            project = Project(self.ctor_, builder.name_)
            project.sources = self.sources[:]
            project.builders_ = [builder]
            outputs += project.generate_combined(generator, cx)
        return outputs

    def generate_combined(self, generator, cx):
        outputs = []
        proj_path = paths.Join(cx.localFolder,
                               self.name + GetProjectFileSuffix(generator.vs_vendor.version))
        # A project of this name may already be in this folder: a script run once per
        # architecture, like hl2sdk-manifests does with an SDK's libraries, makes one each
        # time. Its configurations go into the same project file.
        node = generator.findProjectNode(proj_path)
        if node is None:
            node = nodes.ProjectNode(cx, proj_path, self)
            generator.addProjectNode(cx, node)
        else:
            node.project.mergeFrom(cx, node, self)
        for builder in self.builders_:
            tag_folder = generator.addFolder(cx, builder.localFolder)
            objFile = paths.Join(tag_folder, builder.outputFile)
            pdbFile = paths.Join(tag_folder, builder.name_ + '.pdb')
            objNode = generator.addOutput(cx, objFile, node)
            # The solution maps a binary a project links back to the builder making it.
            objNode.builder = builder
            pdbNode = generator.addOutput(cx, pdbFile, node)
            outputs.append(CppNodes(objNode, pdbNode, builder.type, builder.compiler.target))
        return outputs

    def mergeFrom(self, cx, node, other):
        if cx.currentSourcePath != node.context.currentSourcePath:
            raise Exception('Project {0} already exists for {1}'.format(
                node.path, node.context.currentSourcePath))
        for builder in other.builders_:
            for existing in self.builders_:
                if existing.tag_ == builder.tag_ and \
                   existing.compiler.target.arch == builder.compiler.target.arch:
                    raise Exception('Project {0} already has configuration {1} ({2})'.format(
                        node.path, builder.tag_, builder.compiler.target.arch))
            # One-off binaries of the same name and tag share a folder, so the one
            # merged in gets its architecture in the folder name.
            if any(existing.localFolder == builder.localFolder for existing in self.builders_):
                builder.localFolderSuffix_ = builder.compiler.target.arch
                if any(existing.localFolder == builder.localFolder for existing in self.builders_):
                    raise Exception('Project {0} already has folder {1}'.format(
                        node.path, builder.localFolder))
        self.builders_ += other.builders_
        for header in other.include_hotlist:
            if header not in self.include_hotlist:
                self.include_hotlist.append(header)

    def export(self, cm, node):
        export_vcxproj.export(cm, node)

class VisualStudio(MSVC):
    def __init__(self, version):
        super(VisualStudio, self).__init__(version)

    def like(self, name):
        return name == 'vs' or name == 'msvc'

class VsLinker(Linker):
    def __init__(self):
        super(VsLinker, self).__init__()

    def like(self, name):
        return name == 'msvc'

class Compiler(compiler.Compiler):
    def __init__(self, vendor, target_arch = 'x86'):
        target = System('windows', target_arch)
        super(Compiler, self).__init__(vendor, target)
        self.linker = VsLinker()

    def clone(self):
        cc = Compiler(self.vendor, self.target.arch)
        cc.inherit(self)
        return cc

    @staticmethod
    def GetVersionFromVS(vs_version):
        vs_version = int(vs_version)
        msvc_version = (vs_version * 100) + 600

        # Microsoft skipped version 13, of course.
        if vs_version >= 14:
            msvc_version -= 100
        # Since VS 2017, the numbering continues from 1910 with increments of 10.
        if vs_version >= 15:
            msvc_version = 1900 + (vs_version - 14) * 10
        return msvc_version

    def Program(self, name):
        return Project(Program, name).default(self)

    def Library(self, name):
        return Project(Library, name).default(self)

    def StaticLibrary(self, name):
        return Project(StaticLibrary, name).default(self)

    def PrecompiledHeaders(self, name, source_type):
        return PrecompiledHeaders(self, name)

    def like(self, name):
        return name == 'msvc'

class BinaryBuilder(object):
    def __init__(self, project, compiler, name, tag):
        super(BinaryBuilder, self).__init__()
        self.project_ = project
        self.compiler = compiler
        self.sources = []
        self.include_hotlist = []
        self.name_ = name
        self.tag_ = tag
        self.localFolderSuffix_ = None

    @property
    def localFolder(self):
        # If this is a one-off binary, we need to make sure its folder name won't
        # create conflicts.
        if hasattr(self, 'generate'):
            folder = '{0} - {1}'.format(self.name_, self.tag_)
        else:
            # Otherwise - we basically expect one project per context.
            folder = self.tag_
        if self.localFolderSuffix_:
            folder = '{0} - {1}'.format(folder, self.localFolderSuffix_)
        return folder

    @property
    def outputFile(self):
        return self.buildOutputName(self.name_)

    def Module(self, context, name):
        return self

class Program(BinaryBuilder):
    def __init__(self, project, compiler, name, tag):
        super(Program, self).__init__(project, compiler, name, tag)

    @staticmethod
    def buildOutputName(name):
        return '{0}.exe'.format(name)

    @property
    def type(self):
        return 'program'

    @property
    def configurationType(self):
        return 'Application'

class Library(BinaryBuilder):
    def __init__(self, project, compiler, name, tag):
        super(Library, self).__init__(project, compiler, name, tag)

    @staticmethod
    def buildOutputName(name):
        return '{0}.dll'.format(name)

    @property
    def type(self):
        return 'library'

    @property
    def configurationType(self):
        return 'DynamicLibrary'

class StaticLibrary(BinaryBuilder):
    def __init__(self, project, compiler, name, tag):
        super(StaticLibrary, self).__init__(project, compiler, name, tag)

    @staticmethod
    def buildOutputName(name):
        return '{0}.lib'.format(name)

    @property
    def type(self):
        return 'static'

    @property
    def configurationType(self):
        return 'StaticLibrary'

class PchNodes(object):
    def __init__(self, name, sources):
        self.name = name
        self.sources = sources

class PrecompiledHeaders(BinaryBuilder):
    def __init__(self, compiler, name):
        self.compiler = compiler
        self.name_ = name
        self.sources = []

    def finish(self, cx):
        pass

    def generate(self, generator, cx):
        return PchNodes(self.name_, self.sources)

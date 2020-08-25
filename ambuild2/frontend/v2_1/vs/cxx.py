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
from ambuild2.frontend.version import Version
from ambuild2.frontend.v2_1.vs import nodes
from ambuild2.frontend.v2_1.vs import export_vcxproj
from ambuild2.frontend.v2_1.cpp import compiler
from ambuild2.frontend.v2_1.cpp import Dep, CppNodes
from ambuild2.frontend.v2_1.cpp.msvc import MSVC

class Project(object):
    def __init__(self, ctor, compiler, name):
        self.ctor_ = ctor
        self.name_ = name
        self.compiler = compiler
        self.sources = []
        self.builders_ = []

    def Configure(self, name, tag):
        compiler = self.compiler.clone()
        builder = self.ctor_(self, compiler, name, tag)
        builder.sources = self.sources[:]
        self.builders_ += [builder]
        return builder

    def default(self):
        # Attach finish/generate methods to this builder, so it generates a
        # projeet file. This is a wrapper around the older API which does not
        # wrap binaries in projects.
        builder = self.Configure(self.name_, 'Default')
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
            project = Project(self.ctor_, self.compiler, builder.name_)
            project.sources = self.sources[:]
            project.builders_ = [builder]
            outputs += project.generate_combined(generator, cx)
        return outputs

    def generate_combined(self, generator, cx):
        outputs = []
        proj_path = paths.Join(cx.localFolder, self.name_ + self.compiler.projectFileSuffix)
        node = nodes.ProjectNode(cx, proj_path, self)
        for builder in self.builders_:
            tag_folder = generator.addFolder(cx, builder.localFolder)
            objFile = paths.Join(tag_folder, builder.outputFile)
            pdbFile = paths.Join(tag_folder, builder.name_ + '.pdb')
            objNode = generator.addOutput(cx, objFile, node)
            pdbNode = generator.addOutput(cx, pdbFile, node)
            outputs.append(CppNodes(objNode, pdbNode, builder.type))
        generator.addProjectNode(cx, node)
        return outputs

    def export(self, cm, node):
        export_vcxproj.export(node)

class VisualStudio(MSVC):
    def __init__(self, version):
        super(VisualStudio, self).__init__(version)

    def like(self, name):
        return name == 'vs' or name == 'msvc'

class Compiler(compiler.Compiler):
    def __init__(self, vendor):
        super(Compiler, self).__init__(vendor)

    def clone(self):
        cc = Compiler(self.vendor)
        cc.inherit(self)
        return cc

    @property
    def projectFileSuffix(self):
        # Assume the compiler version is related to the IDE version.
        if self.version >= 'msvc-1600':
            return '.vcxproj'
        if self.version >= 'msvc-1300':
            return '.vcproj'
        raise Exception('Unhandled version: {0}'.format(self.version))

    @staticmethod
    def GetVersionFromVS(vs_version):
        vs_version = int(vs_version)
        msvc_version = (vs_version * 100) + 600

        # Microsoft skipped version 13, of course.
        if vs_version >= 14:
            msvc_version -= 100
        # In VS 2017, the numbering continues from 1910
        if vs_version == 15:
            msvc_version = 1910
        return msvc_version

    def ProgramProject(self, name):
        return Project(Program, self, name)

    def LibraryProject(self, name):
        return Project(Library, self, name)

    def StaticLibraryProject(self, name):
        return Project(StaticLibrary, self, name)

    def Program(self, name):
        return Project(Program, self, name).default()

    def Library(self, name):
        return Project(Library, self, name).default()

    def StaticLibrary(self, name):
        return Project(StaticLibrary, self, name).default()

    def like(self, name):
        return name == 'msvc'

class BinaryBuilder(object):
    def __init__(self, project, compiler, name, tag):
        super(BinaryBuilder, self).__init__()
        self.project_ = project
        self.compiler = compiler
        self.sources = []
        self.name_ = name
        self.tag_ = tag

    def Dep(self, text, node = None):
        return Dep(text, node)

    @property
    def localFolder(self):
        # If this is a one-off binary, we need to make sure its folder name won't
        # create conflicts.
        if hasattr(self, 'generate'):
            return '{0} - {1}'.format(self.name_, self.tag_)

        # Otherwise - we basically expect one project per context.
        return self.tag_

    @property
    def outputFile(self):
        return self.buildOutputName(self.name_)

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

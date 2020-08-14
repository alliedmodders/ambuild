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
import subprocess
import re, os
from ambuild2 import nodetypes
from ambuild2 import util

class CppNodes(object):
    def __init__(self, output, debug_outputs):
        self.binary = output
        self.debug = debug_outputs

# Poor abstraction - vendor object should encapsulate logic to avoid instanceof
# checks. For now, we just import the name.
from ambuild2.frontend.v2_0.cpp.vendors import MSVC, CompatGCC, Emscripten

class Dep(object):
    def __init__(self, text, node):
        self.text = text
        self.node = node

    @staticmethod
    def resolve(cx, builder, item):
        if type(item) is Dep:
            # If the dep is a file dependency (no node attached), and has a relative
            # path, make it absolute so the linker knows where to look.
            if item.node is None and not os.path.isabs(item.text):
                return os.path.join(cx.currentSourcePath, item.text)
            return item.text

        if hasattr(item, 'path'):
            if os.path.isabs(item.path):
                return item.path

            local_path = os.path.join(cx.buildFolder, builder.localFolder)
            return os.path.relpath(item.path, local_path)

        return item

class BuilderProxy(object):
    def __init__(self, builder, compiler, name):
        self.constructor_ = builder.constructor_
        self.sources = builder.sources[:]
        self.compiler = compiler
        self.name_ = name

    @property
    def outputFile(self):
        return self.constructor_.buildName(self.compiler, self.name_)

    @property
    def localFolder(self):
        return self.name_

    @property
    def type(self):
        return self.constructor_.type

    @staticmethod
    def Dep(text, node = None):
        return Dep(text, node)

class Project(object):
    def __init__(self, constructor, compiler, name):
        super(Project, self).__init__()
        self.constructor_ = constructor
        self.compiler = compiler
        self.name = name
        self.sources = []
        self.proxies_ = []
        self.builders_ = []

    def finish(self, cx):
        for task in self.proxies_:
            builder = task.constructor_(task.compiler, task.name_)
            builder.sources = task.sources
            builder.finish(cx)
            self.builders_.append(builder)

    def generate(self, generator, cx):
        outputs = []
        for builder in self.builders_:
            outputs += [builder.generate(generator, cx)]
        return outputs

    def Configure(self, name, tag):
        compiler = self.compiler.clone()
        proxy = BuilderProxy(self, compiler, name)
        self.proxies_.append(proxy)
        return proxy

# Environment representing a C/C++ compiler invocation. Encapsulates most
# arguments.
class ArgBuilder(object):
    def __init__(self, outputPath, config, compiler):
        args = compiler.command.split(' ')
        args += config.cflags
        if config.debug_symbols:
            args += compiler.debuginfo_argv
        if compiler == config.cxx:
            args += config.cxxflags
        else:
            args += config.c_only_flags
        args += [compiler.definePrefix + define for define in config.defines]
        if compiler == config.cxx:
            args += [compiler.definePrefix + define for define in config.cxxdefines]
        for include in config.includes:
            args += compiler.formatInclude(outputPath, include)
        if compiler == config.cxx:
            for include in config.cxxincludes:
                args += compiler.formatInclude(outputPath, include)
        self.argv = args
        self.compiler = compiler

def NameForObjectFile(file):
    return re.sub('[^a-zA-Z0-9_]+', '_', os.path.splitext(file)[0])

class ObjectFile(object):
    def __init__(self, sourceFile, outputFile, argv, sharedOutputs):
        self.sourceFile = sourceFile
        self.outputFile = outputFile
        self.argv = argv
        self.sharedOutputs = sharedOutputs

class RCFile(object):
    def __init__(self, sourceFile, preprocFile, outputFile, cl_argv, rc_argv):
        self.sourceFile = sourceFile
        self.preprocFile = preprocFile
        self.outputFile = outputFile
        self.cl_argv = cl_argv
        self.rc_argv = rc_argv

class BinaryBuilder(object):
    def __init__(self, compiler, name):
        super(BinaryBuilder, self).__init__()
        self.compiler = compiler
        self.sources = []
        self.name_ = name
        self.used_cxx_ = False
        self.linker_ = None

    @property
    def outputFile(self):
        return self.buildName(self.compiler, self.name_)

    def generate(self, generator, cx):
        folder_node = generator.generateFolder(cx.localFolder, self.localFolder)

        # Find dependencies
        inputs = []
        generator.parseCxxDeps(cx, self, inputs, self.compiler.linkflags)
        generator.parseCxxDeps(cx, self, inputs, self.compiler.postlink)

        for objfile in self.objects:
            cxxData = {'argv': objfile.argv, 'type': self.linker.behavior}
            cxxCmd, (cxxNode,) = generator.addCommand(context = cx,
                                                      weak_inputs = self.compiler.sourcedeps,
                                                      inputs = [objfile.sourceFile],
                                                      outputs = [objfile.outputFile],
                                                      node_type = nodetypes.Cxx,
                                                      folder = folder_node,
                                                      data = cxxData,
                                                      shared_outputs = objfile.sharedOutputs)
            inputs.append(cxxNode)
        for rcfile in self.resources:
            rcData = {
                'cl_argv': rcfile.cl_argv,
                'rc_argv': rcfile.rc_argv,
            }
            rcCmd, (preprocNode, rcNode) = generator.addCommand(
                context = cx,
                weak_inputs = self.compiler.sourcedeps,
                inputs = [rcfile.sourceFile],
                outputs = [rcfile.preprocFile, rcfile.outputFile],
                node_type = nodetypes.Rc,
                folder = folder_node,
                data = rcData)
            inputs.append(rcNode)

        output_file, debug_file = self.link(context = cx, folder = folder_node, inputs = inputs)

        return CppNodes(output_file, debug_file)

    # Make an item that can be passed into linkflags/postlink but has an attached
    # dependency.
    def Dep(self, text, node = None):
        return Dep(text, node)

    # The folder we'll be in, relative to our build context.
    @property
    def localFolder(self):
        return self.name_

    # Exposed only for frontends.
    @property
    def linker(self):
        return self.linker_

    # Compute the build folder.
    def getBuildFolder(self, builder):
        return os.path.join(builder.buildFolder, self.localFolder)

    def linkFlags(self, cx):
        argv = [Dep.resolve(cx, self, item) for item in self.compiler.linkflags]
        argv += [Dep.resolve(cx, self, item) for item in self.compiler.postlink]
        return argv

    def finish(self, cx):
        # Because we want to compute relative include folders for MSVC (see its
        # vendor object), we need to compute an absolute path to the build folder.
        self.outputFolder = self.getBuildFolder(cx)
        self.outputPath = os.path.join(cx.buildPath, self.outputFolder)
        self.default_c_env = ArgBuilder(self.outputPath, self.compiler, self.compiler.cc)
        self.default_cxx_env = ArgBuilder(self.outputPath, self.compiler, self.compiler.cxx)

        shared_cc_outputs = []
        if self.compiler.debug_symbols and self.compiler.cc.behavior == 'msvc':
            cl_version = (int(int(self.compiler.cc.version) / 100) - 6) * 10
            if cl_version >= 130:
                cl_version += 10
            shared_pdb = 'vc{0}.pdb'.format(cl_version)
            shared_cc_outputs += [shared_pdb]

        self.objects = []
        self.resources = []
        for item in self.sources:
            if os.path.isabs(item):
                sourceFile = item
            else:
                sourceFile = os.path.join(cx.currentSourcePath, item)
            sourceFile = os.path.normpath(sourceFile)

            filename, extension = os.path.splitext(item)
            encname = NameForObjectFile(filename)

            if extension == '.rc':
                cenv = self.default_c_env
                objectFile = encname + '.res'
            else:
                if extension == '.c':
                    cenv = self.default_c_env
                else:
                    cenv = self.default_cxx_env
                    self.used_cxx_ = True
                objectFile = encname + cenv.compiler.objSuffix

            if extension == '.rc':
                # This is only relevant on Windows.
                vendor = cenv.compiler
                defines = self.compiler.defines + self.compiler.cxxdefines + self.compiler.rcdefines
                cl_argv = vendor.command.split(' ')
                cl_argv += [vendor.definePrefix + define for define in defines]
                for include in (self.compiler.includes + self.compiler.cxxincludes):
                    cl_argv += vendor.formatInclude(objectFile, include)
                cl_argv += vendor.preprocessArgs(sourceFile, encname + '.i')

                rc_argv = ['rc', '/nologo']
                for define in defines:
                    rc_argv.extend(['/d', define])
                for include in (self.compiler.includes + self.compiler.cxxincludes):
                    rc_argv.extend(['/i', MSVC.IncludePath(objectFile, include)])
                rc_argv.append('/fo' + objectFile)
                rc_argv.append(sourceFile)

                self.resources.append(
                    RCFile(sourceFile, encname + '.i', objectFile, cl_argv, rc_argv))
            else:
                argv = cenv.argv + cenv.compiler.objectArgs(sourceFile, objectFile)
                obj = ObjectFile(sourceFile, objectFile, argv, shared_cc_outputs)
                self.objects.append(obj)

        if not self.linker_:
            if self.used_cxx_:
                self.linker_ = self.compiler.cxx
            else:
                self.linker_ = self.compiler.cc

        files = [out.outputFile for out in self.objects + self.resources]
        self.argv = self.generateBinary(cx, files)
        self.linker_outputs = [self.outputFile]
        self.debug_entry = None

        if self.linker_.behavior == 'msvc':
            if isinstance(self, Library):
                # In theory, .dlls should have exports, so MSVC will generate these
                # files. If this turns out not to be true, we may have to get fancier.
                self.linker_outputs += [self.name_ + '.lib']
                self.linker_outputs += [self.name_ + '.exp']

        if self.compiler.debug_symbols == 'separate':
            self.perform_symbol_steps(cx)

    def perform_symbol_steps(self, cx):
        if isinstance(self.linker_, MSVC):
            # Note, pdb is last since we read the pdb as outputs[-1].
            self.linker_outputs += [self.name_ + '.pdb']
        elif cx.target_platform == 'mac':
            bundle_folder = os.path.join(self.localFolder, self.outputFile + '.dSYM')
            bundle_entry = cx.AddFolder(bundle_folder)
            bundle_layout = [
                'Contents',
                'Contents/Resources',
                'Contents/Resources/DWARF',
            ]
            for folder in bundle_layout:
                cx.AddFolder(os.path.join(bundle_folder, folder))
            self.linker_outputs += [
                self.outputFile + '.dSYM/Contents/Info.plist',
                self.outputFile + '.dSYM/Contents/Resources/DWARF/' + self.outputFile
            ]
            self.debug_entry = bundle_entry
            self.argv = ['ambuild_dsymutil_wrapper.sh', self.outputFile] + self.argv
        elif cx.target_platform == 'linux':
            self.linker_outputs += [self.outputFile + '.dbg']
            self.argv = ['ambuild_objcopy_wrapper.sh', self.outputFile] + self.argv

    def link(self, context, folder, inputs):
        # The existence of .ilk files on Windows does not seem reliable, so we
        # treat it as "shared" which does not participate in the DAG (yet).
        shared_outputs = []
        if self.linker_.behavior == 'msvc':
            if not isinstance(self, StaticLibrary) and '/INCREMENTAL:NO' not in self.argv:
                shared_outputs += [self.name_ + '.ilk']

        ignore, outputs = context.AddCommand(inputs = inputs,
                                             argv = self.argv,
                                             outputs = self.linker_outputs,
                                             folder = folder,
                                             shared_outputs = shared_outputs)
        if not self.debug_entry and self.compiler.debug_symbols:
            if self.linker_.behavior != 'msvc' and self.compiler.debug_symbols == 'bundled':
                self.debug_entry = outputs[0]
            else:
                self.debug_entry = outputs[-1]
        return outputs[0], self.debug_entry

class Program(BinaryBuilder):
    def __init__(self, compiler, name):
        super(Program, self).__init__(compiler, name)

    @staticmethod
    def buildName(compiler, name):
        return compiler.nameForExecutable(name)

    @property
    def type(self):
        return 'program'

    def generateBinary(self, cx, files):
        argv = self.linker_.command.split(' ')
        argv += files

        if isinstance(self.linker_, MSVC):
            argv.append('/link')
            argv.extend(self.linkFlags(cx))
            argv.append('/nologo')
            argv += [
                '/OUT:' + self.outputFile,
                '/nologo',
            ]
            if self.compiler.debug_symbols:
                argv += ['/DEBUG', '/PDB:"' + self.name_ + '.pdb"']
        else:
            argv.extend(self.linkFlags(cx))
            argv.extend(['-o', self.outputFile])

        return argv

class Library(BinaryBuilder):
    def __init__(self, compiler, name):
        super(Library, self).__init__(compiler, name)

    @staticmethod
    def buildName(compiler, name):
        return compiler.nameForSharedLibrary(name)

    @property
    def type(self):
        return 'library'

    def generateBinary(self, cx, files):
        argv = self.linker_.command.split(' ')
        argv += files

        if isinstance(self.linker_, MSVC):
            argv.append('/link')
            argv.extend(self.linkFlags(cx))
            argv += [
                '/OUT:' + self.outputFile,
                '/DEBUG',
                '/nologo',
                '/DLL',
            ]
            if self.compiler.debug_symbols:
                argv += ['/DEBUG', '/PDB:"' + self.name_ + '.pdb"']
        elif isinstance(self.linker_, CompatGCC):
            argv.extend(self.linkFlags(cx))
            if util.IsMac():
                argv.append('-dynamiclib')
            else:
                argv.append('-shared')
            argv.extend(['-o', self.outputFile])

        return argv

class StaticLibrary(BinaryBuilder):
    def __init__(self, compiler, name):
        super(StaticLibrary, self).__init__(compiler, name)

    @staticmethod
    def buildName(compiler, name):
        return compiler.nameForStaticLibrary(name)

    @property
    def type(self):
        return 'static'

    def generateBinary(self, cx, files):
        if isinstance(self.linker_, MSVC):
            argv = ['lib.exe', '/OUT:' + self.outputFile]
        elif isinstance(self.linker_, Emscripten):
            argv = ['llvm-ar', 'rcs', self.outputFile]
        else:
            argv = ['ar', 'rcs', self.outputFile]
        argv += files
        return argv

    def perform_symbol_steps(self, cx):
        pass

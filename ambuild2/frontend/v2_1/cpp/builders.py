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
from ambuild2 import util
from ambuild2.frontend import paths

class CppNodes(object):
    def __init__(self, output, debug_outputs, type):
        self.binary = output
        self.debug = debug_outputs
        self.type = type

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
        self.custom = builder.custom[:]
        self.compiler = compiler
        self.name_ = name
        self.localFolder = name

    @property
    def outputFile(self):
        return self.constructor_.buildName(self.compiler, self.name_)

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
        self.custom = []

    def finish(self, cx):
        for task in self.proxies_:
            builder = task.constructor_(task.compiler, task.name_)
            builder.localFolder = task.localFolder
            builder.sources = task.sources
            builder.custom = task.custom
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

def NameForObjectFile(file):
    return re.sub('[^a-zA-Z0-9_]+', '_', os.path.splitext(file)[0])

class ObjectFileBase(object):
    def __init__(self, parent, inputObj, outputFile):
        super(ObjectFileBase, self).__init__()
        self.env_data = parent.env_data
        self.folderNode = parent.localFolderNode
        self.inputObj = inputObj
        self.outputFile = outputFile
        self.sourcedeps = parent.sourcedeps

    @property
    def type(self):
        raise Exception("Must be implemented!")

class ObjectFile(ObjectFileBase):
    def __init__(self, parent, inputObj, outputFile, argv):
        super(ObjectFile, self).__init__(parent, inputObj, outputFile)
        self.argv = argv
        self.behavior = parent.compiler.vendor.behavior

    @property
    def type(self):
        return 'object'

class RCFile(ObjectFileBase):
    def __init__(self, parent, inputObj, preprocFile, outputFile, cl_argv, rc_argv):
        super(RCFile, self).__init__(parent, inputObj, outputFile)
        self.preprocFile = preprocFile
        self.cl_argv = cl_argv
        self.rc_argv = rc_argv

    @property
    def type(self):
        return 'resource'

class ObjectArgvBuilder(object):
    def __init__(self):
        super(ObjectArgvBuilder, self).__init__()
        self.outputFolder = None
        self.outputPath = None
        self.localFolderNode = None
        self.vendor = None
        self.compiler = None
        self.cc_argv = None
        self.cxx_argv = None
        self.objects = []
        self.resources = []
        self.used_cxx = False
        self.has_code = False
        self.sourcedeps = []
        self.env_data = None

    def setOutputs(self, localFolderNode, outputFolder, outputPath):
        self.outputFolder = outputFolder
        self.outputPath = outputPath
        self.localFolderNode = localFolderNode

    def setCompiler(self, compiler, addl_include_dirs, addl_source_deps):
        self.vendor = compiler.vendor
        self.compiler = compiler

        # Set up the C compiler argv.
        self.cc_argv = compiler.cc_argv[:]
        self.cc_argv += compiler.cflags
        if compiler.symbol_files is not None:
            self.cc_argv += self.vendor.debugInfoArgv
        self.cc_argv += compiler.c_only_flags
        self.cc_argv += [self.vendor.definePrefix + define for define in compiler.defines]
        for include in compiler.includes + addl_include_dirs:
            self.cc_argv += self.vendor.formatInclude(self.outputPath, include)

        # Set up the C++ compiler argv.
        self.cxx_argv = compiler.cxx_argv[:]
        self.cxx_argv += compiler.cflags
        if compiler.symbol_files is not None:
            self.cxx_argv += self.vendor.debugInfoArgv
        self.cxx_argv += compiler.cxxflags
        self.cxx_argv += [self.vendor.definePrefix + define for define in compiler.defines]
        self.cxx_argv += [self.vendor.definePrefix + define for define in compiler.cxxdefines]
        for include in compiler.includes + compiler.cxxincludes + addl_include_dirs:
            self.cxx_argv += self.vendor.formatInclude(self.outputPath, include)

        self.env_data = compiler.env_data

        # Set up source dependencies.
        self.sourcedeps += compiler.sourcedeps + addl_source_deps

    def buildItem(self, inputObj, sourceName, sourceFile):
        sourceNameSansExtension, extension = os.path.splitext(sourceName)
        encodedName = NameForObjectFile(sourceNameSansExtension)

        if extension == '.rc':
            return self.buildRcItem(inputObj, sourceFile, encodedName)
        return self.buildCxxItem(inputObj, sourceFile, encodedName, extension)

    def buildCxxItem(self, inputObj, sourceFile, encodedName, extension):
        self.has_code = True

        if extension == '.c':
            argv = self.cc_argv[:]
        else:
            argv = self.cxx_argv[:]
            self.used_cxx = True

        objectFile = encodedName + self.vendor.objSuffix
        argv += self.vendor.objectArgs(sourceFile, objectFile)
        return ObjectFile(self, inputObj, objectFile, argv)

    def buildRcItem(self, inputObj, sourceFile, encodedName):
        objectFile = encodedName + '.res'

        defines = self.compiler.defines + self.compiler.cxxdefines + self.compiler.rcdefines
        cl_argv = self.cc_argv[:]
        cl_argv += [self.vendor.definePrefix + define for define in defines]
        for include in (self.compiler.includes + self.compiler.cxxincludes):
            cl_argv += self.vendor.formatInclude(objectFile, include)
        cl_argv += self.vendor.preprocessArgv(sourceFile, encodedName + '.i')

        rc_argv = ['rc', '/nologo']
        for define in defines:
            rc_argv += ['/d', define]
        for include in (self.compiler.includes + self.compiler.cxxincludes):
            rc_argv += ['/i', self.vendor.IncludePath(objectFile, include)]
        rc_argv += ['/fo' + objectFile, sourceFile]

        return RCFile(self, inputObj, encodedName + '.i', objectFile, cl_argv, rc_argv)

def ComputeSourcePath(context, localFolderNode, item):
    # This is a path into the source tree.
    if util.IsString(item):
        if os.path.isabs(item):
            sourceFile = item
        else:
            sourceFile = os.path.join(context.currentSourcePath, item)
        return os.path.normpath(sourceFile)

    # This is a node computed by a previous step. Compute a relative path.
    return os.path.relpath(item.path, localFolderNode.path)

class CustomSource(object):
    def __init__(self, source, weak_deps = None):
        super(CustomSource, self).__init__()
        self.source = source
        self.weak_deps = weak_deps or []

class CustomToolCommand(object):
    def __init__(self, cx, module, localFolderNode, data):
        super(CustomToolCommand, self).__init__()
        self.context = cx
        self.module_ = module
        self.localFolderNode = localFolderNode
        self.data = data
        self.sources = []
        self.sourcedeps = []

    @property
    def compiler(self):
        return self.module_.compiler

    @staticmethod
    def NameForObjectFile(path):
        return NameForObjectFile(path)

    def ComputeSourcePath(self, path):
        return ComputeSourcePath(self.module_.context, self.localFolderNode, path)

    @staticmethod
    def CustomSource(source, weak_deps = None):
        return CustomSource(source, weak_deps or [])

class Module(object):
    def __init__(self, context, compiler, name):
        super(Module, self).__init__()
        self.context = context
        self.compiler = compiler
        self.name = name
        self.sources = []
        self.custom = []

class BinaryBuilder(object):
    def __init__(self, compiler, name):
        super(BinaryBuilder, self).__init__()
        self.compiler = compiler
        self.sources = []
        self.custom = []
        self.name_ = name
        self.used_cxx_ = False
        self.linker_ = None
        self.modules_ = []
        self.localFolder = name
        self.has_code_ = False

    @property
    def outputFile(self):
        return self.buildName(self.compiler, self.name_)

    def generate(self, generator, cx):
        # Find dependencies
        inputs = []
        generator.parseCxxDeps(cx, self, inputs, self.compiler.linkflags)
        generator.parseCxxDeps(cx, self, inputs, self.compiler.postlink)

        # Add object files.
        for obj in self.objects:
            if obj.type == 'object':
                inputs.append(
                    generator.addCxxObjTask(cx, self.shared_cc_outputs, obj.folderNode, obj))
            elif obj.type == 'resource':
                inputs.append(generator.addCxxRcTask(cx, obj.folderNode, obj))

        # Add the link step.
        folder_node = generator.generateFolder(cx.localFolder, self.localFolder)
        output_file, debug_file = self.link(context = cx, folder = folder_node, inputs = inputs)

        return CppNodes(output_file, debug_file, self.type)

    # Make an item that can be passed into linkflags/postlink but has an attached
    # dependency.
    def Dep(self, text, node = None):
        return Dep(text, node)

    # Create a sub-component of the binary.
    def Module(self, context, name):
        module = Module(context = context, compiler = self.compiler.clone(), name = name)
        self.modules_.append(module)
        return module

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

    def buildModules(self, cx):
        for module in self.modules_:
            self.buildModule(cx, module)

    def buildModule(self, cx, module):
        localFolder, outputFolder, outputPath = self.computeModuleFolders(cx, module)
        localFolderNode = cx.AddFolder(localFolder)

        must_include_builddir = False

        # Run custom tools attached to this module.
        addl_source_deps = []
        for custom in module.custom:
            cmd = CustomToolCommand(cx = cx,
                                    module = module,
                                    localFolderNode = localFolderNode,
                                    data = custom)
            custom.tool.evaluate(cmd)

            # Integrate any additional outputs.
            module.sources += cmd.sources
            if cmd.sourcedeps:
                addl_source_deps += cmd.sourcedeps
                must_include_builddir = True

        # If custom tools run, they may place new headers in the objdir. For now
        # we put them implicitly in the include path. We might need to make this
        # explicit (or the path customizable) later.
        if must_include_builddir:
            addl_include_dirs = [outputPath]
        else:
            addl_include_dirs = []

        builder = ObjectArgvBuilder()
        builder.setOutputs(localFolderNode, outputFolder, outputPath)
        builder.setCompiler(module.compiler, addl_include_dirs, addl_source_deps)

        # Parse all source file entries.
        for entry in module.sources:
            if isinstance(entry, CustomSource):
                item = entry.source
                extra_weak_deps = entry.weak_deps
            else:
                item = entry
                extra_weak_deps = None

            sourceFile = ComputeSourcePath(module.context, localFolderNode, item)

            # If the item is a string, use the computed source path as the dependent
            # item. Otherwise, use the raw item, since it's probably an output from
            # a precursor step.
            #
            # For the short-form name, which is used to compute an object file name,
            # we use the given source string. If the item is a dependent step then
            # use the path to its output.
            if util.IsString(item):
                inputObj = sourceFile
                sourceName = item
            else:
                inputObj = item
                sourceName = sourceFile

            # Build the object we pass to the generator. Include any extra source deps
            # if the file has extended requirements.
            obj_item = builder.buildItem(inputObj, sourceName, sourceFile)
            if extra_weak_deps is not None:
                obj_item.sourcedeps += extra_weak_deps

            self.objects.append(obj_item)

        # Propagate the used_cxx bit.
        if builder.used_cxx:
            self.used_cxx_ = True
        if builder.has_code:
            self.has_code_ = True

    def computeModuleFolders(self, cx, module):
        buildBase = self.getBuildFolder(cx)
        buildPath = os.path.join(cx.buildPath, buildBase)

        if module.context.sourceFolder == '' and cx.sourceFolder == '':
            # Special degenerate case that fails os.path.relpath().
            subfolder = ''
        elif paths.IsSubPath(module.context.sourceFolder, cx.sourceFolder):
            # If this module is a subpath of the original context, we use the difference.
            subfolder = os.path.relpath(module.context.sourceFolder, cx.sourceFolder)
            if subfolder == '.':
                subfolder = ''
        else:
            # Otherwise... do our best approximation and use a replica of the source
            # folder path. This is not ideal since we could have a collision, if for
            # example we compile:
            #   toplevel/module1/crab.cc -> toplevel/toplevel.so/module1/crab.o
            #   module1/crab.cc          -> toplevel/toplevel.so/module1/crab.o
            #
            # This is bad organization on the project's part, so hopefully we don't
            # have to make a workaround for it.
            subfolder = module.context.sourceFolder

        # Local is relative to the context of the module. buildFolder is relative
        # to the build root.
        localFolder = os.path.normpath(os.path.join(self.localFolder, subfolder))
        buildFolder = os.path.normpath(os.path.join(buildBase, subfolder))
        buildPath = os.path.normpath(os.path.join(buildPath, subfolder))
        return localFolder, buildFolder, buildPath

    def finish(self, cx):
        # Wrap sources into an initial module.
        root = Module(cx, self.compiler, 'root')
        root.sources = self.sources
        root.custom = self.custom
        self.modules_.insert(0, root)

        # Prep shared outputs.
        self.shared_cc_outputs = []
        if self.compiler.symbol_files and self.compiler.family == 'msvc':
            self.shared_cc_outputs += [self.compiler.vendor.shared_pdb_name]

        # Prep outputs.
        self.objects = []

        # Compute source file argvs.
        self.buildModules(cx)

        if self.used_cxx_:
            self.linker_argv_ = self.compiler.cxx_argv
        else:
            self.linker_argv_ = self.compiler.cc_argv
        self.linker_ = self.compiler.vendor

        # Translate object file paths relative to the link build context. This
        # should never result in ../ appearing in the object path.
        files = []
        localBuildFolder = self.getBuildFolder(cx)
        for obj in self.objects:
            objPath = os.path.join(obj.folderNode.path, obj.outputFile)
            files.append(os.path.relpath(objPath, localBuildFolder))

        self.argv = self.generateBinary(cx, files)
        self.linker_outputs = [self.outputFile]
        self.debug_entry = None

        if self.linker_.behavior == 'msvc':
            if isinstance(self, Library) and self.has_code_:
                # In theory, .dlls should have exports, so MSVC will generate these
                # files. If this turns out not to be true, we may have to get fancier.
                self.linker_outputs += [self.name_ + '.lib']
                self.linker_outputs += [self.name_ + '.exp']

        if self.linker_.like('emscripten'):
            if isinstance(self, Program):
                # This might not be correct if the user is actually still using asm.js,
                # we would need to look for `-s WASM=0` in the linker args to check.
                self.linker_outputs += [self.name_ + '.wasm']

        if self.compiler.symbol_files == 'separate':
            self.perform_symbol_steps(cx)

    def perform_symbol_steps(self, cx):
        if self.linker_.family == 'msvc':
            # Note, pdb is last since we read the pdb as outputs[-1].
            self.linker_outputs += [self.name_ + '.pdb']
        elif cx.target.platform == 'mac':
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
        elif cx.target.platform == 'linux':
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
                                             weak_inputs = self.compiler.weaklinkdeps,
                                             shared_outputs = shared_outputs,
                                             env_data = self.compiler.env_data)
        if not self.debug_entry and self.compiler.symbol_files:
            if self.linker_.behavior != 'msvc' and self.compiler.symbol_files == 'bundled':
                self.debug_entry = outputs[0]
            else:
                self.debug_entry = outputs[-1]
        return outputs[0], self.debug_entry

class Program(BinaryBuilder):
    def __init__(self, compiler, name):
        super(Program, self).__init__(compiler, name)

    @staticmethod
    def buildName(compiler, name):
        return compiler.vendor.nameForExecutable(name)

    @property
    def type(self):
        return 'program'

    def generateBinary(self, cx, files):
        return self.compiler.vendor.programLinkArgv(
            cmd_argv = self.linker_argv_,
            files = files,
            linkFlags = self.linkFlags(cx),
            symbolFile = self.name_ if self.compiler.symbol_files else None,
            outputFile = self.outputFile)

class Library(BinaryBuilder):
    def __init__(self, compiler, name):
        super(Library, self).__init__(compiler, name)

    @staticmethod
    def buildName(compiler, name):
        return compiler.vendor.nameForSharedLibrary(name)

    @property
    def type(self):
        return 'library'

    def generateBinary(self, cx, files):
        return self.compiler.vendor.libLinkArgv(
            cmd_argv = self.linker_argv_,
            files = files,
            linkFlags = self.linkFlags(cx),
            symbolFile = self.name_ if self.compiler.symbol_files else None,
            outputFile = self.outputFile)

class StaticLibrary(BinaryBuilder):
    def __init__(self, compiler, name):
        super(StaticLibrary, self).__init__(compiler, name)

    @staticmethod
    def buildName(compiler, name):
        return compiler.vendor.nameForStaticLibrary(name)

    @property
    def type(self):
        return 'static'

    def generateBinary(self, cx, files):
        return self.linker_.staticLinkArgv(files, self.outputFile)

    def perform_symbol_steps(self, cx):
        pass

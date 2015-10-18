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
  def Dep(text, node=None): 
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
  def __init__(self, outputPath, config, mode):
    vendor = config.vendor

    if mode == 'cc':
      self.argv = config.cc_argv[:]
    elif mode == 'cxx':
      self.argv = config.cxx_argv[:]

    self.argv += config.cflags

    if config.symbol_files is not None:
      self.argv += vendor.debugInfoArgv

    if mode == 'cxx':
      self.argv += config.cxxflags
    else:
      self.argv += config.c_only_flags

    self.argv += [vendor.definePrefix + define for define in config.defines]
    if mode == 'cxx':
      self.argv += [vendor.definePrefix + define for define in config.cxxdefines]

    for include in config.includes:
      self.argv += vendor.formatInclude(outputPath, include)
    if mode == 'cxx':
      for include in config.cxxincludes:
        self.argv += vendor.formatInclude(outputPath, include)

    self.vendor = vendor

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
    return generator.addCxxTasks(cx, self)

  # Make an item that can be passed into linkflags/postlink but has an attached
  # dependency.
  def Dep(self, text, node=None): 
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
    self.default_c_env = ArgBuilder(self.outputPath, self.compiler, 'cc')
    self.default_cxx_env = ArgBuilder(self.outputPath, self.compiler, 'cxx')

    shared_cc_outputs = []
    if self.compiler.symbol_files and self.compiler.family == 'msvc':
      shared_cc_outputs += [self.compiler.vendor.shared_pdb_name()]

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
        objectFile = encname + cenv.vendor.objSuffix

      if extension == '.rc':
        # This is only relevant on Windows.
        vendor = cenv.vendor
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

        self.resources.append(RCFile(sourceFile, encname + '.i', objectFile, cl_argv, rc_argv))
      else:
        argv = cenv.argv + cenv.vendor.objectArgs(sourceFile, objectFile)
        obj = ObjectFile(sourceFile, objectFile, argv, shared_cc_outputs)
        self.objects.append(obj)

    if self.used_cxx_:
      self.linker_argv_ = self.compiler.cxx_argv
    else:
      self.linker_argv_ = self.compiler.cc_argv
    self.linker_ = self.compiler.vendor

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

    if self.compiler.symbol_files == 'separate':
      self.perform_symbol_steps(cx)

  def perform_symbol_steps(self, cx):
    if self.linker_.family == 'msvc':
      # Note, pdb is last since we read the pdb as outputs[-1].
      self.linker_outputs += [self.name_ + '.pdb']
    elif cx.target_platform is 'mac':
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
    elif cx.target_platform is 'linux':
      self.linker_outputs += [
        self.outputFile + '.dbg'
      ]
      self.argv = ['ambuild_objcopy_wrapper.sh', self.outputFile] + self.argv

  def link(self, context, folder, inputs):
    # The existence of .ilk files on Windows does not seem reliable, so we
    # treat it as "shared" which does not participate in the DAG (yet).
    shared_outputs = []
    if self.linker_.behavior == 'msvc':
      if not isinstance(self, StaticLibrary) and '/INCREMENTAL:NO' not in self.argv:
        shared_outputs += [self.name_ + '.ilk']

    ignore, outputs = context.AddCommand(
      inputs = inputs,
      argv = self.argv,
      outputs = self.linker_outputs,
      folder = folder,
      shared_outputs = shared_outputs
    )
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

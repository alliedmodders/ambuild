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
from __future__ import print_function
import subprocess
import re, os, copy
from ambuild2 import util
from version import Version

EnvVars = ['CFLAGS', 'CXXFLAGS', 'CC', 'CXX']

class Vendor(object):
  def __init__(self, name, version, behavior, command, objSuffix):
    self.name = name
    self.version = version
    self.behavior = behavior
    self.command = command
    self.objSuffix = objSuffix
    self.debuginfo_argv = []
    self.extra_props = {}
    self.versionObject = Version(self.version)

class MSVC(Vendor):
  def __init__(self, command, version):
    super(MSVC, self).__init__('msvc', version, 'msvc', command, '.obj')
    self.definePrefix = '/D'
    self.debuginfo_argv = ['/Zi']
    if int(self.version) >= 1800:
      self.debuginfo_argv += ['/FS']

  def like(self, name):
    return name == 'msvc'

  @staticmethod
  def IncludePath(outputPath, includePath):
    # Hack - try and get a relative path because CL, with either 
    # /Zi or /ZI, combined with subprocess, apparently tries and
    # looks for paths like c:\bleh\"c:\bleh" <-- wtf
    # .. this according to Process Monitor
    outputPath = os.path.normcase(outputPath)
    includePath = os.path.normcase(includePath)
    outputDrive = os.path.splitdrive(outputPath)[0]
    includeDrive = os.path.splitdrive(includePath)[0]
    if outputDrive == includeDrive:
      return os.path.relpath(includePath, outputPath)
    return includePath

  def formatInclude(self, outputPath, includePath):
    return ['/I', self.IncludePath(outputPath, includePath)]

  def preprocessArgs(self, sourceFile, outFile):
    return ['/showIncludes', '/nologo', '/P', '/c', sourceFile, '/Fi' + outFile]

  def objectArgs(self, sourceFile, objFile):
    return ['/showIncludes', '/nologo', '/c', sourceFile, '/Fo' + objFile]

class CompatGCC(Vendor):
  def __init__(self, name, command, version):
    super(CompatGCC, self).__init__(name, version, 'gcc', command, '.o')
    parts = version.split('.')
    self.majorVersion = int(parts[0])
    self.minorVersion = int(parts[1])
    self.definePrefix = '-D'

  def formatInclude(self, outputPath, includePath):
    return ['-I', os.path.normpath(includePath)]

  def objectArgs(self, sourceFile, objFile):
    return ['-H', '-c', sourceFile, '-o', objFile]

class GCC(CompatGCC):
  def __init__(self, command, version):
    super(GCC, self).__init__('gcc', command, version)
    self.debuginfo_argv = ['-g3', '-ggdb3']

  def like(self, name):
    return name == 'gcc'

class Clang(CompatGCC):
  def __init__(self, command, version):
    super(Clang, self).__init__('clang', command, version)
    self.debuginfo_argv = ['-g3']

  def like(self, name):
    return name == 'gcc' or name == 'clang'

class SunPro(Vendor):
  def __init__(self, command, version):
    super(SunPro, self).__init__('sun', version, 'sun', command, '.o')
    self.definePrefix = '-D'
    self.debuginfo_argv = ['-g3']

  def formatInclude(self, outputPath, includePath):
    return ['-I', os.path.normpath(includePath)]

  def objectArgs(self, sourceFile, objFile):
    return ['-H', '-c', sourceFile, '-o', objFile]

  def like(self, name):
    return name == 'sun'

def TryVerifyCompiler(env, mode, cmd):
  if util.IsWindows():
    cc = VerifyCompiler(env, mode, cmd, 'msvc')
    if cc:
      return cc
  return VerifyCompiler(env, mode, cmd, 'gcc')

CompilerSearch = {
  'CC': {
    'mac': ['cc', 'clang', 'gcc', 'icc'],
    'windows': ['cl'],
    'default': ['cc', 'gcc', 'clang', 'icc']
  },
  'CXX': {
    'mac': ['c++', 'clang++', 'g++', 'icc'],
    'windows': ['cl'],
    'default': ['c++', 'g++', 'clang++', 'icc']
  }
}

def DetectMicrosoftInclusionPattern(text):
  for line in [raw.strip() for raw in text.split('\n')]:
    m = re.match(r'(.*)\s+([A-Za-z]:\\.*stdio\.h)$', line)
    if m is None:
      continue

    phrase = m.group(1)
    return re.escape(phrase) + r'\s+([A-Za-z]:\\.*)$'

  raise Exception('Could not find compiler inclusion pattern')

def DetectCompilers(env, options):
  cc = DetectCompiler(env, 'CC')
  cxx = DetectCompiler(env, 'CXX')

  # Ensure that the two compilers have the same vendor.
  if type(cc) is not type(cxx):
    message = 'C and C++ compiler vendors are not the same: CC={0}, CXX={1}'
    message = message.format(cc.name, cxx.name)

    util.con_err(util.ConsoleRed, message, util.ConsoleNormal)
    raise Exception(message)

  # Ensure that the two compilers have the same version.
  if cc.version != cxx.version:
    message = 'C and C++ compilers have different versions: CC={0}-{1}, CXX={2}-{3}'
    message = message.format(cc.name, cc.version, cxx.name, cxx.version)

    util.con_err(util.ConsoleRed, message, util.ConsoleNormal)
    raise Exception(message)

  return Compiler(cc, cxx, options)

def DetectCompiler(env, var):
  if var in env:
    trys = [env[var]]
  else:
    if util.Platform() in CompilerSearch[var]:
      trys = CompilerSearch[var][util.Platform()]
    else:
      trys = CompilerSearch[var]['default']
  for i in trys:
    cc = TryVerifyCompiler(env, var, i)
    if cc:
      return cc
  raise Exception('Unable to find a suitable ' + var + ' compiler')

def VerifyCompiler(env, mode, cmd, vendor):
  args = cmd.split(' ')
  if 'CXXFLAGS' in env:
    args.extend(env['CXXFLAGS'])
  if 'CFLAGS' in env:
    args.extend(env['CFLAGS'])
  if mode == 'CXX' and 'CXXFLAGS' in env:
    args.extend(env['CXXFLAGS'])
  if mode == 'CXX':
    filename = 'test.cpp'
  else:
    filename = 'test.c'
  file = open(filename, 'w')
  file.write("""
#include <stdio.h>
#include <stdlib.h>

int main()
{
#if defined __ICC
  printf("icc %d\\n", __ICC);
#elif defined __clang__
# if defined(__clang_major__) && defined(__clang_minor__)
  printf("clang %d.%d\\n", __clang_major__, __clang_minor__);
# else
  printf("clang 1.%d\\n", __GNUC_MINOR__);
# endif
#elif defined __GNUC__
  printf("gcc %d.%d\\n", __GNUC__, __GNUC_MINOR__);
#elif defined _MSC_VER
  printf("msvc %d\\n", _MSC_VER);
#elif defined __TenDRA__
  printf("tendra 0\\n");
#elif defined __SUNPRO_C
  printf("sun %x\\n", __SUNPRO_C);
#elif defined __SUNPRO_CC
  printf("sun %x\\n", __SUNPRO_CC);
#else
#error "Unrecognized compiler!"
#endif
#if defined __cplusplus
  printf("CXX\\n");
#else
  printf("CC\\n");
#endif
  exit(0);
}
""")
  file.close()
  if mode == 'CC':
    executable = 'test' + util.ExecutableSuffix()
  elif mode == 'CXX':
    executable = 'testp' + util.ExecutableSuffix()

  # Make sure the exe is gone.
  if os.path.exists(executable):
    os.unlink(executable)

  # Until we can better detect vendors, don't do this.
  # if vendor == 'gcc' and mode == 'CXX':
  #   args.extend(['-fno-exceptions', '-fno-rtti'])
  args.extend([filename, '-o', executable])

  # For MSVC, we need to detect the inclusion pattern for foreign-language
  # systems.
  if vendor == 'msvc':
    args += ['-nologo', '-showIncludes']

  util.con_out(
    util.ConsoleHeader,
    'Checking {0} compiler (vendor test {1})... '.format(mode, vendor),
    util.ConsoleBlue,
    '{0}'.format(args),
    util.ConsoleNormal
  )
  p = util.CreateProcess(args)
  if p == None:
    print('not found')
    return False
  if util.WaitForProcess(p) != 0:
    print('failed with return code {0}'.format(p.returncode))
    return False

  inclusion_pattern = None
  if vendor == 'msvc':
    inclusion_pattern = DetectMicrosoftInclusionPattern(p.stdoutText)

  exe = util.MakePath('.', executable)
  p = util.CreateProcess([executable], executable = exe)
  if p == None:
    print('failed to create executable')
    return False
  if util.WaitForProcess(p) != 0:
    print('executable failed with return code {0}'.format(p.returncode))
    return False
  lines = p.stdoutText.splitlines()
  if len(lines) != 2:
    print('invalid executable output')
    return False
  if lines[1] != mode:
    print('requested {0} compiler, found {1}'.format(mode, lines[1]))
    return False

  vendor, version = lines[0].split(' ')
  if vendor == 'gcc':
    v = GCC(cmd, version)
  elif vendor == 'clang':
    v = Clang(cmd, version)
  elif vendor == 'msvc':
    v = MSVC(cmd, version)
  elif vendor == 'sun':
    v = SunPro(cmd, version)
  else:
    print('Unknown vendor {0}'.format(vendor))
    return False

  if inclusion_pattern is not None:
    v.extra_props['inclusion_pattern'] = inclusion_pattern

  util.con_out(
    util.ConsoleHeader,
    'found {0} version {1}'.format(vendor, version),
    util.ConsoleNormal
  )
  return v

class Dep(object):
  def __init__(self, text, node):
    self.text = text
    self.node = node

class Compiler(object):
  attrs = [
    'includes',         # C and C++ include paths
    'cxxincludes',      # C++-only include paths
    'cflags',           # C and C++ compiler flags
    'cxxflags',         # C++-only compiler flags
    'defines',          # C and C++ #defines
    'cxxdefines',       # C++-only #defines

    'rcdefines',        # Resource Compiler (RC) defines

    # Link flags. If any members are not strings, they will be interpreted as
    # Dep entries created from BinaryBuilder.
    'linkflags',

    # An array of objects to link, after all link flags have been specified.
    # Entries may either be strings containing a path, or Dep entries created
    # from BinaryBuilder.
    'postlink',

    # An array of nodes which should be weak dependencies on each source
    # compilation command.
    'sourcedeps',
  ]

  def __init__(self, cc, cxx, options = None):
    # Accesssing these attributes through the API is deprecated.
    self.cc = cc
    self.cxx = cxx

    if getattr(options, 'symbol_files', False):
      self.debuginfo = 'separate'
    else:
      self.debuginfo = 'bundled'

    for attr in Compiler.attrs:
      setattr(self, attr, [])

  def clone(self):
    cc = Compiler(self.cc, self.cxx)
    cc.cc = self.cc
    cc.cxx = self.cxx
    cc.debuginfo = self.debuginfo
    for attr in Compiler.attrs:
      setattr(cc, attr, copy.copy(getattr(self, attr)))
    return cc

  @staticmethod
  def Dep(text, node=None):
    return Dep(text, node)

  def Program(self, name):
    return Program(self, name)

  def Library(self, name):
    return Library(self, name)

  def StaticLibrary(self, name):
    return StaticLibrary(self, name)

  # These functions use |cxx|, because we expect the vendors to be the same
  # across |cc| and |cxx|.

  # Returns whether this compiler acts like another compiler. Available names
  # are: msvc, gcc, icc, sun, clang
  def like(self, name):
    return self.cxx.like(name)

  # Returns the vendor name (msvc, gcc, icc, sun, clang)
  @property
  def vendor(self):
    return self.cxx.name

  # Returns the version of the compiler. The return value is an object that
  # can be compared against other versions, for example:
  #
  #  compiler.version >= '4.8.3'
  #
  @property
  def version(self):
    return self.cxx.versionObject

  # Returns a list containing the program name and arguments used to invoke the compiler.
  @property
  def argv(self):
    return self.cxx.command.split(' ')

# Environment representing a C/C++ compiler invocation. Encapsulates most
# arguments.
class CCommandEnv(object):
  def __init__(self, outputPath, config, compiler):
    args = compiler.command.split(' ')
    args += config.cflags
    if config.debuginfo:
      args += compiler.debuginfo_argv
    if compiler == config.cxx:
      args += config.cxxflags
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
  return re.sub('[^a-zA-Z0-9_]+', '_', os.path.splitext(file)[0]);

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
    self.compiler = compiler.clone()
    self.sources = []
    self.name_ = name
    self.used_cxx_ = False
    self.linker_ = None

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

  def linkFlag(self, cx, item):
    if type(item) is Dep:
      # If the dep is a file dependency (no node attached), and has a relative
      # path, make it absolute so the linker knows where to look.
      if item.node is None and not os.path.isabs(item.text):
        return os.path.join(cx.currentSourcePath, item.text)
      return item.text

    if hasattr(item, 'path'):
      if os.path.isabs(item.path):
        return item.path

      local_path = os.path.join(cx.buildFolder, self.localFolder)
      return os.path.relpath(item.path, local_path)

    return item

  def linkFlags(self, cx):
    argv = [self.linkFlag(cx, item) for item in self.compiler.linkflags]
    argv += [self.linkFlag(cx, item) for item in self.compiler.postlink]
    return argv

  def finish(self, cx):
    # Because we want to compute relative include folders for MSVC (see its
    # vendor object), we need to compute an absolute path to the build folder.
    self.outputFolder = self.getBuildFolder(cx)
    self.outputPath = os.path.join(cx.buildPath, self.outputFolder)
    self.default_c_env = CCommandEnv(self.outputPath, self.compiler, self.compiler.cc)
    self.default_cxx_env = CCommandEnv(self.outputPath, self.compiler, self.compiler.cxx)

    shared_cc_outputs = []
    if self.compiler.debuginfo and self.compiler.cc.behavior == 'msvc':
      cl_version = int(self.compiler.cc.version) - 600
      shared_pdb = 'vc{0}.pdb'.format(int(cl_version / 10))
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

        self.resources.append(RCFile(sourceFile, encname + '.i', objectFile, cl_argv, rc_argv))
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

    if self.compiler.debuginfo == 'separate':
      self.perform_symbol_steps(cx)

  def perform_symbol_steps(self, cx):
    if isinstance(self.linker_, MSVC):
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
    if not self.debug_entry and self.compiler.debuginfo:
      if self.linker_.behavior != 'msvc' and self.compiler.debuginfo == 'bundled':
        self.debug_entry = outputs[0]
      else:
        self.debug_entry = outputs[-1]
    return outputs[0], self.debug_entry

class Program(BinaryBuilder):
  def __init__(self, compiler, name):
    super(Program, self).__init__(compiler, name)
    self.outputFile = name + util.ExecutableSuffix()

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
      if self.compiler.debuginfo:
        argv += ['/DEBUG', '/PDB:"' + self.name_ + '.pdb"']
    else:
      argv.extend(self.linkFlags(cx))
      argv.extend(['-o', self.outputFile])

    return argv

class Library(BinaryBuilder):
  def __init__(self, compiler, name):
    super(Library, self).__init__(compiler, name)
    self.outputFile = name + util.SharedLibSuffix()

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
      if self.compiler.debuginfo:
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
    self.outputFile = util.StaticLibPrefix() + name + util.StaticLibSuffix()

  def generateBinary(self, cx, files):
    if isinstance(self.linker_, MSVC):
      argv = ['lib.exe', '/OUT:' + self.outputFile]
    else:
      argv = ['ar', 'rcs', self.outputFile]
    argv += files
    return argv

  def perform_symbol_steps(self, cx):
    pass

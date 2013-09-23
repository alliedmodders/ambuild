# vim: set ts=8 sts=2 sw=2 tw=99 et:
from __future__ import print_function
import re, os, copy
import graph, util
import procman, handlers
import subprocess

class Vendor(object):
  def __init__(self, name, version, command, objSuffix):
    self.name = name
    self.version = version
    self.command = command
    self.objSuffix = objSuffix

class MSVC(Vendor):
  def __init__(self, command, version):
    super(MSVC, self).__init__('msvc', version, command, '.obj')
    self.definePrefix = '/D'

  def formatInclude(self, outputPath, includePath):
    #Hack - try and get a relative path because CL, with either 
    #/Zi or /ZI, combined with subprocess, apparently tries and
    #looks for paths like c:\bleh\"c:\bleh" <-- wtf
    #.. this according to Process Monitor
    outputPath = os.path.normcase(outputPath)
    includePath = os.path.normcase(includePath)
    outputDrive = os.path.splitdrive(outputPath)[0]
    includeDrive = os.path.splitdrive(includePath)[0]
    if outputDrive == includeDrive:
      return ['/I', os.path.relpath(includePath, outputPath)]
    return ['/I', includePath]

  def objectArgs(self, sourceFile, objFile):
    return ['/showIncludes', '/c', sourceFile, '/Fo' + objFile]

class CompatGCC(Vendor):
  def __init__(self, name, command, version):
    super(CompatGCC, self).__init__(name, version, command, '.o')
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

class Clang(CompatGCC):
  def __init__(self, command, version):
    super(Clang, self).__init__('clang', command, version)

def TryVerifyCompiler(cx, env, mode, cmd):
  if util.IsWindows():
    cc = VerifyCompiler(cx, env, mode, cmd, 'msvc')
    if cc:
      return cc
  return VerifyCompiler(cx, env, mode, cmd, 'gcc')

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

def DetectCompiler(cx, env, var):
  if var in env:
    trys = [env[var]]
  else:
    if util.Platform() in CompilerSearch[var]:
      trys = CompilerSearch[var][util.Platform()]
    else:
      trys = CompilerSearch[var]['default']
  for i in trys:
    cc = TryVerifyCompiler(cx, env, var, i)
    if cc:
      return cc
  raise Exception('Unable to find a suitable ' + var + ' compiler')

def VerifyCompiler(cx, env, mode, cmd, vendor):
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

  if vendor == 'gcc' and mode == 'CXX':
    args.extend(['-fno-exceptions', '-fno-rtti'])
  args.extend([filename, '-o', executable])
  print('Checking {0} compiler (vendor test {1})... '.format(mode, vendor), end = '')
  print(args)
  p = util.CreateProcess(args)
  if p == None:
    print('not found')
    return False
  if util.WaitForProcess(p) != 0:
    print('failed with return code {0}'.format(p.returncode))
    return False

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
  else:
    print('Unknown vendor {0}'.format(vendor))
    return False

  print('found {0} version {1}'.format(vendor, version))
  return v

class Compiler(object):
  attrs = ['includes', 'cxxincludes', 'linkflags', 'cflags', 'cxxflags', 'defines', 'cxxdefines']

  def __init__(self, builder, cc, cxx):
    self.cx = builder
    self.cc = cc
    self.cxx = cxx
    for attr in Compiler.attrs:
      setattr(self, attr, [])

  def clone(self):
    cc = Compiler(self.cc, self.cxx)
    cc.cx = self.cx
    cc.cc = self.cc
    cc.cxx = self.cxx
    for attr in Compiler.attrs:
      setattr(self, attr, copy.copy(getattr(cc, attr)))
    return cc

  def Program(self, binary):
    return Program(self, binary)

# Environment representing a C/C++ compiler invocation. Encapsulates most
# arguments.
class CCommandEnv(object):
  def __init__(self, outputPath, config, compiler):
    args = compiler.command.split(' ')
    args += config.cflags
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
    self.argv_ = args
    self.compiler = compiler

  def argv(self, sourceFile, objPath):
    return self.argv_ + self.compiler.objectArgs(sourceFile, objPath)

def NameForObjectFile(file):
  return re.sub('[^a-zA-Z0-9_]+', '_', os.path.splitext(file)[0]);

sReadIncludes = 0
sLookForIncludeGuard = 1
sFoundIncludeGuard = 2
sIgnoring = 3

def ParseGCCDeps(text):
  deps = set()
  strip = False
  new_text = ''

  state = sReadIncludes
  for line in re.split('\n+', text):
    if state == sReadIncludes:
      m = re.match('\.+\s+(.+)\s*$', line)
      if m == None:
        state = sLookForIncludeGuard
      else:
        name = m.groups()[0]
        if os.path.exists(name):
          strip = True
          deps.add(name)
        else:
          state = LookForIncludeGuard
    if state == sLookForIncludeGuard:
      if line.startswith('Multiple include guards may be useful for:'):
        state = sFoundIncludeGuard
        strip = True
      else:
        state = sReadIncludes
        strip = False
    elif state == sFoundIncludeGuard:
      if not line in deps:
        strip = False
        state = sIgnoring
    if not strip and len(line):
      new_text += line + '\n'
  return new_text, deps

def CompileGCC(argv, path):
  p = subprocess.Popen(
      args=argv,
      stdout=subprocess.PIPE,
      stderr=subprocess.PIPE,
      shell=False
  )
  stdout, stderr = p.communicate()
  out = stdout.decode()
  err = stderr.decode()

  new_err, deps = ParseGCCDeps(err)

  if p.returncode != 0:
    return {
      'ok': False,
      'stdout': out,
      'stderr': new_err
    }

  return {
    'ok': True,
    'stdout': out,
    'stderr': new_err,
    'deps': deps
  }

class CxxHandler(handlers.Handler):
  msg_type = 'cxx-c'

  @staticmethod
  def build(process, message):
    cctype = message['type']
    argv = message['argv']
    path = message['path']
    if cctype == 'gcc':
      return CompileGCC(argv, path)

  @staticmethod
  def createTask(cx, builder, node):
    return {
      'path': node.path,
      'argv': node.data['argv'],
      'type': node.data['type'],
    }

  @staticmethod
  def update(cx, dmg_node, node, reply):
    if len(reply['stdout']):
      print(reply['stdout'])
    if len(reply['stderr']):
      print(reply['stderr'])
    if not reply['ok']:
      return False

    raise Exception('egg')

  @staticmethod
  def createNodeData(argv, cctype):
    return {
      'argv': argv,
      'type': cctype,
    }

class LinkHandler(handlers.Handler):
  msg_type = 'cxx-link'

  @staticmethod
  def build(process, message):
    print(message)

  @staticmethod
  def createTask(cx, builder, node):
    return {
      'data': node.data
    }

  @staticmethod
  def createNodeData(binary):
    return None

handlers.Register(CxxHandler)
handlers.Register(LinkHandler)

class BinaryBuilder(graph.NodeBuilder):
  def __init__(self, compiler, binary):
    super(BinaryBuilder, self).__init__()
    self.compiler = compiler
    self.binary = binary
    self.sources = []
    self.sourcePath = compiler.cx.currentSourcePath
    self.outputFolder = compiler.cx.currentOutputFolder

  def generate(self, cx, graph):
    # Construct an absolute path to our output folder.
    outputPath = os.path.join(cx.buildPath, self.outputFolder)

    self.default_c_env = CCommandEnv(outputPath, self.compiler, self.compiler.cc)
    self.default_cxx_env = CCommandEnv(outputPath, self.compiler, self.compiler.cxx)

    binPath = os.path.join(self.outputFolder, self.binary)
    data = LinkHandler.createNodeData(self.binary)
    binNode = graph.addNode(LinkHandler, binPath, data)

    for item in self.sources:
      objNode = self.generateItem(cx, graph, item)
      graph.addDependency(binNode, objNode)

  def generateItem(self, cx, graph, item):
    fparts = os.path.splitext(item)

    if fparts[1] == 'c':
      cenv = self.default_c_env
    else:
      cenv = self.default_cxx_env

    if isinstance(cenv.compiler, MSVC):
      cctype = 'msvc'
    else:
      cctype = 'gcc'

    # Find or add node for the source input file.
    sourcePath = os.path.join(self.sourcePath, item);
    objName = NameForObjectFile(fparts[0]) + cenv.compiler.objSuffix
    objPath = os.path.join(self.outputFolder, objName)
    argv = cenv.argv(sourcePath, objName)

    data = CxxHandler.createNodeData(argv, cctype)
    objNode = graph.addNode(CxxHandler, objPath, data)
    graph.addDependency(objNode, sourcePath)
    return objNode

class Program(BinaryBuilder):
  def __init__(self, compiler, binary):
    super(Program, self).__init__(compiler, binary)


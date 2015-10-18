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
import sys, copy
from ambuild2 import util
from ambuild2.frontend.system import System

# AMBuild 2 scripts are parsed recursively. Each script is supplied with a
# "builder" object, which maps to a Context object. Each script gets its own
# context. The context describes the parent build file generator, the local
# input and output folders, and the global compiler that was detected in the
# root script (if any).
#
# Contexts form a tree that matches the build script hierarchy. This can be
# utilized by backends for minimal reparsing and DAG updates when build
# scripts change.

class ConfigureException(Exception):
  def __init__(self, *args, **kwargs):
    super(ConfigureException, self).__init__(*args, **kwargs)

class Context(object):
  def __init__(self, generator, parent, script):
    self.generator = generator
    self.parent = parent
    self.script = script
    self.compiler = None

    if parent:
      self.compiler = parent.compiler.clone()

    # By default, all generated files for a build script are placed in a path
    # matching its layout in the source tree.
    path, name = os.path.split(script)
    if parent:
      self.currentSourcePath = os.path.join(parent.currentSourcePath, path)
      self.currentSourceFolder = os.path.join(parent.currentSourceFolder, path)
      self.buildFolder = os.path.join(parent.buildFolder, path)
    else:
      self.currentSourcePath = generator.sourcePath
      self.currentSourceFolder = ''
      self.buildFolder = ''
    self.buildScript = os.path.join(self.currentSourceFolder, name)
    self.localFolder_ = self.buildFolder

  # Root source folder.
  @property
  def sourcePath(self):
    return self.generator.sourcePath

  @property
  def options(self):
    return self.generator.options

  @property
  def buildPath(self):
    return self.generator.buildPath

  # In build systems with dependency graphs, this can return a node
  # representing buildFolder. Otherwise, it returns buildFolder.
  @property
  def localFolder(self):
    return self.generator.getLocalFolder(self)

  @property
  def target(self):
    return self.generator.target

  @property
  def host(self):
    return self.generator.host

  @property
  def originalCwd(self):
    return self.generator.originalCwd

  @property
  def backend(self):
    return self.generator.backend

  def SetBuildFolder(self, folder):
    if folder == '/' or folder == '.' or folder == './':
      self.buildFolder = ''
    else:
      self.buildFolder = os.path.normpath(folder)
    self.localFolder_ = self.buildFolder

  def DetectCompilers(self):
    if not self.compiler:
      self.compiler = self.generator.detectCompilers().clone()
    return self.compiler

  def ImportScript(self, file, vars={}):
    return self.generator.importScript(self, file, vars)

  def RunScript(self, file, vars={}):
    return self.generator.evalScript(file, vars)

  def RunBuildScripts(self, files, vars={}):
    if util.IsString(files):
      self.generator.evalScript(files, vars)
    else:
      for script in files:
        self.generator.evalScript(script, vars)

  def Add(self, taskbuilder):
    taskbuilder.finish(self)
    return taskbuilder.generate(self.generator, self)

  def AddSource(self, source_path):
    return self.generator.addSource(self, source_path)

  def AddSymlink(self, source, output_path):
    return self.generator.addSymlink(self, source, output_path)

  def AddFolder(self, folder):
    return self.generator.addFolder(self, folder)

  def AddCopy(self, source, output_path):
    return self.generator.addCopy(self, source, output_path)

  def AddCommand(self, inputs, argv, outputs, folder=-1, dep_type=None, weak_inputs=[],
                 shared_outputs=[]):
    return self.generator.addShellCommand(
      self,
      inputs,
      argv,
      outputs,
      folder = folder,
      dep_type = dep_type,
      weak_inputs = weak_inputs,
      shared_outputs = shared_outputs
    )

  def AddConfigureFile(self, path):
    return self.generator.addConfigureFile(self, path)

  def Context(self, name):
    return self.generator.Context(name)

class AutoContext(Context):
  def __init__(self, gen, parent, file):
    super(AutoContext, self).__init__(gen, parent, file)

  def __enter__(self):
    self.generator.pushContext(self)
    return self

  def __exit__(self, type, value, traceback):
    self.generator.popContext()

class BaseGenerator(object):
  def __init__(self, sourcePath, buildPath, originalCwd, options, args):
    super(BaseGenerator, self).__init__()
    self.sourcePath = sourcePath
    self.buildPath = os.path.normpath(buildPath)
    self.originalCwd = originalCwd
    self.options = options
    self.args = args
    self.contextStack_ = [None]
    self.configure_failed = False

    # Detect the target architecture.
    self.host = System.Host
    self.target = System.Host

    # Override the target architecture.
    new_arch = getattr(self.options, 'target_arch', None)
    if new_arch is not None:
      self.target = System(self.target.platform, util.NormalizeArchString(new_arch))

  def parseBuildScripts(self):
    root = os.path.join(self.sourcePath, 'AMBuildScript')
    self.evalScript(root)

  def pushContext(self, cx):
    self.contextStack_.append(cx)

  def popContext(self):
    self.contextStack_.pop()

  def enterContext(self, cx):
    pass

  def leaveContext(self, cx):
    pass

  def compileScript(self, path):
    with open(path) as fp:
      chars = fp.read()

      # Python 2.6 can't compile() with Windows line endings?!?!!?
      chars = chars.replace('\r\n', '\n')
      chars = chars.replace('\r', '\n')

      return compile(chars, path, 'exec')

  def importScript(self, context, file, vars={}):
    path = os.path.normpath(os.path.join(context.sourcePath, file))
    self.addConfigureFile(context, path)

    new_vars = copy.copy(vars)
    new_vars['builder'] = context

    code = self.compileScript(path)
    exec(code, new_vars)

    obj = util.Expando()
    for key in new_vars:
      setattr(obj, key, new_vars[key])
    return obj

  def Context(self, name):
    return AutoContext(self, self.contextStack_[-1], name)

  def evalScript(self, file, vars={}):
    file = os.path.normpath(file)

    cx = Context(self, self.contextStack_[-1], file)
    self.pushContext(cx)

    full_path = os.path.join(self.sourcePath, cx.buildScript)

    self.addConfigureFile(cx, full_path)

    new_vars = copy.copy(vars)
    new_vars['builder'] = cx

    # Run it.
    rvalue = None
    code = self.compileScript(full_path)

    self.enterContext(cx)
    exec(code, new_vars)
    self.leaveContext(cx)

    if 'rvalue' in new_vars:
      rvalue = new_vars['rvalue']
      del new_vars['rvalue']

    self.popContext()
    return rvalue

  def generateBuildFiles(self):
    build_py = os.path.join(self.buildPath, 'build.py')
    with open(build_py, 'w') as fp:
      fp.write("""
#!{exe}
# vim set: ts=8 sts=2 sw=2 tw=99 et:
import sys
from ambuild2 import run

if not run.CompatBuild(r"{build}"):
  sys.exit(1)
""".format(exe=sys.executable, build=self.buildPath))

    with open(os.path.join(self.buildPath, 'Makefile'), 'w') as fp:
      fp.write("""
all:
	"{exe}" "{py}"
""".format(exe=sys.executable, py=build_py))

  def generate(self):
    self.preGenerate()
    self.parseBuildScripts()
    self.postGenerate()
    if self.options.make_scripts:
      self.generateBuildFiles()
    return True

  def getLocalFolder(self, context):
    return context.localFolder_

  @property
  def backend(self):
    raise Exception('Must be implemented!')

  def addSymlink(self, context, source, output_path):
    raise Exception('Must be implemented!')

  def addFolder(self, context, folder):
    raise Exception('Must be implemented!')

  def addCopy(self, context, source, output_path):
    raise Exception('Must be implemented!')

  def addShellCommand(self, context, inputs, argv, outputs, folder=-1, dep_type=None,
                      weak_inputs=[], shared_outputs=[]):
    raise Exception('Must be implemented!')

  def addConfigureFile(self, context, path):
    raise Exception('Must be implemented!')

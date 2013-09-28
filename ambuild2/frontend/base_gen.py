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
import util
from frontend import cpp

# AMBuild 2 scripts are parsed recursively. Each script is supplied with a
# "builder" object, which maps to a Context object. Each script gets its own
# context. The context describes the parent build file generator, the local
# input and output folders, and the global compiler that was detected in the
# root script (if any).
#
# Contexts form a tree that matches the build script hierarchy. This can be
# utilized by backends for minimal reparsing and DAG updates when build
# scripts change.

class Context(object):
  def __init__(self, generator, parent, script):
    self.generator = generator
    self.parent = parent
    self.script = script
    self.compiler = None

    if parent:
      self.compiler = parent.compiler

    # By default, all generated files for a build script are placed in a path
    # matching its layout in the source tree.
    path, name = os.path.split(script)
    if parent:
      self.sourcePath = os.path.join(parent.sourcePath, path)
      self.buildFolder = os.path.join(parent.buildFolder, path)
    else:
      self.sourcePath = generator.sourcePath
      self.buildFolder = ''

  @property
  def buildPath(self):
    return self.generator.buildPath

  def DetectCompilers(self):
    if not self.compiler:
      self.compiler = self.generator.DetectCompilers()

  def RunBuildScripts(self, *args):
    for script in args:
      self.generator.parseBuildScript(script)

  def Add(self, taskbuilder):
    taskbuilder.finish(self)
    self.generator.addCxxTasks(self, taskbuilder)

class Generator(object):
  def __init__(self, sourcePath, buildPath, options, args):
    self.sourcePath = sourcePath
    self.buildPath = buildPath
    self.options = options
    self.args = args
    self.compiler = None
    self.contextStack_ = [None]

  def parseBuildScripts(self):
    root = os.path.join(self.sourcePath, 'AMBuildScript')
    self.parseBuildScript(root)

  def pushContext(self, cx):
    self.contextStack_.append(cx)

  def popContext(self):
    self.contextStack_.pop()

  def parseBuildScript(self, file):
    cx = Context(self, self.contextStack_[-1], file)
    self.pushContext(cx)

    # Compile the build script.
    with open(file) as fp:
      chars = fp.read()
      code = compile(chars, file, 'exec')

    # Run it.
    exec(code, {
      'builder': cx
    })

    self.popContext()

  def Generate(self):
    self.preGenerate()
    self.parseBuildScripts()
    return self.postGenerate()

  def DetectCompilers(self):
    if self.compiler:
      return self.compiler

    cc = cpp.DetectCompiler(self, os.environ, 'CC')
    cxx = cpp.DetectCompiler(self, os.environ, 'CXX')
    self.compiler = cpp.Compiler(cc, cxx)
    return self.compiler

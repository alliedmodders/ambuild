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
import nodetypes
from frontend.cpp import DetectCompiler
from frontend.amb2 import dbcreator
from frontend.amb2 import graphbuilder
from frontend import base_gen

class Generator(base_gen.Generator):
  def __init__(self, sourcePath, buildPath, options, args):
    super(Generator, self).__init__(sourcePath, buildPath, options, args)
    self.cacheFolder = os.path.join(buildPath, '.ambuild2')
    self.graph = graphbuilder.GraphBuilder()

  def preGenerate(self):
    self.cleanPriorBuild()

  def cleanPriorBuild(self):
    if os.path.isdir(self.cacheFolder):
      util.RemoveFolderAndContents(self.cacheFolder)
    os.mkdir(self.cacheFolder)

  def addCxxTasks(self, cx, binary):
    folderNode = self.graph.generateFolder(cx.buildFolder)

    binNode = self.graph.addOutput(path=binary.outputFile)
    linkCmd = self.graph.addCommand(type=nodetypes.Command,
                                    folder=folderNode,
                                    data=binary.argv)
    self.graph.addDependency(binNode, linkCmd)

    for objfile in binary.objfiles:
      srcNode = self.graph.addSource(path=objfile.sourceFile)
      cxxData = {
        'argv': objfile.argv,
        'type': binary.linker.behavior
      }
      objNode = self.graph.addOutput(path=objfile.outputFile)
      cxxNode = self.graph.addCommand(type=nodetypes.Cxx,
                                      folder=folderNode,
                                      data=cxxData)
      self.graph.addDependency(cxxNode, srcNode)
      self.graph.addDependency(objNode, cxxNode)
      self.graph.addDependency(linkCmd, objNode)

  def postGenerate(self):
    dbpath = os.path.join(self.cacheFolder, 'graph')
    with dbcreator.Database(dbpath) as database:
      database.createTables()
      database.exportGraph(self.graph)
    self.saveVars()
    self.generateBuildFile()
    return True

  def generateBuildFile(self):
    with open(os.path.join(self.buildPath, 'build.py'), 'w') as fp:
      fp.write("""
# vim set: ts=8 sts=2 sw=2 tw=99 et:
import sys
import run

if not run.Build("{build}"):
  sys.exit(1)
""".format(build=self.buildPath))

  def saveVars(self):
    vars = {
      'sourcePath': self.sourcePath,
      'buildPath': self.buildPath
    }
    with open(os.path.join(self.cacheFolder, 'vars'), 'wb') as fp:
      util.pickle.dump(vars, fp)

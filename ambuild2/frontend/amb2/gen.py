# vim: set ts=8 sts=2 sw=2 tw=99 et:
import os
import util
from frontend.cpp import DetectCompiler
from frontend.amb2 import cxx as amb2cxx
from frontend.amb2 import graphbuilder
from frontend import base_gen

class Generator(base_gen.Generator):
  def __init__(self, sourcePath, buildPath, options, args):
    super(Generator, self).__init__(sourcePath, buildPath, options, args)
    self.cacheFolder = os.path.join(buildPath, '.ambuild2')
    self.graph = graphbuilder.GraphBuilder()

  def Generate(self):
    self.cleanPriorBuild()
    self.parseBuildScripts()

  def cleanPriorBuild(self):
    if os.path.isdir(self.cacheFolder):
      util.RemoveFolderAndContents(self.cacheFolder)
    os.mkdir(self.cacheFolder)

  def addCxxTasks(self, binary):

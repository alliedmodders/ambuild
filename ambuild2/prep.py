# vim: set ts=8 sts=2 sw=2 tw=99 et:
import os, imp, sys
import util, graph, cpp
import pickle, database

class Preparer(object):
  def __init__(self, sourcePath, buildPath):
    self.sourcePath = sourcePath
    self.buildPath = buildPath
    self.cacheFolder = os.path.join(buildPath, '.ambuild2')

  def Configure(self):
    # Remove any existing cache folder.
    if os.path.isdir(self.cacheFolder):
      util.RemoveFolderAndContents(self.cacheFolder)
    os.mkdir(self.cacheFolder)

    # Create the database.
    dbPath = os.path.join(self.cacheFolder, 'db')
    database.CreateDatabase(dbPath)

    # Server the DB server.
    self.server = database.DatabaseParent(dbPath)
    self.graph = graph.GraphProxy(self.server)

    # Build the graph.
    try:
      self.generateGraph()
      self.generateBuildPy()
      self.saveVars()
    finally:
      self.server.close()

  def DetectCompilers(self):
    cc = cpp.DetectCompiler(self, os.environ, 'CC')
    cxx = cpp.DetectCompiler(self, os.environ, 'CXX')
    self.compiler = cpp.Compiler(self, cc, cxx)

  def Add(self, n):
    n.generate(self, self.graph)

  def execFile(self, path):
    with open(path) as fp:
      chars = fp.read()
      code = compile(chars, path, 'exec')
    exec(code, {
      'builder': self
    })

  def generateGraph(self):
    self.currentSourcePath = self.sourcePath
    self.currentOutputFolder = ''

    root = os.path.join(self.sourcePath, 'AMBuildScript')
    self.execFile(root)
    self.server.commit()

  def generateBuildPy(self):
    # Create an output.
    with open(os.path.join(self.buildPath, 'build.py'), 'w') as fp:
      fp.write("""
# vim set: ts=8 sts=4 sw=4 tw=99 et:
import sys
import run

if not run.Build("{source}", "{build}"):
  sys.exit(1)
""".format(source=self.sourcePath, build=self.buildPath))

  def saveVars(self):
    vars = {
        'sourcePath': self.sourcePath
    }
    with open(os.path.join(self.cacheFolder, 'cx'), 'wb') as fp:
      pickle.dump(vars, fp)

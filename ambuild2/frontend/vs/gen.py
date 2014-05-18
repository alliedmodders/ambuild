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
import os, errno
from ambuild2 import util
from ambuild2 import nodetypes
from ambuild2.frontend import base_gen, paths
from ambuild2.frontend.vs.compiler import Compiler
from ambuild2.frontend.vs.entry import FolderEntry

SupportedVersions = ['10', '11', '12']
YearMap = {
  '2010': 10,
  '2012': 11,
  '2013': 12,
}

class Generator(base_gen.Generator):
  def __init__(self, sourcePath, buildPath, originalCwd, options, args):
    super(Generator, self).__init__(sourcePath, buildPath, originalCwd, options, args)
    self.compiler = None
    self.vs_version = None
    self.files_ = {}

    if self.options.vs_version in SupportedVersions:
      self.vs_version = int(self.options.vs_version)
    else:
      if self.options.vs_version not in YearMap:
        util.con_err(
          util.ConsoleRed,
          'Unsupported Visual Studio version: {0}'.format(self.options.vs_version),
          util.ConsoleNormal
        )
        raise Exception('Unsupported Visual Studio version: {0}'.format(self.options.vs_version)) 
      self.vs_version = YearMap[self.options.vs_version]

  @property
  def backend(self):
    return 'vs'

  def preGenerate(self):
    pass

  # We don't support reconfiguring in this frontend.
  def addConfigureFile(self, cx, path):
    pass

  def detectCompilers(self):
    if not self.compiler:
      self.compiler = Compiler(Compiler.GetVersionFromVS(self.vs_version))
    return self.compiler

  def addFolder(self, cx, folder):
    _, path = paths.ResolveFolder(cx.localFolder, folder)
    if path in self.files_:
      entry = self.files_[path]
      if type(entry) is not FolderEntry:
        util.con_err(
          util.ConsoleRed, 'Path already exists as: {0}'.format(entry.kind),
          util.ConsoleNormal
        )
        raise Exception('Path already exists as: {0}'.format(entry.kind))
      return entry

    try:
      os.makedirs(path)
    except OSError as exn:
      if not (exn.errno == errno.EEXIST and os.path.isdir(path)):
        raise

    obj = FolderEntry(path)
    self.files_[path] = obj

    return obj

  def addShellCommand(self, context, inputs, argv, outputs, folder=-1, dep_type=None,
                      weak_inputs=[], shared_outputs=[]):
    print(inputs, argv, outputs, folder, dep_type, weak_inputs, shared_outputs)

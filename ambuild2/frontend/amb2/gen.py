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
from ambuild2 import util
from ambuild2 import nodetypes
from ambuild2.frontend.cpp import DetectCompiler
from ambuild2.frontend import base_gen
from ambuild2 import database

class CppNodes(object):
  def __init__(self, output, debug_outputs):
    self.binary = output
    self.debug = debug_outputs

class Generator(base_gen.Generator):
  def __init__(self, sourcePath, buildPath, options, args, db=None, refactoring=False):
    super(Generator, self).__init__(sourcePath, buildPath, options, args)
    self.cacheFolder = os.path.join(self.buildPath, '.ambuild2')
    self.old_scripts_ = set()
    self.old_folders_ = set()
    self.old_commands_ = set()
    self.old_groups_ = set()
    self.rm_list_ = []
    self.bad_outputs_ = set()
    self.db = db
    self.is_bootstrap = not self.db
    self.refactoring = refactoring

  def preGenerate(self):
    if not os.path.isdir(self.cacheFolder):
      os.mkdir(self.cacheFolder)
    if not self.db:
      self.db = database.Database(os.path.join(self.cacheFolder, 'graph'))
      self.db.connect()
    self.db.create_tables()

    self.db.query_scripts(lambda id,path,stamp: self.old_scripts_.add(path))
    self.db.query_mkdir(lambda entry: self.old_folders_.add(entry))
    self.db.query_commands(lambda entry: self.old_commands_.add(entry))
    self.db.query_groups(lambda entry:self.old_groups_.add(entry))

  def cleanup(self):
    for path in self.rm_list_:
      util.rm_path(path)

    for cmd_entry in self.old_commands_:
      if self.refactoring:
        util.con_err(util.ConsoleRed, 'Command removed during refactoring: \n',
                     util.ConsoleBlue, cmd_entry.format(),
                     util.ConsoleNormal)
        raise Exception('Refactoring error: command removed')
      self.db.drop_command(cmd_entry)

    for path in self.old_scripts_:
      self.db.drop_script(path)

    for group in self.old_groups_:
      self.db.drop_group(group)

    class Node:
      def __init__(self):
        self.incoming = set()
        self.outgoing = set()

    # Build a tree of dead folders.
    tracker = {}
    for entry in self.old_folders_:
      if entry not in tracker:
        tracker[entry] = Node()

      if entry.folder is None:
        continue

      # If our parent is not a dead folder, don't create an edge. It should be
      # impossible for a/b to be dead, a/b/c to be alive, and a/b/c/d to be
      # dead, since a/b/c will implicitly keep a/b alive.
      if entry.folder not in self.old_folders_:
        continue

      if entry.folder not in tracker:
        tracker[entry.folder] = Node()

      parent = tracker[entry.folder]
      child = tracker[entry]
      parent.incoming.add(entry)
      child.outgoing.add(entry.folder)

    # Find the leaves. Sets start out >= 1 items. Remove them as they they
    # are empty.
    dead_folders = [entry for entry in self.old_folders_ if len(tracker[entry].incoming) == 0]
    while len(dead_folders):
      child_entry = dead_folders.pop()
      child_node = tracker[child_entry]

      if self.refactoring:
        util.con_err(util.ConsoleRed, 'Folder removed during refactoring: \n',
                     util.ConsoleBlue, child_entry.format(),
                     util.ConsoleNormal)
        raise Exception('Refactoring error: command removed')

      self.db.drop_folder(child_entry)
      for parent_entry in child_node.outgoing:
        parent_node = tracker[parent_entry]
        parent_node.incoming.remove(child_entry)
        if not len(parent_node.incoming):
          dead_folders.append(parent_entry)

  def postGenerate(self):
    self.cleanup()
    self.db.commit()
    if self.is_bootstrap:
      self.saveVars()
      self.db.close()

  def saveVars(self):
    vars = {
      'sourcePath': self.sourcePath,
      'buildPath': self.buildPath,
      'options': self.options,
      'args': self.args
    }
    with open(os.path.join(self.cacheFolder, 'vars'), 'wb') as fp:
      util.DiskPickle(vars, fp)

  def getLocalFolder(self, context):
    if type(context.localFolder_) is nodetypes.Entry or context.localFolder_ is None:
      return context.localFolder_

    if len(context.buildFolder):
      context.localFolder_ = self.generateFolder(None, context.buildFolder)
    else:
      context.localFolder_ = None
    return context.localFolder_

  def generateFolder(self, parent, folder):
    parent_path = ''
    if parent:
      parent_path = parent.path
    path = os.path.normpath(os.path.join(parent_path, folder))

    if path.startswith('..'):
      util.con_err(
        util.ConsoleRed,
        'Output path ',
        util.ConsoleBlue,
        path,
        util.ConsoleRed,
        ' is outside the build folder!',
        util.ConsoleNormal
      )
      raise Exception('Cannot generate folders outside the build folder')

    # Quick check. If this folder is not in our old folder list, and it's in
    # the DB, then we already have an entry for it that has already negotiated
    # its parent paths.
    old_entry = self.db.query_path(path)
    if old_entry and self.isValidFolderEntry(old_entry):
      return old_entry

    components = []
    while folder:
      folder, name = os.path.split(folder)
      if not name:
        break
      components.append(name)

    path = parent_path
    while len(components):
      name = components.pop()
      path = os.path.join(path, name)
      entry = self.db.query_path(path)
      if not entry:
        if self.refactoring:
          util.con_err(util.ConsoleRed, 'New folder introduced: ',
                       util.ConsoleBlue, path,
                       util.ConsoleNormal)
          raise Exception('Refactoring error: new folder')
        entry = self.db.add_folder(parent, path)
      elif entry.type == nodetypes.Output:
        cmd_entry = self.db.query_command_of(entry)
        if cmd_entry not in self.old_commands_:
          util.con_err(util.ConsoleRed, 'Folder has the same path as an output file generated by:\n',
                       util.ConsoleBlue, cmd_entry.format(),
                       util.ConsoleNormal)
          raise Exception('Output has been duplicated: {0}'.format(entry.path))

        if self.refactoring:
          util.con_err(util.ConsoleRed, 'Path "',
                       util.ConsoleBlue, entry.path,
                       util.ConsoleRed, '" has changed from a file to a folder.',
                       util.ConsoleNormal)
          raise Exception('Refactoring error: path changed from file to folder')

        self.rm_list_.append(entry.path)
        self.db.change_output_to_folder(entry)
      elif entry.type == nodetypes.Mkdir:
        # We let the same folder be generated twice, so use discard, not remove.
        self.old_folders_.discard(entry)
      else:
        util.con_err(util.ConsoleRed, 'Folder has the same node signature as: ',
                     util.ConsoleBlue, entry.format(),
                     util.ConsoleNormal)
        raise Exception('Output has been duplicated: {0}'.format(entry.path))

      parent = entry

    return entry

  def isValidFolderEntry(self, folder_entry):
    # If it's a mkdir and it's created, we're done.
    return folder_entry.type == nodetypes.Mkdir and folder_entry not in self.old_folders_

  def validateOutputFolder(self, path):
    # Empty path is the root folder, which is null.
    if not len(path):
      return None

    # The folder must already exist.
    folder_entry = self.db.query_path(path)
    if not folder_entry:
      util.con_err(util.ConsoleRed, 'Path "',
                   util.ConsoleBlue, path,
                   util.ConsoleRed, '" specifies a folder that does not exist.',
                   util.ConsoleNormal)
      raise Exception('path specifies a folder that does not exist')

    if self.isValidFolderEntry(folder_entry):
      return folder_entry

    # If it's a folder or an output, we can give a better error message.
    if folder_entry.type == nodetypes.Output or folder_entry.type == nodetypes.Mkdir:
      util.con_err(util.ConsoleRed, 'Folder "',
                   util.ConsoleBlue, folder_entry.path,
                   util.ConsoleRed, '" was never created.',
                   util.ConsoleNormal)
      raise Exception('path {0} was never created', folder_entry.path)

    util.con_err(util.ConsoleRed, 'Attempted to use node "',
                 util.ConsoleBlue, folder_entry.format(),
                 util.ConsoleRed, '" as a path component.',
                 util.ConsoleNormal)
    raise Exception('illegal path component')

  def parseOutput(self, cwd_entry, path):
    if path[-1] == os.sep or path[-1] == os.altsep or path == '.' or path == '':
      util.con_err(util.ConsoleRed, 'Path "',
                   util.ConsoleBlue, path,
                   util.ConsoleRed, '" looks like a folder; a folder was not expected.',
                   util.ConsoleNormal)
      raise Exception('Expected folder, but path has a trailing slash')

    path = os.path.normpath(path)

    path, name = os.path.split(path)
    path = nodetypes.combine(cwd_entry, path)

    # We should have caught a case like 'x/' earlier.
    assert len(name)

    # If we resolved that there is no prefix path, then take this to mean the
    # root folder.
    if path:
      folder_entry = self.validateOutputFolder(path)
      output_path = os.path.join(path, name)
    else:
      folder_entry = None
      output_path = name

    entry = self.db.query_path(output_path)
    if not entry:
      if self.refactoring:
        util.con_err(util.ConsoleRed, 'New output file introduced: ',
                     util.ConsoleBlue, output_path,
                     util.ConsoleNormal)
        raise Exception('Refactoring error')
      return self.db.add_output(folder_entry, output_path)

    if entry.type == nodetypes.Output:
      return entry

    if entry.type != nodetypes.Mkdir:
      util.con_err(util.ConsoleRed, 'An existing node has been specified as an output file: "',
                   util.ConsoleBlue, entry.format(),
                   util.ConsoleRed, '"',
                   util.ConsoleNormal)
      raise Exception('Attempted to re-use an incompatible node as an output')

    if entry not in self.old_folders_:
      util.con_err(util.ConsoleRed, 'A folder is being re-used as an output file: "',
                   util.ConsoleBlue, entry.path,
                   util.ConsoleRed, '"',
                   util.ConsoleNormal)
      raise Exception('Attempted to re-use a folder as generated file')

    if self.refactoring:
      util.con_err(util.ConsoleRed, 'A generated folder has changed to a generated file: ',
                   util.ConsoleBlue, entry.path,
                   util.ConsoleNormal)
      raise Exception('Refactoring error')

    # We keep the node in old_folders_. This should be okay, since we've
    # changed the type to Output now. This way we can stick to one folder
    # deletion routine, since it's fairly complicated.
    self.db.change_folder_to_output(entry)
    return entry

  def parseInput(self, context, source):
    if util.IsString(source):
      if not os.path.isabs(source):
        source = os.path.join(context.currentSourcePath, source)
      source = os.path.normpath(source)

      entry = self.db.query_path(source)
      if not entry:
        return self.db.add_source(source)

      # Otherwise, we have to valid the node.
      source = entry

    if source.type == nodetypes.Source or source.type == nodetypes.Output:
      return source

    if source.type == nodetypes.Mkdir:
      if source not in self.bad_outputs_:
        util.con_err(util.ConsoleRed, 'Tried to use folder path ',
                     util.ConsoleBlue, source.path,
                     util.ConsoleRed, ' as a file path.',
                     util.ConsoleNormal)
        raise Exception('Tried to use folder path as a file path')

    util.con_err(util.ConsoleRed, 'Tried to use incompatible node "',
                 util.ConsoleBlue, source.format(),
                 util.ConsoleRed, '" as a file path.',
                 util.ConsoleNormal)
    raise Exception('Tried to use non-file node as a file path')

  def addCommand(self, context, node_type, folder, data, inputs, outputs, weak_inputs=[]):
    assert not folder or isinstance(folder, nodetypes.Entry)

    # Build the set of weak links.
    weak_links = set()
    for weak_input in weak_inputs:
      assert type(weak_input) is nodetypes.Entry
      assert weak_input.type != nodetypes.Source
      weak_links.add(weak_input)

    # Build the set of strong links.
    strong_links = set()
    for strong_input in inputs:
      strong_input = self.parseInput(context, strong_input)
      strong_links.add(strong_input)

    cmd_entry = None
    output_nodes = []
    for output in outputs:
      output_node = self.parseOutput(folder, output)
      output_nodes.append(output_node)

      input_entry = self.db.query_command_of(output_node)
      if not input_entry:
        continue

      # Make sure this output won't be duplicated.
      if input_entry not in self.old_commands_:
        util.con_err(util.ConsoleRed, 'Command: ', input_entry.format(), util.ConsoleNormal)
        raise Exception('Output has been duplicated: {0}'.format(output_node.path))

      if not cmd_entry:
        cmd_entry = input_entry
    # end for

    must_link = set(output_nodes)

    if cmd_entry:
      # Update the entry in the database.
      self.db.update_command(cmd_entry, node_type, folder, data, self.refactoring)

      # Disconnect any outputs that are no longer connected to this output.
      # It's okay to use must_link since there should never be duplicate
      # outputs.
      for outgoing in self.db.query_strong_outgoing(cmd_entry):
        if outgoing not in must_link:
          self.db.drop_strong_edge(cmd_entry, outgoing)
          self.db.drop_output(outgoing)
        else:
          must_link.remove(outgoing)

      # Remove us from the list of commands to delete.
      self.old_commands_.remove(cmd_entry)
    else:
      cmd_entry = self.db.add_command(node_type, folder, data)

    def refactoring_error(node):
      util.con_err(util.ConsoleRed, 'New input introduced: ',
                   util.ConsoleBlue, node.path + '\n',
                   util.ConsoleRed, 'Command: ',
                   util.ConsoleBlue, cmd_entry.format(),
                   util.ConsoleNormal)
      raise Exception('Refactoring error: new input introduced')

    if len(must_link) and self.refactoring:
      refactoring_error(must_link.pop())

    # Connect each output.
    for output_node in must_link:
      self.db.add_strong_edge(cmd_entry, output_node)

    # Connect/disconnect strong inputs.
    strong_inputs = self.db.query_strong_inputs(cmd_entry)
    strong_added = strong_links - strong_inputs
    strong_removed = strong_inputs - strong_links 

    if len(strong_added) and self.refactoring:
      refactoring_error(strong_added.pop())

    for strong_input in strong_added:
      self.db.add_strong_edge(strong_input, cmd_entry)
    for strong_input in strong_removed:
      self.db.drop_strong_edge(strong_input, cmd_entry)

    # Connect/disconnect weak inputs.
    weak_inputs = self.db.query_weak_inputs(cmd_entry)
    weak_added = weak_links - weak_inputs
    weak_removed = weak_inputs - weak_links 

    if len(weak_added) and self.refactoring:
      refactoring_error(weak_added.pop())

    for weak_input in weak_added:
      self.db.add_weak_edge(weak_input, cmd_entry)
    for weak_input in weak_removed:
      self.db.drop_weak_edge(weak_input, cmd_entry)

    # If we got new outputs or inputs, we need to re-run the command.
    changed = len(must_link) + len(strong_added) + len(weak_added)
    if changed and not cmd_entry.dirty:
      self.db.mark_dirty(cmd_entry)

    return cmd_entry, output_nodes

  def parseCxxDeps(self, context, binary, inputs, items):
    for val in items:
      if util.IsString(val):
        continue

      if util.IsLambda(val.node):
        item = val.node(context, binary)
      elif val.node is None:
        item = val.text
      else:
        item = val.node

      if type(item) is list:
        inputs.extend(item)
      else:
        inputs.append(item)

  def addCxxTasks(self, cx, binary):
    folder_node = self.generateFolder(cx.localFolder, binary.localFolder)

    # Find dependencies
    inputs = []
    self.parseCxxDeps(cx, binary, inputs, binary.compiler.linkflags)
    self.parseCxxDeps(cx, binary, inputs, binary.compiler.postlink)

    for objfile in binary.objects:
      cxxData = {
        'argv': objfile.argv,
        'type': binary.linker.behavior
      }
      cxxCmd, (cxxNode,) = self.addCommand(
        context = cx,
        weak_inputs = binary.compiler.sourcedeps,
        inputs = [objfile.sourceFile],
        outputs = [objfile.outputFile],
        node_type = nodetypes.Cxx,
        folder = folder_node,
        data = cxxData
      )
      inputs.append(cxxNode)
    for rcfile in binary.resources:
      rcData = {
        'cl_argv': rcfile.cl_argv,
        'rc_argv': rcfile.rc_argv,
      }
      rcCmd, (rcNode,) = self.addCommand(
        context = cx,
        weak_inputs = binary.compiler.sourcedeps,
        inputs = [rcfile.sourceFile],
        outputs = [rcfile.outputFile],
        node_type = nodetypes.Rc,
        folder = folder_node,
        data = rcData
      )
      inputs.append(rcNode)

    outputs = [binary.outputFile]
    if binary.pdbFile:
      outputs.append(binary.pdbFile)
  
    linkCmd, binNodes = self.addCommand(
      context = cx,
      node_type = nodetypes.Command,
      folder = folder_node,
      data = binary.argv,
      inputs = inputs,
      outputs = outputs
    )

    return CppNodes(binNodes[0], binNodes[1:])

  def addFileOp(self, cmd, context, source, output_path):
    # Try to detect if our output_path is actually a folder, via trailing
    # slash or '.'/'' indicating the context folder.
    detected_folder = None
    if util.IsString(output_path):
      if output_path[-1] == os.sep or output_path[-1] == os.altsep:
        detected_folder = os.path.join(context.buildFolder, os.path.normpath(output_path))
      elif output_path == '.' or output_path == '':
        detected_folder = context.buildFolder

      # Since we're building something relative to the context folder, ensure
      # that the context folder exists.
      self.getLocalFolder(context)
    else:
      assert output_path.type != nodetypes.Source
      local_path = os.path.relpath(output_path.path, context.buildFolder)
      detected_folder = os.path.join(context.buildFolder, local_path)
      detected_folder = os.path.normpath(detected_folder)

    source_entry = self.parseInput(context, source)

    # This is similar to a "cp a b/", so we append to get "b/a" as the path.
    if detected_folder is not None:
      base, output_path = os.path.split(source_entry.path)
      assert len(output_path)

      output_folder = detected_folder
    else:
      output_folder = context.buildFolder

    output_path = nodetypes.combine(output_folder, output_path)

    # For copy operations, it's okay to use the path from the current folder.
    # However, when performing symlinks, the symlink must be relative to
    # the link.
    if cmd == nodetypes.Symlink:
      source_path = os.path.relpath(source_entry.path, output_folder)
    else:
      source_path = source_entry.path

    # For clarity of spew, we always execute file operations in the root of
    # the build folder. This means that no matter what context we're in,
    # we can use absolute-ish folders and get away with it.
    return self.addCommand(
      context = context,
      node_type = cmd,
      folder = None,
      data = (source_path, output_path),
      inputs = [source_entry],
      outputs = [output_path]
    )

  def addSource(self, context, source_path):
    return self.graph.addSource(source_path)

  def addCopy(self, context, source, output_path):
    return self.addFileOp(nodetypes.Copy, context, source, output_path)

  def addSymlink(self, context, source, output_path):
    if util.IsWindows():
      # Windows pre-Vista does not support symlinks. Windows Vista+ supports
      # symlinks via mklink, but it's Administrator-only by default.
      return self.addFileOp(nodetypes.Copy, context, source, output_path)
    return self.addFileOp(nodetypes.Symlink, context, source, output_path)

  def addFolder(self, context, folder):
    return self.generateFolder(context.localFolder, folder)

  def addShellCommand(self, context, inputs, argv, outputs, folder=-1):
    if folder is -1:
      folder = context.localFolder

    return self.addCommand(
      context = context,
      node_type = nodetypes.Command,
      folder = folder,
      data = argv,
      inputs = inputs,
      outputs = outputs
    )

  def addConfigureFile(self, context, path):
    self.old_scripts_.discard(path)
    self.db.add_or_update_script(path)


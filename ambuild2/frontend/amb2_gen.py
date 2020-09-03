# vim: set ts=8 sts=4 sw=4 tw=99 et:
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
from ambuild2 import database
from ambuild2.frontend import paths
from ambuild2.frontend.base_generator import BaseGenerator

class Generator(BaseGenerator):
    def __init__(self, cm):
        super(Generator, self).__init__(cm)
        self.cacheFolder = os.path.join(self.cm.buildPath, '.ambuild2')
        self.old_scripts_ = set()
        self.old_folders_ = set()
        self.old_commands_ = set()
        self.rm_list_ = []
        self.bad_outputs_ = set()
        self.symlink_support = False
        self.had_symlink_fallback = False
        self.db = cm.db
        self.is_bootstrap = not self.db

    @property
    def backend(self):
        return 'amb2'

    @property
    def refactoring(self):
        return self.cm.refactoring

    def preGenerate(self):
        if not os.path.isdir(self.cacheFolder):
            os.mkdir(self.cacheFolder)
        if not self.db:
            db_path = os.path.join(self.cacheFolder, 'graph')
            if not os.path.isfile(db_path):
                self.db = database.CreateDatabase(db_path)
            else:
                self.db = database.Database(db_path)
                self.db.connect()

        self.symlink_support = util.DetectSymlinkSupport()

        self.db.load_environments()
        self.db.query_scripts(lambda id, path, stamp: self.old_scripts_.add(path))
        self.db.query_mkdir(lambda entry: self.old_folders_.add(entry))
        self.db.query_commands(lambda entry: self.old_commands_.add(entry))
        self.db.set_var('api_version', str(self.cm.apiVersion))

    def cleanup(self):
        for path in self.rm_list_:
            util.rm_path(path)

        for cmd_entry in self.old_commands_:
            if self.refactoring:
                util.con_err(util.ConsoleRed, 'Command removed during refactoring: \n',
                             util.ConsoleBlue, cmd_entry.format(), util.ConsoleNormal)
                raise Exception('Refactoring error: command removed')
            self.db.drop_command(cmd_entry)

        for path in self.old_scripts_:
            self.db.drop_script(path)

        self.db.query_dead_sources(lambda e: self.db.drop_source(e))
        self.db.query_dead_shared_outputs(lambda e: self.db.drop_output(e))
        self.db.drop_unused_environments()

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
                             util.ConsoleBlue, child_entry.format(), util.ConsoleNormal)
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
        self.db.vacuum()
        if self.is_bootstrap:
            self.saveVars()
            self.db.close()

        if self.had_symlink_fallback:
            util.con_out(
                util.ConsoleHeader,
                'Note: filesystem does not support symlinks. Files will be copied instead.',
                util.ConsoleNormal)

    def saveVars(self):
        vars = {
            'sourcePath': self.cm.sourcePath,
            'buildPath': self.cm.buildPath,
            'originalCwd': self.cm.originalCwd,
            'options': self.cm.options,
            'args': self.cm.args
        }

        # Save env vars that will be needed to reconfigure.
        env = {}
        for key in ['CC', 'CXX', 'CFLAGS', 'CXXFLAGS']:
            if key in os.environ:
                env[key] = os.environ[key]
        vars['env'] = env

        self.copyBuildVars(vars)

        with open(os.path.join(self.cacheFolder, 'vars'), 'wb') as fp:
            util.DiskPickle(vars, fp)

    # Implemented by derived classes.
    def copyBuildVars(self, vars):
        pass

    def detectCompilers(self, options = None):
        raise NotImplementedError()

    def getLocalFolder(self, context):
        if self.cm.apiVersion < '2.1':
            if type(context.localFolder_) is nodetypes.Entry or context.localFolder_ is None:
                return context.localFolder_

            if len(context.buildFolder):
                context.localFolder_ = self.generateFolder(None, context.buildFolder)
            else:
                context.localFolder_ = None
            return context.localFolder_

        if len(context.buildFolder):
            return self.generateFolder(None, context.buildFolder)
        return None

    def generateFolder(self, parent, folder):
        parent_path, path = paths.ResolveFolder(parent, folder)

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

        if not len(components):
            return parent

        path = parent_path
        while len(components):
            name = components.pop()
            path = os.path.join(path, name)
            entry = self.db.query_path(path)
            if not entry:
                if self.refactoring:
                    util.con_err(util.ConsoleRed, 'New folder introduced: ', util.ConsoleBlue, path,
                                 util.ConsoleNormal)
                    raise Exception('Refactoring error: new folder')
                entry = self.db.add_folder(parent, path)
            elif entry.type == nodetypes.Output or entry.type == nodetypes.SharedOutput:
                if entry.type == nodetypes.Output:
                    cmd_entries = [self.db.query_command_of(entry)]
                elif entry.type == nodetypes.SharedOutput:
                    cmd_entries = self.db.query_shared_commands_of(entry)

                for cmd_entry in cmd_entries:
                    if cmd_entry not in self.old_commands_:
                        util.con_err(util.ConsoleRed,
                                     'Folder has the same path as an output file generated by:\n',
                                     util.ConsoleBlue, cmd_entry.format(), util.ConsoleNormal)
                        raise Exception('Output has been duplicated: {0}'.format(entry.path))

                if self.refactoring:
                    util.con_err(util.ConsoleRed, 'Path "', util.ConsoleBlue, entry.path,
                                 util.ConsoleRed, '" has changed from a file to a folder.',
                                 util.ConsoleNormal)
                    raise Exception('Refactoring error: path changed from file to folder')

                self.rm_list_.append(entry.path)
                self.db.change_to_folder(entry)
            elif entry.type == nodetypes.Mkdir:
                # We let the same folder be generated twice, so use discard, not remove.
                self.old_folders_.discard(entry)
            else:
                util.con_err(util.ConsoleRed, 'Folder has the same node signature as: ',
                             util.ConsoleBlue, entry.format(), util.ConsoleNormal)
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
            util.con_err(util.ConsoleRed, 'Path "', util.ConsoleBlue, path, util.ConsoleRed,
                         '" specifies a folder that does not exist.', util.ConsoleNormal)
            raise Exception('path specifies a folder that does not exist')

        if self.isValidFolderEntry(folder_entry):
            return folder_entry

        # If it's a folder or an output, we can give a better error message.
        if folder_entry.type == nodetypes.Output or folder_entry.type == nodetypes.Mkdir:
            util.con_err(util.ConsoleRed, 'Folder "', util.ConsoleBlue, folder_entry.path,
                         util.ConsoleRed, '" was never created.', util.ConsoleNormal)
            raise Exception('path {0} was never created', folder_entry.path)

        util.con_err(util.ConsoleRed, 'Attempted to use node "', util.ConsoleBlue,
                     folder_entry.format(), util.ConsoleRed, '" as a path component.',
                     util.ConsoleNormal)
        raise Exception('illegal path component')

    def parseOutput(self, cwd_entry, path, kind):
        if path[-1] == os.sep or path[-1] == os.altsep or path == '.' or path == '':
            util.con_err(util.ConsoleRed, 'Path "', util.ConsoleBlue, path, util.ConsoleRed,
                         '" looks like a folder; a folder was not expected.', util.ConsoleNormal)
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
                util.con_err(util.ConsoleRed, 'New output file introduced: ', util.ConsoleBlue,
                             output_path, util.ConsoleNormal)
                raise Exception('Refactoring error')
            return self.db.add_output(folder_entry, output_path, kind)

        if entry.type == kind:
            return entry

        if entry.type == nodetypes.Mkdir:
            if entry not in self.old_folders_:
                util.con_err(util.ConsoleRed, 'A folder is being re-used as an output file: "',
                             util.ConsoleBlue, entry.path, util.ConsoleRed, '"', util.ConsoleNormal)
                raise Exception('Attempted to re-use a folder as generated file')

            if self.refactoring:
                util.con_err(util.ConsoleRed,
                             'A generated folder has changed to a generated file: ',
                             util.ConsoleBlue, entry.path, util.ConsoleNormal)
                raise Exception('Refactoring error')

            # We keep the node in old_folders_. This should be okay, since we've
            # changed the type to Output now. This way we can stick to one folder
            # deletion routine, since it's fairly complicated.
        elif entry.type == nodetypes.Output:
            # If we're asking for a shared output, make sure we can reuse this one.
            input_cmd = self.db.query_command_of(entry)
            if input_cmd and input_cmd not in self.old_commands_:
                util.con_err(util.ConsoleRed, 'First defined with command: ', input_cmd.format(),
                             util.ConsoleNormal)
                raise Exception('Existing output cannot be a shared output: {0}'.format(entry.path))

            if self.refactoring:
                util.con_err(util.ConsoleRed, 'An output has changed to a shared output: ',
                             util.ConsoleBlue, entry.path, util.ConsoleNormal)
                raise Exception('Refactoring error')
        elif entry.type == nodetypes.SharedOutput:
            input_cmds = self.db.query_shared_commands_of(entry)
            for input_cmd in input_cmds:
                if input_cmd not in self.old_commands_:
                    util.con_err(util.ConsoleRed,
                                 'A shared output cannot be specified as an normal output.',
                                 util.ConsoleNormal)
                    raise Exception('Existing shared output cannot be a normal output: {0}'.format(
                        entry.path))

            if self.refactoring:
                util.con_err(util.ConsoleRed, 'A shared output has changed to a normal output: ',
                             util.ConsoleBlue, entry.path, util.ConsoleNormal)
                raise Exception('Refactoring error')
        else:
            util.con_err(util.ConsoleRed,
                         'An existing node has been specified as an output file: "',
                         util.ConsoleBlue, entry.format(), util.ConsoleRed, '"', util.ConsoleNormal)
            raise Exception('Attempted to re-use an incompatible node as an output')

        self.db.change_to_output(entry, kind)
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
                util.con_err(util.ConsoleRed, 'Tried to use folder path ', util.ConsoleBlue,
                             source.path, util.ConsoleRed, ' as a file path.', util.ConsoleNormal)
                raise Exception('Tried to use folder path as a file path')

        util.con_err(util.ConsoleRed, 'Tried to use incompatible node "', util.ConsoleBlue,
                     source.format(), util.ConsoleRed, '" as a file path.', util.ConsoleNormal)
        raise Exception('Tried to use non-file node as a file path')

    def addCommand(self,
                   context,
                   node_type,
                   folder,
                   data,
                   inputs,
                   outputs,
                   weak_inputs = None,
                   shared_outputs = None,
                   env_data = None):
        assert not folder or isinstance(folder, nodetypes.Entry)

        weak_inputs = weak_inputs or []
        shared_outputs = shared_outputs or []

        if inputs is self.cm.ALWAYS_DIRTY:
            if len(weak_inputs) != 0:
                message = "Always-dirty commands cannot have weak inputs"
                util.con_err(util.ConsoleRed, "{0}.".format(message), util.ConsoleNormal)
                raise Exception(message)
            if node_type != nodetypes.Command:
                message = "Node type {0} cannot be always-dirty".format(node_type)
                util.con_err(util.ConsoleRed, "{0}.".format(message), util.ConsoleNormal)
                raise Exception(message)

        # Build the set of weak links.
        weak_links = set()
        for weak_input in weak_inputs:
            assert type(weak_input) is nodetypes.Entry
            assert weak_input.type != nodetypes.Source
            weak_links.add(weak_input)

        # Build the set of strong links.
        strong_links = set()
        if inputs is not context.cm.ALWAYS_DIRTY:
            for strong_input in inputs:
                strong_input = self.parseInput(context, strong_input)
                strong_links.add(strong_input)

        # Build the list of outputs.
        cmd_entry = None
        output_nodes = []
        for output in outputs:
            output_node = self.parseOutput(folder, output, nodetypes.Output)
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

        # Build the list of shared outputs.
        shared_output_nodes = []
        for shared_output in shared_outputs:
            shared_output_node = self.parseOutput(folder, shared_output, nodetypes.SharedOutput)
            shared_output_nodes.append(shared_output_node)

        output_links = set(output_nodes)
        shared_links = set(shared_output_nodes)

        # There should be no duplicates in either output list. These error messages
        # could be better.
        if len(output_nodes) > len(output_links):
            util.con_err(util.ConsoleRed, 'The output list contains duplicate files.',
                         util.ConsoleNormal)
            raise Exception('Shared output list contains duplicate files.')
        if len(shared_output_nodes) > len(shared_links):
            util.con_err(util.ConsoleRed, 'The output list contains duplicate files.',
                         util.ConsoleNormal)
            raise Exception('Shared output list contains duplicate files.')

        # The intersection of output_links and shared_links should be the empty set.
        duplicates = output_links.intersection(shared_links)
        if len(duplicates):
            bad_entry = duplicates.pop()
            util.con_err(util.ConsoleRed, 'An output has been duplicated as a shared output: ',
                         util.ConsoleBlue, bad_entry.path, util.ConsoleNormal)
            raise Exception('An output has been duplicated as a shared output.')

        dirty = nodetypes.DIRTY
        if inputs == context.cm.ALWAYS_DIRTY:
            dirty = nodetypes.ALWAYS_DIRTY

        if cmd_entry:
            # Update the entry in the database.
            self.db.update_command(cmd_entry, node_type, folder, data, dirty, self.refactoring,
                                   env_data)

            # Disconnect any outputs that are no longer connected to this output.
            # It's okay to use output_links since there should never be duplicate
            # outputs.
            for outgoing in self.db.query_strong_outgoing(cmd_entry):
                if outgoing not in output_links:
                    self.db.drop_strong_edge(cmd_entry, outgoing)
                    self.db.drop_output(outgoing)
                else:
                    output_links.remove(outgoing)

            # Do the same for shared outputs. Since there is a many:1 relationship,
            # we can't drop shared outputs here. We save that for a cleanup step.
            for outgoing in self.db.query_shared_outputs(cmd_entry):
                if outgoing not in shared_links:
                    self.db.drop_shared_output_edge(cmd_entry, outgoing)
                else:
                    shared_links.remove(outgoing)

            # Remove us from the list of commands to delete.
            self.old_commands_.remove(cmd_entry)
        else:
            # Note that if there are no outputs, we will always add a new command,
            # and the old (identical) command will be deleted.
            cmd_entry = self.db.add_command(node_type, folder, data, dirty, env_data)

        # Local helper function to warn about refactoring problems.
        def refactoring_error(node):
            util.con_err(util.ConsoleRed, 'New input introduced: ', util.ConsoleBlue,
                         node.path + '\n', util.ConsoleRed, 'Command: ', util.ConsoleBlue,
                         cmd_entry.format(), util.ConsoleNormal)
            raise Exception('Refactoring error: new input introduced')

        if len(output_links) and self.refactoring:
            refactoring_error(output_links.pop())
        if len(shared_links) and self.refactoring:
            refactoring_error(shared_links.pop())

        # Connect each output.
        for output_node in output_links:
            self.db.add_strong_edge(cmd_entry, output_node)
        for shared_output_node in shared_links:
            self.db.add_shared_output_edge(cmd_entry, shared_output_node)

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
        changed = len(output_links) + len(strong_added) + len(weak_added)
        if changed and cmd_entry.dirty == nodetypes.NOT_DIRTY:
            self.db.mark_dirty(cmd_entry)

        return cmd_entry, output_nodes

    def parseCxxDeps(self, context, binary, inputs, items):
        for val in items:
            if util.IsString(val):
                continue

            if type(val) is nodetypes.Entry:
                item = val
            elif util.IsLambda(val.node):
                item = val.node(context, binary)
            elif val.node is None:
                item = self.parseInput(context, val.text).path
            else:
                item = val.node

            if type(item) is list:
                inputs.extend(item)
            else:
                inputs.append(item)

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
        # However, when performing symlinks, we always want an absolute path.
        if cmd == nodetypes.Symlink:
            if source_entry.type == nodetypes.Source:
                source_path = source_entry.path
            else:
                source_path = os.path.join(context.buildPath, source_entry.path)
        else:
            source_path = source_entry.path

        # For clarity of spew, we always execute file operations in the root of
        # the build folder. This means that no matter what context we're in,
        # we can use absolute-ish folders and get away with it.
        return self.addCommand(context = context,
                               node_type = cmd,
                               folder = None,
                               data = (source_path, output_path),
                               inputs = [source_entry],
                               outputs = [output_path])

    def addSource(self, context, source_path):
        return self.graph.addSource(source_path)

    def addCopy(self, context, source, output_path):
        return self.addFileOp(nodetypes.Copy, context, source, output_path)

    def addSymlink(self, context, source, output_path):
        if util.IsWindows():
            # Windows pre-Vista does not support symlinks. Windows Vista+ supports
            # symlinks via mklink, but it's Administrator-only by default.
            return self.addFileOp(nodetypes.Copy, context, source, output_path)

        if not self.symlink_support:
            self.had_symlink_fallback = True
            return self.addFileOp(nodetypes.Copy, context, source, output_path)

        return self.addFileOp(nodetypes.Symlink, context, source, output_path)

    def addFolder(self, context, folder):
        return self.generateFolder(context.localFolder, folder)

    def addShellCommand(self,
                        context,
                        inputs,
                        argv,
                        outputs,
                        folder = -1,
                        dep_type = None,
                        weak_inputs = None,
                        shared_outputs = None,
                        env_data = None):
        if folder == -1:
            folder = context.localFolder

        weak_inputs = weak_inputs or []
        shared_outputs = shared_outputs or []

        if dep_type is None:
            node_type = nodetypes.Command
            data = argv
        else:
            node_type = nodetypes.Cxx
            if dep_type not in ['gcc', 'msvc', 'sun', 'fxc']:
                util.con_err(util.ConsoleRed, 'Invalid dependency spew type: ', util.ConsoleBlue,
                             dep_type, util.ConsoleNormal)
                raise Exception('Invalid dependency spew type')
            data = {
                'type': dep_type,
                'argv': argv,
            }

        if argv is None:
            raise Exception('argv cannot be None')

        return self.addCommand(context = context,
                               node_type = node_type,
                               folder = folder,
                               data = data,
                               inputs = inputs,
                               outputs = outputs,
                               weak_inputs = weak_inputs,
                               shared_outputs = shared_outputs,
                               env_data = env_data)

    def addOutputFile(self, context, path, contents):
        folder, filename = os.path.split(path)
        if not filename:
            raise Exception('Must specify a file, {} is a folder'.format(path))

        folder_node = self.generateFolder(context.localFolder, folder)
        data = {
            'path': paths.Join(folder_node, filename),
            'contents': contents,
        }

        _, outputs = self.addCommand(context = context,
                                     node_type = nodetypes.BinWrite,
                                     folder = folder_node,
                                     data = data,
                                     inputs = [],
                                     outputs = [filename])
        return outputs[0]

    def addConfigureFile(self, context, path):
        if not os.path.isabs(path) and context is not None:
            path = os.path.join(context.currentSourcePath, path)
        path = os.path.normpath(path)

        self.old_scripts_.discard(path)
        self.db.add_or_update_script(path)

    # This whole interface is a gross hack. It should be moved into builders.py.
    def addCxxObjTask(self, cx, shared_outputs, obj):
        cxxData = {
            'argv': obj.argv,
            'type': obj.behavior,
        }
        if obj.dep_info:
            cxxData['deps'] = obj.dep_info

        _, output_nodes = self.addCommand(context = cx,
                                          weak_inputs = obj.sourcedeps,
                                          inputs = [obj.inputObj] + obj.extra_inputs,
                                          outputs = obj.outputs,
                                          node_type = nodetypes.Cxx,
                                          folder = obj.folderNode,
                                          data = cxxData,
                                          shared_outputs = shared_outputs,
                                          env_data = obj.env_data)
        return output_nodes

    def addCxxRcTask(self, cx, obj):
        rcData = {
            'cl_argv': obj.cl_argv,
            'rc_argv': obj.rc_argv,
        }
        _, (_, rcNode) = self.addCommand(context = cx,
                                         weak_inputs = obj.sourcedeps,
                                         inputs = [obj.inputObj] + obj.extra_inputs,
                                         outputs = obj.outputs,
                                         node_type = nodetypes.Rc,
                                         folder = obj.folderNode,
                                         data = rcData,
                                         env_data = obj.env_data)
        return rcNode

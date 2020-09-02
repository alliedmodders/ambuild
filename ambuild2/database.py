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
import errno
import os, sys
import sqlite3
import time
from ambuild2 import util
from ambuild2 import nodetypes
from ambuild2.nodetypes import Entry
import traceback

def CreateDatabase(path):
  cn = sqlite3.connect(path)
  queries = [
    "create table if not exists nodes(            \
      id integer primary key autoincrement,       \
      type varchar(4) not null,                   \
      stamp real not null default 0.0,            \
      dirty int not null default 0,               \
      path text,                                  \
      folder int,                                 \
      data blob,                                  \
      env_id int default null                     \
    )",

    # The edge table stores links that are specified by the build scripts;
    # this table is essentially immutable (except for reconfigures).
    "create table if not exists edges(          \
      outgoing int not null,                    \
      incoming int not null,                    \
      unique (outgoing, incoming)               \
    )",

    # The weak edge table stores links that are specified by build scripts,
    # but only to enforce ordering. They do not propagate damage or updates.
    "create table if not exists weak_edges(     \
      outgoing int not null,                    \
      incoming int not null,                    \
      unique (outgoing, incoming)               \
    )",

    # The dynamic edge table stores edges that are discovered as a result of
    # executing a command; for example, a |cp *| or C++ #includes.
    "create table if not exists dynamic_edges(  \
      outgoing int not null,                    \
      incoming int not null,                    \
      unique (outgoing, incoming)               \
    )",

    # List of nodes which trigger a reconfigure.
    "create table if not exists reconfigure(    \
      stamp real not null default 0.0,          \
      path text unique                          \
    )",

    # Extra key/values we might randomly want.
    "create table if not exists vars(           \
      key varchar(255) primary key not null,    \
      val varchar(255)                          \
    )",

    "insert into vars (key, val) values ('db_version', '6')",

    "create index if not exists outgoing_edge on edges(outgoing)",
    "create index if not exists incoming_edge on edges(incoming)",
    "create index if not exists weak_outgoing_edge on weak_edges(outgoing)",
    "create index if not exists weak_incoming_edge on weak_edges(incoming)",
    "create index if not exists dyn_outgoing_edge on dynamic_edges(outgoing)",
    "create index if not exists dyn_incoming_edge on dynamic_edges(incoming)",

    # The shared output table.
    "create table if not exists shared_outputs( \
      outgoing int not null,                    \
      incoming int not null,                    \
      unique (outgoing, incoming)               \
    )",
    "create index if not exists sho_outgoing_edge on shared_outputs(outgoing)",
    "create index if not exists sho_incoming_edge on shared_outputs(incoming)",

    # The environment object table. Each blob is a (pickled) tuple,
    # containing (name, object) pairs. Currently, possible pairs:
    #   env_cmds: A tuple of (command, key, value) tuples to modify the
    #             environment.
    #   tools: A tuple of (name, path) tuples, denoting where to find named
    #          tools.
    #
    #   props: A tuple of (key, value) tuples, denoting extra properties that
    #          can be attached to an environment.
    #
    # This is explicitly not a dictionary. A tuple makes it hashable which is
    # useful for doing reverse-lookups without hitting the DB. It also makes
    # it easier to guarantee consistent ordering.
    "CREATE TABLE IF NOT EXISTS environments(   \
      env_id INTEGER PRIMARY KEY,               \
      data BLOB NOT NULL,                       \
      stamp REAL NOT NULL DEFAULT 0.0)",

    "CREATE UNIQUE INDEX IF NOT EXISTS node_path ON nodes(path)",
  ]
  for query in queries:
    cn.execute(query)
  cn.commit()

  db = Database(path)
  db.connect()
  return db

class Database(object):
  def __init__(self, path):
    self.path = path
    self.cn = None
    self.node_cache_ = {}
    self.path_cache_ = {}
    self.env_cache_ = {}
    self.env_reverse_lookup_ = {}

  def connect(self):
    assert not self.cn
    self.cn = sqlite3.connect(self.path)
    with IsolationChange(self.cn, None):
      self.cn.execute("PRAGMA journal_mode = WAL;")
    self.check_upgrade()

  def close(self):
    if self.cn:
      self.cn.close()
    self.cn = None

  def __enter__(self):
    self.connect()
    return self

  def __exit__(self, type, value, traceback):
    self.close()

  def commit(self):
    self.cn.commit()

  def flush_caches(self):
    self.node_cache_ = {}
    self.path_cache_ = {}

  def check_upgrade(self):
    try:
      query = "select val from vars where key = 'db_version'"
      cursor = self.cn.execute(query)
      row = cursor.fetchone()
      if not row:
        raise Exception('Database seems to be misconfigured - cannot read version')
      version = int(row[0])
    except:
      version = 1

    latest_version = 6
    if version == latest_version:
      return
    if version > latest_version:
      raise Exception('Your database version is too new!')

    util.con_out(
      util.ConsoleHeader,
      'Note: upgrading database from version {0} to {1}'.format(version, latest_version),
      util.ConsoleNormal
    )

    if version == 1:
      version = self.upgrade_to_v2()

    if version == 2:
      version = self.upgrade_to_v3()

    if version == 3:
      version = self.upgrade_to_v4()

    if version == 4:
      version = self.upgrade_to_v5()

    if version == 5:
      version = self.upgrade_to_v6()

  def upgrade_to_v2(self):
    queries = [
      "create table if not exists vars(           \
        key varchar(255) primary key not null,    \
        val varchar(255)                          \
      )",

      "drop table if exists nodestmp",
      "drop table if exists nodesold",

      "create table nodestmp(                       \
        id integer primary key autoincrement,       \
        type varchar(4) not null,                   \
        stamp real not null default 0.0,            \
        dirty int not null default 0,               \
        path text,                                  \
        folder int,                                 \
        data blob                                   \
      )",
    ]
    for query in queries:
      self.cn.execute(query)

    # Migrate all rows in nodes to nodestmp.
    query = """
      select id, type, stamp, dirty, path, folder, data
        from nodes
        order by id asc
    """
    ins_query = """
      insert into nodestmp
        (id, type, stamp, dirty, path, folder, data)
        values
        (?,  ?,    ?,     ?,     ?,    ?,      ?)
    """
    for row in self.cn.execute(query):
      self.cn.execute(ins_query, row)

    self.cn.execute("alter table nodes rename to nodesold")
    self.cn.execute("alter table nodestmp rename to nodes")
    self.cn.execute("drop table nodesold")
    self.cn.execute("insert or replace into vars (key, val) values ('db_version', ?)", (2,))
    self.cn.commit()
    return 2

  def upgrade_to_v3(self):
    queries = [
      "create table if not exists shared_outputs( \
        outgoing int not null,                    \
        incoming int not null,                    \
        unique (outgoing, incoming)               \
      )",
      "create index if not exists sho_outgoing_edge on shared_outputs(outgoing)",
      "create index if not exists sho_incoming_edge on shared_outputs(incoming)",
    ]
    for query in queries:
      self.cn.execute(query)
    self.cn.execute("insert or replace into vars (key, val) values ('db_version', ?)", (3,))
    self.cn.commit()
    return 3

  def upgrade_to_v4(self):
    # If we're not on v4, assume the API version is 2.0.
    self.cn.execute("insert or replace into vars (key, val) values ('api_version', ?)", ('2.0',))
    self.cn.execute("insert or replace into vars (key, val) values ('db_version', ?)", (4,))
    self.cn.commit()
    return 4

  def upgrade_to_v5(self):
    self.cn.execute("ALTER TABLE nodes ADD COLUMN env_id INT DEFAULT NULL")
    self.cn.execute("CREATE TABLE IF NOT EXISTS environments(   \
      env_id INTEGER PRIMARY KEY,               \
      data BLOB NOT NULL,                       \
      stamp REAL NOT NULL DEFAULT 0.0)")
    self.cn.execute("INSERT OR REPLACE INTO vars (key, val) VALUES ('db_version', ?)", (5,))
    self.cn.commit()
    return 5

  def upgrade_to_v6(self):
    self.cn.execute("CREATE UNIQUE INDEX IF NOT EXISTS node_path ON nodes(path)")
    self.cn.execute("INSERT OR REPLACE INTO vars (key, val) VALUES ('db_version', ?)", (6,))
    self.cn.commit()
    return 6

  def query_var(self, var):
    cursor = self.cn.execute("select val from vars where key = ?", (var,))
    row = cursor.fetchone()
    if row is None:
      return None
    return row[0]

  def set_var(self, var, value):
    self.cn.execute("insert or replace into vars (key, val) values (?, ?)", (var, value))

  def add_folder(self, parent, path):
    assert path not in self.path_cache_
    assert not os.path.isabs(path)
    assert os.path.normpath(path) == path

    return self.add_file(nodetypes.Mkdir, path, parent)

  def add_output(self, folder_entry, path, kind = nodetypes.Output):
    assert path not in self.path_cache_
    assert not os.path.isabs(path)
    assert not folder_entry or os.path.split(path)[0] == folder_entry.path
    assert kind == nodetypes.Output or kind == nodetypes.SharedOutput

    return self.add_file(kind, path, folder_entry)

  def find_or_add_source(self, path):
    node = self.query_path(path)
    if node:
      assert node.type == nodetypes.Source
      return node

    return self.add_source(path)

  def add_source(self, path):
    assert path not in self.path_cache_
    assert os.path.isabs(path)

    return self.add_file(nodetypes.Source, path)

  def add_file(self, type, path, folder_entry = None):
    if folder_entry:
      folder_id = folder_entry.id
    else:
      folder_id = None

    query = "insert into nodes (type, path, folder) values (?, ?, ?)"

    cursor = self.cn.execute(query, (type, path, folder_id))
    row = (type, 0, 1, path, folder_entry, None, None)
    return self.import_node(
      id=cursor.lastrowid,
      row=row
    )

  def update_command(self, entry, type, folder, data, dirty, refactoring, env_data):
    if not data:
      blob = None
    else:
      blob = util.BlobType(util.CompatPickle(data))

    # Note: it's a little gross/inconsistent how updates are handled. It seems
    # like Database should not be detecting refactoring, and then, we would not
    # need to pass env_id (which is stored in Entry for only this purpose).
    only_env_differs = False
    if entry.type == type and \
       entry.folder == folder and \
       entry.blob == data and \
       (dirty == nodetypes.ALWAYS_DIRTY) == (entry.dirty == nodetypes.ALWAYS_DIRTY):
      if nodetypes.IsSameEnvData(entry.tools_env, env_data):
        return False
      only_env_differs = True

    # Always mark changed nodes as dirty.
    if dirty != nodetypes.ALWAYS_DIRTY:
      dirty = nodetypes.DIRTY

    entry.type = type
    entry.folder = folder
    entry.blob = data
    entry.dirty = dirty

    env_id = None
    if env_data is not None:
      entry.tools_env = self.add_environment(env_data)
      env_id = entry.tools_env.env_id

    if refactoring:
      if only_env_differs:
        util.con_err(util.ConsoleRed, 'Command environment changed!\n',
                     util.ConsoleBlue, entry.format(),
                     util.ConsoleNormal)
      else:
        util.con_err(util.ConsoleRed, 'Command changed!\n',
                     util.ConsoleRed, 'Old: ',
                     util.ConsoleBlue, entry.format(),
                     util.ConsoleNormal)
        util.con_err(util.ConsoleRed, 'New: ',
                     util.ConsoleBlue, entry.format(),
                     util.ConsoleNormal)
      raise Exception('Refactoring error: command changed')

    if not folder:
      folder_id = None
    else:
      folder_id = folder.id

    query = """
      update nodes
      set
        type = ?,
        folder = ?,
        data = ?,
        dirty = ?,
        env_id = ?
      where id = ?
    """
    self.cn.execute(query, (type, folder_id, blob, dirty, env_id, entry.id))
    return True

  def add_command(self, type, folder, data, dirty, env_data):
    if not data:
      blob = None
    else:
      blob = util.BlobType(util.CompatPickle(data))
    if not folder:
      folder_id = None
    else:
      folder_id = folder.id

    env_id = None
    tools_env = None
    if env_data is not None:
      tools_env = self.add_environment(env_data)
      env_id = tools_env.env_id

    query = "insert into nodes (type, folder, data, dirty, env_id) values (?, ?, ?, ?, ?)"
    cursor = self.cn.execute(query, (type, folder_id, blob, dirty, env_id))

    entry = Entry(id = cursor.lastrowid, type = type, path = None, blob = data, folder = folder,
                  stamp = 0, dirty = nodetypes.DIRTY)
    entry.tools_env = tools_env

    self.node_cache_[entry.id] = entry
    return entry

  def add_weak_edge(self, from_entry, to_entry):
    query = "insert into weak_edges (outgoing, incoming) values (?, ?)"
    self.cn.execute(query, (to_entry.id, from_entry.id))
    if to_entry.weak_inputs is not None:
      to_entry.weak_inputs.add(from_entry)

  def add_strong_edge(self, from_entry, to_entry):
    query = "insert into edges (outgoing, incoming) values (?, ?)"
    self.cn.execute(query, (to_entry.id, from_entry.id))
    if to_entry.strong_inputs is not None:
      to_entry.strong_inputs.add(from_entry)
    if from_entry.outgoing is not None:
      from_entry.outgoing.add(to_entry)

  def add_dynamic_edge(self, from_entry, to_entry):
    query = "insert into dynamic_edges (outgoing, incoming) values (?, ?)"
    self.cn.execute(query, (to_entry.id, from_entry.id))
    if to_entry.dynamic_inputs is not None:
      to_entry.dynamic_inputs.add(from_entry)
    if from_entry.outgoing is not None:
      from_entry.outgoing.add(to_entry)

  def add_shared_output_edge(self, from_entry, to_entry):
    # These don't factor into the DAG in any meaningful way, so we don't
    # cache the results or put them into edge lists.
    query = "insert into shared_outputs (outgoing, incoming) values (?, ?)"
    self.cn.execute(query, (to_entry.id, from_entry.id))

  def drop_dynamic_edge(self, from_entry, to_entry):
    query = "delete from dynamic_edges where outgoing = ? and incoming = ?"
    self.cn.execute(query, (to_entry.id, from_entry.id))
    if to_entry.dynamic_inputs is not None:
      to_entry.dynamic_inputs.remove(from_entry)
    if from_entry.outgoing is not None:
      from_entry.outgoing.remove(to_entry)

  def drop_weak_edge(self, from_entry, to_entry):
    query = "delete from weak_edges where outgoing = ? and incoming = ?"
    self.cn.execute(query, (to_entry.id, from_entry.id))
    if to_entry.weak_inputs is not None:
      to_entry.weak_inputs.remove(from_entry)

  def drop_strong_edge(self, from_entry, to_entry):
    query = "delete from edges where outgoing = ? and incoming = ?"
    self.cn.execute(query, (to_entry.id, from_entry.id))
    if to_entry.strong_inputs is not None:
      to_entry.strong_inputs.remove(from_entry)
    if from_entry.outgoing is not None:
      from_entry.outgoing.remove(to_entry)

  def drop_shared_output_edge(self, from_entry, to_entry):
    query = "delete from shared_outputs where outgoing = ? and incoming = ?"
    self.cn.execute(query, (to_entry.id, from_entry.id))

  def query_node(self, id):
    if id in self.node_cache_:
      return self.node_cache_[id]

    query = "select type, stamp, dirty, path, folder, data, env_id from nodes where id = ?"
    cursor = self.cn.execute(query, (id,))
    return self.import_node(id, cursor.fetchone())

  def query_path(self, path):
    if path in self.path_cache_:
      return self.path_cache_[path]

    query = """
      select id, type, stamp, dirty, path, folder, data, env_id
      from nodes
      where path = ?
    """
    cursor = self.cn.execute(query, (path,))
    row = cursor.fetchone()
    if not row:
      return None

    return self.import_node(row[0], row[1:])

  def import_node(self, id, row):
    assert id not in self.node_cache_

    if not row[4]:
      folder = None
    elif type(row[4]) is nodetypes.Entry:
      folder = row[4]
    else:
      folder = self.query_node(row[4])
    if not row[5]:
      blob = None
    else:
      blob = util.Unpickle(row[5])

    node = Entry(id=id,
                 type=row[0],
                 path=row[3],
                 blob=blob,
                 folder=folder,
                 stamp=row[1],
                 dirty=row[2])

    if row[6]:
      node.tools_env = self.fetch_environment(row[6])

    self.node_cache_[id] = node
    if node.path:
      assert node.path not in self.path_cache_
      self.path_cache_[node.path] = node
    return node

  def query_strong_outgoing(self, node):
    # Not cached yet.
    outgoing = set()
    query = "select outgoing from edges where incoming = ?"
    for outgoing_id, in self.cn.execute(query, (node.id,)):
      entry = self.query_node(outgoing_id)
      outgoing.add(entry)
    return outgoing

  # Find the list of shared outputs this command generates.
  def query_shared_outputs(self, node):
    # Not cached.
    outgoing = set()
    query = "select outgoing from shared_outputs where incoming = ?"
    for outgoing_id, in self.cn.execute(query, (node.id,)):
      entry = self.query_node(outgoing_id)
      outgoing.add(entry)
    return outgoing

  def query_outgoing(self, node):
    if node.outgoing is not None:
      return node.outgoing

    node.outgoing = set()

    query = "select outgoing from edges where incoming = ?"
    for outgoing_id, in self.cn.execute(query, (node.id,)):
      entry = self.query_node(outgoing_id)
      node.outgoing.add(entry)

    query = "select outgoing from dynamic_edges where incoming = ?"
    for outgoing_id, in self.cn.execute(query, (node.id,)):
      entry = self.query_node(outgoing_id)
      node.outgoing.add(entry)

    return node.outgoing

  def query_weak_inputs(self, node):
    if node.weak_inputs is not None:
      return node.weak_inputs

    query = "select incoming from weak_edges where outgoing = ?"
    node.weak_inputs = set()
    for incoming_id, in self.cn.execute(query, (node.id,)):
      incoming = self.query_node(incoming_id)
      node.weak_inputs.add(incoming)

    return node.weak_inputs

  def query_strong_inputs(self, node):
    if node.strong_inputs is not None:
      return node.strong_inputs

    query = "select incoming from edges where outgoing = ?"
    node.strong_inputs = set()
    for incoming_id, in self.cn.execute(query, (node.id,)):
      incoming = self.query_node(incoming_id)
      node.strong_inputs.add(incoming)

    return node.strong_inputs

  def query_command_of(self, node):
    assert node.type == nodetypes.Output
    incoming = self.query_strong_inputs(node)

    assert len(incoming) <= 1
    if not len(incoming):
      return None

    cmd_entry = list(incoming)[0]
    assert cmd_entry.isCommand()

    return cmd_entry

  def query_shared_commands_of(self, node):
    query = "select incoming from shared_outputs where outgoing = ?"
    commands = []
    for row in self.cn.execute(query, (node.id,)):
      commands.append(self.query_node(row[0]))
    return commands

  def query_dynamic_inputs(self, node):
    if node.dynamic_inputs is not None:
      return node.dynamic_inputs

    query = "select incoming from dynamic_edges where outgoing = ?"
    node.dynamic_inputs = set()
    for incoming_id, in self.cn.execute(query, (node.id,)):
      incoming = self.query_node(incoming_id)
      node.dynamic_inputs.add(incoming)

    return node.dynamic_inputs

  def fetch_environment(self, env_id):
    if env_id in self.env_cache_:
      return self.env_cache_[env_id]

    query = "SELECT data FROM environments WHERE rowid = ?"
    cursor = self.cn.execute(query, (env_id,))
    row = cursor.fetchone()
    if not row:
      raise Exception('Database error, invalid environment id {}'.format(env_id))

    tools_env = nodetypes.ToolsEnv(env_id, util.Unpickle(row[0]))
    self.env_cache_[env_id] = tools_env
    self.env_reverse_lookup_[tools_env.env_data] = tools_env
    return tools_env

  def add_environment(self, env_data):
    if env_data in self.env_reverse_lookup_:
      return self.env_reverse_lookup_[env_data]

    stamp = time.time()
    blob = util.BlobType(util.CompatPickle(env_data))
    query = "INSERT INTO environments (stamp, data) VALUES (?, ?)"
    cursor = self.cn.execute(query, (stamp, blob))

    tools_env = nodetypes.ToolsEnv(cursor.lastrowid, env_data)
    self.env_cache_[tools_env.env_id] = tools_env
    self.env_reverse_lookup_[env_data] = tools_env
    return tools_env

  def mark_dirty(self, entry):
    assert entry.dirty != nodetypes.ALWAYS_DIRTY

    query = "update nodes set dirty = ? where id = ?"
    self.cn.execute(query, (nodetypes.DIRTY, entry.id))
    entry.dirty = nodetypes.DIRTY

  def unmark_dirty(self, entry, stamp=None):
    assert entry.dirty != nodetypes.ALWAYS_DIRTY

    query = "update nodes set dirty = ?, stamp = ? where id = ?"
    if not stamp:
      if entry.isCommand():
        stamp = 0.0
      else:
        try:
          stamp = os.path.getmtime(entry.path)
        except:
          traceback.print_exc()
          util.con_err(
            util.ConsoleRed,
            'Could not unmark file as dirty; leaving dirty.',
            util.ConsoleNormal
          )
          return

    self.cn.execute(query, (nodetypes.NOT_DIRTY, stamp, entry.id))
    entry.dirty = nodetypes.NOT_DIRTY
    entry.stamp = stamp

  def set_dirty_type(self, entry, dirtyType):
    if entry.dirty == dirtyType:
      return
    query = "update nodes set dirty = ? where id = ?"
    self.cn.execute(query, (dirtyType, entry.id))
    entry.dirty = dirtyType

  # Query all mkdir nodes.
  def query_mkdir(self, aggregate):
    query = """
      select id, type, stamp, dirty, path, folder, data, env_id
      from nodes
      where type == 'mkd'
    """
    for row in self.cn.execute(query):
      node = self.import_node(row[0], row[1:])
      aggregate(node)

  # Intended to be called before any nodes are imported.
  def query_known_dirty(self, aggregate):
    query = """
      select id, type, stamp, dirty, path, folder, data, env_id
      from nodes
      where dirty <> {0}
      and type != 'mkd'
    """.format(nodetypes.NOT_DIRTY)
    for row in self.cn.execute(query):
      node = self.import_node(row[0], row[1:])
      aggregate(node)

  # Query all nodes that are not dirty, but need to be checked. Intended to
  # be called after query_dirty, and returns a mutually exclusive list.
  def query_maybe_dirty(self, aggregate):
    query = """
      select id, type, stamp, dirty, path, folder, data, env_id
      from nodes
      where dirty = {0}
      and (type == 'src' or type == 'out' or type == 'cpa')
    """.format(nodetypes.NOT_DIRTY)
    for row in self.cn.execute(query):
      id = row[6]
      node = self.import_node(row[0], row[1:])
      aggregate(node)

  def query_commands(self, aggregate):
    query = """
      select id, type, stamp, dirty, path, folder, data, env_id
      from nodes
      where (type != 'src' and
             type != 'out' and
             type != 'sho' and
             type != 'grp' and
             type != 'mkd')
    """
    for row in self.cn.execute(query):
      node = self.import_node(row[0], row[1:])
      aggregate(node)

  # Load all environments into the cache (and reverse lookup cache).
  def load_environments(self):
    query = "SELECT rowid, data FROM environments"
    for row in self.cn.execute(query):
      # Note, populating the cache is mandatory otherwise. Otherwise, when the
      # generator populates its cache, it might give us back an env_id that
      # we've never seen. Another indicaton that Database is misdesigned.
      tools_env = nodetypes.ToolsEnv(row[0], util.Unpickle(row[1]))
      self.env_cache_[tools_env.env_id] = tools_env
      self.env_reverse_lookup_[tools_env.env_data] = tools_env

  # Note that this does not update any caches. It should only be called
  # around cleanup.
  def drop_links(self, entry):
    query = "delete from edges where incoming = ? or outgoing = ?"
    self.cn.execute(query, (entry.id, entry.id))

    query = "delete from dynamic_edges where incoming = ? or outgoing = ?"
    self.cn.execute(query, (entry.id, entry.id))

    query = "delete from weak_edges where incoming = ? or outgoing = ?"
    self.cn.execute(query, (entry.id, entry.id))

  def drop_entry(self, entry):
    self.drop_links(entry)

    query = "delete from nodes where id = ?"
    self.cn.execute(query, (entry.id,))

    del self.node_cache_[entry.id]

  def drop_folder(self, entry):
    assert entry.type in [nodetypes.Mkdir, nodetypes.Output, nodetypes.SharedOutput]
    assert not os.path.isabs(entry.path)

    if os.path.exists(entry.path):
      util.con_out(
        util.ConsoleHeader, 'Removing old folder: ',
        util.ConsoleBlue, '{0}'.format(entry.path),
        util.ConsoleNormal)

    try:
      os.rmdir(entry.path)
    except OSError as exn:
      if exn.errno != errno.ENOENT:
        util.con_err(util.ConsoleRed, 'Could not remove folder: ',
                     util.ConsoleBlue, '{0}'.format(entry.path),
                     util.ConsoleNormal, '\n',
                     util.ConsoleRed, '{0}'.format(exn),
                     util.ConsoleNormal)
        raise

    cursor = self.cn.execute("select count(*) from nodes where folder = ?", (entry.id,))
    amount = cursor.fetchone()[0]
    if amount > 0:
      util.con_err(util.ConsoleRed, 'Folder id ',
                   util.ConsoleBlue, '{0} '.format(entry.id),
                   util.ConsoleRed, 'is about to be deleted, but is still in use as a folder!',
                   util.ConsoleNormal)
      raise Exception('folder still in use!')

    # If the node transitioned to an entry, don't delete its node.
    if entry.type == nodetypes.Mkdir:
      self.drop_entry(entry)

  def drop_source(self, output):
    assert output.type == nodetypes.Source
    self.drop_entry(output)

  def drop_output(self, output):
    assert output.type == nodetypes.Output or output.type == nodetypes.SharedOutput
    util.rm_path(output.path)
    self.drop_entry(output)

  def drop_command(self, cmd_entry):
    for output in self.query_outgoing(cmd_entry):
      # Commands should never have dynamic outgoing edges, FWIW.
      assert output.type == nodetypes.Output
      self.drop_output(output)
    self.cn.execute("delete from shared_outputs where incoming = ?", (cmd_entry.id,))
    self.drop_entry(cmd_entry)

  def add_or_update_script(self, path):
    stamp = os.path.getmtime(path)
    query = "insert or replace into reconfigure (path, stamp) values (?, ?)"
    self.cn.execute(query, (path, stamp))

  def query_scripts(self, aggregate):
    query = "select rowid, path, stamp from reconfigure"
    for rowid, path, stamp in self.cn.execute(query):
      aggregate(rowid, path, stamp)

  def query_dead_sources(self, aggregate):
    query = """
      select id from nodes
        where type == '{0}'
        and id not in (select incoming from edges)
        and id not in (select incoming from dynamic_edges)
        and id not in (select incoming from weak_edges)
    """.format(nodetypes.Source)

    for row in self.cn.execute(query):
      entry = self.query_node(row[0])
      aggregate(entry)

  def query_dead_shared_outputs(self, aggregate):
    query = """
      select id from nodes
        where type == '{0}'
        and id not in (select outgoing from shared_outputs)
    """.format(nodetypes.SharedOutput)

    for row in self.cn.execute(query):
      entry = self.query_node(row[0])
      aggregate(entry)

  def drop_script(self, path):
    self.cn.execute("delete from reconfigure where path = ?", (path,))

  def drop_unused_environments(self):
    query = """
      SELECT rowid FROM environments
      WHERE rowid NOT IN (
        SELECT env_id FROM nodes
        WHERE env_id IS NOT NULL)"""
    for row in self.cn.execute(query):
      self.cn.execute("DELETE FROM environments WHERE rowid = ?", (row[0],))

  def change_to_folder(self, entry):
    assert entry.type == nodetypes.Output or entry.type == nodetypes.SharedOutput
    self.drop_links(entry)
    self.cn.execute("update nodes set type = 'mkd' where id = ?", (entry.id,))
    entry.type = nodetypes.Mkdir

  def change_to_output(self, entry, kind):
    assert entry.type in [nodetypes.Mkdir, nodetypes.Output, nodetypes.SharedOutput]
    self.drop_links(entry)
    self.cn.execute("update nodes set type = ? where id = ?", (kind, entry.id))
    entry.type = kind

  def vacuum(self):
    with IsolationChange(self.cn, None):
      self.cn.execute("vacuum")

  def printGraph(self):
    # Find all mkdir nodes.
    query = "select path from nodes where type = 'mkd'"
    for path, in self.cn.execute(query):
      print(' : mkdir \"' + path + '\"')
    # Find all other nodes that have no outgoing edges.
    query = "select id from nodes where id not in (select incoming from edges) and type != 'mkd'"
    for id, in self.cn.execute(query):
      node = self.query_node(id)
      self.printGraphNode(node, 0)

  def printGraphNode(self, node, indent):
    print(('  ' * indent) + ' - ' + node.format())

    for incoming in self.query_strong_inputs(node):
      self.printGraphNode(incoming, indent + 1)
    for incoming in self.query_dynamic_inputs(node):
      self.printGraphNode(incoming, indent + 1)

# Helper for Python 3.6 compatibility changes.
class IsolationChange(object):
  def __init__(self, cn, level):
    self.cn = cn
    self.level = level

  def __enter__(self):
    self.old_level = self.cn.isolation_level
    self.cn.isolation_level = self.level

  def __exit__(self, type, value, traceback):
    self.cn.isolation_level = self.old_level

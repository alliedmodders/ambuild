# vim: set sts=2 ts=8 sw=2 tw=99 et: 
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
import util
import sqlite3
import nodetypes

class Database(object):
  def __init__(self, path):
    self.path = path
    self.cn = None

  def __enter__(self):
    self.cn = sqlite3.connect(self.path)
    self.cn.execute("PRAGMA journal_mode = WAL;")
    return self

  def __exit__(self, type, value, traceback):
    if self.cn:
      self.cn.close()

  def createTables(self):
    query = """
      CREATE TABLE nodes(
        type VARCHAR(4) NOT NULL,
        stamp REAL NOT NULL DEFAULT 0.0,
        dirty INT NOT NULL DEFAULT 0,
        generated INT NOT NULL,
        path TEXT,
        folder INT,
        data BLOB
      );
    """
    self.cn.execute(query)

    # The edge table stores links that are specified by the build scripts;
    # this table is essentially immutable (except for reconfigures).
    query = """
      CREATE TABLE edges(
        outgoing INT NOT NULL,
        incoming INT NOT NULL,
        UNIQUE (outgoing, incoming)
      );
    """
    self.cn.execute(query)

    # The weak edge table stores links that are specified by build scripts,
    # but only to enforce ordering. They do not propagate damage or updates.
    query = """
      create table weak_edges(
        outgoing int not null,
        incoming int not null,
        unique (outgoing, incoming)
      );
    """

    # The dynamic edge table stores edges that are discovered as a result of
    # executing a command; for example, a |cp *| or C++ #includes.
    self.cn.execute(query)
    query = """
      create table dynamic_edges(
        outgoing int not null,
        incoming int not null,
        unique (outgoing, incoming)
      );
    """
    self.cn.execute(query)
    self.cn.execute("CREATE INDEX outgoing_edge ON edges(outgoing)")
    self.cn.execute("CREATE INDEX incoming_edge ON edges(incoming)")
    self.cn.execute("CREATE INDEX weak_outgoing_edge ON weak_edges(outgoing)")
    self.cn.execute("CREATE INDEX weak_incoming_edge ON weak_edges(incoming)")
    self.cn.execute("CREATE INDEX dyn_outgoing_edge ON dynamic_edges(outgoing)")
    self.cn.execute("CREATE INDEX dyn_incoming_edge ON dynamic_edges(incoming)")
    self.cn.commit()

  def exportGraph(self, graph):
    # Create all folder nodes.
    for path in graph.folders:
      node = graph.folders[path]

      assert node.id is None
      query = """
        INSERT INTO nodes (type, generated, path, dirty) VALUES (?, ?, ?, 0)
      """
      cursor = self.cn.execute(query, (node.type, int(node.generated), node.path))
      node.id = cursor.lastrowid

    # Create all file nodes.
    for path in graph.files:
      node = graph.files[path]

      assert node.id is None
      query = """
        INSERT INTO nodes (type, generated, path) VALUES (?, ?, ?)
      """
      cursor = self.cn.execute(query, (node.type, int(node.generated), node.path))
      node.id = cursor.lastrowid

    # Create all command nodes.
    for node in graph.commands:
      assert node.id is None
      
      if node.blob == None:
        blob = None
      else:
        blob = util.BlobType(util.pickle.dumps(node.blob))
      if node.folder == None:
        folder_id = None
      else:
        folder_id = node.folder.id

      query = """
        INSERT INTO nodes (type, generated, path, folder, data, dirty) VALUES (?, ?, ?, ?, ?, 1)
      """
      cursor = self.cn.execute(query, (node.type, int(node.generated), node.path, folder_id, blob))
      node.id = cursor.lastrowid

    # Create all group nodes.
    for group_name in graph.groups:
      group_node = graph.groups[group_name]
      assert group_node.id is None

      query = """
        insert into nodes (type, generated, path, dirty) values (?, 0, ?, 0)
      """
      cursor = self.cn.execute(query, (nodetypes.Group, group_node.path))
      group_node.id = cursor.lastrowid

      for member in group_node.members:
        assert member.id is not None
        query = "insert into edges (outgoing, incoming) values (?, ?)"
        self.cn.execute(query, (group_node.id, member.id))

    # Add all edges.
    for outgoing, incoming in graph.edges:
      assert type(outgoing.id) is int
      assert type(incoming.id) is int

      query = "INSERT INTO edges (outgoing, incoming) VALUES (?, ?)"
      self.cn.execute(query, (outgoing.id, incoming.id))

    # Add all weak edges.
    for outgoing, incoming in graph.weak_edges:
      assert type(outgoing.id) is int
      assert type(incoming.id) is int

      query = "INSERT INTO weak_edges (outgoing, incoming) VALUES (?, ?)"
      self.cn.execute(query, (outgoing.id, incoming.id))

    self.cn.commit()

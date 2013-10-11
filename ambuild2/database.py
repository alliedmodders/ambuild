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
import util
import os, sys
import sqlite3
import nodetypes
import traceback
from nodetypes import Node

class Database(object):
  def __init__(self, path):
    self.path = path
    self.cn = None
    self.node_cache_ = {}
    self.path_cache_ = {}

  def connect(self):
    assert not self.cn
    self.cn = sqlite3.connect(self.path)
    self.cn.execute("PRAGMA journal_mode = WAL;")

  def close(self):
    self.cn.close()
    self.cn = None

  def __enter__(self):
    self.connect()
    return self

  def __exit__(self, type, value, traceback):
    self.close()

  def commit(self):
    self.cn.commit()

  def add_source(self, path):
    assert path not in self.path_cache_

    query = """
      insert into nodes
      (type, generated, path)
      values
      (?, ?, ?)
    """

    cursor = self.cn.execute(query, (nodetypes.Source, 1, path))
    row = (nodetypes.Source, 0, 1, 1, path, None, None)
    return self.import_node(
      id=cursor.lastrowid,
      row=row
    )

  def add_edge(self, from_entry, to_entry, generated):
    query = """
      insert into edges
      (outgoing, incoming, generated)
      values
      (?, ?, ?)
    """
    self.cn.execute(query, (to_entry.id, from_entry.id, int(generated)))

  def drop_edge(self, from_entry, to_entry):
    query = """
      delete from edges
      where
        outgoing = ? and
        incoming = ?
    """
    self.cn.execute(query, (to_entry.id, from_entry.id))

  def query_node(self, id):
    if id in self.node_cache_:
      return self.node_cache_[id]

    query = "select type, stamp, dirty, generated, path, folder, data from nodes where rowid = ?"
    cursor = self.cn.execute(query, (id,))
    return self.import_node(id, cursor.fetchone())

  def query_path(self, path):
    if path in self.path_cache_:
      return self.path_cache_[path]

    query = """
      select type, stamp, dirty, generated, path, folder, data, rowid
      from nodes
      where path = ?
    """
    cursor = self.cn.execute(query, (path,))
    row = cursor.fetchone()
    if not row:
      return None

    return self.import_node(row[7], row)

  def import_node(self, id, row):
    assert id not in self.node_cache_

    if not row[5]:
      folder = None
    else:
      folder = self.query_node(row[5])
    if not row[6]:
      blob = None
    else:
      blob = util.Unpickle(row[6])

    node = Node(id=id,
                type=row[0],
                path=row[4],
                blob=blob,
                folder=folder,
                stamp=row[1],
                dirty=row[2],
                generated=bool(row[3]))
    self.node_cache_[id] = node
    if node.path:
      assert node.path not in self.path_cache_
      self.path_cache_[node.path] = node
    return node

  def query_incoming(self, node):
    if node.incoming:
      return node.incoming

    query = "select incoming from edges where outgoing = ?"
    node.incoming = set()
    for incoming_id, in self.cn.execute(query, (node.id,)):
      incoming = self.query_node(incoming_id)
      node.incoming.add(incoming)
    return node.incoming

  def query_outgoing(self, node):
    if node.outgoing:
      return node.outgoing

    query = "select outgoing from edges where incoming = ?"
    node.outgoing = set()
    for outgoing_id, in self.cn.execute(query, (node.id,)):
      outgoing = self.query_node(outgoing_id)
      node.outgoing.add(outgoing)
    return node.outgoing

  def mark_dirty(self, entry):
    query = "update nodes set dirty = 1 where rowid = ?"
    self.cn.execute(query, (entry.id,))
    entry.dirty |= nodetypes.KnownDirty

  def unmark_dirty(self, entry, stamp=None):
    query = "update nodes set dirty = 0, stamp = ? where rowid = ?"
    if not stamp:
      if entry.isCommand():
        stamp = 0.0
      else:
        try:
          stamp = os.path.getmtime(entry.path)
        except:
          traceback.print_exc()
          sys.stderr.write('Could not unmark file as dirty; leaving dirty.\n')
    self.cn.execute(query, (stamp, entry.id))
    entry.dirty = False
    entry.stamp = stamp

  # Intended to be called before any nodes are imported.
  def query_known_dirty(self, aggregate):
    query = """
      select type, stamp, dirty, generated, path, folder, data, rowid
      from nodes
      where dirty = 1
      and type != 'mkd'
    """
    for row in self.cn.execute(query):
      id = row[7]
      node = self.import_node(id, row)
      aggregate(node)

  # Query all nodes that are not dirty, but need to be checked. Intended to
  # be called after query_dirty, and returns a mutually exclusive list.
  def query_maybe_dirty(self, aggregate):
    query = """
      select type, stamp, dirty, generated, path, folder, data, rowid
      from nodes
      where dirty = 0
      and (type == 'src' or type == 'out' or type == 'cpa')
    """
    for row in self.cn.execute(query):
      id = row[7]
      node = self.import_node(id, row)
      aggregate(node)

  def printGraph(self):
    # Find all mkdir nodes.
    query = "select path from nodes where type = 'mkd'"
    for path, in self.cn.execute(query):
      print(' : mkdir \"' + path + '\"')
    # Find all other nodes that have no outgoing edges.
    query = "select rowid from nodes where rowid not in (select incoming from edges) and type != 'mkd'"
    for id, in self.cn.execute(query):
      node = self.query_node(id)
      self.printGraphNode(node, 0)

  def printGraphNode(self, node, indent):
    print(('  ' * indent) + ' - ' + node.format())

    for incoming in self.query_incoming(node):
      self.printGraphNode(incoming, indent + 1)

# vim: set sts=2 ts=8 sw=2 tw=99 et: 
import util
import sqlite3
from nodetypes import Node

class Database(object):
  def __init__(self, path):
    self.path = path
    self.cn = None
    self.node_cache_ = { }

  def connect(self):
    assert not self.cn
    self.cn = sqlite3.connect(self.path)
    self.cn.execute("PRAGMA journal_mode = WAL;")

    # This is technically not as safe, but we'd rather get the massive
    # performance win. If an OS crash or power outage cases db corruption,
    # the build could become corrupt? But so could any file write, really.
    self.cn.execute("PRAGMA synchronous = OFF;")

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

  def query_node(self, id):
    if id in self.node_cache_:
      return self.node_cache_[id]

    query = "select type, stamp, dirty, generated, path, folder, data from nodes where rowid = ?"
    cursor = self.cn.execute(query, (id,))
    return self.import_node(id, cursor.fetchone())

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
                dirty=bool(row[2]),
                generated=bool(row[3]))
    self.node_cache_[id] = node
    return node

  def query_incoming(self, node):
    if node.incoming:
      return node.incoming

    query = "select incoming from edges where outgoing = ?"
    node.incoming = []
    for incoming_id, in self.cn.execute(query, (node.id,)):
      incoming = self.query_node(incoming_id)
      node.incoming.append(incoming)
    return node.incoming

  def query_outgoing(self, node):
    if node.outgoing:
      return node.outgoing

    query = "select outgoing from edges where incoming = ?"
    node.outgoing = []
    for outgoing_id, in self.cn.execute(query, (node.id,)):
      outgoing = self.query_node(outgoing_id)
      node.outgoing.append(outgoing)
    return node.outgoing

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

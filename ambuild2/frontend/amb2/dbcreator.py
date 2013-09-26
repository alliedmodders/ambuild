# vim: set sts=2 ts=8 sw=2 tw=99 et: 
import util
import sqlite3

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
        dirty INT NOT NULL DEFAULT 1,
        generated INT NOT NULL,
        path TEXT,
        folder INT,
        data BLOB
      );
    """
    self.cn.execute(query)
    query = """
      CREATE TABLE edges(
        outgoing INT NOT NULL,
        incoming INT NOT NULL,
        generated INT NOT NULL,
        UNIQUE (outgoing, incoming, generated)
      );
    """
    self.cn.execute(query)
    self.cn.commit()

  def exportGraph(self, graph):
    # Create all folder nodes.
    for path in graph.folders:
      node = graph.folders[path]

      assert node.id is None
      query = """
        INSERT INTO nodes (type, generated, path) VALUES (?, ?, ?)
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
        INSERT INTO nodes (type, generated, path, folder, data) VALUES (?, ?, ?, ?, ?)
      """
      cursor = self.cn.execute(query, (node.type, int(node.generated), node.path, folder_id, blob))
      node.id = cursor.lastrowid

    # Add all edges.
    for outgoing, incoming, generated in graph.edges:
      assert type(outgoing.id) is int
      assert type(incoming.id) is int

      query = "INSERT INTO edges (outgoing, incoming, generated) VALUES (?, ?, ?)"
      cursor = self.cn.execute(query, (outgoing.id, incoming.id, int(generated)))

    self.cn.commit()

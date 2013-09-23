# vim: set ts=8 sts=2 sw=2 tw=99 et:
import os
try:
  import cPickle as pickle
except:
  import pickle
import sqlite3
import multiprocessing as mp

# Child process view of the database.
class DatabaseChild(object):
  def __init__(self, input):
    self.input = input
    self.cn = None
    self.idcache = { }

  @staticmethod
  def startup(input):
    child = DatabaseChild(input)
    child.run()

  def run(self):
    while True:
      obj = self.input.get()
      if obj == 'die':
        if self.cn:
          self.cn.close()
        return
      self.recvMessage(obj)

  def getIdForProxy(self, proxy_id):
    if type(proxy_id) == str:
      return self.idcache[proxy_id]
    return proxy_id

  def recvMessage(self, message):
    if message['msg'] == 'connect':
      return self.recvConnect(message)
    if message['msg'] == 'register':
      return self.recvRegister(message)
    if message['msg'] == 'addedge':
      return self.recvAddEdge(message)
    if message['msg'] == 'commit':
      return self.recvCommit(message)
    if message['msg'] == 'unmarkDirty':
      return self.recvUnmarkDirty(message)
    if message['msg'] == 'commitDirty':
      return self.recvCommitDirty(message)
    raise Exception('Unknown message type! ' + message['msg'])

  def recvRegister(self, message):
    path = message['path']
    node_type = message['node_type']
    assert path not in self.idcache

    if message['data'] == None:
      query = "INSERT INTO nodes (path, node_type, stamp, dirty) VALUES (?, ?, 0, 1)"
      cursor = self.cn.execute(query, (path, node_type))
    else:
      blob = pickle.dumps(message['data'])
      # Python 2, str == bytes, sqlite3 expects buffers.
      # Python 3, str != bytes, sqlite3 expects bytes.
      if type(blob) == str:
        blob = buffer(blob)
      query = "INSERT INTO nodes (path, node_type, stamp, dirty, data) VALUES (?, ?, 0, 1, ?)"
      cursor = self.cn.execute(query, (path, node_type, blob))
    self.idcache[path] = cursor.lastrowid

  def recvAddEdge(self, message):
    input = message['input']
    output = message['output']
    input_id = self.getIdForProxy(input)
    output_id = self.getIdForProxy(output)
    query = "INSERT INTO edges (output_id, input_id) VALUES (?, ?)"
    self.cn.execute(query, (output_id, input_id))

  def recvUnmarkDirty(self, message):
    node_id = self.getIdForProxy(message['proxy_id'])
    stamp = message['stamp']
    query = "UPDATE nodes SET stamp = ? AND dirty = 1 WHERE rowid = ?"
    self.cn.execute(query, (stamp, node_id))
    self.cn.commit()

  def recvCommitDirty(self, message):
    query = "UPDATE nodes SET dirty = 1 WHERE rowid = ?"
    for proxy_id in message['proxies']:
      node_id = self.getIdForProxy(proxy_id)
      self.cn.execute(query, (node_id,))
    self.cn.commit()

  def recvCommit(self, message):
    self.cn.commit()

  def recvConnect(self, message):
    self.cn = sqlite3.connect(message['path'])

# Parent process view of the database.
class DatabaseParent(object):
  def __init__(self, path):
    self.path = path
    self.input = mp.Queue()
    self.child = mp.Process(
        target=DatabaseChild.startup,
        args=(self.input, )
    )
    self.child.start()
    self.input.put({'msg': 'connect', 'path': path})

  def registerNode(self, node_type, path, data):
    self.input.put({
      'msg': 'register',
      'node_type': node_type,
      'path': path,
      'data': data
    })

    # Registration is asynchronous, so we don't have an ID representation yet.
    return None

  def registerEdge(self, output, input):
    self.input.put({
      'msg': 'addedge',
      'input': input,
      'output': output
    })

  def unmarkDirty(self, proxy_id, stamp):
    self.input.put({
      'msg': 'unmarkDirty',
      'proxy_id': proxy_id,
      'stamp': stamp
    })

  def commitDirty(self, proxy_list):
    if not len(proxy_list):
      return

    self.input.put({
      'msg': 'commitDirty',
      'proxies': proxy_list
    })

  def commit(self):
    self.input.put({'msg': 'commit'})

  def close(self):
    self.input.put('die')
    self.child.join()

  def importGraph(self, graph):
    with sqlite3.connect(self.path) as cn:
      nodes = {}
      cursor = cn.execute("SELECT rowid, path, node_type, stamp, data, dirty FROM nodes")
      for row in cursor:
        rowid = row[0]
        path = row[1]
        node_type = row[2]
        stamp = row[3]
        if not row[4] or len(row[4]) == 0:
          data = None
        elif type(row[4]) == bytes:
          data = pickle.loads(row[4])
        else:
          data = pickle.loads(str(row[4]))
        if row[5]:
          dirty = True
        else:
          dirty = False
        nodes[rowid] = graph.importNode(node_type, path, rowid, stamp, dirty, data)

      cursor = cn.execute("SELECT output_id, input_id FROM edges")
      for row in cursor:
        output_node = nodes[row[0]]
        input_node = nodes[row[1]]
        output_node.inputs.add(input_node)
        input_node.children.add(output_node)

def CreateDatabase(path):
  cn = sqlite3.connect(path)
  query = """
      CREATE TABLE IF NOT EXISTS nodes(
        path TEXT NOT NULL PRIMARY KEY,
        node_type VARCHAR(64) NOT NULL,
        stamp REAL NOT NULL,
        dirty INT NOT NULL,
        data BLOB,
        UNIQUE (path, node_type)
      );
  """
  cn.execute(query)
  query = """
      CREATE TABLE IF NOT EXISTS edges(
        output_id INTEGER NOT NULL,
        input_id INTEGER NOT NULL,
        UNIQUE (output_id, input_id)
      );
  """
  cn.execute(query)
  cn.commit()
  cn.close()


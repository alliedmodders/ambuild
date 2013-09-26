# vim: set ts=8 sts=2 sw=2 tw=99 et:
import os
import time
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
    self.messageMap = {
      'connect': lambda message: self.recvConnect(message),
      'register': lambda message: self.recvRegister(message),
      'addedge': lambda message: self.recvEdgeCmd(message),
      'dropedge': lambda message: self.recvEdgeCmd(message),
      'commit': lambda message: self.recvCommit(message),
      'unmarkDirty': lambda message: self.recvUnmarkDirty(message),
      'commitDirty': lambda message: self.recvCommitDirty(message),
    }

  @staticmethod
  def startup(input):
    child = DatabaseChild(input)
    child.run()

  def run(self):
    while True:
      obj = self.input.recv()
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
    msg_type = message['msg_type']
    self.messageMap[msg_type](message)

  def recvRegister(self, message):
    path = message['path']
    node_type = message['node_type']
    assert path not in self.idcache

    dirty = message['dirty']
    stamp = message['stamp']

    if message['data'] == None:
      query = "INSERT INTO nodes (path, node_type, stamp, dirty) VALUES (?, ?, ?, ?)"
      cursor = self.cn.execute(query, (path, node_type, stamp, dirty))
    else:
      blob = pickle.dumps(message['data'])
      # Python 2, str == bytes, sqlite3 expects buffers.
      # Python 3, str != bytes, sqlite3 expects bytes.
      if type(blob) == str:
        blob = buffer(blob)
      query = "INSERT INTO nodes (path, node_type, stamp, dirty, data) VALUES (?, ?, ?, ?, ?)"
      cursor = self.cn.execute(query, (path, node_type, stamp, dirty, blob))
    self.idcache[path] = cursor.lastrowid

  def recvEdgeCmd(self, message):
    input = message['input']
    output = message['output']
    input_id = self.getIdForProxy(input)
    output_id = self.getIdForProxy(output)
    generated = message['generated']
    if message['msg_type'] == 'addedge':
      query = "INSERT INTO edges (output_id, input_id, generated) VALUES (?, ?, ?)"
    else:
      query = "DELETE FROM edges WHERE output_id = ? AND input_id = ? AND generated = ?"
    self.cn.execute(query, (output_id, input_id, generated))

  def recvUnmarkDirty(self, message):
    node_id = self.getIdForProxy(message['proxy_id'])
    stamp = message['stamp']
    query = "UPDATE nodes SET stamp = ?, dirty = 0 WHERE rowid = ?"
    self.cn.execute(query, (stamp, node_id))
    self.commit()

  def recvCommit(self, message):
    self.commit()

  def recvConnect(self, message):
    self.cn = sqlite3.connect(message['path'])
    self.cn.execute("PRAGMA journal_mode = WAL;")

    # This is technically not as safe, but we'd rather get the massive
    # performance win. If an OS crash or power outage cases db corruption,
    # the build could become corrupt? But so could any file write, really.
    self.cn.execute("PRAGMA synchronous = OFF;")

  def recvCommitDirty(self, message):
    query = "UPDATE nodes SET dirty = 1 WHERE rowid = ?"
    for proxy_id in message['proxies']:
      node_id = self.getIdForProxy(proxy_id)
      self.cn.execute(query, (node_id,))
    self.commit()

  def commit(self):
    self.cn.commit()

# Parent process view of the database.
class DatabaseParent(object):
  def __init__(self, path):
    receiver, sender = mp.Pipe()
    self.path = path
    self.sender = sender
    self.child = mp.Process(
        target=DatabaseChild.startup,
        args=(receiver, )
    )
    self.child.start()
    self.sender.send({'msg_type': 'connect', 'path': path})

  def registerNode(self, node_type, path, data, dirty, stamp):
    self.sender.send({
      'msg_type': 'register',
      'node_type': node_type,
      'path': path,
      'data': data,
      'dirty': int(dirty),
      'stamp': stamp
    })

    # Registration is asynchronous, so we don't have an ID representation yet.
    return None

  def registerEdge(self, output, input, generated):
    self.sender.send({
      'msg_type': 'addedge',
      'input': input,
      'output': output,
      'generated': int(generated),
    })

  def unregisterEdge(self, output, input, generated):
    self.sender.send({
      'msg_type': 'dropedge',
      'input': input,
      'output': output,
      'generated': int(generated)
    })

  def unmarkDirty(self, proxy_id, stamp):
    self.sender.send({
      'msg_type': 'unmarkDirty',
      'proxy_id': proxy_id,
      'stamp': stamp
    })

  def commitDirty(self, proxy_list):
    if not len(proxy_list):
      return

    self.sender.send({
      'msg_type': 'commitDirty',
      'proxies': proxy_list
    })

  def commit(self):
    self.sender.send({'msg_type': 'commit'})

  def close(self):
    self.sender.send('die')
    self.child.join()

  def importGraph(self, graph):
    with sqlite3.connect(self.path) as cn:
      nodes = {}
      cursor = cn.execute("SELECT rowid, path, node_type, stamp, data, dirty FROM nodes")
      for rowid, path, node_type, stamp, blob, dirty in cursor:
        if not blob or len(blob) == 0:
          data = None
        elif type(blob) == bytes:
          data = pickle.loads(blob)
        else:
          data = pickle.loads(str(blob))
        nodes[rowid] = graph.importNode(node_type, path, rowid, data, bool(dirty), stamp)

      cursor = cn.execute("SELECT output_id, input_id, generated FROM edges")
      for output_id, input_id, generated in cursor:
        output_node = nodes[output_id]
        input_node = nodes[input_id]
        output_node.addDependency(input_node, generated)



# vim: set ts=8 sts=2 sw=2 tw=99 et:
import nodetypes

class Task(object):
  def __init__(self, id, entry, outputs):
    self.id = id
    self.type = entry.type
    self.data = entry.blob
    self.outputs = outputs
    self.outgoing = []
    self.incoming = set()

  def addOutgoing(self, task):
    self.outgoing.append(task)
    task.incoming.add(self)

  def format(self):
    text = ''
    if self.type == nodetypes.Cxx:
      return '[' + self.data['type'] + ']' + ' -> ' + (' '.join([arg for arg in self.data['argv']]))
    return (' '.join([arg for arg in self.data]))

class TaskMaster(object):
  def __init__(self, cx, nprocs):
    self.cx = cx
    self.nprocs = nprocs


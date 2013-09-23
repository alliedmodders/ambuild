# vim: set ts=8 sts=2 sw=2 tw=99 et:
import os
import handlers
import multiprocessing as mp

# Python's multiprocessing support doesn't let us access the internal pipe
# behind a queue, which makes it difficult to implement out-of-band messages.
# To get around this, we give each process a pipe, and let the main process
# give tasks to its children, via message passing.

class ProcessChild(object):
  def __init__(self, id, input, output):
    self.id = id
    self.input = input
    self.output = output

  def send_reply(self, message):
    self.output.put((self.id, message))

  def main(self):
    while True:
      message = self.input.recv()
      if message == "die":
        self.send_reply("dead")
        return
      msg_type = message['msg_type']
      msg_handler = handlers.Find(msg_type)
      reply = msg_handler.build(self, message)
      if not reply:
        reply = {
          'stdout': '',
          'stderr': 'No error reported',
          'ok': False
        }
      reply['task_id'] = message['task_id']
      self.send_reply(reply)

class ProcessParent(object):
  def __init__(self, id, output):
    child_read, parent_write = mp.Pipe(duplex=False)

    self.id = id
    self.input = parent_write
    self.output = output
    self.obj = mp.Process(target=ProcessParent.main,
                          args=(id, child_read, output))
    self.obj.start()

  @staticmethod
  def main(id, input, output):
    child = ProcessChild(id, input, output)
    child.main()

  def isAlive(self):
    return self.obj.is_alive()

  def send(self, message):
    self.input.send(message)

  def end(self):
    self.send("die")

  def join(self):
    self.obj.join()

class ProcessManager(object):
  def __init__(self, num_cpus):
    self.idmap = {}
    self.processes = set()
    self.output = mp.Queue()
    for i in range(num_cpus):
      p = ProcessParent(i, self.output)
      self.idmap[i] = p
      self.processes.add(p)

  def close(self):
    for process in [process for process in self.processes]:
      process.end()
      self.cleanup(process)

  def killAll(self, process):
    for process in self.processes:
      process.end()

  def cleanup(self, process):
    process.join()
    del self.idmap[process.id]
    self.processes.remove(process)

  def bringOutYourDead(self):
    processes = [process for process in self.processes]
    for process in processes:
      if not process.isAlive():
        self.cleanup(process)

  def handleSpecialMessage(self, id, message):
    if message == "dead":
      self.cleanup(self.idmap[id])

  def waitForReply(self):
    while True:
      try:
        id, message = self.output.get(timeout=5)
      except:
        # See if any processes died.
        self.bringOutYourDead()
        if not len(self.processes):
          return (None, None)
        continue

      # Is this a dead message?
      if self.handleSpecialMessage(id, message):
        continue

      return self.idmap[id], message


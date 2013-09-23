# vim: set ts=8 sts=2 sw=2 tw=99 et:

MessageHandlers_ = {}

def Register(clasp, msg_type=None):
  if not msg_type:
    msg_type = clasp.msg_type
  assert msg_type not in MessageHandlers_
  MessageHandlers_[msg_type] = clasp

def Find(name):
  return MessageHandlers_[name]

class Handler(object):
  # Must be a unique string amongst all other handlers. Used for message
  # passing and node association in the database.
  msg_type = None

  # May be called on a remote process or thread. The return value is sent back
  # back to the build process, and should be a dictionary to be received by
  # the update() handler.
  @staticmethod
  def build(process, message):
    raise Exception("must be overridden!")

  # Receives the reply given back by build(). Executed in the main thread.
  @staticmethod
  def update(cx, dmg_node, node, reply):
    raise Exception("must be overridden!")

  # Called on the main thread to generate a task.
  @staticmethod
  def createTask(cx, builder, node):
    raise Exception("must be overridden!")

# A special handler is defined for nodes that are purely source files.
class SourceHandler(object):
  msg_type = 'src:'

  @staticmethod
  def createTask(cx, builder, node):
    builder.unmarkDirty(node)

Register(SourceHandler)

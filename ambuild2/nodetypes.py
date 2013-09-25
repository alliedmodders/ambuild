# vim: set ts=8 sts=2 sw=2 tw=99 et:

# Source nodes are files that are leaf inputs to the build system, and are not
# generated as part of the build process.
Source = 'src'

# Command nodes have associated data in the command table, and produce some
# kind of output.
Command = 'cmd'

# Output nodes are files that have been generated as a result of a command.
Output = 'out'

# Folder nodes represent a folder creation action, either explicit or 
# automatically generated.
Folder = 'mkd'

# Copy nodes represent a file copy, from a source to a destination. They do
# not have a command counterpart.
Copy = 'cp'

# Link nodes represent a symlink, from a source to a destination. They do
# not have a command counterpart. On operating systems where symlinking is not
# available or unreliable, copies may be performed instead.
Symlink = 'ln'

# C++ nodes are a builtin type that are capable of performing post-processing
# on the result of the command (for example, for dependency computation). They
# are used when using AMBuild2's automated C++ builders.
Cxx = 'cxx'

# The basic properties of a node as it exists in the database.
def Node(object):
  def __init__(self, id, type, path, stamp, dirty, generated):
    self.id = id
    self.type = type
    self.path = path
    self.stamp = stamp
    self.dirty = dirty
    self.generated = generated

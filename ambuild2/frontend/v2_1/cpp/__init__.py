from ambuild2.frontend.v2_1.cpp.compiler import Compiler
from ambuild2.frontend.v2_1.cpp.builders import Dep

class CppNodes(object):
  def __init__(self, output, debug_outputs, type):
    self.binary = output
    self.debug = debug_outputs
    self.type = type


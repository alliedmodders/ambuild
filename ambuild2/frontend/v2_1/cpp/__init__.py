from ambuild2.frontend.v2_1.cpp.compilers import Compiler
from ambuild2.frontend.v2_1.cpp.builders import Dep

class CppNodes(object):
  def __init__(self, output, debug_outputs):
    self.binary = output
    self.debug = debug_outputs


from ambuild2.frontend.v2_0.cpp.compilers import Compiler
from ambuild2.frontend.v2_0.cpp.builders import Dep

class CppNodes(object):
  def __init__(self, output, debug_outputs):
    self.binary = output
    self.debug = debug_outputs


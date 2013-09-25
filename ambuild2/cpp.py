# vim: set ts=8 sts=2 sw=2 tw=99 et:
from __future__ import print_function
import re, os, copy
import graph, util
import procman, handlers
import subprocess

sReadIncludes = 0
sLookForIncludeGuard = 1
sFoundIncludeGuard = 2
sIgnoring = 3

def ParseGCCDeps(text):
  deps = set()
  strip = False
  new_text = ''

  state = sReadIncludes
  for line in re.split('\n+', text):
    if state == sReadIncludes:
      m = re.match('\.+\s+(.+)\s*$', line)
      if m == None:
        state = sLookForIncludeGuard
      else:
        name = m.groups()[0]
        if os.path.exists(name):
          strip = True
          deps.add(name)
        else:
          state = LookForIncludeGuard
    if state == sLookForIncludeGuard:
      if line.startswith('Multiple include guards may be useful for:'):
        state = sFoundIncludeGuard
        strip = True
      else:
        state = sReadIncludes
        strip = False
    elif state == sFoundIncludeGuard:
      if not line in deps:
        strip = False
        state = sIgnoring
    if not strip and len(line):
      new_text += line + '\n'
  return new_text, deps

def CompileGCC(argv, path):
  p, out, err = util.Execute(argv)
  new_err, deps = ParseGCCDeps(err)

  # Adjust any dependencies relative to the current folder, to be relative
  # to the output folder instead.
  base = os.path.split(path)[0]
  paths = []
  for inc_path in deps:
    if not os.path.isabs(inc_path):
      inc_path = os.path.normpath(os.path.join(base, inc_path))
    paths.append(inc_path)

  if p.returncode != 0:
    return {
      'ok': False,
      'stdout': out,
      'stderr': new_err
    }

  return {
    'ok': True,
    'stdout': out,
    'stderr': new_err,
    'deps': paths
  }

class CxxHandler(handlers.Handler):
  msg_type = 'cxx:obj'

  @staticmethod
  def build(process, message):
    cctype = message['type']
    argv = message['argv']
    path = message['path']
    if cctype == 'gcc':
      return CompileGCC(argv, path)

  @staticmethod
  def createTask(cx, builder, node):
    return {
      'path': node.path,
      'argv': node.data['argv'],
      'type': node.data['type'],
    }

  @staticmethod
  def update(cx, dmg_node, node, reply):
    if not handlers.Handler.checkReply(cx, dmg_node, node, reply):
      return False

    # Make a node for everything in the new set.
    deps = set()
    for path in reply['deps']:
      deps.add(cx.graph.findOrAddSource(path, dirty=True))
    cx.graph.updateDynamicDependencies(node, deps)
    cx.graph.unmarkDirty(node)
    return True

  @staticmethod
  def createNodeData(argv, cctype):
    return {
      'argv': argv,
      'type': cctype,
    }

class LinkHandler(handlers.Handler):
  msg_type = 'cxx:bin'

  @staticmethod
  def build(process, message):
    argv = message['argv']
    p, out, err = util.Execute(argv)
    return {
      'ok': p.returncode == 0,
      'stdout': out,
      'stderr': err
    }

  @staticmethod
  def createTask(cx, builder, node):
    return {
      'argv': node.data
    }

  def update(cx, dmg_node, node, reply):
    if not handlers.Handler.checkReply(cx, dmg_node, node, reply):
      return False
    cx.graph.unmarkDirty(node)
    return True

handlers.Register(CxxHandler)
handlers.Register(LinkHandler)


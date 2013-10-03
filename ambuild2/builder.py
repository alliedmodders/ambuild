# vim: set ts=8 sts=2 sw=2 tw=99 et:
from task import Task
import os, errno
import traceback

# Given the partial command DAG, compute a task tree we can send to the task
# thread.
def ComputeTaskTree(graph):
  lookup = {}
  worklist = []
  for item in graph.commands():
    task = Task(item.entry)
    lookup[item] = task
    worklist.append(item)

def Build(cx, graph):
  

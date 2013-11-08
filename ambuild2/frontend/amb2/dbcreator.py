# vim: set sts=2 ts=8 sw=2 tw=99 et: 
#
# This file is part of AMBuild.
# 
# AMBuild is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# AMBuild is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with AMBuild. If not, see <http://www.gnu.org/licenses/>.
import sqlite3
from ambuild2 import util
from ambuild2 import nodetypes

class Database(object):
  def __init__(self, path):
    self.path = path
    self.cn = None

  def __enter__(self):
    self.cn = sqlite3.connect(self.path)
    self.cn.execute("PRAGMA journal_mode = WAL;")
    return self

  def __exit__(self, type, value, traceback):
    if self.cn:
      self.cn.close()

  def exportGraph(self, graph):
    # Create all group nodes.
    for group_name in graph.groups:
      group_node = graph.groups[group_name]
      assert group_node.id is None

      query = """
        insert into nodes (type, generated, path, dirty) values (?, 0, ?, 0)
      """
      cursor = self.cn.execute(query, (nodetypes.Group, group_node.path))
      group_node.id = cursor.lastrowid

      for member in group_node.members:
        assert member.id is not None
        query = "insert into edges (outgoing, incoming) values (?, ?)"
        self.cn.execute(query, (group_node.id, member.id))

    self.cn.commit()

# vim: set sts=4 ts=8 sw=4 tw=99 et: 
import unittest
from ambuild2.frontend import paths

class IsSubPathTests(unittest.TestCase):
    def runTest(self):
        self.assertEqual(paths.IsSubPath("/a/b/c", "/a"), True)
        self.assertEqual(paths.IsSubPath("/t/b/c", "/a"), False)

# vim: set sts=4 ts=8 sw=4 tw=99 et:
import ntpath
import unittest
from ambuild2.frontend import paths

class IsSubPathTests(unittest.TestCase):
    def runTest(self):
        self.assertEqual(paths.IsSubPath("/a/b/c", "/a"), True)
        self.assertEqual(paths.IsSubPath("/t/b/c", "/a"), False)
        self.assertEqual(paths.IsSubPath("t", "./"), True)
        self.assertEqual(paths.IsSubPath(r"C:\blah", "C:\\", ntpath), True)
        self.assertEqual(paths.IsSubPath(r"C:\blah", "D:\\", ntpath), False)

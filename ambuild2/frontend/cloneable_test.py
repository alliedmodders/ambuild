# vim: set sts=4 ts=8 sw=4 tw=99 et:
import collections
import copy
import unittest
from ambuild2.frontend.cloneable import Cloneable
from ambuild2.frontend.cloneable import CloneableDict

class CloneableDictTests(unittest.TestCase):
    def runTest(self):
        obj = CloneableDict()
        self.assertTrue(isinstance(obj, Cloneable))
        self.assertTrue(isinstance(obj, collections.OrderedDict))

        obj['blah'] = [1, 2, 3, 4, 5]

        clone = copy.deepcopy(obj)
        self.assertTrue(isinstance(clone, Cloneable))
        self.assertTrue(isinstance(clone, collections.OrderedDict))
        self.assertIsNot(obj, clone)
        self.assertIn('blah', clone)
        self.assertIsNot(obj['blah'], clone['blah'])

# vim: set sts=4 ts=8 sw=4 tw=99 et:
import unittest
from ambuild2.frontend.proxy import AttributeProxy

class InnerObject(object):
    def __init__(self):
        self.x = 10
        self.y = 20

class AttributeProxyTests(unittest.TestCase):
    def runTest(self):
        inner = InnerObject()
        outer = AttributeProxy(inner)

        self.assertEqual(outer.x, 10)
        self.assertEqual(outer.y, 20)

        inner.z = 30
        self.assertEqual(outer.z, 30)

        outer.a = 10
        self.assertFalse(hasattr(inner, 'a'))

        self.assertTrue(hasattr(outer, 'a'))
        self.assertTrue(hasattr(outer, 'x'))
        self.assertTrue(hasattr(outer, 'y'))
        self.assertTrue(hasattr(outer, 'z'))

        self.assertIn('a', dir(outer))
        self.assertIn('x', dir(outer))
        self.assertIn('y', dir(outer))
        self.assertIn('z', dir(outer))

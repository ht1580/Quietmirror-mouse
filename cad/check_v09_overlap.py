"""Analytic solid-intersection cases for the CAD QA separation shortcut."""
import unittest
import cadquery as cq
from validate_v09 import overlap
class SolidOverlap(unittest.TestCase):
    def setUp(self):self.a=cq.Workplane('XY').box(2,2,2).val()
    def test_separated(self):self.assertAlmostEqual(overlap(self.a,self.a.translate((3,0,0))),0.,places=6)
    def test_touching_stop(self):self.assertAlmostEqual(overlap(self.a,self.a.translate((2,0,0))),0.,places=6)
    def test_partial_overlap(self):self.assertAlmostEqual(overlap(self.a,self.a.translate((1,0,0))),4.,places=6)
    def test_containment(self):
        small=cq.Workplane('XY').box(1,1,1).val()
        self.assertAlmostEqual(self.a.distance(small),0.,places=6)
        self.assertAlmostEqual(overlap(self.a,small),1.,places=6)
if __name__=='__main__':unittest.main()

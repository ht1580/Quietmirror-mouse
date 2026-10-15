"""Acceptance tests on delivered artifacts; --version v08 records baseline failures.

Catches: excessive overall height, front ears, changed key sizes, nontriangular vents.
No CAD-builder helpers are used to derive expected geometry.
"""
from pathlib import Path
import argparse, json, struct, sys, unittest
ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument('--version', default='v09')
options, other = parser.parse_known_args()
VERSION = options.version

def vertices(path):
    data = path.read_bytes()
    count = struct.unpack_from('<I', data, 80)[0]
    if len(data) != 84 + count * 50:
        raise AssertionError(f'Expected binary STL, got {path}')
    result = []
    for face in struct.iter_unpack('<12fH', data[84:]):
        result.extend((face[3:6], face[6:9], face[9:12]))
    return result

class RedesignAcceptance(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.body = vertices(ROOT / 'exports' / VERSION / 'placed/BODY.stl')
        cls.layout = json.loads((ROOT / 'reports' / VERSION / 'vent_layout.json').read_text(encoding='utf8'))

    def test_length_and_authorized_rear_reduction(self):
        x = [p[0] for p in self.body]; y = [p[1] for p in self.body]
        self.assertGreaterEqual(max(x)-min(x),57.)
        self.assertLessEqual(max(x)-min(x),59.5, "rear reduction requested after original 62mm baseline")
        self.assertAlmostEqual(max(y)-min(y), 90, delta=.6)

    def test_reduced_overall_height(self):
        z = [p[2] for p in self.body]
        self.assertLessEqual(max(z)-min(z), 26.15, 'old 28mm crown remains')

    def test_internal_parts_do_not_project_above_crown(self):
        metrics=json.loads((ROOT/'reports'/VERSION/'cad_metrics.json').read_text(encoding='utf8'))
        offenders=[]
        for part in metrics['parts']:
            if part['name']=='BODY':continue
            points=vertices(ROOT/part['file'])
            highest=max(p[2] for p in points)
            if highest>26.15:offenders.append((part['name'],highest))
        self.assertFalse(offenders,f'Internal brackets project above the continuous roof: {offenders}')
    def test_no_front_side_ears(self):
        front = [abs(x) for x,y,z in self.body if 2 < -y < 18 and z > 4]
        self.assertTrue(front)
        self.assertLessEqual(max(front), 27.5, 'front shoulder still projects beyond flowing key sides')

    def test_main_key_contact_sizes_preserved(self):
        # Measure the actual exterior curved contact face, excluding the
        # hidden inward-offset underside and the separate internal plunger.
        import cadquery as cq
        for name in ('left_KEY','right_KEY'):
            shape=cq.importers.importStep(str(ROOT/'exports'/VERSION/'placed'/(name+'.step'))).val()
            roof=max((f for f in shape.Faces() if f.geomType()=='BSPLINE'),key=lambda f:f.Area())
            cx=-14.5 if name=='left_KEY' else 14.5
            # The original stem reaches D27.8 and can share the crown's face.
            # Measure the two lateral contact strips, excluding that stem.
            centre=cq.Workplane('XY').box(10,100,100).val().translate((cx,-45,30))
            roof=roof.cut(centre)
            bb=roof.BoundingBox()
            self.assertAlmostEqual(bb.xlen,23,delta=.1)
            self.assertAlmostEqual(bb.ylen,27,delta=.1)

    def test_all_weight_relief_profiles_are_triangles(self):
        holes = self.layout.get('holes', [])
        self.assertGreater(len(holes), 5)
        failures = []
        for hole in holes:
            pts = hole.get('triangle_xd_mm', hole.get('sharp_xd_mm', []))
            if pts and pts[0] == pts[-1]: pts = pts[:-1]
            if len(pts) != 3: failures.append((hole.get('id'),len(pts)))
        self.assertFalse(failures, f'nontriangular reliefs: {failures}')

if __name__ == '__main__':
    unittest.main(argv=[sys.argv[0]] + other)

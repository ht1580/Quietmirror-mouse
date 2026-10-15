"""Independent fixed-front and thin moving-roof acceptance on saved STEP."""
import unittest
from pathlib import Path
import cadquery as cq
from build_mouse import rounded_box
ROOT=Path(__file__).resolve().parents[1]
class FrontClosure(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.body=cq.importers.importStep(str(ROOT/'exports/v09/placed/BODY.step')).val()
        cls.keys=[cq.importers.importStep(str(ROOT/f'exports/v09/placed/{n}_KEY.step')).val() for n in ('left','right')]
    def test_both_fixed_front_panels_are_closed(self):
        for x in (-14.5,14.5):
            for z in (3.,6.,9.):
                self.assertTrue(self.body.isInside(cq.Vector(x,-1.,z),1e-5), (x,z))
    def test_charging_aperture_remains_open(self):
        self.assertFalse(self.body.isInside(cq.Vector(0.,-.5,7.1),1e-5))
    def test_straight_charging_gauge_clears_printed_parts(self):
        # A declared geometric gauge, not a claim about an unspecified cable.
        gauge=rounded_box(12.2,5.2,14.,1.4,(0,0,0)).rotate((0,0,0),(1,0,0),90).translate((0,-1.,7.1))
        self.__class__.gauge_overlaps=[]
        for path in sorted((ROOT/'exports/v09/placed').glob('*.step')):
            if path.stem.endswith('_SWITCH_EXAMPLE'):continue
            shape=self.body if path.stem=='BODY' else cq.importers.importStep(str(path)).val()
            volume=float(shape.intersect(gauge).Volume())
            self.gauge_overlaps.append(dict(part=path.stem,overlap_mm3=volume))
            self.assertLessEqual(volume,.001,path.stem)
    def test_moving_keys_do_not_include_lower_skirts(self):
        for key in self.keys:
            self.assertGreaterEqual(key.BoundingBox().zmin,8.,'Moving lower skirt still present')
if __name__=='__main__':
    import hashlib,json
    result=unittest.main(exit=False)
    report=dict(pass_check=result.result.wasSuccessful(),tests_run=result.result.testsRun,
        fixed_front_panel_probe_x_mm=[-14.5,14.5],fixed_front_panel_probe_d_mm=1.,
        fixed_front_panel_probe_z_mm=[3.,6.,9.],USB_probe_xyz_mm=[0.,-.5,7.1],
        moving_key_minimum_z_mm=[k.BoundingBox().zmin for k in FrontClosure.keys],
        USB_straight_gauge=dict(width_mm=12.2,height_mm=5.2,corner_radius_mm=1.4,y_limits_mm=[-8.,6.],center_z_mm=7.1,part_overlaps=getattr(FrontClosure,'gauge_overlaps',[])),
        source_metrics_sha256=hashlib.sha256((ROOT/'reports/v09/cad_metrics.json').read_bytes()).hexdigest(),
        limits='Fixed-face points, full moving-key lower bound, and a declared 12.2x5.2 mm straight charging gauge. Actual connector, PCB mounting and cable strain relief remain untested. Mechanism paths and walls are verified separately.')
    (ROOT/'reports/v09/front_closure_checks.json').write_text(json.dumps(report,indent=2),encoding='utf8')
    if not report['pass_check']:raise SystemExit(1)

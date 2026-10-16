"""Independent requirements gates. Geometry, motion and FEM are separate evidence.

Run --baseline to record the expected failures on the *upstream* v0.9.
All dimensions in mm. A mesh being watertight is not evidence of strength.
"""
from pathlib import Path
import argparse, json, math
import cadquery as cq

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
V = cq.Vector


def load(path):
    return cq.importers.importStep(str(path)).val()


def box(x, y, z, center):
    return cq.Workplane('XY').box(x, y, z).val().translate(center)


def check(body, p, upstream=False):
    bb = body.BoundingBox()
    # Upstream uses negative Y; use its own actual foot positions for a fair test.
    feet = [(-21,-8),(21,-8),(-21.5,-61.5),(21.5,-61.5),(0,-81.5)] if upstream else p['feet']['centers']
    r = p['feet']['diameter']/2
    allowed = None
    for x,y in feet:
        s = cq.Solid.makeCylinder(r+0.015, p['host']['base_open_band']+0.02, V(x,y,-0.01))
        allowed = s if allowed is None else allowed.fuse(s)
    band = box(200,250,p['host']['base_open_band'],(0,0 if upstream else 40,p['host']['base_open_band']/2))
    low = body.intersect(band)
    outside = low.cut(allowed).Volume()
    slices = []
    for i in range(20):
        z = .10 + i*(p['host']['base_open_band']-.2)/19
        sec = body.intersect(cq.Face.makePlane(200,250,V(0,0 if upstream else 40,z),V(0,0,1)))
        area = sum(f.Area() for f in sec.Faces())
        bad = sec.cut(allowed)
        slices.append({'z':z,'material_area':area,'outside_five_pad_prisms_area':sum(f.Area() for f in bad.Faces()),'faces':len(sec.Faces())})
    expected = [p['host'][k]*p['host']['scale'] for k in ('width','length','height')]
    dimensions = [bb.xlen, bb.ylen, bb.zlen]
    dimensions_ok = all(abs(a-b)<.35 for a,b in zip(dimensions,expected))
    open_ok = outside<.05 and max(x['outside_five_pad_prisms_area'] for x in slices)<.10
    foot_section=body.intersect(cq.Face.makePlane(200,250,V(0,0 if upstream else 40,.3),V(0,0,1)))
    foot_faces=[]
    for f in foot_section.Faces():
        fb=f.BoundingBox();c=f.Center()
        foot_faces.append({'center_xy':[c.x,c.y],'diameters_xy':[fb.xlen,fb.ylen],'area_mm2':f.Area()})
    feet_ok=len(foot_faces)==5 and all(abs(f['area_mm2']-math.pi*4**2)<.10 and all(abs(v-8.0)<.03 for v in f['diameters_xy']) for f in foot_faces)
    return {'valid':body.isValid(),'connected_solids':len(body.Solids()),'bounds_mm':dimensions,
            'nominal_width_length_height':expected,'dimension_gate':dimensions_ok,
            'low_band_height_mm':p['host']['base_open_band'],'outside_five_pad_prisms_volume_mm3':outside,
            'low_band_slices':slices,'open_bottom_gate':open_ok,
            'actual_feet_at_z_0_3':foot_faces,'five_8mm_feet_gate':feet_ok,
            'pass':body.isValid() and len(body.Solids())==1 and dimensions_ok and open_ok and feet_ok}


def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--baseline',action='store_true'); ap.add_argument('--body',type=Path)
    args=ap.parse_args(); p=json.loads((HERE/'parameters.json').read_text(encoding='utf-8-sig'))
    out=ROOT/'reports/rebuild_r1'; out.mkdir(exist_ok=True,parents=True)
    path=args.body or (ROOT.parent/'_support/work/upstream_v09_audit/BODY.step' if args.baseline else ROOT/'exports/rebuild_r1/assembly/BODY.step')
    report=check(load(path),p,args.baseline)
    report['source']=str(path); report['expected_failure']=args.baseline
    target=out/('upstream_requirement_baseline.json' if args.baseline else 'requirements_geometry.json')
    target.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps({k:v for k,v in report.items() if k!='low_band_slices'},indent=2))
    if args.baseline:
        assert not report['dimension_gate'] and not report['open_bottom_gate'], 'Baseline must expose both known failures'
    else:
        assert report['pass'], 'Geometry requirement gate failed'


if __name__=='__main__':main()

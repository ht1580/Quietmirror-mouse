"""Independent V0.9 design checks on saved meshes and intermediate crown.

This audits actual saved apertures and shared touch surfaces. It does not infer
physical strength, mechanism quality or a global aperture count from metadata.
"""
from pathlib import Path
import argparse
import json
import hashlib
import math
import sys
import numpy as np
import cadquery as cq
import trimesh
from shapely.geometry import Point, Polygon

ROOT=Path(__file__).resolve().parents[1]
WORK=ROOT.parent/'_support/work'
OUT=ROOT/'exports/v09/placed'
RP=ROOT/'reports/v09'
CACHE=WORK/'v09_build'


def roof_heights(mesh,xd):
    """Highest vertical hit at each given plan location; NaN means no hit."""
    xy=np.asarray(xd,float)
    origins=np.column_stack((xy[:,0],-xy[:,1],np.full(len(xy),45.)))
    directions=np.tile([0.,0.,-1.],(len(origins),1))
    locations,ray_ids,_=mesh.ray.intersects_location(origins,directions,multiple_hits=True)
    heights=np.full(len(xy),np.nan)
    for q,i in zip(locations,ray_ids):
        if not np.isfinite(heights[i]) or q[2]>heights[i]:heights[i]=q[2]
    return heights


def as_float(value):
    return float(value) if np.isfinite(value) else None


def finite_json(value):
    if isinstance(value,dict):return {k:finite_json(v) for k,v in value.items()}
    if isinstance(value,list):return [finite_json(v) for v in value]
    if isinstance(value,(float,np.floating)) and not np.isfinite(value):return None
    return value


def metadata_check(holes):
    rows=[];polys={};valid=True
    for h in holes:
        points=h.get('triangle_xd_mm',[])
        sharp=Polygon(points) if len(points)>=3 else Polygon()
        rounded=Polygon(h.get('rounded_xd_mm',[]))
        okay=(len(points)==3 and sharp.is_valid and sharp.area>5 and rounded.is_valid and rounded.area>5 and rounded.difference(sharp.buffer(.02)).area<.01)
        valid=valid and okay
        rows.append(dict(id=h.get('id'),zone=h.get('zone'),triangle_vertices=len(points),triangle_area_mm2=sharp.area,rounded_area_mm2=rounded.area,pass_check=bool(okay)))
        polys[h['id']]=rounded
    spacing=[]
    for zone in ('roof','base'):
        subset=[h for h in holes if h.get('zone')==zone]
        pairs=[(polys[a['id']].distance(polys[b['id']]),a['id'],b['id']) for i,a in enumerate(subset) for b in subset[i+1:]]
        nearest=min(pairs) if pairs else (0.,None,None)
        okay=len(subset)>0 and nearest[0]>=1.75
        valid=valid and okay
        spacing.append(dict(zone=zone,profile_count=len(subset),minimum_gap_mm=nearest[0],nearest_pair=list(nearest[1:]),required_gap_mm=1.75,pass_check=bool(okay)))
    return dict(pass_check=bool(valid),holes=rows,spacing=spacing,limits='Metadata profiles describe cutters, not a count of final independent physical openings.'),polys


def base_section_check(body,holes,polys):
    section=body.section(plane_origin=[0,0,1.8],plane_normal=[0,0,1])
    if section is None:return dict(pass_check=False,error='BODY has no Z1.8 section')
    loops=[]
    for line in section.discrete:
        if len(line)<4 or np.linalg.norm(line[0]-line[-1])>.001:continue
        poly=Polygon([(float(x),-float(y)) for x,y,_ in line])
        if poly.is_valid and poly.area>.1:loops.append(poly)
    rows=[]
    for h in holes:
        if h.get('zone')!='base':continue
        expected=polys[h['id']];candidates=[q for q in loops if q.covers(expected.centroid)]
        if not candidates:
            rows.append(dict(id=h['id'],pass_check=False,error='No closed section loop contains intended hole centre'))
            continue
        actual=min(candidates,key=lambda q:q.area)
        delta=actual.symmetric_difference(expected).area
        hausdorff=actual.boundary.hausdorff_distance(expected.boundary)
        area_limit=max(.8,.03*expected.area)
        okay=delta<=area_limit and hausdorff<=.12
        rows.append(dict(id=h['id'],expected_area_mm2=expected.area,actual_section_loop_area_mm2=actual.area,symmetric_difference_mm2=delta,area_difference_limit_mm2=area_limit,boundary_hausdorff_mm=hausdorff,boundary_limit_mm=.12,pass_check=bool(okay)))
    return dict(pass_check=bool(rows and all(r['pass_check'] for r in rows)),section_z_mm=1.8,closed_section_loops=len(loops),holes=rows,method='Smallest actual closed BODY mesh section loop containing each intended hole centre; full area and boundary comparison detects filled holes or merger with a neighbouring/function opening at this section.',limits='Proves base aperture profiles only at Z1.8; does not claim all heights are identical or count all openings globally.')


def roof_aperture_check(body,outer,holes,polys):
    points=[];samples=[]
    for h in holes:
        if h.get('zone')!='roof':continue
        poly=polys[h['id']];tri=np.asarray(h['triangle_xd_mm'],float);centre=np.asarray([poly.centroid.x,poly.centroid.y])
        inside=[centre]+[centre+.43*(a-centre) for a in tri]
        for xy in inside:
            if not poly.contains(Point(xy)):raise AssertionError(('unsafe roof probe',h['id'],xy))
            points.append(xy);samples.append((h['id'],'inside'))
        # Probe a complete ring rather than only the three straight sides.
        ring=poly.buffer(.35,quad_segs=6).exterior
        for distance in np.linspace(0,ring.length,12,endpoint=False):
            pt=ring.interpolate(float(distance));points.append([pt.x,pt.y]);samples.append((h['id'],'rim'))
    oh=roof_heights(outer,points);bh=roof_heights(body,points)
    byid={h['id']:dict(id=h['id'],inside_samples=0,inside_failures=0,rim_samples=0,rim_failures=0,minimum_skin_removal_depth_mm=None,maximum_rim_height_error_mm=0.) for h in holes if h.get('zone')=='roof'}
    probes=[]
    for xy,(name,kind),top,body_top in zip(points,samples,oh,bh):
        row=byid[name]
        if kind=='inside':
            # Removing at least 1.0 mm at the sample proves the outer skin is open;
            # deeper internal supports may still be visible through the aperture.
            delta=top-body_top if np.isfinite(body_top) else math.inf
            okay=np.isfinite(top) and delta>=1.0
            row['inside_samples']+=1;row['inside_failures']+=int(not okay)
            if np.isfinite(delta):row['minimum_skin_removal_depth_mm']=float(delta) if row['minimum_skin_removal_depth_mm'] is None else min(row['minimum_skin_removal_depth_mm'],float(delta))
        else:
            delta=abs(body_top-top)
            okay=np.isfinite(top) and np.isfinite(body_top) and delta<=.12
            row['rim_samples']+=1;row['rim_failures']+=int(not okay)
            row['maximum_rim_height_error_mm']=max(row['maximum_rim_height_error_mm'] or 0.,float(delta)) if np.isfinite(delta) else None
        if not okay:probes.append(dict(id=name,kind=kind,point_xd_mm=list(map(float,xy)),outer_z_mm=as_float(top),body_z_mm=as_float(body_top)))
    rows=list(byid.values())
    for row in rows:row['pass_check']=row['inside_failures']==0 and row['rim_failures']==0
    return dict(pass_check=bool(rows and all(r['pass_check'] for r in rows)),holes=rows,failed_samples=probes,inside_depth_required_mm=1.,rim_height_tolerance_mm=.12,method='Final BODY and cached mother-crown vertical rays: four internal probes plus twelve probes on a ring 0.35 mm outside every roof triangle.',limits='Checks sampled skin openings and surrounding rim continuity. Finite ring probes cannot prove global hole independence, minimum web thickness at every location, or complete unobstructed sight through all internal mechanisms. Cutter-profile count is not reported as the actual independent aperture count.')


def key_surface_check(outer,p):
    rows=[]
    for module,keyname in (('left','left_key'),('right','right_key')):
        k=p[keyname]
        points=[[float(k['x']+x),float(k['y']+d)] for d in np.linspace(-k['length']/2+1,k['length']/2-1,11) for x in np.linspace(-k['width']/2+1,k['width']/2-1,9)]
        key=trimesh.load_mesh(OUT/(module+'_KEY.stl'))
        kh=roof_heights(key,points);oh=roof_heights(outer,points)
        error=np.abs(kh-oh);missing=int((~np.isfinite(error)).sum())
        maximum=float(np.nanmax(error)) if missing<len(error) else math.inf
        rows.append(dict(part=module+'_KEY',samples=len(points),missing_samples=missing,maximum_height_error_mm=maximum,median_height_error_mm=float(np.nanmedian(error)) if missing<len(error) else None,required_maximum_mm=.12,plan_size_mm=[k['width'],k['length']],sample_range_xd_mm=[[min(a[i] for a in points),max(a[i] for a in points)] for i in (0,1)],pass_check=bool(missing==0 and maximum<=.12)))
    return dict(pass_check=bool(all(r['pass_check'] for r in rows)),parts=rows,method='Compare saved main-key topmost mesh hits with the saved unperforated mother crown on a 9 x 11 inset grid for each 23 x 27 mm touch face.',limits='Proves sampled outer-height agreement and catches a raised plate. Does not prove physical click force, cap thickness or every boundary point.')


def rear_profile_check(outer,p):
    d=np.linspace(45.,89.,177)*float(p['length'])/90.
    heights=roof_heights(outer,np.column_stack((np.zeros(len(d)),d)))
    s=(d/(float(p['length'])/90.)-44.)/46.
    expected=(26.-15.3*s*s-8.2*s**3)*float(p['height'])/26.
    finite=bool(np.all(np.isfinite(heights)))
    delta=np.diff(heights);slopes=delta/np.diff(d)
    max_rise=float(max(0.,np.max(delta))) if finite else math.inf
    max_error=float(np.max(np.abs(heights-expected))) if finite else math.inf
    max_slope_jump=float(np.max(np.abs(np.diff(slopes)))) if finite else math.inf
    okay=finite and max_rise<=.015 and max_error<=.07 and max_slope_jump<=.20
    return dict(pass_check=bool(okay),samples=len(d),x_mm=0.,distance_range_mm=[float(d[0]),float(d[-1])],maximum_local_rise_mm=max_rise,maximum_hermite_height_error_mm=max_error,maximum_adjacent_slope_change=max_slope_jump,limits=dict(maximum_rise_mm=.015,maximum_height_error_mm=.07,maximum_adjacent_slope_change=.20),sampled_profile=[dict(d_mm=float(dd),outer_z_mm=as_float(h),expected_z_mm=float(e)) for dd,h,e in zip(d,heights,expected)],method='Actual saved unperforated crown centreline against the specified single-span Hermite rear; checks monotone descent and bounded local slope changes.',scope='Crown centreline only, D45..89. No claim of mathematical C2 continuity of an STL tessellation or of every off-centre section.')


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--metadata-only',action='store_true');args=ap.parse_args()
    RP.mkdir(parents=True,exist_ok=True);WORK.mkdir(parents=True,exist_ok=True)
    layout=json.loads((RP/'vent_layout.json').read_text(encoding='utf8'))
    holes=layout['holes'];result=dict(version='0.9',units='mm',source='Saved final meshes and cached unperforated crown; independent checks do not invoke the geometry generator')
    result['source_metrics_sha256']=hashlib.sha256((RP/'cad_metrics.json').read_bytes()).hexdigest()
    meta,polys=metadata_check(holes);result['triangular_profiles']=meta
    if not args.metadata_only:
        body=trimesh.load_mesh(OUT/'BODY.stl')
        step=CACHE/'outer.step';stl=WORK/'v09_design_outer.stl'
        if not stl.exists() or stl.stat().st_mtime<step.stat().st_mtime:
            shape=cq.importers.importStep(str(step)).val()
            shape.exportStl(str(stl),tolerance=.015,angularTolerance=.12,relative=False,parallel=False)
        outer=trimesh.load_mesh(stl)
        p=json.loads((RP/'cad_metrics.json').read_text(encoding='utf8'))['parameters']
        for name,check in (('base_actual_section',lambda:base_section_check(body,holes,polys)),('roof_actual_apertures',lambda:roof_aperture_check(body,outer,holes,polys)),('main_key_surface',lambda:key_surface_check(outer,p)),('rear_crown_profile',lambda:rear_profile_check(outer,p))):
            print('Checking',name,flush=True)
            result[name]=check();print(name,'PASS' if result[name]['pass_check'] else 'FAIL',flush=True)
    result['pass_check']=all(v['pass_check'] for v in result.values() if isinstance(v,dict) and 'pass_check' in v)
    result['verification_scope']='metadata only' if args.metadata_only else 'metadata plus actual base cross-sections, sampled roof rim/openings, sampled key heights and rear crown'
    result['limits']='No physical print, force, friction, strength or fatigue test. These checks do not certify a global minimum thickness or count final independent apertures from cutter metadata.'
    destination=RP/('design_metadata_checks.json' if args.metadata_only else 'design_checks.json')
    destination.write_text(json.dumps(finite_json(result),indent=2,allow_nan=False),encoding='utf8')
    print(destination,'PASS' if result['pass_check'] else 'FAIL',flush=True)
    if not result['pass_check']:sys.exit(1)

if __name__=='__main__':main()

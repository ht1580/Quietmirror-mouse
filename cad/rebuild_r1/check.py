"""Check exported artifacts independently, including actual collision poses."""
from pathlib import Path
import ctypes, hashlib, itertools, json, math
import cadquery as cq
import numpy as np
import trimesh
import pymeshlab
from check_requirements import check as requirements

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
OUT=ROOT/'exports/rebuild_r1';RP=ROOT/'reports/rebuild_r1'


def dump(name,d):
    (RP/name).write_text(json.dumps(d,indent=2,ensure_ascii=False)+'\n',encoding='utf-8',newline='\n')


def possible(a,b):
    aa=a.BoundingBox();bb=b.BoundingBox()
    return all(x[1]>y[0]+1e-6 and y[1]>x[0]+1e-6 for x,y in zip(
        [(aa.xmin,aa.xmax),(aa.ymin,aa.ymax),(aa.zmin,aa.zmax)],
        [(bb.xmin,bb.xmax),(bb.ymin,bb.ymax),(bb.zmin,bb.zmax)]))


def overlap(a,b):
    return max(0,a.intersect(b).Volume()) if possible(a,b) else 0.


def main():
    try:ctypes.windll.kernel32.SetPriorityClass(ctypes.c_void_p(-1),0x4000)
    except Exception:pass
    p=json.loads((HERE/'parameters.json').read_text(encoding='utf-8-sig'))
    meta=json.loads((RP/'design_metadata.json').read_text())
    metrics=json.loads((RP/'cad_metrics.json').read_text())
    shapes={n:cq.importers.importStep(str(OUT/f'assembly/{n}.step')).val() for n in metrics}
    printed=[n for n,v in metrics.items() if v['printable']]
    geometry=requirements(shapes['BODY'],p);dump('requirements_geometry.json',geometry)
    meshes=[]
    for n in printed:
        path=OUT/f'print/{n}.stl';m=trimesh.load_mesh(path,process=True)
        ms=pymeshlab.MeshSet();ms.load_new_mesh(str(path));ms.apply_filter('compute_selection_by_self_intersections_per_face')
        row={'part':n,'watertight':bool(m.is_watertight),'consistent_winding':bool(m.is_winding_consistent),
             'connected_components':len(m.split(only_watertight=False)),
             'self_intersecting_faces':ms.current_mesh().selected_face_number(),
             'faces':len(m.faces),'positive_volume':bool(m.volume>0),
             'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
        row['pass']=row['watertight'] and row['consistent_winding'] and row['connected_components']==1 and row['self_intersecting_faces']==0 and row['positive_volume']
        meshes.append(row);print('Mesh',n,row['pass'],flush=True)
    dump('mesh_checks.json',{'parts':meshes,'pass':all(x['pass'] for x in meshes)})
    static=[]
    for a,b in itertools.combinations(printed,2):
        v=overlap(shapes[a],shapes[b]);static.append({'a':a,'b':b,'overlap_mm3':v,'pass':v<.01})
    dump('static_collisions.json',{'pairs':static,'pass':all(x['pass'] for x in static)})
    motions=[]
    for motion in meta['mechanisms'].get('motions',[]):
        n=motion['part'];initial=shapes[n];rows=[]
        moving=[n,*motion.get('moving_children',[])]
        for i,t in enumerate(np.linspace(0,1,31)):
            if motion['kind']=='rotate':
                origin=motion['origin'];axis=motion['axis'];target=[a+b for a,b in zip(origin,axis)]
                posed={k:shapes[k].rotate(origin,target,float(t)*motion['end_deg']) for k in moving}
            else:posed={k:shapes[k].translate([float(t)*x for x in motion['end_vector']]) for k in moving}
            conflicts=[]
            for moved_name,moved in posed.items():
                for other in printed:
                    if other in moving:continue
                    volume=overlap(moved,shapes[other])
                    if volume>.01:conflicts.append({'moving':moved_name,'part':other,'overlap_mm3':volume})
            rows.append({'fraction':float(t),'conflicts':conflicts})
        motions.append({'part':n,'definition':motion,'poses':rows,'pass':all(not r['conflicts'] for r in rows)})
        print('Motion',n,motions[-1]['pass'],flush=True)
    dump('motion_checks.json',{'motions':motions,'poses_each':31,
         'pass':len(motions)>=4 and all(r['pass'] for r in motions),
         'scope':'Actual STEP intersections against other printed solids. Hardware contact/travel checks are reported separately; no force or return-life inference.'})
    summary={'geometry':geometry['pass'],'meshes':all(x['pass'] for x in meshes),
             'static_collisions':all(x['pass'] for x in static),
             'motion':len(motions)>=4 and all(r['pass'] for r in motions)}
    summary['pass']=all(summary.values());dump('acceptance.json',summary)
    print(json.dumps(summary,indent=2));assert summary['pass'], 'R1 geometry gate failed'


if __name__=='__main__':main()

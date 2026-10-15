"""V0.9 original smooth-front mechanical PLA mouse. Units millimetres.

Preserves V0.1-V0.8. Source geometry uses CadQuery/OpenCascade; native FreeCAD
assembly is produced separately from delivered STEP solids. CERN-OHL-P-2.0.
"""
from pathlib import Path
import argparse, copy, ctypes, json, time
import cadquery as cq
from cadquery.occ_impl.shapes import offset, extrude
import trimesh
from build_mouse import rounded_box, beam
from build_v03 import bounds
from build_v05 import clip_above, save_model
from mechanisms_v08 import union, pose, cartridge, side_face, side_opening as legacy_side_opening
from mechanisms_v09 import wheel_parts
from build_v08 import qmodule, print_pose, main_install_reliefs
from geometry_v09 import make_surfaces, build_base, roof_vents
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'exports/v09'
RP = ROOT/'reports/v09'
CACHE = ROOT.parent/'_support/work/v09_build'
V = cq.Vector
_FRONT_CACHE = {}

def checkpoint(name, shape):
    assert shape.isValid(), (name, 'invalid CAD')
    cq.exporters.export(shape, str(CACHE/f'{name}.step'))
    return shape

def main_roof_patch(k, outer, clearance=0.0):
    # Keep only the outer roof face; raw-skin/XY intersections also contain
    # inner-side-wall slivers and wrongly turn the fixed skirt into a key.
    width=k['width']+2*clearance;length=k['length']+2*clearance
    mask=rounded_box(width,length,80,2.5+clearance,(k['x'],-k['y'],30))
    face=max((f for f in outer.Faces() if f.geomType()=='BSPLINE'),key=lambda f:f.Area())
    patch=face.intersect(mask)
    assert len(patch.Faces())==1 and patch.isValid(), 'Roof face patch'
    return patch,mask

def main_touch(p, k, outer):
    token=(id(outer),k['x'],'touch')
    if token in _FRONT_CACHE:return _FRONT_CACHE[token]
    patch,mask=main_roof_patch(k,outer)
    touch=offset(patch,-float(p['main_key_surface']['thickness']),cap=True).clean()
    assert touch.isValid() and len(touch.Solids())==1, ('touch',len(touch.Solids()))
    _FRONT_CACHE[token]=touch
    return touch

def key_aperture(p, k, outer):
    token=(id(outer),k['x'],'pocket')
    if token in _FRONT_CACHE:return _FRONT_CACHE[token]
    patch,mask=main_roof_patch(k,outer,.4)
    pocket=offset(patch,-1.95,cap=True)
    swept=pocket.fuse(pocket.translate((0,0,-.4))).clean()
    # Expanded normal pockets overlap throughout the 0.4 mm press allowance.
    # Preserve their smooth offset end surfaces: trimming them again with the
    # XY mask or fusing nearly tangential micro-prisms creates invalid slivers.
    # Give the front clearance a real exit through the nose plane. Without
    # this extension the offset patch only touches Y=0, leaving a paper film.
    front_plane=cq.Face.makePlane(100,100,V(0,-.75,20),V(0,1,0))
    section=swept.intersect(front_plane)
    for face in section.Faces():swept=swept.fuse(extrude(face,(0,1.25,0))).clean()
    assert swept.isValid() and len(swept.Solids())==1,'front roof clearance'
    _FRONT_CACHE[token]=swept
    print('Front roof cavity',k['x'],'volume',swept.Volume(),'normal extra clearance',.35,flush=True)
    return swept

def side_opening(p,m):
    opening=legacy_side_opening(p,m)
    depth=float(m.get('side_entry_sweep_depth_mm',3.))
    if depth>3.:
        # The rear cartridge is lower than the exterior contact band. Extend
        # its shoulder entry outwards; leave the local Z<0 guide/stop intact.
        entry=pose(rounded_box(4.1,11.6,depth,.6,(0,0,depth/2)),m)
        opening=opening.fuse(entry)
    return opening

def side_internal_reliefs(p, shell):
    """Preserve V08 guide reliefs; match the rear tray floor and round ears.

    The old 18 x 10.2 rectangular floor clearance removes roof material over
    corners where the actual 9.8 x 9.8 tray has no material.  Rear clearance
    follows the 10.2 square and two R2.5 ears (actual ears R2.3), retaining the
    original local Z -11.4 .. -9.6 extent and the original retainer/rim reliefs.
    """
    for name, m in p['modules'].items():
        if not m.get('side'):
            continue
        q = qmodule(p, m)
        w, l = q['stem_xy']
        ret = rounded_box(w + 2.8, l + 4., 2.4, .8, (0, 0, -4.2))
        if name == 'thumb_rear':
            floor = rounded_box(10.2, 10.2, 1.8, 1, (0, 0, -10.5))
            for x in (-6.5, 6.5):
                floor = floor.fuse(cq.Solid.makeCylinder(2.5, 1.8, V(x, 0, -11.4)))
        else:
            floor = rounded_box(18., 10.2, 1.8, 1, (0, 0, -10.5))
        rim = rounded_box(10.2, 10.2, 3.5, .8, (0, 0, -7.85))
        for x in (-6.5, 6.5):
            rim = rim.cut(cq.Solid.makeCylinder(2.65, 7, V(x, 0, -11.3)))
        shell = shell.cut(pose(ret.fuse(floor).fuse(rim), m))
    return shell


def port_tool(p):
    u = p['usb_port']
    return rounded_box(u['width'],u['height'],16,u['radius'],(0,0,0)).rotate((0,0,0),(1,0,0),90).translate((0,-2,u['z']))

def adapt_side_origins(p, outer):
    for name, m in p['modules'].items():
        if not m.get('side'): continue
        _, y, z = m['origin']
        slice_box = cq.Workplane('XY').box(100,.08,.08).val().translate((0,y,z))
        section = outer.intersect(slice_box)
        m['origin'][0] = bounds(section)[0] + 4.0
        print('Side datum',name,m['origin'],flush=True)

def add_frames(p, shell, outer, raw):
    cap_sweeps = []
    for n in ('left_key','right_key'):
        cap_sweeps.append(key_aperture(p,p[n],outer))
    for name,m in p['modules'].items():
        fr = pose(cartridge(qmodule(p,m))['frame'],m)
        if name == 'middle':
            fr = fr.cut(cq.Workplane('XY').box(12.4,100,80).val().translate((0,20.6,30)))
        if m.get('side'):
            ring = rounded_box(11,17,8,1,(0,0,2)).cut(rounded_box(4.1,8.7,16,.8,(0,0,1)))
            ring = ring.cut(rounded_box(4.1,11.6,14,.6,(0,0,7.01)))
            fr = fr.fuse(pose(ring,m)).intersect(outer)
        elif name != 'middle':
            x,y,z = m['origin']; sign = 1 if x>0 else -1
            fr = fr.fuse(beam((x+sign*6.5,y,z-2),(sign*24.4,y,z-2),2.8)).intersect(outer)
        else:
            for sign in (-1,1):
                fr = fr.fuse(beam((sign*6.5,-33,16.5),(sign*30,-28,16.5),2.8))
            fr = fr.intersect(outer)
        for sweep in cap_sweeps: fr = fr.cut(sweep)
        shell = shell.fuse(fr)
        print('Joined frame',name,'solids',len(shell.Solids()),flush=True)
        checkpoint('frame_'+name,shell)
    for m in p['modules'].values():
        if m.get('side'): shell = shell.cut(side_opening(p,m))
    shell = side_internal_reliefs(p,shell)
    shell = main_install_reliefs(p,shell)
    # A short segment on the common surface is removed only for physical travel.
    for sweep in cap_sweeps: shell = shell.cut(sweep)
    shell = shell.cut(port_tool(p))
    shell = shell.clean()
    assert shell.isValid() and len(shell.Solids())==1, ('complete body',len(shell.Solids()))
    return shell

def build_shell(p, reuse_surfaces=False):
    print('Build smooth mother surfaces',flush=True)
    if reuse_surfaces:
        outer=cq.importers.importStep(str(CACHE/'outer.step')).val()
        raw=cq.importers.importStep(str(CACHE/'raw_skin.step')).val()
    else:
        outer, inner = make_surfaces(p)
        raw = checkpoint('raw_skin',outer.cut(inner))
        checkpoint('outer',outer)
    adapt_side_origins(p,outer)
    skin = raw.copy()
    cutters, roof_report = roof_vents(p,outer)
    for i, tool in enumerate(cutters):
        skin = skin.cut(tool,tol=1e-5)
        assert skin.isValid(), ('roof vent',i)
    print('Roof vent count',len(cutters),flush=True)
    base, base_report = build_base(p,outer)
    checkpoint('base',base)
    # A low front member supports the USB opening, below the same curved caps.
    nose = outer.intersect(cq.Workplane('XY').box(100,2.2,50).val().translate((0,-1.1,26)))
    shell = union([skin,base,nose])
    for name in ('left_key','right_key'):
        shell = shell.cut(key_aperture(p,p[name],outer))
    w=p['wheel']
    shell=shell.cut(rounded_box(w['opening_width'],w['opening_length'],70,2,(0,-w['y'],39.4)))
    cw,cl=w['carrier_install_opening_xy']
    shell=shell.cut(rounded_box(cw,cl,70,2,(0,-w['carrier_install_opening_d'],39.4)))
    shell=shell.cut(port_tool(p))
    # The solid front wall closes both key fronts and surrounds the USB port.
    # Retain its front 2 mm and >=1.7 mm USB ceiling; clear the narrow upper
    # central crown behind it into the wheel opening instead of leaving fins.
    wheel_entry=cq.Workplane('XY').box(7.2,6.5,40).val().translate((0,-5.25,32))
    shell=shell.cut(wheel_entry)
    for m in p['modules'].values():
        if m.get('side'): shell=shell.cut(side_opening(p,m))
    checkpoint('pre_frames',shell)
    layout=dict(version='0.9',coordinate_system='X,D with Y=-D, millimetres',
        holes=roof_report.get('holes',[])+base_report.get('holes',[]),
        roof=roof_report,base=base_report,
        functional_opening_exceptions=['main-key movement/installation gaps','wheel and carrier installation','USB-C cable','sensor','power switch','side keys','fasteners and switch terminals'],
        method='Individually inset full triangles; functional interfaces retain their functional shapes.')
    (RP/'vent_layout.json').write_text(json.dumps(layout,indent=2),encoding='utf8')
    (CACHE/'runtime_parameters.json').write_text(json.dumps(p,indent=2),encoding='utf8')
    shell=add_frames(p,shell,outer,raw)
    checkpoint('BODY',shell)
    return shell,outer,raw,layout

def build_parts(p,shell,outer,raw):
    parts={'BODY':shell}
    meta={'BODY':dict(kind='fixed',color=[.37,.53,.57],print_quantity=1)}
    hardware={}
    for name,m in p['modules'].items():
        if name=='middle':continue
        pl=cartridge(qmodule(p,m))['plunger']
        if m.get('side'):
            cap=pose(pl.cut(clip_above(3.7)),m).fuse(side_face(p,m,outer))
        else:
            touch=main_touch(p,p['left_key' if name=='left' else 'right_key'],outer)
            cap=pose(pl,m).intersect(outer).fuse(touch)
        cap=cap.clean()
        assert cap.isValid() and len(cap.Solids())==1,('cap',name,len(cap.Solids()))
        parts[name+'_KEY']=cap
        meta[name+'_KEY']=dict(kind='moving',module=name,color=[.53,.66,.68] if m.get('side') else [.70,.79,.78],print_quantity=1)
    parts.update({k.upper():v for k,v in wheel_parts(p).items()})
    for name in ('WHEEL','AXLE','AXLE_WASHER','WHEEL_CARRIER','DETENT_LEAF'):
        meta[name]=dict(kind='wheel' if name=='WHEEL' else 'moving',module='middle',color=[.22,.27,.29] if name in ('WHEEL','AXLE','AXLE_WASHER') else [.72,.49,.24],print_quantity=1)
    for name,m in p['modules'].items():
        unit=cartridge(qmodule(p,m))
        for part in ('retainer','tray'):
            key=name+'_'+part.upper();parts[key]=pose(unit[part],m)
            meta[key]=dict(kind='moving' if part=='retainer' else 'fixed',module=name,color=[.64,.69,.70],print_quantity=1)
        hardware[name+'_SWITCH_EXAMPLE']=pose(unit['switch'],m)
    return parts,meta,hardware

def main():
    if hasattr(ctypes,'windll'): ctypes.windll.kernel32.SetPriorityClass(ctypes.c_void_p(-1),0x4000)
    ap=argparse.ArgumentParser();ap.add_argument('--reuse-shell',action='store_true');ap.add_argument('--reuse-core',action='store_true');ap.add_argument('--reuse-surfaces',action='store_true');ap.add_argument('--body-only',action='store_true');args=ap.parse_args()
    for d in (OUT,OUT/'placed',OUT/'print',RP,CACHE,ROOT/'.tools'):d.mkdir(parents=True,exist_ok=True)
    start=time.time();p=json.loads((ROOT/'cad/parameters_v09.json').read_text(encoding='utf8'))
    if args.reuse_shell or args.reuse_core:
        p=json.loads((CACHE/'runtime_parameters.json').read_text())
        outer=cq.importers.importStep(str(CACHE/'outer.step')).val()
        raw=cq.importers.importStep(str(CACHE/'raw_skin.step')).val()
        layout=json.loads((RP/'vent_layout.json').read_text())
        if args.reuse_shell:shell=cq.importers.importStep(str(CACHE/'BODY.step')).val()
        else:
            shell=add_frames(p,cq.importers.importStep(str(CACHE/'pre_frames.step')).val(),outer,raw)
            checkpoint('BODY',shell)
    else:shell,outer,raw,layout=build_shell(p,reuse_surfaces=args.reuse_surfaces)
    if args.body_only:
        print('BODY_ONLY_READY',time.time()-start,flush=True)
        return
    parts,meta,hardware=build_parts(p,shell,outer,raw)
    records=[];assembly=cq.Assembly(name='QUIETMIRROR_V09_PLA_MECHANICAL');scene=trimesh.Scene()
    for name,s in parts.items():
        print('Export',name,flush=True)
        r=save_model(s,name,OUT/'placed');flat=print_pose(s,name,p);pr=save_model(flat,name,OUT/'print')
        r.update(meta[name]);r.update(print_bounds=pr['bounds'],file=f'exports/v09/placed/{name}.stl',print_file=f'exports/v09/print/{name}.stl')
        records.append(r);assembly.add(s,name=name,color=cq.Color(*meta[name]['color']))
        mesh=trimesh.load_mesh(OUT/'placed'/f'{name}.stl');mesh.visual.face_colors=[int(x*255) for x in meta[name]['color']]+[255];scene.add_geometry(mesh,node_name=name)
    for name,s in hardware.items():
        cq.exporters.export(s,str(OUT/'placed'/f'{name}.step'))
        s.exportStl(str(OUT/'placed'/f'{name}.stl'),tolerance=.03,angularTolerance=.15,relative=False)
        assembly.add(s,name=name,color=cq.Color(.76,.31,.21))
    assembly.save(str(OUT/'quietmirror_V0.9_MECHANICAL_ASSEMBLY.step'))
    scene.units='mm';(OUT/'quietmirror_V0.9_VIEW_ONLY.3mf').write_bytes(trimesh.exchange.threemf.export_3MF(scene))
    report=dict(version='0.9',units='mm',parts=records,printable_parts=len(records),switch_examples=5,vent_count=len(layout['holes']),build_seconds=time.time()-start,parameters=p,
        geometry='Thin outer-face roof caps with fixed closed lower skirts and USB nose; front pitch retained. Reduced smooth rear and boundary-adapted triangular skeleton.',
        preserved='V0.1-V0.8 unchanged; original anterior contour/pitch, authorized reduced rear, 23x27 touch faces, five foot centres, sensor and mechanism dimensions retained.')
    (RP/'cad_metrics.json').write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf8')
    print('COMPLETE',len(records),'printable parts',report['build_seconds'],flush=True)

if __name__=='__main__':main()

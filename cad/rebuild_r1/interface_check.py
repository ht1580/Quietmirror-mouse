"""Independent exported-STEP checks for locked USB/sensor reservations.

Checks geometric paths, measured component sizes and real open bores. It does
not validate an electronic design, connector pinout or optical working distance.
"""
from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import time
from pathlib import Path

import cadquery as cq
import numpy as np
from OCP.BRepAdaptor import BRepAdaptor_Surface

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
OUT=ROOT/'exports/rebuild_r1'
RP=ROOT/'reports/rebuild_r1'
WORK=ROOT.parent/'_support/work/fenrir_rebuild'
EPS=.01
V=cq.Vector


def fingerprint(path):
    path=Path(path)
    return dict(file=str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else path.name,
                bytes=path.stat().st_size,sha256=hashlib.sha256(path.read_bytes()).hexdigest())


def bounds(shape):
    b=shape.BoundingBox()
    return dict(min=[b.xmin,b.ymin,b.zmin],max=[b.xmax,b.ymax,b.zmax],size=[b.xlen,b.ylen,b.zlen])


def possible(a,b):
    aa,bb=bounds(a),bounds(b)
    return all(xmax>ymin+1e-6 and ymax>xmin+1e-6 for xmin,xmax,ymin,ymax in
               zip(aa['min'],aa['max'],bb['min'],bb['max']))


def intersection(a,b):
    if not possible(a,b):
        return None,0.
    if a.distance(b)>1e-5:
        return None,0.
    common=a.intersect(b)
    volume=max(0.,common.Volume())
    return common,volume


def conflict(a,b,**labels):
    common,volume=intersection(a,b)
    if volume<=EPS:
        return None
    return dict(**labels,overlap_mm3=volume,
                intersection_centroid_mm=list(common.Center().toTuple()),
                intersection_bounds_mm=bounds(common))


def box(dx,dy,dz,center):
    return cq.Workplane('XY').box(dx,dy,dz).val().translate(center)


def cylinder(radius,height,point):
    return cq.Solid.makeCylinder(radius,height,V(*point),V(0,0,1))


def cylindrical_faces(shape):
    result=[]
    for face in shape.Faces():
        if face.geomType()!='CYLINDER':
            continue
        q=BRepAdaptor_Surface(face.wrapped,True).Cylinder()
        p,d=q.Location(),q.Axis().Direction()
        result.append(dict(radius_mm=q.Radius(),axis_point_mm=[p.X(),p.Y(),p.Z()],
                           axis_direction=[d.X(),d.Y(),d.Z()],area_mm2=face.Area()))
    return result


def measured_hole(faces,x,y,radius):
    matches=[f for f in faces if abs(f['radius_mm']-radius)<.015
             and abs(f['axis_direction'][2])>.999
             and np.linalg.norm(np.array(f['axis_point_mm'][:2])-[x,y])<.025]
    return dict(center_xy_mm=[x,y],target_diameter_mm=2*radius,
                measured_diameters_mm=[2*f['radius_mm'] for f in matches],
                cylindrical_face_found=bool(matches))


def dimension_check(name,shape,expected):
    actual=bounds(shape)
    error=[a-b for a,b in zip(actual['size'],expected)]
    return dict(part=name,expected_xyz_mm=expected,actual_bounds_mm=actual,
                dimension_error_mm=error,pass_check=all(abs(v)<.025 for v in error))


def self_test():
    a=box(2,2,2,(0,0,0))
    tests=[('separated',box(2,2,2,(3,0,0)),0.),
           ('touching',box(2,2,2,(2,0,0)),0.),
           ('partial',box(2,2,2,(1,0,0)),4.),
           ('contained',box(1,1,1,(0,0,0)),1.)]
    rows=[]
    for name,b,expected in tests:
        _,volume=intersection(a,b)
        rows.append(dict(name=name,expected_volume_mm3=expected,actual_volume_mm3=volume,
                         pass_check=abs(volume-expected)<1e-7))
    report=dict(tests=rows,pass_check=all(r['pass_check'] for r in rows))
    WORK.mkdir(parents=True,exist_ok=True)
    (WORK/'interface_boolean_self_test.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,indent=2))
    if not report['pass_check']:
        raise RuntimeError('Independent collision predicate self-test failed')


def run():
    start=time.time()
    p=json.loads((HERE/'parameters.json').read_text(encoding='utf-8-sig'))
    meta=json.loads((RP/'design_metadata.json').read_text(encoding='utf-8-sig'))
    metrics=json.loads((RP/'cad_metrics.json').read_text(encoding='utf-8-sig'))
    if meta['parameters']!=p:
        raise ValueError('Exported design parameters differ from current parameters; rebuild before checking')
    if 'interfaces' not in meta:
        raise ValueError('Exported assembly predates USB/sensor interfaces')
    files=[HERE/'parameters.json',RP/'design_metadata.json',RP/'cad_metrics.json']
    printed={}
    hardware={}
    for name,record in metrics.items():
        path=OUT/'assembly'/f'{name}.step'
        s=cq.importers.importStep(str(path)).val()
        if not s.isValid() or len(s.Solids())!=1:
            raise ValueError(f'Invalid exported solid: {name}')
        (printed if record['printable'] else hardware)[name]=s
        files.append(path)
    gauges={}
    for name in ('USB_PLUG_GAUGE','SENSOR_RESERVED_VOLUME','SENSOR_DOWNWARD_OPTICAL_PATH'):
        path=OUT/'gauges'/f'{name}.step'
        s=cq.importers.importStep(str(path)).val()
        if not s.isValid() or len(s.Solids())!=1:
            raise ValueError(f'Invalid interface gauge: {name}')
        gauges[name]=s;files.append(path)
    required=('USB_C_REFERENCE','USB_ADAPTER_PCB_REFERENCE')
    if any(n not in hardware for n in required):
        raise ValueError('Missing non-printable USB reference components')
    initial_inputs=[fingerprint(f) for f in files]
    findings=[]
    plug_poses=[]
    for fraction in np.linspace(0.,1.,31):
        dy=-30.*(1.-float(fraction))
        gauge=gauges['USB_PLUG_GAUGE'].translate((0,dy,0))
        failures=[]
        for name,part in printed.items():
            f=conflict(gauge,part,check='usb_plug_insertion',gauge='USB_PLUG_GAUGE',part=name,translation_y_mm=dy)
            if f:failures.append(f)
        plug_poses.append(dict(fraction=float(fraction),translation_y_mm=dy,conflicts=failures))
        findings.extend(failures)
    print('USB insertion',len(plug_poses),'poses, conflicts',sum(len(x['conflicts']) for x in plug_poses),flush=True)
    reservation=[]
    for name in ('SENSOR_RESERVED_VOLUME','SENSOR_DOWNWARD_OPTICAL_PATH'):
        failures=[]
        for part_name,part in printed.items():
            f=conflict(gauges[name],part,check='sensor_clearance',gauge=name,part=part_name)
            if f:failures.append(f)
        reservation.append(dict(gauge=name,bounds_mm=bounds(gauges[name]),conflicts=failures))
        findings.extend(failures)
    static=[]
    for name in required:
        for part_name,part in printed.items():
            f=conflict(hardware[name],part,check='usb_static',hardware=name,part=part_name)
            static.append(dict(hardware=name,part=part_name,conflict=f))
            if f:findings.append(f)
    print('Sensor/static reservations checked',flush=True)
    motions=[]
    definitions={m['part']:m for m in meta['mechanisms']['motions']}
    for name in ('LEFT_KEY','RIGHT_KEY'):
        m=definitions[name]
        if m['kind']!='rotate':
            raise ValueError(f'Unexpected main-key motion: {m}')
        moving=[name,*m.get('moving_children',[])]
        origin=m['origin'];end=[a+b for a,b in zip(origin,m['axis'])]
        poses=[]
        for fraction in np.linspace(0.,1.,31):
            angle=float(fraction)*m['end_deg'];failures=[]
            for moving_name in moving:
                part=printed[moving_name].rotate(origin,end,angle)
                for fixed_name in required:
                    f=conflict(part,hardware[fixed_name],check='pressed_key_usb_clearance',moving=moving_name,
                               hardware=fixed_name,fraction=float(fraction),angle_deg=angle)
                    if f:failures.append(f)
            poses.append(dict(fraction=float(fraction),angle_deg=angle,conflicts=failures))
            findings.extend(failures)
        motions.append(dict(part=name,definition=m,poses=poses,pass_check=all(not v['conflicts'] for v in poses)))
        print('Pressed key against USB',name,motions[-1]['pass_check'],flush=True)
    sizes=[dimension_check('USB_C_REFERENCE',hardware['USB_C_REFERENCE'],[8.94,7.35,3.31]),
           dimension_check('USB_ADAPTER_PCB_REFERENCE',hardware['USB_ADAPTER_PCB_REFERENCE'],[16.,10.,1.]),
           dimension_check('SENSOR_RESERVED_VOLUME',gauges['SENSOR_RESERVED_VOLUME'],[18.,18.,9.]),
           dimension_check('SENSOR_DOWNWARD_OPTICAL_PATH',gauges['SENSOR_DOWNWARD_OPTICAL_PATH'],[14.,18.,19.]),
           dimension_check('USB_PLUG_GAUGE',gauges['USB_PLUG_GAUGE'],[14.,26.5,8.])]
    body=printed['BODY'];body_faces=cylindrical_faces(body)
    pcb_faces=cylindrical_faces(hardware['USB_ADAPTER_PCB_REFERENCE'])
    usb_holes=[]
    for x in (-6.2,6.2):
        row=measured_hole(body_faces,x,19.5,.85)
        _,blocked=intersection(cylinder(.84,2.38,(x,19.5,5.61)),body)
        row.update(blocked_probe_volume_mm3=blocked,probe_diameter_mm=1.68,
                   probe_z_range_mm=[5.61,7.99],surround_material=body.isInside(V(x+1.4,19.5,7.0)))
        row['pass_check']=row['cylindrical_face_found'] and blocked<EPS and row['surround_material']
        usb_holes.append(row)
    pcb_holes=[]
    for x in (-6.2,6.2):
        row=measured_hole(pcb_faces,x,19.5,1.2)
        _,blocked=intersection(cylinder(1.19,.98,(x,19.5,8.01)),hardware['USB_ADAPTER_PCB_REFERENCE'])
        row['blocked_probe_volume_mm3']=blocked
        row['pass_check']=row['cylindrical_face_found'] and blocked<EPS
        pcb_holes.append(row)
    sensor_slots=[]
    for y in (43.,65.):
        for x in (-12.5,12.5):
            ends=[measured_hole(body_faces,x,y+dy,1.2) for dy in (-.8,.8)]
            probe=cylinder(1.19,2.38,(x,y-.8,10.41)).fuse(cylinder(1.19,2.38,(x,y+.8,10.41))).fuse(box(2.38,1.6,2.38,(x,y,11.6))).clean()
            _,blocked=intersection(probe,body)
            row=dict(center_xy_mm=[x,y],target_slot_width_mm=2.4,probe_width_mm=2.38,
                     cylindrical_end_faces=ends,blocked_probe_volume_mm3=blocked,
                     pass_check=all(v['cylindrical_face_found'] for v in ends) and blocked<EPS)
            sensor_slots.append(row)
    # An independently reconstructed, slightly undersize rectangular clearance
    # gauge checks the minimum reserved passage; the visible nose is wider.
    axis_z=9.+3.31/2
    port_probe=box(10.18,8.8,4.58,(0,9.,axis_z))
    _,port_blocked=intersection(port_probe,body)
    port_check=dict(nominal_width_height_mm=[10.2,4.6],probe_xyz_mm=[10.18,8.8,4.58],
                    probe_bounds_mm=bounds(port_probe),body_overlap_mm3=port_blocked,
                    pass_check=port_blocked<EPS,
                    meaning='Minimum reserved rectangular passage clearance, not a claim that the sculpted outer opening is exactly rectangular.')
    final_inputs=[fingerprint(f) for f in files]
    gates=dict(usb_plug_31_poses=all(not r['conflicts'] for r in plug_poses),
               sensor_reservation=all(not r['conflicts'] for r in reservation),
               usb_static=all(not r['conflict'] for r in static),
               main_key_31_poses=len(motions)==2 and all(r['pass_check'] for r in motions),
               fixed_component_dimensions=all(r['pass_check'] for r in sizes),
               actual_usb_pilot_bores=all(r['pass_check'] for r in usb_holes),
               actual_usb_pcb_holes=all(r['pass_check'] for r in pcb_holes),
               actual_sensor_mount_slots=all(r['pass_check'] for r in sensor_slots),
               reserved_usb_opening=port_check['pass_check'],
               unchanged_inputs=initial_inputs==final_inputs)
    return dict(gates=gates,pass_check=all(gates.values()),elapsed_seconds=time.time()-start,
                overlap_tolerance_mm3=EPS,inputs=initial_inputs,host_scale=p['host']['scale'],
                usb_plug_insertion=dict(poses=plug_poses,pose_count=31,
                     path='Translation Y -30 to 0 mm relative to seated gauge; all printed solids checked. The tip reaches the reference mating face, not a simulated hollow receptacle interior.'),
                sensor_clearance=reservation,usb_static=static,pressed_main_keys=motions,
                fixed_component_dimensions=sizes,actual_usb_pilot_bores=usb_holes,
                actual_usb_pcb_holes=pcb_holes,actual_sensor_mount_slots=sensor_slots,
                reserved_usb_opening=port_check,collision_findings=findings,
                scope='Independent exact BRep intersections against exported STEP; geometric mechanical reservations only. No verified electrical board, charging circuit, firmware, sensor lens working distance, wear life or print shrinkage inference.')


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--self-test',action='store_true')
    args=ap.parse_args()
    try:ctypes.windll.kernel32.SetPriorityClass(ctypes.c_void_p(-1),0x4000)
    except Exception:pass
    if args.self_test:
        self_test();return
    RP.mkdir(parents=True,exist_ok=True)
    try:
        report=run()
    except Exception as e:
        report=dict(pass_check=False,error_type=type(e).__name__,error=str(e))
    path=RP/'interface_checks.json'
    path.write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k in ('gates','pass_check','error','error_type','elapsed_seconds')},indent=2))
    if not report['pass_check']:
        raise SystemExit(1)


if __name__=='__main__':main()

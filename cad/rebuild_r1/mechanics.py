"""New R1 pinned keys and suspended supports; no inherited v0.9 mechanisms.

All dimensions are millimetres.  Purchased switch envelopes are documented
installation references, not a claim to fit an unmeasured Fenrir donor PCB.
"""
from __future__ import annotations

import math
import cadquery as cq
from surfaces import half_width, roof_height, roof_z

V = cq.Vector


def box(dx, dy, dz, center):
    return cq.Workplane('XY').box(dx, dy, dz).val().translate(center)


def cylinder(radius, length, point, direction=(0, 0, 1)):
    return cq.Solid.makeCylinder(radius, length, V(*point), V(*direction))


def join(*shapes):
    result = shapes[0]
    for item in shapes[1:]:
        result = result.fuse(item)
    return result.clean()


def beam(a, b, radius):
    direction = V(*b)-V(*a)
    return join(cq.Solid.makeCylinder(radius, direction.Length, V(*a), direction.normalized()),
                cq.Solid.makeSphere(radius, V(*a)), cq.Solid.makeSphere(radius, V(*b)))


def check(shape, name, single=True):
    if not shape.isValid() or (single and len(shape.Solids()) != 1):
        raise ValueError(f'{name}: valid={shape.isValid()}, solids={len(shape.Solids())}')
    return shape


def top(outer, x, y):
    line = cq.Edge.makeLine(V(x, y, 0), V(x, y, 65))
    points = outer.intersect(line).Vertices()
    if not points:
        return roof_z(x, y)
    return max(v.Z for v in points)


def rounded_block(dx, dy, dz, center, radius=.55):
    w = cq.Workplane('XY').box(dx, dy, dz)
    try:
        w = w.edges().fillet(radius)
    except Exception:
        pass
    return w.val().translate(center)


def build_mechanics(p, outer, inner):
    additions, cuts, parts, hardware = [], [], {}, {}
    bolt_paths=[]
    meta = dict(feet=[], main_hinges=[], side_motions=[], motions=[],
                printed_interfaces=[], installation=[], hardware_limitations=[])
    mh = p['main']; hh = p['hardware']
    root_y = float(mh.get('root_y', 35.0))+.5
    travel_deg = max(2.1,float(mh.get('travel_deg', 2.0)))
    skin = float(mh.get('skin', 2.0))
    pin_d = float(mh.get('pin_diameter', 2.0))
    bore = float(mh.get('pin_hole', 2.35))
    gutter = float(mh.get('gutter_half', 4.2))
    outer_x = float(mh.get('cap_outer', 26.0))

    # Every low horizontal cut contains only five disks/their own stems.
    for i, (x, y) in enumerate(p['feet']['centers'], 1):
        foot = cylinder(p['feet']['diameter']/2, p['feet']['height'], (x,y,0))
        stem_top = min(8.3,roof_height(y,p)-.3) if i==5 else 8.3
        stem = cylinder(p['feet']['stem_diameter']/2, stem_top-1.5, (x,y,1.5))
        if i == 5:
            end = (0., 70.2, roof_height(70.2,p)-.7)
            radius = 1.8
        else:
            yy = 10.0 if y < 20 else y
            end = (math.copysign(half_width(yy,p)-.35,x), yy,
                   7.5 if y < 20 else 11.2)
            radius = 1.7
        start_z = max(5.01+radius,stem_top-.8) if i==5 else 7.4
        strut = beam((x,y,start_z),end,radius).intersect(outer)
        support = check(join(foot,stem,strut),f'FOOT_{i}_SUPPORT')
        additions.append(support)
        meta['feet'].append(dict(index=i,center=[x,y],diameter_mm=p['feet']['diameter'],
             contact_z=0.,pad_top_z=p['feet']['height'],stem_diameter_mm=p['feet']['stem_diameter'],
             upper_connection=list(end),load_path='vertical foot stem to raised side/crown brace; no bottom plate'))

    roof_skin = outer.cut(outer.translate((0,0,-skin)))
    roof_pocket = outer.cut(outer.translate((0,0,-skin-1.2)))
    for sign, name, sw_name in ((-1,'LEFT_KEY','SWITCH_LEFT'),(1,'RIGHT_KEY','SWITCH_RIGHT')):
        cx = sign*(gutter+outer_x)/2
        cap_mask = box(outer_x-gutter,34.5,60,(cx,17.25,30))
        cap = roof_skin.intersect(cap_mask)
        # Trim only the very low side sliver; keep the contoured upper touch face.
        cap = cap.intersect(box(80,90,55,(0,40,34.0)))
        # Local wheel/encoder access bay. The solid contact area over the
        # main microswitch remains at |X|=15; only the inner edge retreats.
        notch = rounded_block(19.,17.,50.,(0,25.0,27.),1.0)
        cap = cap.cut(notch).clean()
        # The outer key edge slopes down. Set the pin beneath that edge,
        # rather than beneath the higher centre of the key, so the fixed
        # outside bearing cannot pierce the moving touch skin.
        pivot_z = top(outer,sign*23.4,root_y)-5.3
        pivot = [0.,root_y,pivot_z]
        barrel = cylinder(2.65,13.2,(sign*15-6.6,root_y,pivot_z),(1,0,0))
        web_top = top(outer,sign*15,33.8)-.4
        web = box(11.8,3.0,max(2.,web_top-pivot_z),(sign*15,33.8,(web_top+pivot_z)/2))
        cap = join(cap,barrel,web)
        cap = cap.cut(cylinder(bore/2,18,(sign*15-9,root_y,pivot_z),(1,0,0))).clean()
        parts[name] = check(cap,name)
        pocket_mask = box(outer_x-gutter+.6,35.1,60,(cx,17.25,30))
        cuts.append(roof_pocket.intersect(pocket_mask))
        # Fixed axle bearings are outside the moving barrel, attached behind
        # the key aperture by tall roof-intersecting lugs.
        ears=[]
        for ax in (sign*15-8.4, sign*15+8.4):
            ear = cylinder(2.85,2.4,(ax-1.2,root_y,pivot_z),(1,0,0))
            roof_t = top(outer,ax,38.8)
            lug = box(2.4,4.5,roof_t-pivot_z+.5,(ax,38.,(roof_t+pivot_z+.5)/2))
            ear = join(ear,lug).intersect(outer)
            ear = ear.cut(cylinder(bore/2,4,(ax-2,root_y,pivot_z),(1,0,0))).clean()
            ears.append(check(ear,name+'_FIXED_BEARING'))
        additions.extend(ears)
        hardware[name+'_STEEL_PIN'] = cylinder(pin_d/2,21.8,(sign*15-10.9,root_y,pivot_z),(1,0,0))
        # Actual lateral tool/pin entry through the retained fixed side skin.
        cuts.append(cylinder(bore/2,82.,(-41.,root_y,pivot_z),(1,0,0)))

        # Conservative complete D2F envelope + separate visible plunger.  This
        # is an explicitly generic socket, not a donor-PCB hole pattern.
        sw_y = 20.0
        touch_z = top(outer,sign*15,sw_y)-skin
        switch_base = touch_z-7.53
        tilt=18.0
        tilt_origin=(0.,sw_y,touch_z-.03)
        tilt_axis=(1.,sw_y,touch_z-.03)
        def tilted(shape):return shape.rotate(tilt_origin,tilt_axis,tilt)
        def tilted_point(point):
            x,y,z=point;dy=y-sw_y;dz=z-(touch_z-.03);a=math.radians(tilt)
            return [x,sw_y+dy*math.cos(a)-dz*math.sin(a),touch_z-.03+dy*math.sin(a)+dz*math.cos(a)]
        # D2F drawing: the plunger is 4.4 from the front, mounting-hole
        # centres -1.3/+5.2 from it, 1.5 above the housing bottom.
        switch = box(5.8,12.8,6.5,(sign*15,sw_y+2.,switch_base+3.25))
        switch = join(switch,cq.Solid.makeSphere(1.1,V(sign*15,sw_y,switch_base+6.4)))
        tray=box(8.6,15.4,1.8,(sign*15,sw_y+2.,switch_base-.9))
        holders=[]
        holes=[]
        for jj,dy in enumerate((-1.3,5.2)):
            cy=sw_y+dy;hz=switch_base+1.5
            switch=switch.cut(cylinder(1.0,9.,(sign*15-4.5,cy,hz),(1,0,0)))
            for dx in (-4.3,4.3):
                inward = dx*sign < 0
                hx=sign*11.15 if inward else sign*15+dx
                holder=box(1.3 if inward else 2.,3.6,3.8,(hx,cy,switch_base+1.5))
                holder=holder.cut(cylinder(1.175,4.,(hx-2,cy,hz),(1,0,0)))
                holders.append(holder)
            hardware[name+f'_M2_SWITCH_BOLT_{jj+1}']=tilted(cylinder(1.,12.,(sign*15-6.,cy,hz),(1,0,0)))
            bolt_paths.append(tilted(cylinder(1.2,82.,(-41.,cy,hz),(1,0,0))))
            holes.append(tilted_point((sign*15,cy,hz)))
        tray=tilted(join(tray,*holders))
        anchor=tilted_point((sign*20.5,sw_y+2.0,switch_base-.9))
        sidewall_x=sign*(half_width(anchor[1],p)-.35)
        arm=beam(anchor,(sidewall_x,anchor[1],anchor[2]),1.6).intersect(outer)
        tray=join(tray,arm)
        if tray.BoundingBox().zmin < 5.01:
            raise ValueError(f'{name} tilted socket violates open band: {tray.BoundingBox().zmin}')
        additions.append(check(tray,name+'_SUSPENDED_TRAY'))
        hardware[sw_name]=check(tilted(switch.clean()),sw_name)

        # Narrow end-stop shoe near the outside of each cap. Its upper face
        # matches a selected point of the key at the final angle, and joins
        # the retained low side skin below the key pocket.
        stop_x,stop_y = sign*23.,11.5
        stop_initial = [stop_x,stop_y,top(outer,stop_x,stop_y)-skin]
        a = math.radians(travel_deg)
        dy,dz = stop_initial[1]-root_y,stop_initial[2]-pivot_z
        stop_z = pivot_z+dy*math.sin(a)+dz*math.cos(a)-.04
        sx = sign*(half_width(stop_y,p)-.2)
        shoe = box(2.,2.,1.2,(stop_x,stop_y,stop_z-.6))
        stop_arm = beam((stop_x,stop_y,stop_z-.65),(sx,stop_y,stop_z-.65),.85).intersect(outer)
        additions.append(check(join(shoe,stop_arm),name+'_HARD_STOP'))
        end_displacement = abs((sw_y-root_y)*math.sin(a)+(touch_z-pivot_z)*(math.cos(a)-1))
        info=dict(part=name,origin=pivot,axis=[1,0,0],end_deg=travel_deg,
           pin_diameter_mm=pin_d,bore_diameter_mm=bore,diametral_clearance_mm=bore-pin_d,
           actuation_point=[sign*15,sw_y,touch_z],switch=sw_name,
           nominal_actuator_gap_mm=.03,calculated_contact_travel_mm=end_displacement-.03,
           stop_reference_point=stop_initial,stop_reference_z=stop_z,
           switch_tilt_deg=tilt,switch_mount_holes=holes,
           switch_mount='local 18 degree tilted socket; two M2 transverse bolts through actual D2F mounting holes; nuts/washers purchased separately')
        meta['main_hinges'].append(info)
        meta['motions'].append(dict(info,kind='rotate'))

    # Both side buttons are captured sliding keys with a removable steel
    # cross-pin behind the guide. The frame shoulders provide hard stops.
    for index,(cy,name,sw_name) in enumerate(zip(p['side']['centers_y'],
         ('SIDE_FRONT_KEY','SIDE_REAR_KEY'),('SWITCH_SIDE_FRONT','SWITCH_SIDE_REAR'))):
        cz=float(p['side']['z']); h=roof_height(cy,p); w=half_width(cy,p)
        fraction=max(0.,min(1.,(cz-5)/(h-5)))
        wall_x=-w*max(0.,1-fraction**3.4)**(1/3.4)
        cap=rounded_block(2.,10.,5.,(wall_x+.2,cy,cz),.55)
        tongue=box(6.1,3.4,3.4,(wall_x+4.05,cy,cz))
        key=join(cap,tongue)
        pin_x=wall_x+5.75
        key=key.cut(cylinder(.86,8,(pin_x,cy,cz-4))).clean()
        parts[name]=check(key,name)
        hardware[name+'_CAPTURE_PIN']=cylinder(.75,6.,(pin_x,cy,cz-3.))
        cuts.append(box(22,10.7,5.7,(wall_x+3,cy,cz)))
        frame=box(2.4,7.4,7.4,(wall_x+3.8,cy,cz))
        frame=frame.cut(box(5,4.05,4.05,(wall_x+3.8,cy,cz)))
        shoulders=[box(2.,1.8,3.2,(wall_x+2.8,cy+v,cz)) for v in (-4.3,4.3)]
        bridge=box(1.5,11.4,7.4,(wall_x+3.8,cy,cz)).cut(box(3,4.05,4.05,(wall_x+3.8,cy,cz)))
        flange=box(3.8,13.3,8.7,(wall_x+1.5,cy,cz)).intersect(outer)
        flange=flange.cut(box(10,10.7,5.7,(wall_x+1.5,cy,cz)))
        frame=join(frame,bridge,flange,*shoulders)
        # Side switch's long axis is +Y and its plunger points outwards -X.
        body_near=wall_x+7.72
        sw=box(6.5,12.8,5.8,(body_near+3.25,cy+2.,cz))
        sw=join(sw,cylinder(1.0,.62,(body_near+.02,cy,cz),(-1,0,0)))
        # Small upper/bottom rails and a far-end fence form the socket; these
        # remain local rather than spanning the underside as a floor.
        rails=[box(11.8,14.4,1.35,(wall_x+10.4,cy+2.,cz+v)) for v in (-4.0,4.0)]
        fence=box(1.4,12.4,9.35,(body_near+7.6,cy+2.,cz))
        frame=join(frame,*rails,fence)
        side_holes=[]
        for jj,dy in enumerate((-1.3,5.2)):
            hx,hy=body_near+5.,cy+dy
            sw=sw.cut(cylinder(1.,8.,(hx,hy,cz-4.)))
            frame=frame.cut(cylinder(1.2,12.,(hx,hy,cz-6.)))
            hardware[name+f'_M2_SWITCH_BOLT_{jj+1}']=cylinder(1.,10.,(hx,hy,cz-5.))
            side_holes.append([hx,hy,cz])
        hardware[sw_name]=check(sw.clean(),sw_name)
        frame=frame.clean()
        additions.append(check(frame,name+'_GUIDE_AND_SUSPENDED_SOCKET'))
        move=.60
        m=dict(part=name,kind='translate',end_vector=[move,0.,0.],switch=sw_name,
             actuation_point=[wall_x+7.1,cy,cz],plunger_tip=[body_near-.6,cy,cz],
             nominal_actuator_gap_mm=.02,hard_stop_travel_mm=move,
             guide_clearance_per_side_mm=.325,capture_pin_diameter_mm=1.5,
             capture_pin_hole_mm=1.72,
             switch_mount_holes=side_holes,switch_mount='two M2 bolts along Z through D2F mounting holes and local suspended top/bottom rails',
             assembly='Insert key from exterior, then 1.5 mm steel capture pin along Z from open top before switch socket is filled')
        meta['side_motions'].append(m);meta['motions'].append(m)

    # The wheel and encoder move together on a genuinely pinned click
    # carrier. Local key notches above provide room for the encoder housing.
    wy,wz=25.,17.5
    carrier_pivot=[0.,38.5,17.5]
    wheel=cylinder(hh['wheel_diameter']/2,hh['wheel_width'],(-hh['wheel_width']/2,wy,wz),(1,0,0))
    def hex_prism(af,length,x):
        rr=af/math.sqrt(3)
        points=[V(x,wy+rr*math.cos(k*math.pi/3),wz+rr*math.sin(k*math.pi/3)) for k in range(6)]
        wire=cq.Wire.makePolygon(points+[points[0]])
        return cq.Solid.extrudeLinear(wire,[],V(length,0,0))
    # Integral hex driver is a replaceable PLA prototype feature; a metal
    # machined replacement and torque test are advised for a service build.
    wheel=join(wheel,hex_prism(1.67,6.0,-8.85),cylinder(1.0,4.2,(3.05,wy,wz),(1,0,0)))
    parts['WHEEL']=check(wheel,'WHEEL')
    encx=-5.75
    # Official drawing No.1: 9.8 width, shaft +3.6/-5.0 housing, 4.4 thick.
    yz=[(-4.9,-5.),(-4.9,1.3),(-2.2,3.6),(2.2,3.6),(4.9,1.3),(4.9,-5.)]
    pts=[V(encx-2.2,wy+y,wz+z) for y,z in yz]
    enc_wire=cq.Wire.makePolygon(pts+[pts[0]])
    enc=cq.Solid.extrudeLinear(enc_wire,[],V(4.4,0,0))
    enc=enc.cut(cylinder(1.60,7,(encx-3.5,wy,wz),(1,0,0))).clean()
    rotor=cylinder(1.49,4.4,(encx-2.2,wy,wz),(1,0,0)).cut(hex_prism(1.73,7.,encx-3.5)).clean()
    hardware['ENCODER_EC10E_HOUSING']=check(enc,'ENCODER_HOUSING')
    hardware['ENCODER_EC10E_ROTOR']=check(rotor,'ENCODER_ROTOR')
    cb=17.5-7.0
    cradle=box(5.8,15.2,1.6,(encx,wy,cb-.8))
    for yy in (-2.5,0.,2.5):
        cradle=cradle.cut(cylinder(.625,4,(encx+2.,wy+yy,cb-3)))
    for yy in (-5.4,5.4):
        cradle=cradle.cut(box(2.35,1.95,4,(encx,wy+yy,cb-1.)))
    cradle=cradle.clean()
    bearing=cylinder(2.8,2.4,(4.3,wy,wz),(1,0,0)).cut(cylinder(1.175,4,(3.5,wy,wz),(1,0,0)))
    barrel=cylinder(2.6,6.,(-3.,38.5,17.5),(1,0,0)).cut(cylinder(1.175,8.,(-4.,38.5,17.5),(1,0,0)))
    carrier=join(cradle,bearing,barrel,
       beam((encx,31.,cb-.4),(-2.,32.5,12.0),1.45),
       beam((-2.,32.5,12.0),(-2.,38.5,17.5),1.45),
       beam((5.5,25.,16.4),(6.,32.9,15.5),1.25),
       beam((6.,32.9,15.5),(2.,33.,14.),1.25),
       beam((2.,33.,14.),(2.,38.5,17.5),1.25),
       beam((-2.,32.5,12.0),(2.,33.,14.),1.25),
       box(6.0,3.0,1.6,(8.0,25.,15.5)))
    carrier=carrier.cut(cylinder(1.175,10.,(-5.,38.5,17.5),(1,0,0)))
    carrier=carrier.cut(cylinder(1.175,17.,(-8.5,wy,wz),(1,0,0))).clean()
    parts['WHEEL_CARRIER']=check(carrier,'WHEEL_CARRIER')
    hardware['WHEEL_CARRIER_STEEL_PIN']=cylinder(1.,13.8,(-6.9,38.5,17.5),(1,0,0))
    for x in (-4.8,4.8):
        ear=cylinder(2.85,2.4,(x-1.2,38.5,17.5),(1,0,0))
        top_z=top(outer,x,40.)
        lug=box(2.4,4.0,top_z-17.0,(x,39.5,(top_z+17.)/2))
        ear=join(ear,lug).cut(cylinder(1.175,4,(x-2.,38.5,17.5),(1,0,0)))
        additions.append(check(ear,'WHEEL_CARRIER_FIXED_HINGE'))
    cuts.append(cylinder(1.175,82.,(-41.,38.5,17.5),(1,0,0)))
    # Fifth D2F: outside the wheel width and inside the main-switch tray.
    middle_x,middle_y,middle_base=7.25,25.,7.55
    sw=box(5.8,12.8,6.5,(middle_x,middle_y,middle_base+3.25))
    sw=join(sw,cylinder(1.,.62,(middle_x,middle_y,middle_base+6.48)))
    hardware['SWITCH_MIDDLE']=check(sw,'SWITCH_MIDDLE')
    mt=box(7.0,15.5,1.8,(middle_x,middle_y,middle_base-.9))
    mt=join(mt,beam((11.7,31.8,middle_base-.9),(26.,31.8,10.0),1.25).intersect(outer),
            box(7.0,1.25,2.6,(middle_x,32.1,middle_base+1.2)))
    additions.append(check(mt,'WHEEL_CLICK_SUSPENDED_TRAY'))
    click_angle=2.4
    point=[10.9,25.,14.7]
    aa=math.radians(click_angle)
    stopz=17.5+(point[1]-38.5)*math.sin(aa)+(point[2]-17.5)*math.cos(aa)-.02
    stop=join(box(.8,2.,1.2,(10.95,25.,stopz-.6)),
       beam((10.95,25.,stopz-.6),(10.95,31.5,11.),.55),
       beam((10.95,31.5,11.),(half_width(31.5,p)-.3,31.5,11.),.55).intersect(outer))
    additions.append(check(stop,'WHEEL_CLICK_HARD_STOP'))
    cuts.append(box(19.6,17.8,32.,(0,25.,17.)))
    meta['wheel']=dict(part='WHEEL',axis_origin=[0,wy,wz],axis=[1,0,0],
       axle_diameter_mm=2.,bearing_hole_mm=2.35,hex_af_mm=1.67,
       encoder_hex_af_min_mm=1.73,minimum_z_mm=wz-hh['wheel_diameter']/2,
       wheel_crown_z_mm=wz+hh['wheel_diameter']/2,
       encoder=dict(model='Alps EC10E1220505',mount_height_mm=7.0,body_width_mm=9.8,
         body_thickness_mm=4.4,above_axis_mm=3.6,three_terminal_pitch_mm=2.5,
         pcb_pin_hole_mm=1.1,designed_clearance_hole_mm=1.25,
         source='https://tech.alpsalpine.com/cms.media/product_catalog_ec_03_ec10e_en_a9ede251c7.pdf'),
       installation='Fit encoder to carrier and insert wheel hex drive into rotor; flex-free approach from +X before carrier installation. Fit carrier between fixed rear ears and slide 2 mm hinge pin along X. Solder/wire encoder pins only after measuring actual component.')
    cm=dict(part='WHEEL_CARRIER',kind='rotate',origin=carrier_pivot,axis=[1,0,0],
        end_deg=click_angle,moving_children=['WHEEL'],
        moving_hardware=['ENCODER_EC10E_HOUSING','ENCODER_EC10E_ROTOR'],
        switch='SWITCH_MIDDLE',actuation_point=[middle_x,25.,14.7],nominal_actuator_gap_mm=.03,
        hard_stop_reference=point,hard_stop_reference_z=stopz)
    meta['motions'].append(cm)

    # Four small adjustable M2 ears, tied directly to adjacent side skin.
    # There is deliberately no PCB-shaped plate and no invented donor holes.
    mounting=[]
    for yy in (43.,66.):
        for sign in (-1,1):
            xx=sign*(half_width(yy,p)-4.0)
            ear=box(7.6,6.3,2.5,(xx,yy,9.5))
            slot=join(cylinder(1.2,5,(xx,yy-.8,7)),cylinder(1.2,5,(xx,yy+.8,7)),box(2.4,1.6,5,(xx,yy,9.5)))
            ear=ear.cut(slot)
            arm=beam((xx,yy,9.5),(sign*(half_width(yy,p)-.3),yy,9.5),1.3).intersect(outer)
            additions.append(check(join(ear,arm),'PCB_LOCAL_M2_EAR'))
            mounting.append(dict(center=[xx,yy,9.5],slot_width_mm=2.4,slot_length_mm=4.0))
    meta['generic_electronics_mounts']=dict(ears=mounting,
        status='Four generic local slotted M2 attachment ears; board adaptor, sensor carrier, battery retention and charging PCB remain donor-specific and require measurement. No bottom plate supplied.')
    meta['hardware_reference']=dict(switch='Omron D2F pin-plunger envelope, conservative 12.8 x 5.8 x 6.5 mm',
       source='https://components.omron.com/sites/default/files/datasheet_pdf/B036-E1.pdf',
       pretravel_max_mm=.5,overtravel_min_mm=.25,
       important='The shell uses generic envelope positioning. Exact free position, operating point, terminals, PCB holes and retention must be calibrated to the purchased switch. Do not infer Fenrir PCB compatibility.')
    meta['hardware_limitations']=[
       'Original Fenrir Pro PCB, sensor lens, battery and charging circuit have not been measured or verified.',
       'Alps EC10E1220505 geometry and pin pattern use its public outline drawing, not formal supply specifications or a measured sample.',
       'Integral PLA 1.67 mm AF encoder hex drive needs a torsion/fit coupon; a machined metal drive shaft is advised if long-term durability is required.',
       'D2F envelopes have real seats and stops, but final electrical switch retention and preload require a measured switch and fastening strap/adaptor.',
       'No universal claim of safe switch overtravel: supplied gaps/stops are geometric starting values; shim contact height to actual PT/OP before use.'
    ]
    meta['installation']=[
       {'step':1,'parts':['BODY'],'action':'Inspect five pads and raised supports; no removable bottom plate is required.'},
       {'step':2,'parts':['SIDE_FRONT_KEY','SIDE_REAR_KEY'],'action':'Insert sliding keys from left exterior. Insert 1.5 mm capture pins downward through their tongues from open shell interior.'},
       {'step':3,'parts':['SWITCH_SIDE_FRONT','SWITCH_SIDE_REAR','SWITCH_LEFT','SWITCH_RIGHT'],'action':'Place switches into local suspended sockets from open top; install measured retention straps/adaptors and set preload before fitting main keys.'},
       {'step':4,'parts':['WHEEL','WHEEL_CARRIER','ENCODER_EC10E_HOUSING','WHEEL_CARRIER_STEEL_PIN'],'action':'Preassemble encoder and wheel on carrier outside body, insert hex shaft along X, place carrier between rear fixed ears and insert 2 mm hinge pin from the side access path.'},
       {'step':5,'parts':['LEFT_KEY','RIGHT_KEY'],'action':'Align moving barrels between fixed bearing ears; slide each 2 mm steel hinge pin along X. Retain pin ends with removable clips or collars.'},
       {'step':6,'parts':['BODY'],'action':'Fit measured electronic board/adaptors to four local M2 slots; keep sensor downward view unobstructed and set measured lens height. Electronics and adaptor are not included as verified donor parts.'},
       {'step':7,'parts':['BODY'],'action':'Affix five PTFE pads after confirming coplanarity; calibrate key stops and test return motion before powering.'}
    ]
    meta['open_bottom']='Only five foot disks and their own stems below Z=5 mm. All other load routes are raised; no continuous bottom skin, perimeter floor ring or grid is added.'
    # Later braces must never refill a previously defined pin/tool path.
    pin_paths=[cylinder(bore/2,82.,(-41.,h['origin'][1],h['origin'][2]),(1,0,0)) for h in meta['main_hinges']]
    pin_paths.append(cylinder(1.175,82.,(-41.,38.5,17.5),(1,0,0)))
    cuts.extend(bolt_paths)
    for k,shape in enumerate(additions):
        for path in pin_paths+bolt_paths:
            shape=shape.cut(path)
        additions[k]=check(shape.clean(),f'FIXED_SUPPORT_{k}')
    for name,shape in parts.items():check(shape,name)
    return dict(body_additions=additions,body_cuts=cuts,parts=parts,hardware=hardware,metadata=meta)

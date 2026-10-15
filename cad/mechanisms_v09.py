"""Original V0.9 PLA wheel cartridge, CERN-OHL-P-2.0; millimetres.

Exact candidate-F function: E3 upper routing and bearing reinforcement with
only the lower foot changed to 11 x 4.6 x 2, centred at (0,-26.8,9.5).
Foot spans D24.5..29.1, clearing guide front D29.4 during all 31 insertion poses.
Wheel axis Z=14.3; ear radius 3.0 vs bore 1.7 gives 1.3 mm radial ligament.
D dogleg C=(+-4.4,-25.5,16.9); all beams retain diameter 2.4 mm.
Runtime wheel.axis_z must be 14.3. Full-press cap gap >= 0.361862068 mm.
The complete wheel-group insertion, internal static pairs and continuous wheel
annulus have no intersection >0.01 mm3. Functional stop contact may be zero.
This is mechanical QA, not physical print, friction, fatigue or strength proof.
"""
import math
import cadquery as cq
from build_mouse import rounded_box, beam
from mechanisms_v08 import union, pose, cartridge, cyl

def wheel_parts(p):
    w=p['wheel'];y=-w['y'];z=w['axis_z'];width=w['width'];q=p['mechanism']
    points=[]
    for i in range(576):
        a=2*math.pi*i/576;r=w['diameter']/2-.2+.2*math.cos(24*a)
        points.append((r*math.cos(a),r*math.sin(a)))
    wheel=cq.Workplane('YZ').polyline(points).close().extrude(width).val().translate((-width/2,y,z))
    wheel=wheel.cut(cyl(q['wheel_bore_diameter']/2,20,(-10,y,z),(1,0,0)))
    axle=union([cyl(q['printed_axle_diameter']/2,14.4,(-7.2,y,z),(1,0,0)),cyl(1.9,1.4,(-8.6,y,z),(1,0,0))])
    axle=axle.cut(cyl(.85,4.1,(3.2,y,z),(1,0,0)))
    washer=cyl(1.9,1.2,(7.2,y,z),(1,0,0)).cut(cyl(1.1,2,(7,y,z),(1,0,0)))
    m=p['modules']['middle'];unit=cartridge(q)
    carrier=pose(unit['plunger'],m).cut(cq.Workplane('XY').box(100,100,50).val().translate((0,-35,48.5)))
    items=[carrier,rounded_box(11,4.6,2,1,(0,-26.8,9.5))]
    for sign in (-1,1):
        x=sign*4.4
        items += [beam((sign*2,-35,21.7),(sign*2,-28,21.7),2.4),beam((sign*2,-28,21.7),(x,-25.5,16.9),2.4),beam((x,-25.5,16.9),(x,-27.2,11),2.4),beam((x,-27.2,11),(x,y,z),2.4),beam((x,-27.2,11),(x,-26,9.5),2.4)]
        ear=cyl(3.0,2.8,(sign*3.3 if sign>0 else -6.1,y,z),(1,0,0))
        items.append(ear)
    carrier=union(items).cut(cyl(q['bearing_bore_diameter']/2,20,(-10,y,z),(1,0,0)))
    carrier=carrier.cut(cyl(.85,5,(0,-27.2,7))).cut(rounded_box(2.9,1.5,5,.2,(0,-24.9,10)))
    # Default leaf sits 0.05 mm clear of the continuous wheel envelope.
    # Printed detent engagement requires physical adjustment, not a rigid clash.
    leaf_y=y-w['diameter']/2-.6-.05
    leaf=rounded_box(6,5,1.6,.6,(0,-26.5,7.7)).cut(cyl(1.1,4,(0,-27.2,6)))
    leaf=leaf.fuse(rounded_box(2.4,.8,z-.4-7.7,.2,(0,leaf_y,(z-.4+7.7)/2)))
    leaf=leaf.fuse(beam((0,leaf_y,z-.6),(0,leaf_y,z),1.2))
    return dict(wheel=wheel,axle=axle,axle_washer=washer,wheel_carrier=carrier,detent_leaf=leaf)

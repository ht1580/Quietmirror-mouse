"""V0.9 smooth mother surface and triangular PLA skeleton, original geometry.

All lengths are millimetres. D=-Y runs from the front (0) to the rear (90).
No commercial CAD is incorporated. CERN-OHL-P-2.0.
"""
import math
import numpy as np
import cadquery as cq
from cadquery.occ_impl.shapes import extrude
from scipy.interpolate import PchipInterpolator, CubicHermiteSpline, PPoly
from scipy.spatial import Delaunay
from shapely.geometry import Polygon, Point, box
from shapely import affinity
from shapely.ops import triangulate
from build_mouse import rounded_box
from build_v03 import arch, bounds

V=cq.Vector
FEET=((-21.,-8.),(21.,-8.),(-21.5,-61.5),(21.5,-61.5),(0.,-81.5))


def _profiles(p):
    """Preserve anterior widths; narrow the rear using the original 62 mm scale."""
    scale_d=float(p['length'])/90.
    ds=np.array([0,2,8,18,30,44,54,64,72,83,86,88,89.5,90],float)*scale_d
    ws=np.array([26.3,27.0,27.35,27.4,27.15,27.2,28.9,31.,28.8,18.,14.5,10.7,5.5,.6],float)
    ws*=float(p['max_width'])/62.
    wf=PchipInterpolator(ds,ws)
    # Preserve the original anterior width curve and its D54 tangent.  Only
    # the rear shoulder/tail narrows; never normalise this new maximum back
    # to 62 mm, which would silently enlarge the finger/primary-key region.
    split=int(np.flatnonzero(np.isclose(ds,54.*scale_d))[0])
    rd=np.array([54,64,72,83,86,88,89.5,90],float)*scale_d
    rw=np.array([28.9,28.9,25.8,16.1,13.,9.8,5.3,.6],float)*float(p['max_width'])/62.
    rw[0]=float(wf(rd[0]))
    rear_slopes=PchipInterpolator(rd,rw).derivative()(rd)
    rear_slopes[0]=float(wf.derivative()(rd[0]))
    rear_slopes[1]=-.18*float(p['max_width'])/62./scale_d
    rear=CubicHermiteSpline(rd,rw,rear_slopes)
    wf=PPoly(np.concatenate((wf.c[:,:split],rear.c),axis=1),
             np.concatenate((ds[:split+1],rd[1:])))
    # Quintic front segment: match height, slope and second derivative at D44.
    # Rear is one monotone Hermite segment, with no intermediate curvature knots.
    h=float(p['height']);tail=2.5*h/26.;front=14.2*h/26.
    rear_a=-8.2*h/26.;rear_b=-15.3*h/26.
    rear_second=2*rear_b/(46.*scale_d)**2
    c0=front;c1=.36*h/26.*44.;c2=0.
    rhs=np.array([h-c0-c1-c2,-c1-2*c2,rear_second*(44.*scale_d)**2-2*c2])
    c3,c4,c5=np.linalg.solve(np.array([[1,1,1],[3,4,5],[6,12,20]],float),rhs)
    def height(d,derivative=0):
        d=float(d)
        if d<=44.*scale_d:
            t=d/(44.*scale_d)
            if derivative==0:return c0+c1*t+c2*t*t+c3*t**3+c4*t**4+c5*t**5
            return (c1+2*c2*t+3*c3*t*t+4*c4*t**3+5*c5*t**4)/(44.*scale_d)
        t=(d-44.*scale_d)/(46.*scale_d)
        if derivative==0:return h+rear_b*t*t+rear_a*t**3
        return (2*rear_b*t+3*rear_a*t*t)/(46.*scale_d)
    return ds,wf,height


def make_surfaces(p):
    """A shared crown for body and flush keys, with an open-front inner loft.

    The nested loft is a slope-corrected approximate normal offset. Its actual
    wall thickness must still be checked on the exported geometry.
    """
    ds,wf,hf=_profiles(p);n=float(p.get('side_profile_power',4.));length=float(p['length'])
    stations=sorted(set(list(ds)+list(np.linspace(0,length,37))))
    outer=cq.Solid.makeLoft([arch(d,float(wf(d)),hf(d),n) for d in stations],ruled=False)
    # A fixed 1.0 scale keeps D<54 dimensions.  The previous B-rep correction
    # was below 0.05 mm; rescaling to the new rear maximum is prohibited.
    xf=1.0
    floor=float(p.get('shell_floor_z',1.))
    clip=cq.Workplane('XY').box(200,300,100).val().translate((0,-60,50+floor))
    outer=outer.intersect(clip)
    wires=[];wall=float(p['wall']);rear=float(p.get('rear_cavity_end',84.))*length/90.
    for d in np.linspace(-3.,rear,43):
        sd=max(0.,d);w=float(wf(sd))*xf;h=hf(sd)
        dw=float(wf.derivative()(sd))*xf if d>=0 else 0.
        dh=hf(sd,1) if d>=0 else 0.
        points=[]
        for angle in np.linspace(0,math.pi,41):
            co=math.cos(angle);x=w*math.copysign(abs(co)**(2/n),co);z=h*max(0.,math.sin(angle))**(2/n)
            nx=math.copysign(abs(x)**(n-1)/w**n,x);nz=z**(n-1)/h**n
            normal=math.hypot(nx,nz);nx/=normal;nz/=normal
            longitudinal=nx*x/w*dw+nz*z/h*dh
            offset=(wall+.08)*math.sqrt(1+longitudinal**2)
            points.append(V(x-offset*nx,-d,z-offset*nz))
        bl=V(points[-1].x,-d,-5);br=V(points[0].x,-d,-5)
        edges=[cq.Edge.makeSpline(points),cq.Edge.makeLine(points[-1],bl),cq.Edge.makeLine(bl,br),cq.Edge.makeLine(br,points[0])]
        wires.append(cq.Wire.assembleEdges(edges))
    inner=cq.Solid.makeLoft(wires,ruled=False)
    assert outer.isValid() and inner.isValid(),'invalid surface loft'
    return outer,inner


def _outline(outer,p):
    section=cq.Workplane(obj=outer).section(float(p.get('shell_floor_z',1.))+.001).val()
    wire=max(section.Wires(),key=lambda w:w.Length())
    coords=[wire.positionAt(float(t)).toTuple()[:2] for t in np.linspace(0,1,max(80,math.ceil(wire.Length()/.18)+1))]
    contour=affinity.scale(Polygon(coords),1,-1,origin=(0,0)).buffer(0).simplify(.015,preserve_topology=True)
    half=contour.intersection(box(0,-5,100,100))
    return half.union(affinity.scale(half,-1,1,origin=(0,0))).buffer(0)


def _prism(poly,z,height):
    wire=cq.Workplane('XY').polyline([(x,-d) for x,d in list(poly.exterior.coords)[:-1]]).close().val()
    return cq.Solid.extrudeLinear(wire,[],V(0,0,height)).translate((0,0,z))


def _triangle_layout(domain,p,prefix,pitch=13.):
    """Inset complete Delaunay triangles; never crop an aperture into a polygon."""
    web=float(p['ventilation']['minimum_planar_web']);radius=.55
    dy=pitch*math.sqrt(3)/2
    points=[]
    for row in range(-1,11):
        d=row*dy+1.5
        points.append((0.,d))
        for col in range(1,6):points.append(((col-(.5 if row%2 else 0))*pitch,d))
    points=np.array(sorted(set(points)),float);tri=Delaunay(points)
    layout=[];adapted_cells=0
    for simplex in tri.simplices:
        cell=Polygon(points[simplex]).convex_hull
        if cell.area<10:continue
        if domain.covers(cell):
            candidates=[cell]
        elif cell.bounds[1]>=54.*float(p['length'])/90.:
            # Fit rear boundary cells to the safe region, then triangulate the
            # resulting polygons.  Every aperture is still a complete triangle;
            # the clipped quadrilateral/pentagon itself is NEVER used as a hole.
            clipped=cell.intersection(domain)
            regions=[clipped] if clipped.geom_type=='Polygon' else list(getattr(clipped,'geoms',[]))
            candidates=[]
            for region in regions:
                if region.geom_type!='Polygon' or region.area<8:continue
                simple=region.simplify(.10,preserve_topology=True)
                for triangle in triangulate(simple):
                    if triangle.area>8 and region.covers(triangle) and domain.covers(triangle):
                        candidates.append(triangle)
            adapted_cells+=int(bool(candidates))
        else:
            # The already-reviewed anterior grip/key region is not reworked.
            continue
        for triangle in candidates:
            # Local rear-shoulder reinforcement: normal wall rays showed the
            # vertical aperture wall truncating the sloping shell here.  Keep
            # the triangular aperture, but retreat these mirrored outer holes
            # an additional 0.50 mm rather than weakening the wall criterion.
            extra=.50 if prefix=='R' and cell.centroid.x>15. and 66.<cell.centroid.y<78. else 0.
            # The last lateral tail pair crosses the steep solid tail root.
            # Identify its complete pre-fillet triangle rather than every cell
            # beyond D80, so the small central tail apertures remain unchanged.
            nominal_sharp=triangle.buffer(-web/2,join_style='mitre')
            if (prefix=='R' and not nominal_sharp.is_empty and
                    4.<nominal_sharp.centroid.x<7. and
                    83.<nominal_sharp.centroid.y<86.):
                extra=.35
            sharp=triangle.buffer(-(web/2+extra),join_style='mitre')
            rear_cell=cell.bounds[1]>=54.*float(p['length'])/90.
            if sharp.is_empty or sharp.geom_type!='Polygon' or sharp.area<(8 if rear_cell else 12):continue
            vertices=list(sharp.exterior.coords)[:-1]
            if len(vertices)!=3:continue
            rounded=sharp.buffer(-radius,join_style='round',quad_segs=6).buffer(radius,join_style='round',quad_segs=6).simplify(.003,preserve_topology=True)
            if rounded.is_empty or rounded.geom_type!='Polygon' or rounded.area<(6 if rear_cell else 10):continue
            layout.append((sharp,rounded,extra))
            layout.append((affinity.scale(sharp,-1,1,origin=(0,0)),affinity.scale(rounded,-1,1,origin=(0,0)),extra))
    layout.sort(key=lambda pair:(pair[0].centroid.y,pair[0].centroid.x))
    holes=[]
    for i,(sharp,rounded,extra) in enumerate(layout):
        xyz=[list(x) for x in list(sharp.exterior.coords)[:-1]]
        holes.append(dict(id=f'{prefix}{i+1:02}',zone='roof' if prefix=='R' else 'base',kind='rounded_triangle',triangle_xd_mm=xyz,vertices_xd_mm=xyz,rounded_xd_mm=[list(x) for x in list(rounded.exterior.coords)[:-1]],corner_radius_mm=radius,area_mm2=float(rounded.area),local_extra_inset_mm=extra,local_reinforcement=('Steep lateral tail: mirrored complete triangles retreat by 0.35 mm' if extra==.35 else 'Sloping rear shoulder: mirrored complete triangles retreat by 0.50 mm') if extra else None))
    gaps=[a[1].distance(b[1]) for i,a in enumerate(layout) for b in layout[i+1:]]
    report=dict(holes=holes,minimum_planar_web_mm=min(gaps) if gaps else None,target_planar_web_mm=web,method='Anterior complete triangles retained. At D>=54 rear grid cells are fit to the safe boundary and each resulting polygon is triangulated; only complete contained triangles are inset by half the web and corner-rounded. Clipped polygons are never aperture profiles.',pitch_mm=pitch,boundary_adaptation_from_d_mm=54.*float(p['length'])/90.,boundary_adapted_half_cells=adapted_cells)
    return [q[1] for q in layout],report


def roof_vents(p,outer):
    """Triangular roof holes with uninterrupted thumb-guide and wheel roots."""
    outline=_outline(outer,p);q=p['ventilation'];web=float(q['minimum_planar_web'])
    domain=outline.buffer(-(float(q['perimeter_web'])-web/2)).intersection(box(-80,31,80,87))
    # The wheel carrier, middle guide and rear shoulders need a continuous root.
    domain=domain.difference(box(-11.5,26.,11.5,43.6))
    domain=domain.difference(box(19.,29.,60.,60.)).difference(box(-60.,29.,-19.,60.))
    domain=domain.difference(box(8.,29.,60.,56.)).difference(box(-60.,29.,-8.,56.))
    # Preserve main guide stop/installation shoulders behind each short cap.
    for sign in (-1,1):domain=domain.difference(box(sign*14.5-5.5,25.,sign*14.5+5.5,31.))
    holes,report=_triangle_layout(domain,p,'R',pitch=12.6)
    report.update(version='0.9',surface='roof',outer_contour_xd_mm=[list(x) for x in outline.exterior.coords],functional_exceptions=['wheel/carrier installation','main-key movement and installation','side-key apertures','USB connector'])
    cutters=[]
    roof=max((face for face in outer.Faces() if face.geomType()=='BSPLINE'),key=lambda face:face.Area())
    for poly,hole in zip(holes,report['holes']):
        vertical=_prism(poly,2.65,45.)
        if hole.get('local_extra_inset_mm')==.35:
            # Follow part of the steep tail slope inside the skin, preserving
            # the actual curved exterior triangle. Limit every depth to the
            # original plan footprint so no neighbouring rib/foot is undercut.
            patch=roof.intersect(vertical)
            tool=extrude(patch,(0.,6.,-15.)).intersect(vertical).clean()
            assert tool.isValid() and len(tool.Solids())==1,'tail roof cutter'
            hole['interior_cut_vector_xyz_mm']=[0.,6.,-15.]
            hole['interior_cut_limit']='Original vertical triangle, Z>=2.65; outer curved triangular aperture retained.'
            cutters.append(tool)
        else:
            cutters.append(vertical)
    return cutters,report


def build_base(p,outer):
    """Rebuilt thin triangular floor, five retained skate datums and service ports."""
    outline=_outline(outer,p);q=p['ventilation'];web=float(q['minimum_planar_web'])
    perimeter=float(q['perimeter_web']);domain=outline.buffer(-(perimeter-web/2))
    # Pad and function reserves stay solid; only full triangles clear of them cut.
    for x,y in FEET:domain=domain.difference(Point(x,-y).buffer(4.7,quad_segs=16))
    sensor=p['sensor'];sd=float(sensor['y']);ow=float(sensor['opening_width']);ol=float(sensor['opening_length'])
    domain=domain.difference(box(-ow/2-2.,sd-ol/2-2.,ow/2+2.,sd+ol/2+2.))
    sw=p['power_switch'];switch_d=float(sw['d'])
    domain=domain.difference(box(-6.5,switch_d-4.5,6.5,switch_d+4.5))
    holes,report=_triangle_layout(domain,p,'B',pitch=12.6)
    # Deliberate 0.25 mm lateral overlap and Z1.1 start avoid coincident skin-floor edges.
    base=_prism(outline.buffer(-.25,join_style='round'),1.1,1.6)
    for poly in holes:base=base.cut(_prism(poly,.5,3.5),tol=1e-5)
    for x,y in FEET:
        pad=cq.Workplane('XY').center(x,y).circle(float(p['foot_diameter'])/2).extrude(float(p['foot_thickness'])).edges('>Z').fillet(.35).val()
        base=base.fuse(pad)
    sensor_ring=rounded_box(ow+4.,ol+4.,1.9,3.,(0,-sd,3.25)).cut(rounded_box(ow,ol,12.,2.,(0,-sd,3.)))
    base=base.fuse(sensor_ring)
    switch_bridge=rounded_box(12.,8.,2.,1.5,(0,-switch_d,2.8))
    base=base.fuse(switch_bridge)
    # These rectangular/rounded service apertures are functional, not lightening.
    base=base.cut(rounded_box(ow,ol,12.,2.,(0,-sd,3.)))
    base=base.cut(rounded_box(float(sw['opening_x']),float(sw['opening_d']),12.,.6,(0,-switch_d,3.)))
    base=base.clean()
    assert base.isValid() and len(base.Solids())==1,('base',len(base.Solids()))
    report.update(version='0.9',surface='base',plate_z_mm=[1.1,2.7],plate_outline_inset_mm=.25,bottom_overlap='Plate starts 0.1 mm above the shell floor and its outline is inset 0.25 mm, creating volumetric skirt overlap instead of coincident bottom/side edges.',feet=[dict(center_xy_mm=[x,y],diameter_mm=float(p['foot_diameter']),thickness_mm=float(p['foot_thickness']),bottom_z_mm=0.) for x,y in FEET],functional_openings=[dict(name='sensor',center_xd_mm=[0,sd],size_xd_mm=[ow,ol],corner_radius_mm=2.),dict(name='power_switch',center_xd_mm=[0,switch_d],size_xd_mm=[float(sw['opening_x']),float(sw['opening_d'])],corner_radius_mm=.6)],outer_contour_xd_mm=[list(x) for x in outline.exterior.coords],minimum_perimeter_web_mm=perimeter,note='New base; no frozen V0.6 lower geometry. Contact feet and optical/service positions retained; planar load paths deliberately rebuilt.')
    return base,report

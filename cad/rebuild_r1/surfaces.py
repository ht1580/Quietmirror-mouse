"""Independent Fenrir Pro reference reconstruction, mm; +Y points rearward.

The manufacturer supplied no reusable CAD.  These curves are an original
parameterisation informed by its public multi-view pictures and nominal size.
They are not a scan, factory tooling data, or a verified PCB replacement.
"""
from __future__ import annotations

import math

import cadquery as cq
import numpy as np
from scipy.interpolate import PchipInterpolator, make_interp_spline
from OCP.Geom import Geom_BSplineSurface
from OCP.gp import gp_Pnt
from OCP.TColgp import TColgp_Array2OfPnt
from OCP.TColStd import TColStd_Array1OfReal, TColStd_Array1OfInteger
from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace

V = cq.Vector
NOMINAL_LENGTH = 81.7
NOMINAL_WIDTH = 61.2
NOMINAL_HEIGHT = 28.3
FLOOR = 5.0
PROFILE_POWER = 3.4

# Rounded, short, broad outline with the widest region at the rear crown.
# The ends are deliberately finite instead of zero-width degenerate sections.
WIDTH_Y = (0., .5, 1.5, 3., 6., 10., 18., 30., 42., 53., 58.,
           63., 70., 74., 77., 79., 80.5, 81.7)
WIDTH_W = (.9, 10., 17., 21., 24.4, 26.1, 27.6, 28.3, 29.2,
           30.45, 30.6, 29.8, 28.3, 26., 22., 18.2, 12., .9)
HEIGHT_Y = (0., 6., 10., 15., 20., 25., 30., 35., 40., 45.,
            50., 55., 60., 65., 68., 70., 72., 74., 75., 76.,
            78., 80., 81.7)
HEIGHT_Z = (9.8, 12.7, 14.4, 16.3, 18.2, 20.23, 22.81, 24.39,
            25.8, 26.88, 27.8, 28.3, 27.55, 25.47, 23.31, 21.31,
            18.31, 13.32, 9.0, 7.4, 6.8, 6.8, 6.8)

_WIDTH = PchipInterpolator(WIDTH_Y, WIDTH_W)
_HEIGHT = PchipInterpolator(HEIGHT_Y, HEIGHT_Z)


def _dimensions(p=None):
    q = (p or {}).get('host', {})
    scale = float(q.get('scale', 1.0))
    return (float(q.get('length', NOMINAL_LENGTH)) * scale,
            float(q.get('width', NOMINAL_WIDTH)) * scale,
            float(q.get('height', NOMINAL_HEIGHT)) * scale)


def half_width(y, p=None):
    """Reference maximum half-width of the transverse cross-section."""
    length, width, _ = _dimensions(p)
    yy = min(NOMINAL_LENGTH, max(0., float(y) * NOMINAL_LENGTH / length))
    return float(_WIDTH(yy)) * width / NOMINAL_WIDTH


def roof_height(y, p=None):
    """Reference crown height on X=0; off-centre roof is lower."""
    length, _, height = _dimensions(p)
    yy = min(NOMINAL_LENGTH, max(0., float(y) * NOMINAL_LENGTH / length))
    return float(_HEIGHT(yy)) * height / NOMINAL_HEIGHT


def roof_z(x, y, p=None):
    """Cross-section approximation, useful for choosing initial mechanisms."""
    width = half_width(y, p)
    h = roof_height(y, p)
    _, _, height = _dimensions(p)
    floor = FLOOR * height / NOMINAL_HEIGHT
    xx = min(1., max(0., abs(float(x)) / width))
    return floor + (h-floor) * max(0., 1.-xx**PROFILE_POWER)**(1./PROFILE_POWER)


def _outer_wire(y, w, h, floor):
    points = []
    for a in np.linspace(0., math.pi, 49):
        c, s = math.cos(a), max(0., math.sin(a))
        x = w * math.copysign(abs(c)**(2./PROFILE_POWER), c)
        z = floor + (h-floor) * s**(2./PROFILE_POWER)
        points.append(V(x, y, z))
    points[0], points[-1] = V(w, y, floor), V(-w, y, floor)
    return cq.Wire.assembleEdges([
        cq.Edge.makeSpline(points, parameters=list(np.linspace(0., 1., len(points)))),
        cq.Edge.makeLine(points[-1], points[0])])


def _inner_wire(y, w, h, floor):
    # Its straight lower boundary extends well below the foot contact plane.
    points = []
    for a in np.linspace(0., math.pi, 49):
        c, s = math.cos(a), max(0., math.sin(a))
        x = w * math.copysign(abs(c)**(2./PROFILE_POWER), c)
        z = floor + (h-floor) * s**(2./PROFILE_POWER)
        points.append(V(x, y, z))
    points[0], points[-1] = V(w, y, floor), V(-w, y, floor)
    lower_left, lower_right = V(-w, y, -8.), V(w, y, -8.)
    return cq.Wire.assembleEdges([
        cq.Edge.makeSpline(points, parameters=list(np.linspace(0., 1., len(points)))),
        cq.Edge.makeLine(points[-1], lower_left),
        cq.Edge.makeLine(lower_left, lower_right), cq.Edge.makeLine(lower_right, points[0])])


def _bounds(shape):
    b = shape.BoundingBox()
    return dict(xmin=b.xmin, xmax=b.xmax, ymin=b.ymin, ymax=b.ymax,
                zmin=b.zmin, zmax=b.zmax,
                width=b.xlen, length=b.ylen, height=b.zlen)


def _array(values, cls):
    result = cls(1, len(values))
    for i, value in enumerate(values, 1):
        result.SetValue(i, value)
    return result


def _knots(full_knots):
    unique, counts = np.unique(full_knots, return_counts=True)
    return (_array([float(x) for x in unique], TColStd_Array1OfReal),
            _array([int(x) for x in counts], TColStd_Array1OfInteger))


def _hermite_bezier(fn, stations):
    """Exact cubic Bezier control values for a C1 PCHIP function."""
    out = []
    der = fn.derivative()
    for a, b in zip(stations[:-1], stations[1:]):
        d = b-a
        segment = [float(fn(a)), float(fn(a))+float(der(a))*d/3.,
                   float(fn(b))-float(der(b))*d/3., float(fn(b))]
        out.extend(segment if not out else segment[1:])
    return np.asarray(out)


def _tensor_solid(stations, widths, heights, floor, lower):
    """Explicit cubic tensor product; no loft parameter matching or sag."""
    wf = PchipInterpolator(stations, widths)
    hf = PchipInterpolator(stations, heights)
    cw, ch = _hermite_bezier(wf, stations), _hermite_bezier(hf, stations)
    cy = []
    for a,b in zip(stations[:-1], stations[1:]):
        segment = [a, a+(b-a)/3., a+2.*(b-a)/3., b]
        cy.extend(segment if not cy else segment[1:])
    u = np.linspace(0., 1., 49)
    angles = np.pi*u
    ux = make_interp_spline(u, np.sign(np.cos(angles))*abs(np.cos(angles))**(2./PROFILE_POWER), k=3)
    uz = make_interp_spline(u, np.sin(angles)**(2./PROFILE_POWER), k=3)
    poles = TColgp_Array2OfPnt(1, len(ux.c), 1, len(cw))
    for i in range(len(ux.c)):
        for j in range(len(cw)):
            poles.SetValue(i+1,j+1,gp_Pnt(float(ux.c[i]*cw[j]),float(cy[j]),
                                        float(floor+uz.c[i]*(ch[j]-floor))))
    uk, um = _knots(ux.t)
    vk = _array([float(x) for x in stations], TColStd_Array1OfReal)
    vm = _array([4]+[3]*(len(stations)-2)+[4], TColStd_Array1OfInteger)
    surface = Geom_BSplineSurface(poles,uk,vk,um,vm,3,3,False,False)
    roof = cq.Face(BRepBuilderAPI_MakeFace(surface,1e-7).Face())
    spanning, ends = [], []
    for edge in roof.Edges():
        a,b = edge.startPoint(),edge.endPoint()
        (spanning if abs(a.y-b.y) > .9*(stations[-1]-stations[0]) else ends).append(edge)
    if len(spanning)!=2 or len(ends)!=2:
        raise ValueError('Unexpected tensor surface boundary')
    roof_front = min(ends,key=lambda e:e.Center().y)
    roof_rear = max(ends,key=lambda e:e.Center().y)
    faces = [roof]
    bottom_edges=[]
    dz=lower-floor
    for edge in spanning:
        bottom_edge=edge.translate((0,0,dz)) if dz else edge
        bottom_edges.append(bottom_edge)
        if dz:
            faces.append(cq.Face.makeRuledSurface(edge,bottom_edge))
    for end in (roof_front,roof_rear):
        a,b=end.startPoint(),end.endPoint()
        aa,bb=V(a.x,a.y,lower),V(b.x,b.y,lower)
        line=cq.Edge.makeLine(bb,aa)
        bottom_edges.append(line)
        edges=[end,line]
        if dz:
            edges=[end,cq.Edge.makeLine(b,bb),line,cq.Edge.makeLine(aa,a)]
        faces.append(cq.Face.makeFromWires(cq.Wire.assembleEdges(edges)))
    faces.append(cq.Face.makeFromWires(cq.Wire.assembleEdges(bottom_edges)))
    shell=cq.Shell.makeShell(faces)
    solid=cq.Solid.makeSolid(shell)
    if not solid.isValid() or len(solid.Solids())!=1:
        raise ValueError('Tensor surface closure is not a valid single solid')
    return solid


def make_surfaces(p):
    """Return outer, inner and source/fit metadata; outer.cut(inner) is open.

    The slope-compensated inner loft targets 1.8 mm skin and keeps more
    material around steep end transitions. Actual thickness belongs in the
    final geometry validation, not an assertion based on nominal parameters.
    """
    length, width, height = _dimensions(p)
    q = p.get('host', {})
    skin = float(q.get('skin', 1.8))
    floor = float(q.get('base_open_band', FLOOR))
    sf_y, sf_x, sf_z = length/NOMINAL_LENGTH, width/NOMINAL_WIDTH, height/NOMINAL_HEIGHT
    stations=sorted(set([float(y)*sf_y for y in WIDTH_Y+HEIGHT_Y]))
    outer=_tensor_solid(stations,[half_width(y,p) for y in stations],
                        [roof_height(y,p) for y in stations],floor,floor)

    # Close the cavity only inside the nominal front/back thickness.  Since
    # outer starts above Z=0, this never creates a bottom plate at the feet.
    ys=sorted(set([skin,length-skin]+[y for y in stations if skin<y<length-skin]))
    inner_widths,inner_heights=[],[]
    for y in ys:
        t = y/sf_y
        dw = float(_WIDTH.derivative()(t))*sf_x/sf_y
        dh = float(_HEIGHT.derivative()(t))*sf_z/sf_y
        iw = max(.25, half_width(y, p)-skin*math.sqrt(1.+dw*dw))
        ih = max(floor-.8, roof_height(y, p)-skin*math.sqrt(1.+dh*dh))
        inner_widths.append(iw)
        inner_heights.append(ih)
    inner=_tensor_solid(ys,inner_widths,inner_heights,floor-1.8,-8.)
    if not (outer.isValid() and inner.isValid()):
        raise ValueError('Independent Fenrir reference loft is invalid')
    shell = outer.cut(inner).clean()
    if not shell.isValid() or len(shell.Solids()) != 1:
        raise ValueError('Independent reference skin must be one valid solid; '
                         f'valid={shell.isValid()}, solids={[(s.Volume(),_bounds(s)) for s in shell.Solids()]}')
    b = _bounds(outer)
    meta = dict(
        identification='G-Wolves Fenrir Pro 8K reference reconstruction',
        provenance='Original parameterised loft from public manufacturer photographs and nominal dimensions; no factory CAD or third-party scan used.',
        original_factory_cad=False,
        original_pcb_fit_verified=False,
        nominal_overall_mm=dict(length=length, width=width, height=height),
        outer_bounds_mm=b,
        dimension_error_mm=dict(length=b['length']-length, width=b['width']-width,
                                crown_height=b['zmax']-height),
        nominal_skin_mm=skin,
        open_below_z_mm=floor,
        inner_method='Slope-compensated transverse cavity; steep end roots retain extra material; final measured thickness required.',
        crown_station_yz_mm=[[float(y)*sf_y, float(z)*sf_z] for y,z in zip(HEIGHT_Y,HEIGHT_Z)],
        width_station_y_halfwidth_mm=[[float(y)*sf_y,float(w)*sf_x] for y,w in zip(WIDTH_Y,WIDTH_W)],
        reference_dimension_discrepancy='Current G-Wolves text width 61.2 mm; its uploaded EloShapes graphic says 60.2 mm. Text nominal dimensions used, image fit is qualitative.',
        reference_profile_adjustments='Centre crown moved to Y55 to follow the official side graphic. Wheel bump is not incorporated into the skin. At Y78..81.7 the tail is raised to Z6.8 so the Z5 open-bottom datum retains at least 1.8 mm of tail material; this differs from the original low tail by approximately 1.5..2.6 mm.',
        minimum_foot_plane_z_mm=0.,
        shell_one_solid=True,
        shell_volume_mm3=shell.Volume(),
    )
    return outer, inner, meta

"""Independent QA of saved V0.9 solids and meshes; units millimetres.

Runtime parameters are read from reports/v09/cad_metrics.json, including adapted
side-key X datums. No frozen-base/sensor equality is required after the V0.9
base rebuild. This does not replace a physical PLA fit/strength test.
"""
from pathlib import Path
import argparse, ctypes, hashlib, itertools, json, math, os, time, traceback
from concurrent.futures import ProcessPoolExecutor

for _key in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS',
             'NUMEXPR_NUM_THREADS', 'VTK_SMP_MAX_THREADS'):
    os.environ[_key] = '2'
os.environ['VTK_SMP_IMPLEMENTATION_TYPE'] = 'Sequential'
import cadquery as cq
import numpy as np
import pymeshlab
import trimesh
from scipy.spatial import cKDTree
from build_v03 import bounds
from validate_mouse import ray_distances

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'exports/v09'
RP = ROOT / 'reports/v09'
SOURCE_CACHE = ROOT.parent / '_support/work/v09_build'
CACHE = ROOT.parent / '_support/work/v09_validation'
EPS_VOLUME = .01
FEET = ((-21., -8.), (21., -8.), (-21.5, -61.5), (21.5, -61.5), (0., -81.5))
WHEEL_GROUP = ('WHEEL_CARRIER', 'WHEEL', 'AXLE', 'AXLE_WASHER', 'DETENT_LEAF')
_SHAPES = {}
_LOCALS = {}
_INDEX = None


def worker_init():
    if hasattr(ctypes, 'windll'):
        if not ctypes.windll.kernel32.SetPriorityClass(ctypes.c_void_p(-1), 0x4000):
            raise ctypes.WinError()


def saved_shape(name):
    if name not in _SHAPES:
        _SHAPES[name] = cq.importers.importStep(str(OUT/'placed'/f'{name}.step')).val()
    return _SHAPES[name]


def load_index():
    global _INDEX
    if _INDEX is None:
        _INDEX = json.loads((CACHE/'body_index.json').read_text(encoding='utf8'))
    return _INDEX


def local_body(name):
    item = load_index()['parts'][name]
    key = item['file']
    if key not in _LOCALS:
        _LOCALS[key] = (cq.Compound.makeCompound([]) if item['empty'] else
                        cq.importers.importStep(str(CACHE/key)).val())
    return _LOCALS[key]


def overlap(a, b):
    if not a.Solids() or not b.Solids():
        return 0.
    aa, bb = bounds(a), bounds(b)
    if any(min(aa[i+3], bb[i+3])-max(aa[i], bb[i]) < 1e-5 for i in range(3)):
        return 0.
    # Exact B-rep separation is sufficient to reject a disjoint pair. This
    # avoids pathological near-parallel offset-surface Boolean intersections.
    # Contact and containment have zero distance and still use solid common.
    if a.distance(b)>1e-5:return 0.
    return float(a.intersect(b).Volume(tol=1e-7))


def region_for(shapes, margin=1.5, motion=(0, 0, 0)):
    bbs = [bounds(s) for s in shapes]
    lo = np.min([b[:3] for b in bbs], axis=0)
    hi = np.max([b[3:] for b in bbs], axis=0)
    vec = np.asarray(motion)
    lo = np.minimum(lo, lo+vec)-margin
    hi = np.maximum(hi, hi+vec)+margin
    return cq.Workplane('XY').box(*[float(v) for v in hi-lo]).val().translate(tuple(float(v) for v in (lo+hi)/2))


def prepare_body_cache(metrics):
    """Clip once per mechanism group, retaining the whole sampled swept region."""
    global _INDEX
    CACHE.mkdir(parents=True, exist_ok=True)
    groups = {}
    for part in metrics['parts']:
        if part['name'] != 'BODY':
            groups.setdefault(part.get('module', part['name']), []).append(part['name'])
    files = [OUT/'placed'/f"{x['name']}.step" for x in metrics['parts']]
    fingerprint = hashlib.sha256((RP/'cad_metrics.json').read_bytes())
    for path in files:
        fingerprint.update(path.name.encode())
        fingerprint.update(str(path.stat().st_size).encode())
        fingerprint.update(str(path.stat().st_mtime_ns).encode())
    token = fingerprint.hexdigest()
    index_path = CACHE/'body_index.json'
    if index_path.exists():
        previous = json.loads(index_path.read_text(encoding='utf8'))
        if previous.get('fingerprint') == token and all(x['empty'] or (CACHE/x['file']).exists() for x in previous['parts'].values()):
            _INDEX = previous
            print('Reusing current local-body cache', flush=True)
            return
    index = {'fingerprint': token, 'parts': {}}
    for group, names in groups.items():
        clip = region_for([saved_shape(n) for n in names], margin=1.5)
        s = saved_shape('BODY').intersect(clip)
        filename = f'module_{group}.step'
        empty = not bool(s.Solids())
        if not empty:
            cq.exporters.export(s, str(CACHE/filename))
        for n in names:
            index['parts'][n] = {'file': filename, 'empty': empty, 'group': group}
        print('Cached body region', group, len(s.Solids()), flush=True)
    index_path.write_text(json.dumps(index, indent=2), encoding='utf8')
    _INDEX = index
    _LOCALS.clear()


def topology_check(metrics):
    rows = []
    for part in metrics['parts']:
        n = part['name']; s = saved_shape(n)
        mesh = trimesh.load_mesh(OUT/'placed'/f'{n}.stl')
        ms = pymeshlab.MeshSet()
        ms.load_new_mesh(str(OUT/'placed'/f'{n}.stl'))
        ms.compute_selection_by_self_intersections_per_face()
        row = dict(name=n, cad_valid=s.isValid(), solids=len(s.Solids()),
                   watertight=bool(mesh.is_watertight), winding_consistent=bool(mesh.is_winding_consistent),
                   components=len(mesh.split(only_watertight=False)),
                   self_intersecting_faces=int(ms.current_mesh().selected_face_number()),
                   dimensions_xyz_mm=mesh.extents.tolist(), volume_mm3=float(mesh.volume))
        row['pass_check'] = (row['cad_valid'] and row['solids'] == 1 and row['watertight']
                             and row['winding_consistent'] and row['components'] == 1
                             and row['self_intersecting_faces'] == 0)
        rows.append(row)
        print('Topology', n, row['pass_check'], row['self_intersecting_faces'], flush=True)
    return rows


def static_check(names):
    contacts = []
    for an, bn in itertools.combinations(names, 2):
        if an == 'BODY':
            v = overlap(local_body(bn), saved_shape(bn))
        elif bn == 'BODY':
            v = overlap(saved_shape(an), local_body(an))
        else:
            v = overlap(saved_shape(an), saved_shape(bn))
        if v > EPS_VOLUME:
            contacts.append(dict(a=an, b=bn, overlap_mm3=v))
            print('Static collision', contacts[-1], flush=True)
    return contacts


def travel_check(job):
    name, module, names, travel = job
    moving = ([name+'_KEY', name+'_RETAINER'] if name != 'middle' else
              list(WHEEL_GROUP)+['middle_RETAINER'])
    rows = []
    for distance in np.linspace(0, travel, 9):
        vec = (float(distance), 0, 0) if module.get('side') else (0, 0, -float(distance))
        hits = []
        for n in moving:
            moved = saved_shape(n).translate(vec)
            for fixed in names:
                if fixed in moving:
                    continue
                v = overlap(moved, local_body(n) if fixed == 'BODY' else saved_shape(fixed))
                if v > EPS_VOLUME:
                    hits.append(dict(a=n, b=fixed, overlap_mm3=v))
        rows.append(dict(module=name, travel_mm=float(distance), hits=hits))
    return rows


def wheel_check(p):
    wheel = p['wheel']; bore = p['mechanism']['wheel_bore_diameter']
    axis = ((0, -wheel['y'], wheel['axis_z']), (1, -wheel['y'], wheel['axis_z']))
    start = cq.Vector(-wheel['width']/2, -wheel['y'], wheel['axis_z'])
    direction = cq.Vector(1, 0, 0)
    swept = cq.Solid.makeCylinder(wheel['diameter']/2, wheel['width'], start, direction).cut(
        cq.Solid.makeCylinder(bore/2, wheel['width'], start, direction))
    fixed_names = ('BODY', 'WHEEL_CARRIER', 'AXLE', 'AXLE_WASHER', 'DETENT_LEAF')
    envelope_hits = []; rotations = []
    for n in fixed_names:
        v = overlap(swept, local_body('WHEEL') if n == 'BODY' else saved_shape(n))
        if v > EPS_VOLUME:
            envelope_hits.append(dict(a='WHEEL_CONTINUOUS_ENVELOPE', b=n, overlap_mm3=v))
    for angle in (0, 3.75, 7.5):
        moved = saved_shape('WHEEL').rotate(*axis, float(angle)); hits = []
        for n in fixed_names:
            v = overlap(moved, local_body('WHEEL') if n == 'BODY' else saved_shape(n))
            if v > EPS_VOLUME:
                hits.append(dict(a='WHEEL', b=n, overlap_mm3=v))
        rotations.append(dict(angle_degrees=float(angle), rigid_hits=hits,
                              detent_interference_mm3=overlap(moved, saved_shape('DETENT_LEAF'))))
    return dict(rotations=rotations, continuous_envelope=dict(outer_diameter_mm=wheel['diameter'],
                bore_diameter_mm=bore, width_mm=wheel['width'], rigid_hits=envelope_hits),
                pass_check=not envelope_hits and not any(r['rigid_hits'] for r in rotations))


def insertion_check(job):
    name, earlier = job
    moving = list(WHEEL_GROUP) if name == 'WHEEL_CARRIER' else [name]
    fixed = []
    for q in earlier:
        fixed.extend(WHEEL_GROUP if q == 'WHEEL_CARRIER' else [q])
    path_motion = (-30., 0, 0) if name.startswith('thumb') else (0, 0, 30.)
    body = saved_shape('BODY').intersect(region_for([saved_shape(n) for n in moving], margin=.1, motion=path_motion))
    rows = []
    for distance in np.linspace(0, 30, 31):
        vec = (-float(distance), 0, 0) if name.startswith('thumb') else (0, 0, float(distance))
        hits = []
        for n in moving:
            moved = saved_shape(n).translate(vec)
            for fn in ['BODY']+fixed:
                v = overlap(moved, body if fn == 'BODY' else saved_shape(fn))
                if v > EPS_VOLUME:
                    hits.append(dict(a=n, b=fn, overlap_mm3=v))
        rows.append(dict(distance_mm=float(distance), overlap_mm3=sum(h['overlap_mm3'] for h in hits), hits=hits))
    return dict(part=name, poses=rows, pass_check=not any(r['hits'] for r in rows))


def hardware_check(p, names):
    results = []
    for module in p['modules']:
        example = saved_shape(module+'_SWITCH_EXAMPLE'); hits = []
        reference = next(n for n in names if n.startswith(module+'_')) if module != 'middle' else 'WHEEL_CARRIER'
        for n in names:
            v = overlap(example, local_body(reference) if n == 'BODY' else saved_shape(n))
            if v > EPS_VOLUME:
                hits.append(dict(a=module+'_SWITCH_EXAMPLE', b=n, overlap_mm3=v))
        results.append(dict(module=module, rest_intersections=hits, pass_check=not hits))
    return results


def fit_clearances(p):
    front = []
    for n in ('left_KEY', 'right_KEY'):
        # D <= 2 mm; only the movable front tip, including its complete press.
        region = cq.Workplane('XY').box(80, 20, 60).val().translate((0, 8, 25))
        tip = saved_shape(n).intersect(region)
        gap = tip.translate((0, 0, -p['mechanism']['travel'])).distance(saved_shape('BODY'))
        front.append(dict(part=n, full_press_tip_to_body_mm=float(gap), tip_region='D <= 2 mm', pass_check=gap > .25))
    main_end = max(-bounds(saved_shape(n))[1] for n in ('left_KEY', 'right_KEY', 'left_RETAINER', 'right_RETAINER'))
    side_start = min(-bounds(saved_shape(n))[4] for n in ('thumb_front_KEY', 'thumb_front_RETAINER'))
    gap = side_start-main_end; required = 2*p['mechanism']['radial_clearance']
    return dict(front_key_clearance=front, main_to_front_side_longitudinal_gap_mm=float(gap),
                required_longitudinal_gap_mm=float(required),
                pass_check=all(r['pass_check'] for r in front) and gap > required)


def feet_check(p):
    mesh = trimesh.load_mesh(OUT/'placed/BODY.stl'); results = []
    bottom = np.unique(mesh.vertices[np.abs(mesh.vertices[:, 2]) < .0001, :2], axis=0)
    for x, y in FEET:
        points = [(x, y)]+[(x+3.7*math.cos(t), y+3.7*math.sin(t)) for t in np.linspace(0, 2*math.pi, 8, endpoint=False)]
        hits = ray_distances(mesh, [[a, b, -1] for a, b in points], [[0, 0, 1]]*9)
        zs = [h[0]-1 for h in hits if h]
        radial = np.linalg.norm(bottom-np.array([x, y]), axis=1)
        perimeter = bottom[np.abs(radial-p['foot_diameter']/2) < .3]
        center = None; radius = None; center_error = None
        if len(perimeter) >= 3:
            a = np.column_stack((2*perimeter, np.ones(len(perimeter))))
            cx, cy, constant = np.linalg.lstsq(a, np.sum(perimeter**2, axis=1), rcond=None)[0]
            radius = float(math.sqrt(max(0., constant+cx*cx+cy*cy)))
            center = [float(cx), float(cy)]; center_error = float(math.hypot(cx-x, cy-y))
        row = dict(expected_center_xy_mm=[x, y], fitted_bottom_circle_center_xy_mm=center,
                   fitted_bottom_circle_radius_mm=radius, center_error_mm=center_error,
                   samples=len(zs), min_z=min(zs) if zs else None, max_z=max(zs) if zs else None)
        row['pass_check'] = (len(zs) == 9 and all(abs(z) < .001 for z in zs)
                             and center_error is not None and center_error < .05
                             and abs(radius-p['foot_diameter']/2) < .05)
        results.append(row)
    return results


def sharp_edge_tree(mesh):
    edge_indices = mesh.face_adjacency_edges[mesh.face_adjacency_angles > math.radians(25)]
    samples = []
    for edge in edge_indices:
        a, b = mesh.vertices[edge]
        count = max(2, math.ceil(np.linalg.norm(b-a)/.35)+1)
        samples.extend(a+(b-a)*t for t in np.linspace(0, 1, count))
    return cKDTree(np.asarray(samples)) if samples else None


WALL_REGRESSION_TARGETS = (
    dict(name='old_front_side_rim_minimum', expectation='material_and_minimum_thickness',
         point_xyz_mm=[26.71860378288816, -23.288217828226152, 12.059918294308785],
         normal=[0.9792323595559981, 0.008826200616873298, 0.2025489673660754],
         baseline_cad_thickness_mm=0.32756107541843443),
    dict(name='front_thumb_roof_1', expectation='material_and_minimum_thickness',
         point_xyz_mm=[-11.617768012635077, -34.083209115784484, 24.980203658537103],
         normal=[-0.07219215485995797, 0.15329909793363566, 0.9855392835140615],
         baseline_cad_thickness_mm=1.204482358862816),
    dict(name='front_thumb_roof_2', expectation='material_and_minimum_thickness',
         point_xyz_mm=[-12.50669917502622, -34.36812265297024, 24.9573948301903],
         normal=[-0.10324388588846328, 0.16529434797492193, 0.9808254067642189],
         baseline_cad_thickness_mm=1.1810006213492263),
    dict(name='rear_vent_lip_p1_left', expectation='material_and_minimum_thickness',
         point_xyz_mm=[-20.827906876473797, -74.30182903562181, 14.010627624703414],
         normal=[-0.48157283088534114, -0.644433508964341, 0.5939638550256954],
         baseline_cad_thickness_mm=1.062724350633276),
    dict(name='rear_vent_lip_p1_right_mirror', expectation='material_and_minimum_thickness',
         point_xyz_mm=[20.827906876473797, -74.30182903562181, 14.010627624703414],
         normal=[0.48157283088534114, -0.644433508964341, 0.5939638550256954],
         baseline_cad_thickness_mm=1.062724350633276),
    dict(name='rear_vent_lip_p2_right', expectation='material_and_minimum_thickness',
         point_xyz_mm=[23.526111301596387, -69.96118628195156, 15.701927558785593],
         normal=[0.6115224913881798, -0.5334919466038694, 0.5843171959092149],
         baseline_cad_thickness_mm=1.1941444289635803),
    dict(name='rear_vent_lip_p2_left_mirror', expectation='material_and_minimum_thickness',
         point_xyz_mm=[-23.526111301596387, -69.96118628195156, 15.701927558785593],
         normal=[-0.6115224913881798, -0.5334919466038694, 0.5843171959092149],
         baseline_cad_thickness_mm=1.1941444289635803),
    dict(name='tail_vent_lip_right', expectation='material_and_minimum_thickness',
         point_xyz_mm=[6.6554406313532715, -86.82893581095676, 5.957829323616716],
         normal=[0.07217648434017256, -0.7474887694776492, 0.660341649915468],
         baseline_cad_thickness_mm=0.9772163671668669,
         baseline_mesh_thickness_mm=0.975182,
         baseline_raw_cad_thickness_mm=3.786623124498472),
    dict(name='tail_vent_lip_left_mirror', expectation='material_and_minimum_thickness',
         point_xyz_mm=[-6.6554406313532715, -86.82893581095676, 5.957829323616716],
         normal=[-0.07217648434017256, -0.7474887694776492, 0.660341649915468],
         baseline_cad_thickness_mm=0.9772163671668669,
         baseline_mesh_thickness_mm=0.975182,
         baseline_raw_cad_thickness_mm=3.786623124498472),
)


FRONT_DESIGN_CONTRACT = dict(
    moving_roof_method='Normal thickening of the exact outer mother-surface patch',
    moving_roof_nominal_mm=1.6,
    fixed_lower_skirt_restored=True,
    fixed_skirt_requirement='Material must remain at the old front-side regression point with exact normal-ray thickness >=1.2 mm.',
    v2_removed_material_expectation_obsolete=True,
    superseded_expectation='The V2 expectation that the old front-side rim be removed is superseded by the restored fixed-skirt front closure.',
)


WALL_REGRESSION_TARGETS += (
    dict(name='rear_thumb_floor_roof_left',
         expectation='material_and_minimum_thickness',
         point_xyz_mm=[-12.612594059051348, -47.0973697012639, 25.625996952102973],
         normal=[-.09553323166786874, -.03603474479602803, .9947737927863692],
         baseline_cad_thickness_mm=.739124,
         baseline_mesh_thickness_mm=.729811,
         baseline_raw_cad_thickness_mm=1.679946),
    dict(name='rear_thumb_floor_roof_right_mirror',
         expectation='material_and_minimum_thickness',
         point_xyz_mm=[12.612594059051348, -47.0973697012639, 25.625996952102973],
         normal=[.09553323166786874, -.03603474479602803, .9947737927863692],
         mirror_control_of='rear_thumb_floor_roof_left'),
    dict(name='rear_vent_adjacent_b_left',
         expectation='material_and_minimum_thickness',
         point_xyz_mm=[-20.741881393255998, -74.16344185498822, 14.23052126097057],
         normal=[-.48157283088534114, -.644433508964341, .5939638550256954],
         baseline_mesh_thickness_mm=1.197283),
    dict(name='rear_vent_adjacent_b_right_mirror',
         expectation='material_and_minimum_thickness',
         point_xyz_mm=[20.741881393255998, -74.16344185498822, 14.23052126097057],
         normal=[.48157283088534114, -.644433508964341, .5939638550256954],
         mirror_control_of='rear_vent_adjacent_b_left'),
)


WALL_REGRESSION_TARGETS += (
    dict(name='tail_vent_oblique_lip_right',
         expectation='material_and_minimum_thickness',
         point_xyz_mm=[4.579492094775015, -86.55309737181278, 6.381411515555374],
         normal=[.016533128584238627, -.7341149015591016, .6788239587463657],
         baseline_mesh_thickness_mm=1.093967),
    dict(name='tail_vent_oblique_lip_left_mirror',
         expectation='material_and_minimum_thickness',
         point_xyz_mm=[-4.579492094775015, -86.55309737181278, 6.381411515555374],
         normal=[-.016533128584238627, -.7341149015591016, .6788239587463657],
         mirror_control_of='tail_vent_oblique_lip_right'),
)


def targeted_wall_regression():
    """Fixed old failure coordinates: no resampling or threshold relaxation.

    Baseline coordinates/normals were read from the old wall.json and confirmed
    by work/v09_validation/wall_exact_cad_ray_confirmation.json. Roof probes
    and restored fixed-side-skirt probes must still hit the original exterior
    near the expected surface and retain >=1.2 mm along the same normal. The old
    V2 removed-material expectation no longer applies to the fixed side skirt.
    """
    body = saved_shape('BODY')
    rows = []
    for target in WALL_REGRESSION_TARGETS:
        row = dict(target)
        point = np.asarray(target['point_xyz_mm'], dtype=float)
        normal = np.asarray(target['normal'], dtype=float)
        normal /= np.linalg.norm(normal)
        if target['expectation'] == 'removed_material':
            probe = cq.Workplane('XY').box(1., 1., 1.).val().translate(tuple(float(v) for v in point))
            common = body.intersect(probe)
            empty = not common.Faces() and not common.Edges() and not common.Vertices()
            row.update(probe_size_xyz_mm=[1., 1., 1.],
                       probe_overlap_mm3=float(common.Volume(tol=1e-7)),
                       remaining_faces=len(common.Faces()), remaining_edges=len(common.Edges()),
                       remaining_vertices=len(common.Vertices()),
                       removed_material=bool(empty), pass_check=bool(empty))
        else:
            origin = point + normal*.2
            end = point - normal*4.
            ray = cq.Edge.makeLine(cq.Vector(*[float(v) for v in origin]),
                                   cq.Vector(*[float(v) for v in end]))
            common = body.intersect(ray)
            segments = []
            for edge in common.Edges():
                values = sorted(float(np.dot(np.asarray(vertex.toTuple())-origin, -normal))
                                for vertex in (edge.startPoint(), edge.endPoint()))
                segments.append(dict(start_mm=values[0], end_mm=values[1],
                                     thickness_mm=values[1]-values[0]))
            segments.sort(key=lambda item: item['start_mm'])
            exterior = [item for item in segments if -.05 <= item['start_mm'] <= .45]
            thickness = exterior[0]['thickness_mm'] if exterior else None
            row.update(exact_cad_ray_segments=segments, material_present=bool(exterior),
                       minimum_required_mm=1.2, thickness_mm=thickness,
                       pass_check=bool(exterior) and thickness >= 1.2)
        rows.append(row)
        print('Targeted wall', row['name'], row['pass_check'],
              row.get('thickness_mm', row.get('removed_material')), flush=True)
    return dict(targets=rows, pass_check=all(row['pass_check'] for row in rows),
                front_design_contract=FRONT_DESIGN_CONTRACT,
                baseline_source='_support/work/v09_validation/wall_exact_cad_ray_confirmation.json',
                method=f'All {len(WALL_REGRESSION_TARGETS)} fixed baseline coordinates and normals use exact saved-STEP line common; every roof, restored fixed-side-skirt, rear-vent and tail-vent target must contain material with thickness >=1.2 mm. The old V2 removal expectation is obsolete.')


def wall_check(p):
    """Normal-ray measurements away from exposed edges and functional cutouts.

    Candidates must match the independently saved mother surface and its outward
    normal. Sharp edges/vent/interface transitions within 1 mm are excluded.
    This is a finite sample, not a global medial-axis/minimum-wall proof.
    """
    outer = cq.importers.importStep(str(SOURCE_CACHE/'outer.step')).val()
    outer_path = CACHE/'outer_reference.stl'
    cq.exporters.export(outer, str(outer_path), tolerance=.025, angularTolerance=.08)
    reference = trimesh.load_mesh(outer_path)
    results = []; rng = np.random.default_rng(909)
    # Side caps are nominal 1.8 mm skins, offset 0.35 mm from the mother surface.
    targets = [('BODY', float(p['wall'])), ('left_KEY', float(p['wall'])),
               ('right_KEY', float(p['wall'])),
               ('thumb_front_KEY', float(p['fenrir_side']['skin_depth'])),
               ('thumb_rear_KEY', float(p['fenrir_side']['skin_depth']))]
    for name, nominal in targets:
        mesh = trimesh.load_mesh(OUT/'placed'/f'{name}.stl')
        count = 6000 if name == 'BODY' else 3500
        indices = rng.choice(len(mesh.faces), size=count, p=mesh.area_faces/mesh.area)
        triangles = mesh.triangles[indices]; uv = rng.random((count, 2))
        uv[uv.sum(axis=1) > 1] = 1-uv[uv.sum(axis=1) > 1]
        points = triangles[:, 0]+uv[:, :1]*(triangles[:, 1]-triangles[:, 0])+uv[:, 1:]*(triangles[:, 2]-triangles[:, 0])
        normals = mesh.face_normals[indices]
        reference_points = points.copy()
        if name.startswith('thumb'):
            reference_points[:, 0] += float(p['fenrir_side']['surface_protrusion'])
        _, distances, face_ids = reference.nearest.on_surface(reference_points)
        aligned = np.einsum('ij,ij->i', normals, reference.face_normals[face_ids]) > .96
        keep = (distances < .06) & aligned & (points[:, 2] > 4.)
        if name == 'BODY':
            keep &= points[:, 1] < -3.  # Exclude the USB nose and its functional rim.
        tree = sharp_edge_tree(mesh)
        if tree is not None:
            keep &= tree.query(points)[0] > 1.
        selected = np.flatnonzero(keep)
        if len(selected) > 400:
            selected = selected[np.linspace(0, len(selected)-1, 400).astype(int)]
        samples = []; missing = 0
        if len(selected):
            origins = points[selected]+normals[selected]*.05
            rays = ray_distances(mesh, origins, -normals[selected])
            for i, ts in zip(selected, rays):
                if len(ts) < 2 or ts[0] > .15:
                    missing += 1
                    continue
                samples.append(dict(point_xyz_mm=points[i].tolist(), normal=normals[i].tolist(), thickness_mm=float(ts[1]-ts[0])))
        values = [s['thickness_mm'] for s in samples]
        low = [s for s in samples if s['thickness_mm'] < 1.2]
        row = dict(part=name, nominal_mm=nominal, candidate_count=int(len(selected)),
                   measured_count=len(samples), missing_ray_count=missing,
                   minimum_mm=min(values) if values else None, maximum_mm=max(values) if values else None,
                   samples_below_1_2_mm=low, samples=samples,
                   pass_check=bool(samples) and not low)
        results.append(row)
        print('Wall', name, row['measured_count'], row['minimum_mm'], 'below 1.2:', len(low), flush=True)
    targeted = targeted_wall_regression()
    return dict(parts=results, targeted_regression=targeted,
                pass_check=all(r['pass_check'] for r in results) and targeted['pass_check'],
                method='Deterministic area samples on exported meshes; normal rays from matched mother-surface faces, >=1 mm from sharp vent/interface/part edges, Z > 4 mm. Main/body nominal 1.6 mm; side-cap nominal 1.8 mm. Functional structures and the lower base are excluded.',
                limits='Finite samples of ordinary skin only; this is not a continuous/global minimum-thickness guarantee. Thick samples can cross an integral support. Physical printing remains untested.')


def map_jobs(function, jobs, workers):
    if workers == 1:
        for job in jobs:
            yield function(job)
    else:
        with ProcessPoolExecutor(max_workers=2, initializer=worker_init) as pool:
            yield from pool.map(function, jobs)


def main():
    worker_init()
    parser = argparse.ArgumentParser()
    parser.add_argument('--phase', choices=('all', 'topology', 'static', 'motion', 'insertion', 'fit', 'feet', 'wall'), default='all')
    parser.add_argument('--workers', type=int, choices=(1, 2), default=1)
    args = parser.parse_args()
    CACHE.mkdir(parents=True, exist_ok=True)
    metrics = json.loads((RP/'cad_metrics.json').read_text(encoding='utf8'))
    p = metrics['parameters']  # Includes runtime adapt_side_origins; static JSON is insufficient.
    assert str(metrics['version']) == '0.9', 'Not V0.9 saved metrics'
    names = [part['name'] for part in metrics['parts']]
    report = dict(version='0.9', units='mm', phase=args.phase, parameter_source='reports/v09/cad_metrics.json.parameters',
                  front_design_contract=FRONT_DESIGN_CONTRACT,
                  runtime_module_origins={k: v['origin'] for k, v in p['modules'].items()},
                  overlap_failure_threshold_mm3=EPS_VOLUME, failures=[], errors=[], stages={},
                  method_limits='No physical print, force/friction/fatigue/elastic FEA. Five button strokes use 9 positions each, five installation paths 31 positions each. The wheel annulus conservatively covers every rotation; 3 explicit angles are additionally checked. PLA fit, switch travel and detent engagement require physical calibration. V0.9 lower base is intentionally rebuilt; no equality to historical base/sensor solids is asserted.')
    start = time.time()
    def stage(name, function):
        try:
            result = function(); report['stages'][name] = result
            (CACHE/f'{name}.json').write_text(json.dumps(result, indent=2), encoding='utf8')
            print('STAGE', name, 'saved', flush=True)
            return result
        except Exception as error:
            detail = dict(stage=name, error=repr(error), traceback=traceback.format_exc())
            report['errors'].append(detail)
            print('STAGE ERROR', name, repr(error), flush=True)
            return None
    selected = lambda phase: args.phase in ('all', phase)
    if any(selected(x) for x in ('static', 'motion', 'insertion', 'fit')):
        stage('local_body_cache', lambda: (prepare_body_cache(metrics) or {'ready': True}))
    if selected('topology'):
        rows = stage('topology', lambda: topology_check(metrics))
        if rows is not None: report['failures'] += [dict(stage='topology', **r) for r in rows if not r['pass_check']]
    if selected('static'):
        rows = stage('static_intersections', lambda: static_check(names))
        if rows is not None: report['failures'] += [dict(stage='static', **r) for r in rows]
    if selected('motion'):
        jobs = [(n, m, names, p['mechanism']['travel']) for n, m in p['modules'].items()]
        def paths():
            result = []
            for rows in map_jobs(travel_check, jobs, args.workers):
                result.extend(rows); print('Travel', rows[0]['module'], sum(bool(x['hits']) for x in rows), flush=True)
            return result
        rows = stage('sampled_button_paths', paths)
        if rows is not None: report['failures'] += [dict(stage='button_travel', module=r['module'], travel_mm=r['travel_mm'], **h) for r in rows for h in r['hits']]
        result = stage('wheel', lambda: wheel_check(p))
        if result is not None:
            report['failures'] += [dict(stage='wheel_envelope', **h) for h in result['continuous_envelope']['rigid_hits']]
            report['failures'] += [dict(stage='wheel_rotation', angle_degrees=r['angle_degrees'], **h) for r in result['rotations'] for h in r['rigid_hits']]
    if selected('insertion'):
        order = ('WHEEL_CARRIER', 'left_KEY', 'right_KEY', 'thumb_front_KEY', 'thumb_rear_KEY')
        def insertions():
            result = []
            for row in map_jobs(insertion_check, [(n, order[:i]) for i, n in enumerate(order)], args.workers):
                result.append(row); print('Insertion', row['part'], row['pass_check'], flush=True)
            return result
        rows = stage('insertion_paths', insertions)
        if rows is not None: report['failures'] += [dict(stage='insertion', group=r['part'], distance_mm=s['distance_mm'], **h) for r in rows for s in r['poses'] for h in s['hits']]
    if selected('fit'):
        rows = stage('switch_example_rest_fit', lambda: hardware_check(p, names))
        if rows is not None: report['failures'] += [dict(stage='switch_fit', module=r['module'], **h) for r in rows for h in r['rest_intersections']]
        result = stage('clearances', lambda: fit_clearances(p))
        if result is not None and not result['pass_check']: report['failures'].append(dict(stage='clearances', **result))
    if selected('feet'):
        rows = stage('feet', lambda: feet_check(p))
        if rows is not None: report['failures'] += [dict(stage='feet', **r) for r in rows if not r['pass_check']]
    if selected('wall'):
        result = stage('wall', lambda: wall_check(p))
        if result is not None:
            report['failures'] += [dict(stage='wall', part=r['part'], measured_count=r['measured_count'], minimum_mm=r['minimum_mm'], samples_below_1_2_mm=r['samples_below_1_2_mm']) for r in result['parts'] if not r['pass_check']]
            report['failures'] += [dict(stage='wall_targeted', **r) for r in result['targeted_regression']['targets'] if not r['pass_check']]
    # Keep the established report fields usable by release/package tools.
    stages = report['stages']
    if 'topology' in stages:
        report['topology'] = stages['topology']
        report['topology_pass'] = all(r['pass_check'] for r in stages['topology'])
    for key in ('static_intersections', 'sampled_button_paths', 'insertion_paths', 'switch_example_rest_fit', 'feet'):
        if key in stages:
            report[key] = stages[key]
    if 'wheel' in stages:
        report['wheel_rotations'] = stages['wheel']['rotations']
        report['wheel_continuous_envelope'] = stages['wheel']['continuous_envelope']
        if 'sampled_button_paths' in stages:
            report['rigid_motion_pass'] = stages['wheel']['pass_check'] and not any(r['hits'] for r in stages['sampled_button_paths'])
    if 'clearances' in stages:
        report.update({k: v for k, v in stages['clearances'].items() if k != 'pass_check'})
    if 'wall' in stages:
        report['wall_check'] = stages['wall']
    report['parameter_sha256'] = hashlib.sha256(json.dumps(p, sort_keys=True).encode()).hexdigest()
    report['artifact_inputs'] = [dict(name=n, step_size_bytes=(OUT/'placed'/f'{n}.step').stat().st_size,
                                     step_mtime_ns=(OUT/'placed'/f'{n}.step').stat().st_mtime_ns,
                                     stl_size_bytes=(OUT/'placed'/f'{n}.stl').stat().st_size,
                                     stl_mtime_ns=(OUT/'placed'/f'{n}.stl').stat().st_mtime_ns) for n in names]
    report['elapsed_seconds'] = time.time()-start
    report['pass_check'] = not report['failures'] and not report['errors']
    path = CACHE/f'validation_{args.phase}.json'
    path.write_text(json.dumps(report, indent=2), encoding='utf8')
    if args.phase == 'all':
        (RP/'validation.json').write_text(json.dumps(report, indent=2), encoding='utf8')
    summary = dict(pass_check=report['pass_check'], phase=args.phase, failures=len(report['failures']), errors=report['errors'], elapsed_seconds=report['elapsed_seconds'], report=str(path))
    print(json.dumps(summary, indent=2), flush=True)
    if not report['pass_check']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()

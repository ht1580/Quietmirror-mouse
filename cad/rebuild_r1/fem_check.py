"""Reproducible Gmsh / CalculiX solid FEM; units mm, N and MPa.

All bulky meshes, decks and raw results stay under the E-drive support folder.
The code runs actual ccx.exe jobs; analytic formulas are used only to validate
the independent beam benchmark. No commercial-product strength is inferred.
"""
from __future__ import annotations
import argparse
import ctypes
from dataclasses import dataclass
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import time

os.environ.setdefault('OMP_NUM_THREADS', '2')
os.environ.setdefault('OPENBLAS_NUM_THREADS', '2')
os.environ.setdefault('CCX_NPROC_RESULTS', '2')
os.environ.setdefault('NUMBER_OF_CPUS', '2')
import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components

ROOT = Path(__file__).resolve().parents[2]
SUPPORT = ROOT.parent / '_support'
WORK = SUPPORT/'work/fenrir_rebuild/fem'
TOOLS = SUPPORT/'tools/FreeCAD/bin'
GMSH = TOOLS/'gmsh.exe'
CCX = TOOLS/'ccx.exe'
REPORT = ROOT/'reports/rebuild_r1'
SOURCE_DOCS = {
    'gmsh': 'https://gmsh.info/doc/texinfo/gmsh.html',
    'calculix': 'https://www.dhondt.de/ccx_2.22.pdf',
    'calculix_node_print': 'https://feacluster.com/CalculiX/ccx_2.18/doc/ccx/node307.html',
}
POSTPROCESS_VERSION = 3


def low_priority():
    if os.name == 'nt':
        ctypes.windll.kernel32.SetPriorityClass(ctypes.c_void_p(-1), 0x4000)


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        while data := f.read(1024*1024):
            h.update(data)
    return h.hexdigest()


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding='utf-8')


def command(args, cwd, log, timeout=600):
    start = time.monotonic()
    env = os.environ.copy()
    env.update(OMP_NUM_THREADS='2', OPENBLAS_NUM_THREADS='2',
               CCX_NPROC_RESULTS='2', NUMBER_OF_CPUS='2')
    with Path(log).open('w', encoding='utf-8') as stream:
        proc = subprocess.run([str(x) for x in args], cwd=str(cwd), env=env,
                              stdout=stream, stderr=subprocess.STDOUT,
                              timeout=timeout, creationflags=0x08000000 if os.name == 'nt' else 0)
    elapsed = time.monotonic()-start
    if proc.returncode:
        tail = Path(log).read_text(encoding='utf-8', errors='replace')[-3500:]
        raise RuntimeError(f'{Path(args[0]).name} exit {proc.returncode}; {log}\n{tail}')
    return elapsed


@dataclass
class Mesh:
    ids: np.ndarray
    xyz: np.ndarray
    eids: np.ndarray
    conn: np.ndarray       # zero-based row indices, Abaqus C3D10 order
    faces: np.ndarray     # boundary triangles, six nodes each
    normals: np.ndarray
    centers: np.ndarray
    face_weights: np.ndarray
    areas: np.ndarray
    volumes: np.ndarray
    quadrature_volumes: np.ndarray
    inp: Path
    stats: dict


# Corner-first face nodes for Abaqus/CalculiX C3D10 ordering. Gmsh's Abaqus
# exporter performs the Gmsh->Abaqus edge-node reorder; do not reinterpret MSH.
FACES = ((0,1,2,4,5,6), (0,3,1,7,8,4),
         (1,3,2,8,9,5), (2,3,0,9,7,6))
OPPOSITE = (3,2,0,1)


def face_quadrature(coords):
    """Consistent nodal weights for quadratic triangles; 7-point integration."""
    a, b = .059715871789770, .470142064105115
    c, d = .797426985353087, .101286507323456
    quadrature = [((1/3,1/3), .225/2),
                  ((a,b), .132394152788506/2), ((b,a), .132394152788506/2),
                  ((b,b), .132394152788506/2),
                  ((c,d), .125939180544827/2), ((d,c), .125939180544827/2),
                  ((d,d), .125939180544827/2)]
    weights = np.zeros((len(coords), 6))
    area_centroid = np.zeros((len(coords), 3))
    area = np.zeros(len(coords))
    for (u,v), w in quadrature:
        l = 1-u-v
        n = np.array([l*(2*l-1), u*(2*u-1), v*(2*v-1), 4*l*u, 4*u*v, 4*v*l])
        du = np.array([1-4*l, 4*u-1, 0, 4*(l-u), 4*v, -4*v])
        dv = np.array([1-4*l, 0, 4*v-1, -4*u, 4*u, 4*(l-v)])
        jac = np.linalg.norm(np.cross(coords.transpose(0,2,1)@du,
                                      coords.transpose(0,2,1)@dv), axis=1)
        local = jac*w
        weights += local[:,None]*n
        area += local
        area_centroid += local[:,None]*(coords.transpose(0,2,1)@n)
    return weights, area, area_centroid / area[:,None]


def parse_mesh(path):
    nodes, elems = {}, {}
    section = None
    partial = []
    for line in Path(path).read_text(encoding='utf-8', errors='replace').splitlines():
        line = line.strip()
        if not line or line.startswith('**'):
            continue
        if line.startswith('*'):
            upper = line.upper()
            section = 'nodes' if upper == '*NODE' else (
                'elems' if upper.startswith('*ELEMENT') and 'TYPE=C3D10' in upper else None)
            partial = []
            continue
        fields = [x.strip() for x in line.split(',') if x.strip()]
        if section == 'nodes':
            nodes[int(fields[0])] = [float(x) for x in fields[1:4]]
        elif section == 'elems':
            partial.extend(int(x) for x in fields)
            if len(partial) == 11:
                elems[partial[0]] = partial[1:]
                partial = []
            elif len(partial) > 11:
                raise ValueError(f'Unexpected C3D10 line: {line}')
    if not elems:
        raise ValueError(f'No C3D10 elements in {path}')
    used = sorted({n for conn in elems.values() for n in conn})
    ids = np.array(used, dtype=np.int64)
    xyz = np.array([nodes[n] for n in used])
    index = {n:i for i,n in enumerate(used)}
    eids = np.array(sorted(elems), dtype=np.int64)
    conn = np.array([[index[n] for n in elems[e]] for e in eids], dtype=np.int64)
    corners = xyz[conn[:,:4]]
    signed = np.linalg.det(corners[:,1:]-corners[:,:1])/6
    if np.any(signed <= 0):
        raise ValueError(f'Nonpositive corner tetra volumes: {(signed <= 0).sum()}')
    edge_square_sum=sum(np.sum((corners[:,i]-corners[:,j])**2,axis=1)
                        for i,j in ((0,1),(0,2),(0,3),(1,2),(1,3),(2,3)))
    mean_ratio=12*np.power(3*signed,2/3)/edge_square_sum
    # Positive corner volume is insufficient for curved second-order tets.
    # Evaluate actual C3D10 isoparametric Jacobians at its four integration
    # points and at the centre before passing the mesh to the solver.
    qa,qb=.5854101966249685,.1381966011250105
    jacobians=[]
    for u,v,w in ((qa,qb,qb),(qb,qa,qb),(qb,qb,qa),(qb,qb,qb),(.25,.25,.25)):
        l=1-u-v-w
        du=np.array([1-4*l,4*u-1,0,0,4*(l-u),4*v,-4*v,-4*w,4*w,0])
        dv=np.array([1-4*l,0,4*v-1,0,-4*u,4*u,4*(l-v),-4*w,0,4*w])
        dw=np.array([1-4*l,0,0,4*w-1,-4*u,0,-4*v,4*(l-w),4*u,4*v])
        derivative=np.stack((du,dv,dw),axis=1)
        jacobians.append(np.linalg.det(xyz[conn].transpose(0,2,1)@derivative))
    jacobians=np.array(jacobians)
    if np.any(jacobians<=0):
        raise ValueError(f'Nonpositive quadratic tetra integration/centre Jacobians: {(jacobians<=0).sum()}')
    allfaces = np.concatenate([conn[:,f] for f in FACES])
    keys = np.sort(allfaces[:,:3], axis=1)
    _, first, counts = np.unique(keys, axis=0, return_index=True, return_counts=True)
    boundary_first = first[counts == 1]
    if np.any(counts > 2):
        raise ValueError('Non-manifold tetrahedral face incidence')
    faces = allfaces[boundary_first]
    face_num = boundary_first // len(conn)
    elem_num = boundary_first % len(conn)
    coords = xyz[faces]
    normal = np.cross(coords[:,1]-coords[:,0], coords[:,2]-coords[:,0])
    normal /= np.linalg.norm(normal, axis=1)[:,None]
    opp = xyz[conn[elem_num, np.asarray(OPPOSITE)[face_num]]]
    flip = np.einsum('ij,ij->i', normal, opp-coords[:,0]) > 0
    normal[flip] *= -1
    weights, areas, centers = face_quadrature(coords)
    rows = np.repeat(conn[:,0], 9)
    cols = conn[:,1:].reshape(-1)
    adj = coo_matrix((np.ones(len(rows)), (rows,cols)), shape=(len(ids),len(ids)))
    ncomp = int(connected_components(adj, directed=False, return_labels=False))
    if ncomp != 1:
        raise ValueError(f'Mesh has {ncomp} disconnected solid node components')
    stats = dict(nodes=len(ids), elements=len(conn), element_type='C3D10',
                 boundary_tri6=len(faces), connected_components=ncomp,
                 corner_tet_min_volume_mm3=float(signed.min()),
                 corner_tet_total_volume_mm3=float(signed.sum()),
                 corner_tet_mean_ratio_min=float(mean_ratio.min()),
                 corner_tet_mean_ratio_p01=float(np.percentile(mean_ratio,1)),
                 corner_tet_mean_ratio_definition='12*(3V)^(2/3)/sum(six squared edge lengths); regular tetrahedron=1, degenerate=0. Corner geometry diagnostic only.',
                 quadratic_tet_integrated_volume_mm3=float(jacobians[:4].sum()/24),
                 quadratic_jacobian_min_mm3=float(jacobians.min()),
                 quadratic_jacobian_min_over_max_per_element=float((jacobians.min(axis=0)/jacobians.max(axis=0)).min()),
                 quadratic_jacobian_check='Four C3D10 integration points and centroid; all positive. This is not a formal interval proof at every point.',
                 quadratic_boundary_area_mm2=float(areas.sum()),
                 mesh_file_sha256=digest(path))
    return Mesh(ids,xyz,eids,conn,faces,normal,centers,weights,areas,signed,
                jacobians[:4].T/24,Path(path),stats)


def generate_mesh(directory, size, step=None, beam=False):
    directory.mkdir(parents=True, exist_ok=True)
    inp = directory/'mesh.inp'
    header = 'SetFactory("OpenCASCADE");\n'
    if beam:
        header += 'Box(1) = {0,-2,-2,40,4,4};\n'
    else:
        header += f'Merge "{Path(step).resolve().as_posix()}";\n'
    text = header + f'''
Physical Volume("BODY") = Volume{{:}};
General.NumThreads = 2;
Mesh.MaxNumThreads1D = 2;
Mesh.MaxNumThreads2D = 2;
Mesh.MaxNumThreads3D = 2;
Mesh.MeshSizeMin = {size if beam else max(.35,size*.38):.8g};
Mesh.MeshSizeMax = {size:.8g};
Mesh.MeshSizeFromPoints = 1;
Mesh.MeshSizeFromCurvature = {0 if beam else 24};
Mesh.MeshSizeExtendFromBoundary = 1;
Mesh.Algorithm = 6;
Mesh.Algorithm3D = 1;
Mesh.ElementOrder = 2;
Mesh.SecondOrderLinear = 0;
Mesh.HighOrderOptimize = 2;
Mesh.Optimize = 1;
Mesh.SaveAll = 0;
'''
    geo_sha=hashlib.sha256(text.encode('utf-8')).hexdigest()
    quality_path=directory/'mesh_quality.json'
    if inp.is_file() and quality_path.is_file():
        old=json.loads(quality_path.read_text(encoding='utf-8'))
        if old.get('geo_sha256')==geo_sha and old.get('mesh_file_sha256')==digest(inp):
            mesh=parse_mesh(inp)
            mesh.stats={**old,**mesh.stats}
            print('REUSE_MESH',directory,flush=True)
            return mesh
    (directory/'mesh.geo').write_text(text, encoding='utf-8')
    seconds = command([GMSH,'mesh.geo','-3','-nt','2','-format','inp','-o','mesh.inp','-v','3'],
                      directory,directory/'gmsh.log',timeout=600)
    mesh = parse_mesh(inp)
    mesh.stats.update(target_max_size_mm=size, meshing_seconds=seconds,geo_sha256=geo_sha,
                      source_step_sha256=None if beam else digest(step))
    write_json(directory/'mesh_quality.json', mesh.stats)
    np.savez_compressed(directory/'mesh_arrays.npz', node_ids=mesh.ids,xyz=mesh.xyz,
                        element_ids=mesh.eids,conn=mesh.conn,boundary_faces=mesh.faces)
    return mesh


def selected_load(mesh, mask, direction, force, name):
    selected = np.flatnonzero(mask)
    if len(selected) == 0:
        raise ValueError(f'Load region {name} has no boundary faces')
    area = float(mesh.areas[selected].sum())
    if area < 1:
        raise ValueError(f'Load region {name} area {area:.4g} mm2 is too small')
    direction = np.asarray(direction, dtype=float)
    direction /= np.linalg.norm(direction)
    loads = np.zeros((len(mesh.ids),3))
    for j in range(6):
        np.add.at(loads, mesh.faces[selected,j],
                  (force/area*mesh.face_weights[selected,j])[:,None]*direction)
    centroid = np.sum(mesh.centers[selected]*mesh.areas[selected,None],axis=0)/area
    return loads, dict(name=name, magnitude_N=force, direction=direction.tolist(),
                       selected_triangles=len(selected), surface_area_mm2=area,
                       pressure_magnitude_MPa=force/area,
                       area_centroid_mm=centroid.tolist(),
                       actual_force_sum_N=loads.sum(axis=0).tolist(),
                       selected_face_centers_bounds_mm=[mesh.centers[selected].min(axis=0).tolist(),
                                                       mesh.centers[selected].max(axis=0).tolist()],
                       distribution='Uniform vector surface traction, integrated using 7-point quadratic-triangle shape functions; total resultant normalized to specified N.')


def write_set(f, name, ids):
    f.write(f'*NSET,NSET={name}\n')
    ids = list(ids)
    for i in range(0,len(ids),16):
        f.write(','.join(str(int(x)) for x in ids[i:i+16])+'\n')


def write_deck(mesh, directory, young, poisson, constraints, loads):
    directory.mkdir(parents=True, exist_ok=True)
    deck = directory/'solve.inp'
    support = sorted({i for i,dof in constraints})
    with deck.open('w', encoding='ascii', newline='\n') as f:
        f.write('*HEADING\nActual linear-elastic solid FEM; mm N MPa\n*NODE\n')
        for nid, p in zip(mesh.ids, mesh.xyz):
            f.write(f'{nid},{p[0]:.12g},{p[1]:.12g},{p[2]:.12g}\n')
        f.write('*ELEMENT,TYPE=C3D10,ELSET=EALL\n')
        for eid, conn in zip(mesh.eids, mesh.conn):
            f.write(str(eid)+','+','.join(str(int(x)) for x in mesh.ids[conn])+'\n')
        write_set(f,'NALL',mesh.ids)
        write_set(f,'SUPPORT',mesh.ids[support])
        f.write(f'*MATERIAL,NAME=PLA_IDEAL\n*ELASTIC\n{young:.12g},{poisson:.12g}\n')
        f.write('*SOLID SECTION,ELSET=EALL,MATERIAL=PLA_IDEAL\n*BOUNDARY\n')
        for i,dof in sorted(set(constraints)):
            f.write(f'{mesh.ids[i]},{dof},{dof},0\n')
        f.write('*STEP\n*STATIC\n1.,1.\n*CLOAD\n')
        for i in np.flatnonzero(np.any(np.abs(loads)>1e-13,axis=1)):
            for dof in range(3):
                if abs(loads[i,dof])>1e-13:
                    f.write(f'{mesh.ids[i]},{dof+1},{loads[i,dof]:.12g}\n')
        f.write('*NODE PRINT,NSET=NALL\nU\n*NODE PRINT,NSET=SUPPORT\nRF\n')
        f.write('*EL PRINT,ELSET=EALL\nS\n*NODE FILE\nU\n*EL FILE\nS\n*END STEP\n')
    return deck


def parse_dat(path):
    displacement, force, stress = {}, {}, []
    mode = None
    for line in Path(path).read_text(encoding='utf-8',errors='replace').splitlines():
        low = line.lower().strip()
        if low.startswith('displacements ('):
            mode = 'u'
            continue
        if low.startswith('forces ('):
            mode = 'rf'
            continue
        if low.startswith('stresses ('):
            mode = 's'
            continue
        bits = line.split()
        if not bits or not bits[0].isdigit():
            continue
        if mode in ('u','rf') and len(bits) == 4:
            (displacement if mode=='u' else force)[int(bits[0])] = [float(x) for x in bits[1:]]
        elif mode == 's' and len(bits) == 8:
            stress.append([int(bits[0]),int(bits[1]),*[float(x) for x in bits[2:]]])
    if not displacement or not force or not stress:
        raise ValueError(f'Incomplete CalculiX DAT output: u={len(displacement)} rf={len(force)} s={len(stress)}')
    if not all(np.isfinite(x).all() for x in (
        np.asarray(list(displacement.values())), np.asarray(list(force.values())), np.asarray(stress))):
        raise ValueError(f'Non-finite values in CalculiX output: {path}')
    return displacement,force,np.array(stress)


def solve(mesh, directory, young, poisson, constraints, loads, description, feet=None):
    deck = write_deck(mesh,directory,young,poisson,constraints,loads)
    result_path=directory/'result.json'
    array_path=directory/'result_arrays.npz'
    if result_path.is_file() and array_path.is_file() and (directory/'solve.dat').is_file():
        old=json.loads(result_path.read_text(encoding='utf-8'))
        if (old.get('deck_sha256')==digest(deck) and
            old.get('dat_sha256')==digest(directory/'solve.dat') and
            old.get('mesh',{}).get('mesh_file_sha256')==mesh.stats['mesh_file_sha256'] and
            old.get('postprocess_version')==POSTPROCESS_VERSION):
            print('REUSE_SOLVE',directory,flush=True)
            old['mesh']=mesh.stats
            with np.load(array_path) as arrays:
                return old,arrays['displacement_mm'].copy()
    seconds = command([CCX,'-i','solve'],directory,directory/'ccx.log',timeout=600)
    log = (directory/'ccx.log').read_text(encoding='utf-8',errors='replace')
    if 'Job finished' not in log:
        raise RuntimeError(f'CalculiX did not report Job finished: {directory}')
    ud,rf,stress = parse_dat(directory/'solve.dat')
    u = np.array([ud[int(n)] for n in mesh.ids])
    support = sorted({i for i,dof in constraints})
    # RF is total external nodal force. Subtract any applied CLOAD on the
    # support nodes before calling it a reaction; normally these are disjoint.
    reactions = np.array([rf[int(mesh.ids[i])] for i in support])-loads[support]
    total_reaction = reactions.sum(axis=0)
    applied = loads.sum(axis=0)
    force_error = total_reaction+applied
    moment_reaction = np.cross(mesh.xyz[support],reactions).sum(axis=0)
    moment_applied = np.cross(mesh.xyz,loads).sum(axis=0)
    moment_error = moment_reaction+moment_applied
    scale = max(1,float(np.linalg.norm(applied)))
    force_relative = float(np.linalg.norm(force_error)/scale)
    moment_relative = float(np.linalg.norm(moment_error)/(scale*max(1,np.ptp(mesh.xyz,axis=0).max())))
    sx,sy,sz,txy,txz,tyz = stress[:,2:].T
    vm = np.sqrt(.5*((sx-sy)**2+(sy-sz)**2+(sz-sx)**2)+3*(txy*txy+txz*txz+tyz*tyz))
    element_indices=np.searchsorted(mesh.eids,stress[:,0].astype(np.int64))
    integration_indices=stress[:,1].astype(np.int64)-1
    if not np.all((integration_indices>=0)&(integration_indices<4)):
        raise ValueError('Expected four C3D10 stress integration points per element')
    stress_volume_weights=mesh.quadrature_volumes[element_indices,integration_indices]
    order=np.argsort(vm)
    cumulative=np.cumsum(stress_volume_weights[order])
    p95=float(np.interp(.95*cumulative[-1],cumulative,vm[order]))
    unorm = np.linalg.norm(u,axis=1)
    peak_i = int(np.argmax(vm))
    peak_elem = int(stress[peak_i,0])
    e_index = int(np.flatnonzero(mesh.eids==peak_elem)[0])
    integration_element_centers=mesh.xyz[mesh.conn[np.searchsorted(mesh.eids,stress[:,0].astype(np.int64)),:4]].mean(axis=1)
    horizontal_anchors=sorted({i for i,dof in constraints if dof in (1,2)})
    anchor_distance=np.linalg.norm(integration_element_centers[:,None,:]-mesh.xyz[horizontal_anchors][None,:,:],axis=2).min(axis=1)
    outside_anchor=anchor_distance>=3.
    foot_reactions = []
    if feet is not None:
        ridx = {int(i):j for j,i in enumerate(support)}
        for n,indices in enumerate(feet):
            rr = np.array([reactions[ridx[int(i)]] for i in indices])
            foot_reactions.append(dict(foot=n+1, constrained_nodes=len(indices),
                                       reaction_N=rr.sum(axis=0).tolist(),
                                       negative_z_requires_hold_down=bool(rr[:,2].sum() < -.005)))
    result = dict(postprocess_version=POSTPROCESS_VERSION,case=description, material=dict(E_MPa=young,nu=poisson,
                  model='homogeneous isotropic linear elastic; not measured printed PLA'),
                  mesh=mesh.stats, deck_sha256=digest(deck), dat_sha256=digest(directory/'solve.dat'),
                  solving_seconds=seconds, applied_force_N=applied.tolist(),
                  support_reaction_N=total_reaction.tolist(), force_balance_error_N=force_error.tolist(),
                  force_balance_relative_error=force_relative,
                  moment_balance_error_Nmm=moment_error.tolist(),
                  moment_balance_relative_error=moment_relative,
                  equilibrium_pass=force_relative<1e-4 and moment_relative<1e-4,
                  maximum_displacement_mm=float(unorm.max()),
                  maximum_displacement_node=int(mesh.ids[int(np.argmax(unorm))]),
                  displacement_components_at_max_mm=u[int(np.argmax(unorm))].tolist(),
                  maximum_vm_stress_MPa=float(vm.max()),
                  p95_integration_point_vm_MPa=p95,
                  unweighted_integration_point_p95_vm_MPa=float(np.percentile(vm,95)),
                  p95_definition='95th percentile of integration-point von Mises stress weighted by actual C3D10 Jacobian quadrature volume; avoids overweighting locally tiny elements.',
                  peak_stress_element=peak_elem,
                  peak_stress_element_centroid_mm=mesh.xyz[mesh.conn[e_index,:4]].mean(axis=0).tolist(),
                  peak_element_distance_to_nearest_horizontal_constraint_node_mm=float(anchor_distance[peak_i]),
                  auxiliary_peak_vm_outside_3mm_horizontal_constraint_neighbourhood_MPa=float(vm[outside_anchor].max()) if np.any(outside_anchor) else None,
                  auxiliary_stress_scope='Diagnostic only: removes element-centroid regions within 3 mm of the minimum horizontal point anchors, which can create stress singularities. The global maximum remains separately reported and is not replaced for a strength claim.',
                  foot_reactions=foot_reactions,
                  negative_foot_reactions=any(x['negative_z_requires_hold_down'] for x in foot_reactions),
                  interpretation='Bilateral Z supports model a supported/held test fixture. Negative net foot reaction indicates lift-off for a free unbonded mouse; that case is not a valid all-five-feet contact prediction. Peak stresses near constraints/load edges may be singular; p95 is a convergence diagnostic, not a strength substitute.')
    write_json(directory/'result.json',result)
    np.savez_compressed(directory/'result_arrays.npz',node_ids=mesh.ids,xyz=mesh.xyz,
                        displacement_mm=u,stress_element_ids=stress[:,0].astype(np.int64),
                        stress_integration_points=stress[:,1].astype(np.int64),
                        stress_tensor_MPa=stress[:,2:],von_mises_MPa=vm)
    return result,u


def beam_benchmark():
    results=[]
    # Independent continuum benchmark: 40 x 4 x 4 mm cantilever; 1 N
    # uniformly distributed end shear, and independent 10 N axial traction.
    length,b,h,young,nu=40.,4.,4.,1500.,.35
    euler=length**3/(3*young*(b*h**3/12))
    shear=length/((5/6)*(young/(2*(1+nu)))*b*h)
    exact_axial=10*length/(young*b*h)
    for size in (2.0,1.25):
        directory=WORK/'benchmark'/f'h{size:g}'
        mesh=generate_mesh(directory,size,beam=True)
        fixed=np.flatnonzero(mesh.xyz[:,0]<1e-7)
        constraints=[(int(i),d) for i in fixed for d in (1,2,3)]
        tip=np.flatnonzero(mesh.xyz[:,0]>length-1e-7)
        face_mask=(mesh.centers[:,0]>length-1e-6)&(mesh.normals[:,0]>.99)
        for name,direction,magnitude,expected,component in (
            ('cantilever_bending',[0,0,-1],1.,euler+shear,2),
            ('axial_tension',[1,0,0],10.,exact_axial,0)):
            loads,description=selected_load(mesh,face_mask,direction,magnitude,name)
            result,u=solve(mesh,directory/name,young,nu,constraints,loads,description)
            # Area-weighted displacement is work-conjugate to the end traction.
            nodal_weights=np.abs(loads[:,component])/magnitude
            measured=abs(float(nodal_weights@u[:,component]))
            result.update(analytic_displacement_mm=expected,measured_end_displacement_mm=measured,
                          relative_analytic_error=abs(measured/expected-1),
                          euler_bernoulli_displacement_mm=euler if component==2 else None,
                          timoshenko_shear_addition_mm=shear if component==2 else None)
            write_json(directory/name/'result.json',result)
            results.append(result)
            print('BENCHMARK',size,name,measured,expected,result['relative_analytic_error'],flush=True)
    fine=results[-2:]
    convergence=[]
    for j in range(2):
        coarse,finer=results[j],results[j+2]
        convergence.append(dict(case=finer['case']['name'],
             displacement_relative_change=abs(coarse['measured_end_displacement_mm']/finer['measured_end_displacement_mm']-1)))
    passed=all(x['equilibrium_pass'] and x['relative_analytic_error']<.05 for x in fine) and all(
        x['displacement_relative_change']<.05 for x in convergence)
    report=dict(units='mm N MPa', solver='CalculiX 2.22', mesher='Gmsh 4.15.0',
                benchmark='40 x 4 x 4 mm cantilever: 1 N end shear and 10 N axial traction; 1500 MPa, nu .35',
                analytic_formulas=dict(axial='F L / (E A)',bending='F L^3 / (3 E I)',
                                       shear='F L / ((5/6) G A)',G='E/(2(1+nu))'),
                acceptance='Fine-grid analytic error <5%, two-grid displacement change <5%, force/moment balance relative error <1e-4',
                results=results,convergence=convergence,pass_check=passed,source_docs=SOURCE_DOCS)
    write_json(WORK/'benchmark/benchmark.json',report)
    REPORT.mkdir(parents=True,exist_ok=True)
    write_json(REPORT/'fem_beam_benchmark.json',report)
    lines=['# FEM 求解器解析梁验证','',
           '实际运行 Gmsh 4.15.0 和 CalculiX 2.22；毫米、牛顿、MPa。40×4×4 mm 固支梁，E=1500 MPa、ν=0.35；端面面积积分施加 1 N 横向剪力及独立 10 N 轴向拉力。','',
           '| 网格 mm | 工况 | 计算位移 mm | 解析位移 mm | 误差 |',
           '|---:|---|---:|---:|---:|']
    for r in results:
        lines.append(f'| {r["mesh"]["target_max_size_mm"]:.3g} | {r["case"]["name"]} | {r["measured_end_displacement_mm"]:.8g} | {r["analytic_displacement_mm"]:.8g} | {r["relative_analytic_error"]:.3%} |')
    lines += ['', f'验收结果：**{passed}**。细网格解析误差及两档位移变化 <5%；反力、力矩平衡相对误差 <0.01%。',
              '', '解析式：轴向 FL/EA；横弯 FL³/(3EI)+FL/((5/6)GA)，G=E/(2(1+ν))。固支端局部三维约束与梁理论仍有小差异。',
              '', '各次真实求解的输入、DAT 哈希、节点/单元数和具体平衡误差见 fem_beam_benchmark.json；原始作业位于 E 盘支持目录。','']
    (REPORT/'FEM_BEAM_BENCHMARK.md').write_text('\n'.join(lines),encoding='utf-8')
    return report


def foot_constraints(mesh,p):
    centers=np.asarray(p['feet']['centers'])
    radius=p['feet']['diameter']/2
    feet=[]
    for center in centers:
        indices=np.flatnonzero((mesh.xyz[:,2]<.025)&
                              (np.linalg.norm(mesh.xyz[:,:2]-center,axis=1)<radius+.03))
        if len(indices)<6:
            raise ValueError(f'Too few support nodes at foot {center}: {len(indices)}')
        feet.append(indices)
    a=int(feet[0][np.argmin(np.linalg.norm(mesh.xyz[feet[0],:2]-centers[0],axis=1))])
    b=int(feet[1][np.argmin(np.linalg.norm(mesh.xyz[feet[1],:2]-centers[1],axis=1))])
    constraints=[(int(i),3) for group in feet for i in group]+[(a,1),(a,2),(b,2)]
    description=dict(vertical='All five foot bottom surface nodes: Uz=0 only; no pad has full XYZ clamp.',
                     horizontal='One node near front-left foot center Ux=Uy=0; one near front-right center Uy=0, eliminating exactly three in-plane rigid DOFs.',
                     horizontal_anchor_node_ids=[int(mesh.ids[a]),int(mesh.ids[b])],
                     horizontal_anchor_coordinates_mm=[mesh.xyz[a].tolist(),mesh.xyz[b].tolist()],
                     foot_centers_xy_mm=centers.tolist(),
                     foot_support_node_counts=[len(x) for x in feet],
                     physical_limit='Bilateral vertical fixture constraints permit tensile reactions; report lift-off whenever a pad requires tension. No friction/contact solve or glue is claimed.')
    return constraints,feet,description


def body_cases(mesh,p,metadata=None):
    x,y,z=mesh.centers.T
    nx,ny,nz=mesh.normals.T
    root_y=p['main']['root_y']
    cases=[
        selected_load(mesh,(y>=44)&(y<=71)&(np.abs(x)<=24)&(z>=23)&(nz>.3),
                      [0,0,-1],20,'palm_down_20N'),
        selected_load(mesh,(y>=root_y-3)&(y<=root_y+4)&(x<=-6)&(x>=-24)&(z>=11)&(nz>.2),
                      [0,0,-1],5,'left_main_root_down_5N'),
    ]
    # The switch is supported by an internal far-end fence. A load on the
    # exterior grip skin would bypass its suspended socket and thin braces.
    # Use the actual exported mechanism metadata, not a point in a window.
    if metadata is None:
        metadata_path=REPORT/'design_metadata.json'
        metadata=json.loads(metadata_path.read_text(encoding='utf-8-sig'))
    motions=metadata['mechanisms']['side_motions']
    for i,motion in enumerate(motions):
        # mechanics.py: plunger_tip=body_near-.6, inner fence=body_near+6.6.
        tip=np.asarray(motion['plunger_tip'],dtype=float)
        fence_x=tip[0]+7.2
        cy,cz=tip[1:]
        load,description=selected_load(
            mesh,(np.abs(x-fence_x)<.04)&(np.abs(y-cy)<=7.25)&
                 (np.abs(z-cz)<=3.3)&(nx<-.95),
            [1,0,0],5,f'side_{i+1}_switch_fence_inward_5N')
        description['transfer_model']='5 N switch rear reaction distributed on the actual exposed inner far-end-fence face; key cap, switch compliance and screw contact are not included in this BODY-only load transfer model.'
        description['target_inner_fence_x_mm']=fence_x
        cases.append((load,description))
    return cases


def held_side_cases(mesh,p,metadata,cases):
    """Fine-grid supplementary tests, distinct from pure-side fixture cases."""
    result=[]
    x,y,z=mesh.centers.T
    nx=mesh.normals[:,0]
    for i,(side_load,side_description) in enumerate(cases[2:]):
        cy=float(metadata['mechanisms']['side_motions'][i]['plunger_tip'][1])
        palm=cases[0][0]*.25
        baseline=palm+side_load
        description=dict(name=f'side_{i+1}_with_5N_palm_preload',
                         components=[dict(case='palm_down_20N',scale=.25),side_description],
                         actual_force_sum_N=baseline.sum(axis=0).tolist(),
                         physical_assumption='Specified 5 N downward hand preload plus 5 N side-switch reaction; no opposite gripping force. Not a measured hand-force distribution.')
        result.append((baseline,description))
        counter,counter_description=selected_load(
            mesh,(x>=21)&(np.abs(y-cy)<=5)&(z>=12)&(z<=18)&(nx>.3),
            [-1,0,0],5,f'right_grip_counterforce_for_side_{i+1}')
        combined=baseline+counter
        description=dict(name=f'side_{i+1}_held_pinch_with_5N_palm',
                         components=[dict(case='palm_down_20N',scale=.25),side_description,counter_description],
                         actual_force_sum_N=combined.sum(axis=0).tolist(),
                         physical_assumption='Specified held-mouse test: 5 N palm preload and opposing 5 N right-side grip balances the left switch force. Actual grip/contact and friction are not measured or solved.')
        result.append((combined,description))
    return result


def body_analysis(sizes,step,youngs=(1500.,2300.)):
    parameter_path=ROOT/'cad/rebuild_r1/parameters.json'
    parameter_raw=parameter_path.read_bytes()
    p=json.loads(parameter_raw.decode('utf-8-sig'))
    metadata_raw=(REPORT/'design_metadata.json').read_bytes()
    metadata=json.loads(metadata_raw.decode('utf-8-sig'))
    if metadata['parameters']!=p:
        raise ValueError('Current parameters differ from the exported CAD metadata; rebuild before FEM')
    source=digest(step)
    # Root may continue editing the project while background meshing runs.
    # Freeze the actual analysis input and definitions for all mesh levels.
    inputs=WORK/'inputs'/source[:12]
    inputs.mkdir(parents=True,exist_ok=True)
    frozen_step=inputs/'BODY.step'
    if not frozen_step.exists():
        shutil.copyfile(step,frozen_step)
    if digest(frozen_step)!=source:
        raise ValueError('Frozen STEP copy does not match the intended source')
    (inputs/'parameters.json').write_bytes(parameter_raw)
    (inputs/'design_metadata.json').write_bytes(metadata_raw)
    benchmark_path=REPORT/'fem_beam_benchmark.json'
    benchmark=json.loads(benchmark_path.read_text()) if benchmark_path.exists() else beam_benchmark()
    if not benchmark['pass_check']:
        raise RuntimeError('Beam benchmark did not pass; refuse body verification')
    levels=[]
    for size in sizes:
        directory=WORK/'body'/f'h{size:g}_{source[:10]}'
        mesh=generate_mesh(directory,size,step=frozen_step)
        constraints,feet,support=foot_constraints(mesh,p)
        cases=body_cases(mesh,p,metadata)
        write_json(directory/'support_and_loads.json',dict(support=support,loads=[d for _,d in cases]))
        results=[]
        # Both E values are actually solved. Linear-model 1/E scaling is also
        # checked; the high-E case is not merely estimated from the low-E run.
        for young in youngs:
            for loads,description in cases:
                result,_=solve(mesh,directory/f'E{young:g}_{description["name"]}',young,.35,
                               constraints,loads,description,feet)
                results.append(result)
                print('BODY',size,young,description['name'],
                      'umax',result['maximum_displacement_mm'],
                      'smax',result['maximum_vm_stress_MPa'],
                      'p95',result['p95_integration_point_vm_MPa'],flush=True)
        levels.append(dict(size_mm=size,mesh=mesh.stats,support=support,results=results))
        write_json(WORK/'body/progress.json',dict(source_step_sha256=source,completed_levels=levels))
    supplemental=[]
    for loads,description in held_side_cases(mesh,p,metadata,cases):
        r,_=solve(mesh,directory/f'E{youngs[0]:g}_{description["name"]}',youngs[0],.35,
                  constraints,loads,description,feet)
        supplemental.append(r)
        print('HELD_SIDE',description['name'],'umax',r['maximum_displacement_mm'],
              'negative_feet',r['negative_foot_reactions'],flush=True)
    convergence=[]
    for a,b in zip(levels,levels[1:]):
        for ra,rb in zip(a['results'],b['results']):
            def relative(key):
                return abs(ra[key]/rb[key]-1) if rb[key] else None
            convergence.append(dict(from_size_mm=a['size_mm'],to_size_mm=b['size_mm'],
                                    case=rb['case']['name'],E_MPa=rb['material']['E_MPa'],
                                    displacement_relative_change=relative('maximum_displacement_mm'),
                                    peak_stress_relative_change=relative('maximum_vm_stress_MPa'),
                                    p95_stress_relative_change=relative('p95_integration_point_vm_MPa')))
    sensitivity=[]
    for level in levels:
        low=[r for r in level['results'] if r['material']['E_MPa']==youngs[0]]
        high=[r for r in level['results'] if r['material']['E_MPa']==youngs[1]]
        for a,b in zip(low,high):
            ratio=a['maximum_displacement_mm']/b['maximum_displacement_mm']
            sensitivity.append(dict(size_mm=level['size_mm'],case=a['case']['name'],
                                    measured_displacement_ratio=ratio,expected_ratio=youngs[1]/youngs[0],
                                    ratio_relative_error=abs(ratio/(youngs[1]/youngs[0])-1),
                                    stress_relative_change=abs(a['maximum_vm_stress_MPa']/b['maximum_vm_stress_MPa']-1)))
    latest=[c for c in convergence if c['to_size_mm']==levels[-1]['size_mm']]
    converged=len(levels)>=3 and bool(latest) and all(c['displacement_relative_change']<.05 and
                                  c['p95_stress_relative_change']<.05 for c in latest)
    peak_stress_converged=bool(latest) and all(c['peak_stress_relative_change']<.05 for c in latest)
    result=dict(version='R1',units='mm N MPa',source_step_sha256=source,
                source_step=str(step),frozen_source_step=str(frozen_step),
                parameters_sha256=hashlib.sha256(parameter_raw).hexdigest(),
                design_metadata_sha256=hashlib.sha256(metadata_raw).hexdigest(),
                source_still_current_at_completion=digest(step)==source and parameter_path.read_bytes()==parameter_raw and (REPORT/'design_metadata.json').read_bytes()==metadata_raw,
                solver=dict(name='CalculiX',version='2.22',exe_sha256=digest(CCX)),
                mesher=dict(name='Gmsh',version='4.15.0',exe_sha256=digest(GMSH)),
                formulation='Static small-displacement homogeneous isotropic linear elasticity; quadratic C3D10 tetrahedra.',
                benchmark_pass=benchmark['pass_check'],mesh_levels=levels,convergence=convergence,
                fine_grid_supplemental_cases=supplemental,
                convergence_pass=converged,young_modulus_sensitivity=sensitivity,
                peak_stress_convergence_pass=peak_stress_converged,
                equilibrium_pass=all(r['equilibrium_pass'] for l in levels for r in l['results']) and all(r['equilibrium_pass'] for r in supplemental),
                negative_reactions_present=any(r['negative_foot_reactions'] for l in levels for r in l['results']) or any(r['negative_foot_reactions'] for r in supplemental),
                strength_certificate=False,
                material_limit='E=1500/2300 MPa and nu=.35 are stated analysis assumptions, not measured properties of the actual PLA print. No tensile, interlayer, fatigue, screw-bearing or creep allowable was supplied; stress results alone do not certify strength.',
                contact_limit='Feet use bilateral Z fixture supports with minimal in-plane anchors. Any negative pad reaction implies real unbonded contact would lift off; no unilateral/friction contact solution is claimed.',
                convergence_limit='At least three mesh levels and <5% max-displacement / integration-point-p95 stress changes for the final pair are required. Global peak-stress <5% convergence is evaluated separately; an unconverged peak is not silently replaced by p95 as a strength claim.',
                raw_results_directory=str(WORK/'body'),source_docs=SOURCE_DOCS)
    write_json(REPORT/'fem_results.json',result)
    write_json(WORK/'body/fem_results.json',result)
    write_markdown(result,benchmark)
    return result


def write_markdown(result,benchmark):
    lines=['# R1 实际有限元计算记录','',
           '本报告由实际 Gmsh 网格和 CalculiX 求解生成。它验证给定边界条件下的线弹性响应；没有把估算公式当成模型求解，也不把计算称为实物强度认证。','',
           f'- BODY STEP SHA256：`{result["source_step_sha256"]}`',
           '- 单位：mm、N、MPa。二次四面体 C3D10；PLA 假设 E=1500 / 2300 MPa，ν=0.35。',
           '- 五脚底面只固定 Z；前左脚一个节点固定 X/Y、前右脚一个节点固定 Y，共三个面内刚体约束。',
           '- 载荷按选定曲面面积进行二次三角形形函数积分，归一化到指定总力；报告实际面积、合力和载荷位置。',
           '- RF 输出是节点总外力；计算反力时已扣除约束节点上可能存在的外加集中力。','',
           '## 解析梁验证','',
           '40×4×4 mm 固支悬臂梁，E=1500 MPa、ν=0.35；独立求解端面均布 1 N 横向剪力和 10 N 轴向拉力。轴向解析式 FL/EA；横弯采用 FL³/(3EI) 加 FL/((5/6)GA) 剪切项。','',
           '| 网格 (mm) | 工况 | 解析位移 (mm) | 计算端面位移 (mm) | 误差 |','|---:|---|---:|---:|---:|']
    for r in benchmark['results']:
        lines.append(f'| {r["mesh"]["target_max_size_mm"]:.3g} | {r["case"]["name"]} | {r["analytic_displacement_mm"]:.6g} | {r["measured_end_displacement_mm"]:.6g} | {r["relative_analytic_error"]:.2%} |')
    lines += ['',f'解析梁验收：**{benchmark["pass_check"]}**；细网格解析误差及两档位移变化均要求 <5%。','',
              '## 主壳结果','',
              '| 网格 | E (MPa) | 工况 | 节点/单元 | 最大位移 mm | 最大 von Mises MPa | 积分点 P95 MPa | 平衡相对误差 | 脚点需拉住 |',
              '|---:|---:|---|---|---:|---:|---:|---:|---|']
    for level in result['mesh_levels']:
        for r in level['results']:
            lines.append(f'| {level["size_mm"]:.3g} | {r["material"]["E_MPa"]:.0f} | {r["case"]["name"]} | {r["mesh"]["nodes"]}/{r["mesh"]["elements"]} | {r["maximum_displacement_mm"]:.6g} | {r["maximum_vm_stress_MPa"]:.6g} | {r["p95_integration_point_vm_MPa"]:.6g} | {r["force_balance_relative_error"]:.3g} | {r["negative_foot_reactions"]} |')
    for r in result.get('fine_grid_supplemental_cases',[]):
        lines.append(f'| {result["mesh_levels"][-1]["size_mm"]:.3g} | {r["material"]["E_MPa"]:.0f} | {r["case"]["name"]}（补充） | {r["mesh"]["nodes"]}/{r["mesh"]["elements"]} | {r["maximum_displacement_mm"]:.6g} | {r["maximum_vm_stress_MPa"]:.6g} | {r["p95_integration_point_vm_MPa"]:.6g} | {r["force_balance_relative_error"]:.3g} | {r["negative_foot_reactions"]} |')
    lines += ['',f'合力与力矩平衡验收：**{result["equilibrium_pass"]}**。',
              f'三档网格及最终两档收敛验收：**{result["convergence_pass"]}**（至少三档，位移变化 <5%，积分点 P95 应力变化 <5%）。',
              f'全局峰值应力的最终两档变化 <5%：**{result["peak_stress_convergence_pass"]}**；此项单独报告，不能用 P95 掩盖未收敛峰值。',
              '', '| 工况 / E | 网格变化 (mm) | 位移变化 | P95 应力变化 | 峰值应力变化 |',
              '|---|---|---:|---:|---:|']
    for c in result['convergence']:
        lines.append(f'| {c["case"]} / {c["E_MPa"]:.0f} | {c["from_size_mm"]:.3g}→{c["to_size_mm"]:.3g} | {c["displacement_relative_change"]:.2%} | {c["p95_stress_relative_change"]:.2%} | {c["peak_stress_relative_change"]:.2%} |')
    lines += ['', '## 载荷位置及脚点反力','',
              '以下是最终细网格、E=1500 MPa。负 Z 反力表示该脚需要拉住；正值为桌面向上支承。补充工况另外明确给定 5 N 掌压；手持工况再在右侧真实握持面施加相反 5 N 夹持力。附加预载及夹持是定义的试验条件，不是从模型推得的实际人手力量。','',
              '| 工况 | 脚1 Fz N | 脚2 Fz N | 脚3 Fz N | 脚4 Fz N | 脚5 Fz N |','|---|---:|---:|---:|---:|---:|']
    final_low=[r for r in result['mesh_levels'][-1]['results'] if r['material']['E_MPa']==1500]
    for r in final_low+result.get('fine_grid_supplemental_cases',[]):
        foot=' | '.join(f'{f["reaction_N"][2]:.5g}' for f in r['foot_reactions'])
        lines.append(f'| {r["case"]["name"]} | {foot} |')
    lines += ['', '| 基本载荷 | 实际加载曲面面积 mm² | 面积中心 XYZ mm |','|---|---:|---|']
    for r in final_low:
        d=r['case']
        lines.append(f'| {d["name"]} | {d["surface_area_mm2"]:.5g} | {", ".join(f"{x:.4g}" for x in d["area_centroid_mm"])} |')
    lines += ['', '## 接触、强度与解释边界','',
              '所有脚面 Z 约束采用双向支承。某脚反力为负表示该脚必须被拉住才能保持该计算姿态；真实未粘接鼠标会出现脚点离地和支承重分配。因此负反力工况只代表被支承夹具托住的壳体测试，不能声称自然放在桌上仍五脚接触。侧载的水平反力经两个最小定位点闭合，实际桌面摩擦分布未建模。','',
              '最大应力与峰值位置保存在 JSON。约束边缘、载荷边缘和理想尖角可产生局部应力奇异性；P95 只用作网格收敛诊断，不能替代峰值强度验收。没有提供实际打印方向、层间强度、材料批次、螺钉承压或蠕变/疲劳允许值，因此不能由 E 值假设推导出打印成品的安全系数。','',
              '本次只分析 BODY 主壳。主键根部 5 N 是传递到固定根座区域的等效载荷；两个侧载分别施加到真实开关背挡板的内壁，以检查悬吊开关座及其连接。没有在该模型中加入转轴/开关接触、主键弹性或所有螺钉预紧。那些部件仍需独立公差、运动、安装及实物验证。','',
              '每档网格及每次求解的输入、求解器日志、DAT/FRD 和数组均保存在 E 盘支持目录；摘要绑定 STEP、网格、求解输入和 DAT 哈希。','',
              '## 软件说明','',
              f'- [Gmsh 官方手册]({SOURCE_DOCS["gmsh"]})',
              f'- [CalculiX 官方手册]({SOURCE_DOCS["calculix"]})',
              f'- [CalculiX NODE PRINT / RF 说明]({SOURCE_DOCS["calculix_node_print"]})','']
    (REPORT/'FEM_REPORT.md').write_text('\n'.join(lines),encoding='utf-8')


def main():
    low_priority()
    ap=argparse.ArgumentParser()
    ap.add_argument('--benchmark',action='store_true')
    ap.add_argument('--body',action='store_true')
    ap.add_argument('--sizes',type=float,nargs='+',default=[2.0,1.6,1.2])
    ap.add_argument('--step',type=Path,default=ROOT/'exports/rebuild_r1/assembly/BODY.step')
    args=ap.parse_args()
    WORK.mkdir(parents=True,exist_ok=True)
    if args.benchmark or not args.body:
        benchmark=beam_benchmark()
        print('BEAM_PASS',benchmark['pass_check'],flush=True)
    if args.body:
        if not args.step.is_file():
            raise FileNotFoundError(args.step)
        result=body_analysis(args.sizes,args.step)
        print('BODY_EQUILIBRIUM',result['equilibrium_pass'],
              'CONVERGENCE',result['convergence_pass'],flush=True)


if __name__=='__main__':
    main()

"""Reproducible 2D outline comparison; this is not a scan/CAD accuracy claim.

Only generated CAD contours and extracted reference strokes appear in the plot.
The manufacturer product photograph is read locally and is not copied to output.
"""
from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage as ndi
import trimesh

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
SUPPORT=ROOT.parent/'_support'
DEFAULT_REF=SUPPORT/'work/fenrir_rebuild/references/fenrir_official_25.png'
SOURCE_URL='https://shop.g-wolves.com/products/g-wolves-fenrir-pro-8k-wireless-mouse'
IMAGE_URL='https://cdn.shopify.com/s/files/1/0540/7981/5877/files/20250831230412_1528_13.png?v=1766749378'
PARTS=('BODY','LEFT_KEY','RIGHT_KEY','SIDE_FRONT_KEY','SIDE_REAR_KEY','WHEEL')


def fingerprint(path):
    p=Path(path)
    return dict(file=p.name,bytes=p.stat().st_size,
                sha256=hashlib.sha256(p.read_bytes()).hexdigest())


def extract_reference(path,crop,shape,flip_vertical=False):
    im=np.asarray(Image.open(path).convert('RGB'))
    x0,y0,x1,y1=crop
    rgb=im[y0:y1,x0:x1]
    cyan=(rgb[:,:,0]<70)&(rgb[:,:,1]>120)&(rgb[:,:,2]>170)
    labels,n=ndi.label(cyan,structure=np.ones((3,3)))
    if not n:
        raise ValueError('Reference crop contains no cyan outline')
    counts=np.bincount(labels.ravel());counts[0]=0
    line=labels==counts.argmax()
    ys,xs=np.where(line)
    box=(int(xs.min()),int(ys.min()),int(xs.max()+1),int(ys.max()+1))
    filled=ndi.binary_fill_holes(ndi.binary_closing(line,iterations=1))
    filled=filled[box[1]:box[3],box[0]:box[2]]
    if filled.sum()<filled.size*.25:
        raise ValueError('Reference outline failed to close; no fabricated fill used')
    if flip_vertical:
        filled=filled[::-1]
    resized=np.asarray(Image.fromarray(filled).resize((shape[1],shape[0]),Image.Resampling.NEAREST),dtype=bool)
    return resized,dict(crop_xyxy=list(crop),stroke_bounds_pixels=[box[0]+x0,box[1]+y0,box[2]+x0,box[3]+y0],
                        normalized_to_nominal_bbox=True,source_stroke_pixels=int(line.sum()),
                        source_filled_pixels=int(filled.sum()),stroke_uncertainty_px=3)


def project_triangles(meshes,axes,limits,shape):
    im=Image.new('1',(shape[1],shape[0]),0)
    draw=ImageDraw.Draw(im)
    low=np.array([v[0] for v in limits],float)
    span=np.array([v[1]-v[0] for v in limits],float)
    scale=np.array([shape[1]-1,shape[0]-1],float)/span
    for mesh in meshes:
        points=(np.asarray(mesh.vertices)[:,axes]-low)*scale
        faces=np.asarray(mesh.faces)
        for f in faces:
            q=points[f]
            a,b=q[1]-q[0],q[2]-q[0]
            if abs(a[0]*b[1]-a[1]*b[0])<.01:
                continue
            draw.polygon([tuple(x) for x in q],fill=1)
    # Compare outer silhouettes, not internal hole typography. The raw mask is
    # retained separately so open-bottom omissions are measured as such.
    return ndi.binary_fill_holes(np.asarray(im,dtype=bool))


def metrics(cad,reference,limits):
    sampling=((limits[1][1]-limits[1][0])/(cad.shape[0]-1),
              (limits[0][1]-limits[0][0])/(cad.shape[1]-1))
    cedge=cad&~ndi.binary_erosion(cad)
    redge=reference&~ndi.binary_erosion(reference)
    d_to_r=ndi.distance_transform_edt(~redge,sampling=sampling)[cedge]
    d_to_c=ndi.distance_transform_edt(~cedge,sampling=sampling)[redge]
    dist=np.concatenate((d_to_r,d_to_c))
    return dict(iou=float(np.logical_and(cad,reference).sum()/np.logical_or(cad,reference).sum()),
                symmetric_boundary_mean_mm=float(np.mean(dist)),
                symmetric_boundary_p95_mm=float(np.percentile(dist,95)),
                symmetric_boundary_max_mm=float(np.max(dist)),
                reference_area_mm2=float(reference.sum()*sampling[0]*sampling[1]),
                cad_area_mm2=float(cad.sum()*sampling[0]*sampling[1]),
                raster_pixel_mm=list(sampling))


def upper_envelope(cad,reference,length,height):
    cy=np.where(cad.any(axis=0),cad.shape[0]-1-np.argmax(cad[::-1],axis=0),np.nan)
    ry=np.where(reference.any(axis=0),reference.shape[0]-1-np.argmax(reference[::-1],axis=0),np.nan)
    cy*=height/(cad.shape[0]-1);ry*=height/(reference.shape[0]-1)
    valid=np.isfinite(cy)&np.isfinite(ry)
    differences=np.abs(cy[valid]-ry[valid])
    samples=[]
    for y in np.arange(0.,length+.001,2.):
        i=min(cad.shape[1]-1,round(y/length*(cad.shape[1]-1)))
        if valid[i]:
            samples.append(dict(y_mm=float(y),cad_z_mm=float(cy[i]),
                                graphic_z_mm=float(ry[i]),signed_difference_mm=float(cy[i]-ry[i])))
    return dict(mean_absolute_vertical_difference_mm=float(np.mean(differences)),
                p95_absolute_vertical_difference_mm=float(np.percentile(differences,95)),
                max_absolute_vertical_difference_mm=float(np.max(differences)),
                note='Upper projection includes wheel and key profiles. A vertical graphic difference is not a 3D surface error.',
                samples_2mm=samples)


def load_meshes(mode,p):
    inputs=[]
    if mode=='assembly':
        meshes=[]
        for name in PARTS:
            path=ROOT/'exports/rebuild_r1/assembly'/f'{name}.stl'
            if not path.exists():
                raise FileNotFoundError(f'Final assembly part absent: {path}')
            mesh=trimesh.load_mesh(path,process=False)
            if not isinstance(mesh,trimesh.Trimesh):
                raise ValueError(f'Expected one triangle mesh: {path}')
            meshes.append(mesh);inputs.append(fingerprint(path))
        return meshes,inputs
    from surfaces import make_surfaces
    shape,_,meta=make_surfaces(p)
    vertices,faces=shape.tessellate(.065,angularTolerance=.14)
    mesh=trimesh.Trimesh(vertices=np.array([v.toTuple() for v in vertices]),faces=faces,process=False)
    return [mesh],[fingerprint(HERE/'surfaces.py'),dict(surface_metadata=meta)]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode',choices=('surface','assembly'),default='assembly')
    parser.add_argument('--reference',type=Path,default=DEFAULT_REF)
    args=parser.parse_args()
    try:ctypes.windll.kernel32.SetPriorityClass(ctypes.c_void_p(-1),0x4000)
    except Exception:pass
    p=json.loads((HERE/'parameters.json').read_text(encoding='utf-8-sig'))
    scale=float(p['host']['scale'])
    length=float(p['host']['length'])*scale
    width=float(p['host']['width'])*scale
    height=float(p['host']['height'])*scale
    meshes,inputs=load_meshes(args.mode,p)
    lo=np.min([m.bounds[0] for m in meshes],axis=0)
    hi=np.max([m.bounds[1] for m in meshes],axis=0)
    nominal_low=np.array([-width/2.,0.,0.])
    nominal_high=np.array([width/2.,length,height])
    outside=np.maximum(nominal_low-lo,hi-nominal_high)
    if np.max(outside)>.15:
        raise ValueError(f'CAD exceeds nominal comparison canvas; cannot silently clip it: min={lo}, max={hi}, excess={outside}')
    px=12
    top_limits=((-width/2,width/2),(0,length))
    side_limits=((0,length),(0,height))
    top_shape=(round(length*px)+1,round(width*px)+1)
    side_shape=(round(height*px)+1,round(length*px)+1)
    top_ref,top_evidence=extract_reference(args.reference,(280,420,640,900),top_shape)
    side_ref,side_evidence=extract_reference(args.reference,(640,700,1120,900),side_shape,True)
    top=project_triangles(meshes,(0,1),top_limits,top_shape)
    side=project_triangles(meshes,(1,2),side_limits,side_shape)
    result=dict(mode=args.mode,status='2D reference comparison; not factory CAD or physical fit verification',
                source_product_url=SOURCE_URL,source_image_url=IMAGE_URL,
                source_image=fingerprint(args.reference),inputs=inputs,
                cad_assembly_bounds_mm=[lo.tolist(),hi.tolist()],
                parameters=fingerprint(HERE/'parameters.json'),
                normalization='Reference top and side strokes individually aligned by their outer bounding boxes to the nominal host dimensions. No non-rigid fitting and no best-fit optimisation.',
                limitations=[
                    'Official product text says 61.2 mm width; its EloShapes picture says 60.2 mm. Normalisation uses the text nominal width and hides that aspect-ratio discrepancy, which must remain disclosed.',
                    'The reference is a 2D graphic posted by the manufacturer, not calibrated factory CAD or a 3D scan. Raster stroke thickness, image version and view alignment limit interpretation.',
                    'The graphic includes wheel and original bottom edge; the new design intentionally substitutes MiniSE keys, generic wheel hardware, and an open five-foot bottom. Side silhouette differences include these design choices.',
                    'IoU is overlap of projected outline masks and is not a requirement-compliance percentage, structural score, or 3D surface tolerance.',
                    'Only the generated model and extracted outline strokes are plotted; the original manufacturer image is not republished.',
                ],
                nominal_dimensions_mm=dict(length=length,width=width,height=height),
                top=dict(metrics=metrics(top,top_ref,top_limits),image_evidence=top_evidence),
                side=dict(metrics=metrics(side,side_ref,side_limits),image_evidence=side_evidence))
    result['side_upper_envelope']=upper_envelope(side,side_ref,length,height)
    # Also quantify the crown region apart from intentionally absent low floor.
    upper_start=int(np.ceil(float(p['host']['base_open_band'])/height*(side_shape[0]-1)))
    upper_side=side.copy();upper_ref=side_ref.copy()
    upper_side[:upper_start]=False;upper_ref[:upper_start]=False
    result['side_above_open_band']=metrics(upper_side,upper_ref,side_limits)
    result['reference_stroke_uncertainty_approx_mm']=dict(
        top=max(width/(top_evidence['stroke_bounds_pixels'][2]-top_evidence['stroke_bounds_pixels'][0]),
                length/(top_evidence['stroke_bounds_pixels'][3]-top_evidence['stroke_bounds_pixels'][1]))*3,
        side=max(length/(side_evidence['stroke_bounds_pixels'][2]-side_evidence['stroke_bounds_pixels'][0]),
                 height/(side_evidence['stroke_bounds_pixels'][3]-side_evidence['stroke_bounds_pixels'][1]))*3)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,(ax,ay)=plt.subplots(1,2,figsize=(12.8,7.2),gridspec_kw={'width_ratios':[.9,1.25]})
    for axis,mask,ref,limits in ((ax,top,top_ref,top_limits),(ay,side,side_ref,side_limits)):
        xx=np.linspace(*limits[0],mask.shape[1]);yy=np.linspace(*limits[1],mask.shape[0])
        axis.contour(xx,yy,ref.astype(float),levels=[.5],colors=['#89929c'],linewidths=1.5,linestyles='dashed')
        axis.contour(xx,yy,mask.astype(float),levels=[.5],colors=['#117e89'],linewidths=1.6)
        axis.set_aspect('equal');axis.grid(alpha=.15)
        axis.spines[['right','top']].set_visible(False)
    ax.set_ylim(length+2,-2);ax.set_xlim(-width/2-2,width/2+2)
    ax.set_xlabel('X / mm');ax.set_ylabel('Y from front / mm')
    ax.set_title('Top outline')
    ay.set_xlim(-2,length+2);ay.set_ylim(-2,height+3)
    ay.set_xlabel('Y from front / mm');ay.set_ylabel('Z / mm')
    ay.axhline(float(p['host']['base_open_band']),color='#d39544',ls=':',lw=1)
    ay.set_title('Left projection / open bottom intentional')
    from matplotlib.lines import Line2D
    fig.legend([Line2D([0],[0],color='#117e89',lw=1.6),Line2D([0],[0],color='#89929c',ls='--',lw=1.5)],
               [f'Generated R1 {args.mode}','Official graphic outline, bbox-normalised'],loc='lower center',ncol=2,bbox_to_anchor=(.5,.16),frameon=False)
    t=result['top']['metrics'];s=result['side']['metrics']
    fig.suptitle(f'Fenrir Pro reference comparison — {args.mode.upper()}\n2D graphic agreement only; no factory CAD or scan incorporated',fontsize=13)
    fig.text(.08,.10,f"Top IoU {t['iou']:.3f}  |  mean boundary {t['symmetric_boundary_mean_mm']:.2f} mm\n"
                      f"Side IoU {s['iou']:.3f}  |  mean boundary {s['symmetric_boundary_mean_mm']:.2f} mm",fontsize=10)
    fig.text(.56,.10,'Reference stroke uncertainty about 0.6 mm.\nOfficial width conflict: text 61.2 mm / graphic 60.2 mm.\nIoU is not a compliance or structural score.',fontsize=9,color='#525c67')
    fig.subplots_adjust(top=.83,bottom=.27,wspace=.30)
    views=ROOT/'views/rebuild_r1';reports=ROOT/'reports/rebuild_r1'
    views.mkdir(parents=True,exist_ok=True);reports.mkdir(parents=True,exist_ok=True)
    suffix='_surface_draft' if args.mode=='surface' else ''
    image_path=views/f'reference_silhouette_comparison{suffix}.png'
    report_path=reports/f'silhouette_comparison{suffix}.json'
    fig.savefig(image_path,dpi=170,facecolor='white');plt.close(fig)
    result['generated_preview']=image_path.name
    report_path.write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print(json.dumps(dict(mode=args.mode,top=t,side=s,report=str(report_path),preview=str(image_path)),indent=2))


if __name__=='__main__':main()

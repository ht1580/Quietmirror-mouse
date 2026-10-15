"""Actual STL orthographic views via headless CPU Mesa, with depth buffering."""
from pathlib import Path
import os,ctypes,json,hashlib
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'views/v09'
ctypes.windll.kernel32.SetErrorMode(3)
ctypes.windll.kernel32.SetPriorityClass(ctypes.c_void_p(-1),0x4000)
MESA=ROOT.parent/'_support/tools/PrusaSlicer/PrusaSlicer-2.9.6/mesa'
os.environ['LIBGL_ALWAYS_SOFTWARE']='1';os.environ['GALLIUM_DRIVER']='llvmpipe';os.environ['LP_NUM_THREADS']='2'
_DLL_SEARCH=os.add_dll_directory(str(MESA));_MESA_GL=ctypes.WinDLL(str(MESA/'opengl32.dll'))
import render_views as r
from PIL import Image,ImageDraw,ImageFont
import trimesh
r.OUT=OUT

def paths(version):
    data=json.loads((ROOT/f'reports/{version}/cad_metrics.json').read_text(encoding='utf8'))
    return [(ROOT/part['file'],part['color'],1) for part in data['parts']]

def main():
    OUT.mkdir(parents=True,exist_ok=True);parts=paths('v09')
    for name,camera,up,scale,title in [
        ('01_isometric.png',(-140,160,140),(0,0,1),49,'薄上键与固定封口 · 收窄后背 · 三角骨架'),
        ('02_top.png',(0,-44,220),(0,1,0),53,'俯视：前端肩翼收回，23 × 27 mm 双键'),
        ('03_left_side.png',(-220,-44,14),(0,0,1),40,'左侧：共享曲面前键，冠高约 26 mm'),
        ('04_bottom.png',(0,-44,-220),(0,1,0),53,'底视：三角减重、五脚与功能接口'),
        ('05_right_side.png',(220,-44,14),(0,0,1),40,'右侧：连续顺滑后背'),
        ('06_front.png',(0,220,7),(0,0,1),27,'前视：薄上键、固定封口与 USB')]:
        r.render(name,parts,camera,up=up,scale=scale,title='V0.9 / '+title,subtitle='90 mm 长 · 后缘收窄、前段保持 · 1.6 mm 薄上键 · 1.8 mm 三角筋',version='V0.9',footer='实际 STL 网格 · CPU Mesa 离屏渲染 · 机械样机待实物试印')
        print('Render',name,flush=True)
    old=paths('v08')
    r.render('before_top.png',old,(0,-44,220),up=(0,1,0),scale=53,title='V0.8 / 修改前',subtitle='同一相机尺度的真实 STL',version='V0.8')
    r.render('before_side.png',old,(-220,-44,14),scale=40,title='V0.8 / 修改前',subtitle='同一相机尺度的真实 STL',version='V0.8')
    canvas=Image.new('RGB',(1800,1440),'#f5f8fa')
    for i,name in enumerate(('before_top.png','02_top.png','before_side.png','03_left_side.png')):
        im=Image.open(OUT/name);im.thumbnail((900,720));canvas.paste(im,((i%2)*900,(i//2)*720))
    canvas.save(OUT/'07_before_after.png')
    # Actual separated meshes explain the moving roof/fixed-skirt boundary.
    cache=ROOT.parent/'_support/work/v09_preview';cache.mkdir(parents=True,exist_ok=True)
    exploded=[(ROOT/'exports/v09/placed/BODY.stl',(.37,.53,.57),1)]
    shifts={}
    for name,sign in [('left_KEY',-1),('right_KEY',1)]:
        delta=[8.*sign,4.,14.];shifts[name]=delta
        mesh=trimesh.load_mesh(ROOT/'exports/v09/placed'/f'{name}.stl');mesh.apply_translation(delta)
        path=cache/f'{name}_exploded.stl';mesh.export(path);exploded.append((path,(.95,.64,.21),1))
    r.render('08_front_roof_exploded.png',exploded,(-140,180,130),focus=(0,-40,18),scale=55,
        title='V0.9 / 主键分件：橙色活动薄上键，蓝色固定壳体',
        subtitle='实际 BODY + 左右 KEY 网格分解；下裙、前脸与 USB 支撑留在 BODY',version='V0.9',
        footer='分件示意 · 两主键向外/前/上平移 · 其余机构省略 · 非打印排版')
    (ROOT/'reports/v09/rendering.json').write_text(json.dumps(dict(engine='VTK with verified Mesa llvmpipe software OpenGL3.3',offscreen=True,depth_buffered=True,source='Delivered printable STL parts, same camera scales before/after',source_metrics_sha256=hashlib.sha256((ROOT/'reports/v09/cad_metrics.json').read_bytes()).hexdigest(),exploded_key_translations_xyz_mm=shifts,outputs=[p.name for p in OUT.glob('*.png')]),indent=2),encoding='utf8')

if __name__=='__main__':main()

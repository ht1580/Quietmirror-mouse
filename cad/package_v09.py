"""Package only verified V0.9 deliverables into the E: project output folder."""
from pathlib import Path
import hashlib,json,shutil,subprocess,sys,zipfile
import xml.etree.ElementTree as ET
import trimesh
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'exports/v09';RP=ROOT/'reports/v09'
DELIVERY=ROOT.parent/'_support/outputs/Quietmirror_V0.9_PLA'
BASE='c200308ceafff8805ebec9744344d4626b925dfa'

def main():
    metrics=json.loads((RP/'cad_metrics.json').read_text(encoding='utf8'))
    validation=json.loads((RP/'validation.json').read_text(encoding='utf8'))
    native=json.loads((RP/'freecad_validation.json').read_text(encoding='utf8'))
    design=json.loads((RP/'design_checks.json').read_text(encoding='utf8'))
    slicing=json.loads((RP/'slice_summary.json').read_text(encoding='utf8'))
    rendering=json.loads((RP/'rendering.json').read_text(encoding='utf8'))
    assert validation['phase']=='all' and validation['pass_check'],validation.get('failures')
    assert native['passed'] and design['pass_check']
    assert native['source_metrics_sha256']==hashlib.sha256((RP/'cad_metrics.json').read_bytes()).hexdigest(), 'Stale FreeCAD source metrics'
    assert native['document_sha256']==hashlib.sha256((OUT/'quietmirror_V0.9.FCStd').read_bytes()).hexdigest(), 'FreeCAD document changed after verification'
    assert all(slicing['embedded_profile_checks'].values())
    for item in validation['artifact_inputs']:
        for kind in ('step','stl'):
            stat=(OUT/'placed'/(item['name']+'.'+kind)).stat()
            assert stat.st_size==item[kind+'_size_bytes'] and stat.st_mtime_ns==item[kind+'_mtime_ns'], 'Stale mechanism verification'
    assert validation['parameter_sha256']==hashlib.sha256(json.dumps(metrics['parameters'],sort_keys=True).encode()).hexdigest()
    assert slicing['source_metrics_sha256']==hashlib.sha256((RP/'cad_metrics.json').read_bytes()).hexdigest()
    assert design['source_metrics_sha256']==hashlib.sha256((RP/'cad_metrics.json').read_bytes()).hexdigest()
    assert rendering['source_metrics_sha256']==hashlib.sha256((RP/'cad_metrics.json').read_bytes()).hexdigest()
    assert all((ROOT/'views/v09'/name).is_file() for name in rendering['outputs'])
    subprocess.run([sys.executable,str(ROOT/'cad/check_v09_acceptance.py'),'-v'],check=True)
    subprocess.run([sys.executable,str(ROOT/'cad/check_v09_front_closure.py'),'-v'],check=True)
    subprocess.run([sys.executable,str(ROOT/'cad/check_v09_overlap.py'),'-v'],check=True)
    mesh_checks=[]
    for path in sorted((OUT/'print').glob('*.stl'))+sorted((OUT/'calibration').glob('*.stl')):
        mesh=trimesh.load_mesh(path)
        check=dict(file=path.relative_to(ROOT).as_posix(),watertight=bool(mesh.is_watertight),winding_consistent=bool(mesh.is_winding_consistent),components=len(mesh.split(only_watertight=False)),bottom_z_mm=float(mesh.bounds[0,2]))
        assert check['watertight'] and check['winding_consistent'] and check['components']==1,check
        assert abs(check['bottom_z_mm'])<.001,check
        mesh_checks.append(check)
    assert len(list((OUT/'print').glob('*.stl')))==20
    plate=OUT/'quietmirror_V0.9_PRINT_PLATE.3mf';ns={'m':'http://schemas.microsoft.com/3dmanufacturing/core/2015/02'}
    with zipfile.ZipFile(plate) as archive:
        root=ET.fromstring(archive.read('3D/3dmodel.model'))
        assert root.get('unit','millimeter')=='millimeter'
        assert len(root.findall('m:build/m:item',ns))==20
        assert 'Metadata/Slic3r_PE.config' in archive.namelist()
    layout=json.loads((RP/'vent_layout.json').read_text(encoding='utf8'))
    roof_count=len(layout['roof']['holes']);base_count=len(layout['base']['holes'])
    body=metrics['parts'][0]['dimensions_xyz_mm'];mass=slicing['plate_estimate']
    volume=sum(p['volume_mm3'] for p in metrics['parts'])/1000
    readme=f'''# Quietmirror V0.9 · PLA 打印包

本轮保持原前段轮廓、纵向角度与 23 × 27 mm 左右键接触面，按最新标注收窄后肩；实际主体 X×Y×Z 约 {body[0]:.3f} × {body[1]:.3f} × {body[2]:.3f} mm。

## 修改

- 左右键由母壳外表面向内法向增厚 1.6 mm，只让薄上键活动；下方侧裙、封闭前脸及充电口支撑归固定 BODY，纵向角度保持。
- 收回前端两侧肩翼；后肩收窄，后背连续平滑；后部边界三角再剖分使减重孔靠近约 2 mm 外缘筋。
- 冠高约 28 → 26 mm；普通壳壁名义 1.8 → 1.6 mm；平面筋目标 2.2 → 1.8 mm。
- 上壳 {roof_count}、底架 {base_count} 个圆角三角减重轮廓；滚轮、传感器、开关、螺钉等功能接口保留工作所需形状。孔轮廓数与最终独立开口数的核验见 reports/design_checks.json。
- 保留五脚位置、传感器接口、五键可拆机械试按机构及可旋转/下压滚轮；V0.1–V0.8 未改动。

## 使用哪些文件

- `quietmirror_V0.9_PRINT_PLATE.3mf`：20 件分开排版，内含通用 PLA 切片设置。
- `print/`：20 个按打印朝向放置的 STL 和 STEP，底部为 Z=0。
- `calibration/`：先打印配合间隙、柱塞和轮轴校准件。
- `quietmirror_V0.9.FCStd`：FreeCAD 原生文档，20 个命名 B-rep 零件和参数记录；不是自动恢复的 CadQuery 历史树或已求解装配关节。
- `quietmirror_V0.9_MECHANICAL_ASSEMBLY.step`：装配观察 STEP，含 5 枚非打印开关示例，不能整块直接打印。
- `quietmirror_V0.9_VIEW_ONLY.3mf`：装配观察 3MF，不能替代分件打印排版。
- `source/`：本轮及依赖的参数化生成/验证源代码。完整工作仓库仍在 E:\\Projects\\Quietmirror\\github。
- `views/07_before_after.png`：从真实 STL 渲染的修改前后对照。
- reports/HANDOFF.md：最新要求、当前进度、结构决策和继续修改命令；reports/TASK_STATUS.json 提供机器可读进度。

## PLA 设置与实际切片

假设 0.4 mm 喷嘴、1.75 mm PLA、0.2 mm 层高、4 壁、20% gyroid、210°C/60°C、可清理支撑；配置随 3MF 保存。请在切片器选择自己的打印机和实际 PLA 参数后重切；包中不提供可直接发送未知打印机的 G-code。

本版 20 个塑料件 CAD 体积约 {volume:.3f} cm³。通用配置实际切片估算：模型 {mass['model_g']:.2f} g，支撑 {mass['support_g']:.2f} g，合计 {mass['total_g']:.2f} g，时间 {mass['time']}。这不是你的打印机的保证工时。

BODY 五脚朝下；键面朝上；滚轮侧面平放、轴孔朝上；小零件按 print/ 朝向。先试印校准件，再检查 0.3 mm 名义导向间隙和 Ø3 mm 轴的配合。

## 验证边界

保存的 CAD/STL、机构静态与采样行程、轮旋转包络、安装路径、足底共面、三角孔、母壳键面与通用 PLA 切片已经计算核验，完整证据在 reports/。尚未实物打印、试握、测力或验证疲劳寿命。0.8 mm PLA 段落弹片为试验件，需实物调整；五个真实开关、螺钉和脚贴另备。原项目电子功能仍未实现/实测。

## E 盘工具

FreeCAD: E:\\Projects\\Quietmirror\\_support\\tools\\FreeCAD\\bin\\FreeCAD.exe

环境入口: E:\\Projects\\Quietmirror\\_support\\enter-project.ps1

后续支持、依赖、缓存和拓展继续保存在 E 盘项目目录。
'''
    (RP/'PRINT_README.md').write_text(readme,encoding='utf8')
    from handoff_v09 import write_handoff
    write_handoff(metrics,validation,native,design,slicing)
    archive_readme=ROOT/'README_V0.8.md'
    if not archive_readme.exists():shutil.copy2(ROOT/'README.md',archive_readme)
    project_readme=f'''# Quietmirror · V0.9 PLA 三角骨架机械样机

前端为沿原曲面的1.6mm薄上键，下方固定侧裙、封闭前脸和USB支撑保留；前段和23×27mm键面保持，后肩收窄平滑。当前主体平面约{body[0]:.2f}×{body[1]:.2f}mm，冠高约26mm。普通壳壁名义1.6mm，平面三角筋1.8mm。上壳{roof_count}、底架{base_count}个圆角三角减重轮廓，功能接口保留所需形状。

![实际模型](views/v09/01_isometric.png)

[修改前后](views/v09/07_before_after.png) · [俯视](views/v09/02_top.png) · [侧视](views/v09/03_left_side.png) · [底视](views/v09/04_bottom.png)

## 打印和编辑

- [完整打印包 ZIP 与发布记录](https://github.com/ht1580/Quietmirror-mouse/releases/tag/v0.9-pla)
- [20件PLA打印排版3MF](exports/v09/quietmirror_V0.9_PRINT_PLATE.3mf) · [分件STL/STEP](exports/v09/print/) · [配合校准件](exports/v09/calibration/)
- [FreeCAD原生文档](exports/v09/quietmirror_V0.9.FCStd) · [装配STEP](exports/v09/quietmirror_V0.9_MECHANICAL_ASSEMBLY.step) · [装配观察3MF](exports/v09/quietmirror_V0.9_VIEW_ONLY.3mf)
- [打印说明](reports/v09/PRINT_README.md) · [装配及限制](reports/v09/ASSEMBLY.md) · [交接报告与当前进度](reports/v09/HANDOFF.md)

打印使用PRINT_PLATE或print/，装配文件不能作为整块打印模型。通用0.4mm喷嘴/0.2mm层PLA实际切片估算{mass['total_g']:.2f}g、{mass['time']}；必须选择自己的打印机配置重切。尚未实物试印、测力或疲劳验证。

## 已保存证据

[几何与孔型](reports/v09/design_checks.json) · [20件拓扑、静态、采样行程和装入路径](reports/v09/validation.json) · [FreeCAD保存重开](reports/v09/freecad_validation.json) · [实际PLA切片](reports/v09/slice_summary.json)

最终零件均为有效单实体、封闭且无网格自相交；五个活动组采样行程/装入路径、滚轮旋转包络和五脚共面通过。独立检查匹配{base_count}个底孔实际截面，验证{roof_count}个顶孔开口和孔缘，主键198点贴合母曲面、后背177点连续下降。采样结果不等于全局强度或连续运动证明。

## 源码与E盘环境

[参数](cad/parameters_v09.json) · [生成器](cad/build_v09.py) · [曲面与骨架](cad/geometry_v09.py) · [滚轮机构](cad/mechanisms_v09.py) · [官方参考记录](references/V0.9_REFERENCE_NOTES.md)

E盘环境入口：`E:\\Projects\\Quietmirror\\_support\\enter-project.ps1`。所有新增依赖、缓存、工具和拓展继续留在E盘。FreeCAD文件包含命名B-rep及参数记录，不伪称已恢复CadQuery历史树或求解装配关节。

[上一版首页](README_V0.8.md) · [历史](HISTORY.md) · [许可证](LICENSE) · [署名](NOTICE.md)。V0.1–V0.8的模型与代码保留。
'''
    (ROOT/'README.md').write_text(project_readme,encoding='utf8')
    history=ROOT/'HISTORY.md';history_text=history.read_text(encoding='utf8')
    if '## V0.9' not in history_text:
        history.write_text(history_text+'\n\n## V0.9 · PLA 三角骨架与光顺前端\n\n保留原前段、纵坡与23×27主键，后肩按最新反馈收窄；26mm冠、1.6mm薄上键、1.8mm三角筋。固定下裙、前脸封口及USB支撑，后部边界适配三角减重，实际孔数见本轮报告，功能开口例外。外部侧键带下降2.8mm，后侧内部机构另降0.8mm，滚轮轴14.3mm、1.3mm轴承耳径向壁和2.4mm转折支架。导出20件STL/STEP、FreeCAD和PLA3MF；保存几何、网格、机构及切片证据，未实物打印。旧版不覆盖。\n',encoding='utf8')
    changed=subprocess.check_output(['git','-C',str(ROOT),'diff','--name-only','--diff-filter=MDRCT',BASE],text=True).splitlines()
    assert set(changed)<={'README.md','HISTORY.md'},('Historical tracked files changed',changed)
    readme_blob=subprocess.check_output(['git','-C',str(ROOT),'rev-parse',BASE+':README.md'],text=True).strip()
    archived_blob=subprocess.check_output(['git','-C',str(ROOT),'hash-object','--path=README.md',str(ROOT/'README_V0.8.md')],text=True).strip()
    assert readme_blob==archived_blob,'V0.8 README archive changed'
    history_report=dict(pass_check=True,base_commit=subprocess.check_output(['git','-C',str(ROOT),'rev-parse',BASE],text=True).strip(),modified_historical_files=changed,scope='Only current README and appended HISTORY may differ; every historically tracked CAD/model/view/report/config file is unchanged.',archived_readme_blob=archived_blob)
    (RP/'history_preservation.json').write_text(json.dumps(history_report,indent=2),encoding='utf8')
    DELIVERY.mkdir(parents=True,exist_ok=True)
    for folder in ('print','calibration'):
        shutil.copytree(OUT/folder,DELIVERY/folder,dirs_exist_ok=True)
    for name in ('quietmirror_V0.9_PRINT_PLATE.3mf','quietmirror_V0.9_VIEW_ONLY.3mf','quietmirror_V0.9_MECHANICAL_ASSEMBLY.step','quietmirror_V0.9.FCStd'):
        shutil.copy2(OUT/name,DELIVERY/name)
    shutil.copytree(RP,DELIVERY/'reports',dirs_exist_ok=True)
    packaged_handoff=DELIVERY/'reports/HANDOFF.md'
    packaged_handoff.write_text(packaged_handoff.read_text(encoding='utf8').replace('../../cad/','../source/').replace('../../exports/v09/','../').replace('../../views/v09/','../views/'),encoding='utf8')
    shutil.copytree(ROOT/'views/v09',DELIVERY/'views',dirs_exist_ok=True)
    (DELIVERY/'source').mkdir(exist_ok=True)
    for src in (ROOT/'cad').iterdir():
        if src.is_file() and src.suffix.lower() in ('.py','.json','.md','.fcmacro'):shutil.copy2(src,DELIVERY/'source'/src.name)
    for src in (ROOT/'slicing').glob('V0.9*.ini'):shutil.copy2(src,DELIVERY/src.name)
    shutil.copytree(ROOT/'references/v09_user_revision',DELIVERY/'references/v09_user_revision',dirs_exist_ok=True)
    shutil.copytree(ROOT/'environment/v09',DELIVERY/'environment',dirs_exist_ok=True)
    shutil.copy2(ROOT/'references/V0.9_REFERENCE_NOTES.md',DELIVERY/'references/V0.9_REFERENCE_NOTES.md')
    for name in ('LICENSE','NOTICE.md','requirements.txt'):shutil.copy2(ROOT/name,DELIVERY/name)
    shutil.copy2(RP/'PRINT_README.md',DELIVERY/'README_先读我.md')
    shutil.copy2(ROOT.parent/'_support/work/environment_status.md',DELIVERY/'reports/environment_status.md')
    package_checks=dict(version='0.9',all_required_checks_pass=True,print_parts=20,meshes=mesh_checks,print_3mf_units='millimeter',print_3mf_objects=20,embedded_profile_verified=True,delivery=str(DELIVERY))
    (RP/'package_checks.json').write_text(json.dumps(package_checks,indent=2),encoding='utf8')
    shutil.copy2(RP/'package_checks.json',DELIVERY/'reports/package_checks.json')
    manifest=[]
    for path in sorted(DELIVERY.rglob('*')):
        if path.is_file() and path.name!='SHA256SUMS.json':manifest.append(dict(file=path.relative_to(DELIVERY).as_posix(),bytes=path.stat().st_size,sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
    (DELIVERY/'SHA256SUMS.json').write_text(json.dumps(manifest,indent=2),encoding='utf8')
    zip_path=DELIVERY.parent/'Quietmirror_V0.9_PLA_Print_Pack.zip'
    with zipfile.ZipFile(zip_path,'w',zipfile.ZIP_DEFLATED,compresslevel=5) as archive:
        for path in sorted(DELIVERY.rglob('*')):
            if path.is_file():archive.write(path,path.relative_to(DELIVERY.parent))
    with zipfile.ZipFile(zip_path) as archive:assert archive.testzip() is None
    print(json.dumps(dict(directory=str(DELIVERY),zip=str(zip_path),zip_bytes=zip_path.stat().st_size,sha256=hashlib.sha256(zip_path.read_bytes()).hexdigest()),indent=2),flush=True)

if __name__=='__main__':main()

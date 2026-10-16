"""Build/reopen a native FreeCAD B-rep assembly, with no GUI launch.

Run using the existing E-drive freecadcmd.exe. Parametric generator and JSON
are delivered separately: imported Part features do not recreate a sketch tree.
"""
from pathlib import Path
import hashlib, json, os, traceback
import FreeCAD as App
import Part

ROOT=Path(os.environ.get('QUIETMIRROR_ROOT',str(Path(__file__).resolve().parents[2])))
OUT=ROOT/'exports/rebuild_r1';RP=ROOT/'reports/rebuild_r1'


def main():
    metrics=json.loads((RP/'cad_metrics.json').read_text(encoding='utf-8'))
    doc=App.newDocument('Fenrir_MiniSE_R1')
    printed=doc.addObject('App::DocumentObjectGroup','PrintedParts');printed.Label='PLA printed parts / mm'
    hardware=doc.addObject('App::DocumentObjectGroup','HardwareReferences');hardware.Label='Purchased hardware references / NOT PRINTED'
    info=doc.addObject('App::FeaturePython','DesignInfo')
    for key,val in {
        'Version':'R1 — independent Fenrir-reference / MiniSE-priority rebuild',
        'Provenance':'Official dimensions / independent multiview reconstruction. No manufacturer CAD or restricted scan.',
        'BaseDimensions':'81.7 x 61.2 x 28.3 mm nominal; inspect reports for actual bounds.',
        'SourceParameters':'cad/rebuild_r1/parameters.json; rebuild using project E-drive Python.',
        'Editing':'Editable imported B-reps. Generator source is delivered; no solved Assembly joints or sketch feature history.',
        'FitBoundary':'Generic mechanical interface prototype; actual Fenrir PCB / optics / cables require measured fit.'
    }.items():
        info.addProperty('App::PropertyString',key,'R1');setattr(info,key,val)
    expected={}
    for name,metric in metrics.items():
        shape=Part.Shape();shape.read(str(OUT/f'assembly/{name}.step'))
        assert shape.isValid() and len(shape.Solids)==1,(name,'invalid imported STEP')
        obj=doc.addObject('Part::Feature',name);obj.Label=name;obj.Shape=shape
        obj.addProperty('App::PropertyBool','PrintInPLA','Manufacture');obj.PrintInPLA=metric['printable']
        obj.addProperty('App::PropertyString','SourceSTEP','Manufacture');obj.SourceSTEP=f'assembly/{name}.step'
        obj.addProperty('App::PropertyString','UnitSystem','Manufacture');obj.UnitSystem='mm'
        (printed if metric['printable'] else hardware).addObject(obj)
        expected[name]=shape.Volume
    doc.recompute();path=OUT/'FENRIR_MINISE_R1.FCStd';doc.saveAs(str(path));App.closeDocument(doc.Name)
    reopened=App.openDocument(str(path));checks=[]
    for name,volume in expected.items():
        obj=reopened.getObject(name);s=obj.Shape
        checks.append({'part':name,'valid':s.isValid(),'solids':len(s.Solids),
                       'saved_volume_mm3':s.Volume,'volume_difference_mm3':abs(s.Volume-volume),
                       'pass':s.isValid() and len(s.Solids)==1 and abs(s.Volume-volume)<1e-4})
    App.closeDocument(reopened.Name)
    report={'application':'FreeCAD '+'.'.join(App.Version()[:3]),'file':str(path.relative_to(ROOT)),
            'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'parts':checks,'pass':all(x['pass'] for x in checks),
            'scope':'Saved and reopened using native FreeCAD; imported B-reps, not sketch history or solved joints.'}
    (RP/'native_freecad_checks.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')
    assert report['pass'];print('R1 FreeCAD saved/reopened',len(checks),'valid single solids',flush=True)


try:main()
except Exception:
    (RP/'native_freecad_ERROR.txt').write_text(traceback.format_exc(),encoding='utf-8');raise

r"""Import V0.9 assembly STEP solids into a verified native FreeCAD document.

Run with FreeCADCmd.exe (no visible GUI):
  freecadcmd.exe --user-cfg E:\...\user.cfg --system-cfg E:\...\system.cfg \
    --log-file E:\...\freecad.log E:\...\cad\freecad_v09.py

The default project root is this file's parent directory. An optional --root path
may be passed through FreeCAD's --pass option, or QUIETMIRROR_ROOT may be set.
The shapes are editable imported B-reps. This script does not reconstruct the
CadQuery feature history or create solved assembly joints.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import sys
import traceback
import xml.etree.ElementTree as ET
import zipfile

import FreeCAD as App
import Part


def sha256(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def add_property(obj, kind, name, value, group='Design'):
    obj.addProperty(kind, name, group)
    setattr(obj, name, value)
    obj.setEditorMode(name, 1)


def group_for(name):
    if name == 'BODY':
        return 'Shell'
    if name in ('left_KEY', 'right_KEY'):
        return 'MainKeys'
    if name.startswith('thumb_') and name.endswith('_KEY'):
        return 'SideKeys'
    if name in ('WHEEL', 'AXLE', 'AXLE_WASHER', 'WHEEL_CARRIER', 'DETENT_LEAF'):
        return 'WheelAssembly'
    return 'SwitchMounts'


def attach_native_gui_metadata(path, part_names, group_names):
    """Use FreeCAD's own serialized materials in native GUI view-provider data.

    FreeCADCmd cannot instantiate ViewObjects. The application-level material
    properties serialize genuine versioned material side entries; GuiDocument
    references those same entries. No binary material data is hand-encoded.
    """
    with zipfile.ZipFile(path, 'r') as archive:
        members = {info.filename: (info, archive.read(info.filename))
                   for info in archive.infolist() if info.filename != 'GuiDocument.xml'}
    document = ET.fromstring(members['Document.xml'][1])
    object_data = {node.attrib['name']: node for node in document.findall('./ObjectData/Object')}
    gui = ET.Element('Document', SchemaVersion='1', HasExpansion='0')
    providers = ET.SubElement(gui, 'ViewProviderData', Count=str(len(part_names) + len(group_names)))
    material_bindings = {}
    for name in [*group_names, *part_names]:
        provider = ET.SubElement(providers, 'ViewProvider', name=name, expanded='1', treeRank='-1')
        props = ET.SubElement(provider, 'Properties', Count='0', TransientCount='0')
        visibility = ET.SubElement(props, 'Property', name='Visibility', type='App::PropertyBool', status='1')
        ET.SubElement(visibility, 'Bool', value='true')
        tree = ET.SubElement(props, 'Property', name='ShowInTree', type='App::PropertyBool', status='1')
        ET.SubElement(tree, 'Bool', value='true')
        if name in part_names:
            source_props = object_data[name].find('Properties')
            native_material = source_props.find("Property[@name='PreviewMaterials']")
            if native_material is None or native_material.find('MaterialList') is None:
                raise RuntimeError('FreeCAD did not serialize the native material for ' + name)
            appearance = ET.SubElement(props, 'Property', name='ShapeAppearance',
                                       type='App::PropertyMaterialList', status='1')
            carrier = copy.deepcopy(native_material.find('MaterialList'))
            if carrier.attrib['file'] not in members:
                raise RuntimeError('Missing native material side entry: ' + carrier.attrib['file'])
            appearance.append(carrier)
            color_prop = copy.deepcopy(source_props.find("Property[@name='PreviewColor']"))
            color_prop.attrib = {'name': 'ShapeColor', 'type': 'App::PropertyColor', 'status': '1'}
            props.append(color_prop)
            material_bindings[name] = carrier.attrib['file']
        props.set('Count', str(len(props)))
    ET.SubElement(gui, 'Camera', settings='')
    gui_bytes = ET.tostring(gui, encoding='utf-8', xml_declaration=True)
    temporary = path.with_name(path.name + '.writing')
    with zipfile.ZipFile(temporary, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for name, (info, payload) in members.items():
            archive.writestr(info, payload)
        archive.writestr('GuiDocument.xml', gui_bytes)
    os.replace(temporary, path)
    return material_bindings


def build(root):
    exports = root / 'exports' / 'v09'
    reports = root / 'reports' / 'v09'
    metrics_path = reports / 'cad_metrics.json'
    output = exports / 'quietmirror_V0.9.FCStd'
    report_path = reports / 'freecad_validation.json'
    metrics = json.loads(metrics_path.read_text(encoding='utf-8'))
    parts = [p for p in metrics['parts'] if int(p.get('print_quantity', 0)) > 0]
    names = [p['name'] for p in parts]
    if len(names) != 20 or len(set(names)) != 20:
        raise ValueError('Expected exactly 20 unique printable parts; got ' + str(names))
    if int(metrics.get('printable_parts', 20)) != 20:
        raise ValueError('Unexpected printable_parts count in cad_metrics.json')
    sources = {name: exports / 'placed' / (name + '.step') for name in names}
    for source in sources.values():
        if not source.is_file():
            raise FileNotFoundError(source)
    parameters = metrics['parameters']
    for key, expected in [('length', 90), ('max_width', 62), ('height', 26), ('wall', 1.6)]:
        if abs(float(parameters[key]) - expected) > 1e-6:
            raise ValueError('Unexpected V0.9 design parameter: ' + key)
    if abs(float(parameters['ventilation']['minimum_planar_web']) - 1.8) > 1e-6:
        raise ValueError('Unexpected V0.9 planar web parameter')
    for side in ('left_key', 'right_key'):
        if parameters[side]['width'] != 23 or parameters[side]['length'] != 27:
            raise ValueError('Unexpected key touch dimensions: ' + side)
    report = {
        'version': '0.9', 'freecad_version': list(App.Version()),
        'headless': not bool(App.GuiUp), 'gui_visual_tested': False,
        'document': str(output), 'source_metrics': str(metrics_path),
        'source_metrics_sha256': sha256(metrics_path),
        'limitations': [
            'Imported editable B-reps; CadQuery feature history is not reconstructed.',
            'Named groups preserve assembly positions; no solved joints or constraints.',
            'Colors are native serialized material metadata; GUI display was not opened.',
            'This validates saved document geometry and metadata, not physical print fit.'
        ]
    }
    doc = App.newDocument('Quietmirror_V09')
    doc.Label = 'Quietmirror V0.9 - PLA mechanical assembly'
    doc.Comment = 'Imported placed STEP solids. Modify source dimensions in cad/build_v09.py; no solved assembly joints.'
    top = doc.addObject('App::DocumentObjectGroup', 'PrintableParts')
    top.Label = 'Printable parts (20) - assembly positions'
    groups = {}
    for name, label in [('Shell', 'Body shell'), ('MainKeys', 'Front main keys'),
                        ('SideKeys', 'Left side keys'), ('WheelAssembly', 'Wheel mechanism'),
                        ('SwitchMounts', 'Mechanical test switch mounts')]:
        groups[name] = doc.addObject('App::DocumentObjectGroup', name)
        groups[name].Label = label
        top.addObject(groups[name])
    design = doc.addObject('App::DocumentObjectGroup', 'DesignParameters')
    design.Label = 'Source parameters and measured body dimensions'
    for name, value in [('NominalLength', 90), ('NominalWidth', 62), ('NominalHeight', 26),
                        ('OrdinaryWall', 1.6), ('MinimumPlanarWeb', 1.8),
                        ('MainKeyTouchWidth', 23), ('MainKeyTouchLength', 27)]:
        add_property(design, 'App::PropertyLength', name, value)
    body_dims = next(item['dimensions_xyz_mm'] for item in parts if item['name'] == 'BODY')
    for name, value in zip(('ActualBodyWidth', 'ActualBodyLength', 'ActualBodyHeight'), body_dims):
        add_property(design, 'App::PropertyLength', name, value)
    add_property(design, 'App::PropertyString', 'WidthReferenceNote',
                 'NominalWidth=62 is the original source-profile scale. The rear is narrowed; ActualBodyWidth is the exported width.')
    add_property(design, 'App::PropertyString', 'SourceGenerator', 'cad/build_v09.py')
    add_property(design, 'App::PropertyString', 'SourceParameters', 'cad/parameters_v09.json')
    add_property(design, 'App::PropertyString', 'SourceMetricsSHA256', report['source_metrics_sha256'])
    add_property(design, 'App::PropertyString', 'EditBoundary',
                 'Metadata only: regenerate source CAD to change the imported B-reps.')
    add_property(design, 'App::PropertyString', 'Orientation',
                 'X: lateral; front: Y=0; rear: negative Y; Z: up; units: mm.')
    before = {}
    for item in parts:
        name = item['name']
        shape = Part.Shape()
        shape.read(str(sources[name]))
        if shape.isNull() or not shape.isValid() or len(shape.Solids) != 1 or shape.Volume <= 0:
            raise ValueError('Invalid imported STEP solid: ' + name)
        obj = doc.addObject('Part::Feature', name)
        obj.Label = name
        obj.Shape = shape
        groups[group_for(name)].addObject(obj)
        add_property(obj, 'App::PropertyString', 'SourceSTEP', str(sources[name].relative_to(root)), 'Provenance')
        add_property(obj, 'App::PropertyString', 'SourceSHA256', sha256(sources[name]), 'Provenance')
        add_property(obj, 'App::PropertyString', 'MechanismRole', item.get('kind', 'printable'), 'Provenance')
        add_property(obj, 'App::PropertyInteger', 'PrintQuantity', int(item['print_quantity']), 'Provenance')
        color = tuple(float(c) for c in item.get('color', [0.65, 0.69, 0.73])[:3])
        add_property(obj, 'App::PropertyColor', 'PreviewColor', color, 'Display')
        material = App.Material()
        material.DiffuseColor = color
        add_property(obj, 'App::PropertyMaterialList', 'PreviewMaterials', [material], 'Display')
        before[name] = {'volume_mm3': shape.Volume, 'faces': len(shape.Faces),
                        'source_step_sha256': obj.SourceSHA256, 'preview_color': list(color)}
    doc.recompute()
    exports.mkdir(parents=True, exist_ok=True)
    doc.saveAs(str(output))
    App.closeDocument(doc.Name)
    group_names = ['PrintableParts', *groups, 'DesignParameters']
    report['native_gui_material_bindings'] = attach_native_gui_metadata(output, names, group_names)
    reopened = App.openDocument(str(output))
    checked = []
    for name in names:
        obj = reopened.getObject(name)
        if obj is None:
            raise ValueError('Saved document lost object: ' + name)
        shape = obj.Shape
        bounds = shape.BoundBox
        volume_difference = abs(shape.Volume - before[name]['volume_mm3'])
        valid = bool(shape.isValid()) and len(shape.Solids) == 1 and shape.Volume > 0
        color = [float(c) for c in obj.PreviewColor[:3]]
        metadata_valid = (obj.Label == name and obj.SourceSHA256 == before[name]['source_step_sha256']
                          and max(abs(a-b) for a,b in zip(color,before[name]['preview_color'])) < 0.005
                          and len(obj.PreviewMaterials) == 1)
        checked.append({'name': name, 'cad_valid': bool(shape.isValid()),
                        'solids': len(shape.Solids), 'faces': len(shape.Faces),
                        'volume_mm3': shape.Volume, 'roundtrip_volume_error_mm3': volume_difference,
                        'dimensions_xyz_mm': [bounds.XLength, bounds.YLength, bounds.ZLength],
                        'source_step_sha256': obj.SourceSHA256, 'preview_color': color,
                        'metadata_valid': metadata_valid,
                        'passed': valid and metadata_valid and volume_difference < 0.001})
    actual_shapes = [o for o in reopened.Objects if o.isDerivedFrom('Part::Feature') and not o.Shape.isNull()]
    saved_design = reopened.getObject('DesignParameters')
    report['parameter_metadata_valid'] = all(
        abs(float(getattr(saved_design, key).Value) - val) < 1e-6
        for key, val in [('NominalLength',90), ('NominalWidth',62), ('NominalHeight',26),
                         ('OrdinaryWall',1.6), ('MinimumPlanarWeb',1.8),
                         ('MainKeyTouchWidth',23), ('MainKeyTouchLength',27)])
    report['body_dimensions_xyz_mm'] = body_dims
    report['measured_dimensions_metadata_valid'] = all(
        abs(float(getattr(saved_design, key).Value) - value) < 1e-6
        for key, value in zip(('ActualBodyWidth', 'ActualBodyLength', 'ActualBodyHeight'), body_dims))
    report['printable_parts_expected'] = 20
    report['printable_parts_reopened'] = len(actual_shapes)
    report['reopened_part_feature_names'] = [o.Name for o in actual_shapes]
    report['source_script_sha256'] = sha256(Path(__file__))
    report['parts'] = checked
    report['all_parts_valid_single_solid'] = len(actual_shapes) == 20 and all(p['passed'] for p in checked)
    report['passed'] = report['all_parts_valid_single_solid'] and report['parameter_metadata_valid'] and report['measured_dimensions_metadata_valid']
    App.closeDocument(reopened.Name)
    report['document_sha256'] = sha256(output)
    report['document_bytes'] = output.stat().st_size
    reports.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    if not report['passed']:
        raise RuntimeError('FreeCAD saved-document validation failed; see ' + str(report_path))
    print('FREECAD_V09_VALIDATED', len(checked), str(output), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(os.environ.get('QUIETMIRROR_ROOT', Path(__file__).resolve().parents[1])))
    args, _ = parser.parse_known_args()
    build(args.root.resolve())


if __name__ in ('__main__', 'freecad_v09'):
    try:
        main()
    except Exception:
        traceback.print_exc()
        raise

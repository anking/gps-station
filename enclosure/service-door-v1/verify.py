"""Check assembly STEP round-trip and watertight print meshes after build.py."""
from pathlib import Path
import json, math
import cadquery as cq
import vtk

p=Path(__file__).resolve().parent/'output'
r=json.loads((p/'verification.json').read_text())
a=cq.importers.importStep(str(p/'gps_station_service_door_v1.step'))
assert len(a.solids().vals())==7
assert math.isclose(sum(s.Volume() for s in a.solids().vals()),
                    sum(v['volume_mm3'] for v in r['parts'].values()),rel_tol=1e-6)
r['assembly_step_round_trip']='PASS: 7 solids, total volume preserved'
r['stl_open_or_nonmanifold_edges']={}
for n in r['parts']:
    rd=vtk.vtkSTLReader();rd.SetFileName(str(p/(n+'.stl')));rd.Update()
    ed=vtk.vtkFeatureEdges();ed.SetInputConnection(rd.GetOutputPort())
    ed.BoundaryEdgesOn();ed.NonManifoldEdgesOn();ed.FeatureEdgesOff();ed.ManifoldEdgesOff();ed.Update()
    count=ed.GetOutput().GetNumberOfCells()
    r['stl_open_or_nonmanifold_edges'][n]=count
    assert count==0,(n,count)
(p/'verification.json').write_text(json.dumps(r,indent=2),encoding='utf-8')
print('PASS: seven assembly solids; seven closed print meshes')

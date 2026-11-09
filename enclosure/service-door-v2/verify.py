"""Check assembly STEP round-trip and watertight print meshes after build.py."""
from pathlib import Path
import json, math
import cadquery as cq
import vtk

p=Path(__file__).resolve().parent/'output'
r=json.loads((p/'verification.json').read_text())
a=cq.importers.importStep(str(p/'gps_station_service_door_v2.step'))
assert len(a.solids().vals())==7
assert math.isclose(sum(s.Volume() for s in a.solids().vals()),
                    sum(v['volume_mm3'] for v in r['parts'].values()),rel_tol=1e-6)
r['assembly_step_round_trip']='PASS: 7 solids, total volume preserved'
original=cq.importers.importStep(str(p.parent/'inputs/esp_cradle_user_original.step'))
exported=cq.importers.importStep(str(p/'esp_cradle.step'))
recovered=exported.translate((37,-42,-75)).rotate((0,0,0),(1,0,0),-90)
# Coincident curved faces can make OCCT Boolean subtraction unreliable after STEP
# round-trip. Compare restored vertices, topology, face areas and edge lengths.
ov=[v.Center() for v in original.val().Vertices()]
rv=[v.Center() for v in recovered.val().Vertices()]
assert len(ov)==len(rv)
vertex_error=max(min((a-b).Length for b in rv) for a in ov)
assert vertex_error<1e-6,vertex_error
for a,b in zip(sorted(f.Area() for f in original.val().Faces()),sorted(f.Area() for f in recovered.val().Faces())):
    assert math.isclose(a,b,abs_tol=1e-6,rel_tol=1e-7),(a,b)
oe=sorted(e.Length() for e in original.val().Edges())
re=sorted(e.Length() for e in recovered.val().Edges())
assert len(oe)==len(re)
assert all(math.isclose(a,b,abs_tol=1e-6,rel_tol=1e-7) for a,b in zip(oe,re))
r['user_cradle_after_inverse_transform']={'vertex_position_error_mm':vertex_error,
    'face_areas_and_edge_lengths':'PASS','topology':'PASS'}
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

"""Preview generated solid geometry; purchased hardware shown schematically."""
from pathlib import Path
import json
import vtk
import cadquery as cq

ROOT=Path(__file__).resolve().parent; OUT=ROOT/'output'
P=json.loads((ROOT/'parameters.json').read_text())
M=json.loads((OUT/'view_manifest.json').read_text())
window=vtk.vtkRenderWindow();window.SetOffScreenRendering(1);window.SetSize(2400,1200)
window.SetMultiSamples(8)

def mesh_actor(renderer,name,color):
    rd=vtk.vtkSTLReader();rd.SetFileName(str(OUT/f'_view_{name}.stl'));rd.Update()
    mapper=vtk.vtkPolyDataMapper();mapper.SetInputConnection(rd.GetOutputPort())
    a=vtk.vtkActor();a.SetMapper(mapper);a.GetProperty().SetColor(*color)
    a.GetProperty().SetSpecular(.15);a.GetProperty().SetSpecularPower(24)
    renderer.AddActor(a)
    return a

def cube(renderer,c,size,color):
    s=vtk.vtkCubeSource();s.SetCenter(*c);s.SetXLength(size[0]);s.SetYLength(size[1]);s.SetZLength(size[2])
    m=vtk.vtkPolyDataMapper();m.SetInputConnection(s.GetOutputPort());a=vtk.vtkActor();a.SetMapper(m)
    a.GetProperty().SetColor(*color);renderer.AddActor(a);return a

def line(renderer,points,color,radius=1.5):
    ps=vtk.vtkPoints()
    for pt in points:ps.InsertNextPoint(*pt)
    path=vtk.vtkPolyLine();path.GetPointIds().SetNumberOfIds(len(points))
    for i in range(len(points)):path.GetPointIds().SetId(i,i)
    lines=vtk.vtkCellArray();lines.InsertNextCell(path)
    data=vtk.vtkPolyData();data.SetPoints(ps);data.SetLines(lines)
    tube=vtk.vtkTubeFilter();tube.SetInputData(data);tube.SetRadius(radius);tube.SetNumberOfSides(16)
    mapper=vtk.vtkPolyDataMapper();mapper.SetInputConnection(tube.GetOutputPort())
    a=vtk.vtkActor();a.SetMapper(mapper);a.GetProperty().SetColor(*color);renderer.AddActor(a);return a

def moved_with_door(actor):
    tx=vtk.vtkTransform();tx.Translate(P['hinge_axis_x'],P['hinge_axis_y'],0)
    tx.RotateZ(P['door_open_angle']);tx.Translate(-P['hinge_axis_x'],-P['hinge_axis_y'],0)
    actor.SetUserTransform(tx)

for i in range(2):
    r=vtk.vtkRenderer();r.SetViewport(i*.5,0,(i+1)*.5,1);r.SetBackground(.96,.96,.95);window.AddRenderer(r)
    for name,color in M['printed'].items():
        if i and name=='door':mesh_actor(r,'door_open',color)
        else:mesh_actor(r,name,color)
    for name,color in M['reference'].items():mesh_actor(r,name,color)
    # Hardware envelopes convey selected sizes, not unmeasured fixing positions.
    for z in P['hardware_heights']:
        cube(r,(-100,-66,z),(12.5,1.5,25),(.70,.72,.73))
        leaf=cube(r,(-84,-66,z),(12.5,1.5,25),(.70,.72,.73))
        line(r,[(-92,-67,z-12.5),(-92,-67,z+12.5)],(.74,.75,.76),2)
        latch=cube(r,(45,-73,z),(56,2,18),(.71,.73,.75))
        handle=cube(r,(42,-77,z),(34,5,9),(.78,.07,.04))
        arm=line(r,[(69,-74,z-4),(99,-74,z-4),(102,-74,z),(99,-74,z+4),(69,-74,z+4)],(.75,.76,.77),1.2)
        cube(r,(100,-73,z),(18.3,2,15.2),(.71,.73,.75))
        if i:
            for a in (leaf,latch,handle,arm):moved_with_door(a)
    # Continuous rounded door gasket follows actual groove centreline.
    pts=[]
    import math
    for cx,cz,start in [(75,P['height']-10,0),(-75,P['height']-10,90),(-75,10,180),(75,10,270)]:
        for j in range(13):
            t=math.radians(start+j*90/12)
            pts.append((cx+5*math.cos(t),-60.3,cz+5*math.sin(t)))
    pts.append(pts[0])
    line(r,pts,(.035,.04,.045),1)
    # Flexible wiring and antenna cable: schematic, omitted from manufacturing files.
    line(r,[(69,-20,21),(75,-20,25),(74,-26,48),(60,-26,56),(5,10,60),(-11,29,65)],(.04,.28,.70),1.4)
    line(r,[(-45,28,60),(-45,20,64),(4,0,64),(32,-4,60)],(.05,.05,.05),1.5)
    line(r,[(64,19,60),(63,40,55),(65,42,40),(60,40,-10),(60,68,-10),(60,72,P['height']+6),(30,50,P['height']+26),(21,5,P['height']+42)],(.04,.045,.05),1.5)
    for dx,col in [(0,(.85,.18,.08)),(1.5,(.92,.68,.12)),(3,(.04,.4,.62))]:
        line(r,[(-25,28,79+dx),(-22,20,90+dx),(-12,25,87+dx)],col,.5)
    # Short pole shown only for context.
    line(r,[(0,0,-28),(0,0,-65)],(.45,.47,.48),27)
    c=r.GetActiveCamera();c.SetPosition(90,-530,140);c.SetViewUp(0,0,1)
    c.SetFocalPoint(-5 if not i else -35,-20,65);c.ParallelProjectionOn()
    c.SetParallelScale(145 if not i else 175);r.ResetCameraClippingRange()
    def label(value,x,y,size):
        t=vtk.vtkTextActor();t.SetInput(value);t.SetPosition(x,y)
        t.GetTextProperty().SetFontSize(size);t.GetTextProperty().SetColor(.12,.14,.16);r.AddViewProp(t)
    label('CLOSED / SELECTED HARDWARE' if not i else 'OPEN / FIXED BATTERY SUPPORTS',25,1125,27)
    label('170 x 120 mm main body | 218 mm across mounting wings' if not i else 'Door, shelf, board panel, roof and pole adapter are separate',25,1070,19)
    label('Hardware shown schematically; mounting pads require transfer-drilling',25,55,18)
    label('CAD FIT PROTOTYPE / dimensions of real battery and cable still required',25,25,18)
window.Render();cap=vtk.vtkWindowToImageFilter();cap.SetInput(window);cap.Update()
writer=vtk.vtkPNGWriter();writer.SetFileName(str(OUT/'preview.png'));writer.SetInputConnection(cap.GetOutputPort());writer.Write();window.Finalize()
print(OUT/'preview.png')

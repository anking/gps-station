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
    tx=vtk.vtkTransform();tx.Translate(-170,-20,0)
    actor.SetUserTransform(tx)

for i in range(2):
    r=vtk.vtkRenderer();r.SetViewport(i*.5,0,(i+1)*.5,1);r.SetBackground(.96,.96,.95);window.AddRenderer(r)
    for name,color in M['printed'].items():
        if i and name=='door':mesh_actor(r,'door_open',color)
        else:mesh_actor(r,name,color)
    for name,color in M['reference'].items():mesh_actor(r,name,color)
    # User positions hinges and latch keepers; do not show floating hardware.
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
    line(r,[(69,-20,16),(75,-20,20),(74,-26,48),(60,-26,56),(5,10,60),(-11,29,65)],(.04,.28,.70),1.4)
    line(r,[(-45,28,60),(-45,20,64),(4,0,64),(32,-4,60)],(.05,.05,.05),1.5)
    line(r,[(64,19,60),(63,40,55),(65,42,40),(60,40,-10),(60,68,-10),(60,72,P['height']+6),(30,50,P['height']+26),(21,5,P['height']+42)],(.04,.045,.05),1.5)
    for dx,col in [(0,(.85,.18,.08)),(1.5,(.92,.68,.12)),(3,(.04,.4,.62))]:
        line(r,[(-25,28,79+dx),(-22,20,90+dx),(-12,25,87+dx)],col,.5)
    # Short pole shown only for context.
    line(r,[(0,0,-38),(0,0,-75)],(.45,.47,.48),27)
    c=r.GetActiveCamera();c.SetPosition(90,-530,140);c.SetViewUp(0,0,1)
    c.SetFocalPoint(-5 if not i else -70,-20,65);c.ParallelProjectionOn()
    c.SetParallelScale(165 if not i else 205);r.ResetCameraClippingRange()
    def label(value,x,y,size):
        t=vtk.vtkTextActor();t.SetInput(value);t.SetPosition(x,y)
        t.GetTextProperty().SetFontSize(size);t.GetTextProperty().SetColor(.12,.14,.16);r.AddViewProp(t)
    label('V3 / NO SIDE MOUNTING WINGS' if not i else 'FLAT FLOOR / SLIDING SHELF',25,1125,27)
    label('Exterior post boss with blind mounting holes' if not i else 'Shelf enters C channels from the front, without screws',25,1070,19)
    label('Door hardware to be fitted by user; original ESP cradle retained',25,55,18)
    label('CAD FIT PROTOTYPE / dimensions of real battery and cable still required',25,25,18)
window.Render();cap=vtk.vtkWindowToImageFilter();cap.SetInput(window);cap.Update()
writer=vtk.vtkPNGWriter();writer.SetFileName(str(OUT/'preview.png'));writer.SetInputConnection(cap.GetOutputPort());writer.Write();window.Finalize()
print(OUT/'preview.png')

# Underside view of the actual snap-on roof.
detail=vtk.vtkRenderWindow();detail.SetOffScreenRendering(1);detail.SetSize(1400,1000)
ren=vtk.vtkRenderer();ren.SetBackground(.96,.96,.95);detail.AddRenderer(ren)
mesh_actor(ren,'roof',M['printed']['roof'])
cam=ren.GetActiveCamera();cam.SetPosition(180,-220,-110);cam.SetFocalPoint(0,0,P['height']+10)
cam.SetViewUp(0,0,1);cam.ParallelProjectionOn();cam.SetParallelScale(108);ren.ResetCameraClippingRange()
for value,y in [('V3 / FOUR INTEGRAL LOWER ROOF HOOKS',930),('No screw holes or screw bosses | Release lower tabs outward',40)]:
    t=vtk.vtkTextActor();t.SetInput(value);t.SetPosition(25,y)
    t.GetTextProperty().SetFontSize(25 if y>100 else 20);t.GetTextProperty().SetColor(.12,.14,.16);ren.AddViewProp(t)
detail.Render();shot=vtk.vtkWindowToImageFilter();shot.SetInput(detail);shot.Update()
writer=vtk.vtkPNGWriter();writer.SetFileName(str(OUT/'roof_detail.png'));writer.SetInputConnection(shot.GetOutputPort());writer.Write();detail.Finalize()

# Actual underside and rail geometry, shown separately for review.
mechanism=vtk.vtkRenderWindow();mechanism.SetOffScreenRendering(1);mechanism.SetSize(2200,1100)
for idx in range(2):
    ren=vtk.vtkRenderer();ren.SetViewport(idx*.5,0,(idx+1)*.5,1);ren.SetBackground(.96,.96,.95);mechanism.AddRenderer(ren)
    if idx==0:
        mesh_actor(ren,'body',M['printed']['body'])
        camera=ren.GetActiveCamera();camera.SetPosition(170,-200,-230);camera.SetFocalPoint(0,0,35)
        camera.SetViewUp(0,0,1);camera.ParallelProjectionOn();camera.SetParallelScale(160)
        title='UNDERSIDE / BLIND POST-BOLT HOLES'
        subtitle='External boss 10 mm deep | 6 mm solid material to interior'
    else:
        mesh_actor(ren,'rail_detail',(.66,.71,.75))
        mesh_actor(ren,'shelf_edge_detail',(.15,.4,.65))
        camera=ren.GetActiveCamera();camera.SetPosition(-20,-165,125);camera.SetFocalPoint(76,-15,P['shelf_z']+2)
        camera.SetViewUp(0,0,1);camera.ParallelProjectionOn();camera.SetParallelScale(78)
        title='SLIDE DETAIL / RIGHT CHANNEL'
        subtitle='Blue: shelf edge, partly withdrawn | 0.3 mm clearance per face'
    ren.ResetCameraClippingRange()
    for value,y,size in [(title,1035,25),(subtitle,40,18)]:
        text=vtk.vtkTextActor();text.SetInput(value);text.SetPosition(25,y)
        text.GetTextProperty().SetFontSize(size);text.GetTextProperty().SetColor(.12,.14,.16);ren.AddViewProp(text)
mechanism.Render();shot=vtk.vtkWindowToImageFilter();shot.SetInput(mechanism);shot.Update()
writer=vtk.vtkPNGWriter();writer.SetFileName(str(OUT/'mechanism_detail.png'));writer.SetInputConnection(shot.GetOutputPort());writer.Write();mechanism.Finalize()

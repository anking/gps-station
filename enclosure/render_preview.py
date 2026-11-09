"""Render the exported CAD meshes, not an illustrative reconstruction."""
from pathlib import Path
import vtk

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'output'
window=vtk.vtkRenderWindow()
window.SetOffScreenRendering(1)
window.SetSize(1800,1100)
window.SetMultiSamples(8)

colors={'base':(.70,.74,.78),'lid':(.82,.85,.88),
        'gnss_carrier':(.32,.36,.40),'esp_cradle':(.32,.36,.40),
        'gnss_reference':(.80,.13,.10),'esp_reference':(.08,.20,.35)}
for index,names in enumerate([['base','lid'],['base','gnss_carrier','esp_cradle','gnss_reference','esp_reference']]):
    renderer=vtk.vtkRenderer()
    renderer.SetViewport(index*.5,0,(index+1)*.5,1)
    renderer.SetBackground(.96,.96,.95)
    window.AddRenderer(renderer)
    for name in names:
        reader=vtk.vtkSTLReader()
        reader.SetFileName(str(OUT/f'_preview_{name}.stl'))
        reader.Update()
        mapper=vtk.vtkPolyDataMapper()
        mapper.SetInputConnection(reader.GetOutputPort())
        actor=vtk.vtkActor()
        actor.SetMapper(mapper)
        actor.GetProperty().SetColor(*colors[name])
        actor.GetProperty().SetSpecular(.16)
        actor.GetProperty().SetSpecularPower(25)
        renderer.AddActor(actor)
    camera=renderer.GetActiveCamera()
    camera.SetPosition(95,-140,450)
    camera.SetFocalPoint(0,0,15)
    camera.SetViewUp(0,1,0)
    camera.ParallelProjectionOn()
    camera.SetParallelScale(93)
    renderer.ResetCameraClippingRange()
    def text(value,x,y,size):
        label=vtk.vtkTextActor()
        label.SetInput(value)
        label.SetPosition(x,y)
        label.GetTextProperty().SetFontSize(size)
        label.GetTextProperty().SetColor(.12,.15,.18)
        renderer.AddViewProp(label)
    text('B / RAIN-EXPOSURE PROTOTYPE' if index==0 else 'INTERIOR / LID REMOVED',30,1025,25)
    text('90 x 110 x 40 mm body + cover' if index==0 else '44 x 43.2 mm GNSS | 18 x 24.7 mm ESP32',30,980,21)
    text('Mounting ears extend total height to 144 mm' if index==0 else 'Boards shown as approximate fit envelopes only',30,65,20)
    text('Two bottom gland holes / gasketed removable lid' if index==0 else 'GNSS carrier pads require transfer-drilled holes',30,30,20)
window.Render()
capture=vtk.vtkWindowToImageFilter()
capture.SetInput(window)
capture.SetScale(1)
capture.Update()
writer=vtk.vtkPNGWriter()
writer.SetFileName(str(OUT/'preview.png'))
writer.SetInputConnection(capture.GetOutputPort())
writer.Write()
window.Finalize()
print(OUT/'preview.png')

"""Exploded and cropped views of the actual CAD interfaces."""
from pathlib import Path
import vtk
import cadquery as cq
from PIL import Image, ImageDraw, ImageFont
import build as m

OUT = Path(__file__).resolve().parent / "output"
SIZE = 1800, 1100


def make_actor(shape, color):
    points, tris = shape.val().tessellate(.04)
    vp = vtk.vtkPoints()
    for p in points:
        vp.InsertNextPoint(p.x, p.y, p.z)
    cells = vtk.vtkCellArray()
    for tri in tris:
        cells.InsertNextCell(3, tri)
    pd = vtk.vtkPolyData()
    pd.SetPoints(vp)
    pd.SetPolys(cells)
    normals = vtk.vtkPolyDataNormals()
    normals.SetInputData(pd)
    normals.SetFeatureAngle(40)
    mapper = vtk.vtkPolyDataMapper()
    mapper.SetInputConnection(normals.GetOutputPort())
    a = vtk.vtkActor()
    a.SetMapper(mapper)
    a.GetProperty().SetColor(*color)
    a.GetProperty().SetAmbient(.25)
    return a


def main():
    win = vtk.vtkRenderWindow()
    win.SetOffScreenRendering(1)
    win.SetSize(*SIZE)
    win.SetMultiSamples(4)
    background = vtk.vtkRenderer()
    background.SetBackground(.955, .966, .976)
    win.AddRenderer(background)
    orange, dark = m.COLORS["orange"], (.30, .36, .42)
    clipz = m.H + m.BH - 10
    views = [
        ([(m.PARTS["clamp_lower"]["shape"], orange),
          (m.PARTS["clamp_upper_C"]["shape"].translate((0, 0, 24)), orange),
          (m.PARTS["TEST_socket_tongue"]["shape"].translate((0, 0, 62)), orange),
          (m.box(0, 0, -26, 26, 110, 26), dark)],
         (160, -240, 155), (0, 0, 34), 105),
        ([(m.PARTS["side_arm_lower"]["shape"].intersect(m.box(110, 0, 72, 125, 60, 50)), orange),
          (m.PARTS["side_arm_upper"]["shape"].intersect(m.box(110, 0, 72, 125, 60, 50)).translate((0, 32, 0)), orange)],
         (200, -350, 200), (112, 15, 98), 95),
        ([(m.PARTS["TEST_lid_catch"]["shape"], dark),
          (m.PARTS["TEST_lid_clip"]["shape"].translate((4, 0, 0)), dark)],
         (260, -160, clipz + 95), (123, 55, clipz), 30),
    ]
    for i, (shapes, pos, focal, scale) in enumerate(views):
        ren = vtk.vtkRenderer()
        ren.SetViewport(i / 3, .18, (i + 1) / 3, .85)
        ren.SetBackground(.955, .966, .976)
        win.AddRenderer(ren)
        for shape, color in shapes:
            ren.AddActor(make_actor(shape, color))
        cam = ren.GetActiveCamera()
        cam.SetPosition(*pos)
        cam.SetFocalPoint(*focal)
        cam.SetViewUp(0, 0, 1)
        cam.ParallelProjectionOn()
        cam.SetParallelScale(scale)
        ren.ResetCameraClippingRange()
    win.Render()
    grab = vtk.vtkWindowToImageFilter()
    grab.SetInput(win)
    grab.Update()
    writer = vtk.vtkPNGWriter()
    writer.SetFileName(str(OUT / "details.png"))
    writer.SetInputConnection(grab.GetOutputPort())
    writer.Write()
    win.Finalize()
    im = Image.open(OUT / "details.png").convert("RGB")
    draw = ImageDraw.Draw(im)
    def txt(text, xy, size=24, bold=False):
        font = "C:/Windows/Fonts/segoeuib.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf"
        draw.text(xy, text, font=ImageFont.truetype(font, size), fill=(25, 40, 55))
    txt("СОЕДИНЕНИЯ · ГЕОМЕТРИЯ ИЗ CAD", (40, 25), 38, True)
    txt("Детали разведены для пояснения; штифты и винты подбираются отдельно", (42, 85), 24)
    txt("Хомут и нижний ключ", (35, 165), 28, True)
    txt("Нахлёст боковой ноги", (625, 165), 28, True)
    txt("Защёлка крышки", (1225, 165), 28, True)
    txt("Два M5 на хомут; труба 26 × 26", (35, 935), 23)
    txt("Ключ 24 × 24; штифт Ø5", (35, 975), 23)
    txt("Два ключа воспринимают сдвиг", (625, 935), 23)
    txt("Два M5 стягивают половины", (625, 975), 23)
    txt("Лапка 1,8 мм; отвод наружу", (1225, 935), 23)
    txt("Сначала проверить на образцах", (1225, 975), 23)
    im.save(OUT / "details.png")
    print(OUT / "details.png")


if __name__ == "__main__":
    main()

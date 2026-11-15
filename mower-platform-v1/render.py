"""Render actual exported assembly meshes using VTK; add Russian captions."""
from pathlib import Path
import json
import vtk
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "output"
M = json.loads((OUT / "manifest.json").read_text())
FONT = "C:/Windows/Fonts/segoeui.ttf"
BOLD = "C:/Windows/Fonts/segoeuib.ttf"
SIZE = (1800, 1250)


def actor(path, color, opacity=1):
    r = vtk.vtkSTLReader()
    r.SetFileName(str(path))
    r.Update()
    norm = vtk.vtkPolyDataNormals()
    norm.SetInputConnection(r.GetOutputPort())
    norm.SetFeatureAngle(35)
    mapper = vtk.vtkPolyDataMapper()
    mapper.SetInputConnection(norm.GetOutputPort())
    a = vtk.vtkActor()
    a.SetMapper(mapper)
    a.GetProperty().SetColor(*color)
    a.GetProperty().SetOpacity(opacity)
    a.GetProperty().SetSpecular(.18)
    a.GetProperty().SetSpecularPower(25)
    a.GetProperty().SetAmbient(.28)
    a.GetProperty().SetDiffuse(.72)
    return a


def render(path, views, captions):
    win = vtk.vtkRenderWindow()
    win.SetOffScreenRendering(1)
    win.SetSize(*SIZE)
    win.SetMultiSamples(4)
    background = vtk.vtkRenderer()
    background.SetBackground(.955, .966, .976)
    win.AddRenderer(background)
    for cfg in views:
        ren = vtk.vtkRenderer()
        ren.SetViewport(*cfg["viewport"])
        ren.SetBackground(.955, .966, .976)
        win.AddRenderer(ren)
        for name, row in M["instances"].items():
            if cfg.get("filter") and not cfg["filter"](name):
                continue
            ren.AddActor(actor(OUT / row["mesh"], row["color"],
                              cfg.get("body_opacity", 1) if name.startswith("body_") else 1))
        for name, row in M["references"].items():
            if name.startswith("tube_"):
                opacity = 1
            elif "engine_" in name:
                opacity = .20
            elif "battery_" in name or "linkage_" in name:
                opacity = .22
            elif cfg.get("boards"):
                opacity = 1
            else:
                continue
            ren.AddActor(actor(OUT / row["mesh"], row["color"], opacity))
        cam = ren.GetActiveCamera()
        cam.SetPosition(*cfg["position"])
        cam.SetFocalPoint(*cfg["focal"])
        cam.SetViewUp(*cfg.get("up", (0, 0, 1)))
        cam.ParallelProjectionOn()
        cam.SetParallelScale(cfg["scale"])
        ren.ResetCameraClippingRange()
    win.Render()
    grab = vtk.vtkWindowToImageFilter()
    grab.SetInput(win)
    grab.Update()
    w = vtk.vtkPNGWriter()
    w.SetFileName(str(path))
    w.SetInputConnection(grab.GetOutputPort())
    w.Write()
    win.Finalize()
    im = Image.open(path).convert("RGB")
    draw = ImageDraw.Draw(im)
    for text, pos, size, bold in captions:
        draw.text(pos, text, font=ImageFont.truetype(BOLD if bold else FONT, size), fill=(25, 40, 55))
    im.save(path)


def main():
    no_lid = lambda n: not (n.startswith("lid_") or n in ("lidar_blank_plate", "gps_blank_plate"))
    render(OUT / "preview.png", [
        {"viewport": (0, .08, .63, .87), "position": (760, -1100, 900),
         "focal": (0, 0, 75), "scale": 370},
        {"viewport": (.64, .44, 1, .87), "position": (0, 0, 1500), "focal": (0, 0, 60),
         "up": (0, 1, 0), "scale": 320, "filter": no_lid, "body_opacity": .35},
        {"viewport": (.64, .08, 1, .43), "position": (700, -950, 850),
         "focal": (0, 0, 100), "scale": 310, "filter": no_lid, "boards": True},
    ], [
        ("ПЛАТФОРМА КОСИЛЬЩИКА · V1", (45, 20), 39, True),
        ("Рабочая CAD-модель · нагрузка и температура требуют проверки на прототипе", (46, 80), 23, False),
        ("635 × 463,6 мм — рама по наружным граням", (45, 1110), 25, True),
        ("240 × 200 × 65 мм — корпус; низ платформы на высоте 177,8 мм", (45, 1150), 23, False),
        ("Вид сверху · спереди снизу", (1160, 165), 24, True),
        ("Одиночная опора спереди; смещение 50,8 мм", (1160, 680), 20, False),
        ("Со снятой крышкой", (1160, 730), 24, True),
        ("Красный/серый объём — условные зоны двигателя, АКБ и рычагов", (45, 1195), 20, False),
    ])
    # Front elevation communicates the dogleg, rail height and open engine space.
    render(OUT / "front_and_side.png", [
        {"viewport": (0, .12, .53, .84), "position": (0, -1500, 95),
         "focal": (0, 0, 95), "scale": 360},
        {"viewport": (.53, .12, 1, .84), "position": (1500, 0, 95),
         "focal": (0, 0, 95), "scale": 300},
    ], [
        ("ВИД СПЕРЕДИ / ВИД СБОКУ", (45, 25), 38, True),
        ("Передняя опора с коленом обходит двигатель на предварительной компоновке", (45, 85), 24, False),
        ("Спереди", (50, 200), 26, True), ("Справа", (1000, 200), 26, True),
        ("Низ корпуса: 177,8 мм над трубой. Двигатель: примерно 101,6 мм над трубой.", (45, 1100), 25, False),
        ("76,2 мм — до дна корпуса; 68,2 мм — до нижних соединителей пола.", (45, 1145), 25, True),
        ("Сторона смещения передней опоры — условная; CAD допускает зеркальную компоновку.", (45, 1192), 22, False),
    ])
    print(OUT / "preview.png")
    print(OUT / "front_and_side.png")


if __name__ == "__main__":
    main()

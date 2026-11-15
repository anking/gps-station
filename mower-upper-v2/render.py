"""Product views made from exported V2 STL geometry, not an AI illustration."""
from pathlib import Path
import json
import vtk
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "output"
M = json.loads((OUT / "manifest.json").read_text())
BG = (.945, .958, .969)


def actor(row, reference=False, opacity_override=None):
    read = vtk.vtkSTLReader()
    read.SetFileName(str(OUT / row["file"]))
    read.Update()
    normals = vtk.vtkPolyDataNormals()
    clean = vtk.vtkCleanPolyData()
    clean.SetInputConnection(read.GetOutputPort())
    clean.ToleranceIsAbsoluteOn()
    clean.SetAbsoluteTolerance(.0001)
    normals.SetInputConnection(clean.GetOutputPort())
    normals.SetFeatureAngle(55)
    normals.ConsistencyOn()
    mapper = vtk.vtkPolyDataMapper()
    mapper.SetInputConnection(normals.GetOutputPort())
    a = vtk.vtkActor()
    a.SetMapper(mapper)
    a.GetProperty().SetColor(*row["color"])
    a.GetProperty().SetOpacity(row.get("opacity", 1) if opacity_override is None else opacity_override)
    a.GetProperty().SetAmbient(.38)
    a.GetProperty().SetDiffuse(.62)
    a.GetProperty().SetSpecular(.08)
    a.GetProperty().SetSpecularPower(22)
    if reference and any(c > .6 for c in row["color"]) and row["color"][0] < .15:
        a.GetProperty().SetAmbient(.92)
        a.GetProperty().SetDiffuse(.08)
    return a


def product_ref(name):
    return name.startswith(("Harxon_", "LCD_", "AI_camera_"))


def render(name, views, captions, size=(1800, 1200)):
    win = vtk.vtkRenderWindow()
    win.SetOffScreenRendering(1)
    win.SetSize(*size)
    win.SetMultiSamples(8)
    back = vtk.vtkRenderer()
    back.SetBackground(*BG)
    win.AddRenderer(back)
    for cfg in views:
        ren = vtk.vtkRenderer()
        ren.SetViewport(*cfg["viewport"])
        ren.SetBackground(*BG)
        win.AddRenderer(ren)
        for n, row in M["instances"].items():
            if cfg.get("only_camera") and n != "camera_cartridge":
                continue
            if cfg.get("hide_hood") and n.startswith(("hood_", "roof_join_")):
                continue
            ren.AddActor(actor(row, opacity_override=.3 if cfg.get("transparent") and n.startswith("hood_") else None))
        if cfg.get("mounted"):
            for row in M["context"].values():
                ren.AddActor(actor(row))
        for n, row in M["references"].items():
            if cfg.get("only_camera") and not n.startswith("AI_camera_"):
                continue
            if product_ref(n) or (cfg.get("mounted") and not n.startswith(("TNC_",))):
                a = actor(row, reference=True)
                if cfg.get("explode_camera") and n.startswith("AI_camera_"):
                    a.SetPosition(0, 15, 0)
                ren.AddActor(a)
        camera = ren.GetActiveCamera()
        camera.SetPosition(*cfg["position"])
        camera.SetFocalPoint(*cfg["focal"])
        camera.SetViewUp(*cfg.get("up", (0, 0, 1)))
        camera.ParallelProjectionOn()
        camera.SetParallelScale(cfg["scale"])
        ren.ResetCameraClippingRange()
    win.Render()
    capture = vtk.vtkWindowToImageFilter()
    capture.SetInput(win)
    capture.Update()
    writer = vtk.vtkPNGWriter()
    writer.SetFileName(str(OUT / name))
    writer.SetInputConnection(capture.GetOutputPort())
    writer.Write()
    win.Finalize()
    im = Image.open(OUT / name).convert("RGB")
    draw = ImageDraw.Draw(im)
    for text, xy, font_size, bold in captions:
        font = "C:/Windows/Fonts/segoeuib.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf"
        draw.text(xy, text, font=ImageFont.truetype(font, font_size), fill=(25, 41, 54))
    im.save(OUT / name)
    print(OUT / name)


def main():
    h = 177.8
    render("concept.png", [
        {"viewport": (0, .13, .64, .86), "position": (640, -1100, 690), "focal": (0, 45, h + 48), "scale": 246},
        {"viewport": (.65, .47, 1, .86), "position": (650, 1100, 690), "focal": (0, 70, h + 42), "scale": 235},
        {"viewport": (.65, .13, 1, .46), "position": (0, -1500, h + 50), "focal": (0, 0, h + 50), "scale": 155},
    ], [
        ("НОВЫЙ ВЕРХ · V2", (42, 20), 42, True),
        ("Гладкий капот, два круглых глаза и камера · прежние ноги и посадки", (44, 85), 25, False),
        ("Вид сзади", (1190, 165), 26, True),
        ("Антенна по центру задней колёсной пары", (1180, 631), 21, False),
        ("Передняя маска", (1190, 680), 26, True),
        ("Наклонные боковые прорези · съёмная маска · задний вынос GPS1000", (44, 1070), 26, True),
        ("Это рендер STL-геометрии. Глаза, камера и антенна показаны как покупные компоненты.", (44, 1120), 22, False),
        ("Кассета под Raspberry Pi AI Camera · размеры посадок AITRIP ещё уточняются.", (44, 1157), 22, False),
    ])
    render("mounted.png", [
        {"viewport": (0, .13, .66, .86), "position": (900, -1200, 870), "focal": (0, 25, 92), "scale": 390, "mounted": True},
        {"viewport": (.67, .13, 1, .86), "position": (0, 0, 1600), "focal": (0, 0, 80), "scale": 530, "mounted": True, "up": (0, 1, 0)},
    ], [
        ("СОВМЕСТИМОСТЬ С НОГАМИ V1", (42, 20), 39, True),
        ("Три исходные квадратные посадки 24,6 мм · плоскость крепления Z = 177,8 мм", (44, 80), 25, False),
        ("Вид сверху", (1230, 170), 26, True),
        ("Сзади", (1380, 295), 23, True),
        ("Спереди", (1380, 980), 23, True),
        ("Ноги и хомуты показаны для проверки; их STL не включены в новый комплект.", (44, 1085), 24, True),
        ("Синяя линия — задняя поперечина. Антенна: X = 0, Y = 218,775 мм.", (44, 1132), 23, False),
        ("Колёса и двигатель — условные габариты, не точные модели вашей косилки.", (44, 1167), 21, False),
    ])
    render("open_upper.png", [
        {"viewport": (0, .12, 1, .87), "position": (600, -900, 950), "focal": (0, 50, h + 15), "scale": 255, "hide_hood": True},
    ], [
        ("СО СНЯТЫМ КАПОТОМ", (42, 20), 39, True),
        ("Съёмные панели электроники и задняя вилка антенны", (44, 82), 26, False),
        ("Капот собирается из четырёх секций и снимается единым модулем.", (44, 1090), 25, True),
        ("Крепёж к старым ногам доступен изнутри после снятия панелей электроники.", (44, 1140), 23, False),
    ])
    render("camera_detail.png", [
        {"viewport": (0, .16, .5, .83), "position": (80, -250, h + 95),
         "focal": (0, -126, h + 46), "scale": 38, "only_camera": True},
        {"viewport": (.5, .16, 1, .83), "position": (90, 30, h + 95),
         "focal": (0, -120, h + 48), "scale": 38, "only_camera": True, "explode_camera": True},
    ], [
        ("КАССЕТА RASPBERRY PI AI CAMERA", (42, 20), 38, True),
        ("Родной объектив · крепление за плату · отдельная съёмная деталь", (44, 82), 24, False),
        ("Спереди", (45, 180), 27, True),
        ("Сзади · камера отодвинута", (945, 180), 27, True),
        ("Отверстие Ø10 мм; посадка под плоское стекло Ø12 ×1 мм", (44, 1045), 25, True),
        ("Четыре стойки под штатные отверстия платы: шаг 21 ×12,5 мм.", (44, 1095), 24, False),
        ("Линза и плата — покупной модуль; фактическую посадку и картинку проверить при примерке.", (44, 1140), 22, False),
    ])


if __name__ == "__main__":
    main()

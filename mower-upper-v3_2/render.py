"""Product views from the actual V3 CAD meshes."""
from pathlib import Path
import os
import json
import vtk
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
OUT = Path(os.environ.get("MOWER_CAD_OUTPUT", ROOT / "output")).resolve()
M = json.loads((OUT / "manifest.json").read_text(encoding="utf-8"))
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
            if cfg.get("parts") and n not in cfg["parts"]:
                continue
            if cfg.get("only_camera") and n != "camera_cartridge":
                continue
            if cfg.get("hide_hood") and (n.startswith(("hood_", "roof_join_", "eye_retainer_")) or n in ("killswitch_dome","face_one_piece","camera_cartridge")):
                continue
            a = actor(row, opacity_override=.3 if cfg.get("transparent") and n.startswith("hood_") else None)
            if cfg.get("technical") and n=="face_one_piece":a.GetProperty().SetColor(.64,.69,.72)
            if cfg.get("technical") and n.startswith("eye_retainer"):a.GetProperty().SetColor(.95,.42,.12)
            if cfg.get("explode_dome") and n=="killswitch_dome":a.SetPosition(0,0,45)
            if cfg.get("exploded"):
                if n in ("hood_one_piece","killswitch_dome"): a.SetPosition(0,0,80)
                if n in ("face_one_piece","camera_cartridge","eye_retainer_-54","eye_retainer_54"):
                    a.SetPosition(0,-80,0)
            ren.AddActor(a)
        if cfg.get("mounted"):
            for row in M["context"].values():
                ren.AddActor(actor(row))
        for n, row in M["references"].items():
            if cfg.get("no_refs"):
                continue
            if cfg.get("hide_hood") and n.startswith(("LCD_","AI_camera_")):
                continue
            if cfg.get("only_camera") and not n.startswith("AI_camera_"):
                continue
            if product_ref(n) or (cfg.get("mounted") and not n.startswith(("TNC_",))):
                a = actor(row, reference=True)
                if cfg.get("explode_camera") and n.startswith("AI_camera_"):
                    a.SetPosition(0, 15, 0)
                if cfg.get("exploded") and n.startswith(("LCD_","AI_camera_")):
                    a.SetPosition(0,-80,0)
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
        {"viewport": (0,.12,.65,.85), "position": (640,-1100,690), "focal": (0,45,h+48), "scale": 245},
        {"viewport": (.65,.47,1,.85), "position": (650,1100,690), "focal": (0,70,h+42), "scale": 228},
        {"viewport": (.65,.12,1,.46), "position": (0,-1500,h+50), "focal": (0,0,h+50), "scale": 155},
    ], [
        ("V3.2 / UPDATED UPPER", (42,20),42,True),
        ("Bambu H2S  /  PETG  /  original leg mounts", (44,84),26,False),
        ("Rear antenna", (1200,170),25,True),
        ("One-piece face", (1200,675),25,True),
        ("User eye mounts  |  Clip-on covers  |  Reinforced switch dome", (44,1070),27,True),
        ("Actual CAD geometry. Displays, camera and antenna are purchased components.", (44,1125),23,False),
        ("Eye mounts follow your supplied STEP; verify fit on the printed PETG parts.", (44,1160),22,False),
    ])
    render("exploded.png", [
        {"viewport": (0,.13,1,.86), "position": (660,-1000,780), "focal": (0,20,h+75), "scale": 280,"exploded":True},
    ], [
        ("BASE / HOOD / VISOR + SWITCH DOME", (42,20),42,True),
        ("Three one-piece housing parts and the new removable dome", (44,84),27,False),
        ("No floor or roof joining plates; no tiled seams.", (44,1070),28,True),
        ("Perimeter guides and a flat base; electronics trays removed.", (44,1125),23,False),
        ("Hood and face moved apart for this assembly view; screws and cables omitted.", (44,1160),22,False),
    ])
    render("open_upper.png", [
        {"viewport": (0,.13,1,.86), "position": (600,-900,1000), "focal": (0,50,h+18), "scale": 245,"hide_hood":True},
    ], [
        ("UNDER THE HOOD", (42,20),42,True),
        ("Clear base, wall-side guides and original leg interfaces", (44,84),26,False),
        ("Four guides align the hood; two side detents hold it while fitting the screws.", (44,1080),25,True),
        ("Disconnect the face and switch wiring before lifting the hood away.", (44,1135),23,False),
    ])
    render("mounted.png", [
        {"viewport": (0,.13,.66,.86), "position": (900,-1200,870), "focal": (0,25,92), "scale": 390,"mounted":True},
        {"viewport": (.67,.13,1,.86), "position": (0,0,1600), "focal": (0,0,80), "scale": 530,"mounted":True,"up":(0,1,0)},
    ], [
        ("SAME THREE LEGS", (42,20),42,True),
        ("Original mounting plane: 177.8 mm above the frame tubes", (44,84),26,False),
        ("Top view", (1230,170),26,True),
        ("Rear", (1380,295),23,True),
        ("Front", (1380,980),23,True),
        ("Legs unchanged. Antenna centre remains over the rear crossmember.", (44,1080),25,True),
        ("Engine, battery zone and wheels are approximate reference envelopes.", (44,1135),23,False),
    ])
    render("front_fit.png", [
        {"viewport": (0,.14,.62,.85), "position": (0,-1500,h+42), "focal": (0,-126,h+42), "scale": 125,"parts":["base_one_piece","hood_one_piece","face_one_piece","camera_cartridge"],"no_refs":True},
        {"viewport": (.62,.49,1,.85), "position": (280,-650,h+310), "focal": (0,-115,h+59), "scale": 135,"parts":["base_one_piece","hood_one_piece","face_one_piece","camera_cartridge"],"no_refs":True},
        {"viewport": (.62,.14,1,.49), "position": (280,-650,h-200), "focal": (0,-115,h+25), "scale": 135,"parts":["base_one_piece","hood_one_piece","face_one_piece","camera_cartridge"],"no_refs":True},
    ], [
        ("V3.2 / FACE FIT", (42,20),42,True),
        ("Front panel follows the actual case outline on all four sides", (44,84),26,False),
        ("Top edge", (1150,180),25,True),
        ("Bottom + side edges", (1150,650),25,True),
        ("0.3 mm perimeter inset and 0.3 mm axial fitting gap", (44,1080),27,True),
        ("Two lower access holes reach the existing hood screws; two upper holes retain the face.",(44,1135),23,False),
    ])
    render("base_rim_fixed.png", [
        {"viewport": (0,.17,.5,.84), "position": (1000,0,h-300), "focal": (80,0,h+8), "scale": 142,"parts":["base_one_piece"],"no_refs":True},
        {"viewport": (.5,.17,1,.84), "position": (-1000,0,h-300), "focal": (-80,0,h+8), "scale": 142,"parts":["base_one_piece"],"no_refs":True},
    ], [
        ("V3.2 / SMOOTH BASE RIM", (42,20),42,True),
        ("Four receiver-block protrusions removed; functional pockets retained", (44,84),25,False),
        ("Right side", (80,180),26,True),
        ("Left side", (980,180),26,True),
        ("Four guide-block protrusions trimmed flush on both sides.", (44,1080),26,True),
        ("The central rectangular opening is the intentional side-clip release window.", (44,1135),23,False),
    ])
    render("base_top.png", [
        {"viewport": (0,.13,1,.86), "position": (0,0,1200), "focal": (0,0,h+8), "scale": 170,"parts":["base_one_piece"],"no_refs":True,"up":(0,1,0)},
    ], [
        ("CLEAR BASE / PERIMETER GUIDES", (42,20),39,True),
        ("No raised electronics trays, spacers or tray-mount bosses", (44,84),26,False),
        ("The four guides moved 28-29.5 mm outward, next to the case walls.", (44,1080),25,True),
        ("Original leg and antenna mounting holes retained. Electronics can mount directly to the floor.",(44,1135),22,False),
    ])
    render("eye_mount_detail.png", [
        {"viewport": (0,.15,.5,.85), "position": (-100,-360,h+90), "focal": (-54,-126,h+49), "scale": 43,"parts":["face_one_piece"],"no_refs":True,"technical":True},
        {"viewport": (.5,.15,1,.85), "position": (-120,100,h+95), "focal": (-54,-123,h+49), "scale": 47,"parts":["face_one_piece","eye_retainer_-54"],"no_refs":True,"technical":True},
    ], [
        ("YOUR EYE-MOUNT GEOMETRY / BOTH SIDES", (42,20),38,True),
        ("Stepped recesses, raised lips and small screw pilots copied from the supplied STEP",(44,84),24,False),
        ("Front",(60,180),25,True),
        ("Rear / existing retaining ring",(950,180),25,True),
        ("The left reference is mirrored to the right eye. The centre AI-camera mount is unchanged.",(44,1080),23,True),
        ("Technical view colours highlight the geometry. Print the visor upright with rear supports.",(44,1135),23,False),
    ])
    render("dome_detail.png", [
        {"viewport": (0,.15,.5,.85), "position": (170,-250,h+300), "focal": (0,0,h+106), "scale": 66,"parts":["killswitch_dome"],"no_refs":True},
        {"viewport": (.5,.15,1,.85), "position": (100,-160,h-70), "focal": (0,0,h+99), "scale": 65,"parts":["killswitch_dome"],"no_refs":True,"up":(0,0,-1)},
    ], [
        ("SWITCH DOME / REINFORCED EDGE + CORD GROOVE",(42,20),35,True),
        ("Original 40 mm cavity, 22 mm switch hole and four mounting pilots retained",(44,84),25,False),
        ("3 mm lower skirt",(60,180),25,True),
        ("Underside / continuous groove",(950,180),25,True),
        ("2 mm cord: groove 2.6 mm wide x 1.5 mm deep; 78 mm pitch diameter",(44,1080),25,True),
        ("Nominal 25% compression. Test actual cord, splice and seal on the printed parts.",(44,1135),23,False),
    ])
    render("dome_mount.png", [
        {"viewport": (0,.15,.5,.85), "position": (0,0,1000), "focal": (0,0,h+92), "scale": 66,"parts":["hood_one_piece"],"no_refs":True,"up":(0,1,0)},
        {"viewport": (.5,.15,1,.85), "position": (430,-600,h+430), "focal": (0,0,h+108), "scale": 182,"parts":["hood_one_piece","killswitch_dome"],"no_refs":True,"explode_dome":True},
    ], [
        ("DOME / MATCHED HOOD OPENING AND HOLES",(42,20),38,True),
        ("Centred at X=0, Y=0 on the hood top; mounting plane Z=269.8 mm",(44,84),25,False),
        ("Hood top",(60,180),25,True),
        ("Dome lifted for clarity",(950,180),25,True),
        ("40.6 mm square access opening and four 2.7 mm screw-clearance holes",(44,1080),25,True),
        ("The original offset screw pattern is preserved. Screws fit upward from inside the hood.",(44,1135),23,False),
    ])
    render("hood_inside.png", [
        {"viewport": (0,.13,1,.86), "position": (450,-750,-400), "focal": (0,0,h+40), "scale": 205,"parts":["hood_one_piece"],"no_refs":True,"up":(0,0,-1)},
    ], [
        ("HOOD / INSIDE VIEW", (42,20),42,True),
        ("Side clips, locating tongues and captive-nut retaining points", (44,84),26,False),
        ("Print the fit samples first. Release force and fatigue need a physical PETG trial.", (44,1125),24,False),
    ])


if __name__ == "__main__":
    main()

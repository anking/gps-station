"""Apply local interface refinements to cached native bodies without re-lofting.

The same changes are present in build.py; this script preserves the already
generated spline shell during the prototype iteration.
"""
from pathlib import Path
import json
import csv
import math
import cadquery as cq
import vtk
from camera_mount import build_camera

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "output"
M = json.loads((OUT / "manifest.json").read_text())
H = 177.8
AY = M["parameters"]["antenna_axis_y"]


def box(x, y, z, w, d, h):
    return cq.Workplane("XY", origin=(x, y, z)).box(w, d, h, centered=(True, True, False))


def cyl(x, y, z, r, h):
    return cq.Workplane("XY", origin=(x, y, z)).circle(r).extrude(h)


def bore(p, axis, r, h):
    return cq.Workplane(obj=cq.Solid.makeCylinder(r, h, cq.Vector(*p), cq.Vector(*axis)))


def hexx(x, y, z, af, d):
    pl = cq.Plane(origin=(x, y, z), xDir=(0, 1, 0), normal=(1, 0, 0))
    return cq.Workplane(pl).polygon(6, af / math.cos(math.pi / 6)).extrude(d)


def hexz(x, y, z, af, h):
    return (cq.Workplane("XY", origin=(x, y, z)).polygon(6, af / math.cos(math.pi / 6)).extrude(h)
            .rotate((x, y, 0), (x, y, 1), 30))


def face(w, h, r, y, depth, z):
    return (cq.Workplane("XY").rect(w, h).extrude(depth).edges("|Z").fillet(r)
            .rotate((0, 0, 0), (1, 0, 0), 90).translate((0, y, z)))


def profile(points, width=24):
    pl = cq.Plane(origin=(-width / 2, 0, 0), xDir=(0, 1, 0), normal=(1, 0, 0))
    return cq.Workplane(pl).polyline(points).close().extrude(width)


def weld(path):
    r = vtk.vtkSTLReader(); r.SetFileName(str(path)); r.Update()
    clean = vtk.vtkCleanPolyData(); clean.SetInputConnection(r.GetOutputPort())
    clean.ToleranceIsAbsoluteOn(); clean.SetAbsoluteTolerance(.00001); clean.Update()
    w = vtk.vtkSTLWriter(); w.SetFileName(str(path)); w.SetInputConnection(clean.GetOutputPort())
    w.SetFileTypeToBinary(); w.Write()


def main():
    parts = {n: cq.importers.importStep(str(OUT / f"{n}.step")) for n in M["parts"]}
    changed = {}
    for sx, lr in ((-1, "left"), (1, "right")):
        for sy, fb in ((-1, "front"), (1, "rear")):
            n = f"hood_{fb}_{lr}"
            y = sy * 65
            s = parts[n].cut(box(sx * 137.5, y, H + 5.9, 6, 16.4, 12.11))
            tab = box(135, y, H + 6, 5, 16, 17).union(box(139.75, y, H + 18, 15.5, 16, 5))
            tab = tab.cut(bore((130, y, H + 10), (1, 0, 0), 1.7, 26))
            tab = tab.cut(hexx(132.4, y, H + 10, 5.8, 2.9))
            if sx < 0:
                tab = tab.mirror("YZ")
            s = s.union(tab)
            if fb == "rear":
                s = s.cut(box(0, 145, H + 16, 12, 70, 18))
            changed[n] = s.clean()
    boom = profile([(80, H - 20), (155, H - 20), (AY + 22, H + 26),
                    (AY + 22, H + 44), (AY - 22, H + 44), (155, H), (80, H)])
    pts = [(165, H - 3), (AY - 9, H + 23), (AY - 9, H + 32), (165, H + 4)]
    for x, depth in ((-12.1, 9.1), (3, 9.1)):
        pl = cq.Plane(origin=(x, 0, 0), xDir=(0, 1, 0), normal=(1, 0, 0))
        boom = boom.cut(cq.Workplane(pl).polyline(pts).close().extrude(depth))
    for y in (90, 115):
        boom = boom.cut(cyl(0, y, H - 22, 2.25, 28)).cut(hexz(0, y, H - 20.1, 7.4, 3.5))
    for y in (AY - 12, AY + 12):
        boom = boom.cut(cyl(0, y, H + 21, 2.25, 30)).cut(hexz(0, y, H - 22, 7.4, 51.4))
    changed["antenna_tail_beam"] = boom.clean()

    mask = parts["visor_left"].union(parts["visor_right"])
    skirt = face(214, 60, 17, -119.3, 6.7, H + 46).cut(face(210, 56, 15, -119, 7.3, H + 46))
    cam = build_camera(H)
    mask = mask.union(skirt).cut(cam["opening"])
    for sx in (-1, 1):
        for z0, z1 in ((15.8, 29.5), (58.5, 84.5)):
            mask = mask.cut(box(sx * 108, -122.65, H + z0, 41, 7.3, z1 - z0))
    for sx, lr in ((-1, "left"), (1, "right")):
        changed[f"visor_{lr}"] = mask.intersect(box(sx * 200.2, 0, H, 400, 500, 130)).clean()
    ez = H + 49
    r = bore((0, -120, ez), (0, 1, 0), 25, 3).cut(bore((0, -121, ez), (0, 1, 0), 17.4, 5))
    r = r.cut(box(0, -118.5, ez - 30, 28, 6, 14))
    for x in (-23, 23):
        r = r.union(bore((x, -120, ez), (0, 1, 0), 5, 3))
        r = r.cut(bore((x, -121, ez), (0, 1, 0), 1.7, 5))
    changed["eye_rear_retainer"] = r.clean()
    changed["camera_cartridge"] = cam["cartridge"]
    changed["TEST_eye_seat"] = mask.intersect(box(-54, -122, ez - 30, 62, 30, 60)).clean()
    M["parts"]["camera_cartridge"]["note"] = "Raspberry Pi AI Camera SC1174; four M2 pilots on21x12.5 pitch; visible aperture10mm; optional flat window12x1mm"
    for name, s in changed.items():
        assert s.val().isValid() and len(s.solids().vals()) == 1, (name, len(s.solids().vals()))
        parts[name] = s
        cq.exporters.export(s, str(OUT / f"{name}.step"))
        printable = s
        if name.startswith("visor_") or name in ("camera_cartridge", "eye_rear_retainer", "TEST_eye_seat"):
            printable = s.rotate((0, 0, 0), (1, 0, 0), 90)
        if name == "antenna_tail_beam":
            printable = s.rotate((0, 0, 0), (0, 1, 0), 90)
        b = printable.val().BoundingBox()
        printable = printable.translate((-(b.xmin + b.xmax) / 2, -(b.ymin + b.ymax) / 2, -b.zmin))
        cq.exporters.export(printable, str(OUT / f"{name}.stl"), tolerance=.045, angularTolerance=.12)
        weld(OUT / f"{name}.stl")
        b = printable.val().BoundingBox()
        M["parts"][name]["bbox_mm"] = [b.xlen, b.ylen, b.zlen]
        M["parts"][name]["volume_cm3"] = s.val().Volume() / 1000
        print("Refined", name, flush=True)
    assembly = cq.Assembly(name="sleek_upper_v2_ONLY")
    for n, row in M["instances"].items():
        s = parts[row["part"]]
        if row["part"] in ("antenna_tail_beam", "eye_rear_retainer"):
            s = s.translate((float(n.rsplit("_", 1)[1]), 0, 0))
        elif row["part"] not in changed:
            s = cq.importers.importStep(str(OUT / f"_solid_{n}.step"))
        cq.exporters.export(s, str(OUT / f"_solid_{n}.step"))
        cq.exporters.export(s, str(OUT / row["file"]), tolerance=.07)
        assembly.add(s, name=n, color=cq.Color(*row["color"]))
    assembly.export(str(OUT / "upper_v2_ONLY.step"))
    for name, shape, color in (("AI_camera_PCB_REFERENCE", cam["pcb"], (.12, .40, .26)),
                               ("AI_camera_package_REFERENCE", cam["package"], (.015, .025, .03)),
                               ("AI_camera_lens_REFERENCE", cam["lens"], (.015, .025, .03)),
                               ("AI_camera_glass_REFERENCE", cam["glass"], (.12, .24, .32))):
        filename = f"_references_{name}.stl"
        cq.exporters.export(shape, str(OUT / filename), tolerance=.025)
        cq.exporters.export(shape, str(OUT / f"_{name}.step"))
        M["references"][name] = {"file": filename, "color": color, "opacity": 1}
    M["parameters"] = json.loads((ROOT / "parameters.json").read_text())
    M["camera_mount"] = {"PCB": [25, 23.862, 1.12], "hole_pitch": [21, 12.5],
                           "hole_z_relative_lens": [-.1, 12.4], "hole_x_relative_lens": [-10.5, 10.5],
                           "front_aperture": 10, "optional_flat_window": [12, 1]}
    (OUT / "manifest.json").write_text(json.dumps(M, indent=2), encoding="utf-8")
    with (OUT / "print_list.csv").open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f); writer.writerow(["part", "quantity", "X_mm", "Y_mm", "Z_mm", "note"])
        for n, row in M["parts"].items():
            writer.writerow([n, row["quantity"], *[round(v, 2) for v in row["bbox_mm"]], row["note"]])


if __name__ == "__main__":
    main()

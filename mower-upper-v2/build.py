"""V2: upper assembly only. Imports V1 legs as immutable compatibility context.

Same coordinates and same three 24mm keyed sockets, M5 bores and Z177.8 plane.
Lofted superellipse shell, front eye visor and rear-axis Harxon support.
"""
from pathlib import Path
import csv
import hashlib
import importlib.util
import json
import math
import cadquery as cq
import vtk
from camera_mount import build_camera

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "output"
OUT.mkdir(exist_ok=True)
P = json.loads((ROOT / "parameters.json").read_text(encoding="utf-8"))
OLDROOT = (ROOT / P["legacy_interface"]).resolve()
spec = importlib.util.spec_from_file_location("legacy_mower_v1", OLDROOT / "build.py")
old = importlib.util.module_from_spec(spec)
spec.loader.exec_module(old)
H, F, GAP = old.H, P["floor"], P["split_gap"]
AY = P["antenna_axis_y"]
box, rr, cyl, bore, at, hex_z = old.box, old.rr, old.cylinder, old.bore_axis, old.at, old.hex_z
PARTS, INSTANCES, CONTEXT, REFS = {}, {}, {}, {}
COLORS = {"shell": (.70, .77, .80), "base": (.19, .23, .28),
          "visor": (.045, .065, .08), "accent": (1.0, .38, .06),
          "screen": (.015, .025, .03), "iris": (.04, .78, .93),
          "white": (.91, .93, .94), "metal": (.45, .48, .51)}


def register(name, shape, color="shell", rotation=None, note="", test=False):
    shape = shape.clean()
    PARTS[name] = {"shape": shape, "print": old.print_pose(shape, rotation),
                   "color": color, "note": note, "test": test}


def inst(name, part, shape=None):
    INSTANCES[name] = {"part": part, "shape": shape if shape is not None else PARTS[part]["shape"],
                       "color": PARTS[part]["color"]}


def ref(name, shape, color, opacity=1):
    REFS[name] = {"shape": shape, "color": color, "opacity": opacity}


def superwire(w, d, z, cy=0, n=3.0):
    pts = []
    for i in range(40):
        a = 2 * math.pi * i / 40
        c, s = math.cos(a), math.sin(a)
        x = w / 2 * math.copysign(abs(c) ** (2 / n), c)
        y = cy + d / 2 * math.copysign(abs(s) ** (2 / n), s)
        pts.append(cq.Vector(x, y, z))
    return cq.Wire.assembleEdges([cq.Edge.makeSpline(pts, periodic=True)])


def loft(rows):
    return cq.Workplane(obj=cq.Solid.makeLoft([superwire(w, d, H + z, cy) for w, d, z, cy in rows], False))


def xz_rect(w, h, rad, y0, depth, x=0, z=0):
    # Face shapes build in XY, then rotate into XZ; positive extrusion faces -Y.
    s = rr(w, h, rad, 0, depth)
    return s.rotate((0, 0, 0), (1, 0, 0), 90).translate((x, y0, z))


def xz_round(x, z, radius, y0, depth):
    return bore((x, y0, z), (0, 1, 0), radius, depth)


def yz_hex(x, y, z, af, depth):
    plane = cq.Plane(origin=(x, y, z), xDir=(0, 1, 0), normal=(1, 0, 0))
    return cq.Workplane(plane).polygon(6, af / math.cos(math.pi / 6)).extrude(depth)


def y_z_prism(points, width=24):
    plane = cq.Plane(origin=(-width / 2, 0, 0), xDir=(0, 1, 0), normal=(1, 0, 0))
    return cq.Workplane(plane).polyline(points).close().extrude(width)


def quarter(shape, sx, sy):
    return shape.intersect(box(sx * (250 + GAP / 2), sy * (250 + GAP / 2), H - 35, 500, 500, 160))


# Retain unchanged V1 legs and clamps for checking and rendering only.
for name, row in old.INSTANCES.items():
    if name.startswith(("A_", "B_", "C_")):
        CONTEXT[name] = {"shape": row["shape"], "color": (1, .36, .055)}

print("Building smooth outer shell", flush=True)
outer = loft([(292, 300, 0, 0), (302, 304, 9, -2),
              (294, 300, 48, -7), (274, 279, 72, -2),
              (238, 240, 87, 7), (210, 214, 92, 12)])
inner = loft([(286, 294, F, 0), (296, 298, 10, -2),
              (288, 294, 48, -7), (268, 273, 72, -2),
              (232, 234, 85.5, 7), (204, 208, 88.5, 12)])
# Flat vertical visor face truncates the front of the organic volume.
keep = box(0, 190, H - 2, 600, 632, 105)  # Y >= -126
outer = outer.intersect(keep)
shell = outer.cut(inner)
print("Splitting lower frame and hood", flush=True)
base = shell.intersect(box(0, 0, H - 1, 600, 650, 17))
hood = shell.intersect(box(0, 0, H + 16.3, 600, 650, 100))

# EXACT V1 upper interface: no alterations to foot positions, angle or height.
for label, (fx, fy), (x, y), _ in old.feet:
    angle = math.degrees(math.atan2(y - fy, x - fx))
    base = base.cut(at(box(0, 0, H - .1, old.SOCKET, old.SOCKET, 4.1), x, y, angle))
    base = base.cut(cyl(x, y, H - 1, 2.75, F + 2))


def floor_bridge(length):
    bar = box(0, 0, H - 8, length, 18, 8)
    xs = (-length / 2 + 12, -18, 18, length / 2 - 12)
    for x in xs:
        bar = bar.cut(cyl(x, 0, H - 9, 2.25, 16))
        bar = bar.cut(hex_z(x, 0, H - 8.1, 7.4, 3.5))
    for x in (-27, 27):
        bar = bar.union(cyl(x, 0, H, 3.9, 2.5))
    return bar, xs


for name, length, positions in (
        ("base_join_x", 100, [(0, -105, 0), (0, 65, 0)]),
        ("base_join_y", 90, [(-65, 0, 90), (65, 0, 90)])):
    bar, xs = floor_bridge(length)
    register(name, bar, "base", note="2 copies; ordinary M4 nuts in underside; flat side down")
    for i, (x, y, a) in enumerate(positions):
        inst(f"{name}_{i}", name, at(bar, x, y, a))
        for u in xs:
            base = base.cut(at(cyl(u, 0, H - 1, 2.25, F + 2), x, y, a))
        for u in (-27, 27):
            base = base.cut(at(cyl(u, 0, H - .1, 4.2, 2.9), x, y, a))

# Keep the same removable electronics carriers; replace only their host floor.
for cx in (-57, 57):
    for dx in (-39, 39):
        for y in (-45, 45):
            base = base.union(cyl(cx + dx, y, H + F, 5, 5))
            base = base.cut(cyl(cx + dx, y, H - 1, 1.7, F + 8))
            base = base.cut(hex_z(cx + dx, y, H - .1, 5.8, 2.8))

# Four hidden inward tabs, lower-waist horizontal M3 screws; no roof towers.
print("Building detachable hood joints", flush=True)
for sx in (-1, 1):
    for y in (-65, 65):
        tab = box(135, y, H + 6, 5, 16, 17)
        tab = tab.union(box(139.75, y, H + 18, 15.5, 16, 5))
        tab = tab.cut(bore((130, y, H + 10), (1, 0, 0), 1.7, 26))
        tab = tab.cut(yz_hex(132.4, y, H + 10, 5.8, 2.9))
        if sx < 0:
            tab = tab.mirror("YZ")
        hood = hood.union(tab)
        base = base.cut(bore((sx * 125, y, H + 10), (sx, 0, 0), 1.7, 35))

# Roof quadrant connectors, installed internally; accessible low-profile screws.
print("Building internal roof joins", flush=True)
rb = box(0, 0, H + 79, 90, 14, 4)
for u in (-32, 32):
    rb = rb.cut(cyl(u, 0, H + 78, 1.7, 8))
    rb = rb.cut(hex_z(u, 0, H + 78.9, 5.8, 2.9))
for u in (-20, 20):
    rb = rb.union(cyl(u, 0, H + 83, 1.9, 1.8))
register("roof_join", rb, "base", note="4 copies; M3 captive nuts; four shell panels assemble as one removable hood")
for i, (x, y, a) in enumerate([(0, -55, 0), (0, 65, 0), (-65, 0, 90), (65, 0, 90)]):
    inst(f"roof_join_{i}", "roof_join", at(rb, x, y, a))
    for u in (-32, 32):
        post = cyl(u, 0, H + 83, 4.5, 6)
        post = post.cut(cyl(u, 0, H + 82, 1.7, 16))
        hood = hood.union(at(post, x, y, a))
        hood = hood.cut(at(cyl(u, 0, H + 82, 1.7, 19), x, y, a))
    for u in (-20, 20):
        post = cyl(u, 0, H + 83, 3.4, 6).cut(cyl(u, 0, H + 82.9, 2.2, 2.3))
        hood = hood.union(at(post, x, y, a))

print("Cutting face and side gills", flush=True)
face_blank = xz_rect(214, 60, 17, -126, 4, z=H + 46)
face_return = xz_rect(214, 60, 17, -119.3, 6.7, z=H + 46).cut(
    xz_rect(210, 56, 15, -119, 7.3, z=H + 46))
face_blank = face_blank.union(face_return)
for sx in (-1, 1):
    for z0, z1 in ((15.8, 29.5), (58.5, 84.5)):
        face_blank = face_blank.cut(box(sx * 108, -122.65, H + z0, 41, 7.3, z1 - z0))
face_clear = xz_rect(214.8, 60.8, 17.4, -119, 15, z=H + 46)
hood = hood.cut(face_clear)
# Reinforced screw lugs are left independent of the detachable black visor.
for x in (-96, 96):
    for dz in (24, 64):
        # Extend to the surrounding shell at either edge of the visor opening.
        attach = box(x + math.copysign(12, x), -120, H + dz - 5, 40, 22, 10)
        # Only retain the volume below/above opening, plus outward side shelves.
        if dz == 24:
            attach = attach.union(box(x + math.copysign(12, x), -119, H + 16.3, 40, 20, dz - 16.3 + 5))
        else:
            attach = attach.union(box(x + math.copysign(12, x), -119, H + dz - 5, 40, 20, 20))
        attach = attach.intersect(outer)
        hood = hood.union(attach)
        hood = hood.cut(bore((x, -137, H + dz), (0, 1, 0), 1.35, 30))
        face_blank = face_blank.cut(bore((x, -133, H + dz), (0, 1, 0), 1.7, 10))

for y in [25 + 15 * i for i in range(P["vent_slots_per_side"])]:
    pl = cq.Plane(origin=(110, y, H + 46), xDir=(0, 1, 0), normal=(1, 0, 0))
    slot = cq.Workplane(pl).slot2D(P["vent_slot_length"], P["vent_slot_width"], angle=70).extrude(75)
    hood = hood.cut(slot).cut(slot.mirror("YZ"))
# Open-bottom coax notch: lay cable in with hood removed; connector need not
# pass through a tiny closed hole. Add split grommet/seal after cable sizing.
hood = hood.cut(box(0, 145, H + 16, 12, 70, 18))

# Round display seats: provisional GC9A01 module rear-pocket and header relief.
EYEZ = H + P["eye_axis_z_above_mount"]
for x in (-P["eye_pitch"] / 2, P["eye_pitch"] / 2):
    boss = xz_round(x, EYEZ, 27, -126, 6)
    for dx in (-23, 23):
        boss = boss.union(xz_round(x + dx, EYEZ, 5, -126, 6))
    face_blank = face_blank.union(boss)
    face_blank = face_blank.cut(xz_round(x, EYEZ, P["eye_visible_diameter"] / 2, -135, 20))
    face_blank = face_blank.cut(xz_round(x, EYEZ, P["eye_pocket_diameter_UNCONFIRMED"] / 2, -128.2, 12))
    face_blank = face_blank.cut(box(x, -122, EYEZ - 28, 28, 12.4, 15))
    for dx in (-23, 23):
        face_blank = face_blank.cut(bore((x + dx, -127, EYEZ), (0, 1, 0), 1.3, 10))

retainer = xz_round(0, EYEZ, 25, -120, 3).cut(xz_round(0, EYEZ, 17.4, -121, 5))
retainer = retainer.cut(box(0, -118.5, EYEZ - 30, 28, 6, 14))
for dx in (-23, 23):
    retainer = retainer.union(xz_round(dx, EYEZ, 5, -120, 3))
    retainer = retainer.cut(xz_round(dx, EYEZ, 1.7, -121, 5))
register("eye_rear_retainer", retainer, "visor", rotation=((1, 0, 0), 90),
         note="2 copies; provisional rear ring; match real LCD/PCB and protect glass")
for x in (-54, 54):
    inst(f"eye_retainer_{x}", "eye_rear_retainer", at(retainer, x=x))

# Replaceable cassette for the actual Raspberry Pi AI Camera SC1174.
CZ = H + 46
CAM = build_camera(H)
face_blank = face_blank.cut(CAM["opening"])
for x in (-20, 20):
    face_blank = face_blank.cut(xz_round(x, CZ, 1.3, -134, 14))
register("camera_cartridge", CAM["cartridge"], "visor", rotation=((1, 0, 0), 90),
         note="Pi AI Camera SC1174: 21x12.5mm mounting pitch, M2x5 plastic screws; visible opening Ø10; optional flat window Ø12x1")
inst("camera_cartridge", "camera_cartridge")

# Split front visor only at centre; camera cartridge bridges the centre seam.
for sx, label in ((-1, "left"), (1, "right")):
    p = face_blank.intersect(box(sx * (200 + GAP / 2), 0, H, 400, 500, 130))
    register(f"visor_{label}", p, "visor", rotation=((1, 0, 0), 90), note="Front face down; eye pocket is provisional")
    inst(f"visor_{label}", f"visor_{label}")

print("Building rear axle antenna fork", flush=True)
boom = y_z_prism([(80, H - 20), (155, H - 20), (AY + 22, H + 26),
                   (AY + 22, H + 44), (AY - 22, H + 44), (155, H), (80, H)])
# Side recesses leave a 6mm middle web and continuous top/bottom chords.
relief = [(165, H - 3), (AY - 9, H + 23), (AY - 9, H + 32), (165, H + 4)]
for x0, thick in ((-12.1, 9.1), (3, 9.1)):
    plane = cq.Plane(origin=(x0, 0, 0), xDir=(0, 1, 0), normal=(1, 0, 0))
    boom = boom.cut(cq.Workplane(plane).polyline(relief).close().extrude(thick))
for y in (90, 115):
    boom = boom.cut(cyl(0, y, H - 22, 2.25, 28))
    boom = boom.cut(hex_z(0, y, H - 20.1, 7.4, 3.5))
    for x in (-30, 30):
        base = base.cut(cyl(x, y, H - 1, 2.25, F + 2))
for y in (AY - 12, AY + 12):
    boom = boom.cut(cyl(0, y, H + 21, 2.25, 30))
    boom = boom.cut(hex_z(0, y, H - 22, 7.4, 51.4))
register("antenna_tail_beam", boom, "base", rotation=((0, 1, 0), 90), note="2 copies at X±30; rear fork, not a replacement leg")
for x in (-30, 30):
    inst(f"antenna_tail_{x}", "antenna_tail_beam", at(boom, x=x))

puck = cyl(0, AY, H + 44, 40, 12).cut(cyl(0, AY, H + 42, P["antenna_mount_clearance_diameter"] / 2, 16))
for x in (-30, 30):
    for y in (AY - 12, AY + 12):
        puck = puck.cut(cyl(x, y, H + 42, 2.25, 16))
register("harxon_mount_plate", puck, "base", note="Ø16.5 clearance for METAL BSW5/8-11 mounting stud; do not print thread")
inst("harxon_mount_plate", "harxon_mount_plate")

for sx, lr in ((-1, "left"), (1, "right")):
    for sy, fb in ((-1, "front"), (1, "rear")):
        name = f"base_{fb}_{lr}"
        register(name, quarter(base, sx, sy), "base", note="Flat floor down; underside V1 mounting sockets unchanged")
        inst(name, name)
        name = f"hood_{fb}_{lr}"
        register(name, quarter(hood, sx, sy), "shell", note="Open lower edge down; local supports under dome, tabs and screw shelves")
        inst(name, name)

for name in ("electronics_carrier", "pcb_spacer_5mm"):
    item = old.PARTS[name]
    register(name, item["shape"], "base", note="Reused unchanged from V1; quantities in print list")
for name, row in old.INSTANCES.items():
    if row["part"] in ("electronics_carrier", "pcb_spacer_5mm"):
        inst(name, row["part"], row["shape"])

# Fit coupons can be printed before a full face or base quadrant.
sample = base.intersect(at(box(0, 0, H - .1, 43, 35, F + .2), 94, 65,
                              math.degrees(math.atan2(-15, -210.5))))
register("TEST_legacy_socket", sample, "base", test=True, note="Fit on existing V1 right leg; do not print another leg")
sample = face_blank.intersect(box(-54, -122, EYEZ - 30, 62, 30, 60))
register("TEST_eye_seat", sample, "visor", rotation=((1, 0, 0), 90), test=True,
         note="Provisional LCD seat and screw bosses; use with eye_rear_retainer")

# References rendered but never supplied as printable hardware.
for name, item in old.REFERENCES.items():
    if name.startswith("tube_") or "engine_" in name or "battery_" in name:
        ref(name, item["shape"], (.18, .22, .25) if name.startswith("tube_") else (.7, .25, .19), .18 if not name.startswith("tube_") else 1)

# Radome silhouette follows known Ø152 ×62.2 overall dimensions; bottom profile approximate.
az = H + P["antenna_mount_top_above_base"]
radome = cyl(0, AY, az, 25, 22)
radome = radome.union(cyl(0, AY, az + 22, 76, 5))
wires = [cq.Wire.makeCircle(r, cq.Vector(0, AY, az + z), cq.Vector(0, 0, 1))
         for r, z in ((76, 27), (69, 42), (44, 56), (5, 62.2))]
radome = radome.union(cq.Workplane(obj=cq.Solid.makeLoft(wires, False)))
ref("Harxon_GPS1000_REFERENCE", radome, COLORS["white"])
ref("TNC_cable_clearance_REFERENCE", cyl(45, AY, az - 32, 8, 42), COLORS["metal"], .7)
ref("rear_axle_REFERENCE", bore((-320, AY, -15), (1, 0, 0), 3, 640), (.1, .6, .75), .65)
for x in (-340, 340):
    ref(f"rear_wheel_{x}_REFERENCE", bore((x - 12, AY, -35), (1, 0, 0), 75, 24), (.13, .16, .19), .45)
for x in (-54, 54):
    ref(f"LCD_glass_{x}_REFERENCE", xz_round(x, EYEZ, 16.2, -129.1, .7), COLORS["screen"])
    ref(f"LCD_iris_{x}_REFERENCE", xz_round(x + 1.8, EYEZ + 1.0, 10.2, -129.35, .2), COLORS["iris"])
    ref(f"LCD_pupil_{x}_REFERENCE", xz_round(x + 2.8, EYEZ + 1.5, 5.5, -129.5, .1), COLORS["screen"])
    ref(f"LCD_glint_{x}_REFERENCE", xz_round(x - 1.0, EYEZ + 5, 2.1, -129.65, .1), COLORS["white"])
ref("AI_camera_PCB_REFERENCE", CAM["pcb"], (.12, .40, .26))
ref("AI_camera_package_REFERENCE", CAM["package"], COLORS["screen"])
ref("AI_camera_lens_REFERENCE", CAM["lens"], COLORS["screen"])
ref("AI_camera_glass_REFERENCE", CAM["glass"], (.12, .24, .32))


def export_all():
    counts = {}
    for item in INSTANCES.values():
        counts[item["part"]] = counts.get(item["part"], 0) + 1
    manifest = {"parameters": P, "parts": {}, "instances": {}, "context": {}, "references": {},
                "mounts": [], "source_leg_hashes": {}}
    manifest["camera_mount"] = {"PCB": [25, 23.862, 1.12], "hole_pitch": [21, 12.5],
        "hole_z_relative_lens": [-.1, 12.4], "hole_x_relative_lens": [-10.5, 10.5],
        "front_aperture": 10, "optional_flat_window": [12, 1]}
    for f in (OLDROOT / "output").glob("*.stl"):
        if f.stem.startswith(("side_arm_", "front_dogleg", "clamp_")):
            manifest["source_leg_hashes"][f.name] = hashlib.sha256(f.read_bytes()).hexdigest()
    for label, foot, top, _ in old.feet:
        manifest["mounts"].append({"label": label, "top": [*top, H],
                                   "angle": math.degrees(math.atan2(top[1] - foot[1], top[0] - foot[0])),
                                   "socket": old.SOCKET, "depth": 4, "M5_bore": 5.5})
    # Native snapshots also make independent verification possible without
    # rebuilding the lofts and allow inspection if a component check fails.
    for name, item in PARTS.items():
        cq.exporters.export(item["shape"], str(OUT / f"{name}.step"))
    for group, rows in (("solid", INSTANCES), ("legacy", CONTEXT)):
        for name, item in rows.items():
            cq.exporters.export(item["shape"], str(OUT / f"_{group}_{name}.step"))
    for name, item in PARTS.items():
        shape = item["shape"]
        if not shape.val().isValid() or len(shape.solids().vals()) != 1:
            raise RuntimeError(f"Invalid or disconnected: {name} ({len(shape.solids().vals())} solids)")
        cq.exporters.export(item["print"], str(OUT / f"{name}.stl"), tolerance=.045, angularTolerance=.12)
        old.weld_stl_vertices(OUT / f"{name}.stl")
        b = item["print"].val().BoundingBox()
        dims = [b.xlen, b.ylen, b.zlen]
        if dims[0] > 210.01 or dims[1] > 210.01 or dims[2] > 250.01:
            raise RuntimeError(f"Does not fit printer with 5mm margin: {name} {dims}")
        manifest["parts"][name] = {"quantity": counts.get(name, 0), "test": item["test"],
                                  "bbox_mm": dims, "volume_cm3": shape.val().Volume() / 1000,
                                  "note": item["note"]}
        print(f"{name}: {dims[0]:.1f} x {dims[1]:.1f} x {dims[2]:.1f}", flush=True)
    assy = cq.Assembly(name="sleek_upper_v2_ONLY")
    for name, item in INSTANCES.items():
        assy.add(item["shape"], name=name, color=cq.Color(*COLORS[item["color"]]))
        filename = f"_view_{name}.stl"
        cq.exporters.export(item["shape"], str(OUT / filename), tolerance=.10)
        manifest["instances"][name] = {"part": item["part"], "file": filename, "color": COLORS[item["color"]]}
    assy.export(str(OUT / "upper_v2_ONLY.step"))
    for group, rows in (("context", CONTEXT), ("references", REFS)):
        for name, item in rows.items():
            filename = f"_{group}_{name}.stl"
            cq.exporters.export(item["shape"], str(OUT / filename), tolerance=.16)
            if name.startswith("AI_camera_"):
                cq.exporters.export(item["shape"], str(OUT / f"_{name}.step"))
            manifest[group][name] = {"file": filename, "color": item["color"], "opacity": item.get("opacity", 1)}
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    with (OUT / "print_list.csv").open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["part", "quantity", "X_mm", "Y_mm", "Z_mm", "note"])
        for name, row in manifest["parts"].items():
            writer.writerow([name, row["quantity"], *[round(v, 2) for v in row["bbox_mm"]], row["note"]])
    print("Export complete", flush=True)


if __name__ == "__main__":
    export_all()

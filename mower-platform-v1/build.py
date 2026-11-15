"""Parametric mower tripod, mm. CadQuery 2.8; no certified load rating.

World origin: frame centre, TOP of tubing. +X=right, -Y=front, +Z=up.
The side called right is defined looking forward in the direction -Y.
Native printable parts are kept separate from assembly placements.
"""
from pathlib import Path
import csv
import json
import math
import cadquery as cq
import vtk

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "output"
OUT.mkdir(exist_ok=True)
P = json.loads((ROOT / "parameters.json").read_text(encoding="utf-8"))
H = P["platform_underside_height"]
W, L = P["platform_width"], P["platform_length"]
F, BH, LT = P["base_floor"], P["body_height"], P["lid_thickness"]
T = P["tube_size"]
SOCKET = 24 + 2 * P["socket_clearance_per_side"]
SIDE_X = (P["frame_outer_width"] - T) / 2
END_Y = (P["frame_outer_length"] - T) / 2
OFFSET = P["front_offset"]
if P["front_offset_direction"].startswith("left"):
    OFFSET = -abs(OFFSET)
else:
    OFFSET = abs(OFFSET)
TOP_Z = H - 8
BEAM_Z0 = 28.3
JOINT_Z0, JOINT_Z1 = 76.0, 116.0
PARTS, INSTANCES, REFERENCES = {}, {}, {}
COLORS = {"orange": (1.0, .36, .055), "dark": (.20, .24, .29),
          "black": (.10, .12, .14), "gray": (.48, .51, .55),
          "red": (.70, .16, .12), "green": (.12, .42, .26)}


def box(x, y, z, w, d, h):
    return cq.Workplane("XY", origin=(x, y, z)).box(w, d, h, centered=(True, True, False))


def rr(w, d, r, z, h, x=0, y=0):
    return box(x, y, z, w, d, h).edges("|Z").fillet(r)


def cylinder(x, y, z, radius, h):
    return cq.Workplane("XY", origin=(x, y, z)).circle(radius).extrude(h)


def bore_axis(start, axis, radius, length):
    return cq.Workplane(obj=cq.Solid.makeCylinder(radius, length, cq.Vector(*start), cq.Vector(*axis)))


def hex_z(x, y, z, af, h):
    return (cq.Workplane("XY", origin=(x, y, z))
            .polygon(6, af / math.cos(math.pi / 6)).extrude(h)
            .rotate((x, y, 0), (x, y, 1), 30))


def prism(points, v0=-12, v1=12):
    """Polygon in the U/Z plane, extruded across arm width V."""
    plane = cq.Plane(origin=(0, v1, 0), xDir=(1, 0, 0), normal=(0, -1, 0))
    return cq.Workplane(plane).polyline(points).close().extrude(v1 - v0)


def at(part, x=0, y=0, angle=0, z=0):
    return part.rotate((0, 0, 0), (0, 0, 1), angle).translate((x, y, z))


def print_pose(part, rotation=None):
    if rotation:
        axis, angle = rotation
        part = part.rotate((0, 0, 0), axis, angle)
    b = part.val().BoundingBox()
    return part.translate((-(b.xmin + b.xmax) / 2, -(b.ymin + b.ymax) / 2, -b.zmin))


def register(name, shape, color="orange", rotation=None, note=""):
    PARTS[name] = {"shape": shape, "print": print_pose(shape, rotation), "color": color,
                   "note": note}


def instance(name, part, shape=None):
    INSTANCES[name] = {"part": part, "shape": shape if shape is not None else PARTS[part]["shape"],
                       "color": PARTS[part]["color"]}


def top_hardware(arm, run):
    # Broad shoulder carries compression. Square peg registers the tray.
    arm = arm.union(box(run, 0, H - 14, 40, 24, 14))
    arm = arm.union(box(run, 0, H, 24, 24, 3.7))
    arm = arm.cut(cylinder(run, 0, H - 40, 2.75, 49))
    # M5 nut can be inserted sideways before the arm is assembled.
    nut_z = H - 18.8
    arm = arm.cut(hex_z(run, 0, nut_z, 8.4, 4.4))
    arm = arm.cut(box(run, 14, nut_z, 8.4, 28, 4.4))
    return arm


def tongue(arm):
    arm = arm.union(box(0, 0, 8.3, 24, 24, 24))
    return arm.cut(bore_axis((0, -22, 20), (0, 1, 0), 2.75, 44))


def beam_u(run, z):
    return run * (z - BEAM_Z0) / (TOP_Z - BEAM_Z0)


def side_arm(run):
    full = prism([(-24, BEAM_Z0), (24, BEAM_Z0),
                  (run + 24, TOP_Z), (run - 24, TOP_Z)])
    # Through-windows outside the solid splice zone leave two long chords.
    for z0, z1 in ((44, 67), (125, 149)):
        opening = [(beam_u(run, z0) - 10, z0), (beam_u(run, z0) + 10, z0),
                   (beam_u(run, z1) + 10, z1), (beam_u(run, z1) - 10, z1)]
        full = full.cut(prism(opening, -13, 13))
    full = top_hardware(tongue(full), run)
    # Stepped lap. 0.3mm initial separation permits assembly after printing.
    low = full.cut(box(100, 0, JOINT_Z1, 650, 90, 300))
    low = low.cut(box(100, 20, JOINT_Z0, 650, 40.3, 40.1))
    high = full.cut(box(100, 0, -50, 650, 90, JOINT_Z0 + 50))
    high = high.cut(box(100, -20, JOINT_Z0 - .01, 650, 40.3, 40.01))
    # Two positive keys take shear; two transverse M5 screws clamp the lap.
    for du in (-16, 16):
        key = [(beam_u(run, 80) + du - 3, 80), (beam_u(run, 80) + du + 3, 80),
               (beam_u(run, 112) + du + 3, 112), (beam_u(run, 112) + du - 3, 112)]
        low = low.union(prism(key, -.3, 6))
        pocket = [(beam_u(run, 79.7) + du - 3.3, 79.7),
                  (beam_u(run, 79.7) + du + 3.3, 79.7),
                  (beam_u(run, 112.3) + du + 3.3, 112.3),
                  (beam_u(run, 112.3) + du - 3.3, 112.3)]
        high = high.cut(prism(pocket, -.4, 6.3))
    for z in (86, 106):
        u = beam_u(run, z)
        hole = bore_axis((u, -20, z), (0, 1, 0), 2.75, 40)
        low, high = low.cut(hole), high.cut(hole)
        # Hex nut pocket entered from the outer positive-V side.
        pl = cq.Plane(origin=(u, 12.1, z), xDir=(1, 0, 0), normal=(0, -1, 0))
        high = high.cut(cq.Workplane(pl).polygon(6, 8.4 / math.cos(math.pi / 6)).extrude(4.7))
    return low.clean(), high.clean()


def front_arm(run):
    # Dogleg keeps the front strut near the rail until above the engine.
    # It avoids sweeping a straight diagonal through the engine envelope.
    knee = P["engine_top_height_approx"] + 12
    pts = [(-18, BEAM_Z0), (18, BEAM_Z0), (18, knee),
           (run + 20, TOP_Z - 20), (run + 20, TOP_Z),
           (run - 20, TOP_Z), (-18, knee + 26)]
    arm = prism(pts)
    # Recessed panels retain a 6mm central shear web and 10mm side chords.
    for v0, v1 in ((-12.1, -3), (3, 12.1)):
        arm = arm.cut(prism([(-8, 44), (8, 44), (8, knee - 12), (-8, knee - 12)], v0, v1))
        arm = arm.cut(prism([(32, knee + 12), (run - 28, TOP_Z - 23),
                              (run - 28, TOP_Z - 12), (32, knee + 23)], v0, v1))
    return top_hardware(tongue(arm), run).clean()


def clamp(socket_angle=0, upper=True):
    # Native tube along Y. Coordinates are relative to rail top at Z=0.
    gap = P["tube_clearance_per_side"]
    if upper:
        s = box(0, 0, -12.6, 70, 58, 20.6)
        s = s.union(at(box(0, 0, 8, 36, 38, 20), angle=socket_angle))
        s = s.cut(at(box(0, 0, 8.3, SOCKET, SOCKET, 24), angle=socket_angle))
        pin = bore_axis((0, -28, 20), (0, 1, 0), 2.75, 56)
        s = s.cut(at(pin, angle=socket_angle))
    else:
        s = box(0, 0, -34, 70, 58, 20.6)
    # 26.6 square cavity. Top and bottom halves retain a .8mm split gap.
    s = s.cut(box(0, 0, -T - gap, T + 2 * gap, 64, T + 2 * gap))
    for x in (-28, 28):
        s = s.cut(cylinder(x, 0, -40, 2.75, 82))
        if not upper:
            s = s.cut(hex_z(x, 0, -34.1, 8.4, 4.7))
    return s.clean()


side_dx = SIDE_X - P["side_top_x"]
side_dy = P["side_top_y"] - P["side_foot_y"]
SIDE_RUN = math.hypot(side_dx, side_dy)
FRONT_RUN = END_Y + P["front_top_y"]
low, high = side_arm(SIDE_RUN)
register("side_arm_lower", low, rotation=((1, 0, 0), 90), note="2 copies; flat on broad side; keyed splice")
register("side_arm_upper", high, rotation=((1, 0, 0), -90), note="2 copies; M5 side-entry nut; keyed splice; positive-V face down")
register("front_dogleg", front_arm(FRONT_RUN), rotation=((1, 0, 0), 90),
         note="1 copy; one piece; knee stays outside engine until above nominal engine top")
register("clamp_lower", clamp(upper=False), note="3 copies; tube open side up; M5 captive nuts underneath")

feet = [
    ("A", (-SIDE_X, P["side_foot_y"]), (-P["side_top_x"], P["side_top_y"]), 0),
    ("B", ( SIDE_X, P["side_foot_y"]), ( P["side_top_x"], P["side_top_y"]), 0),
    ("C", (OFFSET, -END_Y), (OFFSET, P["front_top_y"]), 90),
]
for label, foot, top, tube_angle in feet:
    angle = math.degrees(math.atan2(top[1] - foot[1], top[0] - foot[0]))
    name = f"clamp_upper_{label}"
    register(name, clamp(angle - tube_angle), rotation=((1, 0, 0), 90),
             note=f"Only station {label}; native tube axis Y; local supports in key/pin roofs")
    instance(f"{label}_clamp_upper", name, at(PARTS[name]["shape"], *foot, tube_angle))
    instance(f"{label}_clamp_lower", "clamp_lower", at(PARTS["clamp_lower"]["shape"], *foot, tube_angle))
    for part in (["front_dogleg"] if label == "C" else ["side_arm_lower", "side_arm_upper"]):
        instance(f"{label}_{part}", part, at(PARTS[part]["shape"], *foot, angle))

# Body: two flat-bottom shells. Underside has only recessed key sockets.
body = rr(W, L, 4, H, BH).cut(rr(W - 2 * P["body_wall"], L - 2 * P["body_wall"], 1, H + F, BH))
for _, (fx, fy), (x, y), _ in feet:
    a = math.degrees(math.atan2(y - fy, x - fx))
    body = body.cut(at(box(0, 0, H - .1, SOCKET, SOCKET, 4.1), x, y, a))
    body = body.cut(cylinder(x, y, H - 1, 2.75, F + 2))

for y in (-25, 25):
    for x in (-45, -20, 20, 45):
        body = body.cut(cylinder(x, y, H - 1, 2.25, F + 2))
    for x in (-32.5, 32.5):
        body = body.cut(cylinder(x, y, H - .1, 4.2, 2.9))

# Removable universal carriers. The lower floor stays planar for printing.
for cx in (-57, 57):
    for dx in (-39, 39):
        for y in (-45, 45):
            x = cx + dx
            body = body.union(cylinder(x, y, H + F, 5, 5))
            body = body.cut(cylinder(x, y, H - 1, 1.7, F + 8))
            body = body.cut(hex_z(x, y, H - .1, 5.8, 2.8))

# Four fixed catches outside side walls. The flexible arms belong to lid.
for sign in (-1, 1):
    for y in (-55, 55):
        catch = prism([(120, H + BH - 13), (123, H + BH - 13),
                       (123, H + BH - 12), (120, H + BH - 10)], y - 7, y + 7)
        if sign < 0:
            catch = catch.mirror("YZ")
        body = body.union(catch)

# Camera bracket fastens to left front wall. No assumed sensor hole pitch.
for x in (-68, -42):
    body = body.cut(bore_axis((x, -105, H + 19), (0, 1, 0), 1.7, 12))

gap = P["split_clearance"]
left_clip = box(-200 - gap / 2, 0, H - 20, 400, 500, 200)
right_clip = box(200 + gap / 2, 0, H - 20, 400, 500, 200)
for name, s in (("body_left", body.intersect(left_clip)), ("body_right", body.intersect(right_clip))):
    register(name, s.clean(), "dark", note="Flat floor down; no integral underside protrusions")
    instance(name, name)

bridge = box(0, 0, H - 8, 110, 20, 8)
for x in (-32.5, 32.5):
    bridge = bridge.union(cylinder(x, 0, H, 3.9, 2.5))
for x in (-45, -20, 20, 45):
    bridge = bridge.cut(cylinder(x, 0, H - 9, 2.25, 15))
    bridge = bridge.cut(hex_z(x, 0, H - 8.1, 7.4, 3.5))
register("floor_bridge", bridge, "dark", note="2 copies; flat bottom down; captive M4 nuts")
for y in (-25, 25):
    instance(f"floor_bridge_{y}", "floor_bridge", at(bridge, y=y))

carrier = rr(100, 160, 3, H + F + 5, 3)
for x in (-39, 39):
    for y in (-45, 45):
        carrier = carrier.cut(cylinder(x, y, H + F + 4, 1.7, 5))
for x in (-30, -10, 10, 30):
    for y in (-35, 0, 35):
        length = 27 if y == 0 else 30
        slot = box(x, y, H + F + 4, 5.2, length - 5.2, 5)
        for yy in (y - (length - 5.2) / 2, y + (length - 5.2) / 2):
            slot = slot.union(cylinder(x, yy, H + F + 4, 2.6, 5))
        carrier = carrier.cut(slot)
register("electronics_carrier", carrier, "dark", note="2 copies; universal slots 5.2mm wide; M2.5/M3 hardware with washers; actual boards must be matched")
for cx in (-57, 57):
    instance(f"electronics_carrier_{cx}", "electronics_carrier", at(carrier, x=cx))

spacer = cylinder(0, 0, 0, 4, 5).cut(cylinder(0, 0, -1, 1.4, 7))
register("pcb_spacer_5mm", spacer, "dark", note="4 provisional PCB spacers; M2.5 bore; positions are illustrative, not verified Pi hole coordinates")
for x in (-86, -28):
    for y in (-24.5, 24.5):
        instance(f"pcb_spacer_{x}_{y}", "pcb_spacer_5mm", at(spacer, x=x, y=y, z=H + F + 8))

LID_Z = H + BH
lid = rr(W + 5, L + 5, 6.5, LID_Z, LT)
skirt = rr(W + 5, L + 5, 6.5, LID_Z - 8, 8).cut(rr(W + 1, L + 1, 4.5, LID_Z - 8.1, 8.2))
lid = lid.union(skirt)
for sign in (-1, 1):
    for y in (-55, 55):
        # Release beam, 25mm long, 1.8mm thick; clear of the skirt below root.
        tab = box(124.3, y, H + BH - 20, 1.8, 16, 23)
        tab = tab.union(box(122.9, y, LID_Z, 4.6, 16, LT))
        hook = prism([(123.4, H + BH - 16.5), (125.2, H + BH - 16.5),
                      (125.2, H + BH - 13.3), (120.4, H + BH - 13.3)], y - 8, y + 8)
        tab = tab.union(hook)
        if sign < 0:
            tab = tab.mirror("YZ")
        lid = lid.union(tab)

for y in (-25, 25):
    for x in (-35, 35):
        lid = lid.cut(cylinder(x, y, LID_Z - 1, 1.7, LT + 2))
    for x in (-20, 20):
        lid = lid.cut(cylinder(x, y, LID_Z - .1, 2.2, 1.6))
# Blank accessory plates are removable; their sensor-facing faces undrilled.
for x, y in ((-20, 0), (20, 0), (-93, 65), (-67, 65)):
    lid = lid.cut(cylinder(x, y, LID_Z - 1, 1.7, LT + 2))
for name, s in (("lid_left", lid.intersect(left_clip)), ("lid_right", lid.intersect(right_clip))):
    register(name, s.clean(), "dark", rotation=((1, 0, 0), 180),
             note="Outside face down; local supports at latch hooks/skirt; inspect slicer")
    instance(name, name)

lb = box(0, 0, LID_Z - 5, 90, 14, 5)
for x in (-20, 20):
    lb = lb.union(cylinder(x, 0, LID_Z, 1.9, 1.2))
for x in (-35, 35):
    lb = lb.cut(cylinder(x, 0, LID_Z - 6, 1.7, 10))
    lb = lb.cut(hex_z(x, 0, LID_Z - 5.1, 5.8, 2.9))
register("lid_bridge", lb, "dark", note="2 copies; flat bottom down; M3 captive nuts")
for y in (-25, 25):
    instance(f"lid_bridge_{y}", "lid_bridge", at(lb, y=y))

lidar = cylinder(0, 0, LID_Z + LT, 35, 4)
for x in (-20, 20):
    lidar = lidar.cut(cylinder(x, 0, LID_Z + LT - 1, 1.7, 6))
register("lidar_blank_plate", lidar, "dark", note="Blank Ø70 plate; transfer-drill actual lidar; not a sensor-specific mount")
instance("lidar_blank_plate", "lidar_blank_plate")
gps = rr(46, 46, 3, LID_Z + LT, 4, -80, 65)
for x in (-93, -67):
    gps = gps.cut(cylinder(x, 65, LID_Z + LT - 1, 1.7, 6))
register("gps_blank_plate", gps, "dark", note="Blank antenna plate; actual antenna/ground-plane requirements unmeasured")
instance("gps_blank_plate", "gps_blank_plate")

cam = box(-55, -106, H + 12, 40, 4, 42)
for x in (-68, -42):
    cam = cam.union(bore_axis((x, -104, H + 19), (0, 1, 0), 4.5, 4))
    cam = cam.cut(bore_axis((x, -109, H + 19), (0, 1, 0), 1.7, 12))
for x in (-65, -45):
    slot = box(x, -106, H + 32, 3.4, 7, 15)
    for z in (H + 32, H + 47):
        slot = slot.union(bore_axis((x, -110, z), (0, 1, 0), 1.7, 8))
    cam = cam.cut(slot)
register("camera_slotted_plate", cam.clean(), "dark", rotation=((1, 0, 0), 90),
         note="Slots provisional; 4mm rear stand-offs provide space for camera fixing nuts")
instance("camera_slotted_plate", "camera_slotted_plate")

# Small coupons reproduce full-size interfaces, not arbitrary hole gauges.
coupon_clamp = clamp(0)
register("TEST_tube_upper", coupon_clamp, rotation=((1, 0, 0), 90),
         note="TEST ONLY; use with one clamp_lower on an actual 26mm tube")
coupon_tab = tongue(box(0, 0, 28.3, 28, 24, 12))
register("TEST_socket_tongue", coupon_tab, rotation=((1, 0, 0), 90), note="TEST ONLY; square tongue and transverse retention bore")
test_catch = body.intersect(box(119, 55, H + BH - 22, 12, 26, 18))
test_clip = lid.intersect(box(122, 55, H + BH - 22, 20, 26, 31))
register("TEST_lid_catch", test_catch.clean(), "dark", note="TEST ONLY; rigid catch segment")
register("TEST_lid_clip", test_clip.clean(), "dark", rotation=((1, 0, 0), 180), note="TEST ONLY; flex-and-cycle before printing lid")
top_test = box(0, 0, 0, 42, 42, F).cut(box(0, 0, -.1, SOCKET, SOCKET, 4.1))
top_test = top_test.cut(cylinder(0, 0, -1, 2.75, F + 2))
register("TEST_platform_socket", top_test, "dark", note="TEST ONLY; shallow peg socket under 5mm floor")
peg_test = box(0, 0, 0, 40, 24, 5).union(box(0, 0, 5, 24, 24, 3.7))
peg_test = peg_test.cut(cylinder(0, 0, -1, 2.75, 11))
register("TEST_upper_peg", peg_test, "orange", note="TEST ONLY; exact top peg and shoulder width; no captive nut in coupon")

# Reference geometry is excluded from all printable STLs and primary STEP.
def reference(name, shape, color):
    REFERENCES[name] = {"shape": shape, "color": color}

for x in (-SIDE_X, SIDE_X):
    tube = box(x, 0, -T, T, P["frame_outer_length"], T)
    tube = tube.cut(box(x, 0, -T + 2, T - 4, P["frame_outer_length"] + 2, T - 4))
    reference(f"tube_side_{x}", tube, "black")
for y in (-END_Y, END_Y):
    tube = box(0, y, -T, P["frame_outer_width"] - 2 * T, T, T)
    tube = tube.cut(box(0, y, -T + 2, P["frame_outer_width"], T - 4, T - 4))
    reference(f"tube_end_{y}", tube, "black")
reference("engine_APPROX_UNMEASURED", rr(P["engine_reference_width_unmeasured"],
          P["engine_reference_length_unmeasured"], 35, -40,
          40 + P["engine_top_height_approx"]), "red")
reference("battery_ZONE_UNMEASURED", box(0, 180, 3, 200, 80, 80), "gray")
reference("deck_linkage_ZONE_UNMEASURED", box(0, -END_Y, 0, 36, 60, 80), "gray")
reference("pi_hat_ENVELOPE_UNMEASURED", box(-47, 0, H + F + 13, 85, 56, 40), "green")
reference("gnss_ENVELOPE_UNMEASURED", box(57, 20, H + F + 13, 45, 45, 15), "green")
reference("imu_ENVELOPE_UNMEASURED", box(25, -50, H + F + 13, 25, 20, 10), "green")


def weld_stl_vertices(path):
    # OCC's rotated face tessellations can differ at numerical zero. Weld only
    # duplicate vertices within 0.00001mm, far below print/mesh tolerances.
    reader = vtk.vtkSTLReader()
    reader.SetFileName(str(path))
    reader.Update()
    clean = vtk.vtkCleanPolyData()
    clean.SetInputConnection(reader.GetOutputPort())
    clean.ToleranceIsAbsoluteOn()
    clean.SetAbsoluteTolerance(.00001)
    clean.PointMergingOn()
    clean.Update()
    writer = vtk.vtkSTLWriter()
    writer.SetFileName(str(path))
    writer.SetInputConnection(clean.GetOutputPort())
    writer.SetFileTypeToBinary()
    writer.Write()


def build_exports():
    manifest = {"parameters": P, "parts": {}, "instances": {}, "references": {},
                "coordinates": "+X right, -Y front, +Z up; Z0=top of frame tube",
                "side_arm_run": SIDE_RUN, "front_arm_run": FRONT_RUN}
    counts = {}
    for item in INSTANCES.values():
        counts[item["part"]] = counts.get(item["part"], 0) + 1
    for name, item in PARTS.items():
        s, printable = item["shape"].val(), item["print"].val()
        if not s.isValid() or len(item["shape"].solids().vals()) != 1:
            raise RuntimeError(f"Invalid/disconnected part: {name}")
        cq.exporters.export(item["shape"], str(OUT / f"{name}.step"))
        cq.exporters.export(item["print"], str(OUT / f"{name}.stl"), tolerance=.04, angularTolerance=.12)
        weld_stl_vertices(OUT / f"{name}.stl")
        b = printable.BoundingBox()
        dims = [b.xlen, b.ylen, b.zlen]
        limits = P["printer_volume"]
        margin = P["printer_xy_margin_per_side"]
        if not all(d <= lim - (2 * margin if i < 2 else 0) + 1e-5 for i, (d, lim) in enumerate(zip(dims, limits))):
            raise RuntimeError(f"Part exceeds printer envelope with brim allowance: {name}: {dims}")
        manifest["parts"][name] = {"quantity": counts.get(name, 0), "bbox_print_mm": dims,
                                  "solid_volume_cm3": s.Volume() / 1000,
                                  "color": item["color"], "note": item["note"],
                                  "test_only": name.startswith("TEST_")}
        print(f"Exported {name}: {dims[0]:.1f} x {dims[1]:.1f} x {dims[2]:.1f}", flush=True)
    assembly = cq.Assembly(name="mower_platform_v1")
    layout = cq.Assembly(name="mower_platform_with_REFERENCES")
    for name, item in INSTANCES.items():
        col = cq.Color(*COLORS[item["color"]])
        assembly.add(item["shape"], name=name, color=col)
        layout.add(item["shape"], name=name, color=col)
        mesh = f"_view_{name}.stl"
        cq.exporters.export(item["shape"], str(OUT / mesh), tolerance=.08, angularTolerance=.15)
        manifest["instances"][name] = {"part": item["part"], "color": COLORS[item["color"]], "mesh": mesh}
    for name, item in REFERENCES.items():
        layout.add(item["shape"], name=name, color=cq.Color(*COLORS[item["color"]]))
        mesh = f"_ref_{name}.stl"
        cq.exporters.export(item["shape"], str(OUT / mesh), tolerance=.15)
        manifest["references"][name] = {"color": COLORS[item["color"]], "mesh": mesh}
    assembly.export(str(OUT / "mower_platform_v1.step"))
    layout.export(str(OUT / "layout_with_REFERENCES.step"))
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    with (OUT / "print_list.csv").open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["part", "quantity", "print_X_mm", "print_Y_mm", "print_Z_mm", "note"])
        for name, row in manifest["parts"].items():
            w.writerow([name, row["quantity"], *[round(v, 2) for v in row["bbox_print_mm"]], row["note"]])
    print("Assembly exports complete", flush=True)


if __name__ == "__main__":
    build_exports()

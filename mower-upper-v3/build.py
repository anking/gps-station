"""One-piece H2S upper: monolithic base/hood/face, PETG detent clips.

V1 legs, H177.8 interfaces and V2 bought-component positions are unchanged.
All manufacturing solids below are independent of the old split shell.
"""
from pathlib import Path
import csv
import hashlib
import importlib.util
import json
import math
import shutil
import cadquery as cq
import vtk

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "output"
OUT.mkdir(exist_ok=True)
V2 = ROOT.parent / "mower-upper-v2"
P = json.loads((ROOT / "parameters.json").read_text())
M2 = json.loads((V2 / "output/manifest.json").read_text())
H = P["mount_plane_z"]
PARTS, INSTANCES = {}, {}
COLORS = {"shell": (.70, .77, .80), "base": (.19, .23, .28), "visor": (.045, .065, .08)}
spec = importlib.util.spec_from_file_location("camera_v2", V2 / "camera_mount.py")
cam_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cam_module)


def box(x, y, z, w, d, h):
    return cq.Workplane("XY", origin=(x, y, z)).box(w, d, h, centered=(True, True, False))


def cyl(x, y, z, r, h):
    return cq.Workplane("XY", origin=(x, y, z)).circle(r).extrude(h)


def bore(point, axis, radius, length):
    return cq.Workplane(obj=cq.Solid.makeCylinder(radius, length, cq.Vector(*point), cq.Vector(*axis)))


def hex_z(x, y, z, af, h):
    return (cq.Workplane("XY", origin=(x, y, z)).polygon(6, af / math.cos(math.pi / 6)).extrude(h)
            .rotate((x, y, 0), (x, y, 1), 30))


def hex_y(x, y, z, af, length):
    pl = cq.Plane(origin=(x, y, z), xDir=(1, 0, 0), normal=(0, 1, 0))
    return cq.Workplane(pl).polygon(6, af / math.cos(math.pi / 6)).extrude(length)


def face_rect(w, h, r, y, depth, x=0, z=0):
    s = cq.Workplane("XY").rect(w, h).extrude(depth).edges("|Z").fillet(r)
    return s.rotate((0, 0, 0), (1, 0, 0), 90).translate((x, y, z))


def face_round(x, z, r, y, depth):
    return bore((x, y, z), (0, 1, 0), r, depth)


def at(shape, x=0, y=0, angle=0):
    return shape.rotate((0, 0, 0), (0, 0, 1), angle).translate((x, y, 0))


def xz_prism(points, y0, width):
    pl = cq.Plane(origin=(0, y0 + width, 0), xDir=(1, 0, 0), normal=(0, -1, 0))
    return cq.Workplane(pl).polyline(points).close().extrude(width)


def xy_prism(points, z, height):
    return cq.Workplane("XY", origin=(0, 0, z)).polyline(points).close().extrude(height)


def superwire(w, d, z, cy):
    points = []
    for i in range(40):
        a = math.pi * 2 * i / 40
        c, s = math.cos(a), math.sin(a)
        points.append(cq.Vector(w/2 * math.copysign(abs(c)**(2/3), c),
                                cy + d/2 * math.copysign(abs(s)**(2/3), s), H + z))
    return cq.Wire.assembleEdges([cq.Edge.makeSpline(points, periodic=True)])


def cached_loft(name, rows):
    digest = hashlib.sha256(json.dumps([H, rows]).encode()).hexdigest()[:12]
    path = OUT / f"_cache_{name}_{digest}.step"
    if path.exists():
        return cq.importers.importStep(str(path))
    s = cq.Workplane(obj=cq.Solid.makeLoft([superwire(*row) for row in rows], False))
    cq.exporters.export(s, str(path))
    return s


def print_pose(s, rot=None):
    if rot:
        axis, angle = rot
        s = s.rotate((0, 0, 0), axis, angle)
    b = s.val().BoundingBox()
    return s.translate((-(b.xmin+b.xmax)/2, -(b.ymin+b.ymax)/2, -b.zmin))


def register(name, shape, color, rot=None, test=False, note=""):
    PARTS[name] = {"shape": shape.clean(), "color": color, "rot": rot, "test": test, "note": note}


def inst(name, part, shape=None):
    INSTANCES[name] = {"part": part, "shape": shape if shape is not None else PARTS[part]["shape"],
                       "color": COLORS[PARTS[part]["color"]]}


print("Building the unsplit V2 exterior", flush=True)
outer = cached_loft("outer", [(292,300,0,0), (302,304,9,-2), (294,300,48,-7),
                               (274,279,72,-2), (238,240,87,7), (210,214,92,12)])
inner = cached_loft("inner", [(286,294,5,0), (296,298,10,-2), (288,294,48,-7),
                               (268,273,72,-2), (232,234,85.5,7), (204,208,88.5,12)])
outer = outer.intersect(box(0,190,H-2,600,632,105))
shell = outer.cut(inner)
base = shell.intersect(box(0,0,H-1,600,650,17))
hood = shell.intersect(box(0,0,H+16.3,600,650,100))
# A complete front rail closes the lower edge and carries the two hood screws.
base = base.union(box(0,-124.5,H+5,222,3,11).intersect(outer))

print("Preserving all three original leg interfaces", flush=True)
for mount in M2["mounts"]:
    x,y,z = mount["top"]
    base = base.cut(at(box(0,0,H-.1,24.6,24.6,4.1), x,y,mount["angle"]))
    base = base.cut(cyl(x,y,H-1,2.75,7))
for cx in (-57,57):
    for dx in (-39,39):
        for y in (-45,45):
            base = base.union(cyl(cx+dx,y,H+5,5,5))
            base = base.cut(cyl(cx+dx,y,H-1,1.7,13)).cut(hex_z(cx+dx,y,H-.1,5.8,2.8))
for x in (-30,30):
    for y in (90,115):
        base = base.cut(cyl(x,y,H-1,2.25,7))

print("Adding vertical locating guides and PETG hood clips", flush=True)
for sx in (-1,1):
    for y in (-65,65):
        x = sx * 115
        # Four straight guides: remove cover vertically, no rear-hook sequence.
        socket = box(x,y,H+5,12,16,11).cut(box(x,y,H+8,8.6,6.6,10))
        base = base.union(socket)
        pin = box(x,y,H+8.4,8,6,22.6)
        bridge = box(sx*128,y,H+26,36,18,5).intersect(outer)
        hood = hood.union(pin).union(bridge)

hx = P["hood_clip_beam_inner_x"]
ht = P["hood_clip_beam_thickness"]
hn = P["hood_clip_nose_x"]
hc = P["hood_catch_inner_x"]
hw = P["hood_clip_width"]
hood_clip_right = xz_prism([(hx,H+9),(hx+ht,H+9),(hx+ht,H+34),
                            (hx+ht+2.6,H+37),(hx+ht+2.6,H+40),(hx,H+40)], -hw/2,hw)
hood_clip_right = hood_clip_right.union(xz_prism([(hx+ht,H+9),(hn,H+11.5),(hx+ht,H+14)], -hw/2,hw))
hood_flex_right = hood_clip_right
hood_root_right = box(148,0,H+36,16,20,5).intersect(outer)
hood_clip_right = hood_clip_right.union(hood_root_right)
for sx in (-1,1):
    clip = hood_clip_right if sx>0 else hood_clip_right.mirror("YZ")
    hood = hood.union(clip)
    keeper = box((hc+153)/2,0,H+5,153-hc,20,11).intersect(outer)
    if sx<0:
        keeper = keeper.mirror("YZ")
    base = base.union(keeper)
    # Side access lets fingers unload the ramped clip before lifting the hood.
    base = base.cut(box(sx*150,0,H+6.3,44,15,6.7))

# Two retaining screws below the front mask. Ordinary nuts are inserted from
# inside the removed hood; small sacrificial nubs retain them during servicing.
for sx in (-1,1):
    x = sx * 96
    base = base.cut(bore((x,-135,H+10),(0,1,0),1.7,30))
    ear = box(x,-119.4,H+5.5,12,6,24.5)
    upper_bridge = box(sx*108,-119,H+22,40,22,8).intersect(outer)
    ear = ear.union(upper_bridge)
    ear = ear.cut(bore((x,-130,H+10),(0,1,0),1.7,22))
    ear = ear.cut(hex_y(x,-119.3,H+10,5.8,3.0))
    ear = ear.union(box(x,-116.55,H+12.55,1.2,.5,.35))
    hood = hood.union(ear)

print("Building the one-piece face and its clip catches", flush=True)
mask = face_rect(214,60,17,-126,4,z=H+46)
rim = face_rect(214,60,17,-119.3,6.7,z=H+46).cut(face_rect(210,56,15,-119,7.3,z=H+46))
mask = mask.union(rim)
for sx in (-1,1):
    # Clear both screw-support bridges while retaining the middle rim.
    for low, high in ((15.2,30.5),(58.5,84.5)):
        mask = mask.cut(box(sx*108,-122.65,H+low,41,7.3,high-low))
hood = hood.cut(face_rect(214.8,60.8,17.4,-119,15,z=H+46))
for sx in (-1,1):
    x = sx * 96
    support = box(sx*108,-120,H+59,40,22,25).intersect(outer)
    support = support.cut(bore((x,-137,H+64),(0,1,0),1.7,32))
    support = support.cut(hex_y(x,-121.4,H+64,5.8,2.9))
    # Side loading slot opens toward the interior of the face aperture.
    support = support.cut(box(sx*87.7,-119.95,H+61.1,23.3,2.9,5.8))
    support = support.union(box(sx*88.7,-121.1,H+63.2,1.0,.6,1.6))
    hood = hood.union(support)
    mask = mask.cut(bore((x,-135,H+64),(0,1,0),1.7,20))

# Two snap detents on the lower face. The return perimeter locates the panel;
# the two upper screws stop unintended removal in mower use.
fx = P["face_clip_inner_x"]
ft = P["face_clip_thickness"]
fn = P["face_clip_nose_x"]
fc = P["face_catch_inner_x"]
face_clip_right = box(fx+ft/2,-112,H+34,ft,28,10)
face_clip_right = face_clip_right.union(xy_prism([(fx,-105),(fx+ft,-105),
                                                 (fn,-102.5),(fx+ft,-100),(fx,-100)],H+34,10))
face_clip_right = face_clip_right.union(xy_prism([(fx,-126),(fx+ft+2.5,-126),
                                                 (fx+ft,-122),(fx,-122)],H+34,10))
for sx in (-1,1):
    clip = face_clip_right if sx>0 else face_clip_right.mirror("YZ")
    mask = mask.union(clip)
    # End inside the side wall: avoids a thin coincident outer-surface sliver
    # at the keeper's front edge, while retaining positive shell overlap.
    keeper = box((fc+130)/2,-105.5,H+31,130-fc,3,16)
    if sx<0:
        keeper = keeper.mirror("YZ")
    hood = hood.union(keeper)
mask = mask.union(box(0,-128.5,H+12.5,30,3,5.5))

# Keep the existing eyes, AI-camera position, side gills and rear cable notch.
ez = H + 49
for x in (-54,54):
    boss = face_round(x,ez,27,-126,6)
    for dx in (-23,23):
        boss = boss.union(face_round(x+dx,ez,5,-126,6))
    mask = mask.union(boss)
    mask = mask.cut(face_round(x,ez,16.6,-135,20))
    mask = mask.cut(face_round(x,ez,P["eye_pocket_provisional"]/2,-128.2,12))
    mask = mask.cut(box(x,-122,ez-28,28,12.4,15))
    for dx in (-23,23):
        mask = mask.cut(bore((x+dx,-127,ez),(0,1,0),1.3,10))
CAM = cam_module.build_camera(H)
mask = mask.cut(CAM["opening"])
for x in (-20,20):
    mask = mask.cut(face_round(x,H+46,1.3,-134,14))
for y in (25,40,55,70,85):
    pl = cq.Plane(origin=(110,y,H+46),xDir=(0,1,0),normal=(1,0,0))
    cut = cq.Workplane(pl).slot2D(29,5,angle=70).extrude(75)
    hood = hood.cut(cut).cut(cut.mirror("YZ"))
hood = hood.cut(box(0,145,H+16,12,70,18))
# Normalise the smooth-shell trimming tolerances before the final cuts. The
# STEP round trip avoids OCC silently retaining a coincident left window face.
cq.exporters.export(base,str(OUT/"_base_before_release.step"))
base = cq.importers.importStep(str(OUT/"_base_before_release.step"))
for sx in (-1,1):
    base = base.cut(box(sx*150,0,H+6.3,44,15,6.7))

register("base_one_piece",base,"base",note="One monolithic floor; flat underside down; all V1 leg sockets retained")
register("hood_one_piece",hood,"shell",rot=((1,0,0),180),
         note="One-piece hood; roof exterior down; 2 side detents, 4 guides, 2 front M3 retaining screws")
register("face_one_piece",mask,"visor",rot=((1,0,0),90),
         note="One-piece eye/camera face; front down; 2 snap detents and 2 upper M3 retaining screws")
for n in ("base_one_piece","hood_one_piece","face_one_piece"):
    inst(n,n)

# Reuse the removable components without changing their geometry or positions.
reuse = ("antenna_tail_beam","harxon_mount_plate","electronics_carrier","pcb_spacer_5mm",
         "eye_rear_retainer","camera_cartridge")
for name in reuse:
    shape = cq.importers.importStep(str(V2 / "output" / f"{name}.step"))
    rot = ((0,1,0),90) if name=="antenna_tail_beam" else (((1,0,0),90) if name in ("eye_rear_retainer","camera_cartridge") else None)
    register(name,shape,"visor" if name in ("eye_rear_retainer","camera_cartridge") else "base",rot=rot,
             note="Reused unchanged from V2; see print quantity")
for name,row in M2["instances"].items():
    if row["part"] in reuse:
        s = cq.importers.importStep(str(V2 / "output" / f"_solid_{name}.step"))
        inst(name,row["part"],s)

# Actual interface samples, not simplified substitutes. Print in the same
# orientation as their parent to check PETG tolerance and layer adhesion.
register("TEST_hood_clip",hood.intersect(box(148,0,H+8,22,24,35)),"shell",rot=((1,0,0),180),test=True,
         note="Clip side of actual hood; roof-down orientation; use with TEST_hood_catch")
register("TEST_hood_catch",base.intersect(box(148,0,H-.1,22,25,17)),"base",test=True,
         note="Actual base-side keeper and release window")
register("TEST_face_clip",mask.intersect(box(96,-114,H+32,12,36,14)),"visor",rot=((1,0,0),90),test=True,
         note="Actual lower face clip; front down; use with TEST_face_catch")
register("TEST_face_catch",hood.intersect(box(104,-105.5,H+30,16,5,18)),"shell",rot=((1,0,0),180),test=True,
         note="Actual face keeper contact; detached sample for fit trials")
register("TEST_hood_nut_seat",hood.intersect(box(96,-119,H+5.2,14,10,12.5)),"shell",test=True,
         note="M3 nut pocket for front hood-retaining screw")


def weld(path):
    r=vtk.vtkSTLReader();r.SetFileName(str(path));r.Update()
    c=vtk.vtkCleanPolyData();c.SetInputConnection(r.GetOutputPort());c.ToleranceIsAbsoluteOn();c.SetAbsoluteTolerance(.00001);c.Update()
    w=vtk.vtkSTLWriter();w.SetFileName(str(path));w.SetInputConnection(c.GetOutputPort());w.SetFileTypeToBinary();w.Write()


def export_all():
    manifest={"parameters":P,"parts":{},"instances":{},"context":M2["context"],"references":M2["references"],
              "mounts":M2["mounts"],"source_leg_hashes":M2["source_leg_hashes"],
              "camera_mount":M2["camera_mount"],"cover_screws":{"hood":2,"face":2},
              "hood_clip_right_xz": [[hx+ht,9],[hn,11.5],[hx+ht,14]],
              "face_clip_right_xy": [[fx+ft,-105],[fn,-102.5],[fx+ft,-100]]}
    cq.exporters.export(hood_flex_right,str(OUT/"_hood_flex_right.step"))
    cq.exporters.export(face_clip_right,str(OUT/"_face_flex_right.step"))
    counts={}
    for row in INSTANCES.values(): counts[row["part"]]=counts.get(row["part"],0)+1
    for name,row in PARTS.items():
        s=row["shape"]
        cq.exporters.export(s,str(OUT/f"{name}.step"))
    # Always save diagnostics before validation.
    for name,row in INSTANCES.items():
        cq.exporters.export(row["shape"],str(OUT/f"_solid_{name}.step"))
    for name,row in PARTS.items():
        s=row["shape"]
        if not s.val().isValid() or len(s.solids().vals())!=1:
            raise RuntimeError(f"Invalid/disconnected {name}: {len(s.solids().vals())} solids")
        p=print_pose(s,row["rot"])
        cq.exporters.export(p,str(OUT/f"{name}.stl"),tolerance=.045,angularTolerance=.12)
        weld(OUT/f"{name}.stl")
        b=p.val().BoundingBox();dims=[b.xlen,b.ylen,b.zlen]
        limits=[P["printer_volume"][0]-10,P["printer_volume"][1]-10,P["printer_volume"][2]]
        if any(d>lim+.05 for d,lim in zip(dims,limits)):
            raise RuntimeError(f"Does not fit H2S with brim margin: {name} {dims}")
        manifest["parts"][name]={"quantity":counts.get(name,0),"test":row["test"],"bbox_mm":dims,
                                  "volume_cm3":s.val().Volume()/1000,"note":row["note"]}
        print(f"{name}: {dims[0]:.1f} x {dims[1]:.1f} x {dims[2]:.1f}",flush=True)
    assy=cq.Assembly(name="H2S_one_piece_upper_V3")
    for name,row in INSTANCES.items():
        assy.add(row["shape"],name=name,color=cq.Color(*row["color"]))
        file=f"_view_{name}.stl";cq.exporters.export(row["shape"],str(OUT/file),tolerance=.07)
        manifest["instances"][name]={"part":row["part"],"file":file,"color":row["color"]}
    assy.export(str(OUT/"upper_v3_ONLY.step"))
    for group in ("context","references"):
        for name,row in manifest[group].items():
            shutil.copy2(V2/"output"/row["file"],OUT/row["file"])
    for name in manifest["context"]:
        shutil.copy2(V2/"output"/f"_legacy_{name}.step",OUT/f"_legacy_{name}.step")
    for name in ("AI_camera_PCB_REFERENCE","AI_camera_package_REFERENCE","AI_camera_lens_REFERENCE"):
        shutil.copy2(V2/"output"/f"_{name}.step",OUT/f"_{name}.step")
    (OUT/"manifest.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")
    with (OUT/"print_list.csv").open("w",newline="",encoding="utf-8-sig") as f:
        writer=csv.writer(f);writer.writerow(["part","quantity","X_mm","Y_mm","Z_mm","note"])
        for name,row in manifest["parts"].items():writer.writerow([name,row["quantity"],*[round(v,2) for v in row["bbox_mm"]],row["note"]])


if __name__=="__main__":
    export_all()

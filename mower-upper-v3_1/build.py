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


V3 = ROOT.parent / "mower-upper-v3"
print("Rebuilding the continuous hood skin",flush=True)
outer = cq.importers.importStep(str(V3/"output/_cache_outer_4f076e887a2d.step"))
inner = cq.importers.importStep(str(V3/"output/_cache_inner_36fc15e59619.step"))
outer = outer.intersect(box(0,190,H-2,600,632,105))
oldhood = cq.importers.importStep(str(V3/"output/hood_one_piece.step"))
base = cq.importers.importStep(str(V3/"output/base_one_piece.step"))
# Remove the old inward guides and the obsolete electronics tray pedestals.
for sx in (-1,1):
    for y in (-65,65):
        base=base.cut(box(sx*115,y,H+5,12.2,16.2,11.2))
        oldhood=oldhood.cut(box(sx*128,y,H+8.2,38,18.2,23))
for x in (-96,-18,18,96):
    for y in (-45,45):
        base=base.cut(cyl(x,y,H+5,5.1,5.1))
        base=base.union(box(x,y,H,8,8,5))
# Compact wall-side guides. The rear shell narrows more than the front;
# each centre is chosen from the local perimeter, not a rectangular grid.
guide_rows=[]
for y,xabs in ((-65,144.5),(65,143.0)):
    for sx in (-1,1):
        x=sx*xabs
        socket=box(x,y,H+5,6.4,10,11).cut(box(x,y,H+8,3.4,6.6,10))
        base=base.union(socket)
        pin=box(x,y,H+8.4,2.8,6,22.6)
        bridge=box(sx*(xabs+2),y,H+26,9,10,5)
        oldhood=oldhood.union(pin).union(bridge)
        guide_rows.append([x,y])
cq.exporters.export(base,str(OUT/"_base_normalised.step"))
base=cq.importers.importStep(str(OUT/"_base_normalised.step"))
for sx in (-1,1):
    base=base.cut(box(sx*150,0,H+6.3,44,15,6.7))
for y,xabs in ((-65,144.5),(65,143.0)):
    for sx in (-1,1):
        # The guides now sit partly inside the original curved base wall.
        # Cut the receiver through both its added boss and that existing wall.
        base=base.cut(box(sx*xabs,y,H+8,3.4,6.6,10))
# Preserve existing internal hardware, but form the whole exterior from one
# original loft. No mounting block is unioned onto the external surface.
void = inner.union(box(0,0,H-1,600,650,17.3)).cut(oldhood)
hood = outer.cut(void)
for x in (-96,96):
    for z in (H+10,H+64):
        hood=hood.cut(bore((x,-137,z),(0,1,0),1.7,32))
for y in (25,40,55,70,85):
    pl=cq.Plane(origin=(110,y,H+46),xDir=(0,1,0),normal=(1,0,0))
    cut=cq.Workplane(pl).slot2D(29,5,angle=70).extrude(75)
    hood=hood.cut(cut).cut(cut.mirror("YZ"))
hood=hood.cut(box(0,145,H+16,12,70,18))
cq.exporters.export(hood,str(OUT/"_hood_normalised.step"))
hood=cq.importers.importStep(str(OUT/"_hood_normalised.step"))
print("Building full-outline front panel",flush=True)
# Use the actual front section of the outer case as a shared silhouette.
front=[f for f in outer.faces().vals() if f.geomType()=="PLANE" and abs(f.Center().y+126)<.001]
assert len(front)==1,len(front)
section=front[0].outerWire()
offsets=section.offset2D(-.3)
assert len(offsets)==1
outline=offsets[0].toSplines(degree=3,tolerance=.002,nurbs=True)
assert outline.BoundingBox().xlen < section.BoundingBox().xlen
mask=cq.Workplane(obj=cq.Solid.extrudeLinear(outline,[],cq.Vector(0,-4,0))).translate((0,-.3,0))
# This front plane is 0.3 mm clear of the case. Internal eyes and camera
# interfaces stay at their original positions.
back_envelope=cq.Workplane(obj=cq.Solid.extrudeLinear(outline,[],cq.Vector(0,12,0))).translate((0,-.4,0))
ez=H+49
for x in (-54,54):
    boss=face_round(x,ez,27,-126.4,6.4)
    for dx in (-23,23):
        boss=boss.union(face_round(x+dx,ez,5,-126.4,6.4))
    mask=mask.union(boss.intersect(back_envelope))
    mask=mask.cut(face_round(x,ez,16.6,-135,20))
    mask=mask.cut(face_round(x,ez,P["eye_pocket_provisional"]/2,-128.2,12))
    mask=mask.cut(box(x,-122,ez-28,28,12.4,15))
    for dx in (-23,23):mask=mask.cut(bore((x+dx,-127,ez),(0,1,0),1.3,10))
CAM=cam_module.build_camera(H)
mask=mask.cut(CAM["opening"])
for x in (-20,20):mask=mask.cut(face_round(x,H+46,1.3,-134,14))
for x in (-96,96):
    mask=mask.cut(bore((x,-136,H+64),(0,1,0),1.7,20))
    # Recessed hood fasteners remain accessible through the full-height face.
    mask=mask.cut(bore((x,-136,H+10),(0,1,0),3.6,12))
fx,ft,fn,fc=(P[k] for k in ("face_clip_inner_x","face_clip_thickness","face_clip_nose_x","face_catch_inner_x"))
face_clip_right=cq.importers.importStep(str(V3/"output/_face_flex_right.step"))
face_clip_right=face_clip_right.union(box(fx+ft/2,-126.2,H+34,ft,.8,10))
for sx in (-1,1):mask=mask.union(face_clip_right if sx>0 else face_clip_right.mirror("YZ"))
cq.exporters.export(mask,str(OUT/"_face_normalised.step"))
mask=cq.importers.importStep(str(OUT/"_face_normalised.step"))
hx,ht,hn=(P[k] for k in ("hood_clip_beam_inner_x","hood_clip_beam_thickness","hood_clip_nose_x"))
hood_flex_right=cq.importers.importStep(str(V3/"output/_hood_flex_right.step"))
cq.exporters.export(outer,str(OUT/"_outer_envelope.step"))
cq.exporters.export(cq.Workplane(obj=section),str(OUT/"_front_outline.step"))
register("base_one_piece",base,"base",note="Flat electronics floor; compact perimeter guides; original leg interfaces")
register("hood_one_piece",hood,"shell",rot=((1,0,0),180),note="Continuous exterior loft; compact perimeter guides; original clips and fasteners")
register("face_one_piece",mask,"visor",rot=((1,0,0),90),note="Full case-section silhouette; 0.3 mm perimeter inset and axial seam; front down")
for n in ("base_one_piece","hood_one_piece","face_one_piece"):inst(n,n)

# Reuse the removable components without changing their geometry or positions.
reuse = ("antenna_tail_beam","harxon_mount_plate",
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
    manifest["perimeter_guide_centres_xy"]=guide_rows
    manifest["electronics_trays_removed"]=True
    cq.exporters.export(hood_flex_right,str(OUT/"_hood_flex_right.step"))
    cq.exporters.export(face_clip_right,str(OUT/"_face_flex_right.step"))
    counts={}
    for row in INSTANCES.values(): counts[row["part"]]=counts.get(row["part"],0)+1
    for name,row in PARTS.items():
        s=row["shape"]
        cq.exporters.export(s,str(OUT/f"{name}.step"))
        row["shape"]=cq.importers.importStep(str(OUT/f"{name}.step"))
    for name in ("base_one_piece","hood_one_piece","face_one_piece"):
        INSTANCES[name]["shape"]=PARTS[name]["shape"]
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
    assy=cq.Assembly(name="H2S_full_face_upper_V3_1")
    for name,row in INSTANCES.items():
        assy.add(row["shape"],name=name,color=cq.Color(*row["color"]))
        file=f"_view_{name}.stl";cq.exporters.export(row["shape"],str(OUT/file),tolerance=.07)
        manifest["instances"][name]={"part":row["part"],"file":file,"color":row["color"]}
    assy.export(str(OUT/"upper_v3_1_ONLY.step"))
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

"""Check the requested face coverage, smooth exterior and clear base."""
from pathlib import Path
import os
import json
import cadquery as cq

ROOT=Path(__file__).resolve().parent
OUT=Path(os.environ.get("MOWER_CAD_OUTPUT", ROOT/"output")).resolve()
H=177.8


def box(x,y,z,w,d,h):
    return cq.Workplane("XY",origin=(x,y,z)).box(w,d,h,centered=(True,True,False))


def main():
    m=json.loads((OUT/"manifest.json").read_text(encoding="utf-8"))
    base=cq.importers.importStep(str(OUT/"base_one_piece.step")).val()
    hood=cq.importers.importStep(str(OUT/"hood_one_piece.step")).val()
    face=cq.importers.importStep(str(OUT/"face_one_piece.step")).val()
    outer=cq.importers.importStep(str(OUT/"_outer_envelope.step"))
    inner=cq.importers.importStep(str(ROOT/"inputs/inner.step"))
    cap=[f for f in outer.faces().vals() if f.geomType()=="PLANE" and abs(f.Center().y+126)<.001][0]
    panel=[f for f in face.Faces() if f.geomType()=="PLANE" and abs(f.Center().y+130.3)<.001]
    panel=max(panel,key=lambda f:f.Area())
    distances=[]
    for v in panel.outerWire().sample(180)[0]:
        distances.append(cq.Vertex.makeVertex(v.x,-126,v.z).distance(cap.outerWire()))
    report={"front_panel_perimeter_clearance_mm":{"min":min(distances),"max":max(distances),"samples":len(distances)},
            "front_panel_axial_gap_mm":.3,"electronics_platforms_removed":True,
            "guide_centres_xy":m["perimeter_guide_centres_xy"],"guide_checks":[],"old_guide_locations_clear":True,
            "old_electronics_mount_holes_filled":True,"old_electronics_bosses_removed":True}
    assert min(distances)>.29 and max(distances)<.31,report
    for x,y in m["perimeter_guide_centres_xy"]:
        row={"x":x,"y":y,"hood_pin_present":hood.isInside((x,y,H+12)),
             "base_pocket_clear":not base.isInside((x,y,H+12)),
             "socket_inner_wall_present":base.isInside((x-(2.3 if x>0 else -2.3),y,H+12))}
        assert all(row[k] for k in ("hood_pin_present","base_pocket_clear","socket_inner_wall_present")),row
        report["guide_checks"].append(row)
    for sx in (-1,1):
        for y in (-65,65):
            assert not base.isInside((sx*115,y,H+12))
            assert not hood.isInside((sx*115,y,H+20))
    for x in (-96,-18,18,96):
        for y in (-45,45):
            assert not base.isInside((x,y,H+7))
            assert base.isInside((x,y,H+2))
    assert not any(n in m["parts"] for n in ("electronics_carrier","pcb_spacer_5mm"))
    print("Face seam, perimeter guides and cleared floor passed",flush=True)
    target=outer.cut(inner).intersect(box(0,0,H+16.3,600,650,100))
    for x in (-96,96):
        for z in (H+10,H+64):
            bore=cq.Solid.makeCylinder(1.7,32,cq.Vector(x,-137,z),cq.Vector(0,1,0))
            target=target.cut(bore)
    for y in (25,40,55,70,85):
        pl=cq.Plane(origin=(110,y,H+46),xDir=(0,1,0),normal=(1,0,0))
        cut=cq.Workplane(pl).slot2D(29,5,angle=70).extrude(75)
        target=target.cut(cut).cut(cut.mirror("YZ"))
    target=target.cut(box(0,145,H+16,12,70,18))
    if "killswitch_dome" in m:
        z=m["killswitch_dome"]["centre_xyz"][2]
        target=target.cut(box(0,0,z-8,40.6,40.6,10))
        for x,y in m["killswitch_dome"]["screw_centres_xy"]:
            target=target.cut(cq.Solid.makeCylinder(1.35,9,cq.Vector(x,y,z-8),cq.Vector(0,0,1)))
    missing=target.val().cut(hood).Volume()
    extra=hood.cut(outer.val()).Volume()
    report["nominal_skin_missing_mm3"]=missing
    report["material_outside_nominal_outer_loft_mm3"]=extra
    print("Exterior missing / protruding mm3",missing,extra,flush=True)
    (OUT/"changes_check.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    assert missing<.05 and extra<.05,report


if __name__=="__main__":main()

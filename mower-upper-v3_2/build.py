"""V3.2: contain the four perimeter receivers inside the original base skin.

Previous V3.1 files are the inputs. Only the base changes; all other printed
parts and their positions are carried forward byte-for-byte.
"""
from pathlib import Path
import os
import csv
import json
import cadquery as cq
import vtk

ROOT=Path(__file__).resolve().parent
OUT=Path(os.environ.get("MOWER_CAD_OUTPUT", ROOT/"output")).resolve()
PREV=ROOT/"inputs/v3_1"
H=177.8


def box(x,y,z,w,d,h):
    return cq.Workplane("XY",origin=(x,y,z)).box(w,d,h,centered=(True,True,False))


def main():
    m=json.loads((OUT/"manifest.json").read_text(encoding="utf-8"))
    original=cq.importers.importStep(str(PREV/"base_one_piece.step"))
    outer=cq.importers.importStep(str(PREV/"_outer_envelope.step"))
    inner=cq.importers.importStep(str(ROOT/"inputs/inner.step"))
    domain=outer.intersect(box(0,0,H-.1,600,650,16.1))
    # Keep the current interior features, but derive the complete outer rim
    # from the unbroken original loft rather than the square receiver boxes.
    base=domain.cut(inner.cut(original))
    for row in m["mounts"]:
        x,y,z=row["top"]
        pocket=box(0,0,H-.1,24.6,24.6,4.1).rotate((0,0,0),(0,0,1),row["angle"]).translate((x,y,0))
        base=base.cut(pocket)
        base=base.cut(cq.Solid.makeCylinder(2.75,7,cq.Vector(x,y,H-1),cq.Vector(0,0,1)))
    for x in (-30,30):
        for y in (90,115):
            base=base.cut(cq.Solid.makeCylinder(2.25,7,cq.Vector(x,y,H-1),cq.Vector(0,0,1)))
    for x in (-96,96):
        base=base.cut(cq.Solid.makeCylinder(1.7,30,cq.Vector(x,-135,H+10),cq.Vector(0,1,0)))
    # Trim the receivers and reapply their actual functional pockets/windows.
    cq.exporters.export(base,str(OUT/"_base_skin_rebuilt.step"))
    base=cq.importers.importStep(str(OUT/"_base_skin_rebuilt.step"))
    for sx in (-1,1):base=base.cut(box(sx*150,0,H+6.3,44,15,6.7))
    for x,y in m["perimeter_guide_centres_xy"]:
        base=base.cut(box(x,y,H+8,3.4,6.6,10))
    cq.exporters.export(base,str(OUT/"base_one_piece.step"))
    base=cq.importers.importStep(str(OUT/"base_one_piece.step"))
    assert len(base.solids().vals())==1 and base.val().isValid()
    added=base.val().cut(original.val()).Volume()
    removed=original.val().cut(base.val()).Volume()
    protruding=base.val().cut(outer.val()).Volume()
    report={"added_material_mm3":added,"removed_material_mm3":removed,
            "remaining_material_outside_outer_loft_mm3":protruding}
    (OUT/"base_trim_check.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    print(json.dumps(report,indent=2),flush=True)
    assert added<.05 and protruding<.05 and 150<removed<155,report
    cq.exporters.export(base,str(OUT/"_solid_base_one_piece.step"))
    b=base.val().BoundingBox()
    printable=base.translate((-(b.xmin+b.xmax)/2,-(b.ymin+b.ymax)/2,-b.zmin))
    path=OUT/"base_one_piece.stl"
    cq.exporters.export(printable,str(path),tolerance=.03,angularTolerance=.10)
    r=vtk.vtkSTLReader();r.SetFileName(str(path));r.Update()
    c=vtk.vtkCleanPolyData();c.SetInputConnection(r.GetOutputPort());c.ToleranceIsAbsoluteOn();c.SetAbsoluteTolerance(.00001);c.Update()
    w=vtk.vtkSTLWriter();w.SetFileName(str(path));w.SetInputConnection(c.GetOutputPort());w.SetFileTypeToBinary();w.Write()
    cq.exporters.export(base,str(OUT/m["instances"]["base_one_piece"]["file"]),tolerance=.03,angularTolerance=.10)
    row=m["parts"]["base_one_piece"]
    row["volume_cm3"]=base.val().Volume()/1000
    b=printable.val().BoundingBox();row["bbox_mm"]=[b.xlen,b.ylen,b.zlen]
    row["note"]="V3.2: all four guide receivers trimmed to smooth outer wall; internal interfaces unchanged"
    m["parameters"]["version"]="V3.2 base rim cleanup"
    assy=cq.Assembly(name="H2S_upper_V3_2")
    for n,r in m["instances"].items():
        s=cq.importers.importStep(str(OUT/f"_solid_{n}.step"))
        assy.add(s,name=n,color=cq.Color(*r["color"]))
    assy.export(str(OUT/"upper_v3_2_ONLY.step"))
    (OUT/"manifest.json").write_text(json.dumps(m,indent=2),encoding="utf-8")
    with (OUT/"print_list.csv").open("w",newline="",encoding="utf-8-sig") as f:
        w=csv.writer(f);w.writerow(["part","quantity","X_mm","Y_mm","Z_mm","note"])
        for n,r in m["parts"].items():w.writerow([n,r["quantity"],*[round(v,2) for v in r["bbox_mm"]],r["note"]])


if __name__=="__main__":main()

"""Apply final release-window cuts to the saved base without rebuilding lofts.

Same STEP-normalised final operation as build.py; retained for reproducibility.
"""
from pathlib import Path
import csv
import json
import cadquery as cq
import vtk

ROOT=Path(__file__).resolve().parent
OUT=ROOT/"output"
H=177.8


def main():
    m=json.loads((OUT/"manifest.json").read_text())
    s=cq.importers.importStep(str(OUT/"base_one_piece.step"))
    for x in (-150,150):
        cut=cq.Workplane("XY",origin=(x,0,H+6.3)).box(44,15,6.7,centered=(True,True,False))
        s=s.cut(cut)
    for y,xabs in ((-65,144.5),(65,143.0)):
        for sx in (-1,1):
            s=s.cut(cq.Workplane("XY",origin=(sx*xabs,y,H+8)).box(3.4,6.6,10,centered=(True,True,False)))
    s=s.clean()
    assert s.val().isValid() and len(s.solids().vals())==1
    for name in ("base_one_piece","_solid_base_one_piece"):
        cq.exporters.export(s,str(OUT/f"{name}.step"))
    b=s.val().BoundingBox()
    p=s.translate((-(b.xmin+b.xmax)/2,-(b.ymin+b.ymax)/2,-b.zmin))
    cq.exporters.export(p,str(OUT/"base_one_piece.stl"),tolerance=.045,angularTolerance=.12)
    cq.exporters.export(s,str(OUT/m["instances"]["base_one_piece"]["file"]),tolerance=.07)
    m["parts"]["base_one_piece"]["volume_cm3"]=s.val().Volume()/1000
    b=p.val().BoundingBox()
    m["parts"]["base_one_piece"]["bbox_mm"]=[b.xlen,b.ylen,b.zlen]
    assy=cq.Assembly(name="H2S_full_face_upper_V3_1")
    for n,row in m["instances"].items():
        solid=cq.importers.importStep(str(OUT/f"_solid_{n}.step"))
        assy.add(solid,name=n,color=cq.Color(*row["color"]))
    assy.export(str(OUT/"upper_v3_1_ONLY.step"))
    (OUT/"manifest.json").write_text(json.dumps(m,indent=2),encoding="utf-8")
    with (OUT/"print_list.csv").open("w",newline="",encoding="utf-8-sig") as f:
        w=csv.writer(f);w.writerow(["part","quantity","X_mm","Y_mm","Z_mm","note"])
        for n,r in m["parts"].items():w.writerow([n,r["quantity"],*[round(v,2) for v in r["bbox_mm"]],r["note"]])
    print("Final base volume cm3",s.val().Volume()/1000,flush=True)


if __name__=="__main__":main()

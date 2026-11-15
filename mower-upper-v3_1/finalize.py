"""Export meshes and assembly from canonical production STEP solids."""
from pathlib import Path
import csv
import json
import cadquery as cq
import vtk

ROOT=Path(__file__).resolve().parent
OUT=ROOT/"output"


def main():
    m=json.loads((OUT/"manifest.json").read_text())
    m["perimeter_guide_centres_xy"]=[[s*x,y] for y,x in ((-65,144.5),(65,143.0)) for s in (-1,1)]
    m["electronics_trays_removed"]=True
    for n,row in m["parts"].items():
        s=cq.importers.importStep(str(OUT/f"{n}.step"))
        assert len(s.solids().vals())==1 and s.val().isValid(),n
        row["volume_cm3"]=s.val().Volume()/1000
        p=s
        if n=="antenna_tail_beam":p=p.rotate((0,0,0),(0,1,0),90)
        if n.startswith("hood_") or n in ("TEST_hood_clip","TEST_face_catch"):
            p=p.rotate((0,0,0),(1,0,0),180)
        if n in ("face_one_piece","camera_cartridge","eye_rear_retainer","TEST_face_clip"):
            p=p.rotate((0,0,0),(1,0,0),90)
        b=p.val().BoundingBox();p=p.translate((-(b.xmin+b.xmax)/2,-(b.ymin+b.ymax)/2,-b.zmin))
        path=OUT/f"{n}.stl"
        cq.exporters.export(p,str(path),tolerance=.03,angularTolerance=.10)
        r=vtk.vtkSTLReader();r.SetFileName(str(path));r.Update()
        c=vtk.vtkCleanPolyData();c.SetInputConnection(r.GetOutputPort());c.ToleranceIsAbsoluteOn();c.SetAbsoluteTolerance(.00001);c.Update()
        w=vtk.vtkSTLWriter();w.SetFileName(str(path));w.SetInputConnection(c.GetOutputPort());w.SetFileTypeToBinary();w.Write()
        b=p.val().BoundingBox();row["bbox_mm"]=[b.xlen,b.ylen,b.zlen]
        if n in ("base_one_piece","hood_one_piece","face_one_piece"):
            cq.exporters.export(s,str(OUT/f"_solid_{n}.step"))
            cq.exporters.export(s,str(OUT/m["instances"][n]["file"]),tolerance=.03,angularTolerance=.10)
    assy=cq.Assembly(name="H2S_full_face_upper_V3_1")
    for n,row in m["instances"].items():
        s=cq.importers.importStep(str(OUT/f"_solid_{n}.step"))
        assy.add(s,name=n,color=cq.Color(*row["color"]))
    assy.export(str(OUT/"upper_v3_1_ONLY.step"))
    (OUT/"manifest.json").write_text(json.dumps(m,indent=2),encoding="utf-8")
    with (OUT/"print_list.csv").open("w",newline="",encoding="utf-8-sig") as f:
        w=csv.writer(f);w.writerow(["part","quantity","X_mm","Y_mm","Z_mm","note"])
        for n,r in m["parts"].items():w.writerow([n,r["quantity"],*[round(v,2) for v in r["bbox_mm"]],r["note"]])


if __name__=="__main__":main()

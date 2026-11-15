"""Mount the user's dome and strengthen its feathered lower edge."""
from pathlib import Path
import os
import csv
import hashlib
import json
import math
import cadquery as cq
import vtk

ROOT=Path(__file__).resolve().parent
OUT=Path(os.environ.get("MOWER_CAD_OUTPUT", ROOT/"output")).resolve()
Z=269.8
HOLES=[(-23.8,-24.2),(24.2,-24.2),(-23.8,23.8),(24.2,23.8)]


def box(x,y,z,w,d,h):
    return cq.Workplane("XY",origin=(x,y,z)).box(w,d,h,centered=(True,True,False))


def export_mesh(s,path,print_pose=False):
    if print_pose:
        b=s.val().BoundingBox();s=s.translate((-(b.xmin+b.xmax)/2,-(b.ymin+b.ymax)/2,-b.zmin))
    cq.exporters.export(s,str(path),tolerance=.025,angularTolerance=.10)
    r=vtk.vtkSTLReader();r.SetFileName(str(path));r.Update()
    c=vtk.vtkCleanPolyData();c.SetInputConnection(r.GetOutputPort());c.ToleranceIsAbsoluteOn();c.SetAbsoluteTolerance(.00001);c.Update()
    w=vtk.vtkSTLWriter();w.SetFileName(str(path));w.SetInputConnection(c.GetOutputPort());w.SetFileTypeToBinary();w.Write()
    return s


def main():
    m=json.loads((OUT/"manifest.json").read_text(encoding="utf-8"))
    original=cq.importers.importStep(str(ROOT/"references/user_killswitch_dome.step"))
    # 3 mm vertical skirt, then a gradual transition into the original shape.
    # The 44 mm central exclusion preserves the user's 40 mm cavity and text.
    wires=[cq.Wire.makeCircle(r,cq.Vector(0,0,Z+h),cq.Vector(0,0,1))
           for r,h in ((45.7,0),(45.7,3),(44.6,4.5),(41,7),(35.0,10))]
    reinforce=cq.Workplane(obj=cq.Solid.makeLoft(wires,True)).cut(box(0,0,Z-.1,44,44,10.2))
    dome=original.union(reinforce)
    for x,y in HOLES:
        dome=dome.cut(cq.Solid.makeCylinder(1,10,cq.Vector(x,y,Z),cq.Vector(0,0,1)))
    # A continuous axial groove: 2.6 mm width, 1.5 mm depth, 78 mm pitch dia.
    groove=cq.Workplane("XY",origin=(0,0,Z-.01)).circle(40.3).circle(37.7).extrude(1.51)
    dome=dome.cut(groove)
    cq.exporters.export(dome,str(OUT/"killswitch_dome.step"))
    dome=cq.importers.importStep(str(OUT/"killswitch_dome.step"))
    assert len(dome.solids().vals())==1 and dome.val().isValid()
    # Start with the approved V3.1 hood each time, keeping this script repeatable.
    hood=cq.importers.importStep(str(ROOT/"inputs/v3_1/hood_one_piece.step"))
    opening=box(0,0,Z-8,40.6,40.6,10)
    hood=hood.cut(opening)
    for x,y in HOLES:
        hood=hood.cut(cq.Solid.makeCylinder(1.35,9,cq.Vector(x,y,Z-8),cq.Vector(0,0,1)))
    cq.exporters.export(hood,str(OUT/"hood_one_piece.step"))
    hood=cq.importers.importStep(str(OUT/"hood_one_piece.step"))
    assert len(hood.solids().vals())==1 and hood.val().isValid()
    p=export_mesh(dome,OUT/"killswitch_dome.stl",True)
    b=p.val().BoundingBox()
    m["parts"]["killswitch_dome"]={"quantity":1,"test":False,"bbox_mm":[b.xlen,b.ylen,b.zlen],
        "volume_cm3":dome.val().Volume()/1000,"note":"User dome; reinforced 3 mm lower skirt; underside 2 mm cord groove; base down"}
    file="_view_killswitch_dome.stl"
    m["instances"]["killswitch_dome"]={"part":"killswitch_dome","file":file,"color":[.85,.27,.09]}
    export_mesh(dome,OUT/file)
    cq.exporters.export(dome,str(OUT/"_solid_killswitch_dome.step"))
    p=export_mesh(hood.rotate((0,0,0),(1,0,0),180),OUT/"hood_one_piece.stl",True)
    b=p.val().BoundingBox();row=m["parts"]["hood_one_piece"]
    row["bbox_mm"]=[b.xlen,b.ylen,b.zlen];row["volume_cm3"]=hood.val().Volume()/1000
    row["note"]="V3.1 hood with aligned 40.6 mm dome access opening and four Ø2.7 clearance holes; roof down"
    cq.exporters.export(hood,str(OUT/"_solid_hood_one_piece.step"))
    export_mesh(hood,OUT/m["instances"]["hood_one_piece"]["file"])
    samples={"TEST_dome_groove":dome.intersect(box(38,0,Z,16,18,4.5)),
             "TEST_dome_screw":dome.intersect(box(24.2,23.8,Z,9,9,12))}
    for n,s in samples.items():
        cq.exporters.export(s,str(OUT/f"{n}.step"))
        s=cq.importers.importStep(str(OUT/f"{n}.step"))
        assert s.val().isValid() and len(s.solids().vals())==1,n
        p=export_mesh(s,OUT/f"{n}.stl",True);b=p.val().BoundingBox()
        m["parts"][n]={"quantity":0,"test":True,"bbox_mm":[b.xlen,b.ylen,b.zlen],
                       "volume_cm3":s.val().Volume()/1000,"note":"Actual dome interface sample; base down"}
    # The visor now prints upright to preserve the user's raised front lip.
    s=cq.importers.importStep(str(OUT/"TEST_face_clip.step"))
    p=export_mesh(s,OUT/"TEST_face_clip.stl",True);b=p.val().BoundingBox()
    m["parts"]["TEST_face_clip"]["bbox_mm"]=[b.xlen,b.ylen,b.zlen]
    m["parts"]["TEST_face_clip"]["note"]="Actual face tab, printed upright like the revised visor"
    groove_area=2.6*1.5
    report={"centre_xyz":[0,0,Z],"dome_clear_square_mm":[40,40],"hood_clear_square_mm":[40.6,40.6],
        "original_switch_hole_diameter_mm":22,"dome_pilot_diameter_mm":2,"hood_clearance_hole_diameter_mm":2.7,
        "screw_centres_xy":HOLES,"pilot_blind_depth_mm":10,"skirt_height_mm":3,
        "cord_diameter_mm":2,"groove_width_mm":2.6,"groove_depth_mm":1.5,"groove_pitch_diameter_mm":78,
        "nominal_squeeze_percent":25,"nominal_gland_fill_percent":100*math.pi/groove_area,
        "nominal_cord_centreline_length_mm":78*math.pi,"physical_seal_and_switch_fit_test_required":True,
        "source_sha256":hashlib.sha256((ROOT/"references/user_killswitch_dome.step").read_bytes()).hexdigest()}
    m["killswitch_dome"]=report
    m["parameters"]["version"]="V3.2 smooth base, user eye mounts and cord-groove switch dome"
    # CAD control hulls can overestimate bounds of trimmed surfaces. Report
    # the actual print meshes, which also determine the bed-fit checks.
    for n,row in m["parts"].items():
        reader=vtk.vtkSTLReader();reader.SetFileName(str(OUT/f"{n}.stl"));reader.Update()
        bounds=reader.GetOutput().GetBounds()
        row["bbox_mm"]=[bounds[1]-bounds[0],bounds[3]-bounds[2],bounds[5]-bounds[4]]
    assy=cq.Assembly(name="H2S_upper_V3_2")
    for n,r in m["instances"].items():
        s=cq.importers.importStep(str(OUT/f"_solid_{n}.step"))
        assy.add(s,name=n,color=cq.Color(*r["color"]))
    assy.export(str(OUT/"upper_v3_2_ONLY.step"))
    (OUT/"manifest.json").write_text(json.dumps(m,indent=2),encoding="utf-8")
    (OUT/"dome_design.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    with (OUT/"print_list.csv").open("w",newline="",encoding="utf-8-sig") as f:
        w=csv.writer(f);w.writerow(["part","quantity","X_mm","Y_mm","Z_mm","note"])
        for n,r in m["parts"].items():w.writerow([n,r["quantity"],*[round(v,2) for v in r["bbox_mm"]],r["note"]])
    print(json.dumps(report,indent=2),flush=True)


if __name__=="__main__":main()

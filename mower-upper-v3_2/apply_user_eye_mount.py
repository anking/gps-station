"""Transfer only the user's eye bays into the V3.2 one-piece front panel."""
from pathlib import Path
import os
import csv
import hashlib
import json
import cadquery as cq
import vtk

ROOT=Path(__file__).resolve().parent
OUT=Path(os.environ.get("MOWER_CAD_OUTPUT", ROOT/"output")).resolve()
PREV=ROOT/"inputs/v3_1"
H=177.8


def box(x,y,z,w,d,h):
    return cq.Workplane("XY",origin=(x,y,z)).box(w,d,h,centered=(True,True,False))


def surface_error(a,b,label):
    # Coincident trimmed Onshape/OCC faces can defeat subtraction even when
    # they occupy the same geometry. Compare their boundary surfaces directly.
    meshes=[]
    for i,s in enumerate((a,b)):
        p=OUT/f"_check_{label}_{i}.stl"
        cq.exporters.export(s,str(p),tolerance=.005,angularTolerance=.06)
        r=vtk.vtkSTLReader();r.SetFileName(str(p));r.Update()
        meshes.append(r.GetOutput())
    errors=[]
    for i,j in ((0,1),(1,0)):
        d=vtk.vtkDistancePolyDataFilter();d.SetInputData(0,meshes[i]);d.SetInputData(1,meshes[j]);d.SignedDistanceOff();d.Update()
        errors.append(d.GetOutput().GetPointData().GetScalars().GetRange()[1])
    return max(errors)


def main():
    m=json.loads((OUT/"manifest.json").read_text(encoding="utf-8"))
    original=cq.importers.importStep(str(PREV/"face_one_piece.step"))
    user=cq.importers.importStep(str(ROOT/"references/user_visor_left.step"))
    ring=cq.importers.importStep(str(ROOT/"references/user_eye_retainer.step"))
    # The user panel's main front is Y=-130.0; V3.1's is -130.3.
    # Translate the complete local mount and its retainer by the same 0.3 mm,
    # retaining the user's raised lip, depths, optical offset and tiny pilots.
    user=user.translate((0,-.3,0))
    front=max([f for f in original.faces().vals() if f.geomType()=="PLANE" and abs(f.Center().y+130.3)<.001],key=lambda f:f.Area())
    silhouette=cq.Workplane(obj=cq.Solid.extrudeLinear(front.outerWire(),[],cq.Vector(0,18,0))).translate((0,-1,0))
    region=box(-54,-124.5,H+17.85,60,23,61)
    # Transfer the eye features, not the reference part's old outer-edge
    # rounding/rim. Keep a flat plate at the new visor's original perimeter.
    slab=box(-54,-128.3,H+17.85,60,4,61)
    negatives=slab.cut(user)
    kept=[]
    for solid in negatives.solids().vals():
        b=solid.BoundingBox()
        touches_edge=(b.xmin < -83.99 or b.xmax > -24.01 or b.zmax > H+78.84)
        if not touches_edge:kept.append(solid)
    plate=slab.cut(cq.Compound.makeCompound(kept))
    front_add=user.intersect(region).intersect(box(-54,-130.425,H+17.85,60,.45,61))
    rear_mask=cq.Workplane(obj=cq.Solid.makeCylinder(25.2,13.4,cq.Vector(-54,-126.4,H+48.35),cq.Vector(0,1,0)))
    for dx in (-23,23):
        rear_mask=rear_mask.union(cq.Solid.makeCylinder(5.2,13.4,cq.Vector(-54+dx,-126.4,H+49),cq.Vector(0,1,0)))
    rear_mask=rear_mask.union(box(-54,-119.7,H+20,30,13.4,19))
    rear_add=user.intersect(region).intersect(rear_mask)
    raw_patch=plate.union(front_add).union(rear_add)
    patch=raw_patch.intersect(silhouette)
    right_patch=raw_patch.mirror("YZ").intersect(silhouette)
    cq.exporters.export(patch,str(OUT/"_user_eye_patch.step"))
    patch=cq.importers.importStep(str(OUT/"_user_eye_patch.step"))
    cq.exporters.export(right_patch,str(OUT/"_user_eye_patch_right.step"))
    right_patch=cq.importers.importStep(str(OUT/"_user_eye_patch_right.step"))
    print("volumes",original.val().Volume(),patch.val().Volume(),"valid",patch.val().isValid(),silhouette.val().isValid(),flush=True)
    face=original.cut(region).cut(region.mirror("YZ"))
    face=face.union(patch).union(right_patch)
    cq.exporters.export(face,str(OUT/"face_one_piece.step"))
    face=cq.importers.importStep(str(OUT/"face_one_piece.step"))
    assert face.val().isValid() and len(face.solids().vals())==1
    report={"user_front_plane_shift_y_mm":-.3,"eyes_mirrored_from_user_left":True,
            "main_outline_retained":True,"centre_AI_camera_unchanged":True,"reference_outer_edge_rounding_excluded":True,
            "source_sha256":{},"local_eye_max_surface_error_mm":[],"retainer_geometry_difference_mm3":0}
    for filename in ("user_visor_left.step","user_eye_retainer.step"):
        report["source_sha256"][filename]=hashlib.sha256((ROOT/"references"/filename).read_bytes()).hexdigest()
    for sx in (-1,1):
        r=region if sx<0 else region.mirror("YZ")
        target=patch if sx<0 else right_patch
        # Validate the operative eye core and pilots against the user's part;
        # the panel perimeter is intentionally the newer unrounded outline.
        core=cq.Workplane(obj=cq.Solid.makeCylinder(24.5,23,cq.Vector(-54,-136,H+48.35),cq.Vector(0,1,0)))
        for dx in (-23,23):
            core=core.union(cq.Solid.makeCylinder(2.5,23,cq.Vector(-54+dx,-136,H+49),cq.Vector(0,1,0)))
        core=core.union(box(-54,-124.5,H+20,29,23,18))
        source=user
        if sx>0:core=core.mirror("YZ");source=user.mirror("YZ")
        actual=face.intersect(core)
        target=source.intersect(core)
        difference=surface_error(actual,target,f"eye_{sx}")
        report["local_eye_max_surface_error_mm"].append(difference)
        print("patch surface error mm",sx,difference,flush=True)
        assert difference<.025,difference
    middle=box(0,-124,H+17,47,25,63)
    a,b=face.intersect(middle),original.intersect(middle)
    delta=surface_error(a,b,"centre")
    report["centre_AI_camera_max_surface_error_mm"]=delta
    assert delta<.025,delta
    oldring=cq.importers.importStep(str(PREV/"_solid_eye_retainer_-54.step"))
    report["retainer_geometry_difference_mm3"]=ring.cut(oldring).val().Volume()+oldring.cut(ring).val().Volume()
    for sx in (-1,1):
        positioned=ring.translate((0,-.3,0))
        if sx>0:positioned=positioned.mirror("YZ")
        name=f"eye_retainer_{sx*54}"
        cq.exporters.export(positioned,str(OUT/f"_solid_{name}.step"))
        cq.exporters.export(positioned,str(OUT/m["instances"][name]["file"]),tolerance=.03,angularTolerance=.10)
    cq.exporters.export(face,str(OUT/"_solid_face_one_piece.step"))
    cq.exporters.export(face,str(OUT/m["instances"]["face_one_piece"]["file"]),tolerance=.03,angularTolerance=.10)
    # Upright print pose keeps the user's proud 0.25 mm bezel lip off the bed
    # and places the thin clip beams along the layer plane.
    b=face.val().BoundingBox()
    printable=face.translate((-(b.xmin+b.xmax)/2,-(b.ymin+b.ymax)/2,-b.zmin))
    path=OUT/"face_one_piece.stl"
    cq.exporters.export(printable,str(path),tolerance=.03,angularTolerance=.10)
    r=vtk.vtkSTLReader();r.SetFileName(str(path));r.Update()
    c=vtk.vtkCleanPolyData();c.SetInputConnection(r.GetOutputPort());c.ToleranceIsAbsoluteOn();c.SetAbsoluteTolerance(.00001);c.Update()
    w=vtk.vtkSTLWriter();w.SetFileName(str(path));w.SetInputConnection(c.GetOutputPort());w.SetFileTypeToBinary();w.Write()
    row=m["parts"]["face_one_piece"]
    row["volume_cm3"]=face.val().Volume()/1000
    b=printable.val().BoundingBox();row["bbox_mm"]=[b.xlen,b.ylen,b.zlen]
    row["note"]="User's eye mount mirrored to both sides; print UPRIGHT on bottom edge with brim and rear supports"
    m["parameters"]["version"]="V3.2 smooth base and user eye mounts"
    m["user_eye_mounts"]=report
    assy=cq.Assembly(name="H2S_upper_V3_2")
    for n,row in m["instances"].items():
        s=cq.importers.importStep(str(OUT/f"_solid_{n}.step"))
        assy.add(s,name=n,color=cq.Color(*row["color"]))
    assy.export(str(OUT/"upper_v3_2_ONLY.step"))
    (OUT/"manifest.json").write_text(json.dumps(m,indent=2),encoding="utf-8")
    (OUT/"user_eye_mount_check.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    with (OUT/"print_list.csv").open("w",newline="",encoding="utf-8-sig") as f:
        w=csv.writer(f);w.writerow(["part","quantity","X_mm","Y_mm","Z_mm","note"])
        for n,r in m["parts"].items():w.writerow([n,r["quantity"],*[round(v,2) for v in r["bbox_mm"]],r["note"]])
    print(json.dumps(report,indent=2),flush=True)


if __name__=="__main__":main()

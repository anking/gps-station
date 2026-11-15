"""Clearance checks with approximate flexed-tab envelopes, not FEA."""
from pathlib import Path
import json
import cadquery as cq

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "output"
H = 177.8


def load(name):
    return cq.importers.importStep(str(OUT / f"{name}.step")).val()


def pressed(body, leaf, kind):
    other = leaf.mirror("YZ")
    rest = body.cut(leaf).cut(other)
    moved = []
    for sign, s in ((1,leaf),(-1,other)):
        if kind == "hood":
            # 1.8 mm inward at the lower end, zero at the nominal root.
            k = sign * 1.8 / 27
            matrix = cq.Matrix([[1,0,k,-k*(H+36)], [0,1,0,0], [0,0,1,0], [0,0,0,1]])
        else:
            # 2 mm inward at the free end of a 28 mm face tab.
            k = -sign * 2 / 28
            matrix = cq.Matrix([[1,k,0,k*126], [0,1,0,0], [0,0,1,0], [0,0,0,1]])
        moved.append(s.transformGeometry(matrix))
    return [rest,*moved]


def main():
    base,hood,face = (load(n) for n in ("base_one_piece","hood_one_piece","face_one_piece"))
    hparts = pressed(hood,load("_hood_flex_right"),"hood")
    fparts = pressed(face,load("_face_flex_right"),"face")
    # The camera and eye retainers travel with the face; only the fixed hood
    # and base matter to the front-panel extraction envelope.
    report = {"approximate_tab_deflection_only":True,"force_or_fatigue_simulation":False,
              "hood_lower_tip_inward_mm":1.8,"face_free_tip_inward_mm":2.0,
              "hood_vertical_lift":[],"face_forward_pull":[]}
    for dz in (0,2,5,9,16,25):
        v = sum(s.translate((0,0,dz)).intersect(base).Volume() for s in hparts)
        # Face remains on the lifted hood. Its low pull lip stays forward of
        # the front base rail and must not clip the base during lifting.
        v += face.translate((0,0,dz)).intersect(base).Volume()
        report["hood_vertical_lift"].append({"lift_mm":dz,"interference_mm3":v})
        print("hood",dz,v,flush=True)
    for dy in (0,-2,-6,-15,-32):
        v = sum(s.translate((0,dy,0)).intersect(hood).Volume() for s in fparts)
        v += sum(s.translate((0,dy,0)).intersect(base).Volume() for s in fparts)
        report["face_forward_pull"].append({"pull_mm":-dy,"interference_mm3":v})
        print("face",dy,v,flush=True)
    (OUT/"removal_check.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    for a,b in (("TEST_hood_clip","TEST_hood_catch"),("TEST_face_clip","TEST_face_catch")):
        assy=cq.Assembly(name=a+"_fit")
        assy.add(load(a),name=a,color=cq.Color(.7,.77,.8))
        assy.add(load(b),name=b,color=cq.Color(.19,.23,.28))
        assy.export(str(OUT/f"{a}_ASSEMBLED.step"))
    assert all(r["interference_mm3"]<.02 for key in ("hood_vertical_lift","face_forward_pull") for r in report[key]),report


if __name__ == "__main__":
    main()

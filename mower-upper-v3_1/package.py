"""Package only validated V3 upper parts; no original legs or bought items."""
from pathlib import Path
import csv
import hashlib
import json
import zipfile

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "output"


def archive(filename, files):
    path = ROOT / filename
    with zipfile.ZipFile(path,"w",zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for src,name in files:
            z.write(src,name)
    print(path,flush=True)


def main():
    manifest=json.loads((OUT/"manifest.json").read_text())
    report=json.loads((OUT/"verification.json").read_text())
    motion=json.loads((OUT/"removal_check.json").read_text())
    changes=json.loads((OUT/"changes_check.json").read_text())
    assert changes["nominal_skin_missing_mm3"]<.05 and changes["material_outside_nominal_outer_loft_mm3"]<.05
    assert not report["intersections"] and not report["legacy_intersections"]
    assert all(r["closed_single_mesh"] for r in report["parts"].values())
    assert all(r["interference_mm3"]<.02 for key in ("hood_vertical_lift","face_forward_pull") for r in motion[key])
    production=[n for n,r in manifest["parts"].items() if not r["test"]]
    tests=[n for n,r in manifest["parts"].items() if r["test"]]
    docs=[(ROOT/"README.md","README.md"),(ROOT/"HARDWARE.md","HARDWARE.md"),
          (OUT/"print_list.csv","print_list.csv")]
    archive("Mower_V3_1_H2S_PETG_UPPER.zip",docs+
            [(OUT/f"{n}.stl",f"STL/{n}.stl") for n in production]+
            [(OUT/"upper_v3_1_ONLY.step","CAD/upper_v3_1_ONLY.step"),
             (OUT/"verification.json","checks/verification.json"),
             (OUT/"removal_check.json","checks/removal_check.json")]+
            [(OUT/"changes_check.json","checks/changes_check.json")]+
            [(OUT/f"{n}.png",f"previews/{n}.png") for n in ("concept","exploded","mounted","hood_inside","front_fit","base_top")])
    archive("Mower_V3_1_THREE_MAIN_PARTS.zip",docs+
            [(OUT/f"{n}_one_piece.stl",f"{n}_one_piece.stl") for n in ("base","hood","face")])
    archive("Mower_V3_1_PETG_FIT_TESTS.zip",docs+
            [(OUT/f"{n}.stl",f"{n}.stl") for n in tests]+
            [(OUT/f"{n}_ASSEMBLED.step",f"{n}_ASSEMBLED.step") for n in ("TEST_hood_clip","TEST_face_clip")])
    files=[ROOT/n for n in ("Mower_V3_1_H2S_PETG_UPPER.zip","Mower_V3_1_THREE_MAIN_PARTS.zip","Mower_V3_1_PETG_FIT_TESTS.zip")]
    files += [OUT/f"{n}.stl" for n in production+tests]+[OUT/"upper_v3_1_ONLY.step"]
    (ROOT/"SHA256SUMS.txt").write_text("\n".join(f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.relative_to(ROOT).as_posix()}" for p in files)+"\n",encoding="utf-8")


if __name__ == "__main__":
    main()

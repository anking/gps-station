"""Package only validated V3 upper parts; no original legs or bought items."""
from pathlib import Path
import os
import csv
import hashlib
import json
import zipfile

ROOT = Path(__file__).resolve().parent
OUT = Path(os.environ.get("MOWER_CAD_OUTPUT", ROOT / "output")).resolve()


DIST = Path(os.environ.get("MOWER_CAD_DIST", ROOT)).resolve()


def archive(filename, files):
    DIST.mkdir(parents=True,exist_ok=True)
    path = DIST / filename
    with zipfile.ZipFile(path,"w",zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for src,name in files:
            z.write(src,name)
    print(path,flush=True)


def main():
    manifest=json.loads((OUT/"manifest.json").read_text(encoding="utf-8"))
    report=json.loads((OUT/"verification.json").read_text(encoding="utf-8"))
    motion=json.loads((OUT/"removal_check.json").read_text(encoding="utf-8"))
    changes=json.loads((OUT/"changes_check.json").read_text(encoding="utf-8"))
    rim=json.loads((OUT/"base_trim_check.json").read_text(encoding="utf-8"))
    eyes=json.loads((OUT/"user_eye_mount_check.json").read_text(encoding="utf-8"))
    dome=json.loads((OUT/"dome_check.json").read_text(encoding="utf-8"))
    assert rim["remaining_material_outside_outer_loft_mm3"]<.05
    assert max(eyes["local_eye_max_surface_error_mm"])<.025 and eyes["centre_AI_camera_max_surface_error_mm"]<.025
    assert dome["groove_clear"] and dome["groove_floor_intact"] and dome["screw_pattern_aligned"]
    assert changes["nominal_skin_missing_mm3"]<.05 and changes["material_outside_nominal_outer_loft_mm3"]<.05
    assert not report["intersections"] and not report["legacy_intersections"]
    assert all(r["closed_single_mesh"] for r in report["parts"].values())
    assert all(r["interference_mm3"]<.02 for key in ("hood_vertical_lift","face_forward_pull") for r in motion[key])
    production=[n for n,r in manifest["parts"].items() if not r["test"]]
    tests=[n for n,r in manifest["parts"].items() if r["test"]]
    docs=[(ROOT/"README.md","README.md"),(ROOT/"HARDWARE.md","HARDWARE.md"),
          (OUT/"print_list.csv","print_list.csv")]
    archive("Mower_V3_2_H2S_PETG_UPPER.zip",docs+
            [(OUT/f"{n}.stl",f"STL/{n}.stl") for n in production]+
            [(OUT/"upper_v3_2_ONLY.step","CAD/upper_v3_2_ONLY.step"),
             (OUT/"verification.json","checks/verification.json"),
             (OUT/"removal_check.json","checks/removal_check.json")]+
            [(OUT/"changes_check.json","checks/changes_check.json")]+
            [(OUT/f"{n}.json",f"checks/{n}.json") for n in ("base_trim_check","user_eye_mount_check","dome_design","dome_check")]+
            [(OUT/f"{n}.step",f"CAD/individual/{n}.step") for n in production]+
            [(ROOT/"references"/f,f"references/{f}") for f in ("user_visor_left.step","user_eye_retainer.step","user_killswitch_dome.step")]+
            [(OUT/f"{n}.png",f"previews/{n}.png") for n in ("concept","exploded","mounted","hood_inside","front_fit","base_top","base_rim_fixed","eye_mount_detail","dome_detail","dome_mount")])
    replacement=("base_one_piece","hood_one_piece","face_one_piece","killswitch_dome")
    archive("Mower_V3_2_REPLACEMENT_PARTS.zip",docs+
            [(OUT/f"{n}.{ext}",f"{ext.upper()}/{n}.{ext}") for n in replacement for ext in ("stl","step")])
    archive("Mower_V3_2_THREE_MAIN_PARTS.zip",docs+
            [(OUT/f"{n}_one_piece.stl",f"{n}_one_piece.stl") for n in ("base","hood","face")])
    archive("Mower_V3_2_PETG_FIT_TESTS.zip",docs+
            [(OUT/f"{n}.stl",f"{n}.stl") for n in tests]+
            [(OUT/f"{n}_ASSEMBLED.step",f"{n}_ASSEMBLED.step") for n in ("TEST_hood_clip","TEST_face_clip")])
    files=[DIST/n for n in ("Mower_V3_2_H2S_PETG_UPPER.zip","Mower_V3_2_THREE_MAIN_PARTS.zip","Mower_V3_2_PETG_FIT_TESTS.zip","Mower_V3_2_REPLACEMENT_PARTS.zip")]
    files += [OUT/f"{n}.stl" for n in production+tests]+[OUT/"upper_v3_2_ONLY.step"]
    (DIST/"SHA256SUMS.txt").write_text("\n".join(f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {Path(os.path.relpath(p,DIST)).as_posix()}" for p in files)+"\n",encoding="utf-8")


if __name__ == "__main__":
    main()

"""Deliver STL of the UPPER assembly only; never package V1 legs or references."""
from pathlib import Path
import json
import zipfile
import cadquery as cq

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "output"


def main():
    manifest = json.loads((OUT / "manifest.json").read_text())
    report = json.loads((OUT / "verification.json").read_text())
    assert not report["intersections"] and not report["legacy_intersections"]
    assert not report["camera_component_intersections"]
    assert report["legacy_file_hashes_unchanged"]
    forbidden = ("clamp_", "side_arm_", "front_dogleg")
    assert all(not n.startswith(forbidden) for n in manifest["parts"])

    assembly = cq.importers.importStep(str(OUT / "upper_v2_ONLY.step"))
    cq.exporters.export(assembly, str(OUT / "upper_v2_assembled_VIEW_ONLY.stl"),
                        tolerance=.045, angularTolerance=.12)
    with zipfile.ZipFile(ROOT / "upper_v2_PRINT_STL_ONLY.zip", "w", zipfile.ZIP_DEFLATED) as z:
        for n, row in manifest["parts"].items():
            folder = "FIT_TEST_STL" if row["test"] else "PRINT_STL"
            z.write(OUT / f"{n}.stl", f"{folder}/{n}.stl")
        z.write(ROOT / "README.md", "README_RU.md")
        z.write(OUT / "print_list.csv", "print_list.csv")
        z.write(OUT / "verification.json", "verification.json")
    small = ("TEST_legacy_socket", "TEST_eye_seat", "eye_rear_retainer", "camera_cartridge", "harxon_mount_plate")
    with zipfile.ZipFile(ROOT / "upper_v2_FIRST_FIT_STL.zip", "w", zipfile.ZIP_DEFLATED) as z:
        for n in small:
            z.write(OUT / f"{n}.stl", f"{n}.stl")
        z.write(ROOT / "README.md", "README_RU.md")
    for name in ("upper_v2_PRINT_STL_ONLY.zip", "upper_v2_FIRST_FIT_STL.zip"):
        path = ROOT / name
        with zipfile.ZipFile(path) as z:
            assert z.testzip() is None
            assert not any(Path(n).name.startswith(forbidden) for n in z.namelist())
            assert not any(n.lower().endswith((".step", ".png", ".pdf")) for n in z.namelist())
        print(f"{path}: {path.stat().st_size} bytes")
    print(OUT / "upper_v2_assembled_VIEW_ONLY.stl")


if __name__ == "__main__":
    main()

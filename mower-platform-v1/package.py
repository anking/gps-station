"""Package only this design; never include unrelated project files or secrets."""
from pathlib import Path
import json
import zipfile

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "output"
MANIFEST = json.loads((OUT / "manifest.json").read_text())


def main():
    report = json.loads((OUT / "verification.json").read_text())
    assert not report["collisions"] and not report["reference_interferences"]
    files = [ROOT / n for n in ("README.md", "parameters.json", "hardware.csv", "build.py",
                                "verify.py", "render.py", "render_details.py", "package.py")]
    for path in OUT.iterdir():
        if not path.name.startswith("_") and path.suffix in (".stl", ".step", ".png", ".json", ".csv"):
            files.append(path)
    with zipfile.ZipFile(ROOT / "mower_platform_v1.zip", "w", zipfile.ZIP_DEFLATED) as z:
        for p in files:
            z.write(p, p.relative_to(ROOT))
    with zipfile.ZipFile(ROOT / "first_fit_tests.zip", "w", zipfile.ZIP_DEFLATED) as z:
        z.write(ROOT / "README.md", "README.md")
        z.write(ROOT / "hardware.csv", "hardware.csv")
        for name in [n for n in MANIFEST["parts"] if n.startswith("TEST_")] + ["clamp_lower"]:
            z.write(OUT / f"{name}.stl", f"{name}.stl")
            z.write(OUT / f"{name}.step", f"{name}.step")
    for n in ("mower_platform_v1.zip", "first_fit_tests.zip"):
        path = ROOT / n
        with zipfile.ZipFile(path) as z:
            assert z.testzip() is None
        print(f"{path}: {path.stat().st_size} bytes")


if __name__ == "__main__":
    main()

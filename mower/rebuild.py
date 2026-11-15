"""Rebuild and validate the latest mower design from tracked inputs only."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys

REPO = Path(__file__).resolve().parent.parent
DESIGN = REPO / "mower-upper-v3_2"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DESIGN / "output",
                        help="An empty destination directory; existing exports are never overwritten.")
    parser.add_argument("--skip-render", action="store_true", help="Build and check geometry without preview images.")
    parser.add_argument("--package", action="store_true", help="Also write ZIP bundles into OUTPUT/packages.")
    args = parser.parse_args()
    if args.package and args.skip_render:
        parser.error("--package requires rendered preview images")
    output = args.output.resolve()
    if output.exists() and any(output.iterdir()):
        parser.error(f"Output directory is not empty: {output}; choose another --output directory")
    checksums = json.loads((DESIGN / "inputs/checksums.json").read_text(encoding="utf-8"))
    for relative, expected in checksums.items():
        path = DESIGN / relative
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise RuntimeError(f"Source input checksum mismatch: {relative}")
    output.mkdir(parents=True, exist_ok=True)
    for path in (DESIGN / "inputs/v3_1").iterdir():
        shutil.copy2(path, output / path.name)
    env = os.environ.copy()
    env["MOWER_CAD_OUTPUT"] = str(output)
    env["MOWER_CAD_DIST"] = str(output / "packages")
    env["PYTHONUTF8"] = "1"
    stages = ["build.py", "apply_user_eye_mount.py", "add_killswitch_dome.py",
              "verify.py", "verify_changes.py", "check_removal.py", "verify_dome.py"]
    if not args.skip_render:
        stages.append("render.py")
    if args.package:
        stages.append("package.py")
    logs = output / "logs"
    logs.mkdir(exist_ok=True)
    for stage in stages:
        print(f"Running {stage}", flush=True)
        log_path = logs / f"{Path(stage).stem}.log"
        with log_path.open("w", encoding="utf-8") as log:
            result = subprocess.run([sys.executable, str(DESIGN / stage)], cwd=REPO,
                                    env=env, stdout=log, stderr=subprocess.STDOUT)
        if result.returncode:
            print(log_path.read_text(encoding="utf-8", errors="replace")[-8000:], file=sys.stderr)
            raise SystemExit(f"Failed {stage}; full log: {log_path}")
    print(f"Built and verified V3.2: {output}", flush=True)


if __name__ == "__main__":
    main()

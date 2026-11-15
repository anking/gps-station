# Robot mower CAD

The current design is [V3.2](../mower-upper-v3_2/README.md): a one-piece base, hood and visor for PETG on Bambu H2S, the user's eye mounts on both sides, and a reinforced switch dome with a cord gland. Original tripod legs remain compatible. [Hardware and fit notes](../mower-upper-v3_2/HARDWARE.md) describe the physical prototype limits.

The other `mower-*` folders retain earlier design scripts, parameters and documentation. The latest rebuild does **not** require their generated outputs. Its accepted V3.1 baseline is frozen under `mower-upper-v3_2/inputs/`, with the user's original edited STEP parts under `references/`.

## What is tracked

- Build, rendering, packaging and verification scripts; parameters, hardware lists and documentation.
- The exact baseline geometry and meshes required by the incremental V3.2 builders and compatibility checks. These are source inputs to this revision, even though the earlier revision originally generated them.
- The user's original visor, retaining-ring and switch-dome STEP files, plus the camera reference brief used by the earlier design.

Generated `output/` folders, ZIP bundles, logs, Python caches and generated checksum lists are ignored. Finished print packages can be regenerated or distributed as release attachments. Local editor settings and unrelated firmware files are not part of this design change.

## Rebuild a fresh checkout

The pinned environment used for the CAD is Python 3.13.7 on Windows. Preview labels use Windows Segoe UI fonts.

```powershell
python -m venv .cad-venv
.\.cad-venv\Scripts\python.exe -m pip install -r mower\requirements.txt
.\.cad-venv\Scripts\python.exe mower\rebuild.py --package
```

The command verifies input checksums, seeds a new output directory, rebuilds the base, transfers the user's eye mounts, mounts the dome, runs all four verification programs, renders the previews and creates ZIP packages. Outputs go to `mower-upper-v3_2/output/`; packages go to its `packages/` subfolder.

An existing output directory is never overwritten. To rebuild alongside local exports:

```powershell
.\.cad-venv\Scripts\python.exe mower\rebuild.py --output .cad-tmp\mower-rebuild --package
```

Use `--skip-render` without `--package` for geometry-only verification. Individual scripts accept `MOWER_CAD_OUTPUT` and the packager also accepts `MOWER_CAD_DIST`; the rebuild command sets both automatically.

The checks cover valid connected solids, closed printable meshes, bed envelopes, assembly intersections, unchanged leg interfaces, the front seam, exact transferred eye details, approximate clip-release paths and the dome's groove/mounting alignment. They do not establish structural rating, fatigue life, actual electronics fit or a water-seal rating. Print the fit coupons before full parts.

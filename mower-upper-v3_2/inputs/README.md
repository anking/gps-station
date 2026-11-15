# Frozen source geometry for V3.2

`v3_1/` is the self-contained accepted V3.1 baseline consumed by the incremental V3.2 builders: named part STEP files, positioned assembly instances, clip envelopes, reference/context meshes and their manifest. The seed meshes preserve the accepted printing orientation of unchanged parts. This baseline is source input, not newly generated V3.2 output.

`legacy_v1/` contains the exact original leg/clamp STL files whose hashes are checked, plus the two original body STEP files used to compare the material and cutouts at all three leg interfaces.

`inner.step` is the original inner loft used to reconstruct the smooth outer skins. The corresponding accepted outer envelope is in `v3_1/_outer_envelope.step`.

The user's three original edited STEP files are in `../references/`. `checksums.json` covers these references and all frozen geometry/manifest inputs. Git attributes preserve their bytes across line-ending settings. `mower/rebuild.py` checks these hashes before building.

# Mower upper V3.2 - corrected base, user eye mounts and switch dome

Build this revision from a fresh checkout using the [mower rebuild guide](../mower/README.md). Generated print packages and previews are not stored in Git.

Use the matching V3.2 base, hood and front visor together, plus the new switch dome. The legs, frame clamps, antenna fork and camera cassette remain compatible. The two eye retaining rings have unchanged geometry and can be reused; the assembly STEP places them 0.3 mm farther forward to match the revised mounts.

## Changes included

- All four triangular guide-block protrusions are removed from the base rim. Its outer wall is smooth; guide locations and functional pockets remain unchanged.
- The round-eye mounting details from your supplied visor STEP are applied to both eyes: stepped recesses, small screw pilots, countersink/transition shapes and raised front lips. The one-piece visor's outer outline and its 0.3 mm fitting seam remain. The small centre AI Camera mounting area is unchanged.
- The switch dome is centred at X=0, Y=0 on the flat hood top, with its mounting plane at Z=269.8 mm. Its original 40 x 40 mm internal cavity, 22 mm top switch hole and four slightly offset screw positions are preserved. The hood has a matching 40.6 x 40.6 mm access opening and four 2.7 mm clearance holes.
- The dome has a 3 mm vertical lower skirt instead of a feathered edge, then transitions into the original upper shape. The skirt adds only 0.2 mm to the original radius: new footprint diameter 91.4 mm, height still 29 mm.
- A continuous underside groove accepts 2 mm round O-ring cord: 2.6 mm wide, 1.5 mm deep, 78 mm pitch diameter. Nominal cord length on the groove centreline is about 245 mm; trim and splice according to the cord supplier's instructions.

The outward alignment guides and clear electronics floor from V3.1 remain. No electronics platforms, loose PCB spacers or tray mounting pedestals are included. The three original leg sockets and antenna beam attachments remain unchanged.

## Files and printing

The replacement-parts ZIP contains the four revised parts in STL and STEP: base, hood, visor and switch dome. The full-upper ZIP contains all eight unique production parts, the assembly STEP, original reference STEP files, checks and preview images. The fit-test ZIP contains seven small interface samples.

| Part | Quantity | STL orientation |
|---|---:|---|
| base_one_piece | 1 | Flat underside down |
| hood_one_piece | 1 | Roof exterior down; support curved edges/internal overhangs |
| face_one_piece | 1 | UPRIGHT on its bottom edge, with brim and rear-feature supports |
| killswitch_dome | 1 | Base down; keep supports out of the cord groove |
| antenna_tail_beam | 2 | Side down |
| harxon_mount_plate | 1 | Flat down |
| eye_rear_retainer | 2 | Flat down; existing V3.1 rings can be reused |
| camera_cartridge | 1 | Front down; unchanged |

The visor prints upright to preserve the user's proud front eye lips and keep its clip beams along the layer plane. This is a change from the older face-down STL orientation. Inspect rear support placement and keep the tiny pilots clear.

All files use millimetres and sit on Z=0. Actual STL envelopes fit within 330 x 310 x 340 mm, leaving 5 mm per side for a brim on the H2S 340 x 320 x 340 mm bed. Actual sliced supports, brims and reserved areas must also fit. print_list.csv reports dimensions measured from the exported meshes.

Print one of each TEST file first; their assembly quantity is zero because they are not installed. TEST_dome_groove is an actual cropped section of the 2 mm cord gland. TEST_dome_screw uses the actual blind pilot. Other coupons cover the clips, catches and M3 nut seat. The face-clip coupon is now upright like the visor.

A calibrated PETG profile with 0.4 mm nozzle, 0.20 mm layers, 5 walls, 6 top/bottom layers and 25-30% infill is a starting point. Use the filament maker's temperatures and inspect thin walls/supports in the slicer. Correct dimensional error or fused tabs before the full prints.

## Assembly and service

The hood and visor retain two clips and two M3 x 12 button-head screws each, with four ordinary M3 nuts total. The two larger lower visor openings provide access to the recessed hood screw heads. The two upper screws hold the visor. The side release windows are intentional.

Fit the dome to the hood using its four preserved blind 2 mm pilots. A preliminary fastener choice is four 2.5 x 8 mm thread-forming screws FOR PLASTIC, inserted from inside the hood with small washers. With the 3.5 mm roof this gives about 4.5 mm engagement in the 10 mm blind pilots. Test the actual screws in the sample; do not substitute long screws that bottom out.

For the eye rings, use the screws/washer arrangement matching your supplied prototype. The revised visor contains 1.2 mm pilots; the old generic 3 x 8 mm eye-ring screw recommendation is no longer applicable without rechecking. The retaining rings themselves still have 3.4 mm clearance holes. This intentionally preserves your STEP geometry rather than changing hole sizes to suit an assumed screw.

The camera cassette and camera PCB keep their prior hardware. See HARDWARE.md for the full list.

To lift the hood, remove its two lower screws through the access openings, press the side tabs inward and lift vertically. Disconnect the face and switch wiring before fully removing it. To remove the visor, remove its two upper screws and gently release the face tabs. The switch-dome screws are accessible from inside the removed hood.

## Cord gland and remaining physical checks

The 1.5 mm gland depth gives 25% nominal compression of 2 mm cord when the dome's flat land contacts the hood. The nominal gland fill is 80.6%. These are design calculations, not a measured water-seal result. They follow the static face-seal range in [Parker's face-seal gland guidance](https://www.parker.com/content/dam/Parker-com/Literature/O-Ring-Division-Literature/O-Ring-ehandbook-pdfs/Design-chart-4-3-for-O-ring-face-seal-glands.pdf); [Parker's handbook](https://www.parker.com/content/dam/Parker-com/Literature/O-Ring-Division-Literature/ORD-5700.pdf) also discusses gland fill.

Check the actual cord diameter/hardness, splice, groove finish, hood flatness and compression using the samples and a physical fit. The top switch itself also needs its own suitable mounting seal. The housing's side ventilation remains open; no waterproof rating is claimed.

Check combined sliced print mass plus actual electronics and antenna against the earlier 1 kg target. Structural load capacity, clip fatigue, vibration and engine heat exposure remain physical prototype checks.

## CAD replacement and verification

Save a copy of the existing CAD project. Replace the old base, hood and visor, remove obsolete electronics trays/spacers, and insert the new dome. Import upper_v3_2_ONLY.step in original coordinates without scaling or automatic centring. Individual STEP files are also provided. Existing leg interfaces remain at Z=177.8 mm above the frame tubes; GPS centre stays at X=0, Y=218.775 mm.

The checks cover connected watertight meshes, CAD validity, print envelopes, part clearances, unchanged leg interfaces, base protrusion removal, the front fitting seam, transferred eye geometry, approximate clip-release paths and the dome gland/mounting pattern. The original user STEP references and their hashes are retained for comparison. The kill-switch electrical function is outside this mechanical model.

# Mower upper housing V3.1 — corrected face, perimeter guides, clear base

This version supersedes V3. Replace **all three main parts** together: base, hood and face. V3.1 keeps the original legs, their mounting interfaces, the rear antenna location, eye spacing and AI Camera cassette.

## What changed

- The front face follows the actual curved cross-section of the case. It covers the sides, top and bottom of the opening, with a nominal **0.3 mm perimeter inset and 0.3 mm axial fitting gap**. It is no longer a rounded rectangle sitting inside a larger opening.
- The hood exterior is formed from one continuous outer loft. The two upper-edge bumps and the small outer patch caused by the old support intersections are removed; internal mounting features are retained inside that skin.
- Four compact alignment guides move from X=±115 mm to **X=±144.5 mm at Y=-65**, and **X=±143 mm at Y=+65**. Their pockets nest in the base wall. This moves their centres outward by 28–29.5 mm per side.
- Both electronics platforms, all four loose PCB spacers and eight tray-mount pedestals are removed. The old eight tray bolt/nut holes are filled. The central base floor is flat; no new electronics hole pattern is imposed.

The three original leg interfaces and four rear antenna beam holes remain. Antenna beams and antenna mounting plate are structural antenna components and are retained.

## Download contents and print quantities

The three-main-parts ZIP contains only the base, hood and face STL files plus instructions. The full-upper ZIP also contains the unchanged antenna and optical mounting accessories, the assembly STEP, preview images and verification reports. The fit-test ZIP contains the small PETG samples and their assembly STEP guides.

| STL | Quantity | Print orientation already applied |
|---|---:|---|
| base_one_piece | 1 | Flat underside down |
| hood_one_piece | 1 | Roof exterior down; support curved edges and internal overhangs |
| face_one_piece | 1 | Flat front down |
| antenna_tail_beam | 2 | Side down |
| harxon_mount_plate | 1 | Flat down |
| eye_rear_retainer | 2 | Flat face down |
| camera_cartridge | 1 | Front down |

There are 9 installed printed parts, 7 unique production STL files. The legacy legs are not in the package. Test pieces have assembly quantity zero because they are not installed; print **one of each TEST file** for fit trials.

The old electronics_carrier and pcb_spacer_5mm files must not be inserted in the V3.1 assembly. They are excluded from these archives.

## Cover attachment and service

The hood and face each have two clips and two M3×12 button-head retaining screws. Use four ordinary M3 hex nuts total; no heat-set inserts or printed metal-screw threads are required.

1. Insert the two lower hood nuts into their pockets behind the front base rail. Lower the hood onto the four perimeter receivers; the side clips engage.
2. Install the two hood screws through the front base rail. **The two larger lower holes in the new face are access holes for these recessed screw heads**, so the hood screws remain accessible with the face fitted.
3. Insert the two upper face nuts into their inward-facing hood slots. Install the displays and camera in the removed face; push the face into position until its two tabs engage.
4. Fit the two upper M3×12 face screws. Use low button heads without added washers here.
5. To remove the hood, remove its two lower screws through the access holes, press the side tabs inward through the base windows and lift vertically. Disconnect face electronics before lifting it away completely.
6. To remove only the face, remove its two upper screws and gently pull its projecting edge forward. The sloped detents are intended to release by flexing inward. If the PETG samples require excessive force, remove the hood and press the face tabs from inside; correct the fit before relying on pull release.

The two internal LCD retainers still use four small screws, and the camera uses its original small fasteners. These stay assembled when the complete face is removed. Secure the covers with their retaining screws during mower use; screw-free vibration retention has not been validated.

## PETG printing and fit trials

All STL files use millimetres, sit on Z=0, and are checked against 330×310×340 mm, allowing a 5 mm brim per side within the H2S 340×320×340 mm build volume. Confirm the actual sliced layout, supports and reserved bed areas.

Print the small clip and nut-seat samples first. They are cropped from the actual interfaces and oriented like their parent parts. Pair each clip with its matching catch using the original-coordinate sample STEP as a positioning guide. The guide pockets have 0.3 mm side clearance and 0.4 mm bottom clearance. Hood tabs are 1.8 mm thick; face tabs are 1.6 mm thick. Keep these sections solid and remove support scars from mating surfaces.

A starting point is a calibrated 0.4 mm nozzle / 0.20 mm PETG profile with 5 walls, 6 top/bottom layers and 25–30% infill. Use the filament maker's temperatures. Inspect thin walls and support separation in the slicer. Correct first-layer spread or dimensional error before printing the full shell; do not force fused tabs.

## CAD replacement

Save a copy of your existing CAD project. Remove/suppress the old upper parts, including the obsolete electronics trays and spacers. Import **upper_v3_1_ONLY.step** in original coordinates, without scaling or automatic centring, alongside the unchanged legs. Replace all three main parts together: the new edge guides require their matching new base and hood. Use STEP for CAD and STL for slicing.

Mounting plane remains Z=177.8 mm above the frame tube tops. Original square leg sockets are 24.6 mm with Ø5.5 M5 holes at the same positions and angles. Harxon GPS1000 remains at X=0, Y=218.775 mm, over the rear crossmember. The frame and existing offset front leg are unchanged.

## Checks and remaining physical trials

verification.json covers STEP/STL validity, connected closed meshes, print envelopes, part intersections, original leg file hashes and material comparison at the three leg interfaces. changes_check.json additionally checks the front seam, new guide positions, cleared floor, filled tray holes and hood material against the original smooth outer skin. removal_check.json checks approximate flexed-tab clearance envelopes; it is not a stress or force simulation.

The LCD pockets remain provisional Ø39.5 mm until the actual AITRIP PCB/header dimensions are confirmed. The factory Raspberry Pi AI Camera lens is retained; no extra photographic lens is needed.

This is a fit prototype. Check combined sliced print mass plus actual electronics and antenna against the earlier 1 kg total target. Physical clip force, fatigue, vibration retention, engine heat exposure and water resistance remain untested. The open ventilation slots have no waterproof rating. Engine, battery and wheel envelopes in the mounted preview are approximate.

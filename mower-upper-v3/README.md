# Mower upper housing V3 — Bambu H2S / PETG

This revision replaces the tiled V2 base, hood and front mask with **three single-piece prints**. Existing V1 legs and clamps are unchanged. The rear antenna fork, antenna plate, electronics trays, LCD retainers and AI-camera cassette are reused unchanged from V2.

## Files and quantity

Use the STL files in `output` or the production ZIP. They are in millimetres, placed on Z=0 and oriented for printing. The assembly STEP is for CAD editing and checking placement; it contains the upper assembly only, in the original frame coordinates. Import it alongside the existing legs without centring or rescaling it.

- `base_one_piece.stl`: print 1, flat underside down.
- `hood_one_piece.stl`: print 1, roof exterior down. The small top plateau is on the bed; use a brim and supports for the curved roof edges and internal overhangs. Do not support the outside of the clip beams against the catch surfaces.
- `face_one_piece.stl`: print 1, front down. The two display openings and camera opening are already cut; support the rear-facing features as needed.
- Antenna tail beam: 2; Harxon mounting plate: 1; electronics carrier: 2; PCB spacer: 4; LCD rear retainer: 2; camera cartridge: 1.

The printer build volume is 340 × 320 × 340 mm. The exported parts are checked against **330 × 310 × 340 mm**, leaving 5 mm per side for a brim in XY. Check the actual sliced bed layout and the printer's reserved areas before printing.

## Hood assembly and removal

1. Place one ordinary M3 hex nut in each lower front hood pocket. These pockets are on the **hood**, behind the front base rail. Test the supplied nut-seat sample with the actual nuts; trim the tiny retention nubs if necessary.
2. Lower the hood straight onto the base. Four rectangular guides align it. The two side tabs deflect inward, then engage their base catches.
3. Fit **two M3 × 12 mm button-head screws** through the front base rail, below the removable face, into the hood's captive nuts. These secure it during mower use.
4. To remove it, take out both screws. Press the side tabs inward through the two lower side access windows and lift the hood vertically. Disconnect camera/display cables before lifting it away completely.

The clips locate and retain the cover during servicing; the supplied design uses the two screws during operation. Screw-free use has not been vibration-tested.

## Front face assembly and removal

1. Install the displays and camera in the removed face. The original two internal LCD retainers and camera cassette still use their small screws; these do not need removing when taking off the complete face.
2. Insert one M3 nut into each **upper** front hood pocket from its inward-facing loading slot.
3. Push the face rearward into the hood aperture until its two side detents engage. Fit **two M3 × 12 mm button-head screws**, one near each upper outside corner. Use low heads, without added washers here, to preserve the available screw engagement.
4. For removal, take out the two face screws and pull the lower lip forward gently. The sloped detents are intended to cam inward and release. If your PETG sample is too stiff to release with a light pull, remove the hood, reach inside and press the two face tabs toward the centre while pulling the face forward. Adjust the fit before relying on external pull release. Unplug the electronics as required.

There are **four externally accessible cover screws total**, two for each removable cover. The eye surround is part of the single front face; there are no separately removable external eye bezels.

## PETG fit trials and slicing

Start with the five `TEST_*.stl` files, not the complete hood. Print one of each test file; their quantity is listed as zero in the assembly list because they are not installed on the mower. Each is cropped from the actual mating geometry and has the same print orientation as its parent. The catch coupons are separate samples: hold each catch in its original relation to its matching clip; the comparison STEP contains their original coordinates. Do not glue coupons together.

- Hood beam: 1.8 mm thick, 14 mm wide; face beam: 1.6 mm thick, 10 mm high. Keep these sections solid and free of support scars.
- The four hood guides have 0.3 mm clearance per side and 0.4 mm bottom clearance. PETG dimensional accuracy, elephant's foot and extrusion width affect the result.
- A starting point is a 0.4 mm nozzle, 0.20 mm layers, 5 walls, 6 top/bottom layers and 25–30% infill. Use the filament maker's temperatures and a calibrated PETG profile. Inspect thin-wall generation in the slicer; the clips must be continuous solid walls.
- Use supports only where needed. In roof-down orientation, keep the clip-to-wall gaps clear and remove all support material before flexing the tabs.
- If the sample binds, correct extrusion/first-layer spread or adjust the clearances before printing the full shell. Do not force a tab that has fused to its surroundings.

No heat-set inserts, glue or printed threads are needed for the four external cover screws. Use ordinary metal M3 nuts in the printed pockets.

## Preserved geometry

The three leg sockets remain 24.6 mm square, with Ø5.5 mm M5 mounting holes at the same angles and coordinates as V1. Mounting plane: Z = 177.8 mm above the frame tube tops. Frame dimensions remain 635 × 463.55 mm with 26 mm square tube. The offset front leg and two side legs are not redesigned.

To replace the old upper in your CAD project, first duplicate/save a copy of that project. Remove or suppress only the old upper parts. Import `upper_v3_ONLY.step` using the original coordinates, without scaling or automatic centring; the base sockets then occupy the same positions relative to the existing legs. Reuse the three original base-to-leg fasteners/mates. STL files are for the slicer; use STEP for CAD assembly work.

Harxon GPS1000 centre remains X=0, Y=218.775 mm, over the rear crossmember, with its mounting surface at Z=233.8 mm. The antenna's detachable fork is separate from the one-piece main floor so the assembly fits the H2S bed. Its metal antenna thread remains a separately sourced BSW 5/8–11 mounting component.

The 1.28-inch display windows, 108 mm eye spacing, Raspberry Pi AI Camera cassette, factory lens and Ø10 mm optical opening are unchanged. The LCD rear pocket is provisional Ø39.5 mm: confirm PCB and header dimensions on the actual AITRIP modules. The camera can accept the previous optional flat Ø12 × 1 mm protective glass; this is an optical window, not a replacement lens.

## Validation and limits

`output/verification.json` records CAD validity, connected and closed STL meshes, print envelopes, assembly clearances, unchanged original-leg files and material comparison at all three leg interfaces. The removal check uses approximate deflected-tab envelopes to check clearance; it is **not** a force, stress or fatigue calculation.

This is a printable fit prototype, not a proven structural load rating. The earlier 1 kg target for the complete upper module is not verified: compare the combined slicer mass of all upper prints plus the actual electronics and antenna before committing to the full prints. CAD solid volumes are provided in the manifest; actual print mass depends on walls, infill and supports. Clip force, layer adhesion, vibration retention, engine heat exposure and water resistance require physical testing. Side gills are open ventilation slots; this housing has no waterproof rating. Engine, battery and wheel shapes in the previews are approximate reference envelopes, so real clearances still need checking.

The preview images are renders of the delivered CAD geometry. Purchased components are reference models and are not included as printable parts.

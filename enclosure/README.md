# GPS station enclosure

The current two-storey design is [service-door-v4](service-door-v4/README.md). The files below describe the earlier concept B; V1–V3 are retained as design history.

## What belongs in Git

Keep the design/build, rendering and verification scripts, `parameters.json`, documentation, and original STEP files in each version's `inputs/` directory. Those STEP files are source geometry, including the user's original cradle and threaded adapter; they cannot be replaced by the generated exports. Keep `concepts/two_storey/user_parts_reference.png` as a visual reference.

The repository ignores all enclosure `output/` directories (STEP/STL exports, renders and generated reports), ZIP bundles, and concept-reference STL meshes. These remain available locally. Publish finished exports as release attachments when sharing a printable or Onshape-ready version rather than committing every regenerated copy. The ignore rules apply only to `enclosure/`, so unrelated CAD files are unaffected.

To recreate the latest exports from the repository root, using Python 3.13 (the version used for this design):

```powershell
python -m venv .cad-venv
.\.cad-venv\Scripts\python.exe -m pip install -r enclosure\requirements.txt
.\.cad-venv\Scripts\python.exe enclosure\service-door-v4\build.py
.\.cad-venv\Scripts\python.exe enclosure\service-door-v4\render.py
.\.cad-venv\Scripts\python.exe enclosure\service-door-v4\verify.py
```

The scripts recreate `service-door-v4/output/`, including the Onshape assembly `gps_station_service_door_v4.step`, printable parts and fit coupons, previews, and verification results. ZIP bundles are optional distribution copies and are not created by these commands. Earlier revisions have their own scripts and parameters in their respective folders.

## Earlier concept B — rain-exposure prototype

This is a first mechanical prototype, not a verified waterproof enclosure. Bench-fit the boards, cables and bought hardware before installing outdoors. All dimensions are millimetres.

## Files and Onshape

Import `output/gps_station_B.step` into an Onshape document using **+ > Import**. It contains four separate solid parts in their assembled positions: base, lid, GNSS carrier and ESP cradle. STEP preserves editable solid geometry, not the source feature history. Onshape's Move Face, Hole and other direct-editing features can modify these solids. The parameterised source is `build_enclosure.py` and `parameters.json` (CadQuery 2.8).

`layout_with_reference_boards.step` additionally contains two simplified board envelopes for checking the intended arrangement; these are not accurate electronic component models and must not be printed. The four plain-name STL files are individually oriented for printing. `preview.png` is rendered from the exported geometry. `verification.json` records solid validity, STEP round-trip and interference checks.

## Dimensions and orientation

* Body: 90 wide × 110 high × 37 deep. Closed depth: 40.
* Cover: 96 wide × 118 high, with 7 mm overlapping skirt and 0.5 mm clearance per side around the body.
* Back mounting ears: full assembly height 144; wall screw centres 128 apart; holes 5.5 diameter. Use suitable washers and wall fixings.
* Rear skin: 3; side walls/seal land: 6; cover face: 3.
* GNSS input size: 44 on the port-bearing side × 43.2, with 3 mm mounting holes. With the SMA facing down, the port-bearing edge is horizontal: 44 wide × 43.2 high. Confirm orientation against your board before drilling.
* ESP input size: 18 × 24.7. Assumed PCB thickness 1.6, without header pins.
* Positive Y is up on the wall; negative Y is the cable-exit edge; Z measures forward from the back.

## Changes from the initial illustration

The USB-C connector is entirely inside the sealed cavity. A bare exposed USB opening would not suit direct rain. Both the power cable and antenna coax enter through separate downward-facing bought cable glands, with drip loops below them. Connect the coax to the existing board SMA inside. No bulkhead SMA adapter is required. The extra cable bend and plug space increases the initial 75 × 100 × 35 sketch to a 90 × 110 × 40 body. The actual cover has a flat face and an overlapping perimeter skirt; its upper overhang serves as the rain hood.

The antenna itself is external to this enclosure. Its mount and ground plane are outside the scope of these files.

## Hardware to match before the final print

* Two sealing cable glands with panel-sealing washers and locknuts. The prototype has **16.2 mm clearance holes**, intended for a gland requiring approximately a 16 mm panel opening. Check the selected gland's datasheet rather than relying on the trade size alone. Threaded shanks must accommodate a 6 mm wall plus washer and locknut. Available nominal nut/washer envelope: no more than 24 mm diameter at each hole. Hole centres are 34 mm apart, at Z=20.
* Match each gland's sealing range to the actual cable outside diameter. USB-C does not specify the plastic plug housing or cable jacket size. For already-terminated USB and antenna cables, choose glands with a split seal/body intended to pass the existing plugs, or verify every gland component passes over the plugs before buying. An ordinary gland may not pass a USB-C housing or SMA connector even when its panel hole is large enough. Change the hole parameter if the chosen glands need another opening; recheck envelope clearance.
* At least 400 mm of 2 mm silicone gasket cord. The continuous groove is 2.4 wide × 1.4 deep; approximate centreline length 371. Join the ends using the gasket supplier's recommended method. At full lid contact the nominal cord squeeze is 30%; adjust to the actual cord and printer tolerances.
* Four M3 × 12 low-profile/button-head screws for the lid (head diameter ≤6.2; recess depth 1.6). The base has 2.5 diameter blind pilot holes for screws suitable for plastic. These are not modelled metal threads. Trial-fit the screw type in scrap material first.
* Four M3 × 5 screws for the removable carriers, likewise into plastic pilot holes. No heat-set inserts are assumed.
* Four M2.5 screws suitable for plastic, approximately 6 mm long, for the GNSS board after transfer-drilling its supports. Check actual PCB thickness and screw penetration; the corner pads are only 4 high above the 2 mm carrier.
* One narrow nonconductive tie or appropriate removable restraint for the ESP32; tie slots are in the cradle. Position it clear of components and buttons. Keep the antenna end free. Verify the cradle rails against actual edge solder joints and do not fit header pins into this prototype without checking space.

## Fit and assembly

1. Print `gland_fit_coupon.stl` and the two small carriers first. The coupon reproduces the 6 mm panel, 16.2 mm gland bore and 2.5 mm blind screw pilot. Check the actual glands, seals and chosen screw. Seat the real boards and check underside components, rail contact, solder joints and plug clearance. The board models omit underside parts. ESP32 PCB bottom is at Z=12; the GNSS PCB bottom is at Z=13.
2. Place the GNSS board on the four broad undrilled corner pads, align it with the carrier, and transfer-mark the centres of the actual 3 mm PCB holes. Remove the board, drill appropriate pilot holes for the selected M2.5 plastic screws, deburr, clean and refit. **Do not use an assumed hole pitch.** Replacement accurately drilled carriers can be generated once the measured hole centres are known.
3. Dry-fit the body, lid, gasket, cables and chosen glands. Internal cable bend space is provisional: use the actual cable manufacturer's bend-radius limit. A large USB plug or stiff coax may need the board moved or the body extended. Keep cable strain off the board connectors.
4. Fit the gland panel seals and locknuts, feed cables according to the gland instructions, then connect the internal USB-C and SMA. Secure the carriers. The GNSS USB connector remains internal and is accessible with the lid removed.
5. Wire boards according to the project's firmware README. Mechanical layout does not establish the electrical connections. Check the ESP32 can power the GNSS using the intended wiring and supply before sealing.
6. Install the gasket and tighten the lid evenly, only enough to seat it without distorting the rim. The lid pilots and carrier pilots are blind to retain the solid back.
7. Test the empty enclosure with tissue inside in the intended mounting orientation before adding powered electronics. Check the lid, gasket joint, glands and printed walls for leaks. Repeat after final assembly with electronics unpowered. No IP rating is claimed. Consider a suitable bought waterproof enclosure if exposure testing cannot establish adequate protection.

## Printing

ASA is the preferred outdoor material because of UV and heat resistance; use settings appropriate to your printer. Source: https://help.prusa3d.com/article/asa_1809

Suggested starting point: 0.2 mm layers, 5–6 perimeters, at least 6 solid top/bottom layers, and 30–40% infill. Inspect layer bonding and seal surfaces. Printed shells are not automatically watertight. Base and carriers print back-down; lid STL is already outside-face-down. Horizontal gland bores and some carrier rail features may need local supports or finishing; use the slicer's preview to decide. Keep supports off the gasket groove where possible. Print a small gland-hole/screw fit sample before committing to the body.

Onshape import reference: https://cad.onshape.com/help/Content/Document/importing_files.htm
CAD export reference: https://cadquery.readthedocs.io/en/latest/importexport.html

## Verification scope

The build asserts one valid connected solid per printable part, zero positive-volume collisions between the four parts, clearance of approximate board envelopes from the body/lid, and matching volume after individual STEP export/reimport. These checks do not establish actual PCB fit, antenna performance, cable routing, fastener pullout strength, printer tolerances or weather resistance. Hole pitch, total populated board heights and actual cable/gland dimensions are still unmeasured.

To regenerate from this workspace:

```powershell
.\.cad-venv\Scripts\python.exe enclosure\build_enclosure.py
.\.cad-venv\Scripts\python.exe enclosure\render_preview.py
```

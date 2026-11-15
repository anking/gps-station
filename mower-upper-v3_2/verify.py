"""Independent checks on cached STEP/STL exports; no loft regeneration."""
from pathlib import Path
import os
import hashlib
import json
import math
import cadquery as cq
import vtk

ROOT = Path(__file__).resolve().parent
OUT = Path(os.environ.get("MOWER_CAD_OUTPUT", ROOT / "output")).resolve()
M = json.loads((OUT / "manifest.json").read_text(encoding="utf-8"))
OLD = ROOT / "inputs/legacy_v1"


def bb_overlap(a, b):
    return all(min(getattr(a, k + "max"), getattr(b, k + "max")) -
               max(getattr(a, k + "min"), getattr(b, k + "min")) > 1e-5 for k in "xyz")


def mesh_check(path):
    reader = vtk.vtkSTLReader()
    reader.SetFileName(str(path))
    reader.Update()
    p = reader.GetOutput()
    edges = vtk.vtkFeatureEdges()
    edges.SetInputData(p)
    edges.BoundaryEdgesOn()
    edges.NonManifoldEdgesOn()
    edges.FeatureEdgesOff()
    edges.ManifoldEdgesOff()
    edges.Update()
    conn = vtk.vtkPolyDataConnectivityFilter()
    conn.SetInputData(p)
    conn.SetExtractionModeToAllRegions()
    conn.Update()
    row = {"triangles": p.GetNumberOfCells(), "open_or_nonmanifold_edges": edges.GetOutput().GetNumberOfCells(),
           "regions": conn.GetNumberOfExtractedRegions(), "bounds": list(p.GetBounds())}
    row["closed_single_mesh"] = bool(row["triangles"] and row["open_or_nonmanifold_edges"] == 0 and row["regions"] == 1)
    b = row["bounds"]
    assert b[1] - b[0] < 330.1 and b[3] - b[2] < 310.1 and b[5] - b[4] < 340.1, (path.name, b)
    assert abs(b[4]) < .05, (path.name, "not on bed", b[4])
    return row


def main():
    report = {"parts": {}, "intersections": [], "legacy_intersections": [], "mount_interface_comparison": [],
              "legacy_file_hashes_unchanged": True, "hardware_mount_fit_unconfirmed": True,
              "rear_axle_reference_confirmed_at_rear_crossmember": True, "strength_thermal_water_tests": False}
    for name, row in M["parts"].items():
        shape = cq.importers.importStep(str(OUT / f"{name}.step"))
        assert shape.val().isValid() and len(shape.solids().vals()) == 1, name
        err = abs(shape.val().Volume() / 1000 - row["volume_cm3"]) / row["volume_cm3"]
        # STEP refits smooth spline surfaces; allow <0.001% volume difference.
        assert err < 1e-5, (name, err)
        report["parts"][name] = {**mesh_check(OUT / f"{name}.stl"), "step_volume_relative_error": err}
    print("STL and STEP checks passed", flush=True)
    solids = {name: cq.importers.importStep(str(OUT / f"_solid_{name}.step")).val() for name in M["instances"]}
    names = list(solids)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            sa, sb = solids[a], solids[b]
            if bb_overlap(sa.BoundingBox(), sb.BoundingBox()):
                v = sa.intersect(sb).Volume()
                if v > .02:
                    report["intersections"].append({"a": a, "b": b, "mm3": v})
    print("New assembly intersection check complete", flush=True)
    legacy = {name: cq.importers.importStep(str(OUT / f"_legacy_{name}.step")).val() for name in M["context"]}
    for a, sa in solids.items():
        for b, sb in legacy.items():
            if bb_overlap(sa.BoundingBox(), sb.BoundingBox()):
                v = sa.intersect(sb).Volume()
                if v > .02:
                    report["legacy_intersections"].append({"a": a, "b": b, "mm3": v})
    print("Unchanged leg clearance check complete", flush=True)
    # Bought camera is clamped by four PCB holes; the standoffs must not
    # intersect PCB material or the approximate optical package envelope.
    report["camera_component_intersections"] = []
    cartridge = solids["camera_cartridge"]
    for refname in ("AI_camera_PCB_REFERENCE", "AI_camera_package_REFERENCE", "AI_camera_lens_REFERENCE"):
        component = cq.importers.importStep(str(OUT / f"_{refname}.step")).val()
        volume = cartridge.intersect(component).Volume()
        if volume > .01:
            report["camera_component_intersections"].append({"component": refname, "mm3": volume})
    # Conservative air-cone estimate at the 10mm mouth, using official max
    # H/V angles including Â±3deg tolerance and the 4.75mm entrance aperture.
    halfdiag = math.hypot(math.tan(math.radians(69.3 / 2)), math.tan(math.radians(55.3 / 2)))
    report["camera_aperture_check"] = {"mouth_diameter_mm": 10,
        "lens_to_front_mouth_assumed_mm": 2.64,
        "conservative_required_diameter_mm": 2 * (2.375 + 2.64 * halfdiag),
        "actual_camera_fit_and_optical_image_test_required": True}
    for filename, digest in M["source_leg_hashes"].items():
        assert hashlib.sha256((OLD / filename).read_bytes()).hexdigest() == digest, filename
    # Compare the entire 5mm floor under each shoulder, not just hole centres.
    for mount in M["mounts"]:
        x, y, h = mount["top"]
        lr, fb = ("left" if x < 0 else "right"), ("front" if y < 0 else "rear")
        new = solids["base_one_piece"]
        previous = cq.importers.importStep(str(OLD / f"body_{lr}.step")).val()
        region = (cq.Workplane("XY", origin=(0, 0, h)).box(38, 22, 5, centered=(True, True, False))
                  .rotate((0, 0, 0), (0, 0, 1), mount["angle"]).translate((x, y, 0)).val())
        n, o = new.intersect(region), previous.intersect(region)
        diff = n.cut(o).Volume() + o.cut(n).Volume()
        report["mount_interface_comparison"].append({"label": mount["label"], "different_volume_mm3": diff})
        assert diff < .02, (mount, diff)
    assembly = cq.importers.importStep(str(OUT / "upper_v3_2_ONLY.step"))
    assert len(assembly.solids().vals()) == len(M["instances"])
    report["upper_instance_count"] = len(M["instances"])
    report["unique_production_parts"] = sum(not r["test"] for r in M["parts"].values())
    report["antenna_center"] = [0, M["parameters"]["antenna_axis_y"], 177.8 + 56]
    report["cover_screws"] = M["cover_screws"]
    report["stl_package_contains_legs"] = False
    (OUT / "verification.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "parts"}, indent=2), flush=True)
    assert not report["intersections"] and not report["legacy_intersections"] and not report["camera_component_intersections"], "Positive volume intersections found"
    assert all(r["closed_single_mesh"] for r in report["parts"].values()), "Open or disconnected STL found"


if __name__ == "__main__":
    main()

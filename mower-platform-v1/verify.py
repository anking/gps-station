"""Verify exported solids/meshes and assembled clearance, not strength or airflow."""
from pathlib import Path
import json
import cadquery as cq
import vtk
import build as m

OUT = Path(__file__).resolve().parent / "output"


def bbox_overlap(a, b, eps=1e-6):
    return (min(a.xmax, b.xmax) - max(a.xmin, b.xmin) > eps and
            min(a.ymax, b.ymax) - max(a.ymin, b.ymin) > eps and
            min(a.zmax, b.zmax) - max(a.zmin, b.zmin) > eps)


def check_mesh(path):
    reader = vtk.vtkSTLReader()
    reader.SetFileName(str(path))
    reader.Update()
    poly = reader.GetOutput()
    edge = vtk.vtkFeatureEdges()
    edge.SetInputData(poly)
    edge.BoundaryEdgesOn()
    edge.NonManifoldEdgesOn()
    edge.FeatureEdgesOff()
    edge.ManifoldEdgesOff()
    edge.Update()
    components = vtk.vtkPolyDataConnectivityFilter()
    components.SetInputData(poly)
    components.SetExtractionModeToAllRegions()
    components.Update()
    row = {"triangles": poly.GetNumberOfCells(),
           "boundary_or_nonmanifold_edges": edge.GetOutput().GetNumberOfCells(),
           "connected_regions": components.GetNumberOfExtractedRegions()}
    assert row["triangles"] > 0 and row["boundary_or_nonmanifold_edges"] == 0, (path.name, row)
    assert row["connected_regions"] == 1, (path.name, row)
    return row


def verify():
    manifest = json.loads((OUT / "manifest.json").read_text())
    report = {"parts": {}, "collisions": [], "reference_interferences": [], "checks": {}}
    for name, item in m.PARTS.items():
        s = item["shape"].val()
        reimported = cq.importers.importStep(str(OUT / f"{name}.step"))
        v = sum(s.Volume() for s in reimported.solids().vals())
        error = abs(v - s.Volume()) / s.Volume()
        assert reimported.val().isValid() and error < 1e-6, (name, error)
        row = {"step_relative_volume_error": error, **check_mesh(OUT / f"{name}.stl")}
        dims = manifest["parts"][name]["bbox_print_mm"]
        assert dims[0] <= 210.0001 and dims[1] <= 210.0001 and dims[2] <= 250.0001
        report["parts"][name] = row
    items = list(m.INSTANCES.items())
    for i, (a, ai) in enumerate(items):
        sa = ai["shape"].val()
        for b, bi in items[i + 1:]:
            sb = bi["shape"].val()
            if bbox_overlap(sa.BoundingBox(), sb.BoundingBox()):
                v = sa.intersect(sb).Volume()
                if v > .01:
                    report["collisions"].append({"a": a, "b": b, "volume_mm3": v})
    for a, ai in items:
        sa = ai["shape"].val()
        for b, bi in m.REFERENCES.items():
            sb = bi["shape"].val()
            if bbox_overlap(sa.BoundingBox(), sb.BoundingBox()):
                v = sa.intersect(sb).Volume()
                if v > .01:
                    report["reference_interferences"].append({"part": a, "reference": b, "volume_mm3": v})
    # Check actual exported primary STEP retains the instance count.
    assembly = cq.importers.importStep(str(OUT / "mower_platform_v1.step"))
    n = len(assembly.solids().vals())
    assert n == len(m.INSTANCES), ("assembly_solid_count", n, len(m.INSTANCES))
    assert assembly.val().isValid()
    solid_volume = sum(i["shape"].val().Volume() for i in m.INSTANCES.values()) / 1000
    report["checks"] = {
        "primary_step_solid_count": n,
        "printable_instances": len(m.INSTANCES),
        "unique_production_parts": sum(not n.startswith("TEST_") for n in m.PARTS),
        "printer_xy_allowance_including_brim_per_side_mm": 5,
        "minimum_height_clearance_floor_to_engine_nominal_mm": m.H - m.P["engine_top_height_approx"],
        "lowest_bridge_to_engine_nominal_mm": m.H - 8 - m.P["engine_top_height_approx"],
        "assembled_solid_volume_cm3_not_sliced_material": solid_volume,
        "solid_mass_g_at_1_27_g_cm3_NOT_print_mass": solid_volume * 1.27,
        "checked_actual_frame_and_engine": False,
        "strength_FEA_or_load_test_performed": False,
        "cooling_or_weather_test_performed": False,
    }
    (OUT / "verification.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"checks": report["checks"], "collisions": report["collisions"],
                      "reference_interferences": report["reference_interferences"]}, indent=2), flush=True)
    assert not report["collisions"], "Positive volume intersections between printable parts"
    assert not report["reference_interferences"], "Intersection with approximate reference envelopes"


if __name__ == "__main__":
    verify()

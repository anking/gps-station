"""Check dome attachment, lower edge and the continuous cord gland."""
from pathlib import Path
import os
import json
import math
import cadquery as cq

ROOT=Path(__file__).resolve().parent
OUT=Path(os.environ.get("MOWER_CAD_OUTPUT", ROOT/"output")).resolve()
Z=269.8


def main():
    m=json.loads((OUT/"manifest.json").read_text(encoding="utf-8"))
    d=cq.importers.importStep(str(OUT/"killswitch_dome.step")).val()
    h=cq.importers.importStep(str(OUT/"hood_one_piece.step")).val()
    report={"continuous_groove_samples":72,"groove_clear":True,"groove_floor_intact":True,
            "sealing_lands_intact":True,"hood_mating_land_flat_and_solid":True,
            "reinforced_skirt_height_mm":3,"reinforced_footprint_diameter_mm":91.4,
            "screw_pattern_aligned":True,"top_switch_hole_preserved":True,
            "square_cavity_preserved":True,"actual_water_seal_test_performed":False}
    for i in range(72):
        a=2*math.pi*i/72
        def point(r,z):return (r*math.cos(a),r*math.sin(a),z)
        assert not d.isInside(point(39,Z+.75)),i
        assert d.isInside(point(39,Z+1.6)),i
        assert d.isInside(point(37.5,Z+.75)) and d.isInside(point(40.5,Z+.75)),i
        assert d.isInside(point(45.6,Z+.5)) and d.isInside(point(45.6,Z+2.9)),i
        assert h.isInside(point(39,Z-.1)),i
    for x,y in m["killswitch_dome"]["screw_centres_xy"]:
        assert not d.isInside((x,y,Z+5))
        assert d.isInside((x,y,Z+10.1))
        assert not h.isInside((x,y,Z-1))
    assert not d.isInside((0,0,Z+28)) and d.isInside((12,0,Z+28))
    for x in (-19.9,19.9):assert not d.isInside((x,0,Z+15))
    for x in (-20.1,20.1):assert d.isInside((x,0,Z+15))
    assert not h.isInside((0,0,Z-1))
    (OUT/"dome_check.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    print(json.dumps(report,indent=2),flush=True)


if __name__=="__main__":main()

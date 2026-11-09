"""Build concept B, millimetres. Requires CadQuery 2.8. See README before printing."""
from pathlib import Path
import json
import math
import cadquery as cq

ROOT = Path(__file__).resolve().parent
P = json.loads((ROOT / "parameters.json").read_text())
OUT = ROOT / "output"
OUT.mkdir(exist_ok=True)

def rect(w, h, r, z, depth, x=0, y=0):
    return (cq.Workplane("XY", origin=(x, y, z)).rect(w, h).extrude(depth)
            .edges("|Z").fillet(r))

def cyl(x, y, z, radius, height):
    return cq.Workplane("XY", origin=(x, y, z)).circle(radius).extrude(height)

def box(x, y, z, w, h, d):
    return cq.Workplane("XY", origin=(x,y,z)).box(w,h,d,centered=(True,True,False))

W, H, D = P['body_width'], P['body_height'], P['body_depth']
T, B, R = P['wall'], P['back_thickness'], P['corner_radius']
screws = [(x,y) for x in (-34,34) for y in (-44,44)]
tray_fix = [(-12,-17),(-12,37)]
esp_fix = [(26,-13.5),(26,18.2)]

base = rect(W,H,R,0,D).cut(rect(W-2*T,H-2*T,3,B,D))
# A continuous seal land outside the lid fasteners.
groove_outer = rect(W-3.6,H-3.6,4.2,D-P['gasket_groove_depth'],2)
groove_inner = rect(W-8.4,H-8.4,1.8,D-P['gasket_groove_depth']-.1,2.2)
groove = groove_outer.cut(groove_inner)
base = base.cut(groove)
for x,y in screws:
    base = base.union(cyl(x,y,B,4.8,D-B))
    # Blind pilot for M3 plastic-thread screw; outside back skin stays intact.
    base = base.cut(cyl(x,y,D-14,1.25,15))
for x,y in tray_fix + esp_fix:
    base = base.union(cyl(x,y,B,3.8,4))
    base = base.cut(cyl(x,y,3.5,1.25,4))
# Bottom is negative Y. Bore along Y, with a broad flat 6 mm gland seat.
for x in P['gland_centres_x']:
    bore = cq.Solid.makeCylinder(P['gland_hole_diameter']/2, T+2,
        cq.Vector(x,-H/2-1,P['gland_centre_depth']),cq.Vector(0,1,0))
    base = base.cut(bore)
# External mounting ears on the back; wall screws never enter the dry cavity.
for y in (-61,61):
    ear = rect(22,22,5,0,5,0,y).cut(cyl(0,y + (3 if y>0 else -3),-1,2.75,7))
    base = base.union(ear)

# Overlapping cover skirt: 0.5 mm clearance per side, 7 mm overlap.
lid = rect(W+6,H+8,8,D,3,0,1)
skirt = rect(W+6,H+8,8,D-7,7,0,1).cut(rect(W+1,H+1,6.5,D-7-.1,7.2))
lid = lid.union(skirt)
for x,y in screws:
    lid = lid.cut(cyl(x,y,D-.1,1.7,3.2))
    lid = lid.cut(cyl(x,y,D+1.4,3.1,2))

# Removable GNSS carrier. Four broad pads, drilled from actual board later.
tray = rect(49,58,2,7,2,-12,10)
for x in (-12-P['gnss_width']/2+4,-12+P['gnss_width']/2-4):
    for y in (10-P['gnss_length']/2+4,10+P['gnss_length']/2-4):
        tray = tray.union(box(x,y,9,8,8,4))
for x,y in tray_fix:
    tray = tray.cut(cyl(x,y,6.9,1.7,2.2))

# Removable ESP cradle: rails below the antenna end, no guessed board holes.
cradle = rect(P['esp_width']+4.6,P['esp_length']+12.3,1,7,2,26,2.35)
for x in (16,36):
    cradle = cradle.union(box(x,-2,9,1.4,16,5.1))
    cradle = cradle.union(box(x + (.9 if x<26 else -.9),-2,9,1.8,16,3))
for x,y in esp_fix:
    cradle = cradle.cut(cyl(x,y,6.9,1.7,2.2))
for x in (15.6,36.4):
    cradle = cradle.cut(box(x,-3,6.9,1.2,4,2.2))

# Reference PCB envelopes, excluded from print files and primary STEP.
gnss = box(-12,10,13,P['gnss_width'],P['gnss_length'],P['assumed_pcb_thickness'])
gnss = gnss.union(box(-12,10,14.6,18,23,4))
gnss = gnss.union(cq.Solid.makeCylinder(3.2,10,cq.Vector(-12,10-P['gnss_length']/2,16),cq.Vector(0,-1,0)))
esp = box(26,2.35,12,P['esp_width'],P['esp_length'],P['assumed_pcb_thickness'])
esp = esp.union(box(26,-10.5,13.6,9,7,3.2))

parts = {'base':base,'lid':lid,'gnss_carrier':tray,'esp_cradle':cradle}
colors = {'base':(.70,.73,.76),'lid':(.83,.85,.87),
          'gnss_carrier':(.38,.41,.45),'esp_cradle':(.38,.41,.45)}
assembly = cq.Assembly(name='GPS_station_B_prototype')
report = {'status':'PROTOTYPE — bench fit and rain test required', 'parts':{}, 'interferences_mm3':{}}
for name,part in parts.items():
    solid = part.val()
    assert solid.isValid(), f'Invalid geometry: {name}'
    assert len(part.solids().vals()) == 1, f'Disconnected part: {name}'
    cq.exporters.export(part,str(OUT/f'{name}.step'))
    # Flat back on bed for base and carriers; lid prints outside face down.
    printable = part
    if name == 'lid':
        printable = part.rotate((0,0,0),(1,0,0),180)
    printable = printable.translate((0,0,-printable.val().BoundingBox().zmin))
    cq.exporters.export(printable,str(OUT/f'{name}.stl'),tolerance=.05,angularTolerance=.1)
    assembly.add(part,name=name,color=cq.Color(*colors[name]))
    bb=solid.BoundingBox()
    report['parts'][name]={'valid':True,'solids':1,'volume_mm3':solid.Volume(),
                          'bounds_mm':[bb.xlen,bb.ylen,bb.zlen]}
assembly.export(str(OUT/'gps_station_B.step'))
for i,(a,pa) in enumerate(parts.items()):
    for b,pb in list(parts.items())[i+1:]:
        v=pa.intersect(pb).val().Volume()
        report['interferences_mm3'][f'{a}/{b}']=v
        assert v<.001, f'Parts collide: {a}/{b}: {v}'
# Solid export round-trip: verify each part survived the Onshape-neutral format.
for name,part in parts.items():
    imported=cq.importers.importStep(str(OUT/f'{name}.step'))
    assert imported.val().isValid()
    assert math.isclose(imported.val().Volume(),part.val().Volume(),rel_tol=1e-6)
report['step_round_trip']='PASS'
# Reference board models must not collide with cover or walls.
for name,pcb in [('gnss',gnss),('esp',esp)]:
    for n in ('base','lid'):
        v=pcb.intersect(parts[n]).val().Volume()
        report['interferences_mm3'][f'{name}_reference/{n}']=v
        assert v<.001, f'PCB envelope collides: {name}/{n}'
assembly.add(gnss,name='GNSS_REFERENCE_ONLY',color=cq.Color(.75,.08,.07))
assembly.add(esp,name='ESP_REFERENCE_ONLY',color=cq.Color(.04,.12,.24))
assembly.export(str(OUT/'layout_with_reference_boards.step'))
(OUT/'verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8')

# Small panel coupon: test bought gland and screw fit before printing a body.
coupon = rect(36,28,2,0,6).cut(cyl(0,0,-.1,P['gland_hole_diameter']/2,6.2))
coupon = coupon.cut(cyl(13,10,2,1.25,4.1))
assert coupon.val().isValid() and len(coupon.solids().vals()) == 1
cq.exporters.export(coupon,str(OUT/'gland_fit_coupon.stl'),tolerance=.05)
cq.exporters.export(coupon,str(OUT/'gland_fit_coupon.step'))

# Meshes for a direct geometry-based preview, never an AI-generated fit claim.
for name,part in {**parts,'gnss_reference':gnss,'esp_reference':esp}.items():
    cq.exporters.export(part,str(OUT/f'_preview_{name}.stl'),tolerance=.1)
print(json.dumps(report,indent=2))

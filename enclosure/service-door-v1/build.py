"""Two-storey enclosure: editable solid prototype, mm; CadQuery 2.8."""
from pathlib import Path
from itertools import combinations
import json, math
import cadquery as cq

ROOT=Path(__file__).resolve().parent
P=json.loads((ROOT/'parameters.json').read_text(encoding='utf-8'))
OUT=ROOT/'output'; OUT.mkdir(exist_ok=True)
W,L,H=P['width'],P['depth'],P['height']
T,F=P['wall'],P['floor']
Y=-L/2
S=P['shelf_z']

def box(x,y,z,w,d,h):
    return cq.Workplane('XY',origin=(x,y,z)).box(w,d,h,centered=(True,True,False))

def rr(w,d,r,z,h,x=0,y=0):
    return (cq.Workplane('XY',origin=(x,y,z)).rect(w,d).extrude(h)
            .edges('|Z').fillet(r))

def disk(x,y,z,r,h):
    return cq.Workplane('XY',origin=(x,y,z)).circle(r).extrude(h)

def front(w,h,r,y,d,x=0,z=0):
    # Local +Z becomes global +Y; local -Y becomes global +Z.
    return rr(w,h,r,0,d).rotate((0,0,0),(1,0,0),-90).translate((x,y,z))

def bore(x,y,z,r,length,axis=(0,0,1)):
    return cq.Workplane(obj=cq.Solid.makeCylinder(r,length,cq.Vector(x,y,z),cq.Vector(*axis)))

def export_mesh(part,path):
    cq.exporters.export(part,str(path),tolerance=.07,angularTolerance=.12)

# One continuous frame avoids a joint crossing the door gasket.
body=rr(W,L,6,0,H).cut(rr(W-2*T,L-2*T,3,F,H+1))
opening=front(W-16,H-16,3.5,Y-1,T+2,z=H/2)
body=body.cut(opening)
groove=(front(W-7.6,H-7.6,6.2,Y,P['gasket_groove_depth'],z=H/2)
        .cut(front(W-12.4,H-12.4,3.8,Y-.1,2,z=H/2)))
body=body.cut(groove)
# Roof gasket on the top rim: 2 mm round cord, 30% nominal squeeze.
roof_groove=rr(W-1.6,L-1.6,5.2,H-1.4,1.5).cut(rr(W-6.4,L-6.4,2.8,H-1.5,1.7))
body=body.cut(roof_groove)

# Stationary shelf supports; no floor-to-shelf posts obstruct the battery.
for x in (-77.5,77.5):
    body=body.union(box(x,0,S-4,7,100,4))
    for y in (-44,44):
        body=body.cut(bore(x + (3.5 if x<0 else -3.5),y,S-3.5,1.25,4))

# Flat, stationary supports and strap bridges; their holes do not pierce the floor.
for y in (-30,30):
    body=body.union(box(-13,y,F,126,8,5))
for y in (-45,45):
    bridge=box(-13,y,F,22,8,8).cut(box(-13,y,F+2,14,10,3))
    body=body.union(bridge)
# Raised central mounting land. Recessed heads finish level with bank supports.
body=body.union(disk(0,0,F,33,5))
post_holes=[(-17.320508,10),(17.320508,10),(0,-20)]
for x,y in post_holes:
    body=body.cut(bore(x,y,-1,1.65,11))
    body=body.cut(bore(x,y,7,3.2,3))
body=body.cut(bore(60,40,-1,P['gland_bore']/2,F+2))

# Blind rear bosses accept the removable electronics plate.
plate_fix=[(-71,57),(-71,97),(1,57),(1,97)]
for x,z in plate_fix:
    body=body.union(box(x,L/2-9.5,z-4,9,11,8))
    body=body.cut(bore(x,L/2-15,z,1.25,9,(0,1,0)))

roof_fix=[(x,y) for x in (-76,76) for y in (-51,51)]
for x,y in roof_fix:
    body=body.union(disk(x,y,H-15,5.5,15))
    body=body.cut(bore(x,y,H-11,1.25,12))

# Outside hinge wings and keeper wings. All drill patterns remain unguessed.
for z in P['hardware_heights']:
    body=body.union(box(-95.5,Y+5,z-17,23,10,34))
    body=body.union(box(-99.5,Y-.625,z-17,15,9.25,34))
    body=body.union(box(97.5,Y+5,z-15,27,10,30))
    body=body.union(box(100,Y-3.5,z-15,22,17,30))

# Single door covering both floors. Thick blind latch pads stay outside dry space.
door=front(W+6,H-4,5,Y-P['door_thickness'],P['door_thickness'],z=H/2)
door_rib=front(W+6,H-4,5,Y-6,2,z=H/2).cut(front(W-10,H-20,3,Y-6.1,2.2,z=H/2))
door=door.union(door_rib)
for z in P['hardware_heights']:
    door=door.union(box(-85,Y-4.5,z-15.5,12,1.5,31))
    door=door.union(box(45,Y-8,z-14,70,8,28))

# Shelf is narrower than the service opening so it can leave through that opening.
shelf=rr(W-18,L-16,2,S,4)
for x in (-74,74):
    for y in (-44,44):
        shelf=shelf.cut(bore(x,y,S-.1,1.7,4.2))
for x,y,w,d in [(60,-26,24,14),(63,40,22,16)]:
    shelf=shelf.cut(rr(w,d,3,S-.1,4.2,x,y))
# Printed cable tie bridges on shelf. No moving battery tray.
for y in (-47,40):
    bridge=box(32,y,S+4,20,8,6).cut(box(32,y,S+5.5,12,10,2.5))
    shelf=shelf.union(bridge)

# Vertical service panel, its four fixings face the open door.
panel=front(82,49,2,45,3,x=-35,z=78.5)
for x,z in plate_fix:
    panel=panel.cut(bore(x,44.9,z,1.7,3.2,(0,1,0)))
# GNSS pitch measured from the user's edited base STEP, not estimated from photo.
pitch=P['gnss_hole_pitch_from_user_step']
gnss_x,gnss_z=-46,78.6
gnss_holes=[(gnss_x+dx,gnss_z+dz) for dx in (-pitch/2,pitch/2) for dz in (-pitch/2,pitch/2)]
for x,z in gnss_holes:
    panel=panel.union(bore(x,35,z,3.8,10,(0,1,0)))
    panel=panel.cut(bore(x,34.9,z,1.05,6,(0,1,0)))
# Cradle is separately printed and screws to the service plate.
esp_fix=[(-11,60),(-11,95)]
for x,z in esp_fix:
    panel=panel.union(bore(x,38,z,3.8,7,(0,1,0)))
    panel=panel.cut(bore(x,37.9,z,1.25,6,(0,1,0)))
cradle=front(23,41,1,36,2,x=-11,z=77.5)
for x,z in esp_fix:
    cradle=cradle.cut(bore(x,35.9,z,1.7,2.2,(0,1,0)))
for x in (-21,-1):
    cradle=cradle.union(box(x,34.5,65,1.4,3,16))
    cradle=cradle.union(box(x,33,65,1.4,1,1.2))
for x in (-20.2,-1.8):
    cradle=cradle.cut(box(x,35.9,70,1.2,2.2,4))
panel=panel.translate((0,-3,0))
cradle=cradle.translate((0,-3,0))

# Four planar roof slopes and a truly flat 42 x 42 mm antenna platform.
roof=(cq.Workplane('XY',origin=(0,0,H)).rect(W+12,L+12)
      .workplane(offset=P['roof_rise']).rect(P['antenna_platform'],P['antenna_platform']).loft())
inner=(cq.Workplane('XY',origin=(0,0,H-1)).rect(W+4,L+4)
       .workplane(offset=P['roof_rise']-2).rect(P['antenna_platform']-6,P['antenna_platform']-6).loft())
roof=roof.cut(inner)
lip=rr(W-9,L-9,2.5,H-4,8).cut(rr(W-13,L-13,1,H-4.1,8.2))
for x,y in roof_fix:
    lip=lip.cut(disk(x,y,H-4.1,6,4.2))
roof=roof.union(lip)
for x,y in roof_fix:
    roof=roof.union(disk(x,y,H,5.5,12))
    roof=roof.cut(bore(x,y,H-1,1.7,14))

# Preserve the user's actual threaded geometry. Flip socket down, cap at Z=0.
adapter=(cq.importers.importStep(str(ROOT/'inputs/post_adapter_original.step'))
         .rotate((0,0,0),(1,0,0),180).translate((0,0,-30)))
for x,y in post_holes:
    adapter=adapter.cut(bore(x,y,-4.2,1.65,4.4))

parts={'body':body,'door':door,'shelf':shelf,'electronics_panel':panel,
       'esp_cradle':cradle,'roof':roof,'post_adapter':adapter}
colors={'body':(.70,.74,.77),'door':(.80,.83,.86),'shelf':(.48,.52,.56),
        'electronics_panel':(.48,.52,.56),'esp_cradle':(.36,.4,.44),
        'roof':(.45,.49,.53),'post_adapter':(.62,.66,.70)}

# Fit envelopes for items whose full mechanical drawings are unavailable.
powerbank=box(-13,0,9,P['powerbank_length'],P['powerbank_width'],P['powerbank_thickness'])
usb_plug=box(58,-20,17,22,12,8)
gnss=box(gnss_x,34.2,57,44,1.6,43.2)
for x,z in gnss_holes:
    gnss=gnss.cut(bore(x,33,z,1.5,3,(0,1,0)))
gnss=gnss.translate((0,-3,0))
module=box(gnss_x,27.9,67,18,5,23)
esp=box(-11,32.2,65,18,1.6,24.7)
coil=cq.Workplane(obj=cq.Solid.makeTorus((P['coil_outer_diameter']-P['coil_height'])/2,
          P['coil_height']/2,cq.Vector(32,-4,S+4+P['coil_height']/2),cq.Vector(0,0,1)))
antenna=rr(42,42,5,H+P['roof_rise'],15)
references={'powerbank_REFERENCE':powerbank,'usb_plug_REFERENCE':usb_plug,
            'gnss_REFERENCE':gnss,'module_REFERENCE':module,'esp_REFERENCE':esp,
            'coil_REFERENCE':coil,'antenna_REFERENCE':antenna}
refcolors={'powerbank_REFERENCE':(.08,.09,.10),'usb_plug_REFERENCE':(.04,.25,.65),
           'gnss_REFERENCE':(.78,.08,.07),'module_REFERENCE':(.7,.72,.73),
           'esp_REFERENCE':(.04,.14,.28),'coil_REFERENCE':(.06,.065,.07),
           'antenna_REFERENCE':(.91,.92,.93)}

report={'status':'FIT PROTOTYPE; hardware pads require transfer-drilling',
        'parts':{},'interferences_mm3':{},'assumed_items':{
        'powerbank_mm':[P['powerbank_length'],P['powerbank_width'],P['powerbank_thickness']],
        'coax_coil_mm':[P['coil_outer_diameter'],P['coil_height']]}}
assembly=cq.Assembly(name='GPS_service_door_v1')
for name,p in parts.items():
    assert p.val().isValid(),f'Invalid geometry: {name}'
    assert len(p.solids().vals())==1,f'Disconnected: {name}: {len(p.solids().vals())}'
    bb=p.val().BoundingBox()
    report['parts'][name]={'valid':True,'solids':1,'volume_mm3':p.val().Volume(),
                         'bounds_mm':[bb.xlen,bb.ylen,bb.zlen]}
    cq.exporters.export(p,str(OUT/f'{name}.step'))
    printable=p
    if name in ('door','electronics_panel','esp_cradle'):
        printable=p.rotate((0,0,0),(1,0,0),-90)
    elif name=='post_adapter':
        printable=p.rotate((0,0,0),(1,0,0),180)
    # Roof print orientation stays upright; it needs selected supports under bosses/lip.
    printable=printable.translate((0,0,-printable.val().BoundingBox().zmin))
    export_mesh(printable,OUT/f'{name}.stl')
    export_mesh(p,OUT/f'_view_{name}.stl')
    assembly.add(p,name=name,color=cq.Color(*colors[name]))
    restored=cq.importers.importStep(str(OUT/f'{name}.step'))
    assert restored.val().isValid()
    assert math.isclose(restored.val().Volume(),p.val().Volume(),rel_tol=1e-6)
for (a,pa),(b,pb) in combinations(parts.items(),2):
    v=pa.intersect(pb).val().Volume()
    report['interferences_mm3'][f'{a}/{b}']=v
    assert v<.001,f'Part collision: {a}/{b}: {v}'
for rn,rp in references.items():
    for pn,pp in parts.items():
        v=rp.intersect(pp).val().Volume()
        report['interferences_mm3'][f'{rn}/{pn}']=v
        assert v<.001,f'Reference collision: {rn}/{pn}: {v}'
    export_mesh(rp,OUT/f'_view_{rn}.stl')
report['step_round_trip']='PASS'
assembly.export(str(OUT/'gps_station_service_door_v1.step'))
for name,p in references.items():
    assembly.add(p,name=name,color=cq.Color(*refcolors[name]))
assembly.export(str(OUT/'layout_with_reference_items.step'))

# Check the door throughout its approximate hinge motion, hardware excluded.
for angle in (-15,-30,-60,-90,P['door_open_angle']):
    open_door=door.rotate((P['hinge_axis_x'],P['hinge_axis_y'],0),
                         (P['hinge_axis_x'],P['hinge_axis_y'],1),angle)
    for name in ('body','roof','shelf'):
        v=open_door.intersect(parts[name]).val().Volume()
        assert v<.001,f'Door swing collision at {angle}: {name}: {v}'
report['door_swing_sampled']='PASS: 0, -15, -30, -60, -90, -110 degrees; hinge hardware is provisional'
export_mesh(open_door,OUT/'_view_door_open.stl')

# Removable shelves and board plates must pass the front aperture without turning.
assert shelf.val().BoundingBox().xlen<W-16
assert panel.val().BoundingBox().xlen<W-16
assert panel.val().BoundingBox().zlen<H-16
report['front_removal_envelope']='PASS for shelf and electronics panel; disconnect cables first'
for name in ('shelf','electronics_panel'):
    for distance in (15,45,80,110,145,180):
        moving=parts[name].translate((0,-distance,0))
        for obstacle in ('body','roof'):
            assert moving.intersect(parts[obstacle]).val().Volume()<.001, f'Removal blocked: {name}/{obstacle}/{distance}'
report['straight_front_removal_sampled']='PASS: shelf and electronics panel, translations 15 to 180 mm; screws and cables removed'
report['cord_lengths_mm']={'door_approx':2*((W-10)+(H-10)-20)+2*math.pi*5,
                         'roof_approx':2*((W-4)+(L-4)-16)+2*math.pi*4}

# Cheap fit coupons: one seal edge sample, one actual panel-thickness gland bore.
coupon=box(0,0,0,40,20,5).cut(box(0,0,3.6,32,2.4,2))
gland_coupon=box(0,0,0,32,32,F).cut(bore(0,0,-1,P['gland_bore']/2,F+2))
for n,p in [('seal_fit_coupon',coupon),('gland_fit_coupon',gland_coupon)]:
    assert p.val().isValid()
    export_mesh(p,OUT/f'{n}.stl')
    cq.exporters.export(p,str(OUT/f'{n}.step'))
(OUT/'verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
(OUT/'view_manifest.json').write_text(json.dumps({'printed':colors,'reference':refcolors},indent=2))
print(json.dumps(report,indent=2))

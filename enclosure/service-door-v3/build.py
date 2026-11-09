"""Two-storey enclosure: editable solid prototype, mm; CadQuery 2.8."""
from pathlib import Path
from itertools import combinations
import json, math
import cadquery as cq
import vtk

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
    # Rotated geometry can tessellate the same zero-plane vertex as 0 and -1e-15.
    # Weld only sub-micron numerical noise, then write a canonical binary STL.
    reader=vtk.vtkSTLReader();reader.SetFileName(str(path));reader.Update()
    clean=vtk.vtkCleanPolyData();clean.SetInputData(reader.GetOutput())
    clean.SetToleranceIsAbsolute(True);clean.SetAbsoluteTolerance(1e-7);clean.Update()
    writer=vtk.vtkSTLWriter();writer.SetFileName(str(path));writer.SetFileTypeToBinary()
    writer.SetInputData(clean.GetOutput());writer.Write()

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

# C-section slide channels capture the 4 mm shelf edges. No shelf screws.
# Opening faces front (-Y). 0.3 mm nominal clearance on each mating face.
for side in (-1,1):
    rail=box(77.25,-1,S-2.3,7.5,106,2)
    rail=rail.union(box(78.65,-1,S-.3,4.7,106,4.6))
    rail=rail.union(box(77.25,-1,S+4.3,7.5,106,2))
    # Rear end stop: shelf reaches Y=52, stop begins at 52.3.
    rail=rail.union(box(75,54.15,S-.3,12,3.7,6.6))
    if side<0:rail=rail.mirror('YZ',union=False)
    body=body.union(rail)

# Interior floor is one flat plane at Z=4. All post-bolt reinforcement is outside.
body=body.union(disk(0,0,-10,34,10))
post_holes=[(-17.320508,10),(17.320508,10),(0,-20)]
for x,y in post_holes:
    # Blind clearance above the insert, then a 5 mm deep M3 insert pocket.
    # Deepest bore ends at Z=-2, leaving 6 mm to the interior floor.
    body=body.cut(bore(x,y,-10.1,1.25,8.1))
    body=body.cut(bore(x,y,-10.1,2.1,5.1))
body=body.cut(bore(60,40,-1,P['gland_bore']/2,F+2))

# Blind rear bosses accept the removable electronics plate.
plate_fix=[(-71,58.5),(-71,97),(1,58.5),(1,97)]
for x,z in plate_fix:
    body=body.union(box(x,L/2-9.5,z-4,9,11,8))
    body=body.cut(bore(x,L/2-15,z,1.25,9,(0,1,0)))

# No lateral hardware wings; user locates hinges and latch keepers independently.

# Single door covering both floors. Thick blind latch pads stay outside dry space.
door=front(W+6,H-4,5,Y-P['door_thickness'],P['door_thickness'],z=H/2)
door_rib=front(W+6,H-4,5,Y-6,2,z=H/2).cut(front(W-10,H-20,3,Y-6.1,2.2,z=H/2))
door=door.union(door_rib)
for z in P['hardware_heights']:
    door=door.union(box(45,Y-8,z-14,70,8,28))
# Closed door forms the removable shelf's front stop (1 mm nominal travel).
door=door.union(box(0,Y+3.5,S,140,7,4))

# Shelf is narrower than the service opening so it can leave through that opening.
shelf=rr(W-18,L-16,2,S,4)
for x,y,w,d in [(60,-26,24,14),(63,40,22,16)]:
    shelf=shelf.cut(rr(w,d,3,S-.1,4.2,x,y))
# Plain shelf: no strap ears or protruding cable-tie bridges.

# Vertical service panel, its four fixings face the open door.
panel=front(82,47.5,2,45,3,x=-35,z=79.25)
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
esp_fix=[(-11,61.5),(-11,93.2)]
for x,z in esp_fix:
    panel=panel.union(bore(x,38,z,3.8,7,(0,1,0)))
    panel=panel.cut(bore(x,37.9,z,1.25,6,(0,1,0)))
# Exact user-provided cradle: rigid transform only; no remodelled retaining rails.
user_cradle=cq.importers.importStep(str(ROOT/'inputs/esp_cradle_user_original.step'))
cradle=user_cradle.rotate((0,0,0),(1,0,0),90).translate((-37,42,75))
panel=panel.translate((0,-3,0))

# Four planar roof slopes and a truly flat 42 x 42 mm antenna platform.
roof=(cq.Workplane('XY',origin=(0,0,H)).rect(W+12,L+12)
      .workplane(offset=P['roof_rise']).rect(P['antenna_platform'],P['antenna_platform']).loft())
inner=(cq.Workplane('XY',origin=(0,0,H-1)).rect(W+4,L+4)
       .workplane(offset=P['roof_rise']-2).rect(P['antenna_platform']-6,P['antenna_platform']-6).loft())
roof=roof.cut(inner)
lip=rr(W-9,L-9,2.5,H-4,8).cut(rr(W-13,L-13,1,H-4.1,8.2))
roof=roof.union(lip)

# Four downward cantilever snap hooks under the roof eaves. No roof screws.
# Body catches stay below the gasket and never pierce the dry wall.
snap_pairs=[]
for side in (-1,1):
    for cy in (-30,30):
        beam=box(87.6,cy,H-20,1.6,18,23)
        root=box(85,cy,H,7,18,2)
        # XZ triangular insertion ramp; horizontal upper face retains the catch.
        hook=(cq.Workplane('XZ',origin=(0,cy+9,0))
              .polyline([(86.8,H-18),(86.8,H-11.15),(85.3,H-11.15)])
              .close().extrude(18))
        grip=box(89.1,cy,H-20,4.6,18,2)
        clip=beam.union(root).union(hook).union(grip)
        catch=box(85.55,cy,H-11,1.1,18,2.5)
        if side<0:
            clip=clip.mirror('YZ',union=False)
            catch=catch.mirror('YZ',union=False)
        roof=roof.union(clip)
        body=body.union(catch)
        snap_pairs.append((clip,catch))

# Preserve the user's actual threaded geometry. Flip socket down, cap at Z=0.
adapter=(cq.importers.importStep(str(ROOT/'inputs/post_adapter_original.step'))
         .rotate((0,0,0),(1,0,0),180).translate((0,0,-40)))
for x,y in post_holes:
    adapter=adapter.cut(bore(x,y,-14.2,1.65,4.4))

parts={'body':body,'door':door,'shelf':shelf,'electronics_panel':panel,
       'esp_cradle':cradle,'roof':roof,'post_adapter':adapter}
colors={'body':(.70,.74,.77),'door':(.80,.83,.86),'shelf':(.48,.52,.56),
        'electronics_panel':(.48,.52,.56),'esp_cradle':(.36,.4,.44),
        'roof':(.45,.49,.53),'post_adapter':(.62,.66,.70)}

# Fit envelopes for items whose full mechanical drawings are unavailable.
powerbank=box(-13,0,F,P['powerbank_length'],P['powerbank_width'],P['powerbank_thickness'])
usb_plug=box(58,-20,12,22,12,8)
gnss=box(gnss_x,34.2,57,44,1.6,43.2)
for x,z in gnss_holes:
    gnss=gnss.cut(bore(x,33,z,1.5,3,(0,1,0)))
gnss=gnss.translate((0,-3,0))
module=box(gnss_x,27.9,67,18,5,23)
esp=box(-11,29.2,65,18,1.6,24.7)
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
assembly=cq.Assembly(name='GPS_service_door_v3')
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
assembly.export(str(OUT/'gps_station_service_door_v3.step'))
for name,p in references.items():
    assembly.add(p,name=name,color=cq.Color(*refcolors[name]))
assembly.export(str(OUT/'layout_with_reference_items.step'))

# Hinge placement deliberately left to user. Preview shows door detached, not hinged.
open_door=door.translate((-170,-20,0))
report['door_swing_sampled']='NOT APPLICABLE: hinge geometry removed at user request'
export_mesh(open_door,OUT/'_view_door_open.stl')
assert math.isclose(cradle.val().Volume(),user_cradle.val().Volume(),rel_tol=1e-10)
assert len(cradle.val().Faces())==len(user_cradle.val().Faces())
report['user_cradle']='PASS: rigid transform only; source volume and face count preserved'
report['roof_snaps']={'count':4,'beam_thickness_mm':1.6,'beam_width_mm':18,
    'root_to_tip_length_mm':23,'hook_engagement_mm':.8,'retention_vertical_play_mm':.15,
    'status':'Closed geometry checked; flexible insertion, fatigue and gasket compression require print tests'}

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
# Verify the new floor and the blind mounting holes with solid material probes.
assert body.intersect(box(-13,0,F+.01,120,80,.5)).val().Volume()<1e-6
for x,y in post_holes:
    probe=bore(x,y,-1.9,.2,5.8)
    assert math.isclose(body.intersect(probe).val().Volume(),probe.val().Volume(),rel_tol=1e-6)
    assert body.intersect(bore(x,y,-9,.2,3)).val().Volume()<1e-6
report['floor']='PASS: flat at Z=4 over battery area; no interior supports, pads or bolt openings'
report['post_mount_blind_holes']={'count':3,'exterior_boss_diameter_mm':68,
    'exterior_boss_depth_mm':10,'pilot_diameter_mm':2.5,'pilot_depth_mm':8,
    'insert_pocket_diameter_mm':4.2,'insert_pocket_depth_mm':5,
    'minimum_solid_material_to_interior_mm':6,'material_probes':'PASS'}
report['shelf_slides']={'shelf_thickness_mm':4,'slot_height_mm':4.6,
    'side_clearance_mm':.3,'vertical_clearance_per_side_mm':.3,
    'rear_stop_clearance_mm':.3,'retention':'C channels prevent lift; rear stops limit insertion; closed door limits forward travel to 1 mm'}
assert shelf.translate((0,1,0)).intersect(body).val().Volume()>1
assert shelf.translate((0,-2,0)).intersect(door).val().Volume()>1
assert shelf.translate((0,0,1)).intersect(body).val().Volume()>1
report['shelf_stop_probes']='PASS: rear, closed-door forward and upward stop probes'
report['cord_lengths_mm']={'door_approx':2*((W-10)+(H-10)-20)+2*math.pi*5,
                         'roof_approx':2*((W-4)+(L-4)-16)+2*math.pi*4}

# Cheap fit coupons: one seal edge sample, one actual panel-thickness gland bore.
coupon=box(0,0,0,40,20,5).cut(box(0,0,3.6,32,2.4,2))
gland_coupon=box(0,0,0,32,32,F).cut(bore(0,0,-1,P['gland_bore']/2,F+2))
for n,p in [('seal_fit_coupon',coupon),('gland_fit_coupon',gland_coupon)]:
    assert p.val().isValid()
    export_mesh(p,OUT/f'{n}.stl')
    cq.exporters.export(p,str(OUT/f'{n}.step'))
# Isolated snap-fit samples to check the printer/material before the full roof.
clip_sample,catch_sample=snap_pairs[-1]
catch_sample=catch_sample.union(box(83.1,30,H-15,4.2,24,12))
for n,p in [('roof_clip_test',clip_sample),('roof_catch_test',catch_sample)]:
    # On side: beam axis lies in the print bed for a practical small fit sample.
    p=p.rotate((0,0,0),(1,0,0),90)
    p=p.translate((0,0,-p.val().BoundingBox().zmin))
    assert p.val().isValid() and len(p.solids().vals())==1
    export_mesh(p,OUT/f'{n}.stl')
    cq.exporters.export(p,str(OUT/f'{n}.step'))
# A short actual rail section and matching edge sample for checking slide clearance.
rail_test=body.intersect(box(79.5,0,S-5,12,32,13))
edge_test=box(72,0,S,8,28,4)
for n,p in [('slider_rail_test',rail_test),('slider_shelf_test',edge_test)]:
    assert p.val().isValid() and len(p.solids().vals())==1
    p=p.translate((0,0,-p.val().BoundingBox().zmin))
    export_mesh(p,OUT/f'{n}.stl')
    cq.exporters.export(p,str(OUT/f'{n}.step'))
export_mesh(body.intersect(box(79.5,0,S-5,12,112,13)),OUT/'_view_rail_detail.stl')
export_mesh(shelf.intersect(box(72,0,S-.1,8,120,4.2)).translate((0,-35,0)),OUT/'_view_shelf_edge_detail.stl')
(OUT/'verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
(OUT/'view_manifest.json').write_text(json.dumps({'printed':colors,'reference':refcolors},indent=2))
print(json.dumps(report,indent=2))

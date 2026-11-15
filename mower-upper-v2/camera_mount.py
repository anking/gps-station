"""Raspberry Pi AI Camera SC1174 cassette, based on official reference drawing.

Axis at X0/Z(H+46). PCB top is 14.4mm above optical axis. The four
2.2mm PCB holes are on 21 x12.5mm pitch, upper row +12.4, lower -0.1.
No additional powered lens: retain the factory optic and manual focus.
"""
import cadquery as cq


def box(x, y, z, w, d, h):
    return cq.Workplane("XY", origin=(x, y, z)).box(w, d, h, centered=(True, True, False))


def bore(x, y, z, r, length):
    return cq.Workplane(obj=cq.Solid.makeCylinder(r, length, cq.Vector(x, y, z), cq.Vector(0, 1, 0)))


def face(w, h, rad, y, depth, z):
    return (cq.Workplane("XY").rect(w, h).extrude(depth).edges("|Z").fillet(rad)
            .rotate((0, 0, 0), (1, 0, 0), 90).translate((0, y, z)))


def build_camera(h=177.8):
    z = h + 46
    plate = face(46, 42, 8, -130.3, 3, z + 2)
    # Inner component well; optical axis stays exactly between the eyes.
    plate = plate.cut(box(0, -126.65, z - 8.25, 15.8, 8.3, 20.5))
    for x in (-10.5, 10.5):
        for dz in (-.1, 12.4):
            post = bore(x, -130.3, z + dz, 3, 5.5)
            post = post.cut(bore(x, -129.3, z + dz, .85, 5.5))
            plate = plate.union(post)
    # 10mm visible mouth, gently enlarged behind the front lip.
    plate = plate.cut(bore(0, -136, z, 5, 17))
    # Optional Ø12 x1mm FLAT window, not a photographic lens.
    plate = plate.cut(bore(0, -133.4, z, 6.2, 1.15))
    for x in (-20, 20):
        plate = plate.cut(bore(x, -136, z, 1.7, 17))
    opening = face(34, 38, 7, -118, 18, z + 2)
    pcb = box(0, -124.24, z - 9.462, 25, 1.12, 23.862)
    for x in (-10.5, 10.5):
        for dz in (-.1, 12.4):
            pcb = pcb.cut(bore(x, -126, z + dz, 1.1, 5))
    package = box(0, -126.55, z - 6.25, 14.4, 3.5, 16.5)
    lens = bore(0, -130.66, z, 2.875, 2.36)
    glass = bore(0, -130.78, z, 2.375, .1)
    return {"cartridge": plate.clean(), "opening": opening,
            "pcb": pcb, "package": package, "lens": lens, "glass": glass,
            "mount_holes_x": [-10.5, 10.5], "mount_holes_z_from_axis": [-.1, 12.4],
            "pcb_front_y": -124.8, "front_aperture": 10.0}

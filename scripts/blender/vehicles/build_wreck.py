# VEH_wreck: burned-out generic civilian sedan, ~4.5 m. Simple blocky 3-box body from convex side-profile prisms,
# empty window openings with a few glass shards, charred interior, front-left door missing, flat tyres,
# body rolled ~2.5 deg onto the left side. Front = -Y, ground z=0, root at the footprint centre.
# Separate destructible parts: wheels (axle pivot), 3 doors (hinge pivot), hood (hinge pivot), trunk lid.
import math
import veh_lib as V
from veh_lib import Part, T, rot, PF, Vector

NAME = 'wreck'
R, W = 0.31, 0.2
TR = 0.76
YF, YR = -1.36, 1.34
ROLL = 2.5  # deg, left side (+X) lower
FLAT = {1: 0.1, -1: 0.035}  # flat-tyre squash per side


def prism(p, poly, x0, x1, mat='burnt', cham=0.035):
    """side-view CCW (y,z) convex polygon extruded from x0 to x1, chamfered on both outer sides"""
    xm = (x0 + x1) / 2
    for s, xe in ((1, x1), (-1, x0)):
        t = abs(xe - xm)
        p.pslab(V.yz_frame(xm, s), V.yz_poly(poly, s), t, cham=cham, mat=mat)


def body(p):
    bz = 0.3
    # front: upper hood block over the wheels + lower nose block + engine block between the wheels
    prism(p, [(-2.25, 0.6), (-1.0, 0.6), (-1.0, 0.9), (-2.0, 0.82), (-2.24, 0.76)], -0.84, 0.84)
    prism(p, [(-2.28, bz + 0.05), (-1.74, bz), (-1.74, 0.62), (-2.27, 0.62)], -0.84, 0.84)
    prism(p, [(-1.74, bz), (-1.0, bz), (-1.0, 0.62), (-1.74, 0.62)], -0.52, 0.52, mat='char', cham=0.01)
    # rear: trunk block + lower tail block + inner block
    prism(p, [(1.0, 0.6), (2.24, 0.6), (2.25, 0.84), (2.15, 0.9), (1.0, 0.92)], -0.84, 0.84)
    prism(p, [(1.72, bz), (2.26, bz + 0.06), (2.27, 0.62), (1.72, 0.62)], -0.84, 0.84)
    prism(p, [(1.0, bz), (1.72, bz), (1.72, 0.62), (1.0, 0.62)], -0.52, 0.52, mat='char', cham=0.01)
    # cabin floor, sills, firewall, rear bulkhead
    p.box(T((0, 0, bz + 0.05)), (1.66, 2.0, 0.1), mat='char', bev=0.01)
    for s in (-1, 1):
        p.box(T((s * 0.8, 0, bz + 0.07)), (0.08, 2.0, 0.14), mat='burnt', bev=0.015)
        # wheel-arch shadows on the inner fender walls
        for y in (YF, YR):
            p.box(T((s * 0.6, y, 0.55)), (0.04, 0.72, 0.1), mat='char', bev=0.005)
    p.box(T((0, -0.98, 0.65)), (1.6, 0.04, 0.6), mat='char', bev=0.01)
    p.box(T((0, 1.0, 0.65)), (1.6, 0.04, 0.6), mat='char', bev=0.01)
    # greenhouse: pillars + roof (window openings left empty)
    zt = 1.38
    for s in (-1, 1):
        x0, x1 = s * 0.8, s * 0.68
        V.beam(p, (x0, -1.0, 0.9), (x1, -0.4, zt), 0.07, 0.06, mat='burnt')       # A
        V.beam(p, (s * 0.76, 0.05, 0.92), (s * 0.68, 0.05, zt), 0.08, 0.06, mat='burnt')  # B
        V.beam(p, (x0, 1.05, 0.92), (x1, 0.75, zt), 0.16, 0.06, mat='burnt')       # C
        p.box(T((s * 0.8, 0.02, 0.94)), (0.06, 2.0, 0.04), mat='burnt', bev=0.01)  # beltline rail
    p.pslab(T((0, 0, zt - 0.02)), V.round_rect(1.38, 1.2, 0.08, 2), 0.05, cham=0.02, mat='burnt')
    p.box(T((0, 0.17, zt - 0.03)), (1.3, 1.1, 0.02), mat='char', bev=0.0)
    # roof dent
    p.box(T((0.2, 0.3, zt + 0.03)) @ rot(4, -3, 0), (0.6, 0.5, 0.02), mat='rust', bev=0.01)
    # windshield / rear window frames (empty), shards stuck in the frames
    for y0, y1 in ((-1.0, -0.4), (1.05, 0.75)):
        V.beam(p, (-0.66, y0, 0.93), (0.66, y0, 0.93), 0.05, 0.04, mat='burnt')
        V.beam(p, (-0.62, y1, zt - 0.02), (0.62, y1, zt - 0.02), 0.05, 0.04, mat='burnt')
    shards = [((-0.5, -0.97, 0.97), (0, -0.6, 0.8), [(-0.1, 0), (0.12, 0), (0.02, 0.16)]),
              ((0.3, -0.95, 0.97), (0, -0.6, 0.8), [(-0.06, 0), (0.1, 0), (-0.02, 0.09)]),
              ((-0.4, -0.45, 1.33), (0, -0.6, 0.8), [(-0.12, 0.0), (0.08, -0.13), (0.1, 0.0)]),
              ((0.71, 0.5, 1.0), (1, 0, 0.1), [(-0.12, 0), (0.1, 0), (0.0, 0.12)]),
              ((-0.71, 0.55, 1.0), (-1, 0, 0.1), [(-0.15, 0), (0.1, 0), (-0.05, 0.1)]),
              ((0.0, 0.98, 0.97), (0, 0.6, 0.8), [(-0.2, 0), (0.15, 0), (0.0, 0.1)])]
    for c, n, tri in shards:
        p.pslab(PF(c, n, (0, 0, 1)), tri, 0.006, cham=0.0, mat='shard')
    # charred interior: seat frames, dash, steering wheel
    for x in (-0.38, 0.38):
        p.box(T((x, -0.35, 0.5)), (0.48, 0.5, 0.12), mat='rust', bev=0.02)
        p.box(T((x, -0.12, 0.78)) @ rot(-12, 0, 0), (0.46, 0.06, 0.5), mat='char', bev=0.02)
        for k in range(4):
            V.rod(p, (x - 0.2, -0.55 + k * 0.13, 0.57), (x + 0.2, -0.55 + k * 0.13, 0.57), 0.006, 'rust', 5)
    p.box(T((0, 0.55, 0.52)), (1.4, 0.5, 0.14), mat='char', bev=0.03)
    p.box(T((0, 0.78, 0.75)) @ rot(-15, 0, 0), (1.4, 0.08, 0.45), mat='char', bev=0.02)
    p.box(T((0, -0.85, 0.85)), (1.5, 0.2, 0.16), mat='char', bev=0.03)
    p.ring(PF((0.38, -0.68, 0.92), (0, -1, 0.6), (0, 0, 1)), 0.17, 0.15, 0.025, mat='rust', n=16)
    # ash heap on the floor
    p.pslab(T((0.1, 0.2, 0.4)), V.round_rect(1.0, 0.7, 0.2, 2), 0.04, cham=0.03, mat='ash')
    # lamps (empty sockets), grille, plate holder
    for s in (-1, 1):
        p.cyl(PF((s * 0.6, -2.255, 0.68), (0, -1, 0)), 0.09, 0.03, mat='hole', n=12)
        p.box(T((s * 0.62, 2.27, 0.74)), (0.3, 0.02, 0.1), mat='hole', bev=0.0)
    p.box(T((0, -2.265, 0.66)), (0.6, 0.02, 0.12), mat='hole', bev=0.0)
    for k in range(5):
        p.box(T((0, -2.27, 0.61 + k * 0.025)), (0.58, 0.012, 0.008), mat='rust', bev=0.0)
    # left front door opening: hinge stubs + a charred door card stuck to the inner sill
    for z in (0.55, 0.8):
        p.box(T((0.83, -0.97, z)), (0.04, 0.05, 0.08), mat='rust', bev=0.006)


def door(tag, s, y0, y1, off, M):
    d = Part('%s_door_%s' % (NAME, tag), M)
    poly = [(y0, 0.36), (y1, 0.36), (y1, 0.92), (y0, 0.92)]
    d.pslab(V.yz_frame(s * 0.82, s), V.yz_poly(poly, s), 0.04, cham=0.012, mat='burnt')
    # empty window frame above the door
    top = [(y0 + 0.04, 0.92), (y1 - 0.03, 0.92), (y1 - 0.22 if y1 > 0.5 else y1 - 0.03, 1.3),
           (y0 + 0.45 if y0 < -0.5 else y0 + 0.03, 1.3)]
    if len(top) == 4:
        inner = V.inset(top, 0.035)
        d.pframe(V.yz_frame(s * 0.79, s) @ T((0, 0, 0)), V.yz_poly(top, s), V.yz_poly(inner, s), 0.03, mat='burnt',
                 cham=0.008)
    d.box(T((s * 0.86, y1 - 0.15, 0.82)), (0.03, 0.12, 0.03), mat='rust', bev=0.006)  # handle
    hy = y0 + 0.02
    pv = M @ Vector((s * 0.84, hy, 0.64))
    return d, pv


def build():
    coll, root = V.new_vehicle(NAME)
    off = Vector((0, 0.0, 0))
    M = T(off) @ T((0, 0, 0.02)) @ rot(0, ROLL, 0)
    p = Part(NAME + '_body', M)
    body(p)
    hd = Part(NAME + '_hood', M)
    hd.pslab(T((0, -1.6, 0.86)) @ rot(-4.5, 0, 0), V.round_rect(1.62, 1.2, 0.06, 2), 0.035, cham=0.012, mat='burnt')
    trunk = Part(NAME + '_trunk_lid', M)
    trunk.pslab(T((0, 1.6, 0.91)) @ rot(2.0, 0, 0), V.round_rect(1.6, 1.1, 0.06, 2), 0.03, cham=0.01, mat='burnt')
    bumpers = []
    for tag, y in (('F', -2.33), ('R', 2.33)):
        b = Part('%s_bumper_%s' % (NAME, tag), M)
        b.box(T((0, y, 0.42)), (1.72, 0.12, 0.16), mat='rust', bev=0.03)
        bumpers.append((b, M @ Vector((0, y, 0.42))))
    V.veh_finish(p, (0, 0, 0), coll, root, hz_k=0.45)
    V.veh_finish(hd, M @ Vector((0, -1.0, 0.9)), coll, root, hz_k=0.45)
    V.veh_finish(trunk, M @ Vector((0, 1.05, 0.93)), coll, root, hz_k=0.45)
    for b, pv in bumpers:
        V.veh_finish(b, pv, coll, root, hz_k=0.45)
    # doors: front-left is missing
    for tag, s, y0, y1 in (('FR', -1, -0.98, 0.04), ('RL', 1, 0.04, 1.02), ('RR', -1, 0.04, 1.02)):
        d, pv = door(tag, s, y0, y1, off, M)
        V.veh_finish(d, pv, coll, root, hz_k=0.45)
    # wheels: flat tyres, burnt rubber
    wl = []
    for side, tag in ((1, 'L'), (-1, 'R')):
        for y, fr in ((YF, 'F'), (YR, 'R')):
            fl = FLAT[side]
            ctr = Vector((side * TR, y, R - fl)) + off
            nm = '%s_wheel_%s%s' % (NAME, fr, tag)
            wp = Part(nm, T(ctr))
            V.wheel(wp, T((0, 0, 0)), R, W, side=side, style='civil', n=24, lugs=0, flat=fl, nuts=4, holes=0,
                    rim_mat='rust', rim_r=0.19, dent=0.1 if fr == 'F' else 0.0)
            wl.append(V.veh_finish(wp, ctr, coll, root, hz_fn=V.wheel_hz(R)))
    V.burn_objects(wl, amount=1.0)
    return coll, root

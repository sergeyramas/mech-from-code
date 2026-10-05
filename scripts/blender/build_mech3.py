# Heavy mech v3 build (procedural, no generators). Proportions measured from reference-sheet-4views-a
# (H = 9.0 m). Axes: mech faces -Y, L = -X (fist), R = +X (cannon). Pose is baked into meshes,
# object rotations are zero, pivots sit at the joints (same names/hierarchy as v2).
import os
import bpy, sys, math, random, importlib
from mathutils import Vector, Matrix

SCRIPTS = os.path.expanduser('~/Documents/learning/mech-test/blender/scripts')
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)
import mech_lib3 as L
importlib.reload(L)
from mech_lib3 import (Part, T, rot, S, P, PF, frame, seg_rot, nrm, outline, inset, rb, rbx, rby, finish,
                       build_materials, tri_count)

COLL = 'HeavyMech'
TUNE = globals().get('TUNE', {})


def tv(key, default):
    return TUNE.get(key, default)


def xr(s, a, b):
    """x-range for side s given inner/outer distances a, b (outward positive)"""
    u, v = s * a, s * b
    return (min(u, v), max(u, v))


def sn(s):
    return 'L' if s < 0 else 'R'


def no_tb(n, c):
    return n.z < -0.55 or n.z > 0.85


def get_coll():
    coll = bpy.data.collections.get(COLL)
    if coll is None:
        coll = bpy.data.collections.new(COLL)
        bpy.context.scene.collection.children.link(coll)
    for o in list(coll.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    for me in list(bpy.data.meshes):
        if me.users == 0:
            bpy.data.meshes.remove(me)
    return coll


# ------------------------------------------------------------------ hip
def build_hip():
    p = Part('hip')
    pts = (rb(-0.72, 0.72, -1.12, 0.95, 4.85, 0.25) + rb(-1.0, 1.0, -1.38, 1.2, 5.3, 0.35) +
           rb(-0.98, 0.98, -1.42, 1.25, 5.95, 0.35) + rb(-0.85, 0.85, -1.25, 1.1, 6.2, 0.3))
    p.armor_hull(pts, t=0.09, maxs=0.85, seed=11, skip=lambda n, c: no_tb(n, c) or abs(n.x) > 0.8)
    # crotch plate (downward hexagon, layered)
    m = PF((0, -1.47, 5.12), nrm(0, -1, -0.12), (0, 0, 1))
    poly = [(-0.95, 0.8), (-0.95, -0.12), (-0.64, -0.5), (-0.27, -0.8), (0.27, -0.8), (0.64, -0.5), (0.95, -0.12),
            (0.95, 0.8)]
    p.pplate(m, [(x * 0.75, y * 0.8) for x, y in poly], 0.14, 0.04, 'armor_dark', True, 0.2, 0.034, True, random.Random(5))
    p.box(m @ T((0, 0.0, 0.2)), (0.16, 1.2, 0.12), 'armor_dark', bev=0.03)
    for sx in (-1, 1):
        p.bolt(m @ T((sx * 0.5, 0.45, 0.2)), 0.05, 0.06, 'brass')
    # waist ring + axle
    p.ring(T((0, 0.0, 6.12)), 1.12, 0.6, 0.16, 'metal', n=32)
    p.cyl(P((0, 0, 5.45), (0, 90, 0)), 0.32, 2.3, 'metal', n=20, bev=0.02)
    # back mechanics / greebles
    p.greebles(PF((0, 1.27, 5.5), (0, 1, 0)), 1.6, 0.9, 22, seed=3)
    for sx in (-1, 1):
        p.cable((sx * 0.5, 1.15, 6.15), (sx * 0.7, 1.6, 5.8), (sx * 0.9, 1.4, 5.2), (sx * 1.1, 0.9, 5.0), 0.055)
        p.piston((sx * 0.75, -1.15, 6.05), (sx * 0.9, -0.95, 5.05), 0.07)
    return p


# ------------------------------------------------------------------ legs
def build_thigh(s):
    p = Part('thigh_' + sn(s))
    pts = (rb(*xr(s, 1.06, 2.14), -0.98, 0.68, 4.05, 0.25) + rb(*xr(s, 1.02, 2.17), -1.05, 0.75, 4.5, 0.32) +
           rb(*xr(s, 1.02, 2.15), -1.0, 0.8, 5.25, 0.3) + rb(*xr(s, 1.15, 2.05), -0.75, 0.6, 5.62, 0.25))
    hipdisc = (s * 2.12, -0.05, 5.12)

    def red(n, c):
        if s > 0 and n.y < -0.6 and c.z < 4.75:
            return (48.0, 0.55, 0.05)
        return None
    p.armor_hull(pts, t=0.09, maxs=0.8 * tv('leg_maxs', 1.0), seed=21 + s, skip=no_tb, avoid=[(hipdisc, 0.5)], red=red)
    p.drum(P((s * 1.55, 0, 5.45), (0, 90, 0)), 0.41, 0.8, ribs=3)
    p.disc(PF(hipdisc, (s, 0, 0)), 0.5, th=0.06, hub=0.1)
    # inner pistons + cables
    p.piston((s * 0.97, -0.55, 5.25), (s * 0.97, -0.35, 4.1), 0.07)
    p.piston((s * 0.97, 0.45, 5.2), (s * 0.97, 0.35, 4.15), 0.06)
    p.cable((s * 1.6, 0.75, 5.4), (s * 1.6, 1.05, 4.9), (s * 1.7, 1.0, 4.3), (s * 1.7, 0.7, 3.9), 0.05)
    return p


def build_shin(s):
    p = Part('shin_' + sn(s))
    # knee block
    kpts = (rb(*xr(s, 1.12, 2.22), -1.0, 0.7, 3.35, 0.25) + rb(*xr(s, 1.1, 2.25), -1.08, 0.75, 3.75, 0.3) +
            rb(*xr(s, 1.15, 2.2), -0.95, 0.65, 4.15, 0.25))
    p.armor_hull(kpts, t=0.08, maxs=0.7 * tv('leg_maxs', 1.0), seed=31 + s, skip=lambda n, c: no_tb(n, c) or abs(n.x) > 0.7)
    m = PF((s * 1.67, -1.15, 3.78), nrm(0, -1, 0.12), (0, 0, 1))
    p.pplate(m, outline(0.95, 0.85, (0.47, 0.22)), 0.12, 0.04, 'armor', True, 0.18, 0.032, True, random.Random(7))
    p.disc(PF((s * 2.25, -0.25, 3.85), (s, 0, 0)), tv('knee_r', 0.5), th=0.1, hub=0.12, teeth=tv('knee_teeth', 0))
    p.disc(PF((s * 1.1, -0.25, 3.85), (-s, 0, 0)), tv('knee_ri', 0.38), th=0.12, hub=0.12, teeth=tv('knee_teeth', 0))
    # shin body
    lowdisc = (s * 2.72, 0.62, 3.08)
    pts = (rb(*xr(s, 1.08, 2.6), -0.92, 0.98, 1.95, 0.3) + rb(*xr(s, 0.95, 2.73), -1.15, 1.15, 2.35, 0.35) +
           rb(*xr(s, 0.95, 2.73), -1.17, 1.17, 3.0, 0.35) + rb(*xr(s, 1.05, 2.62), -1.0, 1.05, 3.4, 0.3))
    p.armor_hull(pts, t=0.1, maxs=0.95 * tv('leg_maxs', 1.0), seed=41 + s, skip=lambda n, c: no_tb(n, c) or (n.y < -0.9 and 2.0 < c.z < 3.4), avoid=[(lowdisc, 0.45)], tilt=6.0)
    p.disc(PF(lowdisc, (s, 0, 0)), 0.45, th=0.08, hub=0.08)
    # big faceted shin guard on the front
    m = PF((s * 1.84, -1.24, 2.72), nrm(0, -1, 0.06), (0, 0, 1))
    if tv('guard_split', False):
        up = [(-0.62, 0.04), (0.62, 0.04), (0.82, 0.24), (0.82, 0.48), (0.6, 0.68), (-0.6, 0.68), (-0.82, 0.48),
              (-0.82, 0.24)]
        lo = [(-0.5, -0.64), (0.5, -0.64), (0.78, -0.36), (0.78, -0.1), (0.6, 0.0), (-0.6, 0.0), (-0.78, -0.1),
              (-0.78, -0.36)]
        p.pplate(m @ T((0, 0, 0.05)), up, 0.13, 0.03, 'armor', True, 0.15, 0.03, False, random.Random(40 + s),
                 red=(50.0, 0.6, 0.0) if s > 0 else None)
        p.pplate(m, lo, 0.13, 0.03, 'armor', True, 0.15, 0.03, True, random.Random(42 + s))
        p.box(m @ T((0, 0.02, 0.06)), (1.5, 0.08, 0.1), 'metal', bev=0.01)
    else:
        guard = [(-0.55, -0.62), (0.55, -0.62), (0.8, -0.2), (0.82, 0.42), (0.55, 0.66), (-0.55, 0.66),
                 (-0.82, 0.42), (-0.8, -0.2)]
        p.pplate(m, guard, 0.13, 0.03, 'armor', True, 0.17, 0.03, True, random.Random(40 + s),
                 red=(50.0, 0.5, 0.1) if s > 0 else None)
    p.pplate(m @ T((0, -0.95, -0.15)), [(-0.5, -0.28), (0.5, -0.28), (0.62, 0.0), (0.62, 0.3), (-0.62, 0.3),
                                         (-0.62, 0.0)], 0.12, 0.03, 'armor_dark', True, 0.17, 0.03, False, None)
    # knee drum between the discs
    p.drum(P((s * 1.67, -0.25, 3.85), (0, 90, 0)), 0.4, 1.0, ribs=2)
    # calf mechanics between knee and shin
    p.cable((s * 1.4, 0.7, 3.9), (s * 1.3, 1.25, 3.6), (s * 1.3, 1.3, 3.1), (s * 1.35, 1.1, 2.6), 0.05)
    p.piston((s * 2.3, 0.55, 3.95), lowdisc, 0.06)
    return p


FOOT_SEGS = [  # (u0,u1,y0,y1) bottom, (u0,u1,y0,y1) top, ztop ; u = outward offset from foot centre
    ((-0.72, 0.72, -2.62, -1.05), (-0.6, 0.6, -1.95, -1.05), 1.18),
    ((0.78, 1.36, -2.42, -0.95), (0.74, 0.98, -1.85, -0.95), 0.98),
    ((-1.36, -0.78, -2.42, -0.95), (-0.98, -0.74, -1.85, -0.95), 0.98),
    ((0.78, 1.36, -0.85, 0.6), (0.74, 0.98, -0.8, 0.55), 1.0),
    ((-1.36, -0.78, -0.85, 0.6), (-0.98, -0.74, -0.8, 0.55), 1.0),
    ((-0.72, 0.72, 0.72, 2.02), (-0.6, 0.6, 0.72, 1.5), 1.05),
    ((0.78, 1.36, 0.68, 1.88), (0.74, 0.98, 0.68, 1.4), 0.95),
    ((-1.36, -0.78, 0.68, 1.88), (-0.98, -0.74, 0.68, 1.4), 0.95),
]


def build_foot(s):
    p = Part('foot_' + sn(s))
    c = 2.1

    def X(u0, u1):
        return xr(s, c + u0, c + u1)
    # dark core filling the gaps between the skirt blocks
    p.hullmesh(rb(*X(-1.25, 1.25), -2.3, 1.8, 0.02, 0.3) + rb(*X(-0.85, 0.85), -1.4, 1.3, 1.1, 0.3), 'metal')
    g = tv('foot_gap', 0.0)
    for k, (bt, tp, zt) in enumerate(FOOT_SEGS):
        u0, u1, y0, y1 = bt
        v0, v1, w0, w1 = tp
        u0, u1, v0, v1 = u0 + g, u1 - g, v0 + g, v1 - g
        if y0 > -2.5:
            y0, w0 = y0 + g, w0 + g
        if y1 < 1.9:
            y1, w1 = y1 - g, w1 - g
        pts = (rb(*X(u0, u1), y0, y1, 0.0, 0.12) + rb(*X(u0 - 0.03, u1 + 0.03), y0 - 0.03, y1 + 0.03, 0.2, 0.14) +
               rb(*X(v0, v1), w0, w1, zt, 0.1))
        p.armor_hull(pts, t=0.08, maxs=1.6, seed=51 + 7 * k + s, skip=no_tb, tilt=2.0, sub_p=0.6, cut_p=0.4)
    # ribbed band
    bx0, bx1 = X(-0.85, 0.85)
    p.hullmesh(rb(bx0, bx1, -1.35, 1.25, 1.1, 0.3) + rb(bx0, bx1, -1.35, 1.25, 1.47, 0.3), tv('band_mat', 'metal'))
    for y in [-1.25 + 0.2 * i for i in range(13)]:
        for xx in (bx0, bx1):
            p.box(T((xx, y, 1.29)), (0.1, 0.07, 0.34), 'armor_dark', bev=0.012)
    for x in [bx0 + 0.25 + 0.2 * i for i in range(int((bx1 - bx0 - 0.4) / 0.2) + 1)]:
        for yy in (-1.35, 1.25):
            p.box(T((x, yy, 1.29)), (0.07, 0.1, 0.34), 'armor_dark', bev=0.012)
    fr = tv('foot_disc', 0.17)
    for y in (-0.55, 0.0, 0.55):
        p.disc(PF((s * (c + 0.86), y, 0.62), (s, 0, 0)), fr, th=0.05, hub=0.05, bolts=4)
        p.disc(PF((s * (c - 0.86), y, 0.62), (-s, 0, 0)), fr, th=0.05, hub=0.05, bolts=4)
    # ankle block + disc
    apts = (rb(*xr(s, 1.15, 2.65), -0.88, 0.95, 1.4, 0.25) + rb(*xr(s, 1.12, 2.68), -0.95, 1.0, 1.75, 0.3) +
            rb(*xr(s, 1.2, 2.6), -0.8, 0.85, 2.05, 0.25))
    p.armor_hull(apts, t=0.08, maxs=0.7, seed=61 + s, skip=lambda n, cc: no_tb(n, cc) or abs(n.x) > 0.7)
    p.cyl(P((s * 1.9, 0.3, 1.72), (0, 90, 0)), 0.36, 1.45, 'metal', n=24, bev=0.02)
    p.disc(PF((s * 2.68, 0.3, 1.72), (s, 0, 0)), 0.42, th=0.08, hub=0.1)
    p.disc(PF((s * 1.12, 0.3, 1.72), (-s, 0, 0)), 0.3, th=0.04, hub=0.05, bolts=6)
    # deck mechanics + pistons
    p.greebles(PF((s * c, -1.65, 1.2), (0, 0, 1)), 1.2, 0.5, 8, seed=70 + s)
    p.greebles(PF((s * c, 1.45, 1.1), (0, 0, 1)), 1.2, 0.45, 6, seed=80 + s)
    p.piston((s * 1.9, -0.9, 1.65), (s * 1.9, -1.75, 1.2), 0.08)
    p.piston((s * 1.5, 0.95, 1.7), (s * 1.5, 1.55, 1.2), 0.07)
    return p


# ------------------------------------------------------------------ torso / cockpit
def build_torso():
    p = Part('torso')
    # core volume (back + sides); the front is formed by the two chest pods and the head
    pts = (rb(-1.25, 1.25, -1.4, 1.25, 6.15, 0.35) + rb(-1.75, 1.75, -1.7, 1.5, 6.45, 0.45) +
           rb(-2.05, 2.05, -1.75, 1.6, 6.95, 0.5) + rb(-2.05, 2.05, -1.75, 1.6, 7.35, 0.5) +
           rb(-1.95, 1.95, -1.6, 1.6, 7.95, 0.45) + rb(-1.65, 1.65, -1.4, 1.45, 8.2, 0.4))
    p.armor_hull(pts, t=0.1, maxs=0.95, seed=101, skip=lambda n, c: n.z < -0.55 or n.y < -0.5, sub_p=0.55)
    # chest pods (faceted octagonal fronts, red diagonal marks on the outer upper faces)
    for s in (-1, 1):
        pp = (rb(*xr(s, 1.0, 1.95), -1.85, -0.6, 6.35, 0.3) + rb(*xr(s, 0.92, 2.12), -2.25, -0.4, 6.75, 0.42) +
              rb(*xr(s, 0.92, 2.14), -2.2, -0.4, 7.55, 0.45) + rb(*xr(s, 0.95, 1.95), -1.6, -0.4, 8.25, 0.35))

        def red(n, c, s=s):
            if c.z > 6.9 and n.y < -0.15 and s * n.x > 0.25:
                return 'plate'
            if c.z > 7.3 and n.y < -0.6 and abs(c.x) > 1.55:
                return (60.0 if s < 0 else 120.0, 0.35, s * 0.25)
            return None
        p.armor_hull(pp, t=0.1, maxs=0.9, seed=110 + s, red=red, skip=lambda n, c: n.z < -0.6 or n.y > 0.5,
                     sub_p=0.6, tilt=3.0)
        # vertical vent grille on the inner front face, next to the head
        m = PF((s * 1.18, -2.27, 7.35), nrm(0, -1, 0.0), (0, 0, 1))
        p.box(m @ T((0, 0, 0.03)), (0.3, 0.75, 0.1), 'armor_dark', bev=0.02)
        p.grille(m @ T((0, 0, 0.08)), 0.2, 0.62, n=6, depth=0.05)
    # back: two tall vertical grille housings
    for sx in (-1, 1):
        m = PF((sx * 0.5, 1.72, 7.3), (0, 1, 0), (0, 0, 1))
        p.box(m @ T((0, 0, 0.05)), (0.72, 1.75, 0.2), 'armor_dark', bev=0.04)
        p.grille(m @ T((0, 0, 0.16)), 0.52, 1.5, n=11, depth=0.1)
        for yy in (-0.8, 0.8):
            for xx in (-0.3, 0.3):
                p.rivet(m @ T((xx, yy, 0.15)), 0.035)
    # side grilles
    for sx in (-1, 1):
        m = PF((sx * 2.16, -1.0, 7.35), (sx, 0, 0), (0, 0, 1))
        p.box(m @ T((0, 0, 0.02)), (0.7, 0.62, 0.12), 'armor_dark', bev=0.03)
        p.grille(m @ T((0, 0, 0.09)), 0.55, 0.48, n=5, depth=0.06)
    # top vents / hump details
    for sx in (-1, 1):
        p.box(T((sx * 1.48, 0.1, 8.33)), (0.36, 0.55, 0.22), 'armor_dark', bev=0.03)
        p.grille(PF((sx * 1.48, 0.1, 8.445), (0, 0, 1), (0, 1, 0)), 0.26, 0.42, n=4, depth=0.05)
    p.greebles(PF((0, 1.2, 8.3), (0, 0, 1)), 2.4, 0.5, 14, seed=105)
    # waist: dark mechanics under the chest
    p.ring(T((0, 0.0, 6.05)), 1.2, 0.95, 0.14, 'armor_dark', n=32)
    p.greebles(PF((0, -1.45, 6.25), nrm(0, -1, -0.5)), 1.8, 0.4, 12, seed=106)
    for sx in (-1, 1):
        p.cyl(P((sx * 0.75, -1.3, 6.2), (0, 90, 0)), 0.16, 0.5, 'metal', n=14)
        p.cable((sx * 1.7, 0.8, 6.6), (sx * 2.3, 1.0, 6.9), (sx * 2.4, 0.9, 7.2), (sx * 2.25, 0.7, 7.4), 0.06)
        p.pipe((sx * 1.2, 1.65, 6.4), (sx * 1.2, 1.65, 8.0), 0.06)
    return p


def build_cockpit():
    p = Part('cockpit')
    pts = (rb(-0.55, 0.55, -1.9, -0.6, 6.35, 0.15) + rb(-0.9, 0.9, -2.45, -0.6, 6.75, 0.25) +
           rb(-0.92, 0.92, -2.5, -0.5, 7.6, 0.3) + rb(-0.9, 0.9, -2.15, -0.4, 8.15, 0.3) +
           rb(-0.72, 0.72, -1.5, 0.3, 8.5, 0.25))
    p.armor_hull(pts, t=0.09, maxs=0.75, seed=121, skip=lambda n, c: n.z < -0.8 or n.y > 0.6, sub_p=0.45,
                 tilt=2.0, avoid=[((0, -2.33, 7.98), 0.3)])
    # visor band with two amber windows (on the upper slanted face)
    m = PF((0, -2.36, 7.98), nrm(0, -1, 0.42), (0, 0, 1))
    p.box(m @ T((0, 0, 0.0)), (1.45, 0.32, 0.16), 'metal', bev=0.025)
    for sx in (-1, 1):
        p.box(m @ T((sx * 0.3, 0, 0.07)), (0.4, 0.12, 0.06), 'glow', bev=0.0)
        p.box(m @ T((sx * 0.3, 0.1, 0.1)), (0.5, 0.05, 0.07), 'armor_dark', bev=0.01)
    p.box(m @ T((0, 0, 0.08)), (0.1, 0.3, 0.08), 'armor_dark', bev=0.01)
    # chin beak plate
    m2 = PF((0, -2.3, 6.62), nrm(0, -1, -0.8), (0, 0, 1))
    p.pplate(m2, [(-0.5, 0.25), (-0.5, -0.05), (0.0, -0.35), (0.5, -0.05), (0.5, 0.25)], 0.08, 0.025, 'armor_dark',
             True, 0.18, 0.028, False, random.Random(9))
    # antenna / sensor boxes (top of the silhouette = 9.0 m)
    for sx in (-1, 1):
        cx = sx * 0.62
        p.box(T((cx, -0.15, 8.78)), (0.5, 0.42, 0.44), 'armor', bev=0.035)
        p.box(T((cx, -0.15, 8.57)), (0.36, 0.3, 0.1), 'metal', bev=0.0)
        p.cyl(P((cx - sx * 0.08, -0.37, 8.82), (90, 0, 0)), 0.085, 0.05, 'glass', n=12)
        p.ring(P((cx - sx * 0.08, -0.38, 8.82), (90, 0, 0)), 0.11, 0.08, 0.04, 'brass', n=12)
        p.box(T((cx + sx * 0.12, -0.37, 8.72)), (0.14, 0.03, 0.07), 'glow', bev=0.0)
        for zz in (8.62, 8.94):
            for xx in (-0.18, 0.18):
                p.rivet(PF((cx + xx, -0.365, zz), (0, -1, 0)), 0.026)
    return p


# ------------------------------------------------------------------ shoulders / launchers / arms
def build_shoulder(s):
    p = Part('shoulder_' + sn(s))
    p.drum(P((s * 2.32, 0.7, 7.45), (0, 90, 0)), 0.42, 0.5, ribs=2)
    p.box(T((s * 3.1, 0.75, 7.0)), (1.5, 1.6, 0.14), 'armor_dark', bev=0.03)
    p.cyl(P((s * 3.3, 0.7, 7.0), (0, 0, 0)), 0.38, 0.3, 'metal', n=20, bev=0.02)
    return p


def build_launcher(s):
    p = Part('launcher_' + sn(s))
    x0, x1 = xr(s, 2.33, 3.87 - (tv('launch_dx', 0.06) if tv('v31', False) else 0.0))
    cx = s * 3.1
    pts = rby(-0.36, x0, x1, 7.12, 8.54, 0.28) + rby(2.25, x0, x1, 7.14, 8.52, 0.3)
    if tv('v31', False):
        lt = tv('l_top', 8.46)
        lc = tv('l_ch', 0.34)
        pts = (rby(-0.36, x0, x1, 7.12, lt, lc) + rby(2.25, x0, x1, 7.14, tv('lz_back', 8.1), 0.3) +
               rby(tv('ly_top', 1.85), x0, x1, 7.4, lt - 0.02, lc))
    p.armor_hull(pts, t=0.1, maxs=1.35, seed=141 + s, skip=lambda n, c: n.y < -0.9 or n.z < -0.55, sub_p=0.65,
                 tilt=2.0)
    m = PF((cx, -0.38, 7.83), (0, -1, 0), (0, 0, 1))
    outer = outline(1.74, 1.62, (0.3, 0.3))
    inner = outline(1.38, 1.26, (0.14, 0.14))
    p.pframe(m, outer, inner, 0.16, 'armor')
    p.rivet_ring(m, outer, 0.08, 0.16, 0.16, 0.032)
    p.slab(m @ T((0, 0, -0.14)), 1.4, 1.28, 0.04, (0.14, 0.14), 0.0, 'metal')
    for i in (-1, 0, 1):
        for j in (-1, 0, 1):
            p.tube(m @ T((i * 0.42, j * 0.39, -0.02)), 0.165, 0.7)
    p.box(T((s * 3.45, 0.57, 8.7)), (0.26, 0.24, 0.18), 'armor_dark', bev=0.02)
    if tv('v31', False):
        p.box(T((s * 2.75, 1.05, 8.66)), (0.4, 0.5, 0.1), 'metal', bev=0.02)
    else:
        p.box(T((s * 2.75, 1.9, 8.66)), (0.4, 0.5, 0.1), 'metal', bev=0.02)
    return p


def build_arm(s):
    p = Part('arm_' + sn(s))
    pts = (rb(*xr(s, 2.88, 3.78), 0.0, 1.78, 6.15, 0.22) + rb(*xr(s, 2.85, 3.8), -0.05, 1.82, 6.6, 0.25) +
           rb(*xr(s, 2.88, 3.78), 0.0, 1.8, 7.0, 0.22))
    p.armor_hull(pts, t=0.09, maxs=0.75, seed=161 + s, skip=no_tb)
    p.drum(P((s * 3.33, 0.6, 6.2), (0, 90, 0)), 0.3, 0.75, ribs=2)
    return p


def build_cannon():
    s = 1
    p = Part('cannon_R')
    yaw = tv('cannon_yaw', 20.0)
    O = Vector((3.25, 0.4, 5.35))
    # elbow connector + discs (world aligned)
    cp = rb(2.9, 3.82, 0.15, 1.25, 5.85, 0.2) + rb(2.95, 3.8, 0.2, 1.2, 6.35, 0.2)
    p.armor_hull(cp, t=0.08, maxs=0.7, seed=171, skip=no_tb)
    p.disc(PF((3.86, 0.72, 6.02), (1, 0, 0)), 0.45, th=0.1, hub=0.12)
    p.push(T(O) @ rot(0, 0, yaw))
    # mechanism box (local: forward = -Y)
    pts = rby(-2.02, -0.55, 0.55, -0.56, 0.56, 0.16) + rby(0.28, -0.55, 0.55, -0.56, 0.56, 0.16)
    p.armor_hull(pts, t=0.09, maxs=0.95, seed=173, skip=lambda n, c: n.y < -0.9, sub_p=0.6)
    p.disc(PF((-0.62, -0.5, -0.05), (-1, 0, 0)), 0.4, th=0.04, hub=0.06)
    p.greebles(PF((0.0, -1.0, 0.64), (0, 0, 1)), 0.9, 1.6, 12, seed=175)
    # wrist drum + barrels
    p.drum(P((0, -2.27, -0.13), (90, 0, 0)), 0.5, 0.45, ribs=2)
    p.disc(PF((0, -2.5, -0.13), (0, -1, 0)), 0.46, th=0.05, hub=0.04, bolts=8)
    for zb in (0.14, -0.38):
        if tv('v31', False):
            p.barrel2(P((0, -2.45, zb), (90, 0, 0)), tv('barrel_len', 2.92), 0.155, tv('shroud', 0.62))
        else:
            p.barrel(P((0, -2.45, zb), (90, 0, 0)), tv('barrel_len', 2.92), 0.155, ribs_len=0.85, ribs=9)
    # under magazine + feed
    p.armor_hull(rb(-0.3, 0.45, -1.5, -0.35, -0.98, 0.08) + rb(-0.3, 0.45, -1.5, -0.35, -0.62, 0.08), t=0.06,
                 maxs=0.6, seed=177, skip=no_tb, rivets=True)
    p.cable((0.5, -0.8, -0.7), (0.9, -0.4, -0.9), (0.8, 0.3, -0.5), (0.55, 0.3, 0.1), 0.06)
    p.piston((0.62, 0.1, 0.3), (0.62, -1.4, 0.35), 0.07)
    p.pop()
    return p


def build_fist():
    s = -1
    p = Part('fist_L')
    p.push(T((-3.55, 0.6, 6.3)) @ rot(0, tv('fist_tilt', 14.0), 0))
    rnd = random.Random(191)

    def redfn(kind):
        def f(n, c):
            if kind == 'outer' and n.x < -0.6:
                return 'plate' if c.z < -1.0 else (60.0, 0.6, 0.0)
            if kind == 'front' and n.y < -0.6 and c.x < -0.3:
                return (35.0, 0.55, 0.1)
            return None
        return f
    # wrist block
    p.armor_hull(rb(-0.87, 0.57, -0.8, 0.95, -0.66, 0.2) + rb(-0.87, 0.57, -0.8, 0.95, 0.05, 0.2), t=0.09,
                 maxs=0.7, seed=192, skip=no_tb)
    # main fist: 2x2 blocks
    blocks = [((-1.1, -0.16), (-0.95, 1.15), (-1.5, -0.7), 'outer'),
              ((-0.11, 0.78), (-0.9, 1.1), (-1.5, -0.72), 'front'),
              ((-1.08, -0.18), (-0.92, 1.12), (-2.2, -1.56), 'outer'),
              ((-0.13, 0.72), (-0.88, 1.05), (-2.15, -1.56), None)]
    for k, ((a, b), (c, d), (z0, z1), kind) in enumerate(blocks):
        pts = rb(a, b, c, d, z0, 0.18) + rb(a + 0.04, b - 0.04, c + 0.05, d - 0.05, z1, 0.2)
        p.armor_hull(pts, t=0.09, maxs=0.62, seed=200 + k, skip=lambda n, cc: n.z > 0.85 and kind is None,
                     red=redfn(kind) if kind else None, sub_p=0.5)
    # front grille on upper-outer block
    m = PF((-0.62, -1.07, -1.1), (0, -1, 0), (0, 0, 1))
    p.box(m @ T((0, 0, 0.03)), (0.72, 0.56, 0.1), 'armor_dark', bev=0.03)
    p.grille(m @ T((0, 0, 0.08)), 0.58, 0.42, n=5, depth=0.06)
    # knuckles
    for k, (c, d) in enumerate(((-0.86, -0.3), (-0.24, 0.36), (0.42, 1.0))):
        pts = rb(-0.9, 0.48, c, d, -2.72, 0.12) + rb(-0.95, 0.52, c, d, -2.22, 0.12)
        p.armor_hull(pts, t=0.07, maxs=0.8, seed=220 + k, skip=lambda n, cc: n.z > 0.85, rs=0.18, sub_p=0.0)
    # amber glow underneath + in the knuckle gap
    for y in (-0.55, 0.05, 0.7):
        p.box(T((-0.2, y, -2.75)), (0.6, 0.16, 0.04), 'glow', bev=0.0)
    p.box(T((-0.2, -0.93, -2.2)), (1.1, 0.05, 0.05), 'glow', bev=0.0)
    # wrist spring + piston on the back, cables
    p.spring(T((0.3, 1.18, -1.05)), 0.15, 0.95, turns=8, wire=0.032)
    p.cyl(T((0.3, 1.18, -0.58)), 0.07, 1.0, 'steel', n=10)
    p.cable((0.5, 0.9, 0.05), (0.85, 1.1, -0.4), (0.85, 1.2, -0.9), (0.6, 1.05, -1.3), 0.05)
    p.cable((-0.6, 1.0, 0.0), (-0.95, 1.2, -0.4), (-1.0, 1.25, -0.9), (-0.8, 1.15, -1.3), 0.05)
    p.pop()
    return p


# ================================================================== v3.1: scale-armour legs, toe skirt, hunched torso
def build_thigh31(s):
    p = Part('thigh_' + sn(s))
    tw = tv('thigh_dx', 0.08)
    pts = (rb(*xr(s, 1.06, 2.14 - tw), -0.98, 0.68, 4.05, 0.25) + rb(*xr(s, 1.02, 2.17 - tw), -1.05, 0.75, 4.5, 0.32) +
           rb(*xr(s, 1.02, 2.15 - tw), -1.0, 0.8, 5.25, 0.3) + rb(*xr(s, 1.15, 2.05 - tw), -0.75, 0.6, 5.62, 0.25))
    hipdisc = (s * (2.15 - tw), -0.05, 5.1)

    def red(n, c):
        if s > 0 and n.y < -0.6 and c.z < 4.75:
            return (48.0, 0.55, 0.05)
        return None
    p.scale_hull(pts, size=tv('sc_thigh', 0.74), t=0.09, seed=21 + s, skip=no_tb, avoid=[(hipdisc, 0.6)], red=red,
                 rk=tuple(tv('sc_rk', (0.52, 0.66))),
                 mech=tv('sc_mech', 0.7), core_in=tv('sc_core', 0.09))
    p.drum(P((s * 1.55, 0, 5.45), (0, 90, 0)), 0.41, 0.8, ribs=3)
    p.bigdisc(PF(hipdisc, (s, 0, 0)), tv('hip_r', 0.56), th=0.1, hub=0.1)
    p.piston((s * 0.97, -0.55, 5.25), (s * 0.97, -0.35, 4.1), 0.07)
    p.piston((s * 0.97, 0.45, 5.2), (s * 0.97, 0.35, 4.15), 0.06)
    p.cable((s * 1.6, 0.75, 5.4), (s * 1.6, 1.05, 4.9), (s * 1.7, 1.0, 4.3), (s * 1.7, 0.7, 3.9), 0.05)
    return p


def build_shin31(s):
    p = Part('shin_' + sn(s))
    kpts = (rb(*xr(s, 1.12, 2.22), -1.0, 0.7, 3.35, 0.25) + rb(*xr(s, 1.1, 2.25), -1.08, 0.75, 3.75, 0.3) +
            rb(*xr(s, 1.15, 2.2), -0.95, 0.65, 4.15, 0.25))
    kdisc = (s * 2.23, -0.2, 3.93)
    p.scale_hull(kpts, size=tv('sc_knee', 0.6), t=0.08, seed=31 + s, avoid=[(kdisc, 0.62)], rk=tuple(tv('sc_rk', (0.52, 0.66))),
                 skip=lambda n, c: no_tb(n, c) or s * n.x < -0.7, mech=tv('sc_mech', 0.7), core_in=tv('sc_core', 0.09))
    m = PF((s * 1.67, -1.15, 3.78), nrm(0, -1, 0.12), (0, 0, 1))
    p.pplate(m, outline(0.95, 0.85, (0.47, 0.22)), 0.12, 0.04, 'armor', True, 0.18, 0.032, True, random.Random(7))
    p.bigdisc(PF(kdisc, (s, 0, 0)), tv('knee_r', 0.55), th=0.15, hub=0.12)
    p.disc(PF((s * 1.1, -0.25, 3.85), (-s, 0, 0)), tv('knee_ri', 0.38), th=0.12, hub=0.12, teeth=tv('knee_teeth', 0))
    # shin body (narrower at the top so the lower knee disc stands proud)
    lowdisc = (s * tv('lowdisc_x', 2.5), 0.48, 3.2)
    yf = tv('shin_yf', -1.0)
    sw = tv('shin_dx', 0.1)
    pts = (rb(*xr(s, 1.08, 2.6 - sw), -0.92, 0.98, 1.95, 0.3) + rb(*xr(s, 0.95, 2.73 - sw), yf, 1.15, 2.35, 0.35) +
           rb(*xr(s, 0.95, 2.7 - sw), yf, 1.17, 3.0, 0.35) + rb(*xr(s, 1.05, tv('shin_top_x', 2.48)), -0.95, 1.05, 3.4, 0.3))
    p.scale_hull(pts, size=tv('sc_shin', 0.8), t=0.1, seed=41 + s, avoid=[(lowdisc, 0.6)], rk=tuple(tv('sc_rk', (0.52, 0.66))),
                 skip=lambda n, c: no_tb(n, c) or (n.y < -0.9 and 2.0 < c.z < 3.4), mech=tv('sc_mech', 0.7),
                 core_in=tv('sc_core', 0.09))
    p.bigdisc(PF(lowdisc, (s, 0, 0)), tv('lowdisc_r', 0.5), th=0.14, hub=0.09)
    # big faceted shin guard on the front
    m = PF((s * 1.84, yf - 0.05, 2.72), nrm(0, -1, 0.06), (0, 0, 1))
    up = [(-0.62, 0.04), (0.62, 0.04), (0.82, 0.24), (0.82, 0.48), (0.6, 0.68), (-0.6, 0.68), (-0.82, 0.48),
          (-0.82, 0.24)]
    lo = [(-0.5, -0.64), (0.5, -0.64), (0.78, -0.36), (0.78, -0.1), (0.6, 0.0), (-0.6, 0.0), (-0.78, -0.1),
          (-0.78, -0.36)]
    p.scale_plate(m @ T((0, 0, 0.05)), up, 0.13, 'armor', 0.032, False, random.Random(40 + s),
                  (50.0, 0.6, 0.0) if s > 0 else None, cham=0.045)
    p.scale_plate(m, lo, 0.13, 'armor', 0.032, True, random.Random(42 + s), None, cham=0.045)
    p.box(m @ T((0, 0.02, 0.06)), (1.5, 0.08, 0.1), 'metal', bev=0.01)
    p.scale_plate(m @ T((0, -0.95, -0.15)), [(-0.5, -0.28), (0.5, -0.28), (0.62, 0.0), (0.62, 0.3), (-0.62, 0.3),
                                              (-0.62, 0.0)], 0.12, 'armor_dark', 0.03, False, None, None, cham=0.04)
    p.drum(P((s * 1.67, -0.25, 3.85), (0, 90, 0)), 0.4, 1.0, ribs=2)
    p.cable((s * 1.4, 0.7, 3.9), (s * 1.3, 1.25, 3.6), (s * 1.3, 1.3, 3.1), (s * 1.35, 1.1, 2.6), 0.05)
    p.piston((s * 2.3, 0.55, 3.95), (s * 2.3, 0.75, 3.1), 0.06)
    return p


FOOT_SPLIT = [('u', 3), ('y', 2), ('y', 2), ('y', 2), ('y', 2), ('u', 3), ('y', 1), ('y', 1)]


def build_foot31(s):
    p = Part('foot_' + sn(s))
    c = 2.1

    def X(u0, u1):
        return xr(s, c + u0, c + u1)
    p.hullmesh(rb(*X(-1.3, 1.3), -2.45, 1.92, 0.0, 0.3) + rb(*X(-1.0, 1.0), -1.75, 1.45, 1.12, 0.3), 'metal')
    g = tv('foot_gap', 0.07)
    spl = tv('toe_splay', 1.05)

    def splay(ring, k):
        return [(s * c + (x - s * c) * k, -0.3 + (y + 0.3) * k, z) for x, y, z in ring]
    tg = tv('toe_gap', 0.09)
    rnd = random.Random(500 + s)
    for k, (bt, tp, zt) in enumerate(FOOT_SEGS):
        u0, u1, y0, y1 = bt
        v0, v1, w0, w1 = tp
        u0, u1, v0, v1 = u0 + g, u1 - g, v0 + g, v1 - g
        if y0 > -2.5:
            y0, w0 = y0 + g, w0 + g
        if y1 < 1.9:
            y1, w1 = y1 - g, w1 - g
        ax, nsp = tv('foot_split', FOOT_SPLIT)[k]
        for i in range(nsp):
            f0, f1 = i / nsp, (i + 1) / nsp
            h0 = tg / 2 if i > 0 else 0.0
            h1 = tg / 2 if i < nsp - 1 else 0.0
            if ax == 'u':
                a0, a1 = u0 + (u1 - u0) * f0 + h0, u0 + (u1 - u0) * f1 - h1
                b0, b1 = v0 + (v1 - v0) * f0 + h0, v0 + (v1 - v0) * f1 - h1
                bb = (a0, a1, y0, y1)
                tt = (b0, b1, w0, w1)
            else:
                a0, a1 = y0 + (y1 - y0) * f0 + h0, y0 + (y1 - y0) * f1 - h1
                b0, b1 = w0 + (w1 - w0) * f0 + h0, w0 + (w1 - w0) * f1 - h1
                bb = (u0, u1, a0, a1)
                tt = (v0, v1, b0, b1)
            ztp = zt * rnd.uniform(*tv('toe_zr', (0.93, 1.04)))
            zb = tv('toe_zb', -0.08)
            pts = (splay(rb(*X(bb[0], bb[1]), bb[2], bb[3], zb, 0.08), spl) +
                   splay(rb(*X(bb[0] - 0.025, bb[1] + 0.025), bb[2] - 0.025, bb[3] + 0.025, 0.17, 0.1), 1 + (spl - 1) * 0.8) +
                   rb(*X(tt[0], tt[1]), tt[2], tt[3], ztp, 0.08))
            axv = Vector((s, 0, 0)) if ax == 'u' else Vector((0, 1, 0))

            def skip(n, cc, i=i, nsp=nsp, axv=axv):
                if n.z < -0.5 or n.z > 0.9:
                    return True
                d = n.dot(axv)
                return (d < -0.75 and i > 0) or (d > 0.75 and i < nsp - 1)
            p.scale_hull(pts, t=0.1, seed=51 + 7 * k + 31 * i + s, skip=skip, big=lambda n, cc: True,
                         core='armor_dark', core_in=0.03, mech=0.0, rr=0.032,
                         big_subk=tuple(tv('toe_subk', (0.74, 0.82))))
    # ribbed band above the toes (dense, proud ribs + lips)
    bx0, bx1 = X(-0.85, 0.85)
    p.hullmesh(rb(bx0, bx1, -1.35, 1.25, 1.1, 0.3) + rb(bx0, bx1, -1.35, 1.25, 1.47, 0.3), tv('band_mat', 'metal'))
    p.hullmesh(rb(bx0 - 0.04, bx1 + 0.04, -1.39, 1.29, 1.45, 0.32) + rb(bx0 - 0.02, bx1 + 0.02, -1.37, 1.27, 1.53, 0.31),
               'armor_dark', 0.6)
    sd = [(-0.55, 1.28), (0.1, 1.28), (0.75, 1.28)]
    xo = bx1 if s > 0 else bx0
    step = tv('rib_step', 0.14)
    for y in [-1.22 + step * i for i in range(int(2.35 / step) + 1)]:
        for xx in (bx0, bx1):
            if xx == xo and any(abs(y - yy) < 0.21 for yy, _ in sd):
                continue
            p.box(T((xx, y, 1.29)), (tv('rib_d', 0.11), 0.065, 0.32), 'armor_dark', bev=0.012)
    for x in [bx0 + 0.2 + step * i for i in range(int((bx1 - bx0 - 0.3) / step) + 1)]:
        for yy in (-1.35, 1.25):
            p.box(T((x, yy, 1.29)), (0.065, tv('rib_d', 0.11), 0.32), 'armor_dark', bev=0.012)
    for yy, zz in sd:
        p.disc(PF((xo - s * 0.06, yy, zz), (s, 0, 0)), 0.17, th=0.05, hub=0.05, bolts=4)
    # ankle block + big disc
    apts = (rb(*xr(s, 1.15, 2.65), -0.88, 0.95, 1.4, 0.25) + rb(*xr(s, 1.12, 2.68), -0.95, 1.0, 1.75, 0.3) +
            rb(*xr(s, 1.2, 2.6), -0.8, 0.85, 2.05, 0.25))
    adisc = (s * tv('adisc_x', 2.6), 0.3, 1.74)
    p.scale_hull(apts, size=tv('sc_ankle', 0.55), t=0.08, seed=61 + s, avoid=[(adisc, 0.5)], rk=tuple(tv('sc_rk', (0.52, 0.66))),
                 skip=lambda n, cc: no_tb(n, cc) or s * n.x < -0.7, mech=tv('sc_mech', 0.7), core_in=0.07)
    p.cyl(P((s * 1.9, 0.3, 1.72), (0, 90, 0)), 0.36, 1.45, 'metal', n=24, bev=0.02)
    p.bigdisc(PF(adisc, (s, 0, 0)), tv('ankle_r', 0.45), th=0.1, hub=0.08)
    p.disc(PF((s * 1.12, 0.3, 1.72), (-s, 0, 0)), 0.3, th=0.04, hub=0.05, bolts=6)
    p.greebles(PF((s * c, -1.65, 1.2), (0, 0, 1)), 1.2, 0.5, 8, seed=70 + s)
    p.greebles(PF((s * c, 1.45, 1.1), (0, 0, 1)), 1.2, 0.45, 6, seed=80 + s)
    p.piston((s * 1.9, -0.9, 1.65), (s * 1.9, -1.75, 1.2), 0.08)
    p.piston((s * 1.5, 0.95, 1.7), (s * 1.5, 1.55, 1.2), 0.07)
    return p


POD31 = [  # z, y_front, x_in, x_out, chamfer  (front profile peaks at z~7, recedes above -> hunch)
    (6.3, -2.05, 1.05, 1.75, 0.3), (6.6, -2.3, 0.95, 2.0, 0.42), (6.9, -2.4, 0.92, 2.14, 0.48),
    (7.2, -2.38, 0.92, 2.14, 0.48), (7.55, -1.98, 0.93, 2.14, 0.46), (7.88, -1.72, 0.95, 2.06, 0.42),
    (8.1, -1.48, 1.0, 1.9, 0.36)]
COCK31 = [  # z, half width, y_front, y_back, chamfer
    (6.4, 0.5, -1.95, -0.6, 0.15), (6.8, 0.78, -2.36, -0.6, 0.3), (7.25, 0.85, -2.42, -0.55, 0.34),
    (7.62, 0.82, -2.0, -0.5, 0.34), (8.05, 0.7, -1.74, -0.4, 0.3), (8.33, 0.55, -1.42, 0.2, 0.22),
    (8.46, 0.42, -1.12, 0.2, 0.15)]


def build_torso31():
    p = Part('torso')
    pts = (rb(-1.25, 1.25, -1.4, 1.25, 6.15, 0.35) + rb(-1.75, 1.75, -1.7, 1.5, 6.45, 0.45) +
           rb(-2.05, 2.05, -1.75, 1.6, 6.95, 0.5) + rb(-2.05, 2.05, -1.72, 1.6, 7.35, 0.5) +
           rb(-1.95, 1.95, -1.5, 1.6, 7.9, 0.45) + rb(-1.3, 1.3, -1.25, 1.45, 8.2, 0.4))
    p.armor_hull(pts, t=0.1, maxs=0.95, seed=101, skip=lambda n, c: n.z < -0.55 or n.y < -0.5, sub_p=0.55)
    for s in (-1, 1):
        pp = []
        for z, yf, xi, xo, ch in POD31:
            pp += rb(*xr(s, xi, xo), yf, -0.4, z, ch)

        def red(n, c, s=s):
            if 6.85 < c.z < 7.9 and n.y < -0.1 and s * n.x > 0.3:
                return 'plate'
            if c.z > 7.35 and n.y < -0.55 and abs(c.x) > 1.5:
                return (60.0 if s < 0 else 120.0, 0.35, s * 0.25)
            return None
        p.armor_hull(pp, t=0.1, maxs=tv('pod_maxs', 0.8), seed=110 + s, red=red,
                     skip=lambda n, c: n.z < -0.75 or n.y > 0.5, sub_p=0.65, tilt=3.0, cut=0.2)
        m = PF((s * 1.18, -2.33, 7.15), nrm(0, -1, 0.15), (0, 0, 1))
        p.box(m @ T((0, 0, 0.03)), (0.3, 0.75, 0.1), 'armor_dark', bev=0.02)
        p.grille(m @ T((0, 0, 0.08)), 0.2, 0.62, n=6, depth=0.05)
    for sx in (-1, 1):
        m = PF((sx * 0.5, 1.72, 7.3), (0, 1, 0), (0, 0, 1))
        p.box(m @ T((0, 0, 0.05)), (0.72, 1.75, 0.2), 'armor_dark', bev=0.04)
        p.grille(m @ T((0, 0, 0.16)), 0.52, 1.5, n=11, depth=0.1)
        for yy in (-0.8, 0.8):
            for xx in (-0.3, 0.3):
                p.rivet(m @ T((xx, yy, 0.15)), 0.035)
    for sx in (-1, 1):
        m = PF((sx * 2.16, -1.0, 7.35), (sx, 0, 0), (0, 0, 1))
        p.box(m @ T((0, 0, 0.02)), (0.7, 0.62, 0.12), 'armor_dark', bev=0.03)
        p.grille(m @ T((0, 0, 0.09)), 0.55, 0.48, n=5, depth=0.06)
    for sx in (-1, 1):
        p.box(T((sx * 1.48, 0.1, 8.33)), (0.36, 0.55, 0.22), 'armor_dark', bev=0.03)
        p.grille(PF((sx * 1.48, 0.1, 8.445), (0, 0, 1), (0, 1, 0)), 0.26, 0.42, n=4, depth=0.05)
    p.greebles(PF((0, 1.2, 8.3), (0, 0, 1)), 2.4, 0.5, 14, seed=105)
    # waist: dark mechanics under the chest (deep shadowed band)
    p.ring(T((0, 0.0, 6.05)), 1.2, 0.95, 0.14, 'armor_dark', n=32)
    p.greebles(PF((0, -1.45, 6.2), nrm(0, -1, -0.5)), 1.9, 0.45, 16, seed=106)
    for sx in (-1, 1):
        p.cyl(P((sx * 0.75, -1.3, 6.2), (0, 90, 0)), 0.16, 0.5, 'metal', n=14)
        p.cable((sx * 1.7, 0.8, 6.6), (sx * 2.3, 1.0, 6.9), (sx * 2.4, 0.9, 7.2), (sx * 2.25, 0.7, 7.4), 0.06)
        p.pipe((sx * 1.2, 1.65, 6.4), (sx * 1.2, 1.65, 8.0), 0.06)
    return p


def build_cockpit31():
    p = Part('cockpit')
    pts = []
    for z, hw, yf, yb, ch in COCK31:
        pts += rb(-hw, hw, yf, yb, z, ch)
    vz = tv('visor_z', 7.86)
    # facet between the 7.62 and 8.05 rings
    (z1, _, y1, _, _), (z2, _, y2, _, _) = COCK31[3], COCK31[4]
    vy = y1 + (vz - z1) / (z2 - z1) * (y2 - y1)
    vn = nrm(0, -(z2 - z1), (y2 - y1))
    p.armor_hull(pts, t=0.09, maxs=0.62, seed=121, skip=lambda n, c: n.z < -0.8 or n.y > 0.6, sub_p=0.5,
                 tilt=2.0, cut=0.16, avoid=[((0, vy, vz), 0.32)])
    m = PF((0, vy - 0.02, vz), vn, (0, 0, 1))
    # recessed dark visor housing, single amber slit with a centre divider, brow plate above
    p.box(m @ T((0, 0, 0.02)), (tv('visor_w', 0.98), 0.3, 0.16), 'metal', bev=0.03)
    p.box(m @ T((0, 0, 0.06)), (tv('visor_w', 0.98) - 0.16, 0.17, 0.08), 'hole', bev=0.0)
    p.box(m @ T((0, -0.01, 0.115)), (tv('visor_w', 0.98) - 0.24, 0.07, 0.03), 'glow', bev=0.0)
    for xx in (-0.25, 0.0, 0.25):
        p.box(m @ T((xx, 0, 0.12)), (0.04 if xx else 0.06, 0.19, 0.05), 'armor_dark', bev=0.008)
    p.pplate(m @ T((0, 0.24, 0.1)) @ rot(-18, 0, 0), [(-0.7, -0.1), (0.7, -0.1), (0.62, 0.12), (-0.62, 0.12)], 0.08,
             0.025, 'armor', True, 0.16, 0.026, False, None)
    for sx in (-1, 1):
        p.pplate(m @ T((sx * 0.72, -0.02, 0.06)) @ rot(0, sx * 20, 0), [(-0.12, -0.2), (0.12, -0.2), (0.12, 0.2), (-0.12, 0.2)],
                 0.07, 0.02, 'armor_dark', True, 0.14, 0.024, False, None)
    # chin beak plate
    m2 = PF((0, -2.32, 6.6), nrm(0, -1, -0.8), (0, 0, 1))
    p.pplate(m2, [(-0.5, 0.25), (-0.5, -0.05), (0.0, -0.35), (0.5, -0.05), (0.5, 0.25)], 0.08, 0.025, 'armor_dark',
             True, 0.18, 0.028, False, random.Random(9))
    for sx in (-1, 1):
        cx = sx * 0.62
        p.box(T((cx, -0.15, 8.78)), (0.5, 0.42, 0.44), 'armor', bev=0.035)
        p.box(T((cx, -0.15, 8.57)), (0.36, 0.3, 0.1), 'metal', bev=0.0)
        p.cyl(P((cx - sx * 0.08, -0.37, 8.82), (90, 0, 0)), 0.085, 0.05, 'glass', n=12)
        p.ring(P((cx - sx * 0.08, -0.38, 8.82), (90, 0, 0)), 0.11, 0.08, 0.04, 'brass', n=12)
        p.box(T((cx + sx * 0.12, -0.37, 8.72)), (0.14, 0.03, 0.07), 'glow', bev=0.0)
        for zz in (8.62, 8.94):
            for xx in (-0.18, 0.18):
                p.rivet(PF((cx + xx, -0.365, zz), (0, -1, 0)), 0.026)
    return p


def build_fist31():
    p = Part('fist_L')
    p.push(T((tv('fist_x', -3.4), 0.6, 6.3)) @ rot(tv('fist_pitch', -18.0), 0, 0) @ rot(0, tv('fist_tilt', 14.0), 0))

    def redfn(kind):
        def f(n, c):
            if kind == 'outer' and n.x < -0.6:
                return 'plate' if c.z < -1.2 else (60.0, 0.6, 0.0)
            if kind == 'front' and n.y < -0.6 and c.x < -0.3:
                return (35.0, 0.55, 0.1)
            return None
        return f
    p.armor_hull(rb(-0.87, 0.57, -0.8, 0.95, -0.62, 0.2) + rb(-0.5, 0.57, -0.8, 0.95, 0.05, 0.2) +
                 rb(-0.87, -0.5, -0.8, 0.95, tv('fist_otop', -0.42), 0.15), t=0.09,
                 maxs=0.7, seed=192, skip=no_tb)
    # dark ribbed collar between forearm and fist
    p.drum(T((-0.15, 0.08, -0.74)), 0.72, 0.2, ribs=2)
    # tier 1: four blocks of different size
    t1 = [((-1.1, -0.2), (-0.95, 0.12), (-1.62, -0.84), 'grille'),
          ((-1.08, -0.2), (0.17, 1.15), (-1.55, -0.86), 'outer'),
          ((-0.15, 0.78), (-0.9, 0.35), (-1.5, -0.88), 'front'),
          ((-0.15, 0.72), (0.4, 1.1), (-1.45, -0.9), None)]
    # tier 2: three blocks along the depth
    t2 = [((-1.08, 0.74), (-0.92, -0.28), (-2.2, -1.68), 'outer'),
          ((-1.05, 0.7), (-0.23, 0.45), (-2.16, -1.6), 'outer'),
          ((-1.02, 0.68), (0.5, 1.1), (-2.12, -1.58), None)]
    for k, ((a, b), (c, d), (z0, z1), kind) in enumerate(t1 + t2):
        ai = 0.04 if a > -1.0 else tv('fist_tin', 0.14)
        pts = rb(a, b, c, d, z0, 0.16) + rb(a + ai, b - 0.04, c + 0.05, d - 0.05, z1, 0.18)
        p.armor_hull(pts, t=0.09, maxs=0.6, seed=200 + k, skip=lambda n, cc: n.z > 0.85 and kind is None,
                     red=redfn(kind) if kind in ('outer', 'front') else None, sub_p=0.5)
    # large grille on the front face of the upper outer block
    m = PF((-0.65, -1.07, -1.23), (0, -1, 0), (0, 0, 1))
    p.box(m @ T((0, 0, 0.03)), (0.78, 0.66, 0.1), 'armor_dark', bev=0.03)
    p.grille(m @ T((0, 0, 0.08)), 0.62, 0.52, n=6, depth=0.06)
    # knuckles: four smaller blocks
    kb = tv('knuckle_z', [-2.74, -2.74, -2.68, -2.52])
    for k, (c, d) in enumerate(((-0.88, -0.45), (-0.4, 0.05), (0.1, 0.56), (0.61, 1.05))):
        ko = tv('knuckle_out', 0.1)
        pts = rb(-0.9 - ko, 0.46, c, d, kb[k], 0.1) + rb(-0.96 - ko, 0.52, c, d, -2.24, 0.12)
        p.armor_hull(pts, t=0.07, maxs=0.8, seed=220 + k, skip=lambda n, cc: n.z > 0.85, rs=0.18, sub_p=0.0)
    for k, y in enumerate((-0.62, -0.17, 0.33, 0.83)):
        p.box(T((-0.2, y, kb[k] - 0.03)), (0.6, 0.14, 0.04), 'glow', bev=0.0)
    p.box(T((-0.2, -0.93, -2.2)), (1.1, 0.05, 0.05), 'glow', bev=0.0)
    p.cyl(T((0.3, 1.18, -0.58)), 0.07, 1.0, 'steel', n=10)
    p.piston((0.3, 1.15, -0.2), (0.3, 1.15, -1.3), 0.08)
    p.cable((0.5, 0.9, 0.05), (0.85, 1.1, -0.4), (0.85, 1.2, -0.9), (0.6, 1.05, -1.3), 0.05)
    p.cable((-0.6, 1.0, 0.0), (-0.95, 1.2, -0.4), (-1.0, 1.25, -0.9), (-0.8, 1.15, -1.3), 0.05)
    p.pop()
    return p


# ------------------------------------------------------------------ assemble
def build():
    L.HULL_DEF.update(TUNE.get('hull', {}))
    L.MAT_DEF.update(TUNE.get('mat', {}))
    for k_, v_ in TUNE.get('palette', {}).items():
        L.PALETTE[k_].update(v_)
    coll = get_coll()
    build_materials()
    root = bpy.data.objects.new('mech_root', None)
    root.empty_display_type = 'ARROWS'
    root.empty_display_size = 1.5
    coll.objects.link(root)
    root['pivot_world'] = [0.0, 0.0, 0.0]
    obs = {}
    obs['hip'] = finish(build_hip(), (0, 0, 5.45), coll, root)
    V = tv('v31', False)
    obs['torso'] = finish((build_torso31 if V else build_torso)(), (0, 0.1, 6.15), coll, obs['hip'])
    obs['cockpit'] = finish((build_cockpit31 if V else build_cockpit)(), (0, -0.5, 7.4), coll, obs['torso'])
    for s in (-1, 1):
        n = sn(s)
        obs['shoulder_' + n] = finish(build_shoulder(s), (s * 2.1, 0.7, 7.45), coll, obs['torso'])
        obs['launcher_' + n] = finish(build_launcher(s), (s * 3.1, 0.9, 7.05), coll, obs['shoulder_' + n])
        obs['arm_' + n] = finish(build_arm(s), (s * 3.3, 0.7, 7.0), coll, obs['shoulder_' + n])
        obs['thigh_' + n] = finish((build_thigh31 if V else build_thigh)(s), (s * 1.55, 0.0, 5.45), coll, obs['hip'])
        obs['shin_' + n] = finish((build_shin31 if V else build_shin)(s), (s * 1.7, -0.25, 3.85), coll,
                                  obs['thigh_' + n])
        obs['foot_' + n] = finish((build_foot31 if V else build_foot)(s), (s * 1.9, 0.3, 1.72), coll, obs['shin_' + n])
    obs['fist_L'] = finish((build_fist31 if V else build_fist)(), (-3.4, 0.6, 6.25), coll, obs['arm_L'])
    obs['cannon_R'] = finish(build_cannon(), (3.3, 0.6, 6.1), coll, obs['arm_R'])
    bpy.context.view_layer.update()
    meshes = [o for o in coll.objects if o.type == 'MESH']
    print('objects', len(coll.objects), 'tris', tri_count(meshes))
    for o in sorted(meshes, key=lambda o: o.name):
        print('  %-12s tris %7d' % (o.name, tri_count([o])))
    return obs


build()

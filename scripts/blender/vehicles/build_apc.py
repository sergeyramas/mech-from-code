# VEH_apc: generic 8x8 wheeled APC, ~7.5 m. Simple sloped boat hull (convex hulls), small conical turret with a
# heavy MG, side doors, roof hatches, vision blocks. Front = -Y, ground z=0, root at the footprint centre.
# Separate destructible parts: wheels (pivot on the axle), turret (pivot on the ring axis), MG (child of the turret,
# pivot on the trunnion), side doors + roof hatches (pivot on the hinge).
import math
import veh_lib as V
from veh_lib import Part, T, rot, PF, Vector

NAME = 'apc'
R, W = 0.56, 0.36
TR = 1.12
AXLES = (-2.45, -1.1, 0.65, 2.0)
AZ = R
HZK = 1.05
TUR = Vector((0, -0.95, 2.0))  # turret ring centre on the roof
SLOPE_N = Vector((0.9, 0, 0.435)).normalized()  # upper side plate normal (left side)


def sym(pts):
    return [(x, y, z) for x0, y, z in pts for x in (x0, -x0)]


def hull(p):
    lower = sym([(0.72, -2.9, 0.42), (0.72, 3.1, 0.42), (0.88, -3.5, 1.25), (0.88, 3.55, 1.25)])
    p.hullmesh(lower, mat='armor_dark', wear=0.3)
    upper = sym([(0.9, -3.74, 1.0), (0.9, -3.76, 1.1), (1.22, -3.3, 1.2), (1.22, -3.3, 1.4),
                 (1.36, -2.9, 1.2), (1.38, -2.85, 1.42), (1.36, 3.6, 1.2), (1.38, 3.6, 1.42),
                 (1.08, -2.35, 2.0), (1.1, 3.5, 2.0)])
    p.hullmesh(upper, mat='armor', wear=0.35)
    # roof trim, rub strip along the sponson edge, weld seams
    for s in (-1, 1):
        p.box(T((s * 1.385, 0.35, 1.31)), (0.04, 6.2, 0.06), mat='armor_dark', bev=0.01)
        for y in (-1.95, -0.6, 1.3, 2.7):
            p.box(T((s * 1.25, y, 1.71)) @ rot(0, s * 25.8, 0), (0.006, 0.01, 0.6), mat='hole', bev=0.0)
    # trim vane on the glacis + headlights + tow hooks
    gl = PF((0, -3.25, 1.42), Vector((0, -0.6, 0.8)).normalized(), (0, 0, 1))
    p.box(gl, (1.6, 0.5, 0.04), mat='armor', bev=0.01)
    for x in (-0.6, 0.0, 0.6):
        p.box(gl @ T((x, 0, 0.04)), (0.04, 0.5, 0.06), mat='armor', bev=0.008)
    for s in (-1, 1):
        V.headlight(p, PF((s * 0.72, -3.72, 1.2), (0, -1, 0.15), (0, 0, 1)), 0.09, guard=True)
        p.box(T((s * 0.45, -3.62, 0.86)), (0.12, 0.2, 0.1), mat='metal', bev=0.015)
        V.rod(p, (s * 0.45, -3.74, 0.82), (s * 0.45, -3.74, 0.92), 0.025, 'steel', 8)
    # driver vision blocks across the front roof edge
    for x in (-0.55, -0.3, 0.3, 0.55):
        m = PF((x, -2.36, 2.02), Vector((0, -1, 0.4)).normalized(), (0, 0, 1))
        p.box(m, (0.18, 0.1, 0.07), mat='armor_dark', bev=0.01)
        p.box(m @ T((0, 0, 0.036)), (0.14, 0.06, 0.006), mat='glass', bev=0.0)
    # hatch bases on the roof (lids are separate parts)
    for c in ((0.45, -2.0), (-0.45, -2.0), (0.6, 1.0), (-0.6, 1.0)):
        p.cyl(T((c[0], c[1], 2.02)), 0.3, 0.04, mat='armor_dark', n=16, bev=0.008)
    # engine deck grilles + exhaust boxes at the rear
    for s in (-1, 1):
        for y in (2.2, 2.95):
            p.box(T((s * 0.5, y, 2.012)), (0.6, 0.55, 0.024), mat='hole', bev=0.0)
            for k in range(6):
                p.box(T((s * 0.5, y - 0.23 + k * 0.092, 2.03)) @ rot(-30, 0, 0), (0.6, 0.05, 0.012),
                      mat='armor_dark', bev=0.0)
        p.box(T((s * 1.3, 3.0, 1.62)), (0.16, 0.6, 0.3), mat='armor_dark', bev=0.02)
        p.cyl(PF((s * 1.36, 3.0, 1.62), (s, 0, 0)), 0.07, 0.06, mat='rust', n=12)
        # rear lights
        p.box(T((s * 1.05, 3.61, 1.6)), (0.14, 0.04, 0.08), mat='armor_dark', bev=0.006)
        p.box(T((s * 1.05, 3.635, 1.6)), (0.1, 0.01, 0.05), mat='tail', bev=0.0)
    # tools / stowage on the sloped sides
    for s in (-1, 1):
        n = Vector((s * SLOPE_N.x, 0, SLOPE_N.z))
        p.box(PF((s * 1.27, 1.85, 1.68), n, (0, 0, 1)) @ T((0, 0, 0.06)), (0.9, 0.3, 0.12), mat='armor', bev=0.015)
        V.rod(p, (s * 1.33, -2.4, 1.55), (s * 1.33, -1.0, 1.55), 0.02, 'metal', 6)  # crowbar
        # firing ports
        for y in (-1.75, 1.15, 2.55):
            p.cyl(PF((s * 1.24, y, 1.74), n, (0, 0, 1)), 0.075, 0.05, mat='armor_dark', n=12, bev=0.01)
    # suspension stubs + wheel hubs behind the wheels
    for y in AXLES:
        for s in (-1, 1):
            V.rod(p, (s * 0.85, y, AZ + 0.12), (s * 0.95, y, AZ), 0.06, 'armor_dark', 8)
            V.rod(p, (s * 0.8, y - 0.25, 0.85), (s * 0.95, y, AZ + 0.1), 0.04, 'steel', 8)
    # markings
    for s in (-1, 1):
        n = Vector((s * SLOPE_N.x, 0, SLOPE_N.z))
        V.decal_text(p, '2-14', PF((s * 1.205, -1.85, 1.86), n, (0, 0, 1)) @ T((0, 0, 0.01)), 0.22)
        V.emblem(p, PF((s * 1.386, 2.55, 1.31), (s, 0, 0)), 0.11)
    V.decal_text(p, 'OB-2', PF((0.0, -3.6, 1.32), Vector((0, -0.6, 0.8)).normalized(), (0, 0, 1)) @ T((0, 0.0, 0.07)),
                 0.12)


def side_door(s, off):
    """door on the sloped upper side between axles 2 and 3; returns (Part, hinge pivot)"""
    n = Vector((s * SLOPE_N.x, 0, SLOPE_N.z))
    c = Vector((s * 1.245, -0.22, 1.7)) + off
    m = PF(c, n, (0, 0, 1))
    d = Part('%s_door_%s' % (NAME, 'L' if s > 0 else 'R'))
    d.pslab(m, V.round_rect(0.62, 0.6, 0.05, 2), 0.035, cham=0.012, mat='armor')
    d.box(m @ T((0.18 * s, 0.05, 0.05)), (0.14, 0.03, 0.03), mat='metal', bev=0.006)  # handle
    for z in (-0.18, 0.18):
        hm = m @ T((-0.33 * s, z, 0.03))
        d.cyl(hm @ rot(90, 0, 0), 0.025, 0.12, mat='armor_dark', n=8)
    d.box(m @ T((0, 0.12, 0.04)), (0.12, 0.08, 0.02), mat='glass', bev=0.0)
    pv = m @ Vector((-0.33 * s, 0, 0.03))
    return d, pv


def hatch(c, off, flip=1):
    m = T(Vector((c[0], c[1], 2.04)) + off)
    h = Part('%s_hatch_%s' % (NAME, c[2]))
    h.cyl(m @ T((0, 0, 0.025)), 0.26, 0.05, mat='armor', n=16, bev=0.012)
    h.box(m @ T((0, 0, 0.06)), (0.3, 0.05, 0.03), mat='armor_dark', bev=0.006)
    pv = Vector((c[0], c[1] + 0.27 * flip, 2.06)) + off
    h.cyl(T(pv) @ rot(0, 90, 0), 0.025, 0.2, mat='armor_dark', n=8)
    return h, pv


def turret(t):
    t.cyl(T((0, 0, 0.04)), 0.66, 0.08, mat='armor_dark', n=20, bev=0.01)
    t.cyl(T((0, 0, 0.29)), 0.6, 0.42, mat='armor', n=10, r2=0.46, bev=0.02)
    t.cyl(T((0, 0, 0.51)), 0.44, 0.04, mat='armor', n=10, bev=0.01)
    # mantlet housing + sight
    t.box(T((0, -0.5, 0.27)), (0.42, 0.24, 0.3), mat='armor', bev=0.03)
    t.box(T((0.32, -0.3, 0.6)), (0.12, 0.18, 0.16), mat='armor_dark', bev=0.015)
    t.box(T((0.32, -0.395, 0.61)), (0.08, 0.01, 0.08), mat='glass', bev=0.0)
    # smoke dischargers + antenna base
    for s in (-1, 1):
        for k in range(3):
            c = Vector((s * 0.5, 0.1 + k * 0.14, 0.35))
            t.cyl(PF(c, (s * 0.75, -0.3, 0.6), (0, 0, 1)), 0.045, 0.24, mat='armor_dark', n=10)
    t.cyl(T((-0.3, 0.32, 0.56)), 0.04, 0.08, mat='armor_dark', n=8)
    V.rod(t, (-0.3, 0.32, 0.6), (-0.3, 0.42, 1.9), 0.006, 'metal', 5)


def mg(g):
    """local frame: trunnion at origin, barrel along -Y"""
    g.box(T((0, 0.05, 0)), (0.16, 0.5, 0.16), mat='armor_dark', bev=0.015)
    g.cyl(T((0, -0.28, 0)) @ rot(90, 0, 0), 0.06, 0.2, mat='metal', n=12, bev=0.008)
    V.rod(g, (0, -0.3, 0), (0, -1.55, 0), 0.026, 'metal', 10)
    g.cyl(T((0, -1.55, 0)) @ rot(90, 0, 0), 0.04, 0.16, mat='metal', n=10)
    V.rod(g, (0.14, -0.2, -0.04), (0.14, -0.75, -0.04), 0.013, 'metal', 8)  # coax
    g.box(T((-0.13, 0.08, -0.02)), (0.1, 0.22, 0.16), mat='armor', bev=0.012)  # ammo box
    g.cyl(T((0, 0.02, 0)) @ rot(0, 90, 0), 0.04, 0.34, mat='armor_dark', n=10)  # trunnion pin


def build():
    coll, root = V.new_vehicle(NAME)
    off = Vector((0, -0.02, 0))
    p = Part(NAME + '_hull', T(off))
    hull(p)
    V.veh_finish(p, (0, 0, 0), coll, root, hz_k=HZK)
    for s in (1, -1):
        d, pv = side_door(s, off)
        V.veh_finish(d, pv, coll, root, hz_k=HZK)
    for c in ((0.45, -2.0, 'driver', -1), (-0.45, -2.0, 'commander', -1), (0.6, 1.0, 'troop_L', 1),
              (-0.6, 1.0, 'troop_R', 1)):
        h, pv = hatch(c[:3], off, c[3])
        V.veh_finish(h, pv, coll, root, hz_k=HZK)
    tp = TUR + off
    t = Part(NAME + '_turret', T(tp))
    turret(t)
    tob = V.veh_finish(t, tp, coll, root, hz_k=HZK)
    gp = tp + Vector((0, -0.62, 0.27))
    g = Part(NAME + '_mg', T(gp))
    mg(g)
    V.veh_finish(g, gp, coll, tob, hz_k=HZK)
    wl = {}
    for side, tag in ((1, 'L'), (-1, 'R')):
        for k, y in enumerate(AXLES):
            ctr = Vector((side * TR, y, AZ)) + off
            nm = '%s_wheel_%d%s' % (NAME, k + 1, tag)
            if tag in wl:
                V.instance(wl[tag], nm, ctr, coll, root)
                continue
            wp = Part(nm, T(ctr))
            V.wheel(wp, T((0, 0, 0)), R, W, side=side, style='mil', n=24, lugs=14, nuts=8, holes=6)
            wl[tag] = V.veh_finish(wp, ctr, coll, root, hz_fn=V.wheel_hz(R))
    return coll, root

# VEH_jeep: light 4x4 utility vehicle, boxy open tub, flat fenders, canvas soft top, rear spare wheel.
# ~4.1 m long. Front = -Y, ground z=0, root at the centre of the wheelbase. Vehicle left = +X.
import math
import veh_lib as V
from veh_lib import Part, T, rot, P, PF, frame, D2R, Vector

NAME = 'jeep'
R, W = 0.40, 0.25
TR = 0.75
YF, YR = -1.36, 1.06
AZ = 0.39
HZK = 0.72  # mud line height (m)
YC = -0.03  # root at the centre of the footprint (bumper -2.13 .. spare wheel 2.07)


def body(p):
    # ---------------- chassis
    for s in (-1, 1):
        p.box(T((s * 0.42, -0.1, 0.56)), (0.075, 3.66, 0.13), mat='armor_dark', bev=0.012)
        # leaf springs + shackles
        for y in (YF, YR):
            p.box(T((s * 0.42, y, AZ + 0.075)), (0.065, 0.86, 0.04), mat='metal', bev=0.008)
            p.box(T((s * 0.42, y, AZ + 0.05)), (0.07, 0.5, 0.025), mat='metal', bev=0.006)
            V.rod(p, (s * 0.52, y + 0.12, AZ), (s * 0.5, y + 0.2, 0.6), 0.026, 'steel', 8)  # shock absorber
    for y in (-1.88, -0.62, 0.55, 1.68):
        p.box(T((0, y, 0.56)), (0.86, 0.07, 0.1), mat='armor_dark', bev=0.01)
    for y in (YF, YR):
        V.rod(p, (-0.66, y, AZ), (0.66, y, AZ), 0.045, 'armor_dark', 12)
        p.cyl(T((0.1, y, AZ)) @ rot(90, 0, 0), 0.125, 0.16, mat='armor_dark', n=16, bev=0.02)
        p.cyl(T((0.1, y + (0.12 if y < 0 else -0.12), AZ)) @ rot(90, 0, 0), 0.05, 0.12, mat='metal', n=10)
    V.rod(p, (0.1, YF + 0.12, AZ), (0.1, YR - 0.12, AZ + 0.06), 0.03, 'metal', 8)  # prop shaft
    V.rod(p, (-0.62, YF - 0.16, AZ + 0.02), (0.62, YF - 0.16, AZ + 0.02), 0.016, 'metal', 6)  # tie rod
    # exhaust along the right side
    V.rod(p, (-0.3, -0.9, 0.44), (-0.3, 1.5, 0.44), 0.03, 'rust', 8)
    V.rod(p, (-0.3, 1.5, 0.44), (-0.42, 1.82, 0.47), 0.03, 'rust', 8)
    p.cyl(T((-0.3, 0.6, 0.44)) @ rot(90, 0, 0), 0.075, 0.45, mat='metal', n=12, bev=0.01)  # muffler
    # ---------------- tub
    zb, zt = 0.55, 1.12
    arch = V.arc(YR, AZ + 0.02, 0.5, 162.5, 17.5, 9)
    side = ([(-0.62, zb)] + [(a, max(b, zb)) for a, b in arch] + [(1.75, zb), (1.75, zt), (0.3, zt)] +
            V.arc(0.18, 0.92, 0.12, 0, -90, 3) + V.arc(-0.42, 0.92, 0.12, -90, -180, 3) + [(-0.54, zt), (-0.62, zt)])
    for s in (-1, 1):
        p.pslab(V.yz_frame(s * 0.78, s), V.yz_poly(side, s), 0.04, cham=0.012, mat='armor', bottom=True)
        # arch flare
        o = V.arc(YR, AZ + 0.02, 0.56, 165, 15, 10)
        i_ = V.arc(YR, AZ + 0.02, 0.5, 15, 165, 10)
        for k in range(10):
            quad = [o[k], o[k + 1], i_[9 - k], i_[10 - k]]
            p.pslab(V.yz_frame(s * 0.815, s), V.yz_poly(quad[::-1] if s > 0 else quad[::-1], s), 0.03, cham=0.0,
                    mat='armor', bottom=False, side_wear=0.9)
        # top rail capping the tub sides + door-opening edge
        p.box(T((s * 0.8, 1.02, zt + 0.012)), (0.07, 1.46, 0.025), mat='armor', bev=0.008)
        # grab handle + rear-quarter tie-down rings
        V.rod(p, (s * 0.835, 1.35, 1.0), (s * 0.835, 1.55, 1.0), 0.012, 'metal', 6)
        for y in (1.35, 1.55):
            V.rod(p, (s * 0.82, y, 1.0), (s * 0.84, y, 1.0), 0.012, 'metal', 6)
        # step under the door opening
        p.box(T((s * 0.86, -0.12, 0.6)), (0.12, 0.42, 0.025), mat='armor_dark', bev=0.006)
        V.rod(p, (s * 0.82, -0.3, 0.6), (s * 0.82, -0.3, 0.68), 0.012, 'metal', 6)
        # tail lights
        p.box(T((s * 0.66, 1.77, 0.78)), (0.12, 0.05, 0.1), mat='armor_dark', bev=0.01)
        p.box(T((s * 0.66, 1.798, 0.795)), (0.08, 0.008, 0.035), mat='tail', bev=0.0)
        p.box(T((s * 0.66, 1.798, 0.755)), (0.08, 0.008, 0.025), mat='amber', bev=0.0)
        # rear bumperettes
        p.box(T((s * 0.66, 1.82, 0.55)), (0.22, 0.14, 0.12), mat='armor_dark', bev=0.015)
    p.box(T((0, -0.06, 0.65)), (1.6, 1.12, 0.05), mat='armor', bev=0.01)  # floor
    p.box(T((0, 1.12, 0.65)), (1.0, 1.24, 0.05), mat='armor', bev=0.01)
    p.box(T((0, 1.73, 0.835)), (1.64, 0.045, 0.57), mat='armor', bev=0.012)  # rear panel
    for x in (-0.25, 0.25):  # pressed ribs on the rear panel
        p.box(T((x, 1.755, 0.84)), (0.04, 0.02, 0.4), mat='armor', bev=0.008)
    # inner wheel wells
    for s in (-1, 1):
        p.box(T((s * 0.65, YR, 0.885)), (0.27, 1.0, 0.05), mat='armor', bev=0.015)
        p.box(T((s * 0.515, YR, 0.76)), (0.03, 1.0, 0.25), mat='armor', bev=0.008)
    # pintle hook
    p.box(T((0, 1.8, 0.56)), (0.18, 0.12, 0.1), mat='armor_dark', bev=0.01)
    p.ring(T((0, 1.9, 0.56)) @ rot(0, 90, 0), 0.06, 0.035, 0.035, mat='metal', n=12)
    # ---------------- firewall / dash / seats / steering
    p.box(T((0, -0.6, 0.86)), (1.64, 0.06, 0.56), mat='armor', bev=0.012)
    p.box(T((0, -0.5, 1.02)), (1.5, 0.14, 0.16), mat='armor_dark', bev=0.02)
    for x in (0.25, 0.38, 0.5):
        p.cyl(T((x, -0.425, 1.03)) @ rot(-90, 0, 0), 0.035, 0.01, mat='glass', n=12)
        p.ring(T((x, -0.425, 1.03)) @ rot(-90, 0, 0), 0.042, 0.035, 0.014, mat='metal', n=12)
    for x in (0.38, -0.38):
        p.box(T((x, 0.05, 0.83)), (0.48, 0.5, 0.12), mat='seat', bev=0.03)
        p.box(T((x, 0.3, 1.08)) @ rot(-12, 0, 0), (0.46, 0.1, 0.46), mat='seat', bev=0.03)
        p.box(T((x, 0.05, 0.72)), (0.36, 0.4, 0.1), mat='metal', bev=0.01)
    p.box(T((0, 1.25, 0.8)), (0.9, 0.45, 0.1), mat='seat', bev=0.03)  # rear bench
    p.box(T((0, 1.52, 1.02)) @ rot(-8, 0, 0), (0.9, 0.08, 0.38), mat='seat', bev=0.03)
    # driver on the left (+X)
    V.rod(p, (0.38, -0.47, 0.98), (0.38, -0.2, 1.2), 0.025, 'metal', 8)
    col = Vector((0, 0.27, 0.22)).normalized()
    p.ring(T((0.38, -0.19, 1.21)) @ V.seg_rot(col), 0.19, 0.165, 0.025, mat='rubber', n=20)
    for a in (0, 120, 240):
        p.box(T((0.38, -0.19, 1.21)) @ V.seg_rot(col) @ rot(0, 0, a) @ T((0.09, 0, 0)), (0.17, 0.02, 0.012),
              mat='metal', bev=0.0)
    V.rod(p, (0.1, -0.3, 0.6), (0.06, -0.15, 0.95), 0.012, 'metal', 6)  # gear lever
    p.cyl(T((0.06, -0.15, 0.97)), 0.025, 0.04, mat='rubber', n=8)


def front(p):
    # hood
    p.box(T((0, -1.255, 0.86)), (1.16, 1.27, 0.36), mat='armor', bev=0.025)
    p.box(T((0, -1.255, 1.045)), (0.5, 1.18, 0.012), mat='armor', bev=0.004)  # raised centre panel
    for s in (-1, 1):
        p.box(T((s * 0.583, -1.62, 1.02)), (0.02, 0.06, 0.06), mat='metal', bev=0.005)  # hood latch
        V.rod(p, (s * 0.25, -0.64, 1.05), (s * 0.4, -0.64, 1.05), 0.012, 'metal', 6)  # hinge
    # grille panel with slotted vent
    p.box(T((0, -1.9, 0.8)), (1.24, 0.05, 0.5), mat='armor', bev=0.015)
    gm = PF((0, -1.93, 0.77), (0, -1, 0), (0, 0, 1))
    p.grille(gm, 0.6, 0.26, n=6, depth=0.06, mat='armor_dark')
    for s in (-1, 1):
        V.headlight(p, PF((s * 0.47, -1.945, 0.84), (0, -1, 0), (0, 0, 1)), 0.085)
        p.box(T((s * 0.47, -1.94, 0.66)), (0.08, 0.03, 0.05), mat='armor_dark', bev=0.006)
        p.box(T((s * 0.47, -1.957, 0.66)), (0.06, 0.006, 0.03), mat='amber', bev=0.0)
    # flat front fenders + aprons
    for s in (-1, 1):
        top = [(0.58, -1.86), (0.95, -1.86), (0.95, -0.66), (0.58, -0.62)]
        if s < 0:
            top = [(-x, y) for x, y in reversed(top)]
        p.pslab(T((0, 0, 0.97)), top, 0.03, cham=0.01, mat='armor', bottom=True)
        p.box(T((s * 0.78, -1.875, 0.8)), (0.34, 0.03, 0.34), mat='armor', bev=0.01)
        p.box(T((s * 0.94, -1.26, 0.93)), (0.02, 1.2, 0.1), mat='armor', bev=0.006)  # rolled fender lip
        # blackout marker light on fender top
        p.box(T((s * 0.82, -1.78, 1.03)), (0.09, 0.06, 0.06), mat='armor_dark', bev=0.01)
        p.box(T((s * 0.82, -1.812, 1.03)), (0.06, 0.004, 0.03), mat='amber', bev=0.0)
        # inner splash apron: fender inner edge down to the frame rail (closes the wheel well)
        ap = [(-1.84, 0.97), (-0.66, 0.97), (-0.66, 0.6), (-1.84, 0.6)]
        p.pslab(V.yz_frame(s * 0.585, s), V.yz_poly(ap, s), 0.02, cham=0.0, mat='armor', bottom=True)
        # fender to tub link plate
        p.box(T((s * 0.78, -0.63, 0.86)), (0.4, 0.03, 0.26), mat='armor', bev=0.008)
    # front bumper, tow shackles, hazard ends
    p.box(T((0, -2.0, 0.57)), (1.92, 0.13, 0.15), mat='armor_dark', bev=0.02)
    for s in (-1, 1):
        p.box(T((s * 0.86, -2.068, 0.57)), (0.2, 0.006, 0.12), mat='red', bev=0.0)
        p.box(T((s * 0.86, -2.07, 0.57)) @ rot(0, 40, 0), (0.035, 0.007, 0.17), mat='decal', bev=0.0)
        p.ring(T((s * 0.42, -2.1, 0.57)) @ rot(0, 90, 0), 0.055, 0.032, 0.03, mat='metal', n=10)
        for x in (s * 0.36, s * 0.48):
            p.bolt(PF((x, -2.067, 0.57), (0, -1, 0)), 0.014, 0.012, 'steel')
    # windshield (tilted 10 deg back), frame, glass, wipers, mirrors
    t = D2R(10)
    wm = T((0, -0.6, 1.12)) @ frame((0, -math.cos(t), math.sin(t)), (0, math.sin(t), math.cos(t)))
    outer = V.outline(1.62, 0.5, (0.03, 0.03))
    outer = [(x, y + 0.25) for x, y in outer]
    inner = V.inset(outer, 0.05)
    p.pframe(wm, outer, inner, 0.04, mat='armor', cham=0.012)
    p.box(wm @ T((0, 0.25, 0.02)), (0.05, 0.42, 0.04), mat='armor', bev=0.008)
    for s in (-1, 1):
        p.box(wm @ T((s * 0.385, 0.25, 0.012)), (0.7, 0.4, 0.006), mat='glass', bev=0.0)
        p.box(wm @ T((s * 0.3, 0.42, 0.05)) @ rot(0, 0, s * 15), (0.015, 0.34, 0.012), mat='rubber', bev=0.0)
        p.cyl(wm @ T((s * 0.3, 0.47, 0.03)) @ rot(90, 0, 0), 0.018, 0.04, mat='metal', n=8)
        p.box(wm @ T((s * 0.82, 0.05, -0.02)), (0.05, 0.08, 0.06), mat='metal', bev=0.008)  # hinges
        V.mirror(p, (s * 0.81, -0.56, 1.42), (s * 1.0, -0.6, 1.5), size=(0.13, 0.18, 0.025), facing=(0, 1, 0))


def top(p):
    # bows
    sec = ([(-0.81, 1.12), (-0.815, 1.6)] + V.arc(-0.66, 1.66, 0.15, 180, 90, 4)[1:] +
           V.arc(0.66, 1.66, 0.15, 90, 0, 4) + [(0.815, 1.6), (0.81, 1.12)])

    def zscale(y):
        # front edge comes down onto the windshield header
        k0 = (1.6 - 1.12) / (1.81 - 1.12)
        t = min(1.0, max(0.0, (y + 0.5) / 0.3))
        return k0 + (1 - k0) * (t * t * (3 - 2 * t))

    def skip(x, y, z):
        return y < 0.3 and z < 1.5

    def matf(x, y, z, kind):
        if kind == 'side' and 0.5 < y < 1.42 and 1.34 < z < 1.66 and abs(x) > 0.7:
            return 'plastic'
        if kind == 'end' and y > 1.0 and abs(x) < 0.48 and 1.34 < z < 1.68:
            return 'plastic'
        return 'canvas'

    V.canvas_cover(p, sec, -0.5, 1.76, nu=30, nv=26, bows=(-0.15, 0.55, 1.2), sag=0.035, fold=0.012, seed=7,
                   zscale=zscale, skip=skip, matf=matf, ends=(False, True), end_bulge=-0.02, sub=1, disp=0.008,
                   solid=0.012)
    for y in (-0.15, 0.55):
        for s in (-1, 1):  # exposed bow legs in the door openings
            V.rod(p, (s * 0.79, y, 1.12), (s * 0.79, y, 1.58), 0.018, 'armor_dark', 8)
    # front strap to the windshield header
    for s in (-1, 1):
        p.box(T((s * 0.55, -0.52, 1.64)), (0.05, 0.08, 0.03), mat='rubber', bev=0.004)


def rear(p):
    # spare carrier + jerry can
    p.box(T((0.42, 1.77, 0.93)), (0.3, 0.05, 0.3), mat='armor_dark', bev=0.01)
    p.box(T((-0.45, 1.77, 0.95)), (0.42, 0.05, 0.08), mat='armor_dark', bev=0.01)
    p.box(T((-0.45, 1.77, 0.68)), (0.42, 0.05, 0.06), mat='armor_dark', bev=0.01)
    jc = T((-0.45, 1.885, 0.9))
    p.box(jc, (0.34, 0.16, 0.46), mat='armor', bev=0.025)
    for s in (-1, 1):
        p.box(jc @ T((0, 0.083, 0)) @ rot(0, s * 35, 0), (0.04, 0.012, 0.5), mat='armor', bev=0.004)
        p.box(jc @ T((s * 0.08, 0, 0.245)), (0.03, 0.03, 0.04), mat='armor', bev=0.005)
    p.box(jc @ T((0, 0, 0.27)), (0.2, 0.03, 0.02), mat='armor', bev=0.004)
    p.cyl(jc @ T((0.12, 0, 0.25)) @ rot(0, 30, 0), 0.025, 0.06, mat='armor_dark', n=8)
    V.rod(p, (-0.45 - 0.2, 1.97, 0.9), (-0.45 + 0.2, 1.97, 0.9), 0.008, 'metal', 6)  # retaining strap
    # whip antenna on the right rear corner
    p.cyl(T((-0.72, 1.6, 1.2)), 0.035, 0.12, mat='armor_dark', n=10, bev=0.008)
    p.cyl(T((-0.72, 1.6, 1.27)), 0.022, 0.06, mat='rubber', n=8)
    # whip bent forward and tied down to the windshield corner (common field practice, keeps the silhouette low)
    P0, P1, P2 = Vector((-0.72, 1.6, 1.3)), Vector((-0.76, 1.25, 2.5)), Vector((-0.87, -0.55, 1.62))
    pts = [(1 - t) ** 2 * P0 + 2 * (1 - t) * t * P1 + t * t * P2 for t in [k / 14 for k in range(15)]]
    for a_, b_ in zip(pts, pts[1:]):
        V.rod(p, a_, b_, 0.006, 'metal', 5)
    p.box(T((-0.85, -0.56, 1.62)), (0.05, 0.04, 0.05), mat='rubber', bev=0.006)  # tie-down


def markings(p):
    for s in (-1, 1):
        V.decal_text(p, 'OB-14', PF((s * 0.823, 0.0, 0.68), (s, 0, 0), (0, 0, 1)), 0.17)
    V.emblem(p, PF((0, -1.3, 1.052), (0, 0, 1), (0, 1, 0)), 0.2)
    V.decal_text(p, '2/7', PF((0.45, -2.066, 0.57), (0, -1, 0), (0, 0, 1)), 0.11)
    V.decal_text(p, 'OB-14', PF((-0.45, -2.066, 0.57), (0, -1, 0), (0, 0, 1)), 0.11)


def build():
    coll, root = V.new_vehicle(NAME)
    off = Vector((0, -YC, 0))
    p = Part(NAME + '_body', T(off))
    body(p)
    front(p)
    rear(p)
    markings(p)
    lim = (Vector((-0.61, -1.95, 0.66)) + off, Vector((0.61, -0.6, 1.1)) + off)
    hood = V.split_part(p, NAME + '_hood', V.in_box(*lim))
    V.veh_finish(p, (0, 0, 0), coll, root, hz_k=HZK)
    V.veh_finish(hood, Vector((0, -0.64, 1.05)) + off, coll, root, hz_k=HZK)
    c = Part(NAME + '_canvas_top', T(off))
    top(c)
    V.veh_finish(c, (0, 0, 0), coll, root, hz_k=HZK)
    # wheels: one mesh per side, shared front/rear
    wl = {}
    for side, tag in ((1, 'L'), (-1, 'R')):
        for y, fr in ((YF, 'F'), (YR, 'R')):
            ctr = Vector((side * TR, y, AZ)) + off
            nm = '%s_wheel_%s%s' % (NAME, fr, tag)
            if tag in wl:
                V.instance(wl[tag], nm, ctr, coll, root)
                continue
            wp = Part(nm, T(ctr))
            V.wheel(wp, T((0, 0, 0)), R, W, side=side, style='jeep', n=28, lugs=16, lug_h=0.022, nuts=5,
                    beadlock=False, holes=4, rim_r=0.21)
            wl[tag] = V.veh_finish(wp, ctr, coll, root, hz_fn=V.wheel_hz(R))
    sc = Vector((0.42, 1.795 + W / 2 + 0.01, 0.93)) + off
    sp = Part(NAME + '_spare_wheel', T(sc) @ rot(0, 0, 90))
    V.wheel(sp, T((0, 0, 0)), R, W, side=1, style='jeep', n=28, lugs=16, lug_h=0.022, nuts=5, beadlock=False,
            holes=4, rim_r=0.21)
    V.veh_finish(sp, sc, coll, root, hz_fn=lambda v: 1.0 + 0.4 * (1 - min(1, math.hypot(v.x, v.z) / R)))
    return coll, root

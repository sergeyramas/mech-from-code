# VEH_truck: generic long-nose 6x6 army cargo truck, ~8.1 m. Narrow bonneted engine, flat-faceted front fenders,
# 2-door cab with roof hatch, drop-side bed with a canvas tilt over five bows, upright spare wheel behind the cab.
# Front = -Y, ground z=0, root at the centre of the footprint. Vehicle left (driver) = +X.
import math
import veh_lib as V
from veh_lib import Part, T, rot, PF, frame, D2R, Vector

NAME = 'truck'
R, W = 0.56, 0.42
TR = 1.0
AXLES = (('F', -2.6), ('M', 1.3), ('R', 2.72))
AZ = R
HZK = 1.0
YC = 0.03


def side_slab(p, x, s, poly, t, mat='armor', cham=0.01, bottom=True, wear=0.45):
    """side-view (y,z) CCW polygon at x*s, extruded outward by t"""
    p.pslab(V.yz_frame(s * x, s), V.yz_poly(poly, s), t, cham=cham, mat=mat, bottom=bottom, side_wear=wear)


def band(path, t):
    """thin sheet polygon (CCW in y,z) along a front->back polyline, thickness t upward"""
    up = []
    n = len(path)
    for i in range(n):
        a = Vector(path[max(0, i - 1)])
        b = Vector(path[min(n - 1, i + 1)])
        d = (b - a).normalized()
        nn = Vector((-d.y, d.x))
        up.append((path[i][0] + nn.x * t, path[i][1] + nn.y * t))
    return list(path) + list(reversed(up))


def vent(p, m, w, h, n=6, fw=0.04, mat='armor_dark', vertical=False, depth=0.03):
    """flush louvered vent on local XY facing +Z: black backing, angled slats, raised frame"""
    p.box(m @ T((0, 0, 0.002)), (w, h, 0.004), mat='hole', bev=0.0)
    for i in range(n):
        if vertical:
            x = -w / 2 + w * (i + 0.5) / n
            p.box(m @ T((x, 0, 0.012)) @ rot(0, 30, 0), (w / n * 0.55, h, 0.012), mat=mat, bev=0.0)
        else:
            y = -h / 2 + h * (i + 0.5) / n
            p.box(m @ T((0, y, 0.012)) @ rot(-30, 0, 0), (w, h / n * 0.55, 0.012), mat=mat, bev=0.0)
    o = V.outline(w + 2 * fw, h + 2 * fw, (fw * 0.6, fw * 0.6))
    i_ = V.outline(w, h, (fw * 0.3, fw * 0.3))
    if len(o) == len(i_):
        p.pframe(m, o, i_, depth, mat=mat, cham=0.008)


def chassis(p):
    for s in (-1, 1):
        p.box(T((s * 0.5, 0.0, 0.98)), (0.1, 7.9, 0.22), mat='armor_dark', bev=0.012)
    for y in (-3.7, -1.5, 0.0, 2.0, 3.86):
        p.box(T((0, y, 0.98)), (0.92, 0.1, 0.16), mat='armor_dark', bev=0.01)
    # axles + diffs
    for tag, y in AXLES:
        V.rod(p, (-0.84, y, AZ), (0.84, y, AZ), 0.065, 'armor_dark', 12)
        dx = 0.12 if tag == 'F' else -0.12
        p.cyl(T((dx, y, AZ)) @ rot(90, 0, 0), 0.19, 0.3, mat='armor_dark', n=18, bev=0.03)
        p.cyl(T((dx, y + (-0.2 if tag != 'R' else -0.2), AZ)) @ rot(90, 0, 0), 0.08, 0.14, mat='metal', n=10)
        for k in range(8):
            a = 2 * math.pi * k / 8
            p.bolt(T((dx + 0.15 * math.cos(a), y + 0.152, AZ + 0.15 * math.sin(a))) @ rot(-90, 0, 0), 0.014, 0.012,
                   'steel')
    # front leaf springs + shocks
    yf = AXLES[0][1]
    for s in (-1, 1):
        for k, (ln, z) in enumerate(((1.3, 0.8), (1.1, 0.76), (0.85, 0.72), (0.55, 0.68))):
            p.box(T((s * 0.5, yf, z)), (0.085, ln, 0.035), mat='metal', bev=0.006)
        for dy in (-0.62, 0.62):
            p.box(T((s * 0.5, yf + dy, 0.86)), (0.1, 0.08, 0.14), mat='armor_dark', bev=0.01)
        V.rod(p, (s * 0.66, yf + 0.18, AZ + 0.05), (s * 0.6, yf + 0.3, 0.95), 0.035, 'steel', 8)
        p.box(T((s * 0.5, yf, AZ + 0.1)), (0.14, 0.2, 0.1), mat='armor_dark', bev=0.01)  # spring seat
    # rear tandem: walking-beam spring packs on a trunnion + torque rods
    yt = (AXLES[1][1] + AXLES[2][1]) / 2
    for s in (-1, 1):
        for k, (ln, z) in enumerate(((1.62, 0.7), (1.4, 0.75), (1.1, 0.8), (0.75, 0.85))):
            p.box(T((s * 0.62, yt, z)), (0.1, ln, 0.045), mat='metal', bev=0.006)
        p.box(T((s * 0.58, yt, 0.92)), (0.22, 0.42, 0.22), mat='armor_dark', bev=0.02)  # trunnion bracket
        p.cyl(T((s * 0.72, yt, 0.85)) @ rot(0, 90, 0), 0.1, 0.1, mat='metal', n=14, bev=0.01)
        for _, y in AXLES[1:]:
            V.rod(p, (s * 0.35, yt, 0.95), (s * 0.35, y, AZ + 0.16), 0.03, 'armor_dark', 8)
            p.box(T((s * 0.62, y, AZ + 0.11)), (0.16, 0.22, 0.1), mat='armor_dark', bev=0.01)
    # engine sump, gearbox, transfer case, prop shafts
    p.box(T((0, -2.35, 0.98)), (0.55, 1.0, 0.28), mat='armor_dark', bev=0.03)
    p.box(T((0, -1.15, 1.0)), (0.42, 0.7, 0.3), mat='armor_dark', bev=0.03)
    p.box(T((0, -0.35, 0.82)), (0.46, 0.42, 0.32), mat='armor_dark', bev=0.03)
    V.rod(p, (0.0, -0.55, 0.78), (0.12, AXLES[0][1] + 0.25, AZ + 0.02), 0.035, 'metal', 8)
    V.rod(p, (0.0, -0.15, 0.78), (-0.12, AXLES[1][1] - 0.25, AZ + 0.02), 0.035, 'metal', 8)
    V.rod(p, (-0.12, AXLES[1][1] + 0.2, AZ + 0.02), (-0.12, AXLES[2][1] - 0.25, AZ + 0.02), 0.035, 'metal', 8)
    # fuel tank (left) with straps + cap
    ft = T((0.86, -0.05, 0.82)) @ rot(90, 0, 0)
    p.cyl(ft, 0.27, 1.0, mat='armor', n=20, bev=0.03)
    for dz in (-0.3, 0.3):
        p.ring(ft @ T((0, 0, dz)), 0.285, 0.265, 0.05, mat='armor_dark', n=20)
    p.cyl(T((0.95, 0.3, 1.1)), 0.05, 0.04, mat='metal', n=10, bev=0.006)
    for y in (-0.35, 0.25):
        p.box(T((0.62, y, 0.9)), (0.18, 0.08, 0.06), mat='armor_dark', bev=0.006)
    # battery box + air tank (right)
    p.box(T((-0.86, -0.05, 0.86)), (0.5, 0.8, 0.42), mat='armor', bev=0.025)
    for y in (-0.3, 0.0, 0.3):
        p.box(T((-1.115, -0.05 + y, 0.86)), (0.014, 0.04, 0.34), mat='armor', bev=0.004)
    for z in (0.98, 0.74):
        p.box(T((-1.12, -0.05, z)), (0.02, 0.12, 0.03), mat='metal', bev=0.004)
    V.rod(p, (-0.75, -0.62, 0.62), (-0.75, 0.5, 0.62), 0.11, 'armor_dark', 14)
    # door steps
    for s in (-1, 1):
        for z in (0.72, 1.0):
            p.box(T((s * 1.0, -0.8, z)), (0.3, 0.44, 0.03), mat='armor_dark', bev=0.006)
            for k in range(4):
                p.box(T((s * 1.0, -0.95 + k * 0.1, z + 0.017)), (0.26, 0.012, 0.006), mat='metal', bev=0.0)
        for y in (-1.02, -0.58):
            p.box(T((s * 1.0, y, 0.88)), (0.26, 0.03, 0.36), mat='armor_dark', bev=0.006)


def front(p):
    # ---- bonnet
    p.box(T((0, -2.57, 1.56)), (1.2, 2.3, 0.88), mat='armor', bev=0.045)
    V.rod(p, (0, -3.68, 2.004), (0, -1.46, 2.004), 0.016, 'armor', 8)  # centre hinge
    for s in (-1, 1):
        p.box(T((s * 0.601, -2.57, 1.88)), (0.006, 2.2, 0.008), mat='hole', bev=0.0)  # top/side seam
        for y in (-3.3, -1.82):
            p.box(T((s * 0.612, y, 1.9)), (0.03, 0.07, 0.09), mat='metal', bev=0.006)  # bonnet clamps
            V.rod(p, (s * 0.63, y, 1.86), (s * 0.63, y, 1.94), 0.008, 'steel', 6)
        for k in range(7):  # side louvers
            y = -2.3 + k * 0.09
            p.box(T((s * 0.6, y, 1.73)), (0.006, 0.03, 0.18), mat='hole', bev=0.0)
            p.box(T((s * 0.607, y - 0.012, 1.73)) @ rot(0, 0, -s * 25), (0.014, 0.04, 0.2), mat='armor', bev=0.003)
    # radiator grille + brush guard
    vent(p, PF((0, -3.72, 1.5), (0, -1, 0), (0, 0, 1)), 0.9, 0.58, n=9, fw=0.05, vertical=True)
    for k in range(7):
        x = -0.48 + k * 0.16
        V.rod(p, (x, -3.84, 1.12), (x, -3.84, 1.9), 0.018, 'armor_dark', 8)
    V.rod(p, (-0.6, -3.84, 1.9), (0.6, -3.84, 1.9), 0.024, 'armor_dark', 8)
    for s in (-1, 1):
        V.rod(p, (s * 0.6, -3.84, 1.9), (s * 0.6, -3.72, 1.96), 0.024, 'armor_dark', 8)
        V.rod(p, (s * 0.6, -3.84, 1.9), (s * 0.6, -3.84, 1.14), 0.024, 'armor_dark', 8)
    # ---- flat-faceted front fenders
    path = [(-3.66, 1.12), (-3.48, 1.5), (-3.3, 1.56), (-1.95, 1.56), (-1.68, 1.4), (-1.45, 1.3)]
    for s in (-1, 1):
        side_slab(p, 0.6, s, band(path, 0.035), 0.66, cham=0.012)
        # headlight on the fender front + guard, blackout marker, side marker
        hl = PF((s * 0.92, -3.36, 1.73), (0, -1, 0), (0, 0, 1))
        V.headlight(p, hl, 0.105, depth=0.14)
        p.box(T((s * 0.92, -3.28, 1.62)), (0.1, 0.14, 0.08), mat='armor_dark', bev=0.01)
        p.box(T((s * 1.16, -3.3, 1.63)), (0.08, 0.1, 0.07), mat='armor_dark', bev=0.01)
        p.box(T((s * 1.16, -3.352, 1.635)), (0.06, 0.004, 0.035), mat='amber', bev=0.0)
        p.box(T((s * 1.262, -2.0, 1.52)), (0.006, 0.05, 0.03), mat='amber', bev=0.0)
        # fender edge bolts
        for k in range(6):
            y = -3.25 + k * 0.25
            p.bolt(PF((s * 1.262, y, 1.575), (s, 0, 0)), 0.011, 0.008, 'steel')
    # air cleaner on the right fender, toolbox on the left
    p.cyl(T((-0.92, -2.25, 1.86)), 0.17, 0.56, mat='armor', n=20, bev=0.02)
    p.cyl(T((-0.92, -2.25, 2.16)), 0.13, 0.05, mat='armor_dark', n=16, bev=0.01)
    for z in (1.66, 2.02):
        p.ring(T((-0.92, -2.25, z)), 0.18, 0.165, 0.035, mat='metal', n=20)
    V.rod(p, (-0.76, -2.25, 1.95), (-0.6, -2.25, 1.95), 0.06, 'rubber', 10)
    p.box(T((0.92, -2.3, 1.72)), (0.5, 0.62, 0.3), mat='armor', bev=0.02)
    p.box(T((0.92, -2.3, 1.876)), (0.5, 0.62, 0.012), mat='armor_dark', bev=0.004)
    for y in (-2.48, -2.12):
        p.box(T((1.175, y, 1.8)), (0.02, 0.05, 0.08), mat='metal', bev=0.005)
    # ---- bumper with recessed winch
    for s in (-1, 1):
        p.box(T((s * 0.835, -3.98, 1.0)), (0.77, 0.2, 0.3), mat='armor_dark', bev=0.03)
        p.box(T((s * 1.06, -4.082, 1.0)), (0.3, 0.006, 0.24), mat='red', bev=0.0)
        for dx in (-0.08, 0.06):
            p.box(T((s * (1.06 + dx), -4.086, 1.0)) @ rot(0, s * 40, 0), (0.05, 0.006, 0.3), mat='decal', bev=0.0)
        for x in (0.52, 0.72):
            for z in (0.9, 1.1):
                p.bolt(PF((s * x, -4.08, z), (0, -1, 0)), 0.016, 0.014, 'steel')
        p.box(T((s * 0.62, -4.1, 0.86)), (0.08, 0.1, 0.06), mat='metal', bev=0.01)
        p.ring(T((s * 0.62, -4.15, 0.86)) @ rot(0, 90, 0), 0.075, 0.045, 0.04, mat='metal', n=12)
    for z in (0.865, 1.135):
        p.box(T((0, -3.95, z)), (0.92, 0.22, 0.03), mat='armor_dark', bev=0.006)
    wm = T((0, -3.94, 1.0)) @ rot(0, 90, 0)
    p.cyl(wm, 0.1, 0.8, mat='steel', n=16)
    for k in range(9):
        p.ring(wm @ T((0, 0, -0.34 + k * 0.085)), 0.106, 0.09, 0.04, mat='steel', n=16, wear_top=0.0)
    for dz in (-0.41, 0.41):
        p.cyl(wm @ T((0, 0, dz)), 0.125, 0.02, mat='armor_dark', n=16, bev=0.004)
    p.pframe(PF((0, -4.07, 1.0), (0, -1, 0), (0, 0, 1)), V.outline(0.26, 0.16, (0.03, 0.03)),
             V.outline(0.16, 0.06, (0.012, 0.012)), 0.05, mat='metal', cham=0.01)
    V.rod(p, (0, -4.05, 1.0), (0.1, -3.97, 1.06), 0.012, 'steel', 6)  # cable to drum
    p.ring(PF((0, -4.12, 1.0), (1, 0, 0)), 0.04, 0.025, 0.02, mat='metal', n=10)


def cab(p):
    y0, y1, zb, zw, zr = -1.42, 0.14, 1.14, 1.98, 2.64
    for s in (-1, 1):
        side_slab(p, 1.05, s, [(y0 + 0.02, zb), (-0.25, zb), (-0.25, zw), (y0 + 0.02, zw)], 0.05, cham=0.015)  # door
        side_slab(p, 1.05, s, [(-0.25, zb), (y1, zb), (y1, zw), (-0.25, zw)], 0.05, cham=0.015)
        # window frames (door + rear quarter) and glass
        for outer in ([(y0 + 0.02, zw), (-0.22, zw), (-0.22, zr), (y0 + 0.18, zr)],
                      [(-0.22, zw), (y1, zw), (y1, zr), (-0.22, zr)]):
            inner = V.inset(outer, 0.06)
            p.pframe(V.yz_frame(s * 1.05, s), V.yz_poly(outer, s), V.yz_poly(inner, s), 0.05, mat='armor',
                     cham=0.012)
            side_slab(p, 1.068, s, inner, 0.006, mat='glass', cham=0.0, bottom=True, wear=0.0)
        # door seams, hinges, handle, grab rail
        for y in (y0 + 0.07, -0.25):
            p.box(T((s * 1.101, y, (zb + zr) / 2)), (0.006, 0.008, zr - zb - 0.08), mat='hole', bev=0.0)
        p.box(T((s * 1.101, (y0 + 0.07 - 0.25) / 2, zb + 0.045)), (0.006, 1.1, 0.008), mat='hole', bev=0.0)
        for z in (1.4, 1.85):
            p.box(T((s * 1.11, y0 + 0.1, z)), (0.03, 0.08, 0.12), mat='armor_dark', bev=0.006)
            p.cyl(T((s * 1.12, y0 + 0.07, z)), 0.015, 0.14, mat='metal', n=8)
        p.box(T((s * 1.115, -0.42, 1.86)), (0.025, 0.16, 0.03), mat='metal', bev=0.005)
        p.box(T((s * 1.108, -0.42, 1.86)), (0.012, 0.06, 0.06), mat='armor_dark', bev=0.004)
        V.rod(p, (s * 1.13, y0 + 0.06, 1.75), (s * 1.13, y0 + 0.13, 2.4), 0.014, 'metal', 6)
        # mirror on tubular arms
        tip = Vector((s * 1.42, -1.46, 2.22))
        V.mirror(p, (s * 1.1, -1.36, 2.3), tip, size=(0.2, 0.34, 0.04), facing=(0, 1, 0))
        V.rod(p, (s * 1.1, -1.36, 1.98), tip - Vector((0, 0, 0.17)), 0.012, 'metal', 6)
        # rain gutter
        p.box(T((s * 1.115, (y0 + 0.16 + y1) / 2, zr - 0.01)), (0.025, y1 - y0 - 0.16, 0.03), mat='armor', bev=0.005)
    # front wall / cowl
    p.box(T((0, y0 + 0.03, (zb + zw) / 2)), (2.2, 0.06, zw - zb), mat='armor', bev=0.015)
    p.box(T((0, y0 - 0.02, zw - 0.06)), (1.6, 0.06, 0.03), mat='armor_dark', bev=0.006)  # cowl vent strip
    # windshield, tilted back
    t = math.atan2(0.16, zr - zw)
    wm = T((0, y0 + 0.02, zw)) @ frame((0, -math.cos(t), math.sin(t)), (0, math.sin(t), math.cos(t)))
    hgt = math.hypot(0.16, zr - zw)
    outer = [(x, y + hgt / 2) for x, y in V.outline(2.2, hgt, (0.03, 0.03))]
    inner = V.inset(outer, 0.06)
    p.pframe(wm, outer, inner, 0.05, mat='armor', cham=0.014)
    p.box(wm @ T((0, hgt / 2, 0.025)), (0.06, hgt - 0.1, 0.05), mat='armor', bev=0.01)
    for s in (-1, 1):
        p.box(wm @ T((s * 0.525, hgt / 2, 0.02)), (0.98, hgt - 0.12, 0.006), mat='glass', bev=0.0)
        p.box(wm @ T((s * 0.5, 0.2, 0.06)) @ rot(0, 0, s * 20), (0.016, 0.42, 0.014), mat='rubber', bev=0.0)
        p.cyl(wm @ T((s * 0.43, 0.08, 0.04)) @ rot(90, 0, 0), 0.02, 0.05, mat='metal', n=8)
    # roof + hatch ring
    roof = [(-1.1, y0 + 0.16), (1.1, y0 + 0.16), (1.1, y1), (-1.1, y1)]
    p.pslab(T((0, 0, zr)), roof, 0.08, cham=0.04, mat='armor', bottom=True)
    hm = T((-0.5, -0.5, zr + 0.08))
    p.ring(hm @ T((0, 0, 0.03)), 0.36, 0.3, 0.06, mat='armor', n=24)
    p.cyl(hm @ T((0, 0, 0.055)), 0.31, 0.04, mat='armor', n=24, bev=0.012)
    p.box(hm @ T((0.33, 0, 0.06)), (0.08, 0.16, 0.05), mat='armor_dark', bev=0.008)
    p.box(hm @ T((-0.2, 0, 0.09)), (0.12, 0.03, 0.03), mat='metal', bev=0.005)
    # rear wall with window
    p.box(T((0, y1 - 0.03, (zb + zr) / 2)), (2.2, 0.06, zr - zb), mat='armor', bev=0.015)
    rw = PF((0, y1, 2.28), (0, 1, 0), (0, 0, 1))
    p.box(rw @ T((0, 0, 0.002)), (0.8, 0.3, 0.004), mat='hole', bev=0.0)
    p.box(rw @ T((0, 0, 0.006)), (0.8, 0.3, 0.004), mat='glass', bev=0.0)
    p.pframe(rw, V.outline(0.9, 0.4, (0.04, 0.04)), V.outline(0.8, 0.3, (0.02, 0.02)), 0.02, mat='rubber',
             cham=0.006)
    # floor, dash, seats, steering
    p.box(T((0, -0.64, 1.25)), (2.1, 1.5, 0.06), mat='armor_dark', bev=0.01)
    p.box(T((0, y0 + 0.2, 1.82)), (2.0, 0.26, 0.24), mat='armor_dark', bev=0.03)
    for x in (0.3, 0.45, 0.6, 0.75):
        p.cyl(T((x, y0 + 0.33, 1.86)) @ rot(-90, 0, 0), 0.035, 0.012, mat='glass', n=12)
    for x in (0.55, -0.5):
        p.box(T((x, -0.35, 1.6)), (0.6, 0.55, 0.14), mat='seat', bev=0.04)
        p.box(T((x, -0.04, 1.95)) @ rot(-10, 0, 0), (0.58, 0.12, 0.6), mat='seat', bev=0.04)
        p.box(T((x, -0.35, 1.45)), (0.4, 0.4, 0.2), mat='armor_dark', bev=0.01)
    col = Vector((0, 0.42, 0.42)).normalized()
    V.rod(p, (0.55, y0 + 0.3, 1.7), (0.55, -0.98, 2.02), 0.03, 'metal', 8)
    p.ring(T((0.55, -0.97, 2.03)) @ V.seg_rot(col), 0.23, 0.2, 0.03, mat='rubber', n=24)
    for a in (0, 120, 240):
        p.box(T((0.55, -0.97, 2.03)) @ V.seg_rot(col) @ rot(0, 0, a) @ T((0.11, 0, 0)), (0.2, 0.025, 0.014),
              mat='metal', bev=0.0)


def bed(p):
    y0, y1, zf, zs = 0.62, 3.97, 1.35, 1.95
    yc, ln = (y0 + y1) / 2, y1 - y0
    p.box(T((0, yc, zf - 0.04)), (2.5, ln, 0.08), mat='armor', bev=0.012)
    for k in range(9):
        p.box(T((0, y0 + 0.15 + k * (ln - 0.3) / 8, zf - 0.13)), (2.4, 0.08, 0.1), mat='armor_dark', bev=0.008)
    for s in (-1, 1):
        p.box(T((s * 0.5, yc, 1.17)), (0.14, ln, 0.1), mat='armor_dark', bev=0.01)
        side_slab(p, 1.2, s, [(y0, zf), (y1, zf), (y1, zs), (y0, zs)], 0.05, cham=0.012)
        p.box(T((s * 1.262, yc, 1.62)), (0.03, ln - 0.06, 0.05), mat='armor', bev=0.008)
        p.box(T((s * 1.262, yc, zf + 0.025)), (0.035, ln, 0.05), mat='armor', bev=0.008)
        for k, y in enumerate((0.9, 1.62, 2.34, 3.06, 3.78)):
            p.box(T((s * 1.275, y, 1.64)), (0.04, 0.08, 0.6), mat='armor', bev=0.01)
            p.box(T((s * 1.28, y, zf - 0.03)), (0.07, 0.12, 0.12), mat='armor_dark', bev=0.01)
            for z in (zf - 0.06, zf + 0.0):
                p.bolt(PF((s * 1.315, y, z), (s, 0, 0)), 0.012, 0.01, 'steel')
            for z in (1.5, 1.74):
                p.rivet(PF((s * 1.296, y, z), (s, 0, 0)), 0.014, 'armor')
            # rope hooks + lashing straps from the canvas hem
            for dy in (-0.33, 0.33):
                yy = y + dy
                if y0 + 0.1 < yy < y1 - 0.1:
                    p.box(T((s * 1.275, yy, 1.48)), (0.04, 0.04, 0.03), mat='metal', bev=0.006)
                    p.box(T((s * 1.298, yy, 1.66)) @ rot(0, 0, 0), (0.008, 0.035, 0.34), mat='rubber', bev=0.0)
        # flat fender plates over the tandem + mud flaps
        p.box(T((s * 1.0, (AXLES[1][1] + AXLES[2][1]) / 2, 1.2)), (0.5, 2.7, 0.02), mat='armor_dark', bev=0.005)
        p.box(T((s * 1.0, AXLES[2][1] + 0.68, 0.74)), (0.48, 0.015, 0.62), mat='rubber', bev=0.004)
        p.box(T((s * 1.0, AXLES[2][1] + 0.68, 1.1)), (0.5, 0.05, 0.05), mat='armor_dark', bev=0.006)
        p.box(T((s * 1.0, AXLES[0][1] + 0.64, 1.17)), (0.36, 0.012, 0.66), mat='rubber', bev=0.004)
    # headboard
    p.box(T((0, y0 + 0.03, 1.73)), (2.5, 0.06, 0.76), mat='armor', bev=0.012)
    # tailgate with ribs, hinges, chains, number
    p.box(T((0, y1 + 0.025, (zf + zs) / 2)), (2.46, 0.05, zs - zf), mat='armor', bev=0.012)
    for z in (1.5, 1.8):
        p.box(T((0, y1 + 0.055, z)), (2.36, 0.02, 0.05), mat='armor', bev=0.006)
    for x in (-0.8, 0.8):
        p.cyl(T((x, y1 + 0.04, zf)) @ rot(0, 90, 0), 0.03, 0.22, mat='metal', n=10)
    for s in (-1, 1):
        p.box(T((s * 1.2, y1 + 0.06, 1.88)), (0.06, 0.04, 0.08), mat='metal', bev=0.006)
        for k in range(5):
            p.ring(T((s * 1.255, y1 + 0.05 - k * 0.0, 1.88 - k * 0.07)) @ rot(0, 90 * (k % 2), 0), 0.024, 0.014,
                   0.01, mat='steel', n=8, wear_top=0.0)
    # rear bumper, tail lights + guards, pintle, hazard panels
    p.box(T((0, y1 + 0.08, 0.98)), (2.2, 0.12, 0.2), mat='armor_dark', bev=0.02)
    for s in (-1, 1):
        lm = T((s * 0.82, y1 + 0.145, 1.0))
        p.box(lm, (0.24, 0.05, 0.12), mat='armor_dark', bev=0.01)
        p.box(lm @ T((-s * 0.05, 0.027, 0.02)), (0.09, 0.006, 0.05), mat='tail', bev=0.0)
        p.box(lm @ T((s * 0.06, 0.027, 0.02)), (0.07, 0.006, 0.05), mat='amber', bev=0.0)
        p.box(lm @ T((0, 0.027, -0.035)), (0.18, 0.006, 0.02), mat='tail', bev=0.0)
        V.rod(p, (s * 0.69, y1 + 0.12, 1.08), (s * 0.69, y1 + 0.21, 1.08), 0.01, 'metal', 6)
        V.rod(p, (s * 0.95, y1 + 0.12, 1.08), (s * 0.95, y1 + 0.21, 1.08), 0.01, 'metal', 6)
        V.rod(p, (s * 0.69, y1 + 0.21, 1.08), (s * 0.95, y1 + 0.21, 1.08), 0.01, 'metal', 6)
        p.box(T((s * 1.0, y1 + 0.142, 0.98)), (0.18, 0.006, 0.16), mat='red', bev=0.0)
        p.box(T((s * 1.0, y1 + 0.146, 0.98)) @ rot(0, s * 40, 0), (0.04, 0.006, 0.2), mat='decal', bev=0.0)
    p.box(T((0, y1 + 0.17, 0.92)), (0.16, 0.08, 0.12), mat='armor_dark', bev=0.01)
    p.ring(T((0, y1 + 0.25, 0.92)) @ rot(0, 90, 0), 0.07, 0.04, 0.04, mat='metal', n=12)


def canvas(p):
    sec = ([(-1.29, 1.8), (-1.3, 2.7)] + V.arc(-1.0, 2.7, 0.3, 180, 90, 4)[1:] + [(0.0, 3.06)] +
           V.arc(1.0, 2.7, 0.3, 90, 0, 4) + [(1.29, 1.8)])
    V.canvas_cover(p, sec, 0.6, 3.99, nu=30, nv=32, bows=(1.42, 2.25, 3.1), sag=0.055, fold=0.016, seed=3,
                   ends=(True, True), end_bulge=0.03, sub=1, disp=0.014, solid=0.0)
    # rolled rear flap bundle + tie straps
    V.rod(p, (-1.2, 4.03, 2.9), (1.2, 4.03, 2.9), 0.07, 'canvas', 12)
    for x in (-0.8, 0.0, 0.8):
        p.ring(T((x, 4.03, 2.9)) @ rot(0, 90, 0), 0.078, 0.07, 0.04, mat='rubber', n=12)


def rear_cab(p):
    # upright spare wheel carrier + fuel can behind the cab
    p.box(T((0.0, 0.38, 1.2)), (1.5, 0.36, 0.05), mat='armor_dark', bev=0.008)
    for x in (-0.5, 0.2):
        p.box(T((x, 0.62 - 0.03, 1.75)), (0.06, 0.04, 1.0), mat='armor_dark', bev=0.008)
    jc = T((0.62, 0.38, 1.47))
    p.box(jc, (0.17, 0.34, 0.48), mat='red', bev=0.022)
    for sgn in (-1, 1):
        p.box(jc @ T((0.086, 0, 0)) @ rot(sgn * 35, 0, 0), (0.012, 0.04, 0.5), mat='red', bev=0.004)
    p.box(jc @ T((0, 0, 0.26)), (0.03, 0.2, 0.02), mat='armor_dark', bev=0.004)
    p.cyl(jc @ T((0, 0.12, 0.25)) @ rot(-30, 0, 0), 0.025, 0.06, mat='armor_dark', n=8)
    V.rod(p, (0.52, 0.21, 1.6), (0.72, 0.21, 1.6), 0.008, 'metal', 6)
    V.rod(p, (0.6, -0.62, 1.12), (0.95, 0.32, 1.22), 0.045, 'rust', 8)
    p.cyl(T((0.95, 0.36, 1.6)), 0.12, 0.76, mat='rust', n=16, bev=0.02)
    V.rod(p, (0.95, 0.36, 1.95), (0.95, 0.36, 2.98), 0.05, 'rust', 10)
    p.cyl(T((0.95, 0.42, 2.45)), 0.085, 0.62, mat='armor_dark', n=14, r2=0.085)
    p.cyl(T((0.95, 0.36, 3.0)) @ rot(-35, 0, 0), 0.065, 0.012, mat='rust', n=12)
    for z in (1.4, 2.6):
        p.box(T((0.95, 0.24, z)), (0.06, 0.2, 0.05), mat='armor_dark', bev=0.006)


def markings(p):
    for s in (-1, 1):
        V.decal_text(p, 'OB-31', PF((s * 1.101, -0.86, 1.6), (s, 0, 0), (0, 0, 1)), 0.2)
        V.emblem(p, PF((s * 0.6, -3.05, 1.72), (s, 0, 0), (0, 0, 1)), 0.13)
        V.decal_text(p, '12', PF((s * 1.25, 2.5, 1.5), (s, 0, 0), (0, 0, 1)), 0.12)
    V.emblem(p, PF((0, -2.75, 2.0), (0, 0, 1), (0, 1, 0)), 0.3)
    V.decal_text(p, '2/7', PF((0.72, -4.08, 1.0), (0, -1, 0), (0, 0, 1)), 0.1)
    V.decal_text(p, 'OB-31', PF((-0.72, -4.08, 1.0), (0, -1, 0), (0, 0, 1)), 0.1)
    V.decal_text(p, 'OB-31', PF((0, 4.02, 1.65), (0, 1, 0), (0, 0, 1)), 0.22)


def build():
    coll, root = V.new_vehicle(NAME)
    off = Vector((0, -YC, 0))
    p = Part(NAME + '_body', T(off))
    chassis(p)
    front(p)
    cab(p)
    bed(p)
    rear_cab(p)
    markings(p)
    # destructible sub-parts (whole primitives moved out of the body by region)
    def ctr_in(a, b):
        a, b = Vector(a) + off, Vector(b) + off
        return lambda lo, hi: all(a[i] <= (lo[i] + hi[i]) / 2 <= b[i] for i in range(3))
    parts = []
    hood = V.split_part(p, NAME + '_hood', lambda lo, hi: lo.x > -0.65 and hi.x < 0.65 and
                        ctr_in((-0.62, -3.7, 1.1), (0.62, -1.45, 2.1))(lo, hi))
    parts.append((hood, Vector((0, -2.57, 1.56)) + off))
    for s, tag in ((1, 'L'), (-1, 'R')):
        lo_, hi_ = ((1.0, -1.42, 1.1), (1.5, -0.22, 2.7)) if s > 0 else ((-1.5, -1.42, 1.1), (-1.0, -0.22, 2.7))
        d = V.split_part(p, NAME + '_door_' + tag, ctr_in(lo_, hi_))
        parts.append((d, Vector((s * 1.1, -1.35, 1.9)) + off))
    V.veh_finish(p, (0, 0, 0), coll, root, hz_k=HZK)
    for pt, pv in parts:
        V.veh_finish(pt, pv, coll, root, hz_k=HZK)
    c = Part(NAME + '_canvas', T(off))
    canvas(c)
    V.veh_finish(c, (0, 0, 0), coll, root, hz_k=HZK)
    wl = {}
    for side, tag in ((1, 'L'), (-1, 'R')):
        for fr, y in AXLES:
            ctr = Vector((side * TR, y, AZ)) + off
            nm = '%s_wheel_%s%s' % (NAME, fr, tag)
            if tag in wl:
                V.instance(wl[tag], nm, ctr, coll, root)
                continue
            wp = Part(nm, T(ctr))
            V.wheel(wp, T((0, 0, 0)), R, W, side=side, style='mil', n=28, lugs=16, nuts=8, holes=6)
            wl[tag] = V.veh_finish(wp, ctr, coll, root, hz_fn=V.wheel_hz(R))
    sc = Vector((-0.15, 0.38, 1.225 + R)) + off
    sp = Part(NAME + '_spare_wheel', T(sc) @ rot(0, 0, -90))
    V.wheel(sp, T((0, 0, 0)), R, W, side=1, style='mil', n=28, lugs=16, nuts=8, holes=6)
    V.veh_finish(sp, sc, coll, root, hz_fn=lambda v: 1.0 + 0.4 * (1 - min(1, math.hypot(v.x, v.z) / R)))
    return coll, root

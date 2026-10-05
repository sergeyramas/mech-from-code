# Environment kit - prop prototypes (ENV_assets/AST_*, SET_*), checkpoint booth, barrier, fence, power line,
# street lamps, hand placed collection instances, vehicle slots + placeholders, top-view labels.
import bpy, math, random
from mathutils import Vector, Matrix, Euler
from env_common import (MB, fbm, smoothstep, lerp, get_coll, coll_instance, instance_points, rot, TR, D2R, join)
import env_ground as G

# ---------------------------------------------------------------- layout (world, metres)
BOOTH = (-10.0, -8.6)                 # 2.4 x 2.4 m checkpoint booth, west of the gate
BOOM_PIVOT = (-8.0, -9.55)
MG_NEST = (9.5, -4.0)
SLOTS = {   # name: (x, y, rz_deg, (L, W, H), kind)   vehicle forward = -Y of the empty
    'truck': (18.5, -6.2, -90.0, (8.0, 2.5, 3.0), 'truck'),
    'jeep': (-8.4, -3.2, 25.0, (4.0, 1.85, 1.9), 'jeep'),
    'apc': (20.0, 12.2, -70.0, (7.5, 2.9, 2.4), 'apc'),
    'wreck': (-27.5, -21.0, -68.0, (4.5, 1.8, 1.4), 'sedan'),
}
POLE_X = [-75.0, -47.0, -19.0, 9.0, 37.0, 65.0]
POLE_OFF = -11.0                      # metres from road centreline (south side)
LAMPS = [(-22.0, 5.8, 0.0), (12.5, 5.8, 0.0), (34.0, 5.8, 9.0)]   # x, offset north of centreline, lean deg
FENCE_N_Y = 16.5
FENCE_W_X = -40.0


def AST(C, name):
    return get_coll('AST_' + name, C['ENV_assets'])


def SET(C, name):
    return get_coll('SET_' + name, C['ENV_assets'])


# ---------------------------------------------------------------- prototypes
def extrude_x(mb, prof, x0, x1, m=0):
    """extrude a CCW (y,z) profile along +X"""
    k = len(prof)
    vs = [(x0, y, z) for y, z in prof] + [(x1, y, z) for y, z in prof]
    fs = [(i, (i + 1) % k, k + (i + 1) % k, k + i) for i in range(k)]
    fs += [tuple(reversed(range(k))), tuple(range(k, 2 * k))]
    mb.add(vs, fs, m)


def proto_jersey(C, M):
    prof = [(-0.305, 0.0), (0.305, 0.0), (0.305, 0.075), (0.2, 0.33), (0.075, 0.81), (-0.075, 0.81), (-0.2, 0.33),
            (-0.305, 0.075)]
    out = []
    for nm, mat in (('jersey_plain', 'ENV_concrete_prop'), ('jersey_striped', 'ENV_jersey_paint')):
        mb = MB()
        # chamfered ends: three segments, end segments slightly narrower
        xs = [-1.5, -1.47, 1.47, 1.5]
        for i in range(3):
            extrude_x(mb, prof if i == 1 else [(y * 0.97, z * 0.985) for y, z in prof], xs[i], xs[i + 1])
        out.append(mb.obj(nm, AST(C, nm), [M[mat]], smooth=35))
    return out


def superellipsoid(a, b, c, n1=0.35, n2=0.25, nu=16, nv=10):
    def sgnpow(v, e):
        return math.copysign(abs(v) ** e, v)
    vs = []
    for j in range(nv + 1):
        phi = -math.pi / 2 + math.pi * j / nv
        for i in range(nu):
            th = -math.pi + 2 * math.pi * i / nu
            cp, sp = math.cos(phi), math.sin(phi)
            x = a * sgnpow(cp, n1) * sgnpow(math.cos(th), n2)
            y = b * sgnpow(cp, n1) * sgnpow(math.sin(th), n2)
            z = c * sgnpow(sp, n1)
            vs.append([x, y, z])
    fs = []
    for j in range(nv):
        for i in range(nu):
            a0 = j * nu + i
            b0 = j * nu + (i + 1) % nu
            fs.append((a0, b0, b0 + nu, a0 + nu))
    return vs, fs


def proto_sandbags(C, M):
    sc = SET(C, 'sandbags')
    obs = []
    for k, (nm, sag) in enumerate((('bag_a', 0.02), ('bag_b', 0.035), ('bag_c', 0.01))):
        vs, fs = superellipsoid(0.3, 0.17, 0.075, 0.45, 0.3, 14, 8)
        rr = random.Random(k + 5)
        for v in vs:
            # pillow sag + lumps + tied end
            v[2] += -sag * (1 - (v[0] / 0.3) ** 2) * (1 if v[2] > 0 else -0.4)
            v[2] += 0.006 * math.sin(v[0] * 23 + k) * math.cos(v[1] * 17)
            if v[0] > 0.24:
                f = (v[0] - 0.24) / 0.06
                v[1] *= 1.0 - 0.45 * f
                v[2] *= 1.0 - 0.4 * f
            v[2] += 0.075
        mb = MB()
        mb.add([tuple(v) for v in vs], fs, 0)
        obs.append(mb.obj(nm, sc, [M['ENV_sandbag']], smooth=80))
    return sc


def proto_hedgehog(C, M):
    mb = MB()
    L = 1.9
    up = Vector((1, 1, 1)).normalized()
    R = up.rotation_difference(Vector((0, 0, 1))).to_matrix()
    for ax in (Vector((1, 0, 0)), Vector((0, 1, 0)), Vector((0, 0, 1))):
        d = R @ ax
        # L-angle: two flanges
        o_ = R @ (Vector((1, 1, 1)) - ax).normalized()
        side = d.cross(o_).normalized()
        a, b = -d * L / 2, d * L / 2
        mb.box_pts(a + side * 0.05, b + side * 0.05, 0.012, 0.11, 0, up=tuple(o_))
        mb.box_pts(a + o_ * 0.05, b + o_ * 0.05, 0.11, 0.012, 0, up=tuple(o_))
    # gusset plate at the centre
    mb.box((0.22, 0.22, 0.02), Matrix.Rotation(0.3, 4, 'Z'), 0, (0, 0, 0))
    zmin = min(v[2] for v in mb.V)
    mb.V = [(x, y, z - zmin - 0.02) for x, y, z in mb.V]
    return mb.obj('hedgehog', AST(C, 'hedgehog'), [M['ENV_rust']], smooth=30)


def lathe(prof, n=24, m=0, mb=None, mat=None):
    """revolve (r,z) profile around Z"""
    mb = mb or MB()
    k = len(prof)
    vs = []
    for i in range(n):
        a = 2 * math.pi * i / n
        for r, z in prof:
            vs.append((r * math.cos(a), r * math.sin(a), z))
    fs = []
    for i in range(n):
        j = (i + 1) % n
        for s in range(k - 1):
            fs.append((i * k + s, j * k + s, j * k + s + 1, i * k + s + 1))
    mb.add(vs, fs, m, mat)
    return mb


def proto_barrels(C, M):
    R, H = 0.29, 0.88
    prof = [(0.0, 0.03), (R - 0.02, 0.03), (R - 0.01, 0.0), (R + 0.008, 0.012), (R, 0.04), (R, 0.28), (R + 0.012, 0.29),
            (R + 0.012, 0.31), (R, 0.32), (R, 0.56), (R + 0.012, 0.57), (R + 0.012, 0.59), (R, 0.6), (R, H - 0.04),
            (R + 0.008, H - 0.012), (R - 0.01, H), (R - 0.02, H - 0.025), (0.0, H - 0.025)]
    out = []
    mb = lathe(prof, 28)
    mb.cyl((0.17, 0.0, H - 0.03), (0.17, 0.0, H + 0.005), 0.03, None, 8, 0)
    out.append(mb.obj('barrel', AST(C, 'barrel'), [M['ENV_barrel']], smooth=40))
    mb = lathe(prof, 28)
    # dents
    V = []
    for x, y, z in mb.V:
        a = math.atan2(y, x)
        d = 0.06 * math.exp(-((a - 0.8) / 0.45) ** 2) * math.exp(-((z - 0.45) / 0.18) ** 2)
        d += 0.03 * math.exp(-((a + 2.2) / 0.3) ** 2) * math.exp(-((z - 0.75) / 0.1) ** 2)
        r = math.hypot(x, y)
        k = (r - d) / r if r > 1e-4 else 1
        V.append((x * k, y * k, z - 0.03 * max(0, z - 0.6) * math.cos(a)))
    mb.V = V
    out.append(mb.obj('barrel_dented', AST(C, 'barrel_dented'), [M['ENV_barrel']], smooth=40))
    return out


def proto_crates(C, M):
    mb = MB()
    L, W, H = 1.2, 0.8, 0.72
    mb.box((L - 0.04, W - 0.04, H - 0.04), None, 0, (0, 0, H / 2))
    t = 0.025
    for z in (0.06, H - 0.06):
        for y in (-W / 2 + t / 2, W / 2 - t / 2):
            mb.box((L, t, 0.1), None, 0, (0, y, z))
        for x in (-L / 2 + t / 2, L / 2 - t / 2):
            mb.box((t, W, 0.1), None, 0, (x, 0, z))
    for x in (-L / 2 + 0.05, L / 2 - 0.05):
        for y in (-W / 2 + t / 2, W / 2 - t / 2):
            mb.box((0.1, t, H), None, 0, (x, y, H / 2))
    # diagonal brace on long sides
    for y in (-W / 2 - 0.002, W / 2 + 0.002):
        mb.box_pts(Vector((-L / 2 + 0.1, y, 0.1)), Vector((L / 2 - 0.1, y, H - 0.1)), 0.09, 0.02, 0, up=(0, 1, 0))
    c1 = mb.obj('crate_wood', AST(C, 'crate_wood'), [M['ENV_wood']], smooth=20)
    # ammo box
    mb = MB()
    L, W, H = 0.95, 0.42, 0.32
    mb.box((L, W, H - 0.05), None, 0, (0, 0, (H - 0.05) / 2))
    mb.box((L + 0.02, W + 0.02, 0.06), None, 0, (0, 0, H - 0.03))
    for x in (-L / 2 - 0.02, L / 2 + 0.02):
        mb.box((0.03, 0.18, 0.04), None, 1, (x, 0, H - 0.12))
    for x in (-0.3, 0.3):
        mb.box((0.06, W + 0.025, 0.025), None, 1, (x, 0, H - 0.03))
    c2 = mb.obj('crate_ammo', AST(C, 'crate_ammo'), [M['ENV_paint_olive'], M['ENV_rust']], smooth=20)
    return c1, c2


def proto_pallet(C, M):
    mb = MB()
    L, W = 1.2, 0.8
    for i in range(5):
        y = -W / 2 + 0.05 + i * (W - 0.1) / 4
        mb.box((L, 0.1 if i % 4 else 0.145, 0.022), None, 0, (0, y, 0.133))
    for y in (-W / 2 + 0.05, 0, W / 2 - 0.05):
        mb.box((L, 0.1, 0.022), None, 0, (0, y, 0.111))
        for x in (-L / 2 + 0.07, 0, L / 2 - 0.07):
            mb.box((0.14, 0.1, 0.078), None, 0, (x, y, 0.061))
        mb.box((L, 0.1, 0.022), None, 0, (0, y, 0.011))
    return mb.obj('pallet', AST(C, 'pallet'), [M['ENV_wood']], smooth=20)


def proto_tires(C, M):
    def tire(mb, c=(0, 0, 0), ang=0.0, flat=True):
        R0, r = 0.37, 0.135
        nu, nv = 28, 10
        vs = []
        for i in range(nu):
            a = 2 * math.pi * i / nu
            for j in range(nv):
                b = 2 * math.pi * j / nv
                tread = 0.012 if (i % 2 == 0 and abs(math.cos(b)) > 0.75) else 0.0
                rr = r + tread
                R = R0 + rr * math.cos(b)
                x, y, z = R * math.cos(a), R * math.sin(a), r * 0.95 * math.sin(b)
                vs.append((x, y, z + r))
        fs = []
        for i in range(nu):
            for j in range(nv):
                a0 = i * nv + j
                fs.append((a0, ((i + 1) % nu) * nv + j, ((i + 1) % nu) * nv + (j + 1) % nv, i * nv + (j + 1) % nv))
        mb.add(vs, fs, 0, Matrix.Translation(Vector(c)) @ Matrix.Rotation(ang, 4, 'Z'))
    mb = MB()
    tire(mb)
    t1 = mb.obj('tire', AST(C, 'tire'), [M['ENV_rubber']], smooth=60)
    mb = MB()
    rr = random.Random(9)
    for k in range(4):
        tire(mb, (rr.uniform(-0.05, 0.05), rr.uniform(-0.05, 0.05), k * 0.255), rr.uniform(0, 3))
    t2 = mb.obj('tire_stack', AST(C, 'tire_stack'), [M['ENV_rubber']], smooth=60)
    return t1, t2


def proto_fence(C, M):
    """Soviet PO-2 style slab: 4.0 x 2.5 x 0.14 m, diamond relief on the +Y face, origin bottom centre"""
    sc = SET(C, 'fence')
    L, H, T = 4.0, 2.5, 0.14
    mb = MB()
    cw, ch = 0.32, 0.2
    nx = int(round((L - 0.2) / (cw / 2)))
    nz = int(round((H - 0.2) / (ch / 2)))
    xs = [-L / 2 + 0.1 + i * (L - 0.2) / nx for i in range(nx + 1)]
    zs = [0.1 + j * (H - 0.2) / nz for j in range(nz + 1)]
    vs = []
    for j, z in enumerate(zs):
        for i, x in enumerate(xs):
            d = 0.028 if (i + j) % 2 == 0 and 0 < i < nx and 0 < j < nz else 0.0
            vs.append((x, T / 2 + d, z))
    fs = []
    for j in range(nz):
        for i in range(nx):
            a = j * (nx + 1) + i
            fs.append((a, a + nx + 1, a + nx + 2, a + 1))
    mb.add(vs, fs, 0)
    # frame border and back as a box shell (front face replaced by the relief grid inside the border)
    def quad(p):
        mb.add(p, [(0, 1, 2, 3)], 0)
    y0, y1 = -T / 2, T / 2
    x0, x1 = -L / 2, L / 2
    # border strips on front face
    quad([(x0, y1, 0), (x0, y1, H), (xs[0], y1, H), (xs[0], y1, 0)])
    quad([(xs[-1], y1, 0), (xs[-1], y1, H), (x1, y1, H), (x1, y1, 0)])
    quad([(xs[0], y1, 0), (xs[0], y1, zs[0]), (xs[-1], y1, zs[0]), (xs[-1], y1, 0)])
    quad([(xs[0], y1, zs[-1]), (xs[0], y1, H), (xs[-1], y1, H), (xs[-1], y1, zs[-1])])
    # back, top, bottom, ends
    quad([(x0, y0, 0), (x1, y0, 0), (x1, y0, H), (x0, y0, H)])
    quad([(x0, y0, H), (x1, y0, H), (x1, y1, H), (x0, y1, H)])
    quad([(x0, y0, 0), (x0, y1, 0), (x1, y1, 0), (x1, y0, 0)])
    quad([(x0, y0, 0), (x0, y0, H), (x0, y1, H), (x0, y1, 0)])
    quad([(x1, y0, 0), (x1, y1, 0), (x1, y1, H), (x1, y0, H)])
    mb.obj('fence_slab', sc, [M['ENV_concrete_prop']], smooth=10)
    return sc


def proto_boom(C, M):
    mb = MB()
    mb.cyl((0, 0, 0), (3.0, 0, 0), 0.05, 0.04, 10, 0)
    return mb.obj('boom_arm', AST(C, 'boom_arm'), [M['ENV_redwhite']], smooth=40)


def proto_pole(C, M):
    mb = MB()
    # tapered square concrete pole (1.6 m buried)
    n = 4
    mb.cyl((0, 0, -1.6), (0, 0, 8.6), 0.17, 0.1, n, 0, True, math.pi / 4)
    # crossarm (steel channel) + braces
    mb.box((2.2, 0.08, 0.1), None, 1, (0, 0.14, 8.05))
    mb.box_pts(Vector((-0.7, 0.14, 8.0)), Vector((0, 0.14, 7.3)), 0.05, 0.05, 1, up=(0, 1, 0))
    mb.box_pts(Vector((0.7, 0.14, 8.0)), Vector((0, 0.14, 7.3)), 0.05, 0.05, 1, up=(0, 1, 0))
    # insulators (glass, stacked discs)
    for x, z0 in ((-1.0, 8.1), (1.0, 8.1), (0.0, 8.6)):
        prof = [(0.0, 0.0), (0.03, 0.0), (0.03, 0.04), (0.075, 0.07), (0.05, 0.1), (0.075, 0.13), (0.045, 0.17),
                (0.04, 0.22), (0.0, 0.22)]
        lathe(prof, 12, 2, mb, Matrix.Translation((x, 0.14 if x else 0.0, z0)))
    ob = mb.obj('power_pole', AST(C, 'power_pole'), [M['ENV_concrete_prop'], M['ENV_rust'], M['ENV_glass']],
                smooth=40)
    return ob


POLE_ATTACH = [Vector((-1.0, 0.14, 8.3)), Vector((1.0, 0.14, 8.3)), Vector((0.0, 0.0, 8.8))]


def proto_lamp(C, M):
    mb = MB()
    mb.cyl((0, 0, -1.2), (0, 0, 8.2), 0.13, 0.075, 8, 0)
    pts = [Vector((0, 0, 7.9))]
    for k in range(1, 9):
        t = k / 8
        pts.append(Vector((0, -1.9 * t, 7.9 + 0.75 * math.sin(t * math.pi * 0.62))))
    mb.tube(pts, 0.035, 6, 1)
    e = pts[-1]
    # cobra head
    vs, fs = superellipsoid(0.16, 0.34, 0.07, 0.5, 0.5, 12, 6)
    mb.add([tuple(v) for v in vs], fs, 1, Matrix.Translation(e + Vector((0, -0.25, -0.02))))
    mb.box((0.18, 0.4, 0.02), None, 2, tuple(e + Vector((0, -0.27, -0.075))))
    return mb.obj('street_lamp', AST(C, 'street_lamp'), [M['ENV_concrete_prop'], M['ENV_steel_paint'], M['ENV_glass']],
                  smooth=40)


def proto_mg(C, M):
    mb = MB()
    mb.box((0.5, 0.09, 0.12), None, 0, (0, 0, 0.42))
    mb.cyl((0.25, 0, 0.44), (1.05, 0, 0.44), 0.016, None, 8, 0)
    mb.cyl((0.25, 0, 0.44), (0.6, 0, 0.44), 0.03, None, 8, 0)
    mb.box((0.3, 0.05, 0.1), None, 0, (-0.38, 0, 0.38))
    mb.box((0.12, 0.1, 0.08), None, 0, (0.05, 0, 0.32))   # ammo box
    for s in (-1, 1):
        mb.box_pts(Vector((0.6, 0, 0.42)), Vector((0.75, 0.22 * s, 0.0)), 0.02, 0.02, 0)
    return mb.obj('machine_gun', AST(C, 'machine_gun'), [M['ENV_steel_paint']], smooth=40)


# ---------------------------------------------------------------- placement helpers
class Placer:
    def __init__(self, C, ground):
        self.C = C
        self.g = ground
        self.n = {}

    def put(self, proto, x, y, rz=0.0, rx=0.0, ry=0.0, s=1.0, dz=0.0, name=None):
        z = self.g.z(x, y) + dz
        k = name or proto
        self.n[k] = self.n.get(k, 0) + 1
        nm = 'PRP_%s_%02d' % (k, self.n[k])
        return coll_instance(nm, self.C['ENV_props'], bpy.data.collections['AST_' + proto], (x, y, z),
                             D2R(rz), D2R(rx), D2R(ry), s)


def bag_wall(items, ground, pts, courses=4, rnd=None, closed=False, z_off=0.0):
    """sandbag wall along a polyline (list of (x,y)); returns GN items"""
    P = [Vector((p[0], p[1], 0)) for p in pts]
    if closed:
        P.append(P[0])
    segs = []
    tot = 0.0
    for a, b in zip(P[:-1], P[1:]):
        segs.append((a, b, tot))
        tot += (b - a).length
    step = 0.56
    protos = ['bag_a', 'bag_b', 'bag_c']
    for c in range(courses):
        s = (step / 2) * (c % 2) + 0.15
        shrink = c * 0.08   # slight batter
        while s < tot - 0.15:
            for a, b, s0 in segs:
                L = (b - a).length
                if s0 <= s <= s0 + L:
                    t = (b - a).normalized()
                    p = a + t * (s - s0)
                    n = Vector((-t.y, t.x, 0))
                    p = p + n * (shrink * 0.5) + n * rnd.uniform(-0.02, 0.02)
                    z = ground.z(p.x, p.y) - 0.02 + c * 0.128 + z_off
                    ang = math.atan2(t.y, t.x) + rnd.uniform(-0.12, 0.12)
                    items.append((Vector((p.x, p.y, z)), (rnd.uniform(-0.05, 0.05), rnd.uniform(-0.06, 0.06), ang),
                                  (rnd.uniform(0.95, 1.05), rnd.uniform(0.95, 1.08), rnd.uniform(0.9, 1.1)),
                                  rnd.choice(protos)))
                    break
            s += step * rnd.uniform(0.97, 1.03)


# ---------------------------------------------------------------- unique set pieces
def build_booth(C, M, ground, rnd):
    x, y = BOOTH
    z = ground.z(x, y) + 0.02
    mb = MB()
    S, Hw = 2.4, 2.45
    h = S / 2
    mb.box((S + 0.2, S + 0.2, 0.22), None, 4, (0, 0, -0.08))       # plinth
    for cx in (-h, h):
        for cy in (-h, h):
            mb.box((0.12, 0.12, Hw), None, 0, (cx, cy, Hw / 2))
    sides = {'S': ((0, -h), (1, 0)), 'N': ((0, h), (1, 0)), 'E': ((h, 0), (0, 1)), 'W': ((-h, 0), (0, 1))}
    for k, ((cx, cy), (tx, ty)) in sides.items():
        sx, sy = (S, 0.08) if tx else (0.08, S)
        if k == 'N':
            # door in the north wall (x in [0.1, 1.0])
            mb.box((1.2, 0.08, 1.0), None, 0, (-0.6, cy, 0.5))
            mb.box((1.2, 0.08, 0.35), None, 0, (-0.6, cy, Hw - 0.17))
            mb.box((0.2, 0.08, Hw), None, 0, (1.1, cy, Hw / 2))
            mb.box((1.0, 0.08, 0.45), None, 0, (0.55, cy, Hw - 0.22))
        else:
            mb.box((sx, sy, 1.05), None, 0, (cx, cy, 0.525))
            mb.box((sx, sy, 0.35), None, 0, (cx, cy, Hw - 0.17))
            for f in (-0.33, 0.33):
                mb.box((0.05 if tx else 0.07, 0.07 if tx else 0.05, Hw - 1.4), None, 3,
                       (cx + tx * f * S, cy + ty * f * S, 1.05 + (Hw - 1.4) / 2))
    # roof slab + red/white fascia
    mb.box((S + 0.6, S + 0.6, 0.12), None, 1, (0, 0, Hw + 0.06))
    for k, ((cx, cy), (tx, ty)) in sides.items():
        L = S + 0.64
        ox, oy = cx * (S + 0.6) / S, cy * (S + 0.6) / S
        mb.box((L if tx else 0.04, 0.04 if tx else L, 0.28), None, 2, (ox, oy, Hw + 0.04))
    # open door leaf
    hinge = Vector((1.0, h, 0.0))
    Mr = Matrix.Translation(hinge) @ Matrix.Rotation(D2R(-115), 4, 'Z')
    mb.box((0.85, 0.04, 2.0), Mr, 3, (-0.43, 0.02, 1.02))
    # glass shards left in some frames
    for (px, py, nx, ny) in ((-0.6, -h, 1, 0), (0.75, -h, 1, 0), (h, 0.4, 0, 1)):
        pts = []
        for k in range(5):
            a = k / 4
            pts.append((px + nx * (a - 0.5) * 0.7, py + ny * (a - 0.5) * 0.7, 1.08 + rnd.uniform(0.05, 0.6) * (1 - abs(a - 0.5))))
        vs = [(px + nx * (-0.35), py + ny * (-0.35), 1.08), (px + nx * 0.35, py + ny * 0.35, 1.08)] + pts[::-1]
        mb.add(vs, [tuple(range(len(vs)))], 5)
    # desk + chair inside
    mb.box((1.4, 0.6, 0.06), None, 3, (-0.2, -0.75, 0.95))
    mb.box((0.05, 0.55, 0.9), None, 3, (-0.85, -0.75, 0.47))
    # soot on the west side (burned)
    ob = mb.obj('CHK_booth', C['ENV_props'],
                [M['ENV_paint_white'], M['ENV_steel_paint'], M['ENV_redwhite'], M['ENV_rust'], M['ENV_concrete_prop'],
                 M['ENV_glass']], loc=(0, 0, 0), smooth=30)
    ob.location = (x, y, z)
    # sign "KPP" on the road side (south), Cyrillic text converted to mesh
    sign_panel = MB()
    sign_panel.box((1.5, 0.05, 0.42), None, 0, (0, -(h + 0.33), Hw + 0.42))
    sign_panel.box((0.05, 0.05, 0.3), None, 1, (-0.6, -(h + 0.3), Hw + 0.18))
    sign_panel.box((0.05, 0.05, 0.3), None, 1, (0.6, -(h + 0.3), Hw + 0.18))
    sp = sign_panel.obj('CHK_sign', C['ENV_props'], [M['ENV_paint_white'], M['ENV_rust']], loc=(0, 0, 0))
    sp.location = (x, y, z)
    txt = text_mesh('CHK_sign_text', C['ENV_props'], 'КПП', 0.3, M['ENV_wire'], extrude=0.01)
    if txt:
        txt.location = (x - 0.33, y - (h + 0.365), z + Hw + 0.31)
        txt.rotation_euler = (D2R(90), 0, 0)
        apply_rot(txt)
    return ob


def apply_rot(ob):
    me = ob.data
    R = ob.rotation_euler.to_matrix().to_4x4()
    me.transform(R)
    ob.rotation_euler = (0, 0, 0)


def text_mesh(name, coll, body, size, mat, extrude=0.0, align='LEFT'):
    cu = bpy.data.curves.new(name, 'FONT')
    cu.body = body
    cu.size = size
    cu.extrude = extrude
    cu.align_x = align
    tmp = bpy.data.objects.new(name + '_tmp', cu)
    coll.objects.link(tmp)
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(tmp.evaluated_get(dg))
    bpy.data.objects.remove(tmp, do_unlink=True)
    bpy.data.curves.remove(cu)
    if not len(me.polygons):
        return None
    me.materials.clear()
    me.materials.append(mat)
    ob = bpy.data.objects.new(name, me)
    coll.objects.link(ob)
    return ob


def build_barrier(C, M, P, ground):
    x, y = BOOM_PIVOT
    z = ground.z(x, y)
    mb = MB()
    mb.box((0.28, 0.28, 1.05), None, 0, (0, 0, 0.52))
    mb.box((0.36, 0.36, 0.12), None, 0, (0, 0, 0.0))
    mb.box((0.5, 0.2, 0.3), None, 1, (-0.45, 0, 1.0))          # counterweight
    mb.cyl((-0.2, 0, 1.0), (0.2, 0, 1.0), 0.06, None, 10, 1)
    ob = mb.obj('CHK_barrier_post', C['ENV_props'], [M['ENV_redwhite'], M['ENV_rust']], loc=(0, 0, 0))
    ob.location = (x, y, z)
    # snapped arm: 1.0 m stub drooping, broken 4.5 m piece lying on the shoulder east of the gate
    P.put('boom_arm', x + 0.15, y, rz=0, ry=12, s=(0.33, 1, 1), dz=1.0)
    P.put('boom_arm', 7.8, -10.2, rz=-28, s=(1.5, 1, 1), dz=0.05)


def build_fence(C, M, ground, rnd):
    sc = bpy.data.collections['SET_fence']
    items = []
    # north line, slabs centred every 4 m from x=-38 to x=22; breach (mech) at x -4..6
    y = FENCE_N_Y
    for i in range(16):
        x = FENCE_W_X + 2.0 + i * 4.02
        zg = ground.z(x, y)
        if i in (9, 10, 11):
            # breach: knocked flat to the south (the mech came through from the north)
            tilt = rnd.uniform(76, 86)
            items.append((Vector((x + rnd.uniform(-0.3, 0.3), y - 0.15, zg + 0.08)),
                          (D2R(tilt), 0, D2R(rnd.uniform(-14, 14))), 1.0, 'fence_slab'))
        elif i == 12:
            items.append((Vector((x, y, zg - 0.25)), (D2R(22), D2R(4), 0), 1.0, 'fence_slab'))   # leaning
        elif i == 4:
            continue   # missing slab
        else:
            items.append((Vector((x, y, zg - 0.25)), (D2R(rnd.uniform(-1.5, 1.5)), 0, D2R(rnd.uniform(-0.6, 0.6))),
                          1.0, 'fence_slab'))
    # west line
    x = FENCE_W_X
    for i in range(6):
        y = FENCE_N_Y - 2.0 - i * 4.02
        zg = ground.z(x, y)
        r = (D2R(rnd.uniform(-1, 1)), D2R(rnd.uniform(-1, 1)), D2R(90))
        if i == 3:
            r = (D2R(-18), 0, D2R(90))
        if i == 4:
            continue
        items.append((Vector((x, y, zg - 0.25)), r, 1.0, 'fence_slab'))
    instance_points('ENV_fence_slabs', C['ENV_props'], sc, items)


def build_sandbags(C, M, ground, rnd):
    items = []
    bx, by = BOOTH
    bag_wall(items, ground, [(bx - 1.75, by - 1.6), (bx - 1.75, by + 1.4)], 4, rnd)
    bag_wall(items, ground, [(bx + 1.6, by + 2.1), (bx - 1.2, by + 2.1)], 3, rnd)
    # MG nest: ring with an opening to the north
    cx, cy = MG_NEST
    ring = [(cx + 1.7 * math.cos(D2R(115 + 310 * k / 14)), cy + 1.7 * math.sin(D2R(115 + 310 * k / 14))) for k in range(15)]
    bag_wall(items, ground, ring, 5, rnd)
    # roadside bunker west of the gate and by the hangar door
    bag_wall(items, ground, [(-24.0, -8.2), (-19.5, -8.0), (-18.5, -6.4)], 4, rnd)
    bag_wall(items, ground, [(24.2, 7.0), (24.2, 9.0)], 3, rnd)
    bag_wall(items, ground, [(24.2, 17.0), (24.2, 19.2)], 3, rnd)
    # spilled bags
    for _ in range(14):
        cx, cy = rnd.choice(((MG_NEST[0], MG_NEST[1] + 2.4), (-21.0, -9.4), (BOOTH[0] - 2.6, BOOTH[1])))
        x, y = cx + rnd.uniform(-1.2, 1.2), cy + rnd.uniform(-1.2, 1.2)
        items.append((Vector((x, y, ground.z(x, y) - 0.02)), (rnd.uniform(-0.3, 0.3), rnd.uniform(-0.3, 0.3),
                                                            rnd.uniform(0, 6.28)), 1.0, rnd.choice(('bag_a', 'bag_b'))))
    instance_points('ENV_sandbags', C['ENV_props'], bpy.data.collections['SET_sandbags'], items)


def build_power_line(C, M, P, ground, rnd):
    poles = []
    for i, x in enumerate(POLE_X):
        c, t, n = G.road_frame(x)
        p = c + n * POLE_OFF
        ang = math.degrees(math.atan2(t.y, t.x)) + 90.0
        lean = (0.0, 0.0)
        if i == 2:
            lean = (9.0, -5.0)
        e = P.put('power_pole', p.x, p.y, rz=ang, rx=lean[0], ry=lean[1], dz=0.0)
        poles.append(e)
    bpy.context.view_layer.update()
    mb = MB()
    for i in range(len(poles) - 1):
        A = poles[i].matrix_world
        B = poles[i + 1].matrix_world
        for w, att in enumerate(POLE_ATTACH):
            a = A @ att
            b = B @ att
            if i == 2 and w == 0:
                # broken wire: hangs from pole i, lies on the ground
                pts = [a]
                d = (b - a)
                d.z = 0
                d.normalize()
                for k in range(1, 9):
                    t = k / 8
                    q = a + d * (6.0 * t) + Vector((0, 0, -a.z * (1 - (1 - t) ** 2.2)))
                    q.z = max(ground.z(q.x, q.y) + 0.02, a.z - (a.z - ground.z(q.x, q.y)) * (t ** 0.6) - 0.02)
                    pts.append(q)
                for k in range(1, 7):
                    q = pts[-1] + Vector((d.x * 0.9, d.y * 0.9 + 0.25 * math.sin(k), 0))
                    q.z = ground.z(q.x, q.y) + 0.02
                    pts.append(q)
                mb.tube(pts, 0.012, 4, 0)
                continue
            L = (b - a).length
            sag = 0.0011 * L * L + rnd.uniform(-0.05, 0.1)
            pts = []
            for k in range(17):
                t = k / 16
                q = a.lerp(b, t)
                q.z -= 4 * sag * t * (1 - t)
                pts.append(q)
            mb.tube(pts, 0.012, 4, 0)
    mb.obj('ENV_power_wires', C['ENV_props'], [M['ENV_wire']], smooth=60)


def build_lamps(C, M, P, ground):
    for x, off, lean in LAMPS:
        c, t, n = G.road_frame(x)
        p = c + n * off
        ang = math.degrees(math.atan2(t.y, t.x))
        P.put('street_lamp', p.x, p.y, rz=ang, rx=lean, ry=-lean * 0.4)


def build_scatter_props(C, M, P, ground, rnd):
    # jersey barriers: along the north road edge east/west of the gate, chicane on the road, a few knocked about
    for x, d, rz, kind in ((9.5, 4.9, 0, 'jersey_striped'), (12.7, 4.9, 2, 'jersey_plain'),
                           (15.9, 5.0, -1, 'jersey_striped'), (24.5, 5.2, 3, 'jersey_plain'),
                           (-14.0, 4.9, 1, 'jersey_striped'), (-17.2, 5.0, -2, 'jersey_plain'),
                           (-25.0, 5.3, 4, 'jersey_striped'),
                           (14.5, 1.6, 0, 'jersey_striped'), (21.0, -1.6, 0, 'jersey_striped'),
                           (-15.0, -1.7, 0, 'jersey_plain'), (-21.0, 1.6, 0, 'jersey_striped')):
        c, t, n = G.road_frame(x)
        p = c + n * d
        ang = math.degrees(math.atan2(t.y, t.x)) + rz
        P.put(kind, p.x, p.y, rz=ang, dz=-0.02)
    # knocked by the mech near the gate
    P.put('jersey_striped', -7.9, -12.2, rz=68, ry=86, dz=0.28)
    P.put('jersey_plain', 8.1, -12.6, rz=-52, dz=-0.02)
    P.put('jersey_striped', 8.6, -15.2, rz=-80, rx=-8, dz=-0.05)
    # hedgehogs: south roadside rows + a few at the gate
    for x in (-22.0, -18.5, -15.0, -11.5, 11.5, 15.0, 18.5, 22.0, 26.0):
        c, t, n = G.road_frame(x)
        p = c + n * rnd.uniform(-6.6, -5.8)
        P.put('hedgehog', p.x, p.y, rz=rnd.uniform(0, 360), dz=-0.04)
    for (x, y) in ((-10.0, -12.8), (10.8, -11.9), (-16.5, 8.5), (-6.9, 10.5)):
        P.put('hedgehog', x, y, rz=rnd.uniform(0, 360), dz=-0.04)
    P.put('hedgehog', -9.0, 7.6, rz=33, rx=62, ry=10, dz=0.25)   # tipped near the crater
    # barrels / crates / pallets / tyres clusters
    def cluster(cx, cy, spec):
        for proto, dx, dy, rz, rx, dz in spec:
            P.put(proto, cx + dx, cy + dy, rz=rz, rx=rx, dz=dz)
    cluster(BOOTH[0] - 0.4, BOOTH[1] + 2.0, [('barrel', -1.1, 0.4, 0, 0, 0), ('barrel_dented', -1.75, 0.75, 40, 0, 0),
                                              ('crate_ammo', 0.6, 0.6, 12, 0, 0)])
    cluster(22.5, 4.2, [('barrel', 0, 0, 0, 0, 0), ('barrel', 0.62, 0.1, 50, 0, 0), ('barrel_dented', 0.3, 0.6, 10, 0, 0),
                        ('barrel', 1.4, -0.5, 30, 90, 0.29), ('pallet', -1.6, 0.2, 7, 0, 0),
                        ('pallet', -1.6, 0.2, 2, 0, 0.145), ('crate_wood', -1.6, 0.25, 5, 0, 0.29),
                        ('crate_ammo', 0.9, 1.4, 70, 0, 0), ('crate_ammo', 1.0, 1.45, 64, 0, 0.32),
                        ('tire_stack', -3.2, -0.4, 0, 0, 0), ('tire', -2.6, 1.2, 0, 0, 0)])
    cluster(24.6, 20.6, [('barrel', 0, 0, 0, 0, 0), ('barrel_dented', 0.6, 0.3, 0, 0, 0), ('barrel', 1.2, -0.1, 0, 0, 0),
                         ('crate_wood', -1.5, 0.2, 80, 0, 0), ('pallet', -0.4, -1.3, 85, 70, 0.45)])
    cluster(-14.2, 18.4, [('barrel', 0, 0, 0, 0, 0), ('barrel', 0.6, 0.2, 0, 90, 0.29), ('tire', -1.3, 0.5, 0, 0, 0),
                          ('tire', -1.25, 0.45, 20, 0, 0.27), ('pallet', 1.6, -0.7, 30, 0, 0)])
    cluster(MG_NEST[0], MG_NEST[1], [('crate_ammo', -0.4, 0.5, 20, 0, 0), ('crate_ammo', 0.5, 0.3, -30, 0, 0),
                                     ('machine_gun', 0.0, -1.45, -90, 0, 0.62)])
    cluster(-30.5, -18.5, [('tire', 0, 0, 0, 0, 0), ('tire', 1.3, -0.6, 0, 75, 0.36), ('barrel_dented', -1.2, 0.8, 0, 90, 0.29)])
    cluster(-6.4, 13.6, [('barrel', 0, 0, 0, 0, 0), ('barrel_dented', 0.7, -0.3, 0, 95, 0.29)])
    cluster(12.6, 9.5, [('pallet', 0, 0, 12, 0, 0), ('crate_wood', 0.1, 0.0, 15, 0, 0.145), ('crate_ammo', 1.2, 0.8, 40, 0, 0)])
    cluster(-12.8, -4.6, [('crate_ammo', 0, 0, 10, 0, 0), ('barrel', 1.0, 0.8, 0, 0, 0)])


# ---------------------------------------------------------------- vehicle slots, placeholders, labels, path
def placeholder_mesh(kind, L, W, H):
    mb = MB()
    if kind == 'truck':
        cab = 2.3
        mb.box((W, cab, H * 0.92), None, 0, (0, -L / 2 + cab / 2, H * 0.46 + 0.0))
        mb.box((W, L - cab - 0.15, H * 0.5), None, 0, (0, cab / 2 + 0.075, 0.55 + H * 0.25))
        mb.box((W * 0.9, L - cab - 0.15, 0.08), None, 1, (0, cab / 2 + 0.075, 0.55 + H * 0.5 + 0.04))
    elif kind == 'apc':
        mb.box((W, L, H * 0.68), None, 0, (0, 0, 0.45 + H * 0.34 - 0.3))
        mb.box((W * 0.85, L * 0.2, 0.4), None, 0, (0, -L / 2 + L * 0.1 - 0.1, 0.35))
        mb.cyl((0, -0.2, H * 0.83), (0, -0.2, H), 0.75, 0.7, 12, 0)
        mb.cyl((0, -0.6, H * 0.9), (0, -3.0, H * 0.9), 0.06, None, 8, 1)
    else:
        mb.box((W, L, H * 0.55), None, 0, (0, 0, 0.2 + H * 0.275))
        cl = L * (0.5 if kind == 'sedan' else 0.45)
        mb.box((W * 0.9, cl, H * 0.4), None, 0, (0, 0.05 * L if kind == 'sedan' else 0.12 * L, 0.2 + H * 0.55 + H * 0.2 - 0.02))
    # forward marker (dark) on the -Y face
    mb.box((W * 0.5, 0.05, 0.25), None, 1, (0, -L / 2 - 0.02, H * 0.35))
    return mb


def build_slots(C, M, ground):
    out = {}
    for nm, (x, y, rz, (L, W, H), kind) in SLOTS.items():
        z = ground.z(x, y)
        e = bpy.data.objects.new('VEH_slot_' + nm, None)
        e.empty_display_type = 'SINGLE_ARROW'
        e.empty_display_size = 2.0
        e.location = (x, y, z)
        e.rotation_euler = (0, 0, D2R(rz))
        e['vehicle_length_m'] = L
        e['vehicle_forward'] = '-Y'
        C['ENV_slots'].objects.link(e)
        mb = placeholder_mesh(kind, L, W, H)
        ph = mb.obj('PH_' + nm, C['ENV_placeholders'], [M['ENV_placeholder'], M['ENV_placeholder_dark']])
        ph.parent = e
        out[nm] = e
    # mech start marker + walk path (top view only)
    e = bpy.data.objects.new('MECH_walk_start', None)
    e.empty_display_type = 'ARROWS'
    e.location = (0, 0, 0)
    C['ENV_slots'].objects.link(e)
    e2 = bpy.data.objects.new('MECH_walk_end', None)
    e2.empty_display_type = 'ARROWS'
    e2.location = (0, -20.0, ground.z(0, -20.0))
    C['ENV_slots'].objects.link(e2)
    mb = MB()
    for k in range(40):
        y0, y1 = -k * 0.5, -(k + 1) * 0.5
        if k % 2:
            continue
        z0 = ground.z(0, y0) + 0.06
        mb.add([(-0.35, y0, z0), (0.35, y0, z0), (0.35, y1, z0), (-0.35, y1, z0)], [(0, 1, 2, 3)][::1], 0)
    zt = ground.z(0, -20) + 0.06
    mb.add([(-1.4, -19.8, zt), (1.4, -19.8, zt), (0, -22.0, zt)], [(0, 2, 1)], 0)
    mb.obj('ENV_walkpath', C['ENV_debug'], [M['ENV_path']])
    labels = {'truck': 'TRUCK 8m', 'jeep': 'JEEP 4m', 'apc': 'APC 8x8', 'wreck': 'WRECK'}
    for nm, txt in labels.items():
        x, y = SLOTS[nm][0], SLOTS[nm][1]
        t = text_mesh('LBL_' + nm, C['ENV_debug'], txt, 2.0, M['ENV_label'], 0.0, 'CENTER')
        if t:
            t.location = (x, y + 3.2, 12.0)
    t = text_mesh('LBL_mech', C['ENV_debug'], 'MECH  walk 20m', 2.0, M['ENV_label'], 0.0, 'CENTER')
    if t:
        t.location = (6.5, -23.5, 14.0)
    return out


def build(C, M, ground, rnd):
    proto_jersey(C, M)
    proto_sandbags(C, M)
    proto_hedgehog(C, M)
    proto_barrels(C, M)
    proto_crates(C, M)
    proto_pallet(C, M)
    proto_tires(C, M)
    proto_fence(C, M)
    proto_boom(C, M)
    proto_pole(C, M)
    proto_lamp(C, M)
    proto_mg(C, M)
    P = Placer(C, ground)
    build_booth(C, M, ground, rnd)
    build_barrier(C, M, P, ground)
    build_fence(C, M, ground, rnd)
    build_sandbags(C, M, ground, rnd)
    build_power_line(C, M, P, ground, rnd)
    build_lamps(C, M, P, ground)
    build_scatter_props(C, M, P, ground, rnd)
    build_slots(C, M, ground)

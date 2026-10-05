# Environment kit - layout constants, height field, terrain, road, apron, puddles, ruts.
import bpy, math, random
from mathutils import Vector, noise
from mathutils.bvhtree import BVHTree
from env_common import MB, fbm, smoothstep, lerp, get_coll

# ---------------- layout ----------------
APRON = (-14.0, -8.0, 14.0, 12.0)          # concrete yard, mech stands at origin
CRATER = (-12.5, 5.0, 3.2)                # x, y, radius
DRIVE_X = (-7.0, 7.0)                     # driveway road -> apron (no ditch), also mech walk corridor
PADS = {  # building pads: (xmin, ymin, xmax, ymax)
    'B1': (-33.0, 20.0, -15.0, 29.0),
    'B2': (-1.5, 26.0, 13.5, 38.0),
    'B3': (-41.0, -38.0, -20.0, -29.0),
    'HANGAR': (26.0, 4.0, 56.0, 22.0),
    'BOOTH': (-11.6, -10.0, -8.4, -7.0),
    'TRUCK': (14.0, -8.0, 23.0, -4.4),
}


def road_y(x):
    y = -15.0 + 3.0 * math.sin((x + 20.0) / 55.0)
    if x > 60:
        y += 0.002 * (x - 60) ** 2
    if x < -60:
        y -= 0.0015 * (x + 60) ** 2
    return y


def road_dy(x):
    d = 3.0 / 55.0 * math.cos((x + 20.0) / 55.0)
    if x > 60:
        d += 0.004 * (x - 60)
    if x < -60:
        d -= 0.003 * (x + 60)
    return d


def road_frame(x):
    t = Vector((1.0, road_dy(x), 0.0)).normalized()
    n = Vector((-t.y, t.x, 0.0))
    return Vector((x, road_y(x), 0.0)), t, n


def road_d(x, y):
    """signed distance to road centreline (+ = north side)"""
    c, t, n = road_frame(x)
    return (Vector((x, y, 0)) - c).dot(n)


def box_dist(x, y, b):
    dx = max(b[0] - x, 0.0, x - b[2])
    dy = max(b[1] - y, 0.0, y - b[3])
    return math.hypot(dx, dy)


def base_h(x, y):
    h = 1.4 * fbm(x / 90.0, y / 90.0, 3, 1) + 0.35 * fbm(x / 25.0, y / 25.0, 3, 2)
    r = math.hypot(x, y)
    h += max(0.0, r - 75.0) ** 1.4 * 0.02
    return h


H0 = base_h(0.0, 0.0)
COMPOUND = (-18.0, -10.0, 26.0, 16.0)


def road_z(x):
    b = base_h(x, road_y(x)) - H0
    w = 1.0 - smoothstep(18.0, 50.0, abs(x - 4.0))
    return lerp(b, 0.0, w)


PAD_Z = {}


def pad_z(k):
    if k not in PAD_Z:
        b = PADS[k]
        cx, cy = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2
        PAD_Z[k] = flat_h(cx, cy)
    return PAD_Z[k]


def flat_h(x, y):
    """terrain before pads/crater/details"""
    h = base_h(x, y) - H0
    wc = 1.0 - smoothstep(0.0, 20.0, box_dist(x, y, COMPOUND))
    h = lerp(h, 0.0, wc)
    d = road_d(x, y)
    wr = 1.0 - smoothstep(5.0, 10.0, abs(d))
    h = lerp(h, road_z(x) - 0.06, wr)
    return h


def ditch_mask(x):
    return smoothstep(DRIVE_X[1] + 1.0, DRIVE_X[1] + 5.0, abs(x - 0.5))


def terrain_h(x, y):
    h = flat_h(x, y)
    d = road_d(x, y)
    ad = abs(d)
    # drainage ditches along the road (not across the driveway)
    h -= 0.5 * math.exp(-((ad - 7.4) / 0.9) ** 2) * ditch_mask(x)
    # building pads
    for k, b in PADS.items():
        w = 1.0 - smoothstep(0.0, 5.0, box_dist(x, y, b))
        if w > 0:
            h = lerp(h, pad_z(k), w)
    # apron sits on a slightly lower bed (slab seams read as gaps)
    wa = 1.0 - smoothstep(0.0, 0.8, box_dist(x, y, APRON))
    h = lerp(h, -0.09, wa)
    # crater bowl + rim
    cx, cy, cr = CRATER
    r = math.hypot(x - cx, y - cy)
    if r < cr * 2.2:
        rn = r / cr
        h -= 1.15 * max(0.0, 1.0 - rn * rn) ** 1.3
        h += 0.38 * math.exp(-((rn - 1.08) / 0.28) ** 2)
    # micro relief away from road / apron
    calm = max(1.0 - smoothstep(4.0, 7.0, ad), wa)
    h += (0.07 * fbm(x / 2.2, y / 2.2, 2, 5) + 0.03 * fbm(x / 0.8, y / 0.8, 1, 6)) * (1.0 - 0.85 * calm)
    return h


# ---------------- terrain ----------------
def axis_samples(dense=50.0, step=0.5, far=178.0, grow=1.16):
    xs = [-dense + i * step for i in range(int(2 * dense / step) + 1)]
    s = step
    x = dense
    out = []
    while x < far:
        s *= grow
        x = min(far, x + s)
        out.append(x)
    return [-v for v in reversed(out)] + xs + out


def masks(x, y, h):
    d = road_d(x, y)
    ad = abs(d)
    ap = box_dist(x, y, APRON)
    near_road = 1.0 - smoothstep(4.5, 6.5, ad)
    gravel = (smoothstep(3.6, 4.2, ad) * (1.0 - smoothstep(5.4, 7.0, ad)))
    if DRIVE_X[0] - 1 < x < DRIVE_X[1] + 1 and -12.5 < y < -7.0:
        gravel = 1.0
    for kk in ('BOOTH', 'TRUCK'):
        gravel = max(gravel, 1.0 - smoothstep(0.0, 2.5, box_dist(x, y, PADS[kk])))
    gravel = max(gravel, (1.0 - smoothstep(0.5, 2.5, ap)) * 0.7)
    g = smoothstep(-0.15, 0.35, fbm(x / 9.0, y / 9.0, 3, 11) + 0.25 * fbm(x / 2.5, y / 2.5, 2, 12))
    g *= (1.0 - near_road) * smoothstep(0.5, 3.0, ap)
    for k, b in PADS.items():
        g *= smoothstep(0.0, 2.5, box_dist(x, y, b))
    cx, cy, cr = CRATER
    g *= smoothstep(cr * 1.6, cr * 2.4, math.hypot(x - cx, y - cy))
    ditch = math.exp(-((ad - 7.4) / 0.9) ** 2) * ditch_mask(x)
    g = max(g, ditch * 0.85)
    wet = ditch * smoothstep(-0.2, 0.3, fbm(x / 6.0, y / 6.0, 2, 13))
    return gravel, g, wet


def build_terrain(coll, mats):
    xs = axis_samples()
    ys = axis_samples()
    mb = MB()
    nx = len(xs)
    verts = []
    gv, gs, wt = [], [], []
    uv = []
    for y in ys:
        for x in xs:
            h = terrain_h(x, y)
            verts.append((x, y, h))
            a, b, c = masks(x, y, h)
            gv.append(a)
            gs.append(b)
            wt.append(c)
            uv.append((x / 10.0, y / 10.0))
    faces = []
    for j in range(len(ys) - 1):
        for i in range(nx - 1):
            a = j * nx + i
            faces.append((a, a + 1, a + nx + 1, a + nx))
    mb.add(verts, faces, 0)
    mb.PA = {'gravel': gv, 'grass': gs, 'wet': wt}
    ob = mb.obj('ENV_terrain', coll, [mats['ENV_ground']], smooth=180, uv=uv)
    return ob


# ---------------- road ----------------
POTHOLES = [  # x, d (across), radius, depth
    (-38, 1.6, 0.7, 0.10), (-31, -2.2, 0.5, 0.08), (-22, 0.5, 0.9, 0.12), (-17, 2.6, 0.45, 0.07),
    (-9, -1.8, 0.8, 0.10), (-3.5, 1.9, 1.1, 0.07), (3, -2.6, 0.6, 0.09), (11, 2.8, 0.55, 0.08),
    (15, -1.2, 0.75, 0.11), (23, 0.8, 0.5, 0.07), (31, -2.9, 0.9, 0.1), (37, 2.2, 0.6, 0.08),
    (44, -0.6, 0.8, 0.12), (52, 1.5, 0.6, 0.09), (-47, -1.0, 0.7, 0.1), (-5.5, -3.2, 0.5, 0.06),
    (7.5, 0.3, 0.4, 0.06), (-27, 3.3, 0.6, 0.08),
]
# shallow sags that hold large puddles: x, d, rx, rd, depth
SAGS = [(-3.0, 1.7, 2.0, 1.25, 0.05), (19.0, -2.0, 1.6, 1.1, 0.045), (-24.0, -1.0, 1.4, 0.9, 0.04)]


def pothole_depth(x, d):
    dep = 0.0
    for px, pd, pr, pz in POTHOLES:
        r = math.hypot(x - px, d - pd) / pr
        if r < 1.25:
            dep = max(dep, pz * (1.0 - smoothstep(0.55, 1.15, r)))
    sag = 0.0
    for sx, sd, rx, rd, sz in SAGS:
        r = math.hypot((x - sx) / rx, (d - sd) / rd)
        if r < 1.6:
            sag = max(sag, sz * (1.0 - smoothstep(0.0, 1.5, r)))
    return dep, sag


def road_width(x):
    return 4.0 + 0.16 * fbm(x / 3.0, 0.5, 3, 21) + 0.1 * fbm(x / 0.9, 2.5, 1, 22)


def road_surface(x, d):
    zr = road_z(x)
    crown = 0.07 * (1.0 - (d / 4.0) ** 2)
    dep, sag = pothole_depth(x, d)
    return zr + 0.01 + crown + 0.008 * fbm(x / 1.5, d / 1.5, 2, 23) - dep - sag, dep


def build_road(coll, mats):
    xs = [x for x in axis_samples(46.0, 0.25, 178.0, 1.12)]
    ncol = 33
    verts, faces, uv, ph = [], [], [], []
    s_acc = 0.0
    prev = None
    rows = 0
    for x in xs:
        c, t, n = road_frame(x)
        if prev is not None:
            s_acc += (c - prev).length
        prev = c
        w = road_width(x)
        row = []
        # skirt (left), body, skirt (right)
        ds = [-(w + 0.06)] + [-w + 2 * w * k / (ncol - 1) for k in range(ncol)] + [w + 0.06]
        for k, d in enumerate(ds):
            z, dep = road_surface(x, max(-w, min(w, d)))
            if k == 0 or k == len(ds) - 1:
                z -= 0.2
            p = c + n * d
            verts.append((p.x, p.y, z))
            uv.append((d / 8.0 + 0.5, s_acc / 8.0))
            ph.append(min(1.0, dep / 0.08))
        rows += 1
    nc = ncol + 2
    for j in range(rows - 1):
        for i in range(nc - 1):
            a = j * nc + i
            faces.append((a, a + nc, a + nc + 1, a + 1))
    mb = MB()
    mb.add(verts, faces, 0)
    mb.PA = {'pothole': ph}
    ob = mb.obj('ENV_road_asphalt', coll, [mats['ENV_asphalt']], smooth=180, uv=uv)
    return ob


def puddle_ring(cx, cy, z, rx, ry, rot, seed, n=24):
    rnd = random.Random(seed)
    pts = []
    for i in range(n):
        a = 2 * math.pi * i / n
        k = 1.0 + 0.22 * fbm(math.cos(a) * 1.3 + seed, math.sin(a) * 1.3, 3, seed)
        px, py = math.cos(a) * rx * k, math.sin(a) * ry * k
        ca, sa = math.cos(rot), math.sin(rot)
        pts.append((cx + px * ca - py * sa, cy + px * sa + py * ca, z))
    return pts


def build_puddles(coll, mats, ground):
    mb = MB()
    seed = 0
    # road sags: big reflective puddles
    for sx, sd, rx, rd, sz in SAGS:
        c, t, n = road_frame(sx)
        p = c + n * sd
        z, _ = road_surface(sx, sd)
        zw = z + sz * 0.55
        ang = math.atan2(t.y, t.x)
        ring = puddle_ring(p.x, p.y, zw, rx * 0.95, rd * 0.9, ang, 100 + seed)
        mb.add(ring, [tuple(range(len(ring)))], 0)
        seed += 1
    # deeper potholes hold water
    for px, pd, pr, pz in POTHOLES:
        if pz < 0.08:
            continue
        c, t, n = road_frame(px)
        p = c + n * pd
        z, _ = road_surface(px, pd)
        ring = puddle_ring(p.x, p.y, z + pz * 0.55, pr * 0.62, pr * 0.55, random.Random(seed).uniform(0, 3), 200 + seed, 16)
        mb.add(ring, [tuple(range(len(ring)))], 0)
        seed += 1
    # ditch puddles
    rnd = random.Random(5)
    for x in (-44, -33, -21, 18, 27, 39, 50, -12):
        side = rnd.choice((-1, 1))
        c, t, n = road_frame(x)
        p = c + n * (7.4 * side)
        z = terrain_h(p.x, p.y)
        ring = puddle_ring(p.x, p.y, z + 0.12, rnd.uniform(1.0, 2.2), rnd.uniform(0.45, 0.7),
                           math.atan2(t.y, t.x), 300 + seed, 20)
        mb.add(ring, [tuple(range(len(ring)))], 0)
        seed += 1
    # crater bottom water
    cx, cy, cr = CRATER
    ring = puddle_ring(cx + 0.2, cy - 0.1, terrain_h(cx, cy) + 0.32, cr * 0.42, cr * 0.36, 0.4, 400, 20)
    mb.add(ring, [tuple(range(len(ring)))], 0)
    return mb.obj('ENV_puddles', coll, [mats['ENV_water']])


# ---------------- apron (concrete yard) ----------------
def build_apron(coll, mats, rnd):
    mb = MB()
    cx, cy, cr = CRATER
    S = 4.0
    gap = 0.035
    x0, y0, x1, y1 = APRON
    pieces = []
    nxp = int(round((x1 - x0) / S))
    nyp = int(round((y1 - y0) / S))
    for i in range(nxp):
        for j in range(nyp):
            px, py = x0 + (i + 0.5) * S, y0 + (j + 0.5) * S
            dc = math.hypot(px - cx, py - cy)
            if dc < cr * 1.6:
                # broken slab: pinwheel split, pieces tilted up/away from blast
                for frag in pinwheel(px, py, S - gap, rnd):
                    fc = Vector((sum(p[0] for p in frag) / 4, sum(p[1] for p in frag) / 4))
                    r = (fc - Vector((cx, cy))).length
                    if r < cr * 1.05:
                        continue
                    pieces.append(('frag', frag, r))
                continue
            if rnd.random() < 0.05 and abs(px) > 7:
                continue  # missing slab, dirt shows
            pieces.append(('slab', (px, py), None))
    for kind, data, r in pieces:
        if kind == 'slab':
            px, py = data
            h = S - gap
            tilt = (rnd.uniform(-0.006, 0.006), rnd.uniform(-0.006, 0.006))
            z0 = rnd.uniform(-0.012, 0.008)
            if abs(px) < 7 and -6 < py < 4:
                tilt = (0.0, 0.0)
                z0 = 0.0
            slab_with_edges(mb, px, py, h, z0, tilt)
        else:
            frag = data
            fc = Vector((sum(p[0] for p in frag) / 4, sum(p[1] for p in frag) / 4, 0))
            away = (fc - Vector((cx, cy, 0))).normalized()
            lift = (1.0 - smoothstep(cr * 1.05, cr * 1.7, r)) * rnd.uniform(0.15, 0.45)
            frag_prism(mb, frag, away, lift, rnd)
    return mb.obj('ENV_apron_slabs', coll, [mats['ENV_concrete_apron']], smooth=20)


def slab_with_edges(mb, px, py, s, z0, tilt):
    fr = [0.0, 0.12, 0.88, 1.0]
    vs = []
    attrs = []
    for b in fr:
        for a in fr:
            x = px - s / 2 + a * s
            y = py - s / 2 + b * s
            z = z0 + (x - px) * tilt[0] + (y - py) * tilt[1]
            vs.append((x, y, z))
            attrs.append(1.0 if (a in (0.0, 1.0) or b in (0.0, 1.0)) else 0.0)
    faces = []
    for j in range(3):
        for i in range(3):
            a = j * 4 + i
            faces.append((a, a + 1, a + 5, a + 4))
    # skirt sides
    base = len(vs)
    ring = [0, 1, 2, 3, 7, 11, 15, 14, 13, 12, 8, 4]
    low = []
    for k in ring:
        x, y, z = vs[k]
        low.append((x, y, z - 0.22))
        attrs.append(1.0)
    vs += low
    m = len(ring)
    for k in range(m):
        a, b = ring[k], ring[(k + 1) % m]
        faces.append((a, base + k, base + (k + 1) % m, b))
    mb.add(vs, faces, 0, attrs={'edge': 0.0})
    off = len(mb.V) - len(vs)
    mb.PA['edge'][off:off + len(vs)] = attrs


def pinwheel(px, py, s, rnd):
    h = s / 2
    C = [(px - h, py - h), (px + h, py - h), (px + h, py + h), (px - h, py + h)]
    c = (px + rnd.uniform(-0.6, 0.6), py + rnd.uniform(-0.6, 0.6))
    E = []
    for k in range(4):
        a, b = C[k], C[(k + 1) % 4]
        t = rnd.uniform(0.3, 0.7)
        E.append((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t))
    frags = []
    for k in range(4):
        frags.append([C[k], E[k], c, E[k - 1]])
    return frags


def frag_prism(mb, frag, away, lift, rnd):
    g = 0.04
    fc = Vector((sum(p[0] for p in frag) / 4, sum(p[1] for p in frag) / 4, 0))
    pts = [Vector((p[0], p[1], 0)) for p in frag]
    pts = [fc + (p - fc) * (1 - g / max(0.3, (p - fc).length)) for p in pts]
    # tilt: lift edge nearest crater, hinge on the far edge
    top = []
    for p in pts:
        k = (p - fc).dot(-away)
        z = 0.0 + max(-0.05, k) * lift + rnd.uniform(-0.01, 0.01)
        top.append((p.x, p.y, z))
    bot = [(x, y, z - 0.2) for x, y, z in top]
    n = len(top)
    faces = [tuple(range(n)), tuple(reversed(range(n, 2 * n)))]
    for k in range(n):
        faces.append((k, n + k, n + (k + 1) % n, (k + 1) % n))
    # fix winding of top (CCW check)
    area = sum(top[k][0] * top[(k + 1) % n][1] - top[(k + 1) % n][0] * top[k][1] for k in range(n))
    if area < 0:
        faces = [tuple(reversed(f)) for f in faces]
    mb.add(top + bot, faces, 0, attrs={'edge': 1.0})


# ---------------- ground ray caster ----------------
class Ground:
    def __init__(self, objs):
        self.trees = []
        dg = bpy.context.evaluated_depsgraph_get()
        for ob in objs:
            ev = ob.evaluated_get(dg)
            me = ev.to_mesh()
            mw = ob.matrix_world
            vs = [mw @ v.co for v in me.vertices]
            ps = [tuple(p.vertices) for p in me.polygons]
            self.trees.append(BVHTree.FromPolygons(vs, ps))
            ev.to_mesh_clear()

    def hit(self, x, y):
        best = None
        for t in self.trees:
            loc, nrm, idx, dist = t.ray_cast(Vector((x, y, 300.0)), Vector((0, 0, -1)))
            if loc is not None and (best is None or loc.z > best[0].z):
                best = (loc, nrm)
        if best is None:
            return Vector((x, y, terrain_h(x, y))), Vector((0, 0, 1))
        return best

    def z(self, x, y):
        return self.hit(x, y)[0].z


# ---------------- ruts (decal strips) ----------------
RUT_PATHS = [
    # tracked APC: road -> hangar door
    ([(21.0, -11.0), (20.5, -6.0), (19.5, 0.0), (20.5, 6.0), (24.0, 11.0), (30.0, 13.0)], 2.3, 0.45),
    # truck: road shoulder -> booth / truck slot
    ([(5.0, -9.6), (14.0, -8.8), (24.0, -8.4), (34.0, -8.3)], 1.9, 0.32),
    # wheels across dirt west of apron to B1
    ([(-9.0, -10.0), (-16.0, -6.0), (-19.0, 3.0), (-21.0, 12.0), (-22.0, 19.0)], 1.8, 0.3),
    # south shoulder to wreck
    ([(-10.0, -19.6), (-20.0, -20.2), (-27.0, -21.0), (-33.0, -21.8)], 1.7, 0.3),
]


def catmull(pts, n=8):
    P = [Vector((p[0], p[1], 0)) for p in pts]
    P = [P[0] * 2 - P[1]] + P + [P[-1] * 2 - P[-2]]
    out = []
    for i in range(1, len(P) - 2):
        p0, p1, p2, p3 = P[i - 1], P[i], P[i + 1], P[i + 2]
        for k in range(n):
            t = k / n
            t2, t3 = t * t, t * t * t
            out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2 +
                              (-p0 + 3 * p1 - 3 * p2 + p3) * t3))
    out.append(P[-2])
    return out


def build_ruts(coll, mats, ground):
    mb = MB()
    uv = []
    for pts, gauge, tw in RUT_PATHS:
        cps = catmull(pts, 10)
        for side in (-1, 1):
            vs = []
            s = 0.0
            for k, p in enumerate(cps):
                if k:
                    s += (p - cps[k - 1]).length
                t = (cps[min(k + 1, len(cps) - 1)] - cps[max(k - 1, 0)]).normalized()
                n = Vector((-t.y, t.x, 0))
                c = p + n * side * gauge / 2
                for u in (-0.5, 0.0, 0.5):
                    q = c + n * u * tw
                    vs.append((q.x, q.y, ground.z(q.x, q.y) + 0.018))
                    uv.append((u + 0.5, s))
            faces = []
            for k in range(len(cps) - 1):
                a = k * 3
                faces += [(a, a + 1, a + 4, a + 3), (a + 1, a + 2, a + 5, a + 4)]
            mb.add(vs, faces, 0)
    return mb.obj('ENV_ruts_decal', coll, [mats['ENV_decal_rut']], smooth=180, uv=uv)

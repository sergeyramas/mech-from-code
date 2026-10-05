# Heavy mech v3 - procedural library: list-based mesh builder, faceted riveted plates,
# disc joints, pistons, cables, greebles + EEVEE paint materials driven by geometry attributes.
import bpy, bmesh, math, random
from mathutils import Vector, Matrix, Euler, Quaternion

D2R = math.radians
MATS = ['armor', 'armor_dark', 'red', 'metal', 'steel', 'brass', 'hole', 'glass', 'glow', 'muzzle', 'rubber', 'joint']
PREFIX = 'MECH_'


# ---------------- transforms ----------------
def T(v):
    return Matrix.Translation(Vector(v))


def rot(rx=0.0, ry=0.0, rz=0.0):
    return Euler((D2R(rx), D2R(ry), D2R(rz)), 'XYZ').to_matrix().to_4x4()


def S(s):
    if isinstance(s, (int, float)):
        return Matrix.Scale(s, 4)
    return Matrix.Diagonal((s[0], s[1], s[2], 1.0))


def P(c, r=None):
    """placement: translation + euler degrees (tuple) or Matrix"""
    if r is None:
        return T(c)
    if isinstance(r, Matrix):
        return T(c) @ r.to_4x4()
    return T(c) @ rot(*r)


def frame(n, up=(0, 0, 1), spin=0.0):
    """rotation with local Z -> n and local Y -> up (projected)"""
    z = Vector(n).normalized()
    u = Vector(up).normalized()
    if abs(u.dot(z)) > 0.97:
        u = Vector((0, 1, 0)) if abs(z.y) < 0.9 else Vector((0, 0, 1))
    y = (u - z * u.dot(z)).normalized()
    x = y.cross(z)
    m = Matrix((x, y, z)).transposed().to_4x4()
    if spin:
        m = m @ rot(0, 0, spin)
    return m


def PF(c, n, up=(0, 0, 1), spin=0.0):
    return T(c) @ frame(n, up, spin)


def seg_rot(d, ref=(0, 0, 1)):
    """rotation taking local ref axis onto direction d (minimal rotation)"""
    return Vector(ref).rotation_difference(Vector(d).normalized()).to_matrix().to_4x4()


def nrm(x, y, z):
    return Vector((x, y, z)).normalized()


# ---------------- 2D outlines ----------------
def outline(w, h, cut):
    """rectangle w*h with corner cuts. cut=(cx,cy) or [(cx,cy)]*4 for BL,BR,TR,TL. CCW."""
    if not isinstance(cut[0], (tuple, list)):
        cut = [cut] * 4
    hw, hh = w / 2, h / 2
    (bx0, by0), (bx1, by1), (tx1, ty1), (tx0, ty0) = [(min(cx, hw), min(cy, hh)) for cx, cy in cut]
    pts = [(-hw + bx0, -hh), (hw - bx1, -hh), (hw, -hh + by1), (hw, hh - ty1),
           (hw - tx1, hh), (-hw + tx0, hh), (-hw, hh - ty0), (-hw, -hh + by0)]
    out = []
    for p in pts:
        if not out or abs(p[0] - out[-1][0]) > 1e-5 or abs(p[1] - out[-1][1]) > 1e-5:
            out.append(p)
    while len(out) > 3 and abs(out[0][0] - out[-1][0]) < 1e-5 and abs(out[0][1] - out[-1][1]) < 1e-5:
        out.pop()
    return out


def inset(pts, d):
    n = len(pts)
    out = []
    for i in range(n):
        ax, ay = pts[i - 1]
        bx, by = pts[i]
        cx, cy = pts[(i + 1) % n]
        e1 = (bx - ax, by - ay)
        l1 = math.hypot(*e1) or 1e-9
        n1 = (-e1[1] / l1, e1[0] / l1)
        e2 = (cx - bx, cy - by)
        l2 = math.hypot(*e2) or 1e-9
        n2 = (-e2[1] / l2, e2[0] / l2)
        k = d / max(1 + n1[0] * n2[0] + n1[1] * n2[1], 0.2)
        out.append((bx + (n1[0] + n2[0]) * k, by + (n1[1] + n2[1]) * k))
    return out


def _area(pts):
    a = 0
    for i in range(len(pts)):
        x0, y0 = pts[i - 1]
        x1, y1 = pts[i]
        a += x0 * y1 - x1 * y0
    return a / 2


# rivet template (unit radius dome, no bottom)
_RV, _RF = [], []
for _i in range(6):
    _a = 2 * math.pi * _i / 6
    _RV.append((math.cos(_a), math.sin(_a), 0.0))
for _i in range(6):
    _a = 2 * math.pi * (_i + 0.5) / 6
    _RV.append((0.62 * math.cos(_a), 0.62 * math.sin(_a), 0.55))
_RV.append((0, 0, 0.78))
for _i in range(6):
    _j = (_i + 1) % 6
    _RF.append((_i, _j, 6 + _i))
    _RF.append((_j, 6 + _j, 6 + _i))
    _RF.append((6 + _i, 6 + _j, 12))


class Part:
    def __init__(self, name, M=None):
        self.name = name
        self.M = M.copy() if M is not None else Matrix.Identity(4)
        self.V, self.F, self.FM, self.FW, self.VP = [], [], [], [], []
        self._stack = []

    def push(self, m):
        self._stack.append(self.M)
        self.M = self.M @ m

    def pop(self):
        self.M = self._stack.pop()

    def W(self, p):
        """design-space point -> world"""
        return self.M @ Vector(p)

    # ---- core ----
    def add(self, verts, faces, mat, m=None, wear=0.0):
        W = self.M @ m if m is not None else self.M
        base = len(self.V)
        pts = [W @ Vector(v) for v in verts]
        zs = [p.z for p in pts]
        z0 = min(zs)
        dz = max(max(zs) - z0, 1e-6)
        self.V.extend(pts)
        self.VP.extend([(p.z - z0) / dz for p in pts])
        mi = MATS.index(mat)
        lw = isinstance(wear, (list, tuple))
        for k, f in enumerate(faces):
            self.F.append(tuple(base + i for i in f))
            self.FM.append(mi)
            self.FW.append(wear[k] if lw else wear)

    def add_bm(self, bm, mat, m=None, wear_faces=None, wear_default=0.0):
        bm.verts.index_update()
        verts = [v.co.copy() for v in bm.verts]
        wf = wear_faces or set()
        faces, wear = [], []
        for f in bm.faces:
            faces.append(tuple(v.index for v in f.verts))
            wear.append(1.0 if f in wf else wear_default)
        self.add(verts, faces, mat, m, wear)
        bm.free()

    # ---- basic primitives (m = design-space placement matrix) ----
    def box(self, m, size, mat='armor', bev=0.03, taper=None):
        bm = bmesh.new()
        bmesh.ops.create_cube(bm, size=1.0)
        for v in bm.verts:
            v.co = Vector((v.co.x * size[0], v.co.y * size[1], v.co.z * size[2]))
        if taper:
            for v in bm.verts:
                if v.co.z > 0:
                    v.co.x *= taper[0]
                    v.co.y *= taper[1]
        wf = set()
        if bev > 0:
            res = bmesh.ops.bevel(bm, geom=list(bm.edges), offset=bev, offset_type='OFFSET', segments=1,
                                  profile=0.5, affect='EDGES', clamp_overlap=True)
            wf = set(res['faces'])
        self.add_bm(bm, mat, m, wf)

    def cyl(self, m, r, depth, mat='metal', n=16, r2=None, bev=0.0, caps=True):
        bm = bmesh.new()
        bmesh.ops.create_cone(bm, cap_ends=caps, cap_tris=False, segments=n, radius1=r,
                              radius2=r if r2 is None else r2, depth=depth)
        wf = set()
        if bev > 0:
            es = [e for e in bm.edges if abs(e.verts[0].co.z - e.verts[1].co.z) < 1e-5
                  and abs(abs(e.verts[0].co.z) - depth / 2) < 1e-4]
            res = bmesh.ops.bevel(bm, geom=es, offset=bev, offset_type='OFFSET', segments=1, profile=0.5,
                                  affect='EDGES', clamp_overlap=True)
            wf = set(res['faces'])
        self.add_bm(bm, mat, m, wf)

    def ring(self, m, ro, ri, depth, mat='metal', n=24, wear_top=0.7):
        verts, faces, wear = [], [], []
        for rr, z in ((ro, -depth / 2), (ro, depth / 2), (ri, depth / 2), (ri, -depth / 2)):
            for i in range(n):
                a = 2 * math.pi * i / n
                verts.append((rr * math.cos(a), rr * math.sin(a), z))
        for i in range(n):
            j = (i + 1) % n
            faces += [(i, j, n + j, n + i), (n + i, n + j, 2 * n + j, 2 * n + i),
                      (2 * n + i, 2 * n + j, 3 * n + j, 3 * n + i), (3 * n + i, 3 * n + j, j, i)]
            wear += [0.2, wear_top, 0.0, 0.0]
        self.add(verts, faces, mat, m, wear)

    def rivet(self, m, r=0.032, mat='brass'):
        self.add(_RV, _RF, mat, m @ S(r), 0.4)

    def bolt(self, m, r=0.04, h=0.05, mat='metal'):
        self.cyl(m @ T((0, 0, h / 2)), r, h, mat=mat, n=6)

    def gear(self, m, r, th, teeth=12, mat='metal', dt=0.13, hub=True):
        bm = bmesh.new()
        segs = teeth * 4
        bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=True, segments=segs, radius1=r, radius2=r, depth=th)
        step = 2 * math.pi / segs
        for v in bm.verts:
            if v.co.xy.length < r * 0.5:
                continue
            k = int(round(math.atan2(v.co.y, v.co.x) / step)) % 4
            if k in (2, 3):
                v.co.x *= (1 - dt)
                v.co.y *= (1 - dt)
        self.add_bm(bm, mat, m, None, 0.35)
        if hub:
            self.cyl(m, r * 0.42, th * 1.7, mat='metal', n=14, bev=0.012)
            for i in range(6):
                a = i * math.pi / 3
                self.bolt(m @ T((math.cos(a) * r * 0.6, math.sin(a) * r * 0.6, th / 2)), r * 0.06, 0.03)

    # ---- faceted plate with chamfer + rivet ring ----
    def pslab(self, m, o, t, cham=0.04, mat='armor', bottom=False, side_wear=0.45):
        """prism from CCW convex polygon o (local XY), base z=0, chamfered top at z=t"""
        n = len(o)
        xs = [p[0] for p in o]
        ys = [p[1] for p in o]
        ch = min(cham, t * 0.7, (max(xs) - min(xs)) * 0.2, (max(ys) - min(ys)) * 0.2)
        if ch > 0.002:
            i2 = inset(o, ch)
            verts = [(x, y, 0) for x, y in o] + [(x, y, t - ch) for x, y in o] + [(x, y, t) for x, y in i2]
            top0 = 2 * n
        else:
            verts = [(x, y, 0) for x, y in o] + [(x, y, t) for x, y in o]
            top0 = n
        faces, wear = [], []
        for i in range(n):
            j = (i + 1) % n
            faces.append((i, j, n + j, n + i))
            wear.append(side_wear)
            if top0 == 2 * n:
                faces.append((n + i, n + j, 2 * n + j, 2 * n + i))
                wear.append(1.0)
        faces.append(tuple(range(top0, top0 + n)))
        wear.append(0.0)
        if bottom:
            faces.append(tuple(reversed(range(n))))
            wear.append(0.0)
        self.add(verts, faces, mat, m, wear)
        return o

    def slab(self, m, w, h, t, cut=(0, 0), cham=0.04, mat='armor', bottom=False):
        return self.pslab(m, outline(w, h, cut), t, cham, mat, bottom)

    def pframe(self, m, outer, inner, t, mat='armor', cham=0.03):
        """frame between two CCW polygons with equal vertex count (outer, inner), base z=0, top z=t"""
        n = len(outer)
        ch = min(cham, t * 0.5)
        oi = inset(outer, ch)
        ii = inset(inner, -ch)
        verts = ([(x, y, 0) for x, y in outer] + [(x, y, t - ch) for x, y in outer] + [(x, y, t) for x, y in oi] +
                 [(x, y, t) for x, y in ii] + [(x, y, t - ch) for x, y in inner] + [(x, y, 0) for x, y in inner])
        faces, wear = [], []
        for i in range(n):
            j = (i + 1) % n
            for k, wv in ((0, 0.45), (1, 1.0), (2, 0.0), (3, 1.0), (4, 0.3)):
                a, b = k * n, (k + 1) * n
                faces.append((a + i, a + j, b + j, b + i))
                wear.append(wv)
        self.add(verts, faces, mat, m, wear)

    def rivet_ring(self, m, poly, margin, z, spacing=0.22, r=0.032, mat='brass'):
        p = inset(poly, margin)
        if _area(p) < 0.02 or _area(p) > _area(poly):
            return
        n = len(p)
        for i in range(n):
            a = Vector((p[i][0], p[i][1], z))
            b = Vector((p[(i + 1) % n][0], p[(i + 1) % n][1], z))
            L = (b - a).length
            if L < 0.03:
                continue
            k = max(1, int(round(L / spacing)))
            for s in range(k):
                self.rivet(m @ T(a + (b - a) * (s / k)), r, mat)

    def plate(self, m, w, h, t=0.1, cut=None, cham=0.035, mat='armor', rivets=True, rs=0.2, rm=None,
              rr=0.032, layer=0, seed=None, rmat='brass'):
        """m: placement with local Z = outward normal. base at z=0."""
        if cut is None:
            k = min(w, h) * 0.2
            cut = (k, k)
        o = self.slab(m, w, h, t, cut, cham, mat)
        if rivets:
            mg = rm if rm is not None else max(0.065, cham + 0.045)
            self.rivet_ring(m, o, mg, t, rs, rr, rmat)
        if layer > 0 and w > 0.45 and h > 0.45:
            rnd = random.Random(seed if seed is not None else len(self.V))
            w2 = w * rnd.uniform(0.5, 0.72)
            h2 = h * rnd.uniform(0.42, 0.62)
            ox = rnd.uniform(-1, 1) * (w - w2) * 0.35
            oy = (h - h2) * rnd.uniform(-0.15, 0.4)
            k2 = min(w2, h2) * rnd.choice((0.12, 0.2, 0.3))
            mat2 = mat
            if mat == 'armor' and rnd.random() < 0.3:
                mat2 = 'armor_dark'
            self.plate(m @ T((ox, oy, t)), w2, h2, t * 0.75, (k2, k2), cham * 0.8, mat2, rivets, rs * 0.85,
                       None, rr * 0.9, layer - 1, rnd.randint(0, 99999), rmat)

    def hexplate(self, m, w, h, t=0.1, point=0.28, **kw):
        """hexagon with points up/down (point = fraction of h cut at the ends)"""
        return self.plate(m, w, h, t, cut=(w / 2, h * point), **kw)

    # ---- mechanical ----
    def disc(self, m, r, th=0.22, mat='metal', bolts=8, rim='armor_dark', teeth=0, hub=0.16, face='joint'):
        """round joint disc, local Z = outward axis, base at z=0"""
        if teeth:
            self.gear(m @ T((0, 0, th / 2)), r, th, teeth=teeth, mat=mat, dt=0.06, hub=False)
        else:
            self.cyl(m @ T((0, 0, th / 2)), r, th, mat=mat, n=32, bev=0.025)
        self.ring(m @ T((0, 0, th + 0.035)), r * 0.97, r * 0.76, 0.07, mat=face, n=32)
        self.ring(m @ T((0, 0, th + 0.075)), r * 0.93, r * 0.88, 0.02, mat=rim, n=32)
        self.cyl(m @ T((0, 0, th + 0.02)), r * 0.76, 0.04, mat=face, n=28)
        self.ring(m @ T((0, 0, th + 0.045)), r * 0.7, r * 0.66, 0.025, mat=rim, n=28)
        self.ring(m @ T((0, 0, th + 0.045)), r * 0.5, r * 0.46, 0.025, mat=rim, n=24)
        self.cyl(m @ T((0, 0, th + hub * 0.6)), r * 0.38, hub, mat='metal', n=20, bev=min(0.02, hub * 0.2))
        self.ring(m @ T((0, 0, th + hub)), r * 0.3, r * 0.18, 0.06, mat='steel', n=16)
        self.cyl(m @ T((0, 0, th + hub - 0.01)), r * 0.18, 0.05, mat='hole', n=12)
        for i in range(bolts):
            a = 2 * math.pi * i / bolts
            self.bolt(m @ T((math.cos(a) * r * 0.57, math.sin(a) * r * 0.57, th + 0.04)), r * 0.055, 0.05,
                      mat='brass' if i % 2 else 'metal')
        for i in range(bolts * 2):
            a = 2 * math.pi * (i + 0.5) / (bolts * 2)
            self.rivet(m @ T((math.cos(a) * r * 0.865, math.sin(a) * r * 0.865, th + 0.07)), r * 0.035)

    def drum(self, m, r, length, ribs=4, mat='metal'):
        """ribbed cylinder along local Z centred"""
        self.cyl(m, r, length, mat=mat, n=28, bev=0.02)
        for i in range(ribs):
            z = -length / 2 + length * (i + 0.5) / ribs
            self.ring(m @ T((0, 0, z)), r * 1.08, r * 0.9, length / ribs * 0.35, mat='armor_dark', n=28)

    def piston(self, p1, p2, r, mat='metal'):
        p1, p2 = Vector(p1), Vector(p2)
        d = p2 - p1
        L = d.length
        R = seg_rot(d)
        dn = d.normalized()
        self.cyl(P(p1 + dn * L * 0.3, R), r, L * 0.6, mat=mat, n=14, bev=0.015)
        self.ring(P(p1 + dn * L * 0.6, R), r * 1.18, r * 0.5, 0.07, mat='armor_dark', n=14)
        self.cyl(P(p1 + dn * L * 0.78, R), r * 0.55, L * 0.44, mat='steel', n=12)
        side = R @ rot(0, 90, 0)
        self.cyl(P(p1, side), r * 1.15, r * 1.7, mat='armor_dark', n=12, bev=0.01)
        self.cyl(P(p2, side), r * 1.05, r * 1.7, mat='armor_dark', n=12, bev=0.01)
        self.cyl(P(p1, side), r * 0.4, r * 2.1, mat='steel', n=8)
        self.cyl(P(p2, side), r * 0.4, r * 2.1, mat='steel', n=8)

    def pipe(self, p1, p2, r=0.05, mat='metal', clamps=True):
        p1, p2 = Vector(p1), Vector(p2)
        d = p2 - p1
        R = seg_rot(d)
        self.cyl(P((p1 + p2) / 2, R), r, d.length, mat=mat, n=8)
        if clamps:
            for pp in (p1, p2):
                self.cyl(P(pp, R), r * 1.6, r * 2.2, mat='steel', n=8)

    def cable(self, p0, p1, p2, p3, r=0.05, mat='rubber', steps=14, n=6):
        p0, p1, p2, p3 = (Vector(x) for x in (p0, p1, p2, p3))
        pts = []
        for k in range(steps + 1):
            t = k / steps
            u = 1 - t
            pts.append(p0 * u ** 3 + p1 * 3 * u * u * t + p2 * 3 * u * t * t + p3 * t ** 3)
        verts, faces = [], []
        tk = (pts[1] - pts[0]).normalized()
        N = tk.orthogonal().normalized()
        for k, p in enumerate(pts):
            tk = (pts[min(k + 1, steps)] - pts[max(k - 1, 0)]).normalized()
            N = (N - tk * N.dot(tk)).normalized()
            B = tk.cross(N)
            for i in range(n):
                a = 2 * math.pi * i / n
                verts.append(p + (N * math.cos(a) + B * math.sin(a)) * r)
        for k in range(steps):
            for i in range(n):
                j = (i + 1) % n
                faces.append((k * n + i, k * n + j, (k + 1) * n + j, (k + 1) * n + i))
        self.add(verts, faces, mat, None, 0.0)
        for pp, dd in ((pts[0], pts[1] - pts[0]), (pts[-1], pts[-1] - pts[-2])):
            self.cyl(P(pp, seg_rot(dd)), r * 1.5, r * 2.5, mat='steel', n=8)

    def grille(self, m, w, h, n=6, depth=0.08, mat='metal'):
        """vent on local XY at z=0 facing +Z"""
        self.box(m @ T((0, 0, -depth / 2 + 0.005)), (w, h, depth), mat='hole', bev=0.0)
        for side in (-1, 1):
            self.box(m @ T((side * (w / 2 + 0.03), 0, 0.02)), (0.06, h + 0.12, 0.06), mat='metal', bev=0.012)
            self.box(m @ T((0, side * (h / 2 + 0.03), 0.02)), (w + 0.12, 0.06, 0.06), mat='metal', bev=0.012)
        for i in range(n):
            y = -h / 2 + h * (i + 0.5) / n
            self.box(m @ T((0, y, -0.01)) @ rot(25, 0, 0), (w * 0.98, h / n * 0.55, 0.025), mat=mat, bev=0.0)

    def greebles(self, m, w, h, count, seed=1, depth=0.12, mats=('metal', 'metal', 'armor_dark', 'steel')):
        rnd = random.Random(seed)
        for _ in range(count):
            kind = rnd.random()
            x = rnd.uniform(-w / 2, w / 2) * 0.9
            y = rnd.uniform(-h / 2, h / 2) * 0.9
            mm = m @ T((x, y, 0))
            mat = rnd.choice(mats)
            if kind < 0.38:
                sx = min(rnd.uniform(0.08, 0.32), w * 0.4)
                sy = min(rnd.uniform(0.06, 0.26), h * 0.4)
                sz = rnd.uniform(0.03, depth)
                self.box(mm @ T((0, 0, sz / 2)), (sx, sy, sz), mat=mat, bev=0.008)
            elif kind < 0.55:
                rr = rnd.uniform(0.03, 0.08)
                hh = rnd.uniform(0.03, depth)
                self.cyl(mm @ T((0, 0, hh / 2)), rr, hh, mat=mat, n=10, bev=0.006)
            elif kind < 0.7:
                for k in range(rnd.randint(2, 4)):
                    self.bolt(mm @ T((k * 0.07, 0, 0)), 0.025, 0.035, mat='steel' if k % 2 else 'metal')
            elif kind < 0.85:
                L = min(rnd.uniform(0.2, 0.6), max(w, h) * 0.6)
                rr = rnd.uniform(0.02, 0.045)
                self.cyl(mm @ T((0, 0, rr)) @ rot(0, 90, rnd.choice((0, 90))), rr, L, mat=mat, n=8)
            else:
                sx = min(rnd.uniform(0.15, 0.3), w * 0.5)
                sy = min(rnd.uniform(0.12, 0.25), h * 0.5)
                self.box(mm @ T((0, 0, 0.02)), (sx, sy, 0.04), mat='metal', bev=0.006)
                for k in range(3):
                    self.box(mm @ T((0, -sy / 2 + sy * (k + 0.5) / 3, 0.045)), (sx * 0.85, sy / 3 * 0.45, 0.02),
                             mat='hole', bev=0.0)

    def tube(self, m, r, depth, rim='brass'):
        """launcher tube along local -Z (open end at z=0 facing +Z)"""
        self.cyl(m @ T((0, 0, -depth / 2)), r * 1.06, depth, mat='metal', n=20, caps=False)
        self.ring(m @ T((0, 0, 0.03)), r * 1.12, r * 0.86, 0.1, mat=rim, n=20)
        self.ring(m @ T((0, 0, -0.06)), r * 0.88, r * 0.84, 0.12, mat='metal', n=20)
        self.cyl(m @ T((0, 0, -depth / 2)), r * 0.86, depth, mat='hole', n=20)
        self.cyl(m @ T((0, 0, -depth * 0.62)), r * 0.55, 0.3, mat='metal', n=12, r2=0.02)

    def barrel(self, m, L, r, ribs_len=1.0, ribs=9):
        """barrel along local +Z from z=0 (breech) to z=L (muzzle)"""
        self.cyl(m @ T((0, 0, L / 2)), r, L, mat='metal', n=20)
        self.cyl(m @ T((0, 0, ribs_len / 2 + 0.05)), r * 1.45, ribs_len + 0.1, mat='metal', n=20, bev=0.015)
        for i in range(ribs):
            z = 0.1 + ribs_len * (i + 0.5) / ribs
            self.ring(m @ T((0, 0, z)), r * 1.75, r * 1.3, ribs_len / ribs * 0.42, mat='metal', n=20)
        for z in (ribs_len + 0.25, L * 0.72):
            self.ring(m @ T((0, 0, z)), r * 1.35, r * 0.9, 0.09, mat='armor_dark', n=20)
        self.cyl(m @ T((0, 0, L - 0.18)), r * 1.55, 0.36, mat='metal', n=20, bev=0.02)
        self.ring(m @ T((0, 0, L + 0.01)), r * 1.5, r * 0.8, 0.04, mat='metal', n=20)
        self.ring(m @ T((0, 0, L - 0.02)), r * 0.82, r * 0.7, 0.1, mat='metal', n=16)
        self.cyl(m @ T((0, 0, L - 0.03)), r * 0.72, 0.1, mat='hole', n=16)
        for k in range(4):
            a = k * 90
            self.box(m @ T((0, 0, L - 0.2)) @ rot(0, 0, a) @ T((r * 1.5, 0, 0)), (0.05, 0.1, 0.18),
                     mat='hole', bev=0.0)


# ---------------- polygon utils + plated hulls ----------------
def clip(poly, a, b, c):
    """keep part of convex polygon with a*x+b*y <= c"""
    out = []
    n = len(poly)
    for i in range(n):
        P = poly[i]
        Q = poly[(i + 1) % n]
        dp = a * P[0] + b * P[1] - c
        dq = a * Q[0] + b * Q[1] - c
        if dp <= 0:
            out.append(P)
        if (dp <= 0) != (dq <= 0):
            t = dp / (dp - dq)
            out.append((P[0] + (Q[0] - P[0]) * t, P[1] + (Q[1] - P[1]) * t))
    return out


def simplify(poly, eps=0.02):
    out = []
    n = len(poly)
    for i in range(n):
        a = Vector(poly[i - 1])
        b = Vector(poly[i])
        c = Vector(poly[(i + 1) % n])
        if (b - a).length < eps:
            continue
        e1 = (b - a).normalized()
        e2 = (c - b)
        if e2.length > 1e-6 and abs(e1.x * e2.normalized().y - e1.y * e2.normalized().x) < 0.01:
            continue
        out.append((b.x, b.y))
    return out


def centroid2(poly):
    return (sum(p[0] for p in poly) / len(poly), sum(p[1] for p in poly) / len(poly))


def cut_corners(poly, d, rnd, prob=0.75):
    out = []
    n = len(poly)
    for i in range(n):
        P = Vector(poly[i])
        A = Vector(poly[i - 1])
        B = Vector(poly[(i + 1) % n])
        e1 = A - P
        e2 = B - P
        if e1.length < 1e-4 or e2.length < 1e-4:
            continue
        sharp = e1.normalized().dot(e2.normalized()) > -0.8
        if sharp and d > 0 and rnd.random() < prob:
            k1 = min(d * rnd.uniform(0.55, 1.45), e1.length * 0.36)
            k2 = min(d * rnd.uniform(0.55, 1.45), e2.length * 0.36)
            q1 = P + e1.normalized() * k1
            q2 = P + e2.normalized() * k2
            out.append((q1.x, q1.y))
            out.append((q2.x, q2.y))
        else:
            out.append((P.x, P.y))
    return out


def split_poly(poly, maxs, rnd, ang=9.0, jit=0.17):
    xs = [p[0] for p in poly]
    x0, x1 = min(xs), max(xs)
    nx = max(1, int(round((x1 - x0) / maxs)))
    cols = [poly]
    for i in range(1, nx):
        xc = x0 + (x1 - x0) * (i + rnd.uniform(-jit, jit)) / nx
        th = D2R(rnd.uniform(-ang, ang))
        a, b = math.cos(th), math.sin(th)
        ys = [p[1] for p in poly]
        c = a * xc + b * (min(ys) + max(ys)) / 2
        new = []
        for pc in cols:
            for q in (clip(pc, a, b, c), clip(pc, -a, -b, -c)):
                if len(q) >= 3 and abs(_area(q)) > 1e-3:
                    new.append(q)
        cols = new
    out = []
    for pc in cols:
        ys = [p[1] for p in pc]
        y0, y1 = min(ys), max(ys)
        ny = max(1, int(round((y1 - y0) / maxs)))
        pieces = [pc]
        for i in range(1, ny):
            yc = y0 + (y1 - y0) * (i + rnd.uniform(-jit, jit)) / ny
            th = D2R(rnd.uniform(-ang, ang))
            a, b = math.sin(th), math.cos(th)
            xs2 = [p[0] for p in pc]
            c = a * (min(xs2) + max(xs2)) / 2 + b * yc
            new = []
            for q0 in pieces:
                for q in (clip(q0, a, b, c), clip(q0, -a, -b, -c)):
                    if len(q) >= 3 and abs(_area(q)) > 1e-3:
                        new.append(q)
            pieces = new
        out += pieces
    return out


def hull_faces(pts, merge_deg=1.0):
    bm = bmesh.new()
    vs = [bm.verts.new(Vector(p)) for p in pts]
    res = bmesh.ops.convex_hull(bm, input=vs, use_existing_faces=False)
    kill = list({g for g in res['geom_interior'] + res['geom_unused'] if isinstance(g, bmesh.types.BMVert) and g.is_valid})
    if kill:
        bmesh.ops.delete(bm, geom=kill, context='VERTS')
    bmesh.ops.dissolve_limit(bm, angle_limit=D2R(merge_deg), verts=bm.verts[:], edges=bm.edges[:])
    bm.normal_update()
    faces = []
    for f in bm.faces:
        faces.append(([v.co.copy() for v in f.verts], f.normal.copy()))
    return bm, faces


def rb(x0, x1, y0, y1, z, c=0.0):
    """rectangle ring (with chamfered corners c) at height z"""
    if c <= 0:
        return [(x0, y0, z), (x1, y0, z), (x1, y1, z), (x0, y1, z)]
    c = min(c, (x1 - x0) * 0.45, (y1 - y0) * 0.45)
    return [(x0 + c, y0, z), (x1 - c, y0, z), (x1, y0 + c, z), (x1, y1 - c, z),
            (x1 - c, y1, z), (x0 + c, y1, z), (x0, y1 - c, z), (x0, y0 + c, z)]


def rbx(x, y0, y1, z0, z1, c=0.0):
    """ring in the YZ plane at x (for blocks extruded along X)"""
    return [(x, y, z) for (y, z, _) in rb(y0, y1, z0, z1, 0, c)]


def rby(y, x0, x1, z0, z1, c=0.0):
    """ring in the XZ plane at y"""
    return [(x, y, z) for (x, z, _) in rb(x0, x1, z0, z1, 0, c)]


HULL_DEF = dict(maxs_k=1.0, cut_k=1.0, cut_p=None, tilt_k=1.0, sub_k=1.0, ov_p=0.0, ov=0.07, gap_k=1.0, cham=0.035,
                rs_k=1.0, rr_k=1.0,
                jit=0.17, ang_k=1.0)


def _plate_part_methods():
    def pplate(self, m, poly, t=0.1, cham=0.035, mat='armor', rivets=True, rs=0.21, rr=0.03, sub=False, rnd=None,
               rmat='brass', red=None):
        o = self.pslab(m, poly, t, cham, mat)
        if rivets and abs(_area(poly)) > 0.05:
            self.rivet_ring(m, o, max(0.065, cham + 0.04), t, rs, rr, rmat)
        if red:
            self.stripe(m @ T((0, 0, t)), inset(o, cham + 0.01), red, rnd)
        elif sub and rnd is not None:
            xs = [p[0] for p in poly]
            ys = [p[1] for p in poly]
            w = max(xs) - min(xs)
            h = max(ys) - min(ys)
            if w > 0.5 and h > 0.5:
                k = rnd.uniform(0.12, 0.24) * min(w, h)
                q = inset(poly, k)
                cx, cy = centroid2(q)
                ox = rnd.uniform(-0.3, 0.3) * k
                oy = rnd.uniform(-0.1, 0.6) * k
                q = [((x - cx) * rnd.uniform(0.8, 1.0) + cx + ox, (y - cy) * rnd.uniform(0.75, 1.0) + cy + oy) for x, y in q]
                q = cut_corners(q, min(w, h) * 0.12, rnd, 0.6)
                if len(q) >= 3 and _area(q) > 0.04:
                    mat2 = mat if (mat != 'armor' or rnd.random() > 0.35) else 'armor_dark'
                    self.pplate(m @ T((0, 0, t)), q, t * 0.6, cham * 0.8, mat2, rivets, rs * 0.9, rr * 0.9,
                                False, rnd, rmat)
        return o

    def stripe(self, m, poly, red, rnd=None):
        """diagonal red band(s) decal clipped to polygon; red = (angle_deg, width_frac, offset_frac)"""
        ang, wf, off = red if isinstance(red, tuple) else (52.0, 0.45, 0.0)
        if wf >= 1.0:
            self.pslab(m @ T((0, 0, 0.002)), poly, 0.008, 0.0, 'red', side_wear=0.2)
            return
        xs = [p[0] for p in poly]
        ys = [p[1] for p in poly]
        ext = max(max(xs) - min(xs), max(ys) - min(ys))
        cx, cy = centroid2(poly)
        a, b = math.cos(D2R(ang)), math.sin(D2R(ang))
        c0 = a * cx + b * cy + off * ext
        hw = wf * ext * 0.5
        q = clip(clip(poly, a, b, c0 + hw), -a, -b, -(c0 - hw))
        if len(q) >= 3 and abs(_area(q)) > 0.005:
            self.pslab(m @ T((0, 0, 0.002)), q, 0.008, 0.0, 'red', side_wear=0.2)

    def armor_hull(self, pts, t=0.1, maxs=1.0, gap=0.05, cut=0.13, mat='armor', core='metal', seed=0,
                   rivets=True, rs=0.21, sub_p=0.5, skip=None, dark_p=0.2, red=None, tilt=5.0, avoid=(),
                   core_mesh=True, cut_p=0.7, zj=0.03, ang=9.0):
        H = HULL_DEF
        maxs *= H['maxs_k']
        cut *= H['cut_k']
        cut_p = cut_p if H['cut_p'] is None else H['cut_p']
        tilt *= H['tilt_k']
        sub_p = min(1.0, sub_p * H['sub_k'])
        gap *= H['gap_k']
        ang *= H['ang_k']
        bm, faces = hull_faces(pts)
        if core_mesh:
            self.add_bm(bm, core, None, None, 0.15)
        else:
            bm.free()
        rnd = random.Random(seed)
        for vs, n in faces:
            c = sum(vs, Vector()) / len(vs)
            if skip is not None and skip(n, c):
                continue
            up = (0, 0, 1) if abs(n.z) < 0.85 else (0, 1, 0)
            mf = PF(c, n, up)
            inv = mf.inverted()
            poly = simplify([tuple((inv @ v).xy) for v in vs])
            if len(poly) < 3:
                continue
            if _area(poly) < 0:
                poly = list(reversed(poly))
            for piece in split_poly(poly, maxs, rnd, ang, H['jit']):
                lift = 0.0
                if H['ov_p'] > 0 and rnd.random() < H['ov_p']:
                    q = inset(piece, -H['ov'] * rnd.uniform(0.5, 1.2))
                    lift = t * rnd.uniform(0.4, 0.8)
                else:
                    q = inset(piece, gap / 2 * rnd.uniform(0.7, 1.4))
                if len(q) < 3 or _area(q) < 0.02:
                    continue
                q = cut_corners(q, cut, rnd, cut_p)
                if len(q) < 3 or _area(q) < 0.02:
                    continue
                pc = centroid2(q)
                wc = mf @ Vector((pc[0], pc[1], 0))
                if any((wc - Vector(a)).length < r for a, r in avoid):
                    continue
                tt = t * rnd.uniform(0.8, 1.2)
                mt = mf @ T((pc[0], pc[1], lift + rnd.uniform(0, zj))) @ rot(rnd.uniform(-tilt, tilt),
                                                                    rnd.uniform(-tilt, tilt), 0) @ T((-pc[0], -pc[1], 0))
                pm = mat
                if mat == 'armor' and rnd.random() < dark_p:
                    pm = 'armor_dark'
                rr_ = red(n, wc) if red is not None else None
                if rr_ == 'plate':
                    pm = 'red'
                    rr_ = None
                self.pplate(mt, q, tt, H['cham'], pm, rivets, rs * H['rs_k'], 0.03 * H['rr_k'], rnd.random() < sub_p,
                            rnd, 'brass', rr_)

    def spring(self, m, r, L, turns=7, wire=0.035, mat='steel', n=6):
        steps = turns * 12
        pts = []
        for k in range(steps + 1):
            a = 2 * math.pi * turns * k / steps
            pts.append(Vector((r * math.cos(a), r * math.sin(a), L * k / steps)))
        verts, faces = [], []
        N = Vector((0, 0, 1))
        for k, p in enumerate(pts):
            tk = (pts[min(k + 1, steps)] - pts[max(k - 1, 0)]).normalized()
            Nk = (N - tk * N.dot(tk)).normalized()
            B = tk.cross(Nk)
            for i in range(n):
                a = 2 * math.pi * i / n
                verts.append(p + (Nk * math.cos(a) + B * math.sin(a)) * wire)
        for k in range(steps):
            for i in range(n):
                j = (i + 1) % n
                faces.append((k * n + i, k * n + j, (k + 1) * n + j, (k + 1) * n + i))
        self.add(verts, faces, mat, m, 0.6)

    def hullmesh(self, pts, mat='metal', wear=0.2):
        bm, _ = hull_faces(pts)
        self.add_bm(bm, mat, None, None, wear)

    # ---- v3.1: scale armour (convex 5/6-gon plates, corner rivets, dark mechanics in the gaps) ----
    def rivet_corners(self, m, poly, margin, z, r=0.03, mat='brass', mid=0.55):
        p = inset(poly, margin)
        if len(p) < 3 or _area(p) < 0.01 or _area(p) > _area(poly):
            return
        n = len(p)
        for i in range(n):
            a = Vector((p[i][0], p[i][1], z))
            self.rivet(m @ T(a), r, mat)
            if mid:
                b = Vector((p[(i + 1) % n][0], p[(i + 1) % n][1], z))
                if (b - a).length > mid:
                    self.rivet(m @ T((a + b) / 2), r, mat)

    def scale_plate(self, m, poly, t, mat='armor', rr=0.03, sub=False, rnd=None, red=None, cham=None, subk=None):
        ch = HULL_DEF['cham'] * 1.3 if cham is None else cham
        o = self.pslab(m, poly, t, ch, mat)
        self.rivet_corners(m, o, max(0.06, ch + 0.04), t, rr)
        if red:
            self.stripe(m @ T((0, 0, t)), inset(o, ch + 0.01), red, rnd)
        elif sub and rnd is not None and abs(_area(poly)) > 0.12:
            cx, cy = centroid2(poly)
            if subk:
                k = rnd.uniform(*subk)
                a = 0.0
                ox, oy = 0.0, rnd.uniform(-0.02, 0.04)
            else:
                k = rnd.uniform(0.5, 0.68)
                a = D2R(rnd.uniform(-10, 10))
                ox, oy = rnd.uniform(-0.08, 0.08), rnd.uniform(-0.04, 0.1)
            ca, sa = math.cos(a), math.sin(a)
            q = []
            for x, y in poly:
                x, y = (x - cx) * k, (y - cy) * k
                q.append((cx + ox + x * ca - y * sa, cy + oy + x * sa + y * ca))
            q = convex2(q)
            if len(q) >= 3:
                mat2 = mat if (mat != 'armor' or rnd.random() > 0.4) else 'armor_dark'
                self.pslab(m @ T((0, 0, t)), q, t * 0.6, ch * 0.8, mat2)
                self.rivet_corners(m @ T((0, 0, t)), q, max(0.05, ch * 0.8 + 0.035), t * 0.6, rr * 0.9, mid=0)
        return o

    def scale_hull(self, pts, size=0.62, t=0.1, core_in=0.08, skip=None, avoid=(), seed=0, red=None,
                   sub_p=0.3, dark_p=0.2, mech=0.6, elong=(1.0, 1.3), mat='armor', core='metal', rr=0.03,
                   rk=(0.52, 0.66), blend=0.45, big=None, lift_j=0.035, tilt=4.0, big_subk=None):
        """Cover the convex hull of pts with overlapping convex 5/6-sided scale plates.
        size: centre spacing (float or fn(n, p)); big: fn(n, p) -> True for faces kept as one large plate."""
        rnd = random.Random(seed)
        bm, faces = hull_faces(pts)
        bm.free()
        planes = [(n.copy(), n.dot(vs[0])) for vs, n in faces]
        cen = sum((Vector(p) for p in pts), Vector()) / len(pts)
        # dark core, shrunk so the gaps between plates read deep
        sp_ = []
        for p in pts:
            p = Vector(p)
            d = p - cen
            d.z = 0
            L = d.length
            k = max(0.3, (L - core_in) / L) if L > 1e-6 else 1.0
            sp_.append((cen.x + d.x * k, cen.y + d.y * k, p.z))
        self.hullmesh(sp_, core, 0.12)
        sz = size if callable(size) else (lambda n, p: size)
        tri = []
        for fi, (vs, n) in enumerate(faces):
            cc = sum(vs, Vector()) / len(vs)
            if skip is not None and skip(n, cc):
                continue
            if big is not None and big(n, cc):
                # one large faceted plate on this face
                up = (0, 0, 1) if abs(n.z) < 0.85 else (0, 1, 0)
                mf = PF(cc, n, up)
                inv = mf.inverted()
                poly = simplify([tuple((inv @ v).xy) for v in vs])
                if len(poly) >= 3:
                    if _area(poly) < 0:
                        poly = list(reversed(poly))
                    q = inset(poly, 0.05)
                    q = cut_corners(q, 0.16, rnd, 0.8)
                    if len(q) >= 3 and _area(q) > 0.05:
                        rr_ = red(n, cc) if red is not None else None
                        pm = 'red' if rr_ == 'plate' else mat
                        self.scale_plate(mf, q, t * 1.2, pm, rr, True, rnd, rr_ if rr_ != 'plate' else None,
                                         subk=big_subk)
                continue
            for k in range(1, len(vs) - 1):
                a, b, c3 = vs[0], vs[k], vs[k + 1]
                ar = (b - a).cross(c3 - a).length / 2
                if ar > 1e-5:
                    tri.append((a, b, c3, ar, n))
        A = sum(x[3] for x in tri)
        if A <= 0:
            return
        s0 = sz(Vector((0, 0, 1)), cen)
        ncand = int(A / (s0 * s0) * 30) + 20
        cum = []
        acc_ = 0.0
        for x in tri:
            acc_ += x[3]
            cum.append(acc_)
        cand = []
        import bisect
        for _ in range(ncand):
            r = rnd.random() * A
            a, b, c3, ar, n = tri[min(bisect.bisect_left(cum, r), len(tri) - 1)]
            u, v = rnd.random(), rnd.random()
            if u + v > 1:
                u, v = 1 - u, 1 - v
            p = a + (b - a) * u + (c3 - a) * v
            if any((p - Vector(av)).length < ar_ for av, ar_ in avoid):
                continue
            cand.append((p, n, sz(n, p)))
        acc = []
        for p, n, s in cand:
            if all((p - q).length >= (s + sq) * 0.5 for q, _, sq in acc):
                acc.append((p, n, s))
        for p, n0, s in acc:
            nsum = Vector()
            for (n, d) in planes:
                dist = d - n.dot(p)
                w = max(0.0, 1 - dist / (s * blend))
                if w > 0:
                    nsum += n * (w * w)
            nb = nsum.normalized() if nsum.length > 1e-6 else n0
            up = (0, 0, 1) if abs(nb.z) < 0.85 else (0, 1, 0)
            kk = 6 if rnd.random() < 0.68 else 5
            R = s * rnd.uniform(*rk)
            e = rnd.uniform(*elong)
            a0 = (rnd.choice((0.0, math.pi / 6)) if kk == 6 else math.pi / 2) + rnd.uniform(-0.3, 0.3)
            poly = []
            for i in range(kk):
                a = a0 + 2 * math.pi * i / kk + rnd.uniform(-0.16, 0.16)
                r_ = R * rnd.uniform(0.86, 1.08)
                poly.append((r_ * math.cos(a) / math.sqrt(e), r_ * math.sin(a) * math.sqrt(e)))
            poly = convex2(poly)
            if len(poly) < 3:
                continue
            M = T(p) @ frame(nb, up) @ rot(rnd.uniform(-tilt, tilt), rnd.uniform(-tilt, tilt), 0)
            npl = (M.to_3x3() @ Vector((0, 0, 1))).normalized()
            lift = 0.0
            for x, y in poly:
                w_ = M @ Vector((x, y, 0))
                inside = True
                best = 1e9
                for (n, d) in planes:
                    g = d - n.dot(w_)
                    if g < 0:
                        inside = False
                        break
                    dn = n.dot(npl)
                    if dn > 0.15:
                        best = min(best, g / dn)
                if inside and best < 1e8:
                    lift = max(lift, best)
            if lift > t * 2.2:
                continue
            lift += rnd.uniform(0, lift_j)
            M = T(npl * lift) @ M
            tt = t * rnd.uniform(0.8, 1.25)
            pm = mat
            if mat == 'armor' and rnd.random() < dark_p:
                pm = 'armor_dark'
            rr_ = red(nb, p) if red is not None else None
            if rr_ == 'plate':
                pm = 'red'
                rr_ = None
            self.scale_plate(M, poly, tt, pm, rr, rnd.random() < sub_p, rnd, rr_)
        # dark mechanics living in the gaps (pipes, pistons, bolts on the core)
        nm = int(A / (s0 * s0) * mech)
        for _ in range(nm):
            r = rnd.random() * A
            a, b, c3, ar, n = tri[min(bisect.bisect_left(cum, r), len(tri) - 1)]
            u, v = rnd.random(), rnd.random()
            if u + v > 1:
                u, v = 1 - u, 1 - v
            p = a + (b - a) * u + (c3 - a) * v - n * core_in
            up = (0, 0, 1) if abs(n.z) < 0.85 else (0, 1, 0)
            F = frame(n, up)
            kind = rnd.random()
            mt = rnd.choice(('metal', 'metal', 'steel', 'rubber'))
            if kind < 0.45:
                rr2 = rnd.uniform(0.035, 0.06)
                Lp = rnd.uniform(0.3, 0.7)
                self.cyl(T(p) @ F @ T((0, 0, rr2)) @ rot(90, 0, rnd.uniform(-25, 25)), rr2, Lp, mat=mt, n=8)
            elif kind < 0.7:
                rr2 = rnd.uniform(0.08, 0.14)
                self.cyl(T(p) @ F @ T((0, 0, 0.03)), rr2, 0.06, mat='metal', n=12, bev=0.01)
                self.cyl(T(p) @ F @ T((0, 0, 0.07)), rr2 * 0.45, 0.04, mat='steel', n=8)
            elif kind < 0.85:
                self.box(T(p) @ F @ T((0, 0, 0.04)), (rnd.uniform(0.1, 0.25), rnd.uniform(0.08, 0.2), 0.08),
                         mat='metal', bev=0.01)
            else:
                for k in range(3):
                    self.bolt(T(p) @ F @ T((0, (k - 1) * 0.08, 0)), 0.03, 0.04, 'steel')

    def bigdisc(self, m, r, th=0.22, hub=0.2, bolts=10, teeth=0):
        """large protruding joint disc: thick drum + housing bezel + stepped concentric rings + hub"""
        if teeth:
            self.gear(m @ T((0, 0, th / 2)), r, th, teeth=teeth, mat='metal', dt=0.05, hub=False)
        else:
            self.cyl(m @ T((0, 0, th / 2)), r, th, mat='metal', n=40, bev=0.03)
        self.ring(m @ T((0, 0, th * 0.35)), r * 1.1, r * 0.98, th * 0.5, mat='armor_dark', n=40)
        z = th
        self.ring(m @ T((0, 0, z + 0.04)), r * 0.98, r * 0.8, 0.08, mat='joint', n=40)
        self.ring(m @ T((0, 0, z + 0.085)), r * 0.95, r * 0.9, 0.02, mat='armor_dark', n=40)
        self.cyl(m @ T((0, 0, z + 0.02)), r * 0.8, 0.04, mat='metal', n=36)
        self.ring(m @ T((0, 0, z + 0.06)), r * 0.74, r * 0.6, 0.08, mat='joint', n=36)
        self.ring(m @ T((0, 0, z + 0.1)), r * 0.7, r * 0.66, 0.02, mat='armor_dark', n=36)
        self.cyl(m @ T((0, 0, z + 0.05)), r * 0.6, 0.06, mat='joint', n=32)
        self.ring(m @ T((0, 0, z + 0.1)), r * 0.52, r * 0.46, 0.06, mat='armor_dark', n=32)
        self.cyl(m @ T((0, 0, z + hub * 0.5 + 0.04)), r * 0.38, hub, mat='metal', n=24, bev=0.025)
        self.ring(m @ T((0, 0, z + hub + 0.05)), r * 0.34, r * 0.22, 0.05, mat='joint', n=20)
        self.ring(m @ T((0, 0, z + hub + 0.07)), r * 0.2, r * 0.12, 0.04, mat='steel', n=16)
        self.cyl(m @ T((0, 0, z + hub + 0.05)), r * 0.12, 0.05, mat='hole', n=12)
        for i in range(bolts):
            a = 2 * math.pi * i / bolts
            self.bolt(m @ T((math.cos(a) * r * 0.53, math.sin(a) * r * 0.53, z + 0.08)), r * 0.05, 0.05,
                      mat='brass' if i % 2 else 'steel')
        for i in range(bolts * 2):
            a = 2 * math.pi * (i + 0.5) / (bolts * 2)
            self.rivet(m @ T((math.cos(a) * r * 0.89, math.sin(a) * r * 0.89, z + 0.08)), r * 0.035)

    def barrel2(self, m, L, r, shroud=0.62):
        """smooth barrel: long shroud with a few bands, step-down, muzzle collar with slots (local +Z)"""
        Ls = L * shroud
        self.cyl(m @ T((0, 0, L / 2)), r, L, mat='metal', n=24, bev=0.01)
        self.cyl(m @ T((0, 0, Ls / 2)), r * 1.42, Ls, mat='metal', n=28, bev=0.025)
        self.cyl(m @ T((0, 0, Ls + 0.06)), r * 1.42, 0.12, mat='metal', n=28, r2=r * 1.05)
        for z in (0.12, Ls * 0.45, Ls - 0.1):
            self.ring(m @ T((0, 0, z)), r * 1.6, r * 1.38, 0.09, mat='armor_dark', n=28)
        self.ring(m @ T((0, 0, Ls * 0.45 + 0.09)), r * 1.5, r * 1.38, 0.03, mat='steel', n=28)
        self.ring(m @ T((0, 0, (Ls + L) * 0.5)), r * 1.22, r * 0.95, 0.07, mat='armor_dark', n=24)
        # muzzle collar
        self.cyl(m @ T((0, 0, L - 0.2)), r * 1.5, 0.4, mat='metal', n=28, bev=0.03)
        self.ring(m @ T((0, 0, L - 0.42)), r * 1.62, r * 1.45, 0.06, mat='armor_dark', n=28)
        self.ring(m @ T((0, 0, L + 0.01)), r * 1.45, r * 0.8, 0.04, mat='metal', n=28)
        self.ring(m @ T((0, 0, L - 0.02)), r * 0.82, r * 0.7, 0.1, mat='metal', n=20)
        self.cyl(m @ T((0, 0, L - 0.03)), r * 0.72, 0.1, mat='hole', n=20)
        for k in range(6):
            self.box(m @ T((0, 0, L - 0.18)) @ rot(0, 0, k * 60) @ T((r * 1.48, 0, 0)), (0.04, 0.08, 0.2),
                     mat='hole', bev=0.0)

    for f in (pplate, stripe, armor_hull, spring, hullmesh, rivet_corners, scale_plate, scale_hull, bigdisc, barrel2):
        setattr(Part, f.__name__, f)


def convex2(pts):
    """2D convex hull, CCW"""
    P_ = sorted(set((round(x, 6), round(y, 6)) for x, y in pts))
    if len(P_) < 3:
        return P_

    def cr(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lo, up = [], []
    for p in P_:
        while len(lo) >= 2 and cr(lo[-2], lo[-1], p) <= 0:
            lo.pop()
        lo.append(p)
    for p in reversed(P_):
        while len(up) >= 2 and cr(up[-2], up[-1], p) <= 0:
            up.pop()
        up.append(p)
    return lo[:-1] + up[:-1]


_plate_part_methods()


# ---------------- materials ----------------
def _n(nt, t, x, y, **kw):
    n = nt.nodes.new(t)
    n.location = (x, y)
    for k, v in kw.items():
        setattr(n, k, v)
    return n


def _i(n, ident):
    return next(s for s in n.inputs if s.identifier == ident)


def _o(n, ident):
    return next(s for s in n.outputs if s.identifier == ident)


def _ramp(nt, x, y, stops, src=None):
    r = _n(nt, 'ShaderNodeValToRGB', x, y)
    el = r.color_ramp.elements
    el[0].position = stops[0][0]
    el[0].color = stops[0][1]
    el[1].position = stops[-1][0]
    el[1].color = stops[-1][1]
    for p, c in stops[1:-1]:
        e = el.new(p)
        e.color = c
    if src is not None:
        nt.links.new(src, _i(r, 'Fac'))
    return _o(r, 'Color')


def _noise(nt, x, y, src, scale, detail=6.0, rough=0.6, dist=0.0):
    n = _n(nt, 'ShaderNodeTexNoise', x, y)
    _i(n, 'Scale').default_value = scale
    _i(n, 'Detail').default_value = detail
    _i(n, 'Roughness').default_value = rough
    _i(n, 'Distortion').default_value = dist
    nt.links.new(src, _i(n, 'Vector'))
    return _o(n, 'Fac')


def _map(nt, x, y, src, scale):
    mp = _n(nt, 'ShaderNodeMapping', x, y)
    _i(mp, 'Scale').default_value = scale
    nt.links.new(src, _i(mp, 'Vector'))
    return _o(mp, 'Vector')


def _math(nt, op, a, b, clamp=True, x=0, y=0):
    m = _n(nt, 'ShaderNodeMath', x, y, operation=op, use_clamp=clamp)
    for k, val in enumerate((a, b)):
        if isinstance(val, (int, float)):
            m.inputs[k].default_value = val
        else:
            nt.links.new(val, m.inputs[k])
    return _o(m, 'Value')


def _mixc(nt, fac, A, B, blend='MIX', x=0, y=0):
    m = _n(nt, 'ShaderNodeMix', x, y, data_type='RGBA', blend_type=blend, clamp_factor=True)
    for ident, val in (('Factor_Float', fac), ('A_Color', A), ('B_Color', B)):
        if isinstance(val, (int, float)):
            _i(m, ident).default_value = val
        elif isinstance(val, tuple):
            _i(m, ident).default_value = val if len(val) == 4 else (*val, 1.0)
        else:
            nt.links.new(val, _i(m, ident))
    return _o(m, 'Result_Color')


def _attr(nt, name, x, y):
    a = _n(nt, 'ShaderNodeAttribute', x, y)
    a.attribute_name = name
    try:
        a.attribute_type = 'GEOMETRY'
    except Exception:
        pass
    return _o(a, 'Fac')


def _newmat(name):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    m.node_tree.nodes.clear()
    return m


def _c(c):
    return (c[0], c[1], c[2], 1.0)


def paint_mat(key, dark, mid, light, edge=(0.34, 0.32, 0.29), rust=1.0, chip=1.0, streak=1.0, rough=0.62,
              white=0.0):
    m = _newmat(PREFIX + key)
    nt = m.node_tree
    out = _n(nt, 'ShaderNodeOutputMaterial', 2000, 0)
    b = _n(nt, 'ShaderNodeBsdfPrincipled', 1700, 0)
    nt.links.new(_o(b, 'BSDF'), _i(out, 'Surface'))
    co = _o(_n(nt, 'ShaderNodeTexCoord', -1800, 0), 'Object')
    pv = _attr(nt, 'pv', -1800, -500)
    wear = _attr(nt, 'wear', -1800, -700)
    # --- camo mottling: large + small blotches
    n1 = _noise(nt, -1400, 600, co, 0.8, 4, 0.55)
    c = _ramp(nt, -1150, 600, [(0.35, _c(dark)), (0.5, _c(mid)), (0.66, _c(light))], n1)
    n1b = _noise(nt, -1400, 400, co, MAT_DEF['blotch_scale'], 3, 0.5, 0.4)
    spots = _ramp(nt, -1150, 400, [(0.5, (0, 0, 0, 1)), (0.6, (1, 1, 1, 1))], n1b)
    c = _mixc(nt, _math(nt, 'MULTIPLY', spots, MAT_DEF['blotch']), c, _c([v * 0.55 for v in dark]), x=-900, y=550)
    n1c = _noise(nt, -1400, 200, co, 14.0, 2, 0.5)
    spots2 = _ramp(nt, -1150, 200, [(0.58, (0, 0, 0, 1)), (0.66, (1, 1, 1, 1))], n1c)
    c = _mixc(nt, _math(nt, 'MULTIPLY', spots2, MAT_DEF['spots']), c, _c(light), x=-750, y=500)
    if white > 0:
        nw = _noise(nt, -1400, 900, co, 3.2, 8, 0.65)
        wm = _ramp(nt, -1150, 900, [(0.56 - 0.1 * white, (0, 0, 0, 1)), (0.6 - 0.1 * white, (1, 1, 1, 1))], nw)
        c = _mixc(nt, wm, c, (0.52, 0.5, 0.45), x=-650, y=700)
    # --- cavity dirt (AO)
    ao = _n(nt, 'ShaderNodeAmbientOcclusion', -1400, 1100)
    _i(ao, 'Distance').default_value = MAT_DEF['ao_dist']
    rao = _ramp(nt, -1150, 1100, [(0.25, (0.03, 0.022, 0.014, 1)), (0.95, (1, 1, 1, 1))], _o(ao, 'AO'))
    c = _mixc(nt, MAT_DEF['ao'], c, rao, 'MULTIPLY', x=-600, y=400)
    # --- grime pooling at the bottom of each panel
    gb = _ramp(nt, -1150, -450, [(0.0, (0.25, 0.2, 0.14, 1)), (0.3, (1, 1, 1, 1))], pv)
    c = _mixc(nt, 0.7, c, gb, 'MULTIPLY', x=-500, y=300)
    # --- rust streaks running down from the top edge / rivet rows
    sm = _map(nt, -1600, -100, co, (26.0, 26.0, 0.7))
    ns = _noise(nt, -1400, -100, sm, 1.6, 4, 0.6)
    sl = _ramp(nt, -1150, -100, [(0.55 - 0.05 * streak, (0, 0, 0, 1)), (0.68, (1, 1, 1, 1))], ns)
    top = _ramp(nt, -1150, -300, [(0.15, (0, 0, 0, 1)), (0.97, (1, 1, 1, 1))], pv)
    nvar = _noise(nt, -1400, -250, co, 2.0, 2, 0.5)
    streakm = _math(nt, 'MULTIPLY', _math(nt, 'MULTIPLY', sl, top), _math(nt, 'MULTIPLY', nvar, 1.6 * streak))
    rustc = _ramp(nt, -1150, -650, [(0.3, (0.035, 0.02, 0.01, 1)), (0.6, (0.085, 0.04, 0.016, 1)),
                                     (0.85, (0.13, 0.06, 0.022, 1))], _noise(nt, -1400, -650, co, 18, 8, 0.7))
    c = _mixc(nt, _math(nt, 'MULTIPLY', streakm, 0.85), c, rustc, x=-400, y=200)
    # --- rust patches (sparse), more near worn edges
    nr = _noise(nt, -1400, -900, co, 2.2, 12, 0.72)
    rlo = 0.66 - 0.06 * rust
    rp = _ramp(nt, -1150, -900, [(rlo, (0, 0, 0, 1)), (rlo + 0.08, (1, 1, 1, 1))], nr)
    rp = _math(nt, 'MAXIMUM', rp, _math(nt, 'MULTIPLY', wear, _math(nt, 'MULTIPLY', nr, 0.9 * rust)))
    c = _mixc(nt, rp, c, rustc, x=-300, y=100)
    # --- scratches (thin voronoi edges, sparse)
    vo = _n(nt, 'ShaderNodeTexVoronoi', -1400, -1150)
    try:
        vo.feature = 'DISTANCE_TO_EDGE'
    except Exception:
        pass
    _i(vo, 'Scale').default_value = 7.0
    nt.links.new(_map(nt, -1600, -1150, co, (1.0, 1.0, 2.5)), _i(vo, 'Vector'))
    sc_ = _ramp(nt, -1150, -1150, [(0.0, (1, 1, 1, 1)), (0.012, (0, 0, 0, 1))], _o(vo, 'Distance'))
    scm = _math(nt, 'MULTIPLY', sc_, _ramp(nt, -1150, -1350, [(0.5, (0, 0, 0, 1)), (0.62, (1, 1, 1, 1))],
                                            _noise(nt, -1400, -1350, co, 3.0, 2, 0.5)))
    # --- edge chips (chamfer faces) + small random chips
    nc = _noise(nt, -1400, -1600, co, 9.0, 6, 0.7)
    clo = 0.68 - 0.12 * chip
    ce = _ramp(nt, -1150, -1600, [(clo - 0.1, (0, 0, 0, 1)), (clo, (1, 1, 1, 1))], nc)
    chipm = _math(nt, 'MULTIPLY', ce, _math(nt, 'MULTIPLY', wear, 1.3))
    vo2 = _n(nt, 'ShaderNodeTexVoronoi', -1400, -1850)
    _i(vo2, 'Scale').default_value = 22.0
    nt.links.new(co, _i(vo2, 'Vector'))
    sm2 = _ramp(nt, -1150, -1850, [(0.0, (1, 1, 1, 1)), (0.1, (0, 0, 0, 1))], _o(vo2, 'Distance'))
    sm2 = _math(nt, 'MULTIPLY', sm2, _ramp(nt, -1150, -2050, [(0.6, (0, 0, 0, 1)), (0.66, (1, 1, 1, 1))],
                                          _noise(nt, -1400, -2050, co, 4.0, 3, 0.5)))
    chipm = _math(nt, 'MAXIMUM', _math(nt, 'MAXIMUM', chipm, sm2), _math(nt, 'MULTIPLY', scm, 0.8))
    c = _mixc(nt, chipm, c, _c(edge), x=0, y=0)
    nt.links.new(c, _i(b, 'Base Color'))
    nt.links.new(_math(nt, 'MULTIPLY', chipm, 0.85), _i(b, 'Metallic'))
    rr = _math(nt, 'ADD', _math(nt, 'MULTIPLY', rp, 0.25), rough)
    rr = _math(nt, 'ADD', rr, _math(nt, 'MULTIPLY', n1c, 0.12))
    rr = _math(nt, 'SUBTRACT', rr, _math(nt, 'MULTIPLY', chipm, 0.3))
    nt.links.new(rr, _i(b, 'Roughness'))
    # bump: fine grain + rust pitting - chip depressions
    nf = _noise(nt, -1400, -2300, co, 80.0, 4, 0.6)
    h = _math(nt, 'MULTIPLY', nf, 0.3, False)
    h = _math(nt, 'ADD', h, _math(nt, 'MULTIPLY', rp, 0.5), False)
    h = _math(nt, 'SUBTRACT', h, _math(nt, 'MULTIPLY', chipm, 0.6), False)
    bp = _n(nt, 'ShaderNodeBump', 1400, -600)
    _i(bp, 'Strength').default_value = 0.3
    _i(bp, 'Distance').default_value = 0.02
    nt.links.new(h, _i(bp, 'Height'))
    nt.links.new(_o(bp, 'Normal'), _i(b, 'Normal'))
    m.diffuse_color = _c(mid)
    return m


def metal_mat(key, base, rough=0.42, rust=0.5, metallic=0.9, edge=None, grime=0.8):
    m = _newmat(PREFIX + key)
    nt = m.node_tree
    out = _n(nt, 'ShaderNodeOutputMaterial', 1400, 0)
    b = _n(nt, 'ShaderNodeBsdfPrincipled', 1100, 0)
    nt.links.new(_o(b, 'BSDF'), _i(out, 'Surface'))
    co = _o(_n(nt, 'ShaderNodeTexCoord', -1400, 0), 'Object')
    wear = _attr(nt, 'wear', -1400, -600)
    n1 = _noise(nt, -1100, 300, co, 6.0, 8, 0.6)
    c = _ramp(nt, -850, 300, [(0.3, _c([x * 0.55 for x in base])), (0.7, _c(base))], n1)
    ao = _n(nt, 'ShaderNodeAmbientOcclusion', -1100, 600)
    _i(ao, 'Distance').default_value = 0.3
    rao = _ramp(nt, -850, 600, [(0.2, (0.15, 0.11, 0.07, 1)), (0.9, (1, 1, 1, 1))], _o(ao, 'AO'))
    c = _mixc(nt, grime, c, rao, 'MULTIPLY', x=-600, y=400)
    n3 = _noise(nt, -1100, 0, co, 3.0, 10, 0.7)
    lo = 0.68 - 0.1 * rust
    r3 = _ramp(nt, -850, 0, [(lo, (0, 0, 0, 1)), (lo + 0.1, (1, 1, 1, 1))], n3)
    c = _mixc(nt, r3, c, (0.06, 0.03, 0.013), x=-400, y=200)
    ek = None
    if edge:
        ne = _noise(nt, -1100, -800, co, 10.0, 5, 0.6)
        ek = _math(nt, 'MULTIPLY', wear, _ramp(nt, -850, -800, [(0.4, (0, 0, 0, 1)), (0.55, (1, 1, 1, 1))], ne))
        c = _mixc(nt, ek, c, _c(edge), x=-200, y=100)
    nt.links.new(c, _i(b, 'Base Color'))
    nt.links.new(_math(nt, 'SUBTRACT', metallic, r3), _i(b, 'Metallic'))
    rr = _math(nt, 'ADD', _math(nt, 'MULTIPLY', n1, 0.25), rough - 0.1)
    rr = _math(nt, 'ADD', rr, _math(nt, 'MULTIPLY', r3, 0.4))
    nt.links.new(rr, _i(b, 'Roughness'))
    n6 = _noise(nt, -1100, -400, co, 50.0, 4, 0.6)
    bp = _n(nt, 'ShaderNodeBump', 800, -500)
    _i(bp, 'Strength').default_value = 0.15
    _i(bp, 'Distance').default_value = 0.02
    nt.links.new(_math(nt, 'ADD', n6, _math(nt, 'MULTIPLY', r3, 0.5), False), _i(bp, 'Height'))
    nt.links.new(_o(bp, 'Normal'), _i(b, 'Normal'))
    m.diffuse_color = _c(base)
    return m


def simple_mat(key, base, rough=0.5, metallic=0.0, emit=None, strength=0.0):
    m = _newmat(PREFIX + key)
    nt = m.node_tree
    out = _n(nt, 'ShaderNodeOutputMaterial', 400, 0)
    b = _n(nt, 'ShaderNodeBsdfPrincipled', 100, 0)
    nt.links.new(_o(b, 'BSDF'), _i(out, 'Surface'))
    _i(b, 'Base Color').default_value = _c(base)
    _i(b, 'Roughness').default_value = rough
    _i(b, 'Metallic').default_value = metallic
    if emit:
        _i(b, 'Emission Color').default_value = _c(emit)
        _i(b, 'Emission Strength').default_value = strength
    m.diffuse_color = _c(emit or base)
    return m


PALETTE = {
    'armor': dict(dark=(0.045, 0.045, 0.026), mid=(0.108, 0.108, 0.064), light=(0.19, 0.185, 0.125)),
    'armor_dark': dict(dark=(0.035, 0.036, 0.026), mid=(0.068, 0.07, 0.05), light=(0.105, 0.105, 0.078)),
}


MAT_DEF = dict(blotch=0.5, blotch_scale=9.0, chip=0.85, edge=(0.3, 0.29, 0.26), glow=5.0, white=0.35, ao=0.95,
               ao_dist=0.6, rust=1.0, streak=1.0, brass=(0.26, 0.16, 0.07), metal=(0.032, 0.033, 0.036),
               steel=(0.3, 0.29, 0.27), steel_rough=0.32, spots=0.35)


def build_materials():
    rk, sk = MAT_DEF['rust'], MAT_DEF['streak']
    paint_mat('armor', **PALETTE['armor'], rust=rk, chip=MAT_DEF['chip'], streak=sk, edge=MAT_DEF['edge'])
    paint_mat('armor_dark', **PALETTE['armor_dark'], rust=1.2 * rk, chip=MAT_DEF['chip'] * 0.9, streak=1.1 * sk,
              rough=0.66,
              edge=MAT_DEF['edge'])
    paint_mat('red', dark=(0.17, 0.022, 0.012), mid=(0.28, 0.035, 0.018), light=(0.36, 0.06, 0.03),
              edge=(0.3, 0.29, 0.26), rust=0.7, chip=1.0, streak=0.8, rough=0.55, white=MAT_DEF['white'])
    metal_mat('metal', MAT_DEF['metal'], rough=0.45, rust=0.6, edge=(0.16, 0.155, 0.15))
    metal_mat('steel', MAT_DEF['steel'], rough=MAT_DEF['steel_rough'], rust=0.3, metallic=1.0, grime=0.6)
    metal_mat('brass', MAT_DEF['brass'], rough=0.42, rust=0.45, metallic=1.0, grime=0.9)
    simple_mat('hole', (0.006, 0.006, 0.006), rough=0.9)
    simple_mat('glass', (0.02, 0.025, 0.03), rough=0.08, metallic=0.3)
    simple_mat('glow', (0.06, 0.03, 0.01), rough=0.3, emit=(1.0, 0.42, 0.08), strength=MAT_DEF['glow'])
    simple_mat('muzzle', (0.02, 0.012, 0.008), rough=0.5, emit=(1.0, 0.35, 0.08), strength=0.4)
    metal_mat('joint', (0.2, 0.155, 0.1), rough=0.38, rust=0.35, metallic=0.95, grime=0.9, edge=(0.42, 0.36, 0.28))
    simple_mat('rubber', (0.018, 0.018, 0.018), rough=0.75)


# ---------------- objects ----------------
def finish(part, pivot, coll, parent=None):
    pv = Vector(pivot)
    old = bpy.data.objects.get(part.name)
    if old:
        bpy.data.objects.remove(old, do_unlink=True)
    me = bpy.data.meshes.new(part.name)
    verts = [tuple(v - pv) for v in part.V]
    me.from_pydata(verts, [], part.F)
    me.update()
    # material slots compacted to the used ones
    used = sorted(set(part.FM))
    remap = {u: k for k, u in enumerate(used)}
    for u in used:
        me.materials.append(bpy.data.materials[PREFIX + MATS[u]])
    me.polygons.foreach_set('material_index', [remap[i] for i in part.FM])
    a = me.attributes.new('wear', 'FLOAT', 'FACE')
    a.data.foreach_set('value', part.FW)
    a = me.attributes.new('pv', 'FLOAT', 'POINT')
    a.data.foreach_set('value', part.VP)
    me.polygons.foreach_set('use_smooth', [True] * len(me.polygons))
    if hasattr(me, 'set_sharp_from_angle'):
        me.set_sharp_from_angle(angle=D2R(30))
    me.validate(clean_customdata=False)
    me.update()
    ob = bpy.data.objects.new(part.name, me)
    coll.objects.link(ob)
    if parent is not None:
        ob.parent = parent
        ob.location = pv - Vector(parent.get('pivot_world', (0, 0, 0)))
    else:
        ob.location = pv
    ob['pivot_world'] = list(pv)
    return ob


def tri_count(objs):
    t = 0
    for o in objs:
        if o.type == 'MESH':
            t += sum(len(p.vertices) - 2 for p in o.data.polygons)
    return t

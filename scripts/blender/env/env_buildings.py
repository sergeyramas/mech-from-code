# Environment kit - ruined buildings (panel/brick blocks with boolean damage + rebar) and the corrugated hangar.
import bpy, math, random
from mathutils import Vector, Matrix, Euler
from env_common import (MB, fbm, smoothstep, lerp, get_coll, noisy_blob, apply_boolean, bake_modifiers, join,
                        instance_points)
import env_ground as G

DEBRIS_SPOTS = []     # (x, y, radius, density, brick) - consumed by env_scatter


def solidify(ob, thick, offset=-1.0):
    md = ob.modifiers.new('solid', 'SOLIDIFY')
    md.thickness = thick
    md.offset = offset
    md.use_even_offset = True
    md.use_rim = True
    bake_modifiers(ob)


def wall_obj(name, coll, mat, org, p0, t, L, H, fh, bw, ww=1.45, sill=0.85, wh=1.5, z0=-0.5, thick=0.25,
             win=None, burned=(), door=(), extra_rows=True):
    """flat wall with window holes; local (u,z) -> world org + p0 + t*u + z*up; normal = t x up (outward)"""
    t = Vector((t[0], t[1], 0)).normalized()
    nb = max(1, int(round(L / bw)))
    bw = L / nb
    us = {0.0, L}
    for i in range(nb):
        us.add(i * bw + (bw - ww) / 2)
        us.add(i * bw + (bw + ww) / 2)
    us = sorted(us)
    nf = int(math.ceil(H / fh))
    zs = {z0, 0.0, H}
    for f in range(nf + 1):
        for dz in (0.0, sill, sill + wh) + ((sill + wh + 0.7,) if extra_rows else ()):
            z = f * fh + dz
            if z0 < z < H - 0.05:
                zs.add(round(z, 4))
    zs = sorted(zs)

    def kind(uc, zc):
        b = int(uc // bw)
        lu = uc - b * bw
        if not ((bw - ww) / 2 < lu < (bw + ww) / 2):
            return None
        f = int(zc // fh)
        lz = zc - f * fh
        if (f, b) in door and 0.0 < lz < sill + wh:
            return 'door'
        if not (sill < lz < sill + wh):
            return None
        if f * fh + sill + wh > H - 0.3:
            return None
        if win is not None and not win(f, b):
            return None
        return 'win'

    nu = len(us)
    verts = []
    soot = []
    for z in zs:
        for u in us:
            verts.append(Vector((p0[0], p0[1], 0.0)) + t * u + Vector((0, 0, z)))
            s = 0.0
            for (f, b) in burned:
                uc = b * bw + bw / 2
                zl = f * fh + sill + wh
                du = (u - uc) / (ww * 0.75)
                if z > zl - 0.4:
                    s = max(s, math.exp(-du * du) * (1.0 - smoothstep(zl, zl + 3.2, z)))
            soot.append(s)
    faces = []
    for r in range(len(zs) - 1):
        for k in range(nu - 1):
            uc = (us[k] + us[k + 1]) / 2
            zc = (zs[r] + zs[r + 1]) / 2
            if kind(uc, zc):
                continue
            a = r * nu + k
            faces.append((a, a + 1, a + nu + 1, a + nu))
    mb = MB()
    mb.add([tuple(v) for v in verts], faces, 0)
    mb.PA['soot'] = soot
    ob = mb.obj(name, coll, [mat])
    ob.location = org
    solidify(ob, thick, -1.0)
    return ob


def slab_obj(name, coll, mat, org, x0, y0, x1, y1, z, th=0.22):
    mb = MB()
    mb.box((x1 - x0, y1 - y0, th), None, 0, ((x0 + x1) / 2, (y0 + y1) / 2, z - th / 2))
    ob = mb.obj(name, coll, [mat])
    ob.location = org
    return ob


def bbox_world(ob):
    mw = ob.matrix_world
    pts = [mw @ Vector(c) for c in ob.bound_box]
    mn = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    mx = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    return mn, mx


def overlaps(a, b, pad=0.1):
    return all(a[0][i] - pad <= b[1][i] and b[0][i] - pad <= a[1][i] for i in range(3))


def cut_all(parts, cutters):
    bpy.context.view_layer.update()
    for p in parts:
        bb = bbox_world(p)
        cs = [c for c in cutters if overlaps(bb, bbox_world(c))]
        if cs:
            apply_boolean(p, cs)


def remove(obs):
    for o in obs:
        if o and o.name in bpy.data.objects:
            bpy.data.objects.remove(o, do_unlink=True)


def rebar(name, coll, mats, ob, rnd, count=120, broken_name='ENV_concrete_broken'):
    me = ob.data
    idx = [i for i, m in enumerate(me.materials) if m and m.name == broken_name]
    if not idx:
        return None
    bpy.context.view_layer.update()
    mw = ob.matrix_world
    polys = [p for p in me.polygons if p.material_index in idx and p.area > 0.002]
    if not polys:
        return None
    areas = [p.area for p in polys]
    tot = sum(areas)
    mb = MB()
    for _ in range(count):
        r = rnd.random() * tot
        acc = 0.0
        for p, a in zip(polys, areas):
            acc += a
            if acc >= r:
                break
        c = mw @ p.center
        n = (mw.to_3x3() @ p.normal).normalized()
        if c.z < mw.translation.z + 0.3:
            continue
        L = rnd.uniform(0.25, 1.3)
        bend = Vector((rnd.uniform(-0.5, 0.5), rnd.uniform(-0.5, 0.5), rnd.uniform(-0.9, 0.2)))
        pts = [c - n * 0.15]
        d = n.copy()
        seg = 5
        for k in range(seg):
            d = (d + bend * (0.35 * k / seg)).normalized()
            pts.append(pts[-1] + d * L / seg)
        mb.tube(pts, 0.011, 4, 0)
        # occasional parallel bar (mesh layer)
        if rnd.random() < 0.35:
            off = n.cross(Vector((0, 0, 1)))
            if off.length < 0.1:
                off = Vector((1, 0, 0))
            off = off.normalized() * 0.2
            mb.tube([q + off for q in pts], 0.011, 4, 0)
    return mb.obj(name, coll, [mats['ENV_rust']], smooth=60)


def rubble_mound(name, coll, mats, center, radii, seed, brick=False):
    ob = noisy_blob(name, coll, center, radii, amp=0.35, freq=2.2, seed=seed, subdiv=4,
                    mat=mats['ENV_rubble'] if not brick else mats['ENV_brick'])
    return ob


def collapsed_slab(mb, p_hinge, along, length, width, drop, th=0.22, rnd=None):
    """slab hanging from a hinge edge: p_hinge centre of hinge edge, along = horizontal dir into void"""
    along = Vector(along).normalized()
    side = along.cross(Vector((0, 0, 1))).normalized()
    dirv = (along * math.cos(drop) - Vector((0, 0, 1)) * math.sin(drop)).normalized()
    up = side.cross(dirv).normalized()
    c = Vector(p_hinge) + dirv * length / 2
    M = Matrix((side, dirv, up)).transposed().to_4x4()
    M.translation = c
    mb.box((width, length, th), M, 0)


# ------------------------------------------------------------------ blocks
def concrete_block(key, C, M, rnd, x0, y0, W, D, floors, fh=2.8, cutters=(), burned=None, win=None,
                   door=None, mat='ENV_concrete', thick=0.25, rebar_n=150, slabs_skip=(), ww=1.45, wh=1.5,
                   cutter_mat='ENV_concrete_broken'):
    coll = C['ENV_buildings']
    zb = G.pad_z(key)
    org = Vector((x0, y0, zb))
    H = floors * fh + 0.7
    m = M[mat]
    sides = [((0, 0), (1, 0), W, 'S'), ((W, 0), (0, 1), D, 'E'), ((W, D), (-1, 0), W, 'N'), ((0, D), (0, -1), D, 'W')]
    parts = []
    for p0, t, L, sname in sides:
        bset = (burned or {}).get(sname, ())
        dset = (door or {}).get(sname, ())
        wf = (lambda s: (lambda f, b: win(s, f, b)))(sname) if win else None
        parts.append(wall_obj('%s_wall_%s' % (key, sname), coll, m, org, p0, t, L, H, fh, 3.0, thick=thick,
                              burned=bset, door=dset, win=wf, ww=ww, wh=wh))
    for f in range(0, floors + 1):
        if f in slabs_skip:
            continue
        z = f * fh + (0.12 if f == 0 else 0.0)
        parts.append(slab_obj('%s_slab_%d' % (key, f), coll, m, org, thick * 0.6, thick * 0.6, W - thick * 0.6,
                              D - thick * 0.6, z))
    # interior cross walls (break see-through)
    for k in range(1, int(W // 6) + 1):
        xw = k * 6.0
        if xw < W - 1:
            mb = MB()
            mb.box((0.18, D - 2 * thick, floors * fh), None, 0, (xw, D / 2, floors * fh / 2))
            parts.append(mb.obj('%s_iwall_%d' % (key, k), coll, [m], loc=(0, 0, 0)))
            parts[-1].location = org
            # door hole per floor
            for f in range(floors):
                c = MB()
                c.box((0.6, 1.0, 2.1), None, 0, (xw, D * 0.35 + (f % 2) * D * 0.3, f * fh + 1.05))
                co = c.obj('%s_cut_tmp' % key, coll, [M['ENV_concrete_broken']])
                co.location = org
                apply_boolean(parts[-1], [co])
                remove([co])
    cobs = []
    for i, (c, r, amp, seed) in enumerate(cutters):
        cobs.append(noisy_blob('%s_cutter_%d' % (key, i), coll, org + Vector(c), r, amp, 1.4, seed, 3,
                               M[cutter_mat]))
    cut_all(parts, cobs)
    remove(cobs)
    shell = join(parts, '%s_shell' % key)
    if rebar_n:
        rebar('%s_rebar' % key, coll, M, shell, rnd, rebar_n)
    return shell, org, H


def build_B1(C, M, rnd):
    # 3-storey admin block west-north of the yard; south-east top corner blown off
    x0, y0, W, D = -33.0, 20.0, 18.0, 9.0
    cut = [
        ((W - 1.0, 0.5, 8.6), (5.2, 4.2, 4.8), 0.32, 11),
        ((W - 0.2, 3.5, 3.6), (1.8, 2.6, 2.4), 0.3, 12),
        ((5.0, -0.2, 1.3), (1.9, 1.2, 2.1), 0.35, 13),
        ((9.5, D + 0.2, 7.8), (3.0, 1.4, 1.8), 0.4, 14),
        ((1.0, 4.0, 8.6), (1.5, 2.0, 1.0), 0.4, 15),
    ]
    burned = {'S': [(1, 2), (2, 3), (0, 4)], 'E': [(1, 1)], 'N': [(2, 1)]}
    door = {'S': [(0, 1)], 'W': [(0, 1)]}
    shell, org, H = concrete_block('B1', C, M, rnd, x0, y0, W, D, 3, cutters=cut, burned=burned, door=door)
    mb = MB()
    collapsed_slab(mb, org + Vector((W - 4.2, 2.5, 2 * 2.8)), (1, -0.4, 0), 4.2, 3.0, math.radians(38))
    collapsed_slab(mb, org + Vector((W - 3.5, 4.5, 3 * 2.8)), (0.8, -0.6, 0), 3.6, 2.6, math.radians(52))
    mb.obj('B1_collapsed', C['ENV_buildings'], [M['ENV_concrete_broken']])
    rubble_mound('B1_rubble', C['ENV_buildings'], M, org + Vector((W + 0.8, 0.6, -0.4)), (3.6, 3.2, 1.5), 21)
    DEBRIS_SPOTS.append((x0 + W + 1.0, y0 + 0.5, 6.0, 1.0, False))
    DEBRIS_SPOTS.append((x0 + 5.0, y0 - 1.0, 3.0, 0.6, False))
    return shell


def build_B2(C, M, rnd):
    # 5-storey panel block north of the yard: facade hole + pancaked slab
    x0, y0, W, D = -1.5, 26.0, 15.0, 12.0
    cut = [
        ((7.5, -0.4, 6.6), (3.4, 2.4, 3.6), 0.35, 31),
        ((9.6, 2.0, 9.4), (2.4, 3.2, 2.0), 0.3, 32),
        ((W + 0.3, 8.0, 13.5), (2.8, 3.6, 2.3), 0.35, 33),
        ((2.0, -0.2, 12.4), (1.6, 1.0, 1.4), 0.4, 34),
        ((0.0, 11.0, 4.0), (1.2, 2.0, 2.0), 0.4, 35),
    ]
    burned = {'S': [(2, 2), (3, 3), (1, 1), (4, 4), (0, 4)], 'E': [(3, 2), (1, 0)]}
    door = {'S': [(0, 2)]}
    win = lambda s, f, b: not (s in ('E', 'W') and b == 1 and f > 0 and False)
    shell, org, H = concrete_block('B2', C, M, rnd, x0, y0, W, D, 5, cutters=cut, burned=burned, door=door,
                                   win=win, rebar_n=200)
    mb = MB()
    # pancake: floor 3 slab dropped onto floor 2 at an angle inside the hole
    collapsed_slab(mb, org + Vector((5.6, 3.6, 3 * 2.8 - 0.1)), (0.1, -1, 0), 4.2, 3.2, math.radians(28))
    collapsed_slab(mb, org + Vector((8.8, 4.0, 2 * 2.8 - 0.1)), (-0.2, -1, 0), 4.6, 2.8, math.radians(48))
    # balconies on the south facade (some missing)
    bal = MB()
    for f in range(1, 5):
        for b in range(5):
            if (f, b) in ((2, 2), (3, 2), (2, 3), (4, 0)):
                continue
            cx = b * 3.0 + 1.5
            z = f * 2.8
            bal.box((2.6, 1.1, 0.14), None, 0, (cx, -0.55, z + 0.05))
            if rnd.random() < 0.85:
                bal.box((2.6, 0.08, 0.95), None, 1, (cx, -1.06, z + 0.6))
                bal.box((0.08, 1.0, 0.95), None, 1, (cx - 1.26, -0.55, z + 0.6))
                bal.box((0.08, 1.0, 0.95), None, 1, (cx + 1.26, -0.55, z + 0.6))
    bo = bal.obj('B2_balconies', C['ENV_buildings'], [M['ENV_concrete'], M['ENV_paint_white']])
    bo.location = org
    mb.obj('B2_collapsed', C['ENV_buildings'], [M['ENV_concrete_broken']])
    rubble_mound('B2_rubble', C['ENV_buildings'], M, org + Vector((7.5, -1.6, -0.3)), (3.6, 2.2, 1.3), 41)
    shell.name = shell.data.name = 'BLD_target'      # destruction target for the VFX pass
    DEBRIS_SPOTS.append((x0 + 7.5, y0 - 2.5, 5.0, 1.0, False))
    DEBRIS_SPOTS.append((x0 + W + 1.0, y0 + 8.0, 3.5, 0.6, False))
    return shell


def build_B3(C, M, rnd):
    # 2-storey brick workshop south of the road: mostly collapsed, roof gone, trusses left
    x0, y0, W, D = -41.0, -38.0, 21.0, 9.0
    fh = 4.2
    cut = [
        ((W - 2.0, D * 0.5, 8.0), (7.5, 7.0, 6.2), 0.3, 51),
        ((W * 0.45, D + 0.5, 7.4), (5.5, 2.5, 4.0), 0.35, 52),
        ((3.0, -0.3, 6.8), (3.5, 1.6, 2.0), 0.4, 53),
        ((11.0, -0.2, 1.6), (2.0, 1.0, 2.0), 0.3, 54),
    ]
    burned = {'N': [(0, 2), (0, 4)], 'S': [(0, 1)]}
    door = {'N': [(0, 3)], 'E': [(0, 1)]}
    shell, org, H = concrete_block('B3', C, M, rnd, x0, y0, W, D, 2, fh=fh, cutters=cut, burned=burned, door=door,
                                   mat='ENV_brick', thick=0.38, rebar_n=0, slabs_skip=(1, 2), ww=2.0, wh=2.4,
                                   cutter_mat='ENV_brick')
    # steel roof trusses: west half intact, east half fallen
    mb = MB()
    for k in range(7):
        x = 1.5 + k * 3.0
        fallen = x > W * 0.55
        zt = 2 * fh + 0.1
        if fallen:
            a = Vector((x, 0.3, rnd.uniform(0.3, 1.5)))
            b = Vector((x + rnd.uniform(-1.5, 1.5), D - 0.3, rnd.uniform(2.0, 4.5)))
            mb.box_pts(a, b, 0.18, 0.3, 0)
            continue
        a, b, c = Vector((x, 0.3, zt)), Vector((x, D - 0.3, zt)), Vector((x, D / 2, zt + 1.6))
        mb.box_pts(a, b, 0.16, 0.22, 0)
        mb.box_pts(a, c, 0.16, 0.22, 0)
        mb.box_pts(c, b, 0.16, 0.22, 0)
        for s in (0.25, 0.5, 0.75):
            p = a.lerp(b, s)
            q = a.lerp(c, s * 2) if s <= 0.5 else c.lerp(b, (s - 0.5) * 2)
            mb.box_pts(p, q, 0.08, 0.08, 0)
    for k in range(3):
        y = 1.0 + k * 3.5
        mb.box_pts(Vector((1.5, y, 2 * fh + 0.35 + (0.9 if k == 1 else 0.0))),
                   Vector((W * 0.55, y, 2 * fh + 0.35 + (0.9 if k == 1 else 0.0))), 0.1, 0.12, 0)
    tr = mb.obj('B3_trusses', C['ENV_buildings'], [M['ENV_rust']])
    tr.location = org
    rubble_mound('B3_rubble_in', C['ENV_buildings'], M, org + Vector((W - 4.0, D / 2, -0.5)), (5.0, 3.6, 2.2), 61,
                 brick=True)
    rubble_mound('B3_rubble_out', C['ENV_buildings'], M, org + Vector((W + 0.6, D * 0.4, -0.4)), (2.6, 3.4, 1.4), 62,
                 brick=True)
    DEBRIS_SPOTS.append((x0 + W + 1.5, y0 + D * 0.5, 6.0, 1.2, True))
    DEBRIS_SPOTS.append((x0 + W * 0.45, y0 + D + 1.5, 4.0, 0.8, True))
    return shell


# ------------------------------------------------------------------ hangar
HX0, HY0, HX1, HY1 = 26.0, 4.0, 56.0, 22.0
EAVE, RIDGE = 6.0, 8.5


def sheet_protos(C, M):
    """corrugated sheet prototypes: 1 m wide (x), 1 m long (y), corrugation in z"""
    sc = get_coll('SET_sheets', C['ENV_assets'])
    mat = M['ENV_corrugated']
    P = 0.125
    cols = [i * P / 4 for i in range(33)]

    def prof(x):
        return 0.018 * math.sin(2 * math.pi * x / P)

    def make(name, rows, fz=None, fx=None, top=None):
        mb = MB()
        vs = []
        nr = len(rows)
        for y in rows:
            for x in cols:
                z = prof(x)
                xx = x
                if fz:
                    dz, dx = fz(x, y)
                    z += dz
                    xx += dx
                yy = y
                if top is not None and y >= rows[-1] - 1e-6:
                    yy = top(x)
                vs.append((xx, yy, z))
        fs = []
        nc = len(cols)
        for j in range(nr - 1):
            for i in range(nc - 1):
                a = j * nc + i
                fs.append((a, a + 1, a + nc + 1, a + nc))
        mb.add(vs, fs, 0)
        ob = mb.obj(name, sc, [mat], smooth=40)
        return ob

    make('sheet_a_flat', [0.0, 1.0])
    make('sheet_b_bent', [i / 8 for i in range(9)],
         fz=lambda x, y: (0.35 * max(0.0, y - 0.45) ** 2 * 3.0 + 0.04 * math.sin(x * 7), 0.0))
    rr = random.Random(3)
    tear = [rr.uniform(0.55, 0.95) for _ in range(33)]
    make('sheet_c_torn', [i / 6 for i in range(7)], top=lambda x: tear[min(32, int(x / (1.0 / 32)))])
    make('sheet_d_crumpled', [i / 8 for i in range(9)],
         fz=lambda x, y: (0.22 * math.sin(y * 9.0 + x * 2.0) * y + 0.15 * math.sin(x * 5 + y * 3), 0.08 * math.sin(y * 6)))
    return sc


def frame_axes(ex, ey):
    ex = Vector(ex).normalized()
    ey = Vector(ey).normalized()
    ez = ex.cross(ey).normalized()
    ey = ez.cross(ex).normalized()
    return Matrix((ex, ey, ez)).transposed().to_euler('XYZ')


def build_hangar(C, M, rnd):
    coll = C['ENV_buildings']
    zb = G.pad_z('HANGAR')
    org = Vector((0, 0, zb))
    sc = sheet_protos(C, M)
    st = MB()   # structure
    W = HY1 - HY0
    ym = (HY0 + HY1) / 2
    xs = [HX0 + 5.0 * i for i in range(7)]
    collapse_x = 43.0

    def roof_z(y):
        return EAVE + (RIDGE - EAVE) * (1.0 - abs(y - ym) / (W / 2))

    for i, x in enumerate(xs):
        dmg = x > collapse_x
        tilt = 0.0 if not dmg else (x - collapse_x) / (HX1 - collapse_x)
        for y in (HY0, HY1):
            top = Vector((x, y, EAVE))
            if dmg and y == HY1 and i == len(xs) - 2:
                # snapped column lying on the floor
                st.box_pts(Vector((x, y, 0.2)), Vector((x - 1.0, y - 5.5, 0.25)), 0.3, 0.3, 0)
                continue
            if dmg:
                top = Vector((x + 0.6 * tilt, y + (0.8 if y == HY0 else -0.8) * tilt, EAVE - 1.6 * tilt))
            st.box_pts(Vector((x, y, -0.3)), top, 0.32, 0.32, 0)
        # rafters
        if not dmg:
            a, b, c = Vector((x, HY0, EAVE)), Vector((x, ym, RIDGE)), Vector((x, HY1, EAVE))
            st.box_pts(a, b, 0.22, 0.45, 0)
            st.box_pts(b, c, 0.22, 0.45, 0)
            st.box_pts(Vector((x, HY0 + 2.5, EAVE + 0.2)), Vector((x, ym - 1.0, RIDGE - 0.5)), 0.1, 0.1, 0)
            st.box_pts(Vector((x, HY1 - 2.5, EAVE + 0.2)), Vector((x, ym + 1.0, RIDGE - 0.5)), 0.1, 0.1, 0)
        else:
            sag = 2.5 + 3.5 * tilt
            a = Vector((x + 0.6 * tilt, HY0 + 0.8 * tilt, EAVE - 1.6 * tilt))
            b = Vector((x + rnd.uniform(-0.8, 0.8), ym, RIDGE - sag))
            c = Vector((x - 0.5 * tilt, HY1 - 0.8 * tilt, EAVE - 2.2 * tilt))
            st.box_pts(a, b, 0.22, 0.45, 0)
            st.box_pts(b, c, 0.22, 0.45, 0)
    # purlins and girts (west intact part only, broken stubs further east)
    for k in range(7):
        s = k / 6
        for side in (0, 1):
            y = lerp(HY0, ym, s) if side == 0 else lerp(HY1, ym, s)
            z = roof_z(y) + 0.3
            st.box_pts(Vector((HX0, y, z)), Vector((collapse_x + 2.5 + rnd.uniform(-1, 1.5), y, z - 0.05)), 0.08, 0.16, 0)
    for zz in (1.5, 3.5, 5.5):
        for y in (HY0 - 0.2, HY1 + 0.2):
            st.box_pts(Vector((HX0, y, zz)), Vector((collapse_x + 1.0, y, zz)), 0.1, 0.14, 0)
        st.box_pts(Vector((HX0 - 0.2, HY0, zz)), Vector((HX0 - 0.2, HY0 + 5.5, zz)), 0.1, 0.14, 0)
        st.box_pts(Vector((HX0 - 0.2, HY1 - 5.5, zz)), Vector((HX0 - 0.2, HY1, zz)), 0.1, 0.14, 0)
    so = st.obj('HANGAR_frame', coll, [M['ENV_steel_paint']], smooth=30)
    so.location = org
    # floor slab
    fl = MB()
    fl.box((HX1 - HX0 + 1.0, W + 1.0, 0.3), None, 0, ((HX0 + HX1) / 2, ym, 0.0))
    fo = fl.obj('HANGAR_floor', coll, [M['ENV_concrete_apron']])
    fo.location = org

    items = []
    names = sorted(o.name for o in sc.objects)
    FL, BE, TO, CR = 'sheet_a_flat', 'sheet_b_bent', 'sheet_c_torn', 'sheet_d_crumpled'

    def add(loc, ex, ey, L, proto, w=1.0):
        items.append((Vector(loc) + org, frame_axes(ex, ey), (w, L, 1.0), proto))

    # long walls (south y=HY0 faces -Y, north y=HY1 faces +Y)
    for side, y, nrm in ((0, HY0 - 0.25, -1), (1, HY1 + 0.25, 1)):
        x = HX0
        while x < HX1 - 0.5:
            dmg = x > collapse_x
            r = rnd.random()
            gap = (r < 0.06) or (dmg and r < 0.45)
            if not gap:
                proto = FL
                L = EAVE + 0.1
                if dmg or r < 0.14:
                    proto = TO if rnd.random() < 0.6 else BE
                    L = EAVE * rnd.uniform(0.5, 0.95) if proto == TO else EAVE * 0.8
                if side == 0:
                    add((x + 1.0, y, -0.1), (-1, 0, 0), (0, 0, 1), L, proto)
                else:
                    add((x, y, -0.1), (1, 0, 0), (0, 0, 1), L, proto)
            x += 0.96
    # west gable with big door opening (x=HX0), door y in [ym-3.5, ym+3.5], h 5.2
    y = HY0
    while y < HY1 - 0.4:
        top = roof_z(y + 0.5)
        if ym - 3.6 < y + 0.5 < ym + 3.6:
            add((HX0 - 0.25, y, 5.3), (0, 1, 0), (0, 0, 1), top - 5.3, FL)
        else:
            if rnd.random() > 0.05:
                add((HX0 - 0.25, y, -0.1), (0, 1, 0), (0, 0, 1), top + 0.1, FL if rnd.random() > 0.15 else TO)
        y += 0.96
    # east gable mostly gone: a few torn sheets
    y = HY0
    while y < HY1:
        if rnd.random() < 0.35:
            add((HX1 + 0.25, y + 1.0, -0.1), (0, -1, 0), (0, 0, 1), rnd.uniform(1.5, 4.0), TO)
        y += 0.96
    # roof (two slopes, 3 courses each)
    for side in (0, 1):
        y0 = HY0 if side == 0 else HY1
        p_e = Vector((0, y0 + (-0.4 if side == 0 else 0.4), EAVE + 0.35 - 0.12))
        p_r = Vector((0, ym, RIDGE + 0.35))
        slope = (p_r - p_e)
        Ls = slope.length
        dirv = slope.normalized()
        x = HX0 - 0.3
        while x < HX1:
            dmg = x > collapse_x - 1.0
            for c in range(3):
                r = rnd.random()
                hole = r < 0.07 or (dmg and r < 0.75)
                s0 = c * Ls / 3
                base = Vector((x, p_e.y, p_e.z)) + dirv * s0
                if hole:
                    if dmg and rnd.random() < 0.5:
                        # sheet hanging off the broken purlins
                        add(base + Vector((0, 0, -0.5)), (1, 0, 0),
                            Vector((rnd.uniform(-0.3, 0.3), dirv.y * 0.3, -1)), Ls / 3 * 1.1, BE)
                    continue
                if side == 0:
                    add(base + Vector((1.0, 0, 0)), (-1, 0, 0), dirv, Ls / 3 + 0.12, FL if not dmg else TO)
                else:
                    add(base, (1, 0, 0), dirv, Ls / 3 + 0.12, FL if not dmg else TO)
            x += 0.96
    # fallen sheets inside / outside the east half
    for _ in range(40):
        x = rnd.uniform(collapse_x - 2, HX1 + 4)
        y = rnd.uniform(HY0 - 3, HY1 + 3)
        z = 0.05 + rnd.uniform(0, 0.6)
        a = rnd.uniform(0, math.tau)
        items.append((Vector((x, y, z)) + org, (rnd.uniform(-0.3, 0.3), rnd.uniform(-0.3, 0.3), a),
                      (1.0, rnd.uniform(1.5, 3.0), 1.0), CR if rnd.random() < 0.6 else BE))
    instance_points('HANGAR_sheets', coll, sc, items)
    DEBRIS_SPOTS.append(((collapse_x + HX1) / 2, ym, 9.0, 0.6, False))
    return so


def build(C, M, ground, rnd):
    DEBRIS_SPOTS.clear()
    build_B1(C, M, rnd)
    build_B2(C, M, rnd)
    build_B3(C, M, rnd)
    build_hangar(C, M, rnd)

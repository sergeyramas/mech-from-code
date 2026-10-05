# Procedural heavy mech - helper library (bmesh primitives + procedural materials)
import bpy, bmesh, math
from mathutils import Vector, Matrix, Euler, Quaternion

D2R = math.radians
MATS = ['armor', 'armor_dark', 'red', 'metal', 'steel', 'rivet', 'hole', 'glass', 'glow', 'muzzle']
MAT_PREFIX = 'MECH_'

AX = {'x': 0, 'y': 1, 'z': 2}
# rotation that takes +Z to the face normal
FACE_ROT = {'+x': (0, 90, 0), '-x': (0, -90, 0), '+y': (-90, 0, 0), '-y': (90, 0, 0),
            '+z': (0, 0, 0), '-z': (180, 0, 0)}


def xf(c=(0, 0, 0), rot=(0, 0, 0), q=None):
    r = q.to_matrix().to_4x4() if q is not None else Euler([D2R(a) for a in rot], 'XYZ').to_matrix().to_4x4()
    return Matrix.Translation(Vector(c)) @ r


def _face_axes(face):
    a = AX[face[1]]
    sign = 1 if face[0] == '+' else -1
    u, v = [i for i in range(3) if i != a]
    return a, sign, u, v


class Part:
    def __init__(self, name, off=(0, 0, 0)):
        self.name = name
        self.off = Vector(off)
        self.bm = bmesh.new()
        self.n_prims = 0

    # ---- core ----
    def _merge(self, tmp, mat, matrix):
        bmesh.ops.transform(tmp, matrix=Matrix.Translation(self.off) @ matrix, verts=tmp.verts)
        mi = MATS.index(mat)
        tmp.verts.index_update()
        vm = [self.bm.verts.new(v.co) for v in tmp.verts]
        for f in tmp.faces:
            try:
                nf = self.bm.faces.new([vm[v.index] for v in f.verts])
                nf.material_index = mi
            except ValueError:
                pass
        tmp.free()
        self.n_prims += 1

    # ---- primitives ----
    def box(self, c, size, rot=(0, 0, 0), mat='armor', bev=0.03, seg=1, taper=None, cham=0.0, cham_axis='y'):
        tmp = bmesh.new()
        bmesh.ops.create_cube(tmp, size=1.0)
        for v in tmp.verts:
            v.co = Vector((v.co.x * size[0], v.co.y * size[1], v.co.z * size[2]))
        if taper:
            for v in tmp.verts:
                if v.co.z > 0:
                    v.co.x *= taper[0]
                    v.co.y *= taper[1]
        if cham > 0:
            ai = AX[cham_axis]
            axv = Vector([1 if i == ai else 0 for i in range(3)])
            es = [e for e in tmp.edges if abs((e.verts[0].co - e.verts[1].co).normalized().dot(axv)) > 0.99]
            bmesh.ops.bevel(tmp, geom=es, offset=cham, offset_type='OFFSET', segments=1, profile=0.5,
                            affect='EDGES', clamp_overlap=True)
        if bev > 0:
            bmesh.ops.bevel(tmp, geom=list(tmp.edges), offset=bev, offset_type='OFFSET', segments=seg,
                            profile=0.5, affect='EDGES', clamp_overlap=True)
        self._merge(tmp, mat, xf(c, rot))

    def cyl(self, c, r, depth, rot=(0, 0, 0), mat='metal', n=16, r2=None, bev=0.0, q=None, cap_tris=False):
        tmp = bmesh.new()
        bmesh.ops.create_cone(tmp, cap_ends=True, cap_tris=cap_tris, segments=n, radius1=r,
                              radius2=r if r2 is None else r2, depth=depth)
        if bev > 0:
            es = [e for e in tmp.edges if abs(e.verts[0].co.z - e.verts[1].co.z) < 1e-5
                  and abs(abs(e.verts[0].co.z) - depth / 2) < 1e-4]
            bmesh.ops.bevel(tmp, geom=es, offset=bev, offset_type='OFFSET', segments=1, profile=0.5,
                            affect='EDGES', clamp_overlap=True)
        self._merge(tmp, mat, xf(c, rot, q))

    def gear(self, c, r, th, teeth=12, rot=(0, 0, 0), mat='metal', dt=0.14, hub=True):
        tmp = bmesh.new()
        segs = teeth * 4
        bmesh.ops.create_cone(tmp, cap_ends=True, cap_tris=True, segments=segs, radius1=r, radius2=r, depth=th)
        step = 2 * math.pi / segs
        for v in tmp.verts:
            if v.co.xy.length < r * 0.5:
                continue
            k = int(round(math.atan2(v.co.y, v.co.x) / step)) % 4
            if k in (2, 3):
                v.co.x *= (1 - dt)
                v.co.y *= (1 - dt)
        self._merge(tmp, mat, xf(c, rot))
        if hub:
            m = xf(c, rot)
            self.cyl(m @ Vector((0, 0, 0)), r * 0.45, th * 1.6, rot=rot, mat='metal', n=12, bev=0.01)
            # bolt ring
            for i in range(6):
                a = i * math.pi / 3
                p = m @ Vector((math.cos(a) * r * 0.62, math.sin(a) * r * 0.62, th / 2))
                self.cyl(p, r * 0.06, th * 0.3, rot=rot, mat='rivet', n=6)

    def tube(self, c, r, depth, rot=(0, 0, 0), ring_mat='rivet', inner=0.78, n=16):
        """ring with dark bore (launcher tube / pipe end) - axis = local Z, open end at +Z"""
        self.cyl(c, r, depth, rot=rot, mat=ring_mat, n=n, bev=0.01)
        m = xf(c, rot)
        self.cyl(m @ Vector((0, 0, 0.003)), r * inner, depth + 0.004, rot=rot, mat='hole', n=n)

    def rivets(self, c, size, rot=(0, 0, 0), face='-y', spacing=0.24, margin=0.09, r=0.028, cham=0.0,
               mat='rivet'):
        a, sign, u, v = _face_axes(face)
        hu = size[u] / 2 - margin
        hv = size[v] / 2 - margin
        if hu <= 0 or hv <= 0:
            return
        pts = []
        nu = max(1, int(round(2 * hu / spacing)))
        nv = max(1, int(round(2 * hv / spacing)))
        for i in range(nu + 1):
            uu = -hu + 2 * hu * i / nu
            pts += [(uu, -hv), (uu, hv)]
        for j in range(1, nv):
            vv = -hv + 2 * hv * j / nv
            pts += [(-hu, vv), (hu, vv)]
        base = xf(c, rot)
        frot = Euler([D2R(x) for x in FACE_ROT[face]], 'XYZ').to_matrix().to_4x4()
        for (uu, vv) in pts:
            if cham > 0 and abs(uu) > hu - cham * 0.8 and abs(vv) > hv - cham * 0.8:
                continue
            lp = [0, 0, 0]
            lp[a] = sign * size[a] / 2
            lp[u] = uu
            lp[v] = vv
            m = base @ Matrix.Translation(Vector(lp)) @ frot @ Matrix.Translation((0, 0, r * 0.3))
            tmp = bmesh.new()
            bmesh.ops.create_cone(tmp, cap_ends=True, cap_tris=False, segments=6, radius1=r, radius2=r * 0.55,
                                  depth=r * 0.9)
            self._merge(tmp, mat, m)

    def plate(self, c, size, rot=(0, 0, 0), face='-y', mat='armor', cham=0.0, bev=0.03, rivet=True,
              spacing=0.24, margin=0.09, sub=True):
        a, sign, u, v = _face_axes(face)
        self.box(c, size, rot, mat=mat, bev=bev, cham=cham, cham_axis='xyz'[a])
        if rivet:
            self.rivets(c, size, rot, face=face, spacing=spacing, margin=max(margin, bev + 0.05), cham=cham)
        if sub and size[u] > 0.55 and size[v] > 0.55:
            k = self.n_prims
            ou = ((k * 37) % 7 - 3) / 3.0 * size[u] * 0.14
            ov = ((k * 53) % 5 - 2) / 2.0 * size[v] * 0.14
            lp = [0, 0, 0]
            lp[a] = sign * (size[a] / 2 + 0.03)
            lp[u] = ou
            lp[v] = ov
            ls = [0, 0, 0]
            ls[a] = 0.07
            ls[u] = size[u] * (0.5 if k % 2 else 0.62)
            ls[v] = size[v] * (0.45 if k % 3 else 0.6)
            smat = 'armor_dark' if (k % 3 == 0 and mat == 'armor') else mat
            self.plate(xf(c, rot) @ Vector(lp), ls, rot, face=face, mat=smat, cham=min(cham * 0.5, min(ls[u], ls[v]) * 0.25),
                       bev=0.02, rivet=True, spacing=0.17, margin=0.06, sub=False)
            # small panel seam / bolt strip
            if k % 2 == 0 and size[v] > 0.9:
                lp2 = list(lp)
                lp2[u] = -ou * 1.6 if abs(ou) > 0.01 else size[u] * 0.3
                lp2[a] = sign * (size[a] / 2 + 0.02)
                ls2 = [0, 0, 0]
                ls2[a] = 0.04
                ls2[u] = 0.09
                ls2[v] = size[v] * 0.6
                self.box(xf(c, rot) @ Vector(lp2), ls2, rot, mat='metal', bev=0.01)

    def pipe(self, p1, p2, r=0.05, mat='metal'):
        p1, p2 = Vector(p1), Vector(p2)
        d = p2 - p1
        q = d.normalized().to_track_quat('Z', 'Y')
        self.cyl((p1 + p2) / 2, r, d.length, q=q, mat=mat, n=8)
        for pp in (p1, p2):
            self.cyl(pp, r * 1.6, r * 2.2, q=q, mat='steel', n=8)

    def decal(self, c, size, rot, face, u0, v0, w, h, mat='red', th=0.02, bev=0.006):
        """thin overlay panel on a face of a box (e.g. red marking)"""
        a, sign, u, v = _face_axes(face)
        lp = [0, 0, 0]
        lp[a] = sign * (size[a] / 2 + th / 2 - 0.004)
        lp[u] = u0
        lp[v] = v0
        ls = [0, 0, 0]
        ls[a] = th
        ls[u] = w
        ls[v] = h
        wc = xf(c, rot) @ Vector(lp)
        self.box(wc, ls, rot, mat=mat, bev=bev)

    def grille(self, c, size, rot=(0, 0, 0), n=6, face='-y', mat='metal'):
        """dark recess with horizontal slats (vent)"""
        a, sign, u, v = _face_axes(face)
        self.box(c, size, rot, mat='hole', bev=0.0)
        base = xf(c, rot)
        for i in range(n):
            lp = [0, 0, 0]
            lp[a] = sign * size[a] * 0.25
            lp[v] = -size[v] / 2 + size[v] * (i + 0.5) / n
            ls = [0, 0, 0]
            ls[a] = size[a] * 0.75
            ls[u] = size[u] * 0.98
            ls[v] = size[v] / n * 0.45
            self.box(base @ Vector(lp), ls, rot, mat=mat, bev=0.008)

    def piston(self, p1, p2, r, mat='metal'):
        p1, p2 = Vector(p1), Vector(p2)
        d = p2 - p1
        L = d.length
        q = d.normalized().to_track_quat('Z', 'Y')
        dn = d.normalized()
        self.cyl(p1 + dn * L * 0.3, r, L * 0.6, q=q, mat=mat, n=14, bev=0.015)
        self.cyl(p1 + dn * L * 0.62, r * 1.15, 0.06, q=q, mat='armor_dark', n=14)
        self.cyl(p1 + dn * L * 0.78, r * 0.55, L * 0.44, q=q, mat='steel', n=12)
        # end eyes
        self.cyl(p1, r * 1.1, r * 1.6, rot=(0, 90, 0), mat='armor_dark', n=12, bev=0.01)
        self.cyl(p2, r * 1.0, r * 1.6, rot=(0, 90, 0), mat='armor_dark', n=12, bev=0.01)

    def spring(self, c, r, length, coils=8, rot=(0, 0, 0)):
        m = xf(c, rot)
        for i in range(coils):
            z = -length / 2 + length * (i + 0.5) / coils
            self.cyl(m @ Vector((0, 0, z)), r, length / coils * 0.45, rot=rot, mat='steel', n=14)
        self.cyl(c, r * 0.45, length, rot=rot, mat='metal', n=10)


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


def _ramp(nt, x, y, stops):
    r = _n(nt, 'ShaderNodeValToRGB', x, y)
    el = r.color_ramp.elements
    el[0].position = stops[0][0]
    el[0].color = stops[0][1]
    el[1].position = stops[-1][0]
    el[1].color = stops[-1][1]
    for p, c in stops[1:-1]:
        e = el.new(p)
        e.color = c
    return r


def _noise(nt, x, y, src, scale, detail=6.0, rough=0.6):
    n = _n(nt, 'ShaderNodeTexNoise', x, y)
    _i(n, 'Scale').default_value = scale
    _i(n, 'Detail').default_value = detail
    _i(n, 'Roughness').default_value = rough
    nt.links.new(src, _i(n, 'Vector'))
    return n


def _math(nt, x, y, op, a, b, clamp=True):
    m = _n(nt, 'ShaderNodeMath', x, y, operation=op, use_clamp=clamp)
    for k, val in enumerate((a, b)):
        if isinstance(val, (int, float)):
            m.inputs[k].default_value = val
        else:
            nt.links.new(val, m.inputs[k])
    return _o(m, 'Value')


def _mixc(nt, x, y, fac, A, B, blend='MIX'):
    m = _n(nt, 'ShaderNodeMix', x, y, data_type='RGBA', blend_type=blend, clamp_factor=True)
    for ident, val in (('Factor_Float', fac), ('A_Color', A), ('B_Color', B)):
        if isinstance(val, (int, float)):
            _i(m, ident).default_value = val
        elif isinstance(val, tuple):
            _i(m, ident).default_value = val
        else:
            nt.links.new(val, _i(m, ident))
    return _o(m, 'Result_Color')


def _newmat(name):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    m.node_tree.nodes.clear()
    return m


def _rgba(c):
    return (c[0], c[1], c[2], 1.0)


def paint_mat(key, base, base2, edge=(0.33, 0.31, 0.28), rust=1.0, chip=1.0, rough=0.55, dirt=1.0):
    m = _newmat(MAT_PREFIX + key)
    nt = m.node_tree
    out = _n(nt, 'ShaderNodeOutputMaterial', 1600, 0)
    b = _n(nt, 'ShaderNodeBsdfPrincipled', 1300, 0)
    nt.links.new(_o(b, 'BSDF'), _i(out, 'Surface'))
    tc = _n(nt, 'ShaderNodeTexCoord', -1400, 0)
    co = _o(tc, 'Object')
    # large colour variation
    n1 = _noise(nt, -1000, 400, co, 1.3, 6, 0.6)
    r1 = _ramp(nt, -750, 400, [(0.32, _rgba(base2)), (0.68, _rgba(base))])
    nt.links.new(_o(n1, 'Fac'), _i(r1, 'Fac'))
    # vertical grime streaks
    mp = _n(nt, 'ShaderNodeMapping', -1150, 150)
    _i(mp, 'Scale').default_value = (5.0, 5.0, 0.35)
    nt.links.new(co, _i(mp, 'Vector'))
    n2 = _noise(nt, -1000, 150, _o(mp, 'Vector'), 3.0, 5, 0.55)
    r2 = _ramp(nt, -750, 150, [(0.35, (1, 1, 1, 1)), (0.7, (0.32, 0.27, 0.2, 1))])
    nt.links.new(_o(n2, 'Fac'), _i(r2, 'Fac'))
    c1 = _mixc(nt, -450, 300, 0.85 * dirt, _o(r1, 'Color'), _o(r2, 'Color'), 'MULTIPLY')
    # rust mask
    n3 = _noise(nt, -1000, -100, co, 1.6, 12, 0.75)
    lo = 0.62 - 0.07 * rust
    r3 = _ramp(nt, -750, -100, [(lo, (0, 0, 0, 1)), (lo + 0.09, (1, 1, 1, 1))])
    nt.links.new(_o(n3, 'Fac'), _i(r3, 'Fac'))
    n4 = _noise(nt, -1000, -350, co, 22.0, 8, 0.7)
    r4 = _ramp(nt, -750, -350, [(0.3, (0.03, 0.018, 0.01, 1)), (0.55, (0.075, 0.035, 0.015, 1)), (0.8, (0.13, 0.055, 0.022, 1))])
    nt.links.new(_o(n4, 'Fac'), _i(r4, 'Fac'))
    # cavity grime (AO) - dark brown dirt in crevices and near plate edges
    ao = _n(nt, 'ShaderNodeAmbientOcclusion', -1000, 650)
    _i(ao, 'Distance').default_value = 0.35
    rao = _ramp(nt, -750, 650, [(0.25, (0.08, 0.06, 0.04, 1)), (0.85, (1, 1, 1, 1))])
    nt.links.new(_o(ao, 'AO'), _i(rao, 'Fac'))
    c1 = _mixc(nt, -300, 450, 0.9, c1, _o(rao, 'Color'), 'MULTIPLY')
    c2 = _mixc(nt, -200, 200, _o(r3, 'Color'), c1, _o(r4, 'Color'))
    # chips / scratches
    vo = _n(nt, 'ShaderNodeTexVoronoi', -1000, -600)
    _i(vo, 'Scale').default_value = 16.0
    nt.links.new(co, _i(vo, 'Vector'))
    rv = _ramp(nt, -750, -600, [(0.0, (1, 1, 1, 1)), (0.16, (0, 0, 0, 1))])
    nt.links.new(_o(vo, 'Distance'), _i(rv, 'Fac'))
    n5 = _noise(nt, -1000, -850, co, 4.5, 4, 0.5)
    lo5 = 0.56 - 0.08 * chip
    r5 = _ramp(nt, -750, -850, [(lo5, (0, 0, 0, 1)), (lo5 + 0.05, (1, 1, 1, 1))])
    nt.links.new(_o(n5, 'Fac'), _i(r5, 'Fac'))
    chipm = _math(nt, -450, -700, 'MULTIPLY', _o(rv, 'Color'), _o(r5, 'Color'))
    c3 = _mixc(nt, 50, 100, chipm, c2, _rgba(edge))
    nt.links.new(c3, _i(b, 'Base Color'))
    # metallic: bare metal in chips
    met = _math(nt, 300, -200, 'MULTIPLY', chipm, 0.9)
    nt.links.new(met, _i(b, 'Metallic'))
    # roughness
    rr = _math(nt, 300, -350, 'MULTIPLY_ADD' if False else 'MULTIPLY', _o(r3, 'Color'), 0.35)
    rr2 = _math(nt, 500, -350, 'ADD', rr, rough)
    rn = _math(nt, 500, -500, 'MULTIPLY', _o(n2, 'Fac'), 0.15)
    rr3 = _math(nt, 700, -400, 'ADD', rr2, rn)
    rr4 = _math(nt, 900, -400, 'SUBTRACT', rr3, _math(nt, 700, -600, 'MULTIPLY', chipm, 0.25))
    nt.links.new(rr4, _i(b, 'Roughness'))
    # bump
    n6 = _noise(nt, -1000, -1100, co, 70.0, 4, 0.6)
    h1 = _math(nt, 300, -900, 'MULTIPLY', _o(n6, 'Fac'), 0.35, clamp=False)
    h2 = _math(nt, 500, -900, 'ADD', h1, _math(nt, 300, -1050, 'MULTIPLY', _o(r3, 'Color'), 0.5), clamp=False)
    h3 = _math(nt, 700, -900, 'SUBTRACT', h2, _math(nt, 500, -1100, 'MULTIPLY', chipm, 0.6), clamp=False)
    bp = _n(nt, 'ShaderNodeBump', 1000, -800)
    _i(bp, 'Strength').default_value = 0.25
    _i(bp, 'Distance').default_value = 0.02
    nt.links.new(h3, _i(bp, 'Height'))
    nt.links.new(_o(bp, 'Normal'), _i(b, 'Normal'))
    m.diffuse_color = _rgba(base)
    return m


def metal_mat(key, base, rough=0.4, rust=0.4, metallic=1.0):
    m = _newmat(MAT_PREFIX + key)
    nt = m.node_tree
    out = _n(nt, 'ShaderNodeOutputMaterial', 1200, 0)
    b = _n(nt, 'ShaderNodeBsdfPrincipled', 900, 0)
    nt.links.new(_o(b, 'BSDF'), _i(out, 'Surface'))
    co = _o(_n(nt, 'ShaderNodeTexCoord', -1200, 0), 'Object')
    n1 = _noise(nt, -900, 300, co, 6.0, 8, 0.6)
    r1 = _ramp(nt, -600, 300, [(0.3, _rgba([x * 0.6 for x in base])), (0.7, _rgba(base))])
    nt.links.new(_o(n1, 'Fac'), _i(r1, 'Fac'))
    n3 = _noise(nt, -900, 0, co, 3.0, 10, 0.7)
    lo = 0.68 - 0.1 * rust
    r3 = _ramp(nt, -600, 0, [(lo, (0, 0, 0, 1)), (lo + 0.1, (1, 1, 1, 1))])
    nt.links.new(_o(n3, 'Fac'), _i(r3, 'Fac'))
    c = _mixc(nt, -200, 200, _o(r3, 'Color'), _o(r1, 'Color'), (0.07, 0.035, 0.015, 1))
    nt.links.new(c, _i(b, 'Base Color'))
    mt = _math(nt, 100, -100, 'SUBTRACT', metallic, _o(r3, 'Color'))
    nt.links.new(mt, _i(b, 'Metallic'))
    rr = _math(nt, 100, -250, 'MULTIPLY', _o(n1, 'Fac'), 0.25)
    rr2 = _math(nt, 300, -250, 'ADD', rr, rough - 0.1)
    rr3 = _math(nt, 500, -250, 'ADD', rr2, _math(nt, 300, -400, 'MULTIPLY', _o(r3, 'Color'), 0.4))
    nt.links.new(rr3, _i(b, 'Roughness'))
    n6 = _noise(nt, -900, -400, co, 50.0, 4, 0.6)
    bp = _n(nt, 'ShaderNodeBump', 600, -500)
    _i(bp, 'Strength').default_value = 0.15
    _i(bp, 'Distance').default_value = 0.02
    nt.links.new(_o(n6, 'Fac'), _i(bp, 'Height'))
    nt.links.new(_o(bp, 'Normal'), _i(b, 'Normal'))
    m.diffuse_color = _rgba(base)
    return m


def simple_mat(key, base, rough=0.5, metallic=0.0, emit=None, strength=0.0):
    m = _newmat(MAT_PREFIX + key)
    nt = m.node_tree
    out = _n(nt, 'ShaderNodeOutputMaterial', 400, 0)
    b = _n(nt, 'ShaderNodeBsdfPrincipled', 100, 0)
    nt.links.new(_o(b, 'BSDF'), _i(out, 'Surface'))
    _i(b, 'Base Color').default_value = _rgba(base)
    _i(b, 'Roughness').default_value = rough
    _i(b, 'Metallic').default_value = metallic
    if emit:
        _i(b, 'Emission Color').default_value = _rgba(emit)
        _i(b, 'Emission Strength').default_value = strength
    m.diffuse_color = _rgba(emit or base)
    return m


def build_materials():
    paint_mat('armor', base=(0.07, 0.078, 0.042), base2=(0.035, 0.036, 0.024), rust=0.9, chip=1.3)
    paint_mat('armor_dark', base=(0.055, 0.06, 0.042), base2=(0.03, 0.033, 0.022), rust=1.3, chip=0.8, rough=0.6)
    paint_mat('red', base=(0.26, 0.03, 0.015), base2=(0.16, 0.02, 0.012), edge=(0.42, 0.40, 0.36), rust=0.6,
              chip=2.0, rough=0.5)
    metal_mat('metal', (0.06, 0.058, 0.055), rough=0.45, rust=0.6)
    metal_mat('steel', (0.28, 0.27, 0.26), rough=0.35, rust=0.35)
    metal_mat('rivet', (0.22, 0.15, 0.085), rough=0.45, rust=0.3)
    simple_mat('hole', (0.008, 0.008, 0.008), rough=0.9)
    simple_mat('glass', (0.02, 0.025, 0.03), rough=0.08, metallic=0.3)
    simple_mat('glow', (0.05, 0.03, 0.01), rough=0.3, emit=(1.0, 0.55, 0.18), strength=14.0)
    simple_mat('muzzle', (0.05, 0.02, 0.01), rough=0.3, emit=(1.0, 0.32, 0.06), strength=6.0)


# ---------------- objects ----------------

def finish(part, pivot, coll, parent=None, parent_pivot=None):
    pv = Vector(pivot) + part.off
    if parent is not None:
        parent_pivot = Vector(parent.get('pivot_world', (0, 0, 0)))
    bmesh.ops.translate(part.bm, vec=-pv, verts=part.bm.verts)
    old = bpy.data.objects.get(part.name)
    if old:
        bpy.data.objects.remove(old, do_unlink=True)
    me = bpy.data.meshes.new(part.name)
    part.bm.to_mesh(me)
    part.bm.free()
    # compact material slots to the ones actually used
    idx = [0] * len(me.polygons)
    me.polygons.foreach_get('material_index', idx)
    used = sorted(set(idx))
    remap = {u: k for k, u in enumerate(used)}
    me.polygons.foreach_set('material_index', [remap[i] for i in idx])
    for u in used:
        me.materials.append(bpy.data.materials[MAT_PREFIX + MATS[u]])
    me.polygons.foreach_set('use_smooth', [True] * len(me.polygons))
    if hasattr(me, 'set_sharp_from_angle'):
        me.set_sharp_from_angle(angle=D2R(32))
    me.update()
    ob = bpy.data.objects.new(part.name, me)
    coll.objects.link(ob)
    if parent is not None:
        ob.parent = parent
        ob.location = pv - Vector(parent_pivot)
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

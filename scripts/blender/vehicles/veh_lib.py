# Vehicles for the post-war mech outpost: shared library.
# Reuses mech_lib3 (list-based Part mesh builder + weathered paint shaders) so the vehicles share the mech's look.
# Adds: VEH_ materials (olive drab, canvas, glass, tyres, burnt metal), a height+noise mud/dust overlay,
# revolved wheels with lug tread and bolted rims, canvas covers (subdivision + noise displace), text decals,
# vehicle roots / finish with a 'hz' dirt-height attribute, smart-UV and FBX helpers.
import bpy, bmesh, math, random, os, sys, importlib
from mathutils import Vector, Matrix, noise as mnoise

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.dirname(HERE)
ROOT = os.path.dirname(SCRIPTS)
for _p in (SCRIPTS, HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)
import mech_lib3 as L

importlib.reload(L)
from mech_lib3 import T, rot, S, P, PF, frame, seg_rot, nrm, outline, inset, Part, D2R, convex2, hull_faces

L.PREFIX = 'VEH_'
for _k in ('tire', 'canvas', 'lens', 'chrome', 'decal', 'tail', 'amber', 'burnt', 'char', 'rust', 'shard',
           'plastic', 'seat', 'ash'):
    if _k not in L.MATS:
        L.MATS.append(_k)

MATNAME = {
    'armor': 'VEH_paint_olive', 'armor_dark': 'VEH_paint_olive_dark', 'red': 'VEH_paint_red',
    'metal': 'VEH_metal_dark', 'steel': 'VEH_steel', 'brass': 'VEH_brass', 'hole': 'VEH_cavity',
    'glass': 'VEH_glass', 'glow': 'VEH_glow', 'muzzle': 'VEH_muzzle', 'rubber': 'VEH_rubber',
    'joint': 'VEH_joint', 'tire': 'VEH_tire', 'canvas': 'VEH_canvas', 'lens': 'VEH_lens_clear',
    'chrome': 'VEH_reflector', 'decal': 'VEH_decal_white', 'tail': 'VEH_lens_red', 'amber': 'VEH_lens_amber',
    'burnt': 'VEH_burnt_body', 'char': 'VEH_charred', 'rust': 'VEH_rust', 'shard': 'VEH_glass_shard',
    'plastic': 'VEH_vinyl_window', 'seat': 'VEH_seat_canvas', 'ash': 'VEH_ash',
}
FONT = '/System/Library/Fonts/Supplemental/DIN Condensed Bold.ttf'
EXPORT_DIR = os.path.join(ROOT, 'export', 'vehicles')
RENDER_DIR = os.path.join(ROOT, 'renders')
BLEND_OUT = os.path.join(ROOT, 'vehicles.blend')
MECH_BLEND = os.path.join(ROOT, 'heavy_mech_v3.blend')

_n, _i, _o, _ramp, _noise, _map, _math, _mixc, _attr = (L._n, L._i, L._o, L._ramp, L._noise, L._map, L._math,
                                                       L._mixc, L._attr)

class Part(L.Part):
    """closed-mesh Part for destructible vehicles: slabs always get their bottom cap, frames their base ring, and every
    primitive is recorded as a block so whole primitives can be moved into separate parts (split_part)."""

    def __init__(self, name, M=None):
        super().__init__(name, M)
        self.blocks = []

    def add(self, verts, faces, mat, m=None, wear=0.0):
        v0, f0 = len(self.V), len(self.F)
        super().add(verts, faces, mat, m, wear)
        self.blocks.append((v0, len(self.V), f0, len(self.F)))

    def pslab(self, m, o, t, cham=0.04, mat='armor', bottom=True, side_wear=0.45):
        return super().pslab(m, o, t, cham, mat, True, side_wear)

    def pframe(self, m, outer, inner, t, mat='armor', cham=0.03):
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
            faces.append((j, i, 5 * n + i, 5 * n + j))  # base ring -> closed
            wear.append(0.0)
        self.add(verts, faces, mat, m, wear)


def split_part(src, name, pred):
    """move whole primitives of src whose world bbox satisfies pred(lo, hi) into a new Part 'name'"""
    dst = Part(name, Matrix.Identity(4))
    keep = Part(src.name, src.M)
    for v0, v1, f0, f1 in src.blocks:
        pts = src.V[v0:v1]
        if not pts:
            continue
        lo = Vector((min(q.x for q in pts), min(q.y for q in pts), min(q.z for q in pts)))
        hi = Vector((max(q.x for q in pts), max(q.y for q in pts), max(q.z for q in pts)))
        tgt = dst if pred(lo, hi) else keep
        b0, c0 = len(tgt.V), len(tgt.F)
        tgt.V.extend(pts)
        tgt.VP.extend(src.VP[v0:v1])
        tgt.F.extend(tuple(i - v0 + b0 for i in f) for f in src.F[f0:f1])
        tgt.FM.extend(src.FM[f0:f1])
        tgt.FW.extend(src.FW[f0:f1])
        tgt.blocks.append((b0, len(tgt.V), c0, len(tgt.F)))
    src.V, src.VP, src.F, src.FM, src.FW, src.blocks = keep.V, keep.VP, keep.F, keep.FM, keep.FW, keep.blocks
    return dst


def in_box(lo_lim, hi_lim):
    """predicate for split_part: primitive bbox fully inside the box"""
    a, b = Vector(lo_lim), Vector(hi_lim)
    return lambda lo, hi: all(a[i] <= lo[i] and hi[i] <= b[i] for i in range(3))


def open_edges(ob):
    """number of non-manifold (boundary / >2 faces) edges of a mesh object; 0 = closed"""
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    k = sum(1 for e in bm.edges if len(e.link_faces) != 2)
    bm.free()
    return k


def _close_holes(bm):
    """fill remaining boundary loops (flat decals, open caps) with faces oriented and textured like their neighbour"""
    be = [e for e in bm.edges if e.is_boundary]
    if not be:
        return 0
    res = bmesh.ops.holes_fill(bm, edges=be, sides=0)
    flip = []
    for f in res['faces']:
        for lp in f.loops:
            e = lp.edge
            nb = [l2 for l2 in e.link_loops if l2.face is not f]
            if nb:
                f.material_index = nb[0].face.material_index
                if nb[0].vert == lp.vert:  # same edge direction -> inconsistent winding
                    flip.append(f)
                break
    if flip:
        bmesh.ops.reverse_faces(bm, faces=flip)
    return len(res['faces'])


# ======================================================================= burnt variant (for the destruction VFX)
def burn_material(mat, amount=1.0, soot=0.9, suffix='_burnt'):
    """Burnt copy of a material: base colour darkened toward scorched brown-black + soot noise blotches + rougher,
    non-metal. The node 'burn_amount' (Value, 0..1) can be keyframed. Returns the cached copy if it exists."""
    name = mat.name + suffix
    m = bpy.data.materials.get(name)
    if m is not None:
        return m
    m = mat.copy()
    m.name = name
    nt = m.node_tree
    b = next((n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED'), None)
    if b is None:
        return m
    amt = _n(nt, 'ShaderNodeValue', -1500, 900)
    amt.name = amt.label = 'burn_amount'
    amt.outputs[0].default_value = amount
    tc = _n(nt, 'ShaderNodeTexCoord', -1700, 700)
    nz = _noise(nt, -1300, 700, _o(tc, 'Object'), 3.5, 5.0, 0.62)
    sm = _ramp(nt, -1100, 700, [(0.38, (0, 0, 0, 1)), (0.62, (1, 1, 1, 1))], nz)
    bc = b.inputs['Base Color']
    src = bc.links[0].from_socket if bc.is_linked else tuple(bc.default_value)
    dark = _mixc(nt, _o(amt, 'Value'), src, (0.11, 0.085, 0.07), 'MULTIPLY', -900, 800)
    sootf = _math(nt, 'MULTIPLY', sm, soot, x=-900, y=600)
    sootf = _math(nt, 'MULTIPLY', sootf, _o(amt, 'Value'), x=-750, y=600)
    out = _mixc(nt, sootf, dark, (0.008, 0.0075, 0.007), 'MIX', -600, 800)
    nt.links.new(out, bc)
    for key, val in (('Roughness', 0.93), ('Metallic', 0.0)):
        sk = b.inputs.get(key)
        if sk is not None:
            for lk in list(sk.links):
                nt.links.remove(lk)
            sk.default_value = val
    return m


def burn_objects(objs, amount=1.0, soot=0.9):
    """swap every material slot of the given objects to its burnt variant (burn_material)"""
    for o in objs:
        if o.type != 'MESH':
            continue
        for i, mt in enumerate(o.data.materials):
            if mt is not None and not mt.name.endswith('_burnt'):
                o.data.materials[i] = burn_material(mt, amount, soot)



# ======================================================================= materials
def _c(c):
    return (c[0], c[1], c[2], 1.0)


def _pr(m):
    return next(n for n in m.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')


def _src(sock):
    return sock.links[0].from_socket if sock.is_linked else None


def _fmix(nt, fac, a, b, x=0, y=0):
    mx = _n(nt, 'ShaderNodeMix', x, y, data_type='FLOAT', clamp_factor=True)
    for ident, val in (('Factor_Float', fac), ('A_Float', a), ('B_Float', b)):
        if isinstance(val, (int, float)):
            _i(mx, ident).default_value = val
        else:
            nt.links.new(val, _i(mx, ident))
    return _o(mx, 'Result_Float')


def _mr(nt, v, a, b, x=0, y=0, smooth=True):
    """0 at v=a .. 1 at v=b (a > b allowed -> inverted)"""
    m = _n(nt, 'ShaderNodeMapRange', x, y)
    m.interpolation_type = 'SMOOTHSTEP' if smooth else 'LINEAR'
    nt.links.new(v, _i(m, 'Value'))
    _i(m, 'From Min').default_value = a
    _i(m, 'From Max').default_value = b
    _i(m, 'To Min').default_value = 0.0
    _i(m, 'To Max').default_value = 1.0
    return _o(m, 'Result')


def _base(name):
    old = bpy.data.materials.get(name)
    if old:
        bpy.data.materials.remove(old)
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = _n(nt, 'ShaderNodeOutputMaterial', 1400, 0)
    b = _n(nt, 'ShaderNodeBsdfPrincipled', 1100, 0)
    nt.links.new(_o(b, 'BSDF'), _i(out, 'Surface'))
    co = _o(_n(nt, 'ShaderNodeTexCoord', -1400, 0), 'Object')
    return m, nt, b, co


def _bump(nt, h, strength, dist, b, x=900, y=-600):
    bp = _n(nt, 'ShaderNodeBump', x, y)
    _i(bp, 'Strength').default_value = strength
    _i(bp, 'Distance').default_value = dist
    nt.links.new(h, _i(bp, 'Height'))
    nt.links.new(_o(bp, 'Normal'), b.inputs['Normal'])
    return bp


def _upmask(nt, a=0.45, b=0.95, x=-1100, y=-1500):
    g = _n(nt, 'ShaderNodeNewGeometry', x, y)
    sp = _n(nt, 'ShaderNodeSeparateXYZ', x + 200, y)
    nt.links.new(_o(g, 'Normal'), _i(sp, 'Vector'))
    return _mr(nt, _o(sp, 'Z'), a, b, x + 400, y)


def add_dirt(m, mud=1.0, dust=0.6, splash=1.0, mudc=None):
    """overlay dried mud (below the normalised mud line hz=1, noisy edge + splatter above it) and dust on
    up-facing surfaces. hz is a point attribute written by veh_finish (vertex height / vehicle mud height)."""
    nt = m.node_tree
    b = _pr(m)
    X, Y = b.location.x - 1000, b.location.y - 2600
    co = _o(_n(nt, 'ShaderNodeTexCoord', X - 900, Y), 'Object')
    hz = _attr(nt, 'hz', X - 900, Y - 250)
    nb = _noise(nt, X - 650, Y, co, 1.5, 6, 0.62)
    h = _math(nt, 'ADD', hz, _math(nt, 'MULTIPLY', _math(nt, 'SUBTRACT', nb, 0.5, False), 0.75, False), False)
    low = _mr(nt, h, 1.0, 0.55, X - 400, Y)
    patch = _mr(nt, _noise(nt, X - 650, Y - 300, co, 4.5, 8, 0.7), 0.34, 0.56, X - 400, Y - 300)
    mudm = _math(nt, 'MULTIPLY', low, _fmix(nt, patch, 0.35, 1.0))
    spl = _mr(nt, _noise(nt, X - 650, Y - 600, co, 24.0, 3, 0.55), 0.62, 0.68, X - 400, Y - 600)
    spl = _math(nt, 'MULTIPLY', spl, _mr(nt, h, 1.75, 0.95))
    mudm = _math(nt, 'MAXIMUM', mudm, _math(nt, 'MULTIPLY', spl, 0.9 * splash))
    mudm = _math(nt, 'MULTIPLY', mudm, mud)
    up = _upmask(nt, 0.4, 0.95, X - 900, Y - 900)
    nd = _mr(nt, _noise(nt, X - 650, Y - 1100, co, 2.6, 6, 0.6), 0.3, 0.72)
    dm = _math(nt, 'ADD', _math(nt, 'MULTIPLY', _math(nt, 'MULTIPLY', up, nd), 0.6 * dust), 0.07 * dust)
    nmc = _noise(nt, X - 650, Y - 1400, co, 8.0, 6, 0.6)
    stops = mudc or [(0.3, (0.062, 0.052, 0.038, 1)), (0.55, (0.135, 0.116, 0.087, 1)),
                     (0.78, (0.185, 0.162, 0.122, 1))]
    mc = _ramp(nt, X - 400, Y - 1400, stops, nmc)
    bc = b.inputs['Base Color']
    s = _src(bc)
    base = s if s is not None else tuple(bc.default_value)
    c = _mixc(nt, dm, base, (0.19, 0.172, 0.138, 1), x=X - 100, y=Y + 200)
    c = _mixc(nt, mudm, c, mc, x=X + 100, y=Y + 200)
    nt.links.new(c, bc)
    rs = b.inputs['Roughness']
    rv = _src(rs) or rs.default_value
    wet = _math(nt, 'MAXIMUM', mudm, _math(nt, 'MULTIPLY', dm, 0.8))
    nt.links.new(_fmix(nt, wet, rv, 0.94), rs)
    ms = b.inputs['Metallic']
    mv = _src(ms) or ms.default_value
    nt.links.new(_math(nt, 'MULTIPLY', mv, _math(nt, 'SUBTRACT', 1.0, mudm)), ms)
    hh = _math(nt, 'MULTIPLY', mudm, _math(nt, 'ADD', _noise(nt, X - 650, Y - 1700, co, 38.0, 4, 0.7), 0.7, False),
               False)
    bp = _n(nt, 'ShaderNodeBump', X + 300, Y - 300)
    _i(bp, 'Strength').default_value = 0.4
    _i(bp, 'Distance').default_value = 0.012
    nt.links.new(hh, _i(bp, 'Height'))
    ns = _src(b.inputs['Normal'])
    if ns is not None:
        nt.links.new(ns, _i(bp, 'Normal'))
    nt.links.new(_o(bp, 'Normal'), b.inputs['Normal'])
    return m


def glass_mat(key, tint=(0.6, 0.66, 0.64), dirt=1.0, rough=0.03, soot=0.0, trans=1.0):
    m, nt, b, co = _base(MATNAME[key])
    pv = _attr(nt, 'pv', -1400, -300)
    low = _mr(nt, pv, 0.32, 0.0, -1100, -300)
    sm = _mr(nt, _noise(nt, -1100, -600, co, 3.0, 6, 0.65), 0.55, 0.8, -850, -600)
    dm = _math(nt, 'MAXIMUM', _math(nt, 'MULTIPLY', low, 0.75), _math(nt, 'MULTIPLY', sm, 0.35))
    dm = _math(nt, 'MULTIPLY', dm, dirt)
    dc = (0.16, 0.145, 0.115, 1) if soot <= 0 else (0.02, 0.018, 0.016, 1)
    if soot > 0:
        sk = _mr(nt, _noise(nt, -1100, -900, co, 2.0, 6, 0.6), 0.35, 0.6, -850, -900)
        dm = _math(nt, 'MAXIMUM', dm, _math(nt, 'MULTIPLY', sk, soot))
    nt.links.new(_mixc(nt, dm, _c(tint), dc, x=-300, y=200), b.inputs['Base Color'])
    nt.links.new(_math(nt, 'MULTIPLY', _math(nt, 'SUBTRACT', 1.0, dm), trans), b.inputs['Transmission Weight'])
    nt.links.new(_math(nt, 'ADD', _math(nt, 'MULTIPLY', dm, 0.6), rough), b.inputs['Roughness'])
    b.inputs['IOR'].default_value = 1.5
    b.inputs['Thin Wall'].default_value = True
    m.diffuse_color = _c(tint)
    return m


def tint_lens(key, col, trans=0.55, rough=0.12):
    m, nt, b, co = _base(MATNAME[key])
    b.inputs['Base Color'].default_value = _c(col)
    b.inputs['Transmission Weight'].default_value = trans
    b.inputs['Roughness'].default_value = rough
    b.inputs['Thin Wall'].default_value = True
    _bump(nt, _noise(nt, -900, -600, co, 60, 3, 0.5), 0.08, 0.003, b)
    m.diffuse_color = _c(col)
    return m


def canvas_mat(key, base=(0.098, 0.09, 0.056), fade=0.35):
    m, nt, b, co = _base(MATNAME[key])
    n1 = _noise(nt, -1100, 400, co, 0.9, 4, 0.55)
    c = _ramp(nt, -850, 400, [(0.3, _c([v * 0.78 for v in base])), (0.7, _c([v * 1.18 for v in base]))], n1)
    st = _mr(nt, _noise(nt, -1100, 150, co, 2.4, 8, 0.7), 0.58, 0.68, -850, 150)
    c = _mixc(nt, _math(nt, 'MULTIPLY', st, 0.55), c, (0.045, 0.038, 0.026, 1), x=-600, y=300)
    pv = _attr(nt, 'pv', -1400, -300)
    lowst = _math(nt, 'MULTIPLY', _mr(nt, pv, 0.28, 0.0, -1100, -300),
                  _mr(nt, _noise(nt, -1100, -500, co, 6.0, 6, 0.6), 0.35, 0.6, -850, -500))
    c = _mixc(nt, _math(nt, 'MULTIPLY', lowst, 0.6), c, (0.06, 0.05, 0.035, 1), x=-450, y=250)
    up = _upmask(nt, 0.3, 0.95, -1100, -800)
    c = _mixc(nt, _math(nt, 'MULTIPLY', up, fade), c, _c([v * 1.45 + 0.012 for v in base]), x=-300, y=200)
    ao = _n(nt, 'ShaderNodeAmbientOcclusion', -1100, 700)
    _i(ao, 'Distance').default_value = 0.35
    rao = _ramp(nt, -850, 700, [(0.3, (0.2, 0.17, 0.13, 1)), (0.95, (1, 1, 1, 1))], _o(ao, 'AO'))
    c = _mixc(nt, 0.85, c, rao, 'MULTIPLY', x=-150, y=200)
    nt.links.new(c, b.inputs['Base Color'])
    b.inputs['Roughness'].default_value = 0.93
    b.inputs['Sheen Weight'].default_value = 0.35
    b.inputs['Sheen Tint'].default_value = (0.5, 0.48, 0.4, 1)
    # weave: two crossed band textures + fine noise
    w1 = _n(nt, 'ShaderNodeTexWave', -1100, -1100, wave_type='BANDS', bands_direction='X')
    w2 = _n(nt, 'ShaderNodeTexWave', -1100, -1300, wave_type='BANDS', bands_direction='Z')
    for w in (w1, w2):
        _i(w, 'Scale').default_value = 220.0
        nt.links.new(co, _i(w, 'Vector'))
    h = _math(nt, 'MULTIPLY', _o(w1, 'Fac'), _o(w2, 'Fac'), False)
    h = _math(nt, 'ADD', h, _math(nt, 'MULTIPLY', _noise(nt, -1100, -1500, co, 30, 4, 0.6), 0.6, False), False)
    _bump(nt, h, 0.18, 0.003, b)
    m.diffuse_color = _c(base)
    return m


def tire_mat(key):
    m, nt, b, co = _base(MATNAME[key])
    wear = _attr(nt, 'wear', -1400, -300)
    n1 = _noise(nt, -1100, 300, co, 7.0, 6, 0.6)
    c = _ramp(nt, -850, 300, [(0.3, (0.016, 0.016, 0.015, 1)), (0.7, (0.034, 0.033, 0.031, 1))], n1)
    wm = _math(nt, 'MULTIPLY', wear, _mr(nt, _noise(nt, -1100, -500, co, 14, 4, 0.6), 0.35, 0.6, -850, -500))
    c = _mixc(nt, wm, c, (0.07, 0.068, 0.064, 1), x=-500, y=200)
    nt.links.new(c, b.inputs['Base Color'])
    nt.links.new(_math(nt, 'ADD', _math(nt, 'MULTIPLY', n1, 0.15), 0.72), b.inputs['Roughness'])
    _bump(nt, _noise(nt, -1100, -800, co, 90, 3, 0.5), 0.12, 0.004, b)
    m.diffuse_color = (0.02, 0.02, 0.02, 1)
    return m


def decal_mat(key, col=(0.5, 0.48, 0.42)):
    m, nt, b, co = _base(MATNAME[key])
    nb = _noise(nt, -1100, 200, co, 16.0, 8, 0.72)
    holes = _mr(nt, nb, 0.6, 0.66, -850, 200)
    vo = _n(nt, 'ShaderNodeTexVoronoi', -1100, -100)
    try:
        vo.feature = 'DISTANCE_TO_EDGE'
    except Exception:
        pass
    _i(vo, 'Scale').default_value = 9.0
    nt.links.new(_map(nt, -1300, -100, co, (1.0, 1.0, 3.0)), _i(vo, 'Vector'))
    scr = _mr(nt, _o(vo, 'Distance'), 0.02, 0.0, -850, -100)
    scr = _math(nt, 'MULTIPLY', scr, _mr(nt, _noise(nt, -1100, -300, co, 3.0, 2, 0.5), 0.5, 0.6, -850, -300))
    gone = _math(nt, 'MAXIMUM', holes, scr)
    big = _mr(nt, _noise(nt, -1100, 500, co, 2.5, 4, 0.6), 0.62, 0.7, -850, 500)
    gone = _math(nt, 'MAXIMUM', gone, big)
    n2 = _noise(nt, -1100, 800, co, 5.0, 4, 0.6)
    c = _ramp(nt, -850, 800, [(0.3, _c([v * 0.72 for v in col])), (0.7, _c(col))], n2)
    nt.links.new(c, b.inputs['Base Color'])
    nt.links.new(_math(nt, 'SUBTRACT', 1.0, gone), b.inputs['Alpha'])
    b.inputs['Roughness'].default_value = 0.78
    m.diffuse_color = _c(col)
    return m


def _rust_color(nt, co, x=-850, y=300, sc=6.0, bright=1.0):
    n = _noise(nt, x - 250, y, co, sc, 10, 0.72)
    return _ramp(nt, x, y, [(0.3, (0.035 * bright, 0.016 * bright, 0.008 * bright, 1)),
                            (0.5, (0.095 * bright, 0.04 * bright, 0.015 * bright, 1)),
                            (0.72, (0.17 * bright, 0.075 * bright, 0.027 * bright, 1))], n), n


def rust_mat(key, bright=1.0, rough=0.82, metallic=0.2):
    m, nt, b, co = _base(MATNAME[key])
    c, n = _rust_color(nt, co, bright=bright)
    sk = _mr(nt, _noise(nt, -1100, -200, co, 2.0, 6, 0.6), 0.5, 0.68, -850, -200)
    c = _mixc(nt, _math(nt, 'MULTIPLY', sk, 0.7), c, (0.018, 0.015, 0.012, 1), x=-500, y=200)
    ao = _n(nt, 'ShaderNodeAmbientOcclusion', -1100, 700)
    _i(ao, 'Distance').default_value = 0.25
    c = _mixc(nt, 0.9, c, _ramp(nt, -850, 700, [(0.25, (0.1, 0.07, 0.05, 1)), (0.9, (1, 1, 1, 1))], _o(ao, 'AO')),
              'MULTIPLY', x=-300, y=200)
    nt.links.new(c, b.inputs['Base Color'])
    b.inputs['Roughness'].default_value = rough
    b.inputs['Metallic'].default_value = metallic
    h = _math(nt, 'ADD', _noise(nt, -1100, -700, co, 45, 6, 0.7), _math(nt, 'MULTIPLY', n, 0.6, False), False)
    _bump(nt, h, 0.35, 0.01, b)
    m.diffuse_color = (0.1, 0.045, 0.02, 1)
    return m


def burnt_mat(key, paint=(0.16, 0.2, 0.215)):
    """burnt-out car body: rust everywhere, soot/char clouds, ash on top, faded paint remnants low down"""
    m, nt, b, co = _base(MATNAME[key])
    hz = _attr(nt, 'hz', -1400, -300)
    wear = _attr(nt, 'wear', -1400, -500)
    c, n = _rust_color(nt, co, sc=5.0)
    soot_n = _noise(nt, -1100, 0, co, 1.1, 6, 0.62)
    soot = _mr(nt, soot_n, 0.42, 0.6, -850, 0)
    soot = _math(nt, 'MAXIMUM', _math(nt, 'MULTIPLY', soot, 0.85),
                 _math(nt, 'MULTIPLY', _mr(nt, hz, 1.2, 2.2, -850, -150), 0.6))
    c = _mixc(nt, soot, c, (0.014, 0.012, 0.011, 1), x=-500, y=300)
    # faded original paint, only low on the body where the fire was weaker
    hl = _math(nt, 'ADD', hz, _math(nt, 'MULTIPLY', _math(nt, 'SUBTRACT', _noise(nt, -1100, -700, co, 2.0, 6, 0.6),
                                                          0.5, False), 0.9, False), False)
    pm = _mr(nt, hl, 1.15, 0.65, -850, -700)
    blist = _mr(nt, _noise(nt, -1100, -900, co, 11.0, 8, 0.7), 0.42, 0.5, -850, -900)
    pm = _math(nt, 'MULTIPLY', pm, blist)
    pm = _math(nt, 'MULTIPLY', pm, _math(nt, 'SUBTRACT', 1.0, wear))
    pc = _ramp(nt, -850, -1100, [(0.3, _c([v * 0.7 for v in paint])), (0.7, _c(paint))],
               _noise(nt, -1100, -1100, co, 4.0, 4, 0.5))
    c = _mixc(nt, pm, c, pc, x=-350, y=250)
    up = _upmask(nt, 0.5, 0.95, -1100, -1400)
    ash = _math(nt, 'MULTIPLY', up, _mr(nt, _noise(nt, -1100, -1600, co, 3.5, 8, 0.65), 0.5, 0.62, -850, -1600))
    c = _mixc(nt, _math(nt, 'MULTIPLY', ash, 0.75), c, (0.3, 0.29, 0.27, 1), x=-200, y=200)
    ao = _n(nt, 'ShaderNodeAmbientOcclusion', -1100, 700)
    _i(ao, 'Distance').default_value = 0.4
    c = _mixc(nt, 0.9, c, _ramp(nt, -850, 700, [(0.25, (0.06, 0.045, 0.035, 1)), (0.9, (1, 1, 1, 1))],
                                 _o(ao, 'AO')), 'MULTIPLY', x=-100, y=200)
    nt.links.new(c, b.inputs['Base Color'])
    nt.links.new(_fmix(nt, pm, 0.88, 0.55), b.inputs['Roughness'])
    nt.links.new(_fmix(nt, soot, 0.25, 0.0), b.inputs['Metallic'])
    h = _math(nt, 'ADD', _noise(nt, -1100, -1900, co, 40, 6, 0.72), _math(nt, 'MULTIPLY', n, 0.8, False), False)
    h = _math(nt, 'ADD', h, _math(nt, 'MULTIPLY', pm, 0.5, False), False)
    _bump(nt, h, 0.4, 0.012, b)
    m.diffuse_color = (0.09, 0.04, 0.02, 1)
    return m


def char_mat(key):
    m, nt, b, co = _base(MATNAME[key])
    n = _noise(nt, -1100, 300, co, 7.0, 8, 0.65)
    c = _ramp(nt, -850, 300, [(0.35, (0.008, 0.008, 0.008, 1)), (0.65, (0.03, 0.028, 0.026, 1))], n)
    r, rn = _rust_color(nt, co, -850, 0, 4.0, 0.8)
    rm = _mr(nt, _noise(nt, -1100, -300, co, 2.5, 6, 0.6), 0.56, 0.66, -850, -300)
    c = _mixc(nt, rm, c, r, x=-500, y=200)
    up = _upmask(nt, 0.5, 0.95, -1100, -600)
    ash = _math(nt, 'MULTIPLY', up, _mr(nt, _noise(nt, -1100, -800, co, 4.0, 8, 0.6), 0.45, 0.6, -850, -800))
    c = _mixc(nt, ash, c, (0.22, 0.21, 0.2, 1), x=-300, y=200)
    nt.links.new(c, b.inputs['Base Color'])
    b.inputs['Roughness'].default_value = 0.92
    _bump(nt, _noise(nt, -1100, -1100, co, 30, 6, 0.75), 0.45, 0.01, b)
    m.diffuse_color = (0.02, 0.02, 0.02, 1)
    return m


def chrome_mat(key):
    m, nt, b, co = _base(MATNAME[key])
    n = _noise(nt, -1100, 300, co, 9.0, 6, 0.6)
    nt.links.new(_ramp(nt, -850, 300, [(0.3, (0.25, 0.24, 0.22, 1)), (0.7, (0.6, 0.6, 0.58, 1))], n),
                 b.inputs['Base Color'])
    b.inputs['Metallic'].default_value = 1.0
    nt.links.new(_math(nt, 'ADD', _math(nt, 'MULTIPLY', n, 0.25), 0.12), b.inputs['Roughness'])
    m.diffuse_color = (0.5, 0.5, 0.5, 1)
    return m


def plain_mat(key, col, rough=0.85, metallic=0.0, var=0.25, bump=0.15):
    m, nt, b, co = _base(MATNAME[key])
    n = _noise(nt, -1100, 300, co, 5.0, 6, 0.6)
    nt.links.new(_ramp(nt, -850, 300, [(0.3, _c([v * (1 - var) for v in col])), (0.7, _c([v * (1 + var) for v in col]))],
                       n), b.inputs['Base Color'])
    b.inputs['Roughness'].default_value = rough
    b.inputs['Metallic'].default_value = metallic
    _bump(nt, _noise(nt, -1100, -600, co, 40, 4, 0.6), bump, 0.006, b)
    m.diffuse_color = _c(col)
    return m


OLIVE = dict(dark=(0.032, 0.036, 0.022), mid=(0.074, 0.081, 0.051), light=(0.13, 0.136, 0.092))
OLIVE_DARK = dict(dark=(0.026, 0.028, 0.02), mid=(0.05, 0.053, 0.038), light=(0.082, 0.085, 0.062))


def build_materials(ao_samples=8):
    D = L.MAT_DEF
    D.update(blotch=0.22, blotch_scale=7.0, spots=0.07, chip=0.75, edge=(0.2, 0.19, 0.17), white=0.0, ao=0.9,
             ao_dist=0.5, rust=1.0, streak=1.0, brass=(0.17, 0.14, 0.1), metal=(0.03, 0.031, 0.033),
             steel=(0.16, 0.155, 0.15), steel_rough=0.45)
    made = {}

    def keep(key, m):
        old = bpy.data.materials.get(MATNAME[key])
        if old and old != m:
            bpy.data.materials.remove(old)
        m.name = MATNAME[key]
        made[key] = m

    keep('armor', L.paint_mat('armor', **OLIVE, rust=0.9, chip=0.8, streak=0.9, edge=D['edge'], rough=0.72))
    keep('armor_dark', L.paint_mat('armor_dark', **OLIVE_DARK, rust=1.1, chip=0.7, streak=1.0, edge=D['edge'],
                                   rough=0.74))
    keep('red', L.paint_mat('red', dark=(0.15, 0.022, 0.012), mid=(0.24, 0.035, 0.018), light=(0.3, 0.055, 0.028),
                            edge=D['edge'], rust=0.7, chip=1.0, streak=0.8, rough=0.6, white=0.0))
    keep('metal', L.metal_mat('metal', D['metal'], rough=0.5, rust=0.6, edge=(0.16, 0.155, 0.15)))
    keep('steel', L.metal_mat('steel', D['steel'], rough=D['steel_rough'], rust=0.4, metallic=1.0, grime=0.7))
    keep('brass', L.metal_mat('brass', D['brass'], rough=0.42, rust=0.45, metallic=1.0, grime=0.9))
    keep('hole', L.simple_mat('hole', (0.006, 0.006, 0.006), rough=0.9))
    keep('rubber', plain_mat('rubber', (0.02, 0.02, 0.019), rough=0.8))
    made['glass'] = glass_mat('glass')
    made['lens'] = glass_mat('lens', tint=(0.85, 0.86, 0.82), dirt=0.6, rough=0.06)
    made['shard'] = glass_mat('shard', tint=(0.45, 0.5, 0.48), dirt=1.0, rough=0.08, soot=0.8)
    made['plastic'] = glass_mat('plastic', tint=(0.3, 0.29, 0.22), dirt=0.8, rough=0.22, trans=0.45)
    made['tail'] = tint_lens('tail', (0.42, 0.02, 0.012))
    made['amber'] = tint_lens('amber', (0.55, 0.24, 0.02))
    made['chrome'] = chrome_mat('chrome')
    made['tire'] = tire_mat('tire')
    made['canvas'] = canvas_mat('canvas')
    made['seat'] = canvas_mat('seat', base=(0.05, 0.052, 0.036), fade=0.15)
    made['decal'] = decal_mat('decal')
    made['burnt'] = burnt_mat('burnt')
    made['char'] = char_mat('char')
    made['rust'] = rust_mat('rust')
    made['ash'] = plain_mat('ash', (0.2, 0.19, 0.18), rough=0.95, var=0.4, bump=0.3)
    keep('glow', L.simple_mat('glow', (0.06, 0.03, 0.01), rough=0.3, emit=(1.0, 0.42, 0.08), strength=4.0))
    # dirt overlay
    for k, kw in (('armor', {}), ('armor_dark', {}), ('red', {}), ('metal', dict(dust=0.4)),
                  ('steel', dict(dust=0.3, mud=0.8)), ('rubber', {}), ('tire', dict(mud=1.0, dust=0.8)),
                  ('canvas', dict(mud=0.8, dust=0.5)), ('seat', dict(mud=0.4, dust=0.6)), ('decal', {}),
                  ('burnt', dict(mud=0.35, dust=0.8, splash=0.3)), ('rust', dict(mud=0.5, dust=0.5)),
                  ('char', dict(mud=0.2, dust=0.3, splash=0.0))):
        add_dirt(made[k], **kw)
    for m in bpy.data.materials:
        if m.node_tree:
            for nd in m.node_tree.nodes:
                if nd.type == 'AMBIENT_OCCLUSION':
                    nd.samples = ao_samples
    return made


# ======================================================================= geometry helpers
def rev_geo(prof, n, phase=0.0, closed=False):
    """revolve profile [(x_axial, r)] around local X. Walk the profile so that the outside is on the left in (x, r)."""
    verts, faces, idx = [], [], []
    for x, r in prof:
        if r < 1e-6:
            idx.append([len(verts)] * n)
            verts.append((x, 0.0, 0.0))
        else:
            row = []
            for i in range(n):
                a = 2 * math.pi * i / n + phase
                row.append(len(verts))
                verts.append((x, r * math.cos(a), r * math.sin(a)))
            idx.append(row)
    for k in range(len(prof) if closed else len(prof) - 1):
        A, B = idx[k], idx[(k + 1) % len(prof)]
        for i in range(n):
            j = (i + 1) % n
            f = []
            for v in (A[i], A[j], B[j], B[i]):
                if v not in f:
                    f.append(v)
            if len(f) >= 3:
                faces.append(tuple(f))
    return verts, faces


def _side_prof(prof, s):
    return prof if s > 0 else [(-x, r) for x, r in reversed(prof)]


def wheel(part, M, R, W, side=1, style='mil', n=32, lugs=18, lug_h=None, rim_r=None, tire=True, flat=0.0,
          nuts=8, rim_mat='armor_dark', tire_mat='tire', lug_tilt=30.0, beadlock=None, holes=6, dent=0.0):
    """wheel in local frame M: axle = local X, outer face toward +X*side. Tyre (revolved carcass + chevron lugs),
    disc rim with lug nuts, optional beadlock ring with bolts."""
    s = 1 if side >= 0 else -1
    hw = W / 2
    lug_h = R * 0.055 if lug_h is None else lug_h
    rr = rim_r or R * 0.6
    Rt = R - lug_h
    if beadlock is None:
        beadlock = style == 'mil'
    if tire:
        sh = R * 0.07
        half = [(-hw * 0.80, rr * 0.985), (-hw * 0.95, rr + 0.07 * (Rt - rr)), (-hw * 1.03, rr + 0.13 * (Rt - rr)),
                (-hw * 1.0, rr + 0.22 * (Rt - rr)), (-hw * 1.04, rr + 0.55 * (Rt - rr)), (-hw * 0.98, Rt - sh),
                (-hw * 0.86, Rt - sh * 0.22), (-hw * 0.6, Rt), (0, Rt + 0.003)]
        prof = half + [(-x, r) for x, r in reversed(half[:-1])]
        v, f = rev_geo(prof, n, closed=True)
        if flat > 0:
            zf = -(R - flat)
            nv = []
            for x, y, z in v:
                if z < zf:
                    k = (zf - z) / max(R - flat, 1e-3)
                    z = zf - (zf - z) * 0.12
                    x *= 1.0 + 0.5 * min(1.0, k * 4)
                rad = math.hypot(y, z)
                if rad > rr * 1.05:
                    j = 0.012 * mnoise.noise(Vector((x * 9, y * 9, z * 9)))
                    y *= 1 + j
                    z *= 1 + j
                nv.append((x, y, z))
            v = nv
        part.add(v, f, tire_mat, M, 0.0)
        if lugs and flat <= 0:
            emb = sh + 0.004
            pitch = 360.0 / lugs
            wt = 2 * math.pi * Rt / lugs * 0.42
            x_in, x_out = hw * 0.07, hw * 1.0
            d = (x_out - x_in) * math.tan(D2R(lug_tilt))
            for k in range(lugs):
                for hs in (-1, 1):
                    a = k * pitch + (pitch * 0.5 if hs > 0 else 0.0)
                    pts = [(x_in, 0), (x_out, d), (x_out, d + wt), (x_in, wt)]
                    pts = [(x, y - (d + wt) / 2) for x, y in pts]
                    if hs < 0:
                        pts = [(-x, y) for x, y in reversed(pts)]
                    part.pslab(M @ rot(a, 0, 0) @ T((0, 0, Rt - emb)), pts, lug_h + emb,
                               cham=min(0.012, lug_h * 0.35), mat=tire_mat, side_wear=0.25)
    # ---- rim
    if style == 'civil':
        disc = [(hw * 0.86, rr + 0.022), (hw * 0.82, rr - 0.004), (hw * 0.4, rr * 0.9), (hw * 0.28, rr * 0.62),
                (hw * 0.3, rr * 0.42), (hw * 0.46, rr * 0.34), (hw * 0.5, rr * 0.2), (hw * 0.5, 0.0)]
        if not tire:
            barrel = [(-hw * 0.9, rr + 0.025), (-hw * 0.8, rr + 0.004), (-hw * 0.6, rr - 0.025), (hw * 0.6, rr - 0.025),
                      (hw * 0.8, rr + 0.004), (hw * 0.9, rr + 0.025)]
            v, f = rev_geo(_side_prof(barrel, s), n)
            part.add(v, f, rim_mat, M, 0.3)
            # flange lips (both sides)
            for sx in (-1, 1):
                lip = [(sx * hw * 0.9, rr + 0.025), (sx * hw * 0.93, rr + 0.03)] if sx > 0 else \
                      [(sx * hw * 0.93, rr + 0.03), (sx * hw * 0.9, rr + 0.025)]
                v, f = rev_geo(_side_prof(lip, s), n)
                part.add(v, f, rim_mat, M, 1.0)
    else:
        disc = [(hw * 0.80, rr + 0.028), (hw * 0.86, rr + 0.012), (hw * 0.84, rr - 0.01), (hw * 0.62, rr * 0.93),
                (hw * 0.46, rr * 0.74), (hw * 0.48, rr * 0.46), (hw * 0.5, rr * 0.4), (hw * 0.62, rr * 0.37),
                (hw * 0.66, rr * 0.27), (hw * 0.8, rr * 0.24), (hw * 0.86, rr * 0.16), (hw * 0.87, 0.0)]
    inner = [(-hw * 0.66, 0.0), (-hw * 0.68, rr * 0.95), (-hw * 0.80, rr * 0.99)]
    v, f = rev_geo(_side_prof(disc + inner, s), n, closed=True)  # dish + back face + barrel = closed rim
    if dent > 0:
        v = [(x, y, max(z, -(rr + 0.022) * (1 - dent)) if z < 0 else z) for x, y, z in v]
    part.add(v, f, rim_mat, M, [0.9 if k < n * 2 else 0.25 for k in range(len(f))])
    if style == 'civil':
        nut_x, nut_r = hw * 0.47, rr * 0.27
    else:
        nut_x, nut_r = hw * 0.49, rr * 0.43
    for k in range(nuts):
        a = 2 * math.pi * k / nuts
        part.bolt(M @ T((s * nut_x, 0, 0)) @ rot(0, 90 * s, 0) @ T((nut_r * math.cos(a), nut_r * math.sin(a), 0)),
                  r=rr * 0.065, h=rr * 0.075, mat='steel')
    hx = hw * (0.47 if style != 'civil' else 0.36)
    hr = rr * (0.6 if style != 'civil' else 0.72)
    for k in range(holes):
        a = 2 * math.pi * (k + 0.5) / holes
        part.cyl(M @ T((s * (hx + 0.004), 0, 0)) @ rot(0, 90 * s, 0) @ T((hr * math.cos(a), hr * math.sin(a), 0)),
                 rr * (0.09 if style != 'civil' else 0.12), 0.004, mat='hole', n=10)
    if beadlock:
        bz = hw * 0.85
        part.ring(M @ T((s * bz, 0, 0)) @ rot(0, 90 * s, 0), rr + 0.04, rr - 0.012, 0.026, mat=rim_mat, n=n,
                  wear_top=0.9)
        nb = 12 if R < 0.5 else 16
        for k in range(nb):
            a = 2 * math.pi * k / nb
            part.bolt(M @ T((s * (bz + 0.013), 0, 0)) @ rot(0, 90 * s, 0) @
                      T(((rr + 0.014) * math.cos(a), (rr + 0.014) * math.sin(a), 0)), r=0.011, h=0.012,
                      mat='steel')


# ---------------------------------------------------------------- misc shape helpers
def beam(part, p1, p2, w, h, mat='armor', up=(0, 0, 1), bev=0.01):
    p1, p2 = Vector(p1), Vector(p2)
    d = p2 - p1
    part.box(PF((p1 + p2) / 2, d, up), (w, h, d.length), mat=mat, bev=bev)


def rod(part, p1, p2, r, mat='metal', n=8, caps=True):
    p1, p2 = Vector(p1), Vector(p2)
    d = p2 - p1
    part.cyl(T((p1 + p2) / 2) @ seg_rot(d), r, d.length, mat=mat, n=n, caps=caps)


def yz_frame(x, side):
    """placement for polygons drawn in the (y, z) side-view plane, extruded toward +X*side from x"""
    return T((x, 0, 0)) @ frame((side, 0, 0), (0, 0, 1))


def yz_poly(poly, side):
    """side-view polygon (y,z) CCW -> local coords of yz_frame(side)"""
    if side > 0:
        return list(poly)
    return [(-y, z) for y, z in reversed(poly)]


def arc(cx, cy, r, a0, a1, n):
    return [(cx + r * math.cos(D2R(a0 + (a1 - a0) * k / n)), cy + r * math.sin(D2R(a0 + (a1 - a0) * k / n)))
            for k in range(n + 1)]


def round_rect(w, h, r, n=3):
    """CCW rounded rectangle centered at 0"""
    pts = []
    for cx, cy, a0 in ((w / 2 - r, -h / 2 + r, -90), (w / 2 - r, h / 2 - r, 0), (-w / 2 + r, h / 2 - r, 90),
                       (-w / 2 + r, -h / 2 + r, 180)):
        pts += arc(cx, cy, r, a0, a0 + 90, n)
    return pts


def headlight(part, m, r, depth=0.08, lens='lens', guard=True, housing='armor'):
    """round lamp in placement m facing +Z (local)"""
    part.cyl(m @ T((0, 0, -depth / 2)), r * 1.12, depth, mat=housing, n=20, r2=r * 1.18, bev=0.008)
    part.ring(m @ T((0, 0, 0.004)), r * 1.16, r * 0.95, 0.016, mat='armor_dark', n=20)
    part.cyl(m @ T((0, 0, -0.03)), r * 0.95, 0.02, mat='chrome', n=20, r2=r * 0.5)
    part.cyl(m @ T((0, 0, -0.004)), r * 0.95, 0.006, mat=lens, n=20)
    if guard:
        for dx in (-0.35, 0.35):
            part.box(m @ T((dx * r, 0, 0.03)), (0.012, r * 2.3, 0.012), mat='metal', bev=0.0)
        part.ring(m @ T((0, 0, 0.022)), r * 1.15, r * 1.08, 0.012, mat='metal', n=16)


def mirror(part, base, tip, size=(0.16, 0.22, 0.03), facing=(0, 1, 0)):
    """arm from base to tip + rectangular mirror head at tip; the glass faces 'facing' (size = w, h, thickness)"""
    rod(part, base, tip, 0.012, 'metal', 6)
    m = PF(tip, facing, (0, 0, 1))
    part.box(m, size, mat='armor_dark', bev=0.008)
    part.box(m @ T((0, 0, size[2] / 2 + 0.001)), (size[0] * 0.86, size[1] * 0.86, 0.003), mat='chrome', bev=0.0)


def text_geo(text, size, font=FONT, res=2, spacing=1.05):
    cu = bpy.data.curves.new('tmp_txt', 'FONT')
    cu.body = text
    cu.font = bpy.data.fonts.load(font, check_existing=True)
    cu.size = size
    cu.align_x = 'CENTER'
    cu.align_y = 'CENTER'
    cu.resolution_u = res
    cu.space_character = spacing
    ob = bpy.data.objects.new('tmp_txt', cu)
    bpy.context.scene.collection.objects.link(ob)
    dg = bpy.context.evaluated_depsgraph_get()
    ev = ob.evaluated_get(dg)
    me = ev.to_mesh()
    verts = [v.co.copy() for v in me.vertices]
    faces = [tuple(p.vertices) for p in me.polygons]
    ev.to_mesh_clear()
    bpy.data.objects.remove(ob, do_unlink=True)
    bpy.data.curves.remove(cu)
    return verts, faces


def decal_text(part, text, m, size, mat='decal', **kw):
    """flat text in local XY of placement m (normal +Z), centred"""
    v, f = text_geo(text, size, **kw)
    part.add(v, f, mat, m @ T((0, 0, 0.003)), 0.0)


def emblem(part, m, r, mat='decal'):
    """generic outpost emblem: ring + downward chevron"""
    part.ring(m @ T((0, 0, 0.003)), r, r * 0.82, 0.002, mat=mat, n=24, wear_top=0.0)
    ch = [(-r * 0.55, r * 0.25), (0, -r * 0.3), (r * 0.55, r * 0.25), (r * 0.55, r * 0.02), (0, -r * 0.52),
          (-r * 0.55, r * 0.02)]
    ch = [ch[1], ch[2], ch[3], ch[4], ch[5], ch[0]]
    part.add([(x, y, 0.004) for x, y in ch], [(5, 0, 4), (0, 3, 4), (0, 1, 3), (1, 2, 3)], mat, m, 0.0)


# ---------------------------------------------------------------- canvas cover
def _resample(pts, k):
    seg = [0.0]
    for a, b in zip(pts, pts[1:]):
        seg.append(seg[-1] + math.dist(a, b))
    Ltot = seg[-1]
    out = []
    for i in range(k + 1):
        t = Ltot * i / k
        j = max(0, min(len(pts) - 2, next((q for q in range(len(seg) - 1) if seg[q + 1] >= t), len(seg) - 2)))
        u = (t - seg[j]) / max(seg[j + 1] - seg[j], 1e-9)
        out.append((pts[j][0] + (pts[j + 1][0] - pts[j][0]) * u, pts[j][1] + (pts[j + 1][1] - pts[j][1]) * u, t / Ltot))
    return out


def canvas_cover(part, section, y0, y1, nu=36, nv=28, bows=(), sag=0.05, fold=0.018, seed=1, zscale=None,
                 skip=None, matf=None, ends=(True, True), end_bulge=0.02, sub=1, disp=0.012, solid=0.0,
                 mat='canvas', hem=True):
    """tarp over bows. section: polyline [(x,z)] from left-bottom over the top to right-bottom.
    zscale(y)->k scales the section height above its bottom. skip(x,y,z)->bool removes faces (openings),
    matf(x,y,z,side)->material key ('canvas'/'plastic'). Built as one connected mesh, then Subdivision + Displace
    (clouds noise) modifiers are evaluated and the result is added to the Part."""
    rnd = random.Random(seed)
    sec = _resample(section, nu)
    zb = min(p[1] for p in section)
    nrm2 = []
    for i in range(nu + 1):
        a = sec[max(0, i - 1)]
        b = sec[min(nu, i + 1)]
        tx, tz = b[0] - a[0], b[1] - a[1]
        ln = math.hypot(tx, tz) or 1.0
        nrm2.append((-tz / ln, tx / ln))
    bl = sorted([y0, y1] + list(bows))
    bm = bmesh.new()
    grid = []
    off = Vector((rnd.uniform(0, 50), rnd.uniform(0, 50), rnd.uniform(0, 50)))
    for j in range(nv + 1):
        y = y0 + (y1 - y0) * j / nv
        k = next(q for q in range(len(bl) - 1) if bl[q] <= y + 1e-9 and y <= bl[q + 1] + 1e-9)
        t = (y - bl[k]) / max(bl[k + 1] - bl[k], 1e-6)
        sg = math.sin(math.pi * t)
        zk = zscale(y) if zscale else 1.0
        row = []
        for i in range(nu + 1):
            x, z, u = sec[i]
            z = zb + (z - zb) * zk
            nx, nz = nrm2[i]
            edge = min(1.0, min(u, 1 - u) / 0.12)
            w = (0.3 + 0.7 * max(0.0, nz)) * edge
            dn = -sag * sg * w
            q = Vector((u * 6.0, y * 4.2, 0)) + off
            dn += fold * (mnoise.noise(q) * 0.8 + 0.45 * mnoise.noise(Vector((x * 7, y * 7, z * 7)) + off))
            if hem and min(u, 1 - u) < 0.02:
                dn += 0.012
            p = Vector((x + nx * dn, y, z + nz * dn))
            row.append(bm.verts.new(p))
        grid.append(row)
    fmat = {}

    def face(vs, key):
        try:
            f = bm.faces.new(vs)
        except ValueError:
            return None
        fmat[f] = key
        return f

    for j in range(nv):
        for i in range(nu):
            vs = (grid[j][i], grid[j][i + 1], grid[j + 1][i + 1], grid[j + 1][i])
            c = sum((v.co for v in vs), Vector()) / 4
            if skip and skip(c.x, c.y, c.z):
                continue
            face(vs, matf(c.x, c.y, c.z, 'side') if matf else mat)
    # end panels: rings toward the centre of the opening, connected to the end rows
    for e, (on, row) in enumerate(zip(ends, (grid[0], grid[-1]))):
        if not on:
            continue
        sgn = -1 if e == 0 else 1
        a, b = row[0].co, row[-1].co
        nb_ = max(4, int((b - a).length / 0.25))
        bottom = [bm.verts.new(a + (b - a) * (q / nb_)) for q in range(nb_ - 1, 0, -1)]
        loop = list(row) + bottom
        cen = sum((v.co for v in loop), Vector()) / len(loop)
        rings = [loop]
        for f_ in (0.34, 0.67):
            rr_ = []
            for v in loop:
                p = v.co.lerp(cen, f_)
                bul = end_bulge * math.sin(math.pi * f_) + fold * 0.6 * mnoise.noise(p * 5 + off)
                rr_.append(bm.verts.new(p + Vector((0, sgn * bul, 0))))
            rings.append(rr_)
        cv = bm.verts.new(cen + Vector((0, sgn * end_bulge, 0)))
        for r0, r1 in zip(rings, rings[1:]):
            for i in range(len(loop)):
                j = (i + 1) % len(loop)
                vs = (r0[i], r0[j], r1[j], r1[i])
                c = sum((v.co for v in vs), Vector()) / 4
                face(vs, matf(c.x, c.y, c.z, 'end') if matf else mat)
        last = rings[-1]
        for i in range(len(loop)):
            j = (i + 1) % len(loop)
            c = (last[i].co + last[j].co + cv.co) / 3
            face((last[i], last[j], cv), matf(c.x, c.y, c.z, 'end') if matf else mat)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    tops = [f for f in bm.faces if f.calc_center_median().z > zb + 0.5 * (max(p[1] for p in section) - zb)]
    if tops and sum(f.normal.z for f in tops) < 0:
        for f in bm.faces:
            f.normal_flip()
    keys = sorted(set(fmat.values()))
    for f, k in fmat.items():
        if f.is_valid:
            f.material_index = keys.index(k)
    bm.verts.ensure_lookup_table()
    loose = [v for v in bm.verts if not v.link_faces]
    bmesh.ops.delete(bm, geom=loose, context='VERTS')
    me = bpy.data.meshes.new('tmp_canvas')
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new('tmp_canvas', me)
    bpy.context.scene.collection.objects.link(ob)
    if sub > 0:
        md = ob.modifiers.new('sub', 'SUBSURF')
        md.levels = sub
        md.render_levels = sub
    if disp > 0:
        tex = bpy.data.textures.new('tmp_folds', 'CLOUDS')
        tex.noise_scale = 0.22
        tex.noise_depth = 2
        md = ob.modifiers.new('disp', 'DISPLACE')
        md.texture = tex
        md.strength = disp
        md.mid_level = 0.5
        md.texture_coords = 'LOCAL'
    if solid > 0:
        md = ob.modifiers.new('solid', 'SOLIDIFY')
        md.thickness = solid
        md.offset = -1.0
    dg = bpy.context.evaluated_depsgraph_get()
    ev = ob.evaluated_get(dg)
    em = ev.to_mesh()
    V = [v.co.copy() for v in em.vertices]
    for mi, k in enumerate(keys):
        F = [tuple(p.vertices) for p in em.polygons if p.material_index == mi]
        if F:
            part.add(V, F, k, None, 0.0)
    ev.to_mesh_clear()
    bpy.data.objects.remove(ob, do_unlink=True)
    bpy.data.meshes.remove(me)
    if disp > 0:
        bpy.data.textures.remove(tex)


# ======================================================================= objects
def new_vehicle(name):
    cname = 'VEH_' + name
    old = bpy.data.collections.get(cname)
    if old:
        for o in list(old.objects):
            bpy.data.objects.remove(o, do_unlink=True)
        bpy.data.collections.remove(old)
    coll = bpy.data.collections.new(cname)
    bpy.context.scene.collection.children.link(coll)
    root = bpy.data.objects.new(name + '_root', None)
    root.empty_display_type = 'SINGLE_ARROW'
    root.empty_display_size = 1.5
    root.rotation_euler = (0, 0, 0)
    coll.objects.link(root)
    root['pivot_world'] = [0.0, 0.0, 0.0]
    root['forward'] = '-Y'
    return coll, root


def veh_finish(part, pivot, coll, parent=None, hz_k=1.0, hz_fn=None, name=None):
    """mesh object from a Part: material slots, 'wear' (face), 'pv' + 'hz' (point) attributes, ngons triangulated,
    smooth + sharp edges, object origin at pivot (parent-relative location)."""
    name = name or part.name
    if not name.startswith('VEH_'):
        name = 'VEH_' + name
    pv = Vector(pivot)
    old = bpy.data.objects.get(name)
    if old:
        bpy.data.objects.remove(old, do_unlink=True)
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(v - pv) for v in part.V], [], part.F)
    used = sorted(set(part.FM))
    remap = {u: k for k, u in enumerate(used)}
    for u in used:
        me.materials.append(bpy.data.materials[MATNAME[L.MATS[u]]])
    me.polygons.foreach_set('material_index', [remap[i] for i in part.FM])
    a = me.attributes.new('wear', 'FLOAT', 'FACE')
    a.data.foreach_set('value', part.FW)
    a = me.attributes.new('pv', 'FLOAT', 'POINT')
    a.data.foreach_set('value', part.VP)
    hz = [hz_fn(v - pv) for v in part.V] if hz_fn else [v.z / hz_k for v in part.V]
    a = me.attributes.new('hz', 'FLOAT', 'POINT')
    a.data.foreach_set('value', hz)
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.remove_doubles(bm, verts=[v for v in bm.verts if not v.link_faces], dist=0.0)
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context='VERTS')
    _close_holes(bm)
    ng = [f for f in bm.faces if len(f.verts) > 4]
    if ng:
        bmesh.ops.triangulate(bm, faces=ng, quad_method='BEAUTY', ngon_method='BEAUTY')
    bm.to_mesh(me)
    bm.free()
    me.polygons.foreach_set('use_smooth', [True] * len(me.polygons))
    if hasattr(me, 'set_sharp_from_angle'):
        me.set_sharp_from_angle(angle=D2R(32))
    me.validate(clean_customdata=False)
    me.update()
    ob = bpy.data.objects.new(name, me)
    coll.objects.link(ob)
    if parent is not None:
        ob.parent = parent
        ob.location = pv - Vector(parent.get('pivot_world', (0, 0, 0)))
    else:
        ob.location = pv
    ob['pivot_world'] = list(pv)
    return ob


def instance(src, name, pivot, coll, parent):
    if not name.startswith('VEH_'):
        name = 'VEH_' + name
    old = bpy.data.objects.get(name)
    if old:
        bpy.data.objects.remove(old, do_unlink=True)
    ob = bpy.data.objects.new(name, src.data)
    coll.objects.link(ob)
    ob.parent = parent
    ob.location = Vector(pivot) - Vector(parent.get('pivot_world', (0, 0, 0)))
    ob['pivot_world'] = list(pivot)
    return ob


def wheel_hz(R, axis='x', base=0.25, span=0.65):
    def f(v):
        if axis == 'x':
            r = math.hypot(v.y, v.z)
        elif axis == 'y':
            r = math.hypot(v.x, v.z)
        else:
            r = math.hypot(v.x, v.y)
        return base + span * (1.0 - min(1.0, r / R))
    return f


def tri_count(objs):
    return L.tri_count(objs)


def vehicle_objects(root):
    return [root] + list(root.children_recursive)


def uv_unwrap(root, margin=0.003):
    meshes, seen = [], set()
    for o in vehicle_objects(root):
        if o.type == 'MESH' and o.data.name not in seen:
            seen.add(o.data.name)
            meshes.append(o)
    if bpy.context.object and bpy.context.object.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')
    bpy.ops.object.select_all(action='DESELECT')
    for o in meshes:
        o.select_set(True)
    bpy.context.view_layer.objects.active = meshes[0]
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.smart_project(angle_limit=D2R(66), island_margin=margin, area_weight=0.0, correct_aspect=True,
                             scale_to_bounds=False)
    bpy.ops.object.mode_set(mode='OBJECT')
    bpy.ops.object.select_all(action='DESELECT')


def export_fbx(root, path):
    objs = vehicle_objects(root)
    old = root.location.copy()
    root.location = (0, 0, 0)
    bpy.context.view_layer.update()
    bpy.ops.object.select_all(action='DESELECT')
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = root
    os.makedirs(os.path.dirname(path), exist_ok=True)
    bpy.ops.export_scene.fbx(filepath=path, use_selection=True, object_types={'EMPTY', 'MESH'},
                             apply_unit_scale=True, apply_scale_options='FBX_SCALE_ALL', bake_space_transform=True,
                             axis_forward='-Z', axis_up='Y', mesh_smooth_type='FACE', add_leaf_bones=False,
                             use_mesh_modifiers=True, use_custom_props=False, path_mode='AUTO')
    root.location = old
    bpy.ops.object.select_all(action='DESELECT')

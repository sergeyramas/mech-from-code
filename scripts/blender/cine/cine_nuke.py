"""cine_nuke.py -- the W-12 tactical nuke rocket (model + markings) and the mushroom-cloud sequence."""
import bpy, bmesh, math, random
import numpy as np
from mathutils import Vector, Matrix, Euler, Quaternion
import fx_lib as F
from fx_lib import NT, inp, outp, new_mat

FONT_CANDIDATES = ['/System/Library/Fonts/Supplemental/DIN Condensed Bold.ttf',
                   '/System/Library/Fonts/Supplemental/Impact.ttf',
                   '/System/Library/Fonts/Supplemental/Arial Black.ttf',
                   '/System/Library/Fonts/Supplemental/Arial Bold.ttf']


def _font():
    import os
    for p in FONT_CANDIDATES:
        if os.path.exists(p):
            try:
                return bpy.data.fonts.load(p, check_existing=True)
            except Exception:
                pass
    return None


# ----------------------------------------------------------------------------- materials
def paint_mat(name, col, rough=0.55, metal=0.25, wear=0.35, emis=None):
    m = new_mat(name)
    T = NT(m.node_tree)
    out = T.n('ShaderNodeOutputMaterial')
    b = T.n('ShaderNodeBsdfPrincipled')
    tc = T.n('ShaderNodeTexCoord')
    nz = T.n('ShaderNodeTexNoise')
    inp(nz, 'Scale').default_value = 18.0
    inp(nz, 'Detail').default_value = 8.0
    T.L(outp(tc, 'Object'), inp(nz, 'Vector'))
    ramp = T.n('ShaderNodeValToRGB')
    ramp.color_ramp.elements[0].position = 0.45
    ramp.color_ramp.elements[0].color = (*[c * (1 - wear * 0.25) for c in col], 1)
    ramp.color_ramp.elements[1].position = 0.75
    ramp.color_ramp.elements[1].color = (*[min(1, c * (1 + wear * 0.4)) for c in col], 1)
    T.L(outp(nz, 'Fac'), ramp.inputs[0])
    T.L(ramp.outputs[0], inp(b, 'Base Color'))
    inp(b, 'Roughness').default_value = rough
    inp(b, 'Metallic').default_value = metal
    bump = T.n('ShaderNodeBump')
    inp(bump, 'Strength').default_value = 0.08
    T.L(outp(nz, 'Fac'), inp(bump, 'Height'))
    T.L(outp(bump, 'Normal'), inp(b, 'Normal'))
    if emis:
        T.L(T.n('ShaderNodeRGB').outputs[0], inp(b, 'Emission Color'))
        b.inputs['Emission Color'].links[0].from_node.outputs[0].default_value = (*emis[0], 1)
        inp(b, 'Emission Strength').default_value = emis[1]
    T.L(b.outputs[0], out.inputs[0])
    return m


def hazard_mat(name='RKT_hazard', width=0.06):
    """diagonal yellow/black stripes in object space (x along the rocket)."""
    m = new_mat(name)
    T = NT(m.node_tree)
    out = T.n('ShaderNodeOutputMaterial')
    b = T.n('ShaderNodeBsdfPrincipled')
    tc = T.n('ShaderNodeTexCoord')
    sx = T.n('ShaderNodeSeparateXYZ')
    T.L(outp(tc, 'Object'), sx.inputs[0])
    ang = T.math('ARCTAN2', sx.outputs[2], sx.outputs[1])
    s = T.math('ADD', sx.outputs[0], T.math('MULTIPLY', ang, 0.18 / 1.0))
    st = T.math('FRACT', T.math('DIVIDE', s, width * 2))
    mask = T.math('GREATER_THAN', st, 0.5)
    mix = T.n('ShaderNodeMix', data_type='RGBA')
    T.L(mask, inp(mix, 'Factor'))
    mix.inputs[6].default_value = (0.9, 0.62, 0.02, 1)
    mix.inputs[7].default_value = (0.015, 0.014, 0.012, 1)
    T.L(mix.outputs[2], inp(b, 'Base Color'))
    inp(b, 'Roughness').default_value = 0.45
    T.L(b.outputs[0], out.inputs[0])
    return m


def flat_mat(name, col, rough=0.5, emis=0.0):
    m = new_mat(name)
    T = NT(m.node_tree)
    out = T.n('ShaderNodeOutputMaterial')
    b = T.n('ShaderNodeBsdfPrincipled')
    inp(b, 'Base Color').default_value = (*col, 1)
    inp(b, 'Roughness').default_value = rough
    if emis:
        inp(b, 'Emission Color').default_value = (*col, 1)
        inp(b, 'Emission Strength').default_value = emis
    T.L(b.outputs[0], out.inputs[0])
    return m


def flame_mat(name='RKT_flame'):
    """emissive cone: hot white core -> orange -> transparent tip (object x from 0 (nozzle) to -1)."""
    m = new_mat(name)
    T = NT(m.node_tree)
    out = T.n('ShaderNodeOutputMaterial')
    tc = T.n('ShaderNodeTexCoord')
    sx = T.n('ShaderNodeSeparateXYZ')
    T.L(outp(tc, 'Generated'), sx.inputs[0])
    u = T.math('SUBTRACT', 1.0, sx.outputs[0])         # 0 at nozzle -> 1 at tip (generated x 1 at nozzle)
    nz = T.n('ShaderNodeTexNoise', noise_dimensions='4D')
    inp(nz, 'Scale').default_value = 6.0
    T.L(outp(tc, 'Object'), inp(nz, 'Vector'))
    T.L(T.attr('flick'), inp(nz, 'W'))
    ramp = T.n('ShaderNodeValToRGB')
    el = ramp.color_ramp.elements
    el[0].position, el[0].color = 0.0, (1.0, 0.95, 0.8, 1)
    el[1].position, el[1].color = 1.0, (0.9, 0.12, 0.01, 1)
    e = el.new(0.35); e.color = (1.0, 0.55, 0.12, 1)
    T.L(u, ramp.inputs[0])
    em = T.n('ShaderNodeEmission')
    T.L(ramp.outputs[0], inp(em, 'Color'))
    strength = T.math('MULTIPLY', T.maprange(u, 0.0, 1.0, 1.0, 0.0), T.maprange(outp(nz, 'Fac'), 0.3, 0.7, 0.4, 1.0))
    T.L(T.math('MULTIPLY', strength, 60.0), inp(em, 'Strength'))
    tr = T.n('ShaderNodeBsdfTransparent')
    mx = T.n('ShaderNodeMixShader')
    alpha = T.math('MULTIPLY', T.maprange(u, 0.55, 1.0, 1.0, 0.0), T.maprange(outp(nz, 'Fac'), 0.25, 0.6, 0.2, 1.0))
    T.L(alpha, mx.inputs[0])
    T.L(tr.outputs[0], mx.inputs[1])
    T.L(em.outputs[0], mx.inputs[2])
    T.L(mx.outputs[0], out.inputs[0])
    try:
        m.surface_render_method = 'BLENDED'
    except Exception:
        pass
    return m


def haze_mat(name='RKT_haze'):
    m = new_mat(name)
    T = NT(m.node_tree)
    out = T.n('ShaderNodeOutputMaterial')
    tc = T.n('ShaderNodeTexCoord')
    nz = T.n('ShaderNodeTexNoise', noise_dimensions='4D')
    inp(nz, 'Scale').default_value = 9.0
    T.L(outp(tc, 'Object'), inp(nz, 'Vector'))
    T.L(T.attr('flick'), inp(nz, 'W'))
    bump = T.n('ShaderNodeBump')
    inp(bump, 'Strength').default_value = 0.35
    T.L(outp(nz, 'Fac'), inp(bump, 'Height'))
    rf = T.n('ShaderNodeBsdfRefraction')
    inp(rf, 'IOR').default_value = 1.015
    inp(rf, 'Roughness').default_value = 0.0
    inp(rf, 'Color').default_value = (1, 1, 1, 1)
    T.L(outp(bump, 'Normal'), inp(rf, 'Normal'))
    T.L(rf.outputs[0], out.inputs[0])
    try:
        m.surface_render_method = 'DITHERED'
        m.use_raytrace_refraction = True
        m.use_screen_refraction = True
    except Exception:
        pass
    try:
        m.use_raytrace_refraction = True
    except Exception:
        pass
    return m


# ----------------------------------------------------------------------------- geometry helpers
def _wrap(me, r, x0=0.0):
    """mesh built in the (u, v) plane (u along the rocket x, v around) -> wrapped onto radius r."""
    for v in me.vertices:
        u, w, h = v.co.x, v.co.y, v.co.z
        a = w / r
        rr = r + h
        v.co = Vector((u + x0, rr * math.sin(a), -rr * math.cos(a)))


def _text_mesh(txt, size, font, extrude=0.0):
    cu = bpy.data.curves.new('tmp_txt', 'FONT')
    cu.body = txt
    if font:
        cu.font = font
    cu.size = size
    cu.align_x = 'CENTER'
    cu.align_y = 'CENTER'
    cu.extrude = extrude
    cu.resolution_u = 3
    ob = bpy.data.objects.new('tmp_txt', cu)
    bpy.context.scene.collection.objects.link(ob)
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
    bpy.data.objects.remove(ob)
    bpy.data.curves.remove(cu)
    return me


def _sub_mesh(me, cuts=2):
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.triangulate(bm, faces=bm.faces)
    bmesh.ops.subdivide_edges(bm, edges=bm.edges, cuts=cuts, use_grid_fill=True)
    bm.to_mesh(me)
    bm.free()


def _join(meshes_mats, name):
    """meshes_mats: list of (mesh, material) -> one mesh with material slots."""
    bm = bmesh.new()
    mats = []
    for me, mt in meshes_mats:
        if mt not in mats:
            mats.append(mt)
        mi = mats.index(mt)
        tmp = bmesh.new()
        tmp.from_mesh(me)
        for f in tmp.faces:
            f.material_index = mi
        tme = bpy.data.meshes.new('tmpj')
        tmp.to_mesh(tme)
        tmp.free()
        bm.from_mesh(tme)
        bpy.data.meshes.remove(tme)
    out = bpy.data.meshes.new(name)
    bm.to_mesh(out)
    bm.free()
    for mt in mats:
        out.materials.append(mt)
    return out


def _revolve(profile, n=40, name='rev'):
    """profile: list of (x, r) -> surface of revolution about x."""
    bm = bmesh.new()
    rings = []
    for x, r in profile:
        ring = []
        for k in range(n):
            a = 2 * math.pi * k / n
            ring.append(bm.verts.new((x, r * math.cos(a), r * math.sin(a))))
        rings.append(ring)
    for i in range(len(rings) - 1):
        for k in range(n):
            a, b = rings[i][k], rings[i][(k + 1) % n]
            c, d = rings[i + 1][(k + 1) % n], rings[i + 1][k]
            if (a.co - d.co).length < 1e-6 and (b.co - c.co).length < 1e-6:
                continue
            try:
                bm.faces.new((a, b, c, d))
            except ValueError:
                pass
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = True
    return me


def _box(sx, sy, sz, c=(0, 0, 0)):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=(sx, sy, sz), verts=bm.verts)
    bmesh.ops.translate(bm, vec=c, verts=bm.verts)
    me = bpy.data.meshes.new('box')
    bm.to_mesh(me)
    bm.free()
    return me


def trefoil_mesh(R=0.13, res=64):
    """radiation trefoil in the (u, v) plane: yellow disc + black blades + black centre; returns (disc, black)."""
    bm = bmesh.new()
    # yellow disc as a fine grid (wraps well)
    bmesh.ops.create_circle(bm, cap_ends=True, segments=res, radius=R)
    bmesh.ops.triangulate(bm, faces=bm.faces)
    bmesh.ops.subdivide_edges(bm, edges=bm.edges, cuts=2, use_grid_fill=True)
    disc = bpy.data.meshes.new('tref_disc')
    bm.to_mesh(disc)
    bm.free()
    bm = bmesh.new()
    r0 = R * 0.16
    r1, r2 = R * 0.24, R * 0.82
    # centre circle
    c = bmesh.ops.create_circle(bm, cap_ends=True, segments=32, radius=r0)
    for k in range(3):
        a0 = math.radians(90 + 120 * k - 30)
        steps = 12
        inner, outer = [], []
        for i in range(steps + 1):
            a = a0 + math.radians(60) * i / steps
            inner.append(bm.verts.new((r1 * math.cos(a), r1 * math.sin(a), 0)))
            outer.append(bm.verts.new((r2 * math.cos(a), r2 * math.sin(a), 0)))
        for i in range(steps):
            bm.faces.new((inner[i], inner[i + 1], outer[i + 1], outer[i]))
    for v in bm.verts:
        v.co.z = 0.002
    black = bpy.data.meshes.new('tref_black')
    bm.to_mesh(black)
    bm.free()
    return disc, black


def chevrons_mesh(n=6, w=0.07, h=0.06, t=0.018, gap=0.025):
    bm = bmesh.new()
    for i in range(n):
        x0 = i * (w * 0.6 + gap)
        pts = [(x0, h / 2), (x0 + w * 0.6, 0), (x0, -h / 2), (x0 + t, -h / 2), (x0 + w * 0.6 + t, 0), (x0 + t, h / 2)]
        vs = [bm.verts.new((x, y, 0.001)) for x, y in pts]
        bm.faces.new(vs)
    me = bpy.data.meshes.new('chev')
    bm.to_mesh(me)
    bm.free()
    _sub_mesh(me, 1)
    return me


def build_rocket(c, serial='SN 0417-77-TX'):
    """W-12 TAC-NUKE: x forward (nose +x), length ~3.9 m, body radius 0.2 m. Returns (root, flame, haze, light)."""
    R = 0.2
    font = _font()
    olive = paint_mat('RKT_paint', (0.16, 0.17, 0.12), rough=0.5, metal=0.3, wear=0.5)
    dark = paint_mat('RKT_dark', (0.035, 0.035, 0.035), rough=0.4, metal=0.6, wear=0.4)
    steel = paint_mat('RKT_steel', (0.35, 0.34, 0.32), rough=0.3, metal=0.9, wear=0.4)
    yellow = flat_mat('RKT_yellow', (0.95, 0.68, 0.02), rough=0.45)
    black = flat_mat('RKT_black', (0.01, 0.01, 0.01), rough=0.55)
    white = flat_mat('RKT_white', (0.85, 0.85, 0.8), rough=0.5)
    red = flat_mat('RKT_red', (0.6, 0.03, 0.02), rough=0.5)
    haz = hazard_mat()
    parts = []
    # body + nose + boat tail
    body = _revolve([(-1.75, 0.0), (-1.75, 0.13), (-1.65, R * 0.92), (-1.55, R), (1.05, R)], name='rkt_body')
    parts.append((body, olive))
    nose_prof = [(1.05, R)]
    for i in range(1, 15):
        s = i / 14
        nose_prof.append((1.05 + 1.0 * s, R * math.sqrt(max(0, 1 - s ** 1.6)) * (1 - 0.05 * s)))
    nose_prof.append((2.06, 0.0))
    parts.append((_revolve(nose_prof, name='rkt_nose'), dark))
    # hazard band just behind the nose + seam bands (slightly proud) with rivets
    parts.append((_revolve([(0.62, R + 0.004), (0.98, R + 0.004)], name='rkt_haz'), haz))
    for xb in (-1.2, -0.45, 0.35, 1.02):
        parts.append((_revolve([(xb - 0.025, R + 0.007), (xb + 0.025, R + 0.007)], name='band'), steel))
        bm = bmesh.new()
        for k in range(18):
            a = 2 * math.pi * k / 18
            for dx in (-0.016, 0.016):
                bmesh.ops.create_uvsphere(bm, u_segments=6, v_segments=4, radius=0.007,
                                          matrix=Matrix.Translation((xb + dx, (R + 0.009) * math.cos(a),
                                                                     (R + 0.009) * math.sin(a))))
        rv = bpy.data.meshes.new('rivets')
        bm.to_mesh(rv)
        bm.free()
        parts.append((rv, steel))
    # tail yellow ring + nozzle
    parts.append((_revolve([(-1.45, R + 0.004), (-1.3, R + 0.004)], name='ring'), yellow))
    parts.append((_revolve([(-1.75, 0.13), (-1.95, 0.155), (-1.97, 0.12), (-1.78, 0.1)], name='nozzle'), steel))
    # fins (4, tail) + canards (4, front)
    for k in range(4):
        a = math.pi / 4 + k * math.pi / 2
        for (x0, x1, x2, span, th, mat) in ((-1.62, -0.95, -1.5, 0.42, 0.022, olive), (0.5, 0.78, 0.6, 0.16, 0.014, dark)):
            bm = bmesh.new()
            pts = [(x0, R - 0.01), (x1, R - 0.01), (x1 - 0.05, R + span * 0.55), (x2, R + span)]
            vs_a = [bm.verts.new((x, y, -th / 2)) for x, y in pts]
            vs_b = [bm.verts.new((x, y, th / 2)) for x, y in pts]
            bm.faces.new(vs_a[::-1])
            bm.faces.new(vs_b)
            for i in range(4):
                j = (i + 1) % 4
                bm.faces.new((vs_a[i], vs_a[j], vs_b[j], vs_b[i]))
            bmesh.ops.rotate(bm, verts=bm.verts, cent=(0, 0, 0), matrix=Matrix.Rotation(a, 3, 'X'))
            fm = bpy.data.meshes.new('fin')
            bm.to_mesh(fm)
            bm.free()
            parts.append((fm, mat))
    # markings on both sides (v measured around the body; side +Y is a = +90 deg)
    for side in (1, -1):
        def place(me, u0, v0, rr=R + 0.006, side=side):
            # decal plane (x right, y up, z out) -> cylinder side s*Y; on +Y the text reads toward -X
            for v in me.vertices:
                x, y, h = v.co
                u = u0 + (-x if side > 0 else x)
                phi = (y + v0) / rr
                v.co = Vector((u, side * (rr + h) * math.cos(phi), (rr + h) * math.sin(phi)))
            return me
        # big designation
        if font:
            t1 = _text_mesh('W-12  TAC-NUKE', 0.15, font)
            _sub_mesh(t1, 1)
            parts.append((place(t1, -0.35, 0.05), black))
            t2 = _text_mesh('TACTICAL NUCLEAR WARHEAD', 0.048, font)
            _sub_mesh(t2, 1)
            parts.append((place(t2, -0.35, -0.075), black))
            t3 = _text_mesh(serial + '   LOT 7  /  YIELD 0.3 KT', 0.03, font)
            _sub_mesh(t3, 1)
            parts.append((place(t3, -0.35, -0.13), white))
        d, bl = trefoil_mesh(0.115)
        parts.append((place(d, 0.42, -0.01, rr=R + 0.006), yellow))
        parts.append((place(bl, 0.42, -0.01, rr=R + 0.006), black))
        ch = chevrons_mesh()
        parts.append((place(ch, -1.27, 0.0, rr=R + 0.008), yellow))
        ch2 = chevrons_mesh()
        parts.append((place(ch2, -1.27, 0.12, rr=R + 0.008), yellow))
    me = _join(parts, 'RKT_W12')
    for p in me.polygons:
        p.use_smooth = True
    rocket = bpy.data.objects.new('RKT_W12', me)
    c.objects.link(rocket)
    # flame + haze + light (children)
    fl = _revolve([(0.0, 0.11), (-0.3, 0.17), (-1.2, 0.14), (-2.6, 0.0)], n=24, name='RKT_flame')
    flo = bpy.data.objects.new('RKT_flame', fl)
    fl.materials.append(flame_mat())
    c.objects.link(flo)
    flo.parent = rocket
    flo.location = (-1.92, 0, 0)
    flo['flick'] = 0.0
    hz = _revolve([(0.0, 0.12), (-1.0, 0.3), (-3.0, 0.4), (-5.0, 0.0)], n=16, name='RKT_haze')
    hzo = bpy.data.objects.new('RKT_haze', hz)
    hz.materials.append(haze_mat())
    c.objects.link(hzo)
    hzo.parent = rocket
    hzo.location = (-2.1, 0, 0)
    hzo['flick'] = 0.0
    hzo.visible_shadow = False
    hzo.hide_render = True    # raytraced refraction renders as an opaque sky-probe blob in EEVEE here
    flo.visible_shadow = False
    ld = bpy.data.lights.new('RKT_light', 'POINT')
    ld.energy = 3500.0
    ld.color = (1.0, 0.55, 0.2)
    ld.shadow_soft_size = 0.4
    lo = bpy.data.objects.new('RKT_light', ld)
    c.objects.link(lo)
    lo.parent = rocket
    lo.location = (-4.5, 0, 0)
    return rocket, flo, hzo, lo


# ----------------------------------------------------------------------------- mushroom volume
def nuke_material(name='FX_nuke'):
    """Object-space volume for a unit domain [-1,1]^3. Object props:
       shape: 0 sphere, 1 torus cap, 2 stem column; a (torus major), b (torus minor / stem radius),
       age, heat (0..1 internal glow), dens, erode, seed, spin (poloidal roll speed)."""
    m = new_mat(name)
    T = NT(m.node_tree)
    out = T.n('ShaderNodeOutputMaterial')
    pv = T.n('ShaderNodeVolumePrincipled')
    T.L(pv.outputs[0], out.inputs['Volume'])
    tc = T.n('ShaderNodeTexCoord')
    p = outp(tc, 'Object')
    sx = T.n('ShaderNodeSeparateXYZ')
    T.L(p, sx.inputs[0])
    X, Y, Z = sx.outputs[0], sx.outputs[1], sx.outputs[2]
    age, heat, dmul, erode, seed = (T.attr(k) for k in ('age', 'heat', 'dens', 'erode', 'seed'))
    shape = T.attr('shape')
    a, b = T.attr('a'), T.attr('b')
    rho = T.math('SQRT', T.math('ADD', T.math('MULTIPLY', X, X), T.math('MULTIPLY', Y, Y)))
    # torus tube coords
    u = T.math('SUBTRACT', rho, a)
    s_t = T.math('SQRT', T.math('ADD', T.math('MULTIPLY', u, u), T.math('MULTIPLY', Z, Z)))
    phi = T.math('ADD', T.math('ARCTAN2', Z, u), T.math('MULTIPLY', age, T.attr('spin')))
    th = T.math('ARCTAN2', Y, X)
    # rolling noise coordinates (continuous): (cos th, sin th) * k, s*(cos phi, sin phi)
    k1 = 2.2
    cv = T.n('ShaderNodeCombineXYZ')
    T.L(T.math('MULTIPLY', T.math('COSINE', th), k1), cv.inputs[0])
    T.L(T.math('MULTIPLY', T.math('SINE', th), k1), cv.inputs[1])
    T.L(T.math('ADD', T.math('MULTIPLY', T.math('MULTIPLY', s_t, T.math('COSINE', phi)), 7.0), seed), cv.inputs[2])
    w_t = T.math('ADD', T.math('MULTIPLY', T.math('MULTIPLY', s_t, T.math('SINE', phi)), 7.0),
                 T.math('MULTIPLY', age, 0.15))
    # sphere / stem: plain noise on position flowing up
    pw = T.vmath('MULTIPLY', p, (2.2, 2.2, 2.2))
    flow = T.n('ShaderNodeCombineXYZ')
    T.L(seed, flow.inputs[0])
    T.L(T.math('MULTIPLY', age, -0.6), flow.inputs[2])
    pw = T.vmath('ADD', pw, flow.outputs[0])
    # torus noise
    nzt = T.n('ShaderNodeTexNoise', noise_dimensions='4D')
    inp(nzt, 'Scale').default_value = 1.0
    inp(nzt, 'Detail').default_value = 7.0
    inp(nzt, 'Roughness').default_value = 0.6
    inp(nzt, 'Distortion').default_value = 0.25
    T.L(cv.outputs[0], inp(nzt, 'Vector'))
    T.L(w_t, inp(nzt, 'W'))
    nzs = T.n('ShaderNodeTexNoise', noise_dimensions='4D')
    inp(nzs, 'Scale').default_value = 1.6
    inp(nzs, 'Detail').default_value = 7.0
    inp(nzs, 'Roughness').default_value = 0.6
    inp(nzs, 'Distortion').default_value = 0.3
    T.L(pw, inp(nzs, 'Vector'))
    T.L(T.math('ADD', T.math('MULTIPLY', age, 0.25), seed), inp(nzs, 'W'))
    # fine detail
    nzf = T.n('ShaderNodeTexNoise', noise_dimensions='4D')
    inp(nzf, 'Scale').default_value = 9.0
    inp(nzf, 'Detail').default_value = 4.0
    T.L(pw, inp(nzf, 'Vector'))
    T.L(T.math('MULTIPLY', age, 0.4), inp(nzf, 'W'))
    nf = T.math('MULTIPLY', T.math('SUBTRACT', outp(nzf, 'Fac'), 0.5), 0.3)
    w1 = T.math('LESS_THAN', T.math('ABSOLUTE', T.math('SUBTRACT', shape, 1.0)), 0.5)    # torus
    w2 = T.math('LESS_THAN', T.math('ABSOLUTE', T.math('SUBTRACT', shape, 2.0)), 0.5)    # stem
    w0 = T.math('SUBTRACT', 1.0, T.math('ADD', w1, w2))
    n_t = T.math('SUBTRACT', outp(nzt, 'Fac'), 0.5)
    n_s = T.math('SUBTRACT', outp(nzs, 'Fac'), 0.5)
    nn = T.math('ADD', T.math('ADD', T.math('MULTIPLY', n_t, w1), T.math('MULTIPLY', n_s, T.math('ADD', w0, w2))), nf)
    # signed "inside" distances (normalised: 1 at the core, 0 at the surface)
    d_sph = T.math('SUBTRACT', 1.0, T.vmath('LENGTH', p))
    d_tor = T.math('DIVIDE', T.math('SUBTRACT', b, s_t), b)
    # stem: radius b, narrowing a little in the middle, z in [-1, 1]
    rz = T.math('MULTIPLY', b, T.math('ADD', 0.8, T.math('MULTIPLY', T.math('MULTIPLY', Z, Z), 0.35)))
    d_stem = T.math('MINIMUM', T.math('DIVIDE', T.math('SUBTRACT', rz, rho), rz),
                    T.math('MULTIPLY', T.math('SUBTRACT', 1.0, T.math('ABSOLUTE', Z)), 3.0))
    dist = T.math('ADD', T.math('ADD', T.math('MULTIPLY', d_sph, w0), T.math('MULTIPLY', d_tor, w1)),
                  T.math('MULTIPLY', d_stem, w2))
    sh = T.math('ADD', dist, T.math('MULTIPLY', nn, 1.5))
    sh = T.math('SUBTRACT', sh, T.math('ADD', 0.08, T.math('MULTIPLY', erode, 0.7)))
    dens = T.maprange(sh, 0.0, 0.22, 0.0, 1.0, 'SMOOTHSTEP')
    # colour: grey-brown smoke, darker underside
    cr = T.n('ShaderNodeValToRGB')
    cr.color_ramp.elements[0].color = (0.06, 0.05, 0.045, 1)
    cr.color_ramp.elements[1].color = (0.5, 0.42, 0.34, 1)
    T.L(T.maprange(T.math('ADD', Z, T.math('MULTIPLY', nn, 0.8)), -0.8, 0.9, 0.0, 1.0), cr.inputs[0])
    T.L(cr.outputs[0], inp(pv, 'Color'))
    inp(pv, 'Anisotropy').default_value = 0.3
    # internal glow: deep inside + hot noise
    hcore = T.math('ADD', T.math('SUBTRACT', T.math('MULTIPLY', dist, 1.3), T.math('SUBTRACT', 1.0, heat)),
                   T.math('MULTIPLY', nn, 1.2))
    h = T.maprange(hcore, -0.1, 0.6, 0.0, 1.0, 'SMOOTHSTEP')
    h = T.math('MULTIPLY', h, T.math('MINIMUM', T.math('MULTIPLY', heat, 2.5), 1.0))
    er = T.n('ShaderNodeValToRGB')
    el = er.color_ramp.elements
    el[0].position, el[0].color = 0.0, (0.25, 0.03, 0.0, 1)
    el[1].position, el[1].color = 1.0, (1.0, 0.75, 0.38, 1)
    e2 = el.new(0.45); e2.color = (0.95, 0.2, 0.02, 1)
    T.L(h, er.inputs[0])
    T.L(er.outputs[0], inp(pv, 'Emission Color'))
    T.L(T.math('MULTIPLY', T.math('MULTIPLY', T.math('POWER', h, 1.5), T.attr('emis')), dens),
        inp(pv, 'Emission Strength'))
    T.L(T.math('MULTIPLY', T.math('MULTIPLY', T.math('MULTIPLY', dens, dmul), T.attr('dmax')),
               T.math('SUBTRACT', 1.0, T.math('MULTIPLY', h, 0.7))), inp(pv, 'Density'))
    return m


def nuke_domain(name, c, shape, **props):
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=2.0)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    c.objects.link(ob)
    base = dict(shape=float(shape), a=0.6, b=0.3, age=0.0, heat=1.0, dens=1.0, erode=0.0, seed=0.0, spin=0.6,
                emis=40.0, dmax=1.5)
    base.update(props)
    for k, v in base.items():
        ob[k] = v
    mat = bpy.data.materials.get('FX_nuke') or nuke_material()
    me.materials.append(mat)
    return ob


def nuke(E, f0, fps, c, f_end, ground_z=0.0, log=print):
    """Mushroom sequence at epicentre E (Vector, ground level) starting at story frame f0.
    Returns dict of objects / event times (story seconds after f0)."""
    objs = []
    rnd = random.Random(12)
    fr = range(int(f0), int(f_end) + 1)
    smooth = lambda x: x * x * (3 - 2 * x)
    # ---------- fireball -> cap
    cap = nuke_domain('NUKE_cap', c, 1, seed=3.1, spin=0.9, emis=9.0, dmax=1.2)
    stem = nuke_domain('NUKE_stem', c, 2, seed=7.7, emis=6.0, dmax=0.9)
    core = nuke_domain('NUKE_fireball', c, 0, seed=1.3, emis=40.0, dmax=1.5)
    skirt = F.volume_domain('NUKE_skirt', c, kind='cyl')
    skirt.data.materials.append(F.get_fx_mats()['dust'])
    ring = F.volume_domain('NUKE_ring', c, kind='cyl')
    ring.data.materials.append(F.get_fx_mats()['dust'])
    for o in (cap, stem, core, skirt, ring):
        objs.append(o)
    for f in fr:
        t = (f - f0) / fps
        # fireball: fast growth, rises, fades into the cap
        Rf = 17.0 * (1 - math.exp(-t / 0.12)) * (1 + 0.05 * t)
        zf = 8.0 + Rf * 0.6 + 6.0 * t * t / (t + 1.0)
        core.scale = (max(Rf, 0.1),) * 3
        core.location = E + Vector((0, 0, zf))
        core['age'] = t
        core['heat'] = max(0.0, 1.0 - t / 2.0) ** 1.2
        core['dens'] = max(0.0, 1.0 - max(0.0, t - 1.6) / 1.4)
        core['erode'] = min(0.6, t * 0.12)
        # cap (torus): rises to ~95 m, grows
        tc = max(0.0, t - 0.5)
        H = 22.0 + 78.0 * (1 - math.exp(-tc / 3.6))
        Rc = 10.0 + 24.0 * (1 - math.exp(-tc / 2.8))
        rc = Rc * (0.62 + 0.1 * (1 - math.exp(-tc / 2)))
        S = (Rc + rc) * 1.12
        cap.scale = (S, S, S)
        cap.location = E + Vector((0, 0, H))
        cap['a'] = Rc / S
        cap['b'] = rc / S
        cap['age'] = t
        cap['heat'] = min(1.0, t / 0.6) * max(0.0, 1.0 - tc / 4.5) ** 1.6
        cap['dens'] = smooth(min(1.0, t / 0.9))
        cap['erode'] = min(0.3, tc * 0.03)
        # stem: from ground to the cap underside
        top = H - rc * 0.6
        hs = max(top, 2.0)
        rs = 3.0 + 6.5 * (1 - math.exp(-tc / 2.5))
        stem.scale = (rs * 1.6, rs * 1.6, hs / 2)
        stem.location = E + Vector((0, 0, hs / 2))
        stem['b'] = 1 / 1.6
        stem['age'] = t
        stem['heat'] = max(0.0, 1.0 - tc / 3.0) ** 1.5 * 0.6
        stem['dens'] = smooth(min(1.0, max(0.0, t - 0.6) / 1.2))
        stem['erode'] = 0.05
        # base skirt (dust)
        Rs = 6.0 + 42.0 * (1 - math.exp(-t / 1.6))
        skirt.scale = (Rs, Rs, 4.0 + 10.0 * (1 - math.exp(-t / 2.5)))
        skirt.location = E + Vector((0, 0, ground_z - 0.5))
        skirt['age'] = t
        skirt['dens'] = min(1.0, t / 0.4)
        skirt['erode'] = min(0.45, t * 0.04)
        # ring shock wave of dust along the ground
        Rr = shock_radius(t) + 1.0
        ring.scale = (Rr / 0.72, Rr / 0.72, 2.5 + 4.0 * min(1.0, t / 2.0))
        ring.location = E + Vector((0, 0, ground_z - 0.3))
        ring['age'] = t * 0.6
        ring['dens'] = min(1.0, t / 0.05) * max(0.0, 1.0 - t / 7.0)
        ring['erode'] = min(0.6, t * 0.08)
        for o, paths in ((core, ('scale', 'location', '["age"]', '["heat"]', '["dens"]', '["erode"]')),
                         (cap, ('scale', 'location', '["a"]', '["b"]', '["age"]', '["heat"]', '["dens"]', '["erode"]')),
                         (stem, ('scale', 'location', '["age"]', '["heat"]', '["dens"]')),
                         (skirt, ('scale', 'location', '["age"]', '["dens"]', '["erode"]')),
                         (ring, ('scale', 'location', '["age"]', '["dens"]', '["erode"]'))):
            for pth in paths:
                o.keyframe_insert(pth, frame=f)
    F._hide_keys(core, int(f0), int(f0 + 3.2 * fps))
    F._hide_keys(cap, int(f0 + 0.4 * fps))
    F._hide_keys(stem, int(f0 + 0.6 * fps))
    F._hide_keys(skirt, int(f0))
    F._hide_keys(ring, int(f0), int(f0 + 7.2 * fps))
    for o in objs:
        F.set_interp(o, 'LINEAR')
        for fc in F.fcurves_of(o.animation_data.action):
            if fc.data_path.startswith('hide'):
                for k in fc.keyframe_points:
                    k.interpolation = 'CONSTANT'
    # ---------- flash light (huge) + warm fill from the fireball
    ld = bpy.data.lights.new('NUKE_flash', 'POINT')
    ld.color = (1.0, 0.85, 0.7)
    ld.shadow_soft_size = 6.0
    lo = bpy.data.objects.new('NUKE_flash', ld)
    c.objects.link(lo)
    lo.location = E + Vector((0, 0, 12))
    for f in range(int(f0) - 1, int(f_end)):
        t = (f - f0) / fps
        e = 0.0 if t < 0 else 3.0e9 * math.exp(-t / 0.05) + 6.0e6 * math.exp(-t / 1.2)
        ld.energy = e
        ld.keyframe_insert('energy', frame=f)
        tc_ = max(0.0, t - 0.5)
        lo.location = E + Vector((0, 0, 12 + 60 * (1 - math.exp(-tc_ / 3.6))))
        lo.keyframe_insert('location', frame=f)
    F.set_interp(ld, 'LINEAR')
    F.set_interp(lo, 'LINEAR')
    objs.append(lo)
    return objs


def shock_radius(t):
    """ground shock-wave radius (m) t story-seconds after detonation."""
    return 0.0 if t <= 0 else 105.0 * t ** 0.62

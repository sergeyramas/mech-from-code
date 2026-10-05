"""fx_lib.py -- procedural FX for the mech cinematic (EEVEE, Blender 5.2).

Everything is driven by keyed custom properties / modifier inputs, so a global time-remap
(slow motion) can be applied afterwards by re-sampling every fcurve (see retime.py).

  explosion(...)      fireball + smoke volume (object-space noise, blackbody), flash light, dust ring
  burst(...)          GN ballistic sparks / debris (analytic drag + gravity, ground clamp)
  trail(...)          GN smoke trail (points of a trajectory -> volume), also used for smoke columns
  fracture(...)       recursive random-plane bisect, caps get a separate material
  RigidSim            rigid body set-up, kinematic->dynamic initial velocity, record transforms
"""
import bpy, bmesh, math, random
import numpy as np
from mathutils import Vector, Matrix, Euler, Quaternion

# ----------------------------------------------------------------------------- small helpers
def coll(name, parent=None):
    c = bpy.data.collections.get(name)
    if c is None:
        c = bpy.data.collections.new(name)
        (parent or bpy.context.scene.collection).children.link(c)
    return c


def link(ob, c):
    for u in list(ob.users_collection):
        u.objects.unlink(ob)
    c.objects.link(ob)
    return ob


def inp(node, name, idx=0):
    """n-th available input socket called `name`."""
    k = 0
    for s in node.inputs:
        if (s.name == name or s.identifier == name) and getattr(s, 'enabled', True) and getattr(s, 'is_available', True):
            if k == idx:
                return s
            k += 1
    raise KeyError(f'{node.bl_idname}.{name}')


def outp(node, name):
    for s in node.outputs:
        if (s.name == name or s.identifier == name) and getattr(s, 'enabled', True) and getattr(s, 'is_available', True):
            return s
    raise KeyError(f'{node.bl_idname} out {name}')


def key_prop(ob, prop, frames_vals, interp='LINEAR'):
    """key a custom property (or rna path) at (frame, value) pairs."""
    path = f'["{prop}"]' if not prop.startswith(('location', 'scale', 'rotation', 'energy', 'color')) else prop
    for f, v in frames_vals:
        if path.startswith('['):
            ob[prop] = v
        else:
            setattr(ob, prop, v)
        ob.keyframe_insert(path, frame=f)
    set_interp(ob, interp)


def set_interp(idb, interp='LINEAR'):
    ad = idb.animation_data
    if not ad or not ad.action:
        return
    for fc in fcurves_of(ad.action):
        for k in fc.keyframe_points:
            k.interpolation = interp


def fcurves_of(action):
    """Blender 5.x layered actions: collect every fcurve of every channelbag."""
    out = []
    if hasattr(action, 'layers') and len(action.layers):
        for L in action.layers:
            for st in L.strips:
                for cb in st.channelbags:
                    out.extend(cb.fcurves)
    elif hasattr(action, 'fcurves'):
        out.extend(action.fcurves)
    return out


def set_keys_fast(idb, path, index, frames, values, interp='LINEAR'):
    """write many keys at once via fcurve foreach_set (fast for baked sims)."""
    if idb.animation_data is None:
        idb.animation_data_create()
    ad = idb.animation_data
    if ad.action is None:
        ad.action = bpy.data.actions.new(idb.name + '_act')
    act = ad.action
    fc = None
    if hasattr(act, 'fcurve_ensure_for_datablock'):
        fc = act.fcurve_ensure_for_datablock(idb, path, index=index)
    else:
        fc = act.fcurves.find(path, index=index) or act.fcurves.new(path, index=index)
    fc.keyframe_points.clear()
    n = len(frames)
    fc.keyframe_points.add(n)
    co = np.empty(2 * n)
    co[0::2] = frames
    co[1::2] = values
    fc.keyframe_points.foreach_set('co', co)
    ip = bpy.types.Keyframe.bl_rna.properties['interpolation'].enum_items[interp].value
    fc.keyframe_points.foreach_set('interpolation', [ip] * n)
    fc.update()
    return fc


# ----------------------------------------------------------------------------- shader node helpers
class NT:
    def __init__(self, nt):
        self.nt = nt
        self.x = 0

    def n(self, kind, **kw):
        nd = self.nt.nodes.new(kind)
        for k, v in kw.items():
            setattr(nd, k, v)
        return nd

    def L(self, a, b):
        self.nt.links.new(a, b)

    def math(self, op, a, b=None, clamp=False, c=None):
        nd = self.n('ShaderNodeMath' if self.nt.bl_idname == 'ShaderNodeTree' else 'ShaderNodeMath', operation=op)
        nd.use_clamp = clamp
        for i, v in enumerate((a, b, c)):
            if v is None:
                continue
            if isinstance(v, (int, float)):
                nd.inputs[i].default_value = v
            else:
                self.L(v, nd.inputs[i])
        return nd.outputs[0]

    def vmath(self, op, a, b=None, scale=None):
        nd = self.n('ShaderNodeVectorMath', operation=op)
        for i, v in enumerate((a, b)):
            if v is None:
                continue
            if isinstance(v, (tuple, list, Vector)):
                nd.inputs[i].default_value = v
            else:
                self.L(v, nd.inputs[i])
        if scale is not None:
            s = inp(nd, 'Scale')
            if isinstance(s, (int, float)):
                pass
            if isinstance(scale, (int, float)):
                s.default_value = scale
            else:
                self.L(scale, s)
        o = outp(nd, 'Value') if op in ('LENGTH', 'DOT_PRODUCT', 'DISTANCE') else outp(nd, 'Vector')
        return o

    def maprange(self, v, a, b, c=0.0, d=1.0, interp='LINEAR', clamp=True):
        nd = self.n('ShaderNodeMapRange')
        nd.interpolation_type = interp
        nd.clamp = clamp
        self.L(v, inp(nd, 'Value'))
        for nm, val in (('From Min', a), ('From Max', b), ('To Min', c), ('To Max', d)):
            s = inp(nd, nm)
            if isinstance(val, (int, float)):
                s.default_value = val
            else:
                self.L(val, s)
        return outp(nd, 'Result')

    def attr(self, name, kind='OBJECT'):
        nd = self.n('ShaderNodeAttribute', attribute_name=name, attribute_type=kind)
        return outp(nd, 'Fac')


def new_mat(name):
    m = bpy.data.materials.get(name)
    if m:
        bpy.data.materials.remove(m)
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    m.node_tree.nodes.clear()
    return m


# ----------------------------------------------------------------------------- explosion volume material
def fireball_material(name='FX_fireball', emis=160.0, smoke_col=(0.035, 0.032, 0.03), dens=14.0,
                      noise_scale=1.6, kind='fire'):
    """Object-space volume. Object props: age, heat(0..1), dens(0..1), seed, erode(0..1).
    kind: 'fire' (fireball turning into smoke), 'smoke' (dark rising smoke), 'dust' (ring of dust)."""
    m = new_mat(name)
    T = NT(m.node_tree)
    out = T.n('ShaderNodeOutputMaterial')
    pv = T.n('ShaderNodeVolumePrincipled')
    T.L(pv.outputs[0], out.inputs['Volume'])
    tc = T.n('ShaderNodeTexCoord')
    p = outp(tc, 'Object')
    age = T.attr('age')
    heat = T.attr('heat')
    dmul = T.attr('dens')
    seed = T.attr('seed')
    erode = T.attr('erode')
    # warp coords: seed offset + slow upward flow in object space
    off = T.n('ShaderNodeCombineXYZ')
    T.L(seed, off.inputs[0])
    T.L(T.math('MULTIPLY', seed, 0.37), off.inputs[1])
    T.L(T.math('MULTIPLY', age, -0.35), off.inputs[2])
    pw = T.vmath('ADD', p, off.outputs[0])
    nz = T.n('ShaderNodeTexNoise', noise_dimensions='4D')
    inp(nz, 'Scale').default_value = noise_scale
    inp(nz, 'Detail').default_value = 7.0
    inp(nz, 'Roughness').default_value = 0.62
    inp(nz, 'Distortion').default_value = 0.35
    T.L(pw, inp(nz, 'Vector'))
    T.L(T.math('MULTIPLY', age, 0.45), inp(nz, 'W'))
    n1 = outp(nz, 'Fac')
    nz2 = T.n('ShaderNodeTexNoise', noise_dimensions='4D')
    inp(nz2, 'Scale').default_value = noise_scale * 4.5
    inp(nz2, 'Detail').default_value = 4.0
    inp(nz2, 'Roughness').default_value = 0.55
    T.L(pw, inp(nz2, 'Vector'))
    T.L(T.math('MULTIPLY', age, 0.9), inp(nz2, 'W'))
    n2 = outp(nz2, 'Fac')
    nn = T.math('ADD', T.math('MULTIPLY', T.math('SUBTRACT', n1, 0.5), 1.0),
                T.math('MULTIPLY', T.math('SUBTRACT', n2, 0.5), 0.35))       # ~[-0.4, 0.4]
    if kind == 'dust':
        # ring: radial distance in xy, height 0..1 (object z), ring centre at r=0.78
        sx = T.n('ShaderNodeSeparateXYZ')
        T.L(p, sx.inputs[0])
        rxy = T.math('SQRT', T.math('ADD', T.math('MULTIPLY', sx.outputs[0], sx.outputs[0]),
                                    T.math('MULTIPLY', sx.outputs[1], sx.outputs[1])))
        ring = T.math('SUBTRACT', 1.0, T.math('ABSOLUTE', T.math('MULTIPLY', T.math('SUBTRACT', rxy, 0.72), 3.2)))
        inner = T.maprange(rxy, 0.0, 0.75, 0.35, 1.0)       # some dust also inside the ring
        ring = T.math('MAXIMUM', ring, T.math('MULTIPLY', inner, 0.55))
        hz = T.maprange(sx.outputs[2], 0.0, 1.0, 1.0, 0.0, 'SMOOTHSTEP')
        shape = T.math('ADD', T.math('MULTIPLY', ring, hz), T.math('MULTIPLY', nn, 1.1))
        shape = T.math('SUBTRACT', shape, T.math('ADD', 0.25, T.math('MULTIPLY', erode, 0.8)))
        d = T.maprange(shape, 0.0, 0.25, 0.0, 1.0, 'SMOOTHSTEP')
        inp(pv, 'Color').default_value = (0.33, 0.28, 0.21, 1)
        T.L(T.math('MULTIPLY', T.math('MULTIPLY', d, dmul), dens), inp(pv, 'Density'))
        inp(pv, 'Anisotropy').default_value = 0.2
        return m
    r = T.vmath('LENGTH', p)
    # main shape: sphere eroded by noise; 'erode' thins the cloud as it dissipates
    shape = T.math('ADD', T.math('SUBTRACT', 1.0, r), T.math('MULTIPLY', nn, 1.35))
    shape = T.math('SUBTRACT', shape, T.math('ADD', 0.05, T.math('MULTIPLY', erode, 0.75)))
    d = T.maprange(shape, 0.0, 0.18, 0.0, 1.0, 'SMOOTHSTEP')
    dd = T.math('MULTIPLY', T.math('MULTIPLY', d, dmul), dens)
    # albedo: dark soot, slightly lighter at the rim
    ramp = T.n('ShaderNodeValToRGB')
    ramp.color_ramp.elements[0].color = (*smoke_col, 1)
    ramp.color_ramp.elements[1].color = tuple(min(1, c * 3.2) for c in smoke_col) + (1,)
    T.L(T.math('MULTIPLY', r, 1.0), ramp.inputs[0])
    T.L(ramp.outputs[0], inp(pv, 'Color'))
    inp(pv, 'Anisotropy').default_value = 0.25
    if kind == 'fire':
        # heat field: hot core (noisy) shrinking with `heat`
        hcore = T.math('ADD', T.math('SUBTRACT', T.math('MULTIPLY', heat, 1.05), r), T.math('MULTIPLY', nn, 1.6))
        h = T.maprange(hcore, -0.05, 0.45, 0.0, 1.0, 'SMOOTHSTEP')
        h = T.math('MULTIPLY', h, T.math('MINIMUM', T.math('MULTIPLY', heat, 3.0), 1.0))
        fr = T.n('ShaderNodeValToRGB')
        el = fr.color_ramp.elements
        el[0].position, el[0].color = 0.0, (0.35, 0.02, 0.0, 1)
        el[1].position, el[1].color = 1.0, (1.0, 0.82, 0.45, 1)
        e2 = el.new(0.35); e2.color = (1.0, 0.18, 0.01, 1)
        e3 = el.new(0.7); e3.color = (1.0, 0.45, 0.06, 1)
        T.L(h, fr.inputs[0])
        T.L(fr.outputs[0], inp(pv, 'Emission Color'))
        T.L(T.math('MULTIPLY', T.math('MULTIPLY', T.math('POWER', h, 1.6), emis), d), inp(pv, 'Emission Strength'))
        dd = T.math('MULTIPLY', dd, T.math('SUBTRACT', 1.0, T.math('MULTIPLY', h, 0.8)))
    T.L(dd, inp(pv, 'Density'))
    return m


def volume_domain(name, c, radius=1.0, kind='ico'):
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    if kind == 'ico':
        bmesh.ops.create_icosphere(bm, subdivisions=2, radius=radius * 1.08)
    elif kind == 'cyl':
        bmesh.ops.create_cone(bm, cap_ends=True, segments=24, radius1=radius, radius2=radius, depth=1.0)
        bmesh.ops.translate(bm, verts=bm.verts, vec=(0, 0, 0.5))
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    c.objects.link(ob)
    for k, v in (('age', 0.0), ('heat', 1.0), ('dens', 1.0), ('seed', 0.0), ('erode', 0.0)):
        ob[k] = v
    ob.visible_shadow = True
    return ob


MATS = {}


def get_fx_mats():
    if not MATS:
        MATS['fire'] = fireball_material('FX_fireball', kind='fire')
        MATS['smoke'] = fireball_material('FX_smoke', kind='smoke', smoke_col=(0.03, 0.028, 0.026), dens=7.0,
                                          noise_scale=1.3)
        MATS['smoke_lt'] = fireball_material('FX_smoke_light', kind='smoke', smoke_col=(0.12, 0.11, 0.1),
                                             dens=4.0, noise_scale=1.3)
        MATS['dust'] = fireball_material('FX_dust', kind='dust', dens=3.0, noise_scale=1.4)
    return MATS


def _hide_keys(ob, f_on, f_off=None):
    """object visible (render+viewport) only in [f_on, f_off)."""
    for f, h in ((f_on - 1, True), (f_on, False)) + (((f_off, True),) if f_off else ()):
        ob.hide_render = h
        ob.hide_viewport = h
        ob.keyframe_insert('hide_render', frame=f)
        ob.keyframe_insert('hide_viewport', frame=f)
    for fc in fcurves_of(ob.animation_data.action):
        if fc.data_path.startswith('hide'):
            for k in fc.keyframe_points:
                k.interpolation = 'CONSTANT'


def explosion(name, loc, f0, fps, c, size=4.0, seed=None, smoke_life=9.0, rise=2.2, light=True,
              dust=True, smoke=True, light_energy=4.0e6, fire_life=2.0, ground_z=None, smoke_size=1.6,
              wind=(0.6, 0.25, 0.0)):
    """size = fireball max radius (m). Returns list of created objects. Events: f0 = detonation frame."""
    M = get_fx_mats()
    rnd = random.Random(seed if seed is not None else hash(name) & 0xffff)
    loc = Vector(loc)
    gz = loc.z if ground_z is None else ground_z
    objs = []
    dur = int(fps * max(fire_life + 1.0, smoke_life)) + 2
    fr = range(f0, f0 + dur + 1)
    # ---- fireball
    fb = volume_domain(name + '_fire', c)
    fb.data.materials.append(M['fire'])
    fb['seed'] = rnd.uniform(0, 100)
    for f in fr:
        t = (f - f0) / fps
        R = size * (0.18 + 0.82 * (1 - math.exp(-t / 0.16))) * (1 + 0.12 * t)
        fb.scale = (R, R, R * 0.92)
        fb.location = loc + Vector((0, 0, R * 0.55 + rise * 0.6 * t * t / (t + 0.8)))
        fb['age'] = t
        fb['heat'] = max(0.0, 1.0 - t / fire_life) ** 0.9
        fb['dens'] = 1.0 if t < fire_life else max(0.0, 1 - (t - fire_life) / 1.5)
        fb['erode'] = min(1.0, max(0.0, (t - 0.3) / (fire_life + 1.2))) * 0.7
        for pth in ('scale', 'location', '["age"]', '["heat"]', '["dens"]', '["erode"]'):
            fb.keyframe_insert(pth, frame=f)
    _hide_keys(fb, f0, f0 + int(fps * (fire_life + 1.6)))
    objs.append(fb)
    # ---- rising dark smoke (two lobes)
    if smoke:
        for j in range(2):
            sm = volume_domain(f'{name}_smoke{j}', c)
            sm.data.materials.append(M['smoke'])
            sm['seed'] = rnd.uniform(0, 100)
            t_on = 0.25 + 0.2 * j
            dx = Vector((rnd.uniform(-.3, .3), rnd.uniform(-.3, .3), 0)) * size
            for f in fr:
                t = (f - f0) / fps
                ts = max(0.0, t - t_on)
                g = 1 - math.exp(-ts / 1.2)
                R = size * smoke_size * (0.45 + 0.9 * g + 0.06 * ts) * (0.85 if j else 1.0)
                sm.scale = (R, R, R * 1.15)
                sm.location = loc + dx + Vector(wind) * ts + Vector((0, 0, size * 0.9 + rise * ts * (1.0 + 0.3 * j)
                                                                        + R * 0.4))
                sm['age'] = t + 3.0 * j
                sm['heat'] = 0.0
                sm['dens'] = min(1.0, ts / 0.35) * max(0.0, 1.0 - ts / smoke_life) ** 0.7
                sm['erode'] = 0.15 + 0.6 * min(1.0, ts / smoke_life)
                for pth in ('scale', 'location', '["age"]', '["dens"]', '["erode"]'):
                    sm.keyframe_insert(pth, frame=f)
            _hide_keys(sm, f0 + int(t_on * fps), f0 + dur)
            objs.append(sm)
    # ---- ground dust ring (shock wave)
    if dust:
        ds = volume_domain(name + '_dust', c, kind='cyl')
        ds.data.materials.append(M['dust'])
        ds['seed'] = rnd.uniform(0, 100)
        for f in fr:
            t = (f - f0) / fps
            R = size * 3.2 * (1 - math.exp(-t / 0.35)) + 0.5
            H = size * 0.55 * (0.4 + 0.6 * (1 - math.exp(-t / 0.8))) + 0.3
            ds.scale = (R, R, H)
            ds.location = (loc.x, loc.y, gz - 0.2)
            ds['age'] = t
            ds['dens'] = min(1.0, t / 0.08) * max(0.0, 1 - t / 4.5) ** 1.5
            ds['erode'] = min(1.0, t / 4.5) * 0.5
            for pth in ('scale', 'location', '["age"]', '["dens"]', '["erode"]'):
                ds.keyframe_insert(pth, frame=f)
        _hide_keys(ds, f0, f0 + int(fps * 4.6))
        objs.append(ds)
    # ---- flash light
    if light:
        ld = bpy.data.lights.new(name + '_flash', 'POINT')
        ld.color = (1.0, 0.55, 0.22)
        ld.shadow_soft_size = size * 0.6
        lo = bpy.data.objects.new(name + '_flash', ld)
        c.objects.link(lo)
        lo.location = loc + Vector((0, 0, size * 0.7))
        for f in range(f0 - 1, f0 + int(fps * (fire_life + 0.8))):
            t = (f - f0) / fps
            e = 0.0 if t < 0 else light_energy * (math.exp(-t / 0.07) * 1.0 + 0.22 * math.exp(-t / (fire_life * 0.5)))
            e *= 1.0 + 0.15 * math.sin(t * 61.0) if t > 0 else 1.0
            ld.energy = e
            ld.keyframe_insert('energy', frame=f)
        ld.energy = 0.0
        ld.keyframe_insert('energy', frame=f0 + int(fps * (fire_life + 0.8)))
        objs.append(lo)
    for o in objs:
        set_interp(o, 'LINEAR')
        if o.animation_data:
            for fc in fcurves_of(o.animation_data.action):
                if fc.data_path.startswith('hide'):
                    for k in fc.keyframe_points:
                        k.interpolation = 'CONSTANT'
        if o.type == 'LIGHT' and o.data.animation_data:
            set_interp(o.data, 'LINEAR')
    return objs


# ----------------------------------------------------------------------------- geometry-nodes helpers
def md_set(md, ident, v):
    s = getattr(md.properties.inputs, ident)
    s.value = tuple(v) if isinstance(v, (tuple, list, Vector)) else v


def md_key(ob, md, ident, frame, v):
    md_set(md, ident, v)
    ob.keyframe_insert(f'modifiers["{md.name}"].properties.inputs.{ident}.value', frame=frame)


class GN:
    def __init__(self, name):
        ng = bpy.data.node_groups.get(name)
        if ng:
            bpy.data.node_groups.remove(ng)
        self.ng = bpy.data.node_groups.new(name, 'GeometryNodeTree')
        self.gi = self.ng.nodes.new('NodeGroupInput')
        self.go = self.ng.nodes.new('NodeGroupOutput')
        self.ins = {}

    def add_in(self, name, typ, default=None, mn=None, mx=None):
        s = self.ng.interface.new_socket(name, in_out='INPUT', socket_type=typ)
        if default is not None:
            s.default_value = default
        if mn is not None:
            s.min_value = mn
        if mx is not None:
            s.max_value = mx
        self.ins[name] = s
        return s

    def add_out(self, name, typ):
        return self.ng.interface.new_socket(name, in_out='OUTPUT', socket_type=typ)

    def I(self, name):
        return self.gi.outputs[name]

    def n(self, kind, **kw):
        nd = self.ng.nodes.new(kind)
        for k, v in kw.items():
            setattr(nd, k, v)
        return nd

    def L(self, a, b):
        self.ng.links.new(a, b)

    def _set(self, sock, v):
        if v is None:
            return
        if isinstance(v, bpy.types.NodeSocket):
            self.L(v, sock)
        else:
            sock.default_value = v

    def math(self, op, a, b=None, c=None):
        nd = self.n('ShaderNodeMath', operation=op)
        for i, v in enumerate((a, b, c)):
            self._set(nd.inputs[i], v)
        return nd.outputs[0]

    def vmath(self, op, a, b=None, scale=None):
        nd = self.n('ShaderNodeVectorMath', operation=op)
        for i, v in enumerate((a, b)):
            self._set(nd.inputs[i], v)
        if scale is not None:
            self._set(inp(nd, 'Scale'), scale)
        return outp(nd, 'Value') if op in ('LENGTH', 'DOT_PRODUCT', 'DISTANCE') else outp(nd, 'Vector')

    def comb(self, x, y, z):
        nd = self.n('ShaderNodeCombineXYZ')
        for i, v in enumerate((x, y, z)):
            self._set(nd.inputs[i], v)
        return nd.outputs[0]

    def sep(self, v):
        nd = self.n('ShaderNodeSeparateXYZ')
        self.L(v, nd.inputs[0])
        return nd.outputs

    def rand(self, dtype, mn, mx, seed, idoff=0):
        nd = self.n('FunctionNodeRandomValue', data_type=dtype)
        self._set(inp(nd, 'Min'), mn)
        self._set(inp(nd, 'Max'), mx)
        self._set(inp(nd, 'Seed'), self.math('ADD', seed, idoff) if not isinstance(seed, int) else seed + idoff)
        return outp(nd, 'Value')


def _seed_int(G, seed_sock, off):
    """integer seed socket + offset (float math -> int via implicit conversion)."""
    return G.math('ADD', seed_sock, float(off))


def burst_group(kind='spark'):
    """GN ballistic burst. kind 'spark' (streaks aligned to velocity) or 'debris' (tumbling chunks)."""
    G = GN('FX_burst_' + kind)
    G.add_out('Geometry', 'NodeSocketGeometry')
    G.add_in('Geometry', 'NodeSocketGeometry')
    for nm, d in (('Age', 0.0), ('Delay Spread', 0.05), ('Speed Min', 8.0), ('Speed Max', 30.0), ('Up Bias', 0.6),
                  ('Drag', 1.2), ('Gravity', 9.81), ('Life Min', 0.4), ('Life Max', 1.4), ('Size', 0.05),
                  ('Streak', 0.03), ('Ground Z', 0.0), ('Radius', 0.3), ('Spin', 8.0), ('Size Var', 0.6)):
        G.add_in(nm, 'NodeSocketFloat', d)
    G.add_in('Count', 'NodeSocketInt', 200)
    G.add_in('Seed', 'NodeSocketInt', 0)
    G.add_in('Direction', 'NodeSocketVector', (0.0, 0.0, 1.0))
    G.add_in('Instance', 'NodeSocketObject')
    G.add_in('Material', 'NodeSocketMaterial')
    seed = G.I('Seed')
    pts = G.n('GeometryNodePoints')
    G.L(G.I('Count'), inp(pts, 'Count'))
    # per-point randoms
    rdir = G.rand('FLOAT_VECTOR', (-1, -1, -1), (1, 1, 1), seed, 0)
    dirn = G.vmath('NORMALIZE', G.vmath('ADD', G.vmath('NORMALIZE', rdir),
                                        G.vmath('SCALE', G.I('Direction'), scale=G.I('Up Bias'))))
    spd = G.rand('FLOAT', G.I('Speed Min'), G.I('Speed Max'), seed, 1)
    u = G.rand('FLOAT', 0.0, 1.0, seed, 2)
    spd = G.math('MULTIPLY', spd, G.math('ADD', 0.35, G.math('MULTIPLY', u, 0.65)))     # many slow, few fast
    v0 = G.vmath('SCALE', dirn, scale=spd)
    life = G.rand('FLOAT', G.I('Life Min'), G.I('Life Max'), seed, 3)
    delay = G.rand('FLOAT', 0.0, G.I('Delay Spread'), seed, 4)
    p0 = G.vmath('SCALE', G.vmath('NORMALIZE', G.rand('FLOAT_VECTOR', (-1, -1, -1), (1, 1, 1), seed, 5)),
                 scale=G.math('MULTIPLY', G.I('Radius'), G.rand('FLOAT', 0.2, 1.0, seed, 6)))
    t = G.math('MAXIMUM', G.math('SUBTRACT', G.I('Age'), delay), 0.0)
    t = G.math('MINIMUM', t, life)
    k = G.math('MAXIMUM', G.I('Drag'), 0.001)
    ekt = G.math('EXPONENT', G.math('MULTIPLY', G.math('MULTIPLY', k, t), -1.0))
    f = G.math('DIVIDE', G.math('SUBTRACT', 1.0, ekt), k)                # (1-e^-kt)/k
    gterm = G.math('DIVIDE', G.math('MULTIPLY', G.I('Gravity'), G.math('SUBTRACT', t, f)), k)
    pos = G.vmath('ADD', p0, G.vmath('SCALE', v0, scale=f))
    pos = G.vmath('SUBTRACT', pos, G.comb(0.0, 0.0, gterm))
    sx = G.sep(pos)
    size_r = G.math('MULTIPLY', G.I('Size'),
                    G.math('ADD', G.math('SUBTRACT', 1.0, G.I('Size Var')),
                           G.math('MULTIPLY', G.I('Size Var'), G.rand('FLOAT', 0.0, 2.0, seed, 7))))
    zc = G.math('MAXIMUM', sx[2], G.math('ADD', G.I('Ground Z'), G.math('MULTIPLY', size_r, 0.5)))
    on_ground = G.math('LESS_THAN', sx[2], G.math('ADD', G.I('Ground Z'), G.math('MULTIPLY', size_r, 0.5)))
    pos = G.comb(sx[0], sx[1], zc)
    vel = G.vmath('SUBTRACT', G.vmath('SCALE', v0, scale=ekt),
                  G.comb(0.0, 0.0, G.math('DIVIDE', G.math('MULTIPLY', G.I('Gravity'), G.math('SUBTRACT', 1.0, ekt)), k)))
    setp = G.n('GeometryNodeSetPosition')
    G.L(outp(pts, 'Points'), inp(setp, 'Geometry'))
    G.L(pos, inp(setp, 'Position'))
    # alive mask
    age_rel = G.math('DIVIDE', G.math('SUBTRACT', G.I('Age'), delay), life)
    dead = G.math('MAXIMUM', G.math('GREATER_THAN', age_rel, 0.999),
                  G.math('LESS_THAN', G.math('SUBTRACT', G.I('Age'), delay), 0.0))
    dl = G.n('GeometryNodeDeleteGeometry', domain='POINT')
    G.L(outp(setp, 'Geometry'), inp(dl, 'Geometry'))
    G.L(dead, inp(dl, 'Selection'))
    heat = G.math('MAXIMUM', G.math('SUBTRACT', 1.0, age_rel), 0.0)
    if kind != 'spark':
        heat = G.math('EXPONENT', G.math('MULTIPLY', t, -1.6))
    if kind == 'spark':
        fade = G.math('SUBTRACT', 1.0, G.math('POWER', G.math('MINIMUM', age_rel, 1.0), 3.0))
    else:
        fade = G.math('SUBTRACT', 1.0, G.math('POWER', G.math('MINIMUM', age_rel, 1.0), 8.0))
    st = G.n('GeometryNodeStoreNamedAttribute', data_type='FLOAT', domain='POINT')
    st.inputs['Name'].default_value = 'heat'
    G.L(outp(dl, 'Geometry'), inp(st, 'Geometry'))
    G.L(heat, inp(st, 'Value'))
    ioi = G.n('GeometryNodeInstanceOnPoints')
    G.L(outp(st, 'Geometry'), inp(ioi, 'Points'))
    oi = G.n('GeometryNodeObjectInfo')
    oi.transform_space = 'ORIGINAL'
    G.L(G.I('Instance'), inp(oi, 'Object'))
    G.L(outp(oi, 'Geometry'), inp(ioi, 'Instance'))
    sz = G.math('MULTIPLY', size_r, fade)
    if kind == 'spark':
        al = G.n('FunctionNodeAlignRotationToVector', axis='Z')
        G.L(vel, inp(al, 'Vector'))
        G.L(outp(al, 'Rotation'), inp(ioi, 'Rotation'))
        spd_now = G.vmath('LENGTH', vel)
        G.L(G.comb(sz, sz, G.math('ADD', sz, G.math('MULTIPLY', spd_now, G.I('Streak')))), inp(ioi, 'Scale'))
    else:
        r0 = G.rand('FLOAT_VECTOR', (0, 0, 0), (6.283, 6.283, 6.283), seed, 8)
        w = G.rand('FLOAT_VECTOR', (-1, -1, -1), (1, 1, 1), seed, 9)
        # spin decays once on the ground
        spin_t = G.math('MULTIPLY', t, G.math('SUBTRACT', 1.0, G.math('MULTIPLY', on_ground, 0.7)))
        rot = G.vmath('ADD', r0, G.vmath('SCALE', w, scale=G.math('MULTIPLY', G.I('Spin'), spin_t)))
        e2r = G.n('FunctionNodeEulerToRotation')
        G.L(rot, inp(e2r, 'Euler'))
        G.L(outp(e2r, 'Rotation'), inp(ioi, 'Rotation'))
        sv = G.rand('FLOAT_VECTOR', (0.6, 0.6, 0.6), (1.4, 1.4, 1.4), seed, 10)
        G.L(G.vmath('SCALE', sv, scale=sz), inp(ioi, 'Scale'))
    ri = G.n('GeometryNodeRealizeInstances')
    G.L(outp(ioi, 'Instances'), inp(ri, 'Geometry'))
    sm = G.n('GeometryNodeSetMaterial')
    G.L(outp(ri, 'Geometry'), inp(sm, 'Geometry'))
    G.L(G.I('Material'), inp(sm, 'Material'))
    G.L(outp(sm, 'Geometry'), G.go.inputs[0])
    return G.ng


def spark_material():
    m = bpy.data.materials.get('FX_spark')
    if m:
        return m
    m = new_mat('FX_spark')
    T = NT(m.node_tree)
    out = T.n('ShaderNodeOutputMaterial')
    em = T.n('ShaderNodeEmission')
    h = T.attr('heat', 'GEOMETRY')
    bb = T.n('ShaderNodeBlackbody')
    T.L(T.math('ADD', 1100.0, T.math('MULTIPLY', h, 2400.0)), inp(bb, 'Temperature'))
    T.L(bb.outputs[0], inp(em, 'Color'))
    T.L(T.math('ADD', 2.0, T.math('MULTIPLY', T.math('POWER', h, 1.5), 60.0)), inp(em, 'Strength'))
    T.L(em.outputs[0], out.inputs[0])
    return m


def debris_material():
    m = bpy.data.materials.get('FX_debris')
    if m:
        return m
    m = new_mat('FX_debris')
    T = NT(m.node_tree)
    out = T.n('ShaderNodeOutputMaterial')
    b = T.n('ShaderNodeBsdfPrincipled')
    inp(b, 'Base Color').default_value = (0.05, 0.045, 0.04, 1)
    inp(b, 'Roughness').default_value = 0.85
    h = T.attr('heat', 'GEOMETRY')
    # glowing embers early in flight
    T.L(T.math('MULTIPLY', T.math('POWER', h, 4.0), 18.0), inp(b, 'Emission Strength'))
    inp(b, 'Emission Color').default_value = (1.0, 0.35, 0.06, 1)
    T.L(b.outputs[0], out.inputs[0])
    return m


def proto_meshes(c):
    """hidden prototype objects used as burst instances."""
    out = {}
    if 'FX_proto_spark' not in bpy.data.objects:
        me = bpy.data.meshes.new('FX_proto_spark')
        bm = bmesh.new()
        bmesh.ops.create_cube(bm, size=1.0)
        bmesh.ops.translate(bm, verts=bm.verts, vec=(0, 0, -0.5))     # streak trails behind (along -velocity)
        bm.to_mesh(me)
        bm.free()
        o = bpy.data.objects.new('FX_proto_spark', me)
        c.objects.link(o)
        o.hide_render = o.hide_viewport = True
    out['spark'] = bpy.data.objects['FX_proto_spark']
    if 'FX_proto_chunk' not in bpy.data.objects:
        me = bpy.data.meshes.new('FX_proto_chunk')
        bm = bmesh.new()
        bmesh.ops.create_icosphere(bm, subdivisions=1, radius=0.6)
        rnd = random.Random(3)
        for v in bm.verts:
            v.co *= rnd.uniform(0.6, 1.25)
            v.co.z *= 0.6
        bm.to_mesh(me)
        bm.free()
        o = bpy.data.objects.new('FX_proto_chunk', me)
        c.objects.link(o)
        o.hide_render = o.hide_viewport = True
    out['chunk'] = bpy.data.objects['FX_proto_chunk']
    return out


def burst(name, loc, f0, fps, c, kind='spark', count=250, seed=1, speed=(8, 35), up=0.7, drag=1.4, life=(0.3, 1.2),
          size=0.04, streak=0.025, ground_z=None, radius=0.3, direction=(0, 0, 1), dur=None, spin=10.0, gravity=9.81):
    """emitter object at `loc`; Age keyed linearly from f0."""
    ng = bpy.data.node_groups.get('FX_burst_' + kind) or burst_group(kind)
    P = proto_meshes(coll('FX_protos'))
    me = bpy.data.meshes.new(name)
    ob = bpy.data.objects.new(name, me)
    c.objects.link(ob)
    ob.location = loc
    md = ob.modifiers.new('burst', 'NODES')
    md.node_group = ng
    vals = {'Count': count, 'Seed': seed, 'Speed Min': speed[0], 'Speed Max': speed[1], 'Up Bias': up, 'Drag': drag,
            'Life Min': life[0], 'Life Max': life[1], 'Size': size, 'Streak': streak, 'Radius': radius,
            'Ground Z': (ground_z - loc[2]) if ground_z is not None else -loc[2], 'Direction': direction,
            'Spin': spin, 'Gravity': gravity,
            'Instance': P['spark' if kind == 'spark' else 'chunk'],
            'Material': spark_material() if kind == 'spark' else debris_material()}
    ids = {s.name: s.identifier for s in ng.interface.items_tree if getattr(s, 'in_out', '') == 'INPUT'}
    for k, v in vals.items():
        md_set(md, ids[k], v)
    aid = ids['Age']
    if dur is None:
        dur = life[1] + 0.1 if kind == 'spark' else 12.0
    nfr = int(dur * fps) + 1
    md_key(ob, md, aid, f0, 0.0)
    md_key(ob, md, aid, f0 + nfr, nfr / fps)
    set_interp(ob, 'LINEAR')
    for fc in fcurves_of(ob.animation_data.action):
        fc.extrapolation = 'LINEAR'
        # age must not run backwards before f0: clamp handled by Delay/age<0 -> delete
    return ob


# ----------------------------------------------------------------------------- smoke trails (points -> volume)
def trail_group():
    G = GN('FX_trail')
    G.add_out('Geometry', 'NodeSocketGeometry')
    G.add_in('Geometry', 'NodeSocketGeometry')
    for nm, d in (('Time', 0.0), ('Life', 6.0), ('R0', 0.25), ('Grow', 0.9), ('Rise', 0.8), ('Voxel', 0.18),
                  ('Density', 1.0), ('Shrink Start', 0.6)):
        G.add_in(nm, 'NodeSocketFloat', d)
    G.add_in('Wind', 'NodeSocketVector', (0.5, 0.2, 0.0))
    G.add_in('Material', 'NodeSocketMaterial')
    m2p = G.n('GeometryNodeMeshToPoints')
    G.L(G.I('Geometry'), inp(m2p, 'Mesh'))
    na = G.n('GeometryNodeInputNamedAttribute', data_type='FLOAT')
    na.inputs['Name'].default_value = 'birth'
    birth = outp(na, 'Attribute')
    na2 = G.n('GeometryNodeInputNamedAttribute', data_type='FLOAT')
    na2.inputs['Name'].default_value = 'rscale'
    rsc = outp(na2, 'Attribute')
    a = G.math('SUBTRACT', G.I('Time'), birth)
    dead = G.math('MAXIMUM', G.math('LESS_THAN', a, 0.0), G.math('GREATER_THAN', a, G.I('Life')))
    dl = G.n('GeometryNodeDeleteGeometry', domain='POINT')
    G.L(outp(m2p, 'Points'), inp(dl, 'Geometry'))
    G.L(dead, inp(dl, 'Selection'))
    a = G.math('MAXIMUM', a, 0.0)
    pos = G.n('GeometryNodeInputPosition').outputs[0]
    drift = G.vmath('ADD', G.vmath('SCALE', G.I('Wind'), scale=a),
                    G.comb(0.0, 0.0, G.math('MULTIPLY', G.I('Rise'), G.math('SQRT', a))))
    sp = G.n('GeometryNodeSetPosition')
    G.L(outp(dl, 'Geometry'), inp(sp, 'Geometry'))
    G.L(G.vmath('ADD', pos, drift), inp(sp, 'Position'))
    lrel = G.math('DIVIDE', a, G.I('Life'))
    shrink = G.math('SUBTRACT', 1.0, G.math('POWER', G.math('MAXIMUM', G.math('DIVIDE', G.math(
        'SUBTRACT', lrel, G.I('Shrink Start')), G.math('SUBTRACT', 1.0001, G.I('Shrink Start'))), 0.0), 1.5))
    rad = G.math('MULTIPLY', G.math('MULTIPLY', G.math('ADD', G.I('R0'), G.math('MULTIPLY', G.I('Grow'), G.math('SQRT', a))),
                                    shrink), G.math('MAXIMUM', rsc, 0.05))
    pv = G.n('GeometryNodePointsToVolume')
    try:
        pv.resolution_mode = 'VOXEL_SIZE'
    except Exception:
        pass
    G.L(outp(sp, 'Geometry'), inp(pv, 'Points'))
    G.L(G.I('Density'), inp(pv, 'Density'))
    try:
        G.L(G.I('Voxel'), inp(pv, 'Voxel Size'))
    except KeyError:
        pass
    G.L(rad, inp(pv, 'Radius'))
    sm = G.n('GeometryNodeSetMaterial')
    G.L(outp(pv, 'Volume'), inp(sm, 'Geometry'))
    G.L(G.I('Material'), inp(sm, 'Material'))
    G.L(outp(sm, 'Geometry'), G.go.inputs[0])
    return G.ng


def trail_material(name='FX_trail_mat', col=(0.09, 0.085, 0.08), dens=2.5, noise=0.9, emis=None):
    m = bpy.data.materials.get(name)
    if m:
        return m
    m = new_mat(name)
    T = NT(m.node_tree)
    out = T.n('ShaderNodeOutputMaterial')
    pv = T.n('ShaderNodeVolumePrincipled')
    T.L(pv.outputs[0], out.inputs['Volume'])
    ga = T.attr('density', 'GEOMETRY')
    tc = T.n('ShaderNodeTexCoord')
    nz = T.n('ShaderNodeTexNoise')
    inp(nz, 'Scale').default_value = noise
    inp(nz, 'Detail').default_value = 6.0
    inp(nz, 'Roughness').default_value = 0.6
    T.L(outp(tc, 'Object'), inp(nz, 'Vector'))
    nmask = T.maprange(outp(nz, 'Fac'), 0.38, 0.62, 0.0, 1.0, 'SMOOTHSTEP')
    T.L(T.math('MULTIPLY', T.math('MULTIPLY', ga, nmask), dens), inp(pv, 'Density'))
    inp(pv, 'Color').default_value = (*col, 1)
    inp(pv, 'Anisotropy').default_value = 0.3
    if emis:
        inp(pv, 'Emission Color').default_value = (1.0, 0.4, 0.1, 1)
        inp(pv, 'Emission Strength').default_value = emis
    return m


def trail(name, pts, births, c, f_time0, fps, t_end, life=6.0, r0=0.25, grow=0.9, rise=0.8, wind=(0.5, 0.2, 0),
          voxel=0.18, density=1.0, rscale=None, material=None):
    """pts: world positions (list of Vector) emitted at story times births (s, relative to f_time0).
    Trail object Time is keyed 0 at f_time0 -> t_end. Emitted points appear when Time >= birth."""
    ng = bpy.data.node_groups.get('FX_trail') or trail_group()
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(p) for p in pts], [], [])
    at = me.attributes.new('birth', 'FLOAT', 'POINT')
    at.data.foreach_set('value', list(births))
    at2 = me.attributes.new('rscale', 'FLOAT', 'POINT')
    at2.data.foreach_set('value', list(rscale) if rscale is not None else [1.0] * len(pts))
    ob = bpy.data.objects.new(name, me)
    c.objects.link(ob)
    md = ob.modifiers.new('trail', 'NODES')
    md.node_group = ng
    ids = {s.name: s.identifier for s in ng.interface.items_tree if getattr(s, 'in_out', '') == 'INPUT'}
    for k, v in (('Life', life), ('R0', r0), ('Grow', grow), ('Rise', rise), ('Wind', wind), ('Voxel', voxel),
                 ('Density', density), ('Material', material or trail_material())):
        md_set(md, ids[k], v)
    tid = ids['Time']
    md_key(ob, md, tid, f_time0, 0.0)
    md_key(ob, md, tid, f_time0 + t_end * fps, t_end)
    set_interp(ob, 'LINEAR')
    for fc in fcurves_of(ob.animation_data.action):
        fc.extrapolation = 'CONSTANT'
    _hide_keys(ob, int(f_time0) + 1, int(f_time0 + t_end * fps))
    return ob


def column_points(src, t0, t1, rate=6.0, jitter=0.15, rnd=None):
    """smoke column emitted from a point `src` (or callable t->Vector) between story times t0..t1."""
    rnd = rnd or random.Random(1)
    pts, births = [], []
    n = int((t1 - t0) * rate)
    for i in range(n):
        t = t0 + i / rate
        p = Vector(src(t)) if callable(src) else Vector(src)
        p += Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), rnd.uniform(0, 1))) * jitter
        pts.append(p)
        births.append(t)
    return pts, births


# ----------------------------------------------------------------------------- fracture
def fracture(ob, n_pieces=60, seed=0, cap_mat=None, min_vol_frac=0.0015, bias_point=None, bias=0.0, prefix=None):
    """Recursive random-plane bisect of a closed mesh (world-applied). Returns new objects (origin at
    each piece centroid). Caps get `cap_mat`. `bias_point`: more cuts near it (smaller chunks at impact)."""
    rnd = random.Random(seed)
    bpy.context.view_layer.update()
    me = ob.data
    bm0 = bmesh.new()
    bm0.from_mesh(me)
    bm0.transform(ob.matrix_world)
    mats = list(me.materials)
    cap_idx = len(mats)
    if cap_mat is not None:
        mats.append(cap_mat)

    def vol_center(bm):
        co = np.array([v.co for v in bm.verts])
        return Vector(co.mean(0)), co

    pieces = [bm0]
    total = None
    guard = 0
    while len(pieces) < n_pieces and guard < n_pieces * 6:
        guard += 1
        # pick the piece to split: largest extent, weighted towards bias point
        best, bi = -1, 0
        for i, b in enumerate(pieces):
            c, co = vol_center(b)
            ext = (co.max(0) - co.min(0))
            s = float(np.prod(np.maximum(ext, 0.02))) ** (1 / 3)
            if bias_point is not None and bias > 0:
                s *= 1.0 + bias * math.exp(-(c - Vector(bias_point)).length / 4.0)
            s *= rnd.uniform(0.85, 1.15)
            if s > best:
                best, bi = s, i
        b = pieces.pop(bi)
        c, co = vol_center(b)
        ext = co.max(0) - co.min(0)
        if total is None:
            total = float(np.prod(np.maximum(ext, 0.02)))
        # plane normal: prefer cutting across the longest dimension
        w = ext / (ext.sum() + 1e-9)
        nrm = Vector((rnd.gauss(0, 1) * (0.3 + w[0]), rnd.gauss(0, 1) * (0.3 + w[1]),
                      rnd.gauss(0, 1) * (0.3 + w[2]))).normalized()
        pc = Vector(co.mean(0)) + Vector((rnd.uniform(-.25, .25) * ext[0], rnd.uniform(-.25, .25) * ext[1],
                                          rnd.uniform(-.25, .25) * ext[2]))
        halves = []
        for side in (1, -1):
            bb = b.copy()
            geom = bb.verts[:] + bb.edges[:] + bb.faces[:]
            r = bmesh.ops.bisect_plane(bb, geom=geom, plane_co=pc, plane_no=nrm * side, clear_inner=True,
                                       clear_outer=False, dist=1e-5)
            cut_edges = [e for e in r['geom_cut'] if isinstance(e, bmesh.types.BMEdge)]
            if cut_edges:
                try:
                    f = bmesh.ops.edgeloop_fill(bb, edges=cut_edges)
                    newf = f['faces']
                except Exception:
                    newf = bmesh.ops.holes_fill(bb, edges=cut_edges, sides=0)['faces']
                for fc in newf:
                    fc.material_index = cap_idx if cap_mat is not None else fc.material_index
                    fc.smooth = False
            if len(bb.verts) < 4 or len(bb.faces) < 4:
                bb.free()
                continue
            halves.append(bb)
        if len(halves) < 2:
            for h in halves:
                h.free()
            pieces.append(b)
            continue
        b.free()
        pieces.extend(halves)
    out = []
    pre = prefix or ob.name + '_frag'
    for i, b in enumerate(pieces):
        c, co = vol_center(b)
        bmesh.ops.translate(b, verts=b.verts, vec=-c)
        nm = bpy.data.meshes.new(f'{pre}_{i:03d}')
        b.to_mesh(nm)
        b.free()
        for m in mats:
            nm.materials.append(m)
        o = bpy.data.objects.new(f'{pre}_{i:03d}', nm)
        o.location = c
        out.append(o)
    bm0.free()
    return out


def concrete_cap_material():
    m = bpy.data.materials.get('FX_concrete_inner')
    if m:
        return m
    m = new_mat('FX_concrete_inner')
    T = NT(m.node_tree)
    out = T.n('ShaderNodeOutputMaterial')
    b = T.n('ShaderNodeBsdfPrincipled')
    tc = T.n('ShaderNodeTexCoord')
    nz = T.n('ShaderNodeTexNoise')
    inp(nz, 'Scale').default_value = 14.0
    inp(nz, 'Detail').default_value = 8.0
    T.L(outp(tc, 'Object'), inp(nz, 'Vector'))
    ramp = T.n('ShaderNodeValToRGB')
    ramp.color_ramp.elements[0].color = (0.22, 0.21, 0.19, 1)
    ramp.color_ramp.elements[1].color = (0.42, 0.40, 0.36, 1)
    T.L(outp(nz, 'Fac'), ramp.inputs[0])
    # rebar: thin rusty grid lines through the section
    w = T.n('ShaderNodeTexWave', wave_type='BANDS', bands_direction='X')
    inp(w, 'Scale').default_value = 3.0
    inp(w, 'Distortion').default_value = 0.0
    T.L(outp(tc, 'Object'), inp(w, 'Vector'))
    w2 = T.n('ShaderNodeTexWave', wave_type='BANDS', bands_direction='Z')
    inp(w2, 'Scale').default_value = 3.0
    T.L(outp(tc, 'Object'), inp(w2, 'Vector'))
    reb = T.math('MAXIMUM', T.maprange(outp(w, 'Fac'), 0.93, 0.97), T.maprange(outp(w2, 'Fac'), 0.93, 0.97))
    mix = T.n('ShaderNodeMix', data_type='RGBA')
    T.L(reb, inp(mix, 'Factor'))
    T.L(ramp.outputs[0], inp(mix, 'A', 0) if False else mix.inputs[6])
    mix.inputs[7].default_value = (0.16, 0.06, 0.025, 1)
    T.L(mix.outputs[2], inp(b, 'Base Color'))
    T.L(T.maprange(reb, 0, 1, 0.92, 0.5), inp(b, 'Roughness'))
    T.L(reb, inp(b, 'Metallic'))
    bump = T.n('ShaderNodeBump')
    inp(bump, 'Strength').default_value = 0.6
    T.L(outp(nz, 'Fac'), inp(bump, 'Height'))
    T.L(outp(bump, 'Normal'), inp(b, 'Normal'))
    T.L(b.outputs[0], out.inputs[0])
    return m


# ----------------------------------------------------------------------------- rigid body simulation
class RigidSim:
    """Builds a temporary rigid-body world, runs it, records world matrices.

    Story time is continuous; the sim runs with time_scale = 1/oversample so one scene frame is
    1/(fps*oversample) s.  Records are returned as arrays [n_bodies, n_samples, 4, 4] together with the
    sample times (s, relative to the sim start)."""

    def __init__(self, fps=24, oversample=4, substeps=4, iterations=20):
        sc = bpy.context.scene
        self.sc = sc
        self.fps = fps
        self.os = oversample
        if sc.rigidbody_world is None:
            bpy.ops.rigidbody.world_add()
        rw = sc.rigidbody_world
        rw.time_scale = 1.0 / oversample
        rw.substeps_per_frame = substeps
        rw.solver_iterations = iterations
        rw.use_split_impulse = True
        self.rw = rw
        self.bodies = []
        self.vel = {}

    def add(self, ob, mass=1.0, shape='CONVEX_HULL', friction=0.6, bounce=0.1, passive=False, margin=0.02,
            lin_damp=0.06, ang_damp=0.12, kinematic=False):
        if ob.rigid_body is None:
            with bpy.context.temp_override(object=ob, active_object=ob, selected_objects=[ob]):
                bpy.ops.rigidbody.object_add()
        elif ob.name not in self.rw.collection.objects:
            self.rw.collection.objects.link(ob)
        rb = ob.rigid_body
        rb.type = 'PASSIVE' if passive else 'ACTIVE'
        rb.collision_shape = shape
        rb.mass = mass
        rb.friction = friction
        rb.restitution = bounce
        rb.use_margin = True
        rb.collision_margin = margin
        rb.linear_damping = lin_damp
        rb.angular_damping = ang_damp
        rb.kinematic = kinematic
        if not passive:
            self.bodies.append(ob)
        return rb

    def launch(self, ob, v, w, f_start, f_release=None):
        """initial linear velocity v (m/s) and angular velocity w (rad/s, world) at sim frame f_start
        by keying a kinematic move over one sim frame, then releasing to dynamic."""
        self.vel[ob.name] = (Vector(v), Vector(w), f_start, f_release)

    def run(self, f_start, n_frames, log=print):
        sc = self.sc
        dt = 1.0 / (self.fps * self.os)
        # pre-key kinematic launch
        for ob in self.bodies:
            if ob.name not in self.vel:
                continue
            v, w, fs, fr = self.vel[ob.name]
            fr = fr or fs + 1
            M0 = ob.matrix_world.copy()
            loc0, rot0 = M0.to_translation(), M0.to_quaternion()
            ob.rotation_mode = 'QUATERNION'
            ob.rigid_body.kinematic = True
            ob.location, ob.rotation_quaternion = loc0, rot0
            ob.keyframe_insert('location', frame=fs - 1)
            ob.keyframe_insert('rotation_quaternion', frame=fs - 1)
            ob.keyframe_insert('rigid_body.kinematic', frame=fs - 1)
            k = fr - fs + 1
            ob.location = loc0 + v * dt * k
            ang = w.length * dt * k
            q = Quaternion(w.normalized(), ang) if w.length > 1e-6 else Quaternion()
            ob.rotation_quaternion = q @ rot0
            ob.keyframe_insert('location', frame=fr)
            ob.keyframe_insert('rotation_quaternion', frame=fr)
            ob.keyframe_insert('rigid_body.kinematic', frame=fr)
            ob.rigid_body.kinematic = False
            ob.keyframe_insert('rigid_body.kinematic', frame=fr + 1)
            set_interp(ob, 'LINEAR')
            for fc in fcurves_of(ob.animation_data.action):
                if 'kinematic' in fc.data_path:
                    for kp in fc.keyframe_points:
                        kp.interpolation = 'CONSTANT'
        pc = self.rw.point_cache
        pc.frame_start = f_start - 2
        pc.frame_end = f_start + n_frames + 2
        sc.frame_start = f_start - 2
        sc.frame_end = f_start + n_frames + 2
        nb = len(self.bodies)
        rec = np.zeros((nb, n_frames, 4, 4), dtype=np.float32)
        sc.frame_set(f_start - 2)
        sc.frame_set(f_start - 1)
        for i in range(n_frames):
            sc.frame_set(f_start + i)
            dg = bpy.context.evaluated_depsgraph_get()
            for j, ob in enumerate(self.bodies):
                rec[j, i] = np.array(ob.evaluated_get(dg).matrix_world)
            if log and i % 100 == 0:
                log(f'  sim frame {i}/{n_frames}')
        times = np.arange(n_frames) * dt
        return rec, times

    def teardown(self):
        for ob in self.bodies:
            if ob.animation_data:
                ob.animation_data_clear()
            try:
                with bpy.context.temp_override(object=ob, active_object=ob, selected_objects=[ob]):
                    bpy.ops.rigidbody.object_remove()
            except Exception as e:
                print('rb remove failed', ob.name, e)
        for ob in list(self.rw.collection.objects) if self.rw.collection else []:
            with bpy.context.temp_override(object=ob, active_object=ob, selected_objects=[ob]):
                bpy.ops.rigidbody.object_remove()
        bpy.ops.rigidbody.world_remove()


def bake_records(objs, rec, times, f0, fps, step=1):
    """write recorded matrices as fcurves. times (s) relative to story frame f0. Keys may be fractional."""
    frames = f0 + times[::step] * fps
    for j, ob in enumerate(objs):
        ob.animation_data_clear()
        ob.rigid_body is not None and None
        ob.rotation_mode = 'QUATERNION'
        M = rec[j, ::step]
        loc = M[:, :3, 3]
        qs = np.array([tuple(Matrix(m.tolist()).to_quaternion()) for m in M])
        for i in range(1, len(qs)):                        # hemisphere continuity
            if np.dot(qs[i], qs[i - 1]) < 0:
                qs[i] = -qs[i]
        sc_ = np.array([Matrix(m.tolist()).to_scale() for m in M[:1]])[0]
        ob.scale = sc_
        for k in range(3):
            set_keys_fast(ob, 'location', k, frames, loc[:, k])
        for k in range(4):
            set_keys_fast(ob, 'rotation_quaternion', k, frames, qs[:, k])

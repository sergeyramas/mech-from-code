# Environment kit - shared helpers: collections, list-based mesh builder, noise, booleans,
# GN point-instancer, shader-node helpers. Pure code, no external assets.
import os
import bpy, bmesh, math, random
from mathutils import Vector, Matrix, Euler, noise

D2R = math.radians
ROOT = os.path.expanduser('~/Documents/learning/mech-test/blender')


# ---------------- math ----------------
def smoothstep(a, b, x):
    if a == b:
        return 1.0 if x >= b else 0.0
    t = min(1.0, max(0.0, (x - a) / (b - a)))
    return t * t * (3 - 2 * t)


def lerp(a, b, t):
    return a + (b - a) * t


def fbm(x, y, octaves=4, seed=0, lac=2.0, gain=0.5):
    s = 0.0
    a = 1.0
    f = 1.0
    nrm = 0.0
    for i in range(octaves):
        s += a * noise.noise(Vector((x * f + seed * 13.17, y * f - seed * 7.71, seed * 3.31 + i * 1.73)))
        nrm += a
        a *= gain
        f *= lac
    return s / nrm


def rot(rx=0.0, ry=0.0, rz=0.0):
    return Euler((D2R(rx), D2R(ry), D2R(rz)), 'XYZ').to_matrix().to_4x4()


def TR(loc, r=(0, 0, 0), s=None):
    m = Matrix.Translation(Vector(loc)) @ rot(*r)
    if s is not None:
        if isinstance(s, (int, float)):
            s = (s, s, s)
        m = m @ Matrix.Diagonal((s[0], s[1], s[2], 1.0))
    return m


# ---------------- collections ----------------
def get_coll(name, parent=None):
    c = bpy.data.collections.get(name)
    if c is None:
        c = bpy.data.collections.new(name)
        (parent if parent is not None else bpy.context.scene.collection).children.link(c)
    return c


def layer_coll(name, lc=None):
    lc = lc or bpy.context.view_layer.layer_collection
    if lc.name == name:
        return lc
    for ch in lc.children:
        r = layer_coll(name, ch)
        if r:
            return r
    return None


# ---------------- mesh builder ----------------
class MB:
    """list based mesh builder: verts, faces, per-face material index, optional point attributes"""

    def __init__(self):
        self.V = []
        self.F = []
        self.M = []
        self.PA = {}

    def add(self, verts, faces, m=0, mat=None, attrs=None):
        o = len(self.V)
        for co in verts:
            v = Vector(co)
            if mat is not None:
                v = mat @ v
            self.V.append((v.x, v.y, v.z))
        for fc in faces:
            self.F.append(tuple(i + o for i in fc))
            self.M.append(m)
        n = len(self.V)
        for k in dict.fromkeys(list(self.PA.keys()) + list((attrs or {}).keys())):
            lst = self.PA.setdefault(k, [])
            lst.extend([0.0] * (o - len(lst)))
            val = (attrs or {}).get(k, 0.0)
            if callable(val):
                lst.extend([val(Vector(self.V[i])) for i in range(o, n)])
            else:
                lst.extend([val] * (n - o))
        return o

    def box(self, size, mat=None, m=0, c=(0, 0, 0), attrs=None):
        sx, sy, sz = size[0] / 2, size[1] / 2, size[2] / 2
        cx, cy, cz = c
        verts = [(cx + x * sx, cy + y * sy, cz + z * sz) for x in (-1, 1) for y in (-1, 1) for z in (-1, 1)]
        faces = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
        return self.add(verts, faces, m, mat, attrs)

    def box_pts(self, p0, p1, w, h, m=0, up=(0, 0, 1)):
        """beam box from p0 to p1 with cross section w (side) x h (up)"""
        p0, p1 = Vector(p0), Vector(p1)
        d = p1 - p0
        L = d.length
        y = d.normalized()
        u = Vector(up)
        if abs(u.dot(y)) > 0.98:
            u = Vector((1, 0, 0))
        x = y.cross(u).normalized()
        z = x.cross(y)
        M = Matrix((x, y, z)).transposed().to_4x4()
        M.translation = (p0 + p1) / 2
        return self.box((w, L, h), M, m)

    def cyl(self, p0, p1, r0, r1=None, n=8, m=0, caps=True, ang0=0.0):
        p0, p1 = Vector(p0), Vector(p1)
        r1 = r0 if r1 is None else r1
        d = (p1 - p0).normalized()
        a = Vector((0, 0, 1)) if abs(d.z) < 0.9 else Vector((1, 0, 0))
        u = d.cross(a).normalized()
        w = d.cross(u)
        verts = []
        for p, r in ((p0, r0), (p1, r1)):
            for i in range(n):
                t = 2 * math.pi * i / n + ang0
                verts.append(p + (u * math.cos(t) + w * math.sin(t)) * r)
        faces = [(i, (i + 1) % n, n + (i + 1) % n, n + i) for i in range(n)]
        if caps:
            faces += [tuple(reversed(range(n))), tuple(range(n, 2 * n))]
        return self.add(verts, faces, m)

    def tube(self, pts, r, n=4, m=0, caps=False):
        """polyline tube (wires, rebar, branches); r may be a list per point"""
        pts = [Vector(p) for p in pts]
        rs = r if isinstance(r, (list, tuple)) else [r] * len(pts)
        verts = []
        prev_u = None
        for k, p in enumerate(pts):
            if k == 0:
                d = pts[1] - pts[0]
            elif k == len(pts) - 1:
                d = pts[-1] - pts[-2]
            else:
                d = pts[k + 1] - pts[k - 1]
            d.normalize()
            if prev_u is None:
                a = Vector((0, 0, 1)) if abs(d.z) < 0.9 else Vector((1, 0, 0))
                u = d.cross(a).normalized()
            else:
                u = (prev_u - d * prev_u.dot(d))
                if u.length < 1e-6:
                    u = d.cross(Vector((0, 0, 1))).normalized()
                u.normalize()
            prev_u = u
            w = d.cross(u)
            for i in range(n):
                t = 2 * math.pi * i / n
                verts.append(p + (u * math.cos(t) + w * math.sin(t)) * rs[k])
        faces = []
        for k in range(len(pts) - 1):
            a, b = k * n, (k + 1) * n
            for i in range(n):
                faces.append((a + i, a + (i + 1) % n, b + (i + 1) % n, b + i))
        if caps:
            faces += [tuple(reversed(range(n))), tuple(range((len(pts) - 1) * n, len(pts) * n))]
        return self.add(verts, faces, m)

    def prism(self, prof, z0, z1, mat=None, m=0, caps=True):
        """extrude CCW 2D profile along local z"""
        k = len(prof)
        verts = [(x, y, z0) for x, y in prof] + [(x, y, z1) for x, y in prof]
        faces = [(i, (i + 1) % k, k + (i + 1) % k, k + i) for i in range(k)]
        if caps:
            faces += [tuple(reversed(range(k))), tuple(range(k, 2 * k))]
        return self.add(verts, faces, m, mat)

    def grid(self, xs, ys, zf, m=0, mat=None, skip=None):
        """height-field grid over xs*ys, zf(x,y)->z; skip(i,j)->True drops a cell"""
        nx = len(xs)
        verts = [(x, y, zf(x, y)) for y in ys for x in xs]
        faces = []
        for j in range(len(ys) - 1):
            for i in range(nx - 1):
                if skip and skip(i, j):
                    continue
                a = j * nx + i
                faces.append((a, a + 1, a + nx + 1, a + nx))
        return self.add(verts, faces, m, mat)

    def obj(self, name, coll, mats, loc=(0, 0, 0), smooth=None, uv=None):
        old = bpy.data.objects.get(name)
        if old:
            bpy.data.objects.remove(old, do_unlink=True)
        me = bpy.data.meshes.new(name)
        l = Vector(loc)
        me.from_pydata([(x - l.x, y - l.y, z - l.z) for x, y, z in self.V], [], self.F)
        for mt in mats:
            me.materials.append(mt)
        if len(me.polygons) == len(self.M):
            me.polygons.foreach_set('material_index', self.M)
        for k, vals in self.PA.items():
            vals = vals + [0.0] * (len(self.V) - len(vals))
            a = me.attributes.new(k, 'FLOAT', 'POINT')
            a.data.foreach_set('value', vals)
        if uv is not None:
            uvl = me.uv_layers.new(name='UVMap')
            uvl.data.foreach_set('uv', [c for p in me.polygons for li in p.loop_indices
                                        for c in uv[me.loops[li].vertex_index]])
        if smooth is not None:
            me.polygons.foreach_set('use_smooth', [True] * len(me.polygons))
            if hasattr(me, 'set_sharp_from_angle'):
                me.set_sharp_from_angle(angle=D2R(smooth))
        me.validate(clean_customdata=False)
        me.update()
        ob = bpy.data.objects.new(name, me)
        ob.location = l
        coll.objects.link(ob)
        return ob


def noisy_blob(name, coll, center, radii, amp=0.25, freq=1.6, seed=0, subdiv=3, mat=None):
    """displaced icosphere used as boolean cutter / rubble mound"""
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=subdiv, radius=1.0)
    for v in bm.verts:
        n = v.co.normalized()
        d = 1.0 + amp * fbm(n.x * freq + seed, n.y * freq, 4, seed) + amp * 0.5 * noise.noise(n * freq * 4 + Vector((seed, 0, 0)))
        v.co = Vector((n.x * radii[0] * d, n.y * radii[1] * d, n.z * radii[2] * d))
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    if mat:
        me.materials.append(mat)
    ob = bpy.data.objects.new(name, me)
    ob.location = center
    coll.objects.link(ob)
    return ob


def apply_boolean(target, cutters, op='DIFFERENCE', solver='EXACT'):
    for c in cutters:
        md = target.modifiers.new('bool', 'BOOLEAN')
        md.operation = op
        md.object = c
        md.solver = solver
        try:
            md.material_mode = 'TRANSFER'
        except Exception:
            pass
    bake_modifiers(target)


def bake_modifiers(ob):
    dg = bpy.context.evaluated_depsgraph_get()
    ev = ob.evaluated_get(dg)
    me = bpy.data.meshes.new_from_object(ev, preserve_all_data_layers=True, depsgraph=dg)
    old = ob.data
    ob.modifiers.clear()
    ob.data = me
    if old.users == 0:
        bpy.data.meshes.remove(old)


def join(objs, name=None):
    objs = [o for o in objs if o is not None and o.type == 'MESH' and len(o.data.polygons)]
    if not objs:
        return None
    if len(objs) > 1:
        with bpy.context.temp_override(active_object=objs[0], object=objs[0], selected_objects=objs,
                                       selected_editable_objects=objs):
            bpy.ops.object.join()
    if name:
        objs[0].name = name
        objs[0].data.name = name
    return objs[0]


def tri_count_mesh(me):
    me.calc_loop_triangles()
    return len(me.loop_triangles)


# ---------------- GN point instancer ----------------
def instancer_group():
    ng = bpy.data.node_groups.get('ENV_PointInstancer')
    if ng:
        return ng
    ng = bpy.data.node_groups.new('ENV_PointInstancer', 'GeometryNodeTree')
    ng.interface.new_socket('Geometry', in_out='INPUT', socket_type='NodeSocketGeometry')
    ng.interface.new_socket('Set', in_out='INPUT', socket_type='NodeSocketCollection')
    ng.interface.new_socket('Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')
    N = ng.nodes
    L = ng.links
    gi = N.new('NodeGroupInput')
    go = N.new('NodeGroupOutput')
    ci = N.new('GeometryNodeCollectionInfo')
    ci.transform_space = 'ORIGINAL'
    ci.inputs['Separate Children'].default_value = True
    ci.inputs['Reset Children'].default_value = True
    L.new(gi.outputs['Set'], ci.inputs['Collection'])
    iop = N.new('GeometryNodeInstanceOnPoints')
    iop.inputs['Pick Instance'].default_value = True
    L.new(gi.outputs['Geometry'], iop.inputs['Points'])
    L.new(ci.outputs['Instances'], iop.inputs['Instance'])

    def named(nm, dt):
        a = N.new('GeometryNodeInputNamedAttribute')
        a.data_type = dt
        a.inputs['Name'].default_value = nm
        return a.outputs['Attribute']

    L.new(named('pick', 'INT'), iop.inputs['Instance Index'])
    e2r = N.new('FunctionNodeEulerToRotation')
    L.new(named('rot', 'FLOAT_VECTOR'), e2r.inputs['Euler'])
    L.new(e2r.outputs['Rotation'], iop.inputs['Rotation'])
    L.new(named('scl', 'FLOAT_VECTOR'), iop.inputs['Scale'])
    L.new(iop.outputs['Instances'], go.inputs['Geometry'])
    return ng


def set_children_names(set_coll):
    """Collection Info 'separate children' order = alphabetical object names"""
    return sorted(o.name for o in set_coll.objects)


def instance_points(name, coll, set_coll, items):
    """items: list of (loc, rot_euler_radians, scale(float|xyz), proto_name)"""
    names = set_children_names(set_coll)
    idx = {n: i for i, n in enumerate(names)}
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(it[0]) for it in items], [], [])
    a = me.attributes.new('rot', 'FLOAT_VECTOR', 'POINT')
    a.data.foreach_set('vector', [c for it in items for c in it[1]])
    a = me.attributes.new('scl', 'FLOAT_VECTOR', 'POINT')
    sc = []
    for it in items:
        s = it[2]
        sc.extend((s, s, s) if isinstance(s, (int, float)) else s)
    a.data.foreach_set('vector', sc)
    a = me.attributes.new('pick', 'INT', 'POINT')
    a.data.foreach_set('value', [idx[it[3]] for it in items])
    ob = bpy.data.objects.new(name, me)
    coll.objects.link(ob)
    md = ob.modifiers.new('instancer', 'NODES')
    md.node_group = instancer_group()
    sid = next(s.identifier for s in md.node_group.interface.items_tree
               if getattr(s, 'in_out', '') == 'INPUT' and s.name == 'Set')
    set_mod_input(md, sid, set_coll)
    return ob


def set_mod_input(md, sid, val):
    ins = getattr(getattr(md, 'properties', None), 'inputs', None)
    if ins is not None:
        getattr(ins, sid).value = val                # Blender 5.x: inputs.<Socket_n>.value
    else:
        md[sid] = val                                # Blender 4.x


def coll_instance(name, coll, src_coll, loc, rz=0.0, rx=0.0, ry=0.0, s=1.0):
    e = bpy.data.objects.new(name, None)
    e.instance_type = 'COLLECTION'
    e.instance_collection = src_coll
    e.location = loc
    e.rotation_euler = (rx, ry, rz)
    e.scale = (s, s, s) if isinstance(s, (int, float)) else s
    e.empty_display_size = 0.5
    coll.objects.link(e)
    return e


# ---------------- shader node helpers ----------------
def _sock(socks, key):
    if isinstance(key, int):
        return socks[key]
    for s in socks:
        if s.identifier == key:
            return s
    for s in socks:
        if s.name == key and s.enabled:
            return s
    return socks[key]


def nn(nt, t, inputs=None, **props):
    n = nt.nodes.new(t)
    for k, v in props.items():
        setattr(n, k, v)
    for k, v in (inputs or {}).items():
        s = _sock(n.inputs, k)
        if isinstance(v, bpy.types.NodeSocket):
            nt.links.new(v, s)
        else:
            if isinstance(v, (tuple, list)) and len(v) == 3 and getattr(s, 'type', '') == 'RGBA':
                v = (*v, 1.0)
            s.default_value = v
    return n


def o(n, key=0):
    return _sock(n.outputs, key)


def new_mat(name):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    m.node_tree.nodes.clear()
    return m, m.node_tree


def texco(nt, kind='Object'):
    return o(nn(nt, 'ShaderNodeTexCoord'), kind)


def attr(nt, name, kind='GEOMETRY', out='Fac'):
    a = nn(nt, 'ShaderNodeAttribute', attribute_name=name)
    try:
        a.attribute_type = kind
    except Exception:
        pass
    return o(a, out)


def objrand(nt):
    return o(nn(nt, 'ShaderNodeObjectInfo'), 'Random')


def mapv(nt, v, scale=(1, 1, 1), loc=(0, 0, 0)):
    return o(nn(nt, 'ShaderNodeMapping', {'Vector': v, 'Scale': scale, 'Location': loc}), 'Vector')


def noi(nt, v, scale, detail=4.0, rough=0.55, dist=0.0, out='Fac', dims='3D'):
    n = nn(nt, 'ShaderNodeTexNoise', {'Vector': v, 'Scale': scale, 'Detail': detail, 'Roughness': rough,
                                       'Distortion': dist})
    try:
        n.noise_dimensions = dims
    except Exception:
        pass
    return o(n, out)


def vor(nt, v, scale, feature='F1', out='Distance', rand=1.0):
    n = nn(nt, 'ShaderNodeTexVoronoi', {'Vector': v, 'Scale': scale, 'Randomness': rand})
    n.feature = feature
    return o(n, out)


def ramp(nt, fac, stops, interp='LINEAR'):
    r = nn(nt, 'ShaderNodeValToRGB')
    r.color_ramp.interpolation = interp
    el = r.color_ramp.elements
    def c4(c):
        if isinstance(c, (int, float)):
            return (c, c, c, 1.0)
        return (*c, 1.0) if len(c) == 3 else tuple(c)
    el[0].position, el[0].color = stops[0][0], c4(stops[0][1])
    el[1].position, el[1].color = stops[-1][0], c4(stops[-1][1])
    for p, c in stops[1:-1]:
        e = el.new(p)
        e.color = c4(c)
    nt.links.new(fac, r.inputs['Fac'])
    return o(r, 'Color')


def mth(nt, op, a, b=0.0, clamp=False):
    n = nn(nt, 'ShaderNodeMath', operation=op, use_clamp=clamp)
    for k, v in enumerate((a, b)):
        if isinstance(v, bpy.types.NodeSocket):
            nt.links.new(v, n.inputs[k])
        else:
            n.inputs[k].default_value = v
    return o(n, 'Value')


def mix(nt, fac, a, b, blend='MIX'):
    n = nn(nt, 'ShaderNodeMix', data_type='RGBA', blend_type=blend, clamp_factor=True)
    for ident, v in (('Factor_Float', fac), ('A_Color', a), ('B_Color', b)):
        s = _sock(n.inputs, ident)
        if isinstance(v, bpy.types.NodeSocket):
            nt.links.new(v, s)
        elif isinstance(v, (int, float)):
            s.default_value = v if ident == 'Factor_Float' else (v, v, v, 1.0)
        else:
            s.default_value = (*v, 1.0) if len(v) == 3 else v
    return o(n, 'Result_Color')


def sstep(nt, x, a, b):
    """smoothstep via map range"""
    n = nn(nt, 'ShaderNodeMapRange', {'Value': x, 'From Min': a, 'From Max': b, 'To Min': 0.0, 'To Max': 1.0},
           interpolation_type='SMOOTHSTEP', clamp=True)
    return o(n, 'Result')


def sepxyz(nt, v):
    n = nn(nt, 'ShaderNodeSeparateXYZ', {'Vector': v})
    return o(n, 'X'), o(n, 'Y'), o(n, 'Z')


def bump(nt, h, strength=0.3, dist=0.02, normal=None):
    ins = {'Height': h, 'Strength': strength, 'Distance': dist}
    if normal is not None:
        ins['Normal'] = normal
    return o(nn(nt, 'ShaderNodeBump', ins), 'Normal')


def bsdf(nt, base, rough=0.8, metal=0.0, normal=None, spec=0.5, extra=None):
    ins = {'Base Color': base, 'Roughness': rough, 'Metallic': metal, 'Specular IOR Level': spec}
    if normal is not None:
        ins['Normal'] = normal
    ins.update(extra or {})
    return o(nn(nt, 'ShaderNodeBsdfPrincipled', ins), 'BSDF')


def out_mat(nt, surf=None, vol=None):
    n = nn(nt, 'ShaderNodeOutputMaterial')
    if surf is not None:
        nt.links.new(surf, n.inputs['Surface'])
    if vol is not None:
        nt.links.new(vol, n.inputs['Volume'])
    return n

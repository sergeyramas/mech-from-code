"""
heavy_mech_v3_env.blend  —  diorama builder (30×30 m military-industrial)
Run from Blender MCP after opening (or creating) the env file.
Step 1: load v3.blend via append, place in Environment collection
Step 2: build ground, terrain, concrete slab, road tracks
Step 3: props – crates, barrels, sandbags, barriers, lamp posts, rocks, rubble
Step 4: vehicles – jeep, truck, APC/tank, fuel cistern, forklift
Step 5: structures – hangar/bunker
Step 6: lighting (sun + fog + volumetric)
Step 7: tweak mech materials (olive / dirty)
Step 8: save & render
"""

import bpy, bmesh, math, random, os, sys
from mathutils import Vector, Matrix, Euler

# ── add env_common to path ────────────────────────────────────────────────────
SCRIPTS = os.path.expanduser('~/Documents/learning/mech-test/blender/scripts')
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)
if SCRIPTS + '/env' not in sys.path:
    sys.path.insert(0, SCRIPTS + '/env')

import env_common as ec
from env_common import (MB, get_coll, new_mat, nn, o, texco, noi, ramp, mth,
                        mix, bump, bsdf, out_mat, fbm, D2R, TR, mapv, vor,
                        sstep, sepxyz, attr, objrand)

ROOT   = os.path.expanduser('~/Documents/learning/mech-test/blender')
SRC    = os.path.join(ROOT, 'heavy_mech_v3.blend')
DEST   = os.path.join(ROOT, 'heavy_mech_v3_env.blend')
RENDER = os.path.join(ROOT, 'renders')
os.makedirs(RENDER, exist_ok=True)

rng = random.Random(42)

sc = bpy.context.scene

# ══════════════════════════════════════════════════════════════════════════════
# 0.  SCENE SETUP  (save as new file)
# ══════════════════════════════════════════════════════════════════════════════
bpy.ops.wm.save_as_mainfile(filepath=DEST)

# ── render engine ─────────────────────────────────────────────────────────────
try:
    sc.render.engine = 'BLENDER_EEVEE'
except TypeError as e:
    valid = [i.identifier for i in sc.render.bl_rna.properties['engine'].enum_items]
    print('engines:', valid)
    for nm in ('BLENDER_EEVEE_NEXT', 'BLENDER_EEVEE'):
        if nm in valid:
            sc.render.engine = nm
            break

ee = sc.eevee
for attr_nm, val in [
    ('taa_render_samples', 64),
    ('use_raytracing', True),
    ('use_shadows', True),
    ('shadow_ray_count', 2),
    ('shadow_step_count', 6),
    ('use_gtao', True),
    ('gtao_distance', 0.3),
    ('use_volumetric_lights', True),
    ('volumetric_end', 80.0),
    ('volumetric_tile_size', '4'),
]:
    if hasattr(ee, attr_nm):
        try:
            setattr(ee, attr_nm, val)
        except Exception:
            pass

r = sc.render
r.resolution_x, r.resolution_y = 1920, 1080
r.resolution_percentage = 100
r.image_settings.file_format = 'PNG'
r.image_settings.color_mode = 'RGB'

try:
    sc.view_settings.view_transform = 'AgX'
    sc.view_settings.look = 'AgX - Medium High Contrast'
except Exception:
    pass

# ══════════════════════════════════════════════════════════════════════════════
# 1.  APPEND MECH  from v3.blend
# ══════════════════════════════════════════════════════════════════════════════
env_top = get_coll('Environment', parent=sc.collection)

# append mech collection
with bpy.data.libraries.load(SRC, link=False) as (data_from, data_to):
    # grab all collections + objects + materials
    data_to.collections = data_from.collections[:]
    data_to.materials   = data_from.materials[:]

# link mech collections into scene (keep separate from Environment)
for coll in data_to.collections:
    if coll is not None and coll.name not in sc.collection.children:
        sc.collection.children.link(coll)

print('Appended collections:', [c.name for c in data_to.collections if c])


# ══════════════════════════════════════════════════════════════════════════════
# 2.  MATERIALS  (shared palette)
# ══════════════════════════════════════════════════════════════════════════════

def mat_ground():
    m, nt = new_mat('ENV_Ground')
    nt.nodes.clear()
    v = texco(nt, 'Generated')
    vs = mapv(nt, v, scale=(6, 6, 1))
    n1 = noi(nt, vs, 4.0, detail=8, rough=0.7)
    n2 = noi(nt, mapv(nt, v, scale=(18, 18, 1)), 1.0, detail=4)
    f  = mth(nt, 'ADD', mth(nt, 'MULTIPLY', n1, 0.7), mth(nt, 'MULTIPLY', n2, 0.3))
    base = ramp(nt, f, [
        (0.0,  (0.06, 0.05, 0.04)),
        (0.35, (0.12, 0.10, 0.07)),
        (0.65, (0.18, 0.15, 0.10)),
        (1.0,  (0.22, 0.19, 0.13)),
    ])
    N = bump(nt, n1, strength=1.2, dist=0.04)
    out_mat(nt, bsdf(nt, base, rough=0.95, metal=0.0, normal=N))
    m.roughness = 0.95
    return m


def mat_concrete():
    m, nt = new_mat('ENV_Concrete')
    nt.nodes.clear()
    v = texco(nt, 'Object')
    vs = mapv(nt, v, scale=(3, 3, 1))
    n1 = noi(nt, vs, 2.0, detail=6, rough=0.7)
    crack = vor(nt, mapv(nt, v, scale=(8, 8, 1)), 5.0, feature='DISTANCE_TO_EDGE', out='Distance')
    crack_m = sstep(nt, crack, 0.0, 0.12)
    base = ramp(nt, mth(nt, 'MULTIPLY', n1, crack_m), [
        (0.0,  (0.28, 0.26, 0.23)),
        (0.5,  (0.38, 0.36, 0.32)),
        (1.0,  (0.48, 0.46, 0.42)),
    ])
    N = bump(nt, n1, strength=0.6, dist=0.02)
    out_mat(nt, bsdf(nt, base, rough=0.9, metal=0.0, normal=N))
    return m


def mat_metal_dark():
    m, nt = new_mat('ENV_MetalDark')
    nt.nodes.clear()
    v = texco(nt, 'Object')
    sc_n = noi(nt, mapv(nt, v, scale=(5, 5, 5)), 1.0, detail=4, rough=0.65)
    base = ramp(nt, sc_n, [(0.0, (0.04, 0.04, 0.04)), (1.0, (0.09, 0.08, 0.08))])
    N = bump(nt, sc_n, strength=0.4, dist=0.01)
    out_mat(nt, bsdf(nt, base, rough=0.65, metal=0.9, normal=N))
    return m


def mat_olive():
    """Dirty olive paint for mech body"""
    m, nt = new_mat('ENV_OliveDirty')
    nt.nodes.clear()
    v = texco(nt, 'Object')
    vs = mapv(nt, v, scale=(2, 2, 2))
    n1 = noi(nt, vs, 3.0, detail=6, rough=0.7)
    dirt = noi(nt, mapv(nt, v, scale=(0.6, 0.6, 0.6)), 1.0, detail=4, rough=0.8)
    base_clean = ramp(nt, n1, [
        (0.0, (0.18, 0.20, 0.10)),
        (0.5, (0.22, 0.24, 0.12)),
        (1.0, (0.16, 0.18, 0.09)),
    ])
    base_dirt = ramp(nt, n1, [
        (0.0, (0.07, 0.06, 0.04)),
        (1.0, (0.10, 0.09, 0.06)),
    ])
    base = mix(nt, sstep(nt, dirt, 0.35, 0.65), base_clean, base_dirt)
    N = bump(nt, n1, strength=0.5, dist=0.01)
    out_mat(nt, bsdf(nt, base, rough=mth(nt, 'ADD', mth(nt, 'MULTIPLY', dirt, 0.2), 0.75), metal=0.05, normal=N))
    return m


def mat_olive_dark():
    """Darker olive for legs"""
    m, nt = new_mat('ENV_OliveDark')
    nt.nodes.clear()
    v = texco(nt, 'Object')
    n1 = noi(nt, mapv(nt, v, scale=(3, 3, 3)), 2.0, detail=6)
    base = ramp(nt, n1, [
        (0.0, (0.07, 0.08, 0.04)),
        (1.0, (0.11, 0.12, 0.06)),
    ])
    N = bump(nt, n1, strength=0.6, dist=0.015)
    out_mat(nt, bsdf(nt, base, rough=0.85, metal=0.05, normal=N))
    return m


def mat_rust():
    m, nt = new_mat('ENV_Rust')
    nt.nodes.clear()
    v = texco(nt, 'Object')
    n1 = noi(nt, mapv(nt, v, scale=(4, 4, 4)), 2.0, detail=6)
    base = ramp(nt, n1, [(0.0, (0.32, 0.12, 0.04)), (0.6, (0.48, 0.22, 0.08)), (1.0, (0.25, 0.09, 0.02))])
    out_mat(nt, bsdf(nt, base, rough=0.92, metal=0.4))
    return m


def mat_wood():
    m, nt = new_mat('ENV_Wood')
    nt.nodes.clear()
    v = texco(nt, 'Object')
    n1 = noi(nt, mapv(nt, v, scale=(1, 8, 1)), 1.5, detail=4)
    base = ramp(nt, n1, [(0.0, (0.22, 0.14, 0.06)), (1.0, (0.35, 0.22, 0.10))])
    out_mat(nt, bsdf(nt, base, rough=0.88))
    return m


def mat_sand():
    m, nt = new_mat('ENV_Sand')
    nt.nodes.clear()
    v = texco(nt, 'Object')
    n1 = noi(nt, mapv(nt, v, scale=(5, 5, 5)), 2.0, detail=5)
    base = ramp(nt, n1, [(0.0, (0.52, 0.45, 0.30)), (1.0, (0.62, 0.56, 0.40))])
    out_mat(nt, bsdf(nt, base, rough=0.98))
    return m


def mat_tire():
    m, nt = new_mat('ENV_Tire')
    nt.nodes.clear()
    v = texco(nt, 'Object')
    n1 = noi(nt, mapv(nt, v, scale=(6, 6, 6)), 1.0, detail=4)
    base = ramp(nt, n1, [(0.0, (0.05, 0.05, 0.05)), (1.0, (0.09, 0.09, 0.09))])
    out_mat(nt, bsdf(nt, base, rough=0.98, metal=0.0))
    return m


def mat_glass():
    m, nt = new_mat('ENV_Glass')
    nt.nodes.clear()
    bsdf_n = nn(nt, 'ShaderNodeBsdfPrincipled')
    bsdf_n.inputs['Roughness'].default_value = 0.05
    bsdf_n.inputs['Transmission Weight'].default_value = 0.9
    bsdf_n.inputs['Base Color'].default_value = (0.6, 0.8, 0.7, 1.0)
    out_mat(nt, o(bsdf_n))
    m.blend_method = 'BLEND' if hasattr(m, 'blend_method') else m.blend_method
    return m


# instantiate all materials
m_ground   = mat_ground()
m_concrete = mat_concrete()
m_metal    = mat_metal_dark()
m_olive    = mat_olive()
m_olive_dk = mat_olive_dark()
m_rust     = mat_rust()
m_wood     = mat_wood()
m_sand     = mat_sand()
m_tire     = mat_tire()
m_glass    = mat_glass()


# ══════════════════════════════════════════════════════════════════════════════
# 3.  MECH MATERIAL PATCH  (olive dirty)
# ══════════════════════════════════════════════════════════════════════════════
LEG_KEYWORDS = ('leg', 'foot', 'shin', 'thigh', 'knee', 'ankle')

for ob in bpy.data.objects:
    if ob.type != 'MESH':
        continue
    nm = ob.name.lower()
    is_leg = any(k in nm for k in LEG_KEYWORDS)
    for slot in ob.material_slots:
        if slot.material is None:
            continue
        mn = slot.material.name.lower()
        # skip emissive/glass slots
        if any(k in mn for k in ('glass', 'lens', 'emit', 'glow', 'light')):
            continue
        if is_leg:
            slot.material = m_olive_dk
        elif any(k in mn for k in ('mech', 'body', 'armor', 'hull', 'hip',
                                   'torso', 'cockpit', 'shoulder', 'cannon',
                                   'arm', 'back')):
            slot.material = m_olive


# ══════════════════════════════════════════════════════════════════════════════
# 4.  GROUND  (30×30 m terrain grid + displacement)
# ══════════════════════════════════════════════════════════════════════════════
env_coll = get_coll('Environment', parent=sc.collection)

RES = 60   # grid resolution
HALF = 15.0

xs = [HALF * (-1 + 2 * i / (RES - 1)) for i in range(RES)]
ys = [HALF * (-1 + 2 * j / (RES - 1)) for j in range(RES)]


def terrain_z(x, y):
    """Moderate bumps, ruts, flat zone under mech"""
    dist_mech = math.sqrt(x * x + y * y)
    flat = max(0.0, 1.0 - dist_mech / 6.0)
    base = 0.18 * fbm(x * 0.22, y * 0.22, octaves=5, seed=7)
    rut1 = -0.06 * max(0.0, 1.0 - abs(x - 1.2) / 0.4) * max(0.0, 1.0 - abs(y) / 14.0)
    rut2 = -0.06 * max(0.0, 1.0 - abs(x + 1.2) / 0.4) * max(0.0, 1.0 - abs(y) / 14.0)
    return (base + rut1 + rut2) * (1.0 - flat)


mb = MB()
mb.grid(xs, ys, terrain_z, m=0)
ground = mb.obj('ENV_Ground', env_coll, [m_ground], loc=(0, 0, 0), smooth=45)

# ── concrete slab (flat 10×7 m pad under mech) ──────────────────────────────
mb2 = MB()
mb2.box((10, 7, 0.18), m=0)
slab = mb2.obj('ENV_Slab', env_coll, [m_concrete], loc=(0, -4.5, -0.08))

# ── border kerb strips ───────────────────────────────────────────────────────
for sign, label in ((1, 'A'), (-1, 'B')):
    mb3 = MB()
    mb3.box((10, 0.22, 0.12), m=0)
    k = mb3.obj(f'ENV_Kerb{label}', env_coll, [m_concrete], loc=(0, -4.5 + sign * 3.5, 0.0))


# ══════════════════════════════════════════════════════════════════════════════
# 5.  PROPS  (crates, barrels, sandbags, barriers, lamps, rocks)
# ══════════════════════════════════════════════════════════════════════════════

def _place(mb_fn, name, coll, loc, rz=0, s=1.0):
    mb_ = MB()
    mb_fn(mb_)
    ob = mb_.obj(name, coll, mb_._mats_list, loc=loc, smooth=30)
    ob.rotation_euler.z = D2R(rz)
    if s != 1.0:
        ob.scale = (s, s, s)
    return ob


# helper to make object with specific mats list
class _MB2(MB):
    def __init__(self, mats):
        super().__init__()
        self._mats_list = mats


def make_crate(w=0.9, h=0.7, d=0.8):
    mb_ = _MB2([m_wood, m_metal])
    mb_.box((w, d, h), m=0)
    # metal corner strips
    for sx in (-1, 1):
        for sy in (-1, 1):
            mb_.box((0.06, d + 0.02, h + 0.02), m=1,
                    mat=Matrix.Translation(Vector((sx * w / 2, 0, 0))))
    return mb_


def make_barrel(r=0.24, h=0.72):
    mb_ = _MB2([m_metal, m_rust])
    mb_.cyl((0, 0, 0), (0, 0, h), r, n=12, m=0)
    mb_.cyl((0, 0, h * 0.12), (0, 0, h * 0.14), r + 0.015, n=12, m=1)
    mb_.cyl((0, 0, h * 0.5),  (0, 0, h * 0.52), r + 0.015, n=12, m=1)
    mb_.cyl((0, 0, h * 0.87), (0, 0, h * 0.89), r + 0.015, n=12, m=1)
    return mb_


def make_sandbag(l=0.8, w=0.36, h=0.22):
    mb_ = _MB2([m_sand])
    # lumpy box – approximate with a box + subdivision done at bake time
    mb_.box((l, w, h), m=0)
    return mb_


def make_barrier():
    """Jersey barrier / concrete T-wall"""
    mb_ = _MB2([m_concrete])
    # main body
    mb_.prism(
        [(-.15, 0), (.15, 0), (.2, .25), (.1, .55), (-.1, .55), (-.2, .25)],
        0.0, 0.9, m=0
    )
    return mb_


def make_lamp_post(h=5.5):
    mb_ = _MB2([m_metal])
    mb_.cyl((0, 0, 0), (0, 0, h), 0.055, n=8, m=0)
    mb_.cyl((0, 0, h), (0.7, 0, h + 0.1), 0.04, n=6, m=0)
    # lamp head
    mb_.box((0.35, 0.18, 0.14), m=0,
            mat=Matrix.Translation(Vector((0.7, 0, h + 0.05))))
    return mb_


def make_rock(sx=0.6, sy=0.4, sz=0.35, seed=0):
    mb_ = _MB2([m_concrete])
    # deformed octahedron
    pts = [
        (0, 0, sz), (0, 0, -sz * 0.3),
        (sx, 0, 0.1), (-sx * 0.9, 0, 0.05),
        (0, sy, 0.08), (0, -sy * 0.85, 0.12),
        (sx * 0.6, sy * 0.6, sz * 0.5), (-sx * 0.6, sy * 0.5, sz * 0.4),
        (sx * 0.5, -sy * 0.7, sz * 0.3), (-sx * 0.5, -sy * 0.6, sz * 0.35),
    ]
    rr = random.Random(seed)
    pts = [(x + rr.uniform(-0.06, 0.06) * sx,
            y + rr.uniform(-0.06, 0.06) * sy,
            z + rr.uniform(-0.04, 0.04) * sz) for x, y, z in pts]
    # convex hull via bmesh
    bm_ = bmesh.new()
    for p in pts:
        bm_.verts.new(p)
    bmesh.ops.convex_hull(bm_, input=bm_.verts)
    me_ = bpy.data.meshes.new('_rock_tmp')
    bm_.to_mesh(me_)
    bm_.free()
    for v_ in me_.vertices:
        mb_.V.append(tuple(v_.co))
    for p_ in me_.polygons:
        mb_.F.append(tuple(p_.vertices))
        mb_.M.append(0)
    bpy.data.meshes.remove(me_)
    return mb_


# ── scatter props ─────────────────────────────────────────────────────────────
prop_locs = [
    # crates cluster left
    ((-7.5, -2.0, 0.0),   0,   'crate'),
    ((-7.5, -1.1, 0.7),  15,   'crate'),
    ((-8.2, -2.0, 0.0),  -8,   'crate'),
    ((-8.2, -1.1, 0.0),   5,   'crate'),
    # crates right
    ((6.5,  -3.5, 0.0),  20,   'crate'),
    ((7.2,  -3.5, 0.7), -12,   'crate'),
    ((6.5,  -4.3, 0.0),   3,   'crate'),
    # barrels cluster
    ((-5.0, -8.5, 0.0),   0,   'barrel'),
    ((-4.4, -8.5, 0.0),  12,   'barrel'),
    ((-4.7, -7.8, 0.0),  -5,   'barrel'),
    ((8.0,   4.0, 0.0),   0,   'barrel'),
    ((8.5,   4.0, 0.0),  20,   'barrel'),
    # sandbags row (fortification line)
    ((-6.0,  6.5, 0.0),   0,   'sandbag'),
    ((-5.2,  6.5, 0.0),   2,   'sandbag'),
    ((-4.4,  6.5, 0.0),  -1,   'sandbag'),
    ((-3.6,  6.5, 0.0),   3,   'sandbag'),
    ((-2.8,  6.5, 0.0),   0,   'sandbag'),
    ((-2.0,  6.5, 0.22),  5,   'sandbag'),  # second row
    ((-2.8,  6.5, 0.22), -2,   'sandbag'),
    # barriers
    ((-9.0,  0.0, 0.0),   0,   'barrier'),
    ((-9.0,  1.5, 0.0),   0,   'barrier'),
    ((-9.0, -1.5, 0.0),   0,   'barrier'),
    ((9.5,   2.0, 0.0),  90,   'barrier'),
    # lamp posts
    ((-11.0, -11.0, 0.0), 0,   'lamp'),
    (( 11.0, -11.0, 0.0), 0,   'lamp'),
    ((-11.0,  11.0, 0.0), 0,   'lamp'),
    (( 11.0,  11.0, 0.0), 0,   'lamp'),
    # rocks
    (( 3.5,   9.0, 0.0),  30,  'rock0'),
    (( 4.2,   9.6, 0.0), -15,  'rock1'),
    ((-10.5,  5.0, 0.0),  55,  'rock2'),
    ((-11.0,  5.8, 0.0), -20,  'rock3'),
    (( 9.0,  -8.0, 0.0),  10,  'rock4'),
]

factories = {
    'crate':   make_crate,
    'barrel':  make_barrel,
    'sandbag': make_sandbag,
    'barrier': make_barrier,
    'lamp':    make_lamp_post,
    'rock0':   lambda: make_rock(0.55, 0.38, 0.32, 0),
    'rock1':   lambda: make_rock(0.42, 0.55, 0.28, 1),
    'rock2':   lambda: make_rock(0.70, 0.45, 0.40, 2),
    'rock3':   lambda: make_rock(0.35, 0.30, 0.22, 3),
    'rock4':   lambda: make_rock(0.60, 0.50, 0.35, 4),
}

for i, (loc, rz, kind) in enumerate(prop_locs):
    mb_ = factories[kind]()
    gnd_z = terrain_z(loc[0], loc[1])
    real_loc = (loc[0], loc[1], loc[2] + gnd_z)
    ob = mb_.obj(f'ENV_{kind}_{i:03d}', env_coll, mb_._mats_list, loc=real_loc, smooth=30)
    ob.rotation_euler.z = D2R(rz)


# ══════════════════════════════════════════════════════════════════════════════
# 6.  VEHICLES  (jeep, truck, APC, fuel cistern, forklift)
# ══════════════════════════════════════════════════════════════════════════════

def vehicle_jeep(coll_, loc, rz=0):
    """Low-poly military jeep"""
    mb_ = _MB2([m_olive, m_tire, m_glass, m_metal])
    # body
    mb_.box((1.8, 3.8, 0.5), m=0, c=(0, 0, 0.8))
    # cabin
    mb_.box((1.6, 2.0, 0.75), m=0, c=(0, -0.3, 1.4))
    # windshield
    mb_.box((1.5, 0.08, 0.55), m=2, c=(0, 0.7, 1.5))
    # 4 wheels
    for wx, wy in ((-0.95, 1.1), (0.95, 1.1), (-0.95, -1.1), (0.95, -1.1)):
        mb_.cyl((wx, wy, 0.38), (wx + 0.0, wy, 0.38), 0.38, n=12, m=1)
        mb_.cyl((wx, wy - 0.02, 0.38), (wx, wy + 0.02, 0.38), 0.24, n=12, m=3)
    # spare tire back
    mb_.cyl((0, -2.1, 0.9), (0.02, -2.1, 0.9), 0.32, n=10, m=1)
    ob = mb_.obj('ENV_Jeep', coll_, mb_._mats_list, loc=loc, smooth=30)
    ob.rotation_euler.z = D2R(rz)
    return ob


def vehicle_truck(coll_, loc, rz=0):
    """Military 6×6 cargo truck"""
    mb_ = _MB2([m_olive, m_tire, m_metal])
    # chassis
    mb_.box((2.3, 6.5, 0.3), m=2, c=(0, 0, 0.65))
    # cargo bed
    mb_.box((2.1, 3.5, 0.8), m=0, c=(0, -1.2, 1.1))
    # cab
    mb_.box((2.0, 2.0, 1.1), m=0, c=(0,  1.8, 1.1))
    # engine hood
    mb_.box((1.9, 1.2, 0.55), m=0, c=(0,  3.0, 0.9))
    # 6 wheels
    for wx in (-1.2, 1.2):
        for wy in (1.0, -0.5, -2.0):
            mb_.cyl((wx, wy, 0.45), (wx, wy, 0.45), 0.45, n=12, m=1)
            mb_.cyl((wx, wy - 0.02, 0.45), (wx, wy + 0.02, 0.45), 0.28, n=12, m=2)
    ob = mb_.obj('ENV_Truck', coll_, mb_._mats_list, loc=loc, smooth=30)
    ob.rotation_euler.z = D2R(rz)
    return ob


def vehicle_apc(coll_, loc, rz=0):
    """Tracked APC / light tank hull"""
    mb_ = _MB2([m_olive_dk, m_metal, m_tire])
    # hull
    mb_.box((2.8, 5.5, 1.0), m=0, c=(0, 0, 0.9))
    # turret
    mb_.box((1.6, 2.0, 0.7), m=0, c=(0, 0.3, 1.9))
    mb_.cyl((0, 0.3, 2.25), (0, 0.3, 2.25), 0.7, n=10, m=0)
    # gun barrel
    mb_.cyl((0, 1.0, 2.1), (0, 2.8, 2.1), 0.09, n=8, m=1)
    # tracks (simplified flat belt)
    for sx in (-1, 1):
        mb_.box((0.45, 5.6, 0.55), m=1, c=(sx * 1.5, 0, 0.55))
    # road wheels
    for sx in (-1, 1):
        for wy in (1.8, 0.6, -0.6, -1.8):
            mb_.cyl((sx * 1.5, wy, 0.55), (sx * 1.52, wy, 0.55), 0.38, n=10, m=2)
    ob = mb_.obj('ENV_APC', coll_, mb_._mats_list, loc=loc, smooth=30)
    ob.rotation_euler.z = D2R(rz)
    return ob


def vehicle_cistern(coll_, loc, rz=0):
    """Fuel tank truck / static cistern"""
    mb_ = _MB2([m_metal, m_rust, m_tire])
    # frame
    mb_.box((2.0, 6.0, 0.4), m=0, c=(0, 0, 0.6))
    # tank cylinder
    mb_.cyl((0, -2.5, 1.35), (0, 2.5, 1.35), 0.85, r1=0.85, n=14, m=0)
    # end caps already included in cyl caps=True
    # rust stripe
    mb_.cyl((0, -0.5, 1.35), (0, 0.5, 1.35), 0.86, n=14, m=1)
    # stand legs
    for sx in (-0.8, 0.8):
        for sy in (-2.0, 2.0):
            mb_.cyl((sx, sy, 0.0), (sx, sy, 0.5), 0.06, n=6, m=0)
    ob = mb_.obj('ENV_Cistern', coll_, mb_._mats_list, loc=loc, smooth=30)
    ob.rotation_euler.z = D2R(rz)
    return ob


def vehicle_forklift(coll_, loc, rz=0):
    """Basic warehouse forklift"""
    mb_ = _MB2([m_metal, m_tire, m_olive])
    # body
    mb_.box((1.0, 1.6, 1.1), m=2, c=(0, 0, 0.9))
    # counterweight back
    mb_.box((0.9, 0.35, 0.9), m=0, c=(0, -1.05, 0.6))
    # mast
    mb_.box((0.12, 0.12, 2.5), m=0, c=(-0.4, 0.8, 1.5))
    mb_.box((0.12, 0.12, 2.5), m=0, c=( 0.4, 0.8, 1.5))
    # forks
    mb_.box((0.08, 0.85, 0.07), m=0, c=(-0.25, 1.2, 0.35))
    mb_.box((0.08, 0.85, 0.07), m=0, c=( 0.25, 1.2, 0.35))
    # 4 wheels
    for wx, wy in ((-0.55, 0.6), (0.55, 0.6), (-0.55, -0.6), (0.55, -0.6)):
        mb_.cyl((wx, wy, 0.28), (wx, wy, 0.28), 0.28, n=10, m=1)
    ob = mb_.obj('ENV_Forklift', coll_, mb_._mats_list, loc=loc, smooth=30)
    ob.rotation_euler.z = D2R(rz)
    return ob


# place vehicles
vehicle_jeep(env_coll,    (-8.5, -7.0, terrain_z(-8.5, -7.0)),  rz=35)
vehicle_truck(env_coll,   ( 9.5,  5.0, terrain_z( 9.5,  5.0)),  rz=-20)
vehicle_apc(env_coll,     (-9.0,  8.5, terrain_z(-9.0,  8.5)),  rz=155)
vehicle_cistern(env_coll, ( 6.0, -9.5, terrain_z( 6.0, -9.5)),  rz=10)
vehicle_forklift(env_coll,(-6.5, -5.0, terrain_z(-6.5, -5.0)),  rz=70)


# ══════════════════════════════════════════════════════════════════════════════
# 7.  HANGAR / BUNKER  (background structure)
# ══════════════════════════════════════════════════════════════════════════════
def make_hangar(coll_, loc, rz=0):
    mb_ = _MB2([m_concrete, m_metal])
    W, D_, H = 14.0, 8.0, 5.5
    hw, hd = W / 2, D_ / 2
    # floor
    mb_.box((W, D_, 0.2), m=0, c=(0, 0, 0.1))
    # back wall
    mb_.box((W, 0.35, H), m=0, c=(0, -hd, H / 2))
    # side walls
    mb_.box((0.35, D_, H), m=0, c=(-hw, 0, H / 2))
    mb_.box((0.35, D_, H), m=0, c=( hw, 0, H / 2))
    # arched roof (approximation: folded quads)
    segs = 10
    for i in range(segs):
        a0 = math.pi * i / segs
        a1 = math.pi * (i + 1) / segs
        y0, z0 = -math.cos(a0) * hd, math.sin(a0) * (H - 2.5) + 2.5
        y1, z1 = -math.cos(a1) * hd, math.sin(a1) * (H - 2.5) + 2.5
        verts = [(-hw, y0, z0), (hw, y0, z0), (hw, y1, z1), (-hw, y1, z1)]
        mb_.add(verts, [(0, 1, 2, 3)], m=1)
    # large door opening (front facade only – represented by empty gap, no geometry for inside)
    # front header beam
    mb_.box((W, 0.35, 0.5), m=1, c=(0, hd, H - 0.25))
    ob = mb_.obj('ENV_Hangar', coll_, mb_._mats_list, loc=loc, smooth=60)
    ob.rotation_euler.z = D2R(rz)
    return ob


make_hangar(env_coll, (0, 14.0, terrain_z(0, 14.0)), rz=0)


# ══════════════════════════════════════════════════════════════════════════════
# 8.  ATMOSPHERIC LIGHTING + FOG
# ══════════════════════════════════════════════════════════════════════════════
stage_coll = get_coll('EnvStage', parent=sc.collection)


def look_at(ob, target):
    d = Vector(target) - ob.location
    ob.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()


# sun (overcast, slightly warm)
sun_d = bpy.data.lights.new('ENV_Sun', 'SUN')
sun_d.energy = 4.5
sun_d.angle  = D2R(8)
sun_d.color  = (1.0, 0.92, 0.80)
sun_ob = bpy.data.objects.new('ENV_Sun', sun_d)
sun_ob.rotation_euler = (-Vector((-0.5, -0.65, 0.8))).to_track_quat('-Z', 'Y').to_euler()
stage_coll.objects.link(sun_ob)

# large soft fill (sky dome approximation)
fill_d = bpy.data.lights.new('ENV_Fill', 'AREA')
fill_d.energy = 1200
fill_d.size   = 20
fill_d.color  = (0.65, 0.75, 0.95)
fill_ob = bpy.data.objects.new('ENV_Fill', fill_d)
fill_ob.location = (0, 0, 22)
look_at(fill_ob, (0, 0, 0))
stage_coll.objects.link(fill_ob)

# rim from behind hangar
rim_d = bpy.data.lights.new('ENV_Rim', 'AREA')
rim_d.energy = 3500
rim_d.size   = 8
rim_d.color  = (1.0, 0.75, 0.45)
rim_ob = bpy.data.objects.new('ENV_Rim', rim_d)
rim_ob.location = (8, 18, 12)
look_at(rim_ob, (0, -4, 3))
stage_coll.objects.link(rim_ob)

# world  – dark overcast sky + volumetric fog
w = sc.world or bpy.data.worlds.new('World')
sc.world = w
w.use_nodes = True
wnt = w.node_tree
wnt.nodes.clear()

bg_n = wnt.nodes.new('ShaderNodeBackground')
bg_n.inputs['Color'].default_value = (0.04, 0.045, 0.05, 1.0)
bg_n.inputs['Strength'].default_value = 0.6

# volume scatter (fog)
vol_n = wnt.nodes.new('ShaderNodeVolumePrincipled')
vol_n.inputs['Density'].default_value = 0.008
vol_n.inputs['Anisotropy'].default_value = 0.3
fog_col = (0.55, 0.58, 0.62)
vol_n.inputs['Color'].default_value = (*fog_col, 1.0)

out_w = wnt.nodes.new('ShaderNodeOutputWorld')
wnt.links.new(bg_n.outputs['Background'], out_w.inputs['Surface'])
wnt.links.new(vol_n.outputs['Volume'],    out_w.inputs['Volume'])

sc.eevee.volumetric_end = 60.0
if hasattr(sc.eevee, 'volumetric_tile_size'):
    try:
        sc.eevee.volumetric_tile_size = '4'
    except Exception:
        pass


# ══════════════════════════════════════════════════════════════════════════════
# 9.  ENV CAMERA  (beauty shot)
# ══════════════════════════════════════════════════════════════════════════════
cam_d = bpy.data.cameras.new('ENV_Cam')
cam_d.lens = 35
cam_ob = bpy.data.objects.new('ENV_Cam', cam_d)
cam_ob.location = (18, -22, 7)
look_at(cam_ob, (0, -3, 4.5))
stage_coll.objects.link(cam_ob)
sc.camera = cam_ob

sc.render.resolution_x = 1920
sc.render.resolution_y = 1080


# ══════════════════════════════════════════════════════════════════════════════
# 10.  SAVE
# ══════════════════════════════════════════════════════════════════════════════
bpy.ops.wm.save_as_mainfile(filepath=DEST)
print(f'SAVED → {DEST}')
print('Objects in scene:', len(bpy.data.objects))
print('Done – diorama built.')

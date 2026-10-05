"""build_cine.py -- the whole mech cinematic: story-time animation + FX + rigid sims -> retime -> cameras.

Run (never on the source files -- result is saved to cinematic/mech_cinematic.blend):
  Blender -b environment.blend --python scripts/cine/build_cine.py -- [--quick]
"""
import bpy, bmesh, sys, os, math, random, json, time
import numpy as np
from mathutils import Vector, Matrix, Euler, Quaternion

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.expanduser('~/Documents/learning/mech-test/blender')
for p in (HERE, os.path.join(ROOT, 'scripts'), os.path.join(ROOT, 'scripts/vehicles')):
    if p not in sys.path:
        sys.path.insert(0, p)
import fx_lib as F
import cine_mech as CM
import cine_nuke as N

ARGS = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
QUICK = '--quick' in ARGS
OUT_BLEND = os.path.join(ROOT, 'cinematic', 'mech_cinematic.blend')
EVENTS = os.path.join(ROOT, 'renders', 'cine', 'events.json')
FPS = 24
OS = 2 if QUICK else 4
T00 = time.time()


def log(*a):
    print(f'[cine {time.time() - T00:7.1f}s]', *a, flush=True)


def sf(S):
    return 1.0 + S * FPS


def smooth(x):
    x = min(1.0, max(0.0, x))
    return x * x * (3 - 2 * x)


sc = bpy.context.scene
sc.render.fps = FPS
bpy.context.preferences.edit.keyframe_new_interpolation_type = 'LINEAR'
C_FX = F.coll('CINE_fx')
C_SIM = F.coll('CINE_sim')
C_CAM = F.coll('CINE_cams')
C_HELP = F.coll('CINE_helpers')
EV = dict(fps=FPS, time_convention='render_s = (frame-1)/fps; story_s = physical time before slow-motion remap',
          shots=[], explosions=[], impacts=[], steps=[], notes=[])
TER = bpy.data.objects['ENV_terrain']


def ground_z(x, y):
    Mi = TER.matrix_world.inverted()
    o = Mi @ Vector((x, y, 300.0))
    d = (Mi.to_3x3() @ Vector((0, 0, -1))).normalized()
    ok, loc, n, i = TER.ray_cast(o, d)
    return (TER.matrix_world @ loc).z if ok else 0.0


# =============================================================================== story constants
SCRIPT = [('idle', 0.4), ('walk', 7), ('wait', 0.35), ('torso', 0.8, -80, 1.2), ('torso', 0.9, 0, 0.2),
          ('walk', 3), ('wait', 0.3), ('torso', 0.4, -9, 2.0), ('torso', 0.6, 0, 0.2),
          ('walk', 4, {1: 3.0}), ('wait', 0.6), ('torso', 0.4, 75, 3.0)]
Y0, Z0 = -21.0, -0.07
T_FIRE, T_TRUCK = 9.75, 9.80
MISSILES = [(15.80, 'launcher_L', Vector((3.0, 26.0, 9.0)), 5.5),
            (16.05, 'launcher_R', Vector((9.5, 26.0, 5.0)), 5.5),
            (16.30, 'launcher_L', Vector((6.0, 26.0, 12.0)), 5.5),
            (16.55, 'launcher_R', Vector((11.5, 26.0, 9.5)), 6.5)]
T_FLY = 0.55
T_CORE = 17.35                    # final internal detonation (building centre)
APC_BURSTS = [19.0, 21.5, 22.3]
T_SNAP = 23.46
T_IMP = 26.0
T_NUKE = T_IMP + 0.75
T_END = T_NUKE + 9.4
V_RKT = 85.0
D_CAM = 22.0
S_MID = T_IMP - D_CAM / V_RKT
TRUCK_C = Vector((18.5, -6.2, 0.0))
BLD_C = Vector((6.0, 32.0, 6.0))

# =============================================================================== 1. mech animation
log('mech animation')
mev, ctx, g = CM.animate(SCRIPT, y0=Y0, z0=Z0)
CM.snap_turn(ctx, T_SNAP, 75.0, dur=0.38, over_deg=11.0, fps=FPS)
CM.recoil(T_FIRE, fps=FPS)
MECH = [o for o in bpy.data.collections['HeavyMech'].objects if o.type == 'MESH']
MNAMES = [o.name for o in MECH]
sc.frame_start = 1
F_REC = int(sf(T_IMP)) + 2
REC = np.zeros((len(MECH), F_REC + 1, 4, 4))
for f in range(1, F_REC + 1):
    sc.frame_set(f)
    for j, o in enumerate(MECH):
        REC[j, f] = np.array(o.matrix_world)
REC[:, 0] = REC[:, 1]
log('mech recorded', F_REC, 'frames')


def MW(name, S):
    j = MNAMES.index(name)
    x = min(max(sf(S), 1.0), F_REC - 1e-3)
    i0 = int(x)
    a = x - i0
    M0 = Matrix(REC[j, i0].tolist())
    M1 = Matrix(REC[j, min(i0 + 1, F_REC)].tolist())
    q = M0.to_quaternion().slerp(M1.to_quaternion(), a)
    t = M0.translation.lerp(M1.translation, a)
    return Matrix.Translation(t) @ q.to_matrix().to_4x4()


def local_verts(name):
    o = bpy.data.objects[name]
    me = o.data
    co = np.empty(len(me.vertices) * 3)
    me.vertices.foreach_get('co', co)
    return co.reshape(-1, 3)


# muzzle of cannon_R (most forward vertex, mech forward = local -Y), launcher tops
cv = local_verts('cannon_R')
MUZZLE_L = Vector(cv[np.argmin(cv[:, 1])])
LAUNCH_L = {}
for nm in ('launcher_L', 'launcher_R'):
    lv = local_verts(nm)
    top = lv[lv[:, 2] > lv[:, 2].max() - 0.25]
    LAUNCH_L[nm] = Vector(top.mean(0)) + Vector((0, 0, 0.3))
fv = local_verts('foot_R')
SOLE_L = Vector(((fv[:, 0].min() + fv[:, 0].max()) / 2, (fv[:, 1].min() + fv[:, 1].max()) / 2, fv[:, 2].min()))
SOLE_HX = (fv[:, 0].max() - fv[:, 0].min()) / 2
SOLE_HY = (fv[:, 1].max() - fv[:, 1].min()) / 2

# foot-down events (story) -> footstep dust + crush time
STEPS = []
for e in mev['foot_down']:
    STEPS.append((e['time_s'], e['foot'], e['phase'], e['step']))
_cr = [(t, ft) for (t, ft, ph, k) in STEPS if ph == 'walk2' and k == 1][0]
T_CRUSH, CRUSH_FOOT = _cr
log('crush foot', CRUSH_FOOT)
fv = local_verts(CRUSH_FOOT)
SOLE_L = Vector(((fv[:, 0].min() + fv[:, 0].max()) / 2, (fv[:, 1].min() + fv[:, 1].max()) / 2, fv[:, 2].min()))
SOLE_HX = (fv[:, 0].max() - fv[:, 0].min()) / 2
SOLE_HY = (fv[:, 1].max() - fv[:, 1].min()) / 2
M_sole_crush = MW(CRUSH_FOOT, T_CRUSH) @ Matrix.Translation(SOLE_L)
JEEP_XY = (M_sole_crush.translation.x - 0.25, M_sole_crush.translation.y)
log('crush at', T_CRUSH, 'jeep', JEEP_XY, 'sole half', SOLE_HX, SOLE_HY)


def toe(name, S):
    return MW(name, S) @ Vector((0, -2.9, 0))


def kick_block(step_k, out_sign):
    t_land, ft = [(t, f) for (t, f, ph, k) in STEPS if ph == 'walk2' and k == step_k][0]
    p = toe(ft, t_land)
    side = 1.0 if p.x > 0 else -1.0
    b = Vector((p.x + side * 0.5 * out_sign, p.y + 0.45, 0.0))
    return t_land - 0.06, b


T_KICK_A, BLOCK_A = kick_block(2, 1.0)
T_KICK_B, BLOCK_B = kick_block(3, 1.0)
log('kicks', T_KICK_A, tuple(BLOCK_A), T_KICK_B, tuple(BLOCK_B))

# rocket geometry
Mt = MW('torso', T_IMP)
fwd = Mt.to_3x3() @ Vector((0, -1, 0))
U_SRC = Vector((fwd.x, fwd.y, 0)).normalized()                  # where the rocket comes from
D_RKT = (-U_SRC + Vector((0, 0, -0.06))).normalized()           # travel direction
tv = local_verts('torso')
tw = np.array([tuple(Mt @ Vector(v)) for v in tv[::7]])
cen = Vector(tw.mean(0))
proj = (tw - np.array(cen)) @ np.array(U_SRC)
I_PT = cen + U_SRC * float(proj.max()) * 0.92 + Vector((0, 0, 0.4))
E_PT = Vector((I_PT.x, I_PT.y, ground_z(I_PT.x, I_PT.y)))
PERP = Vector((-D_RKT.y, D_RKT.x, 0)).normalized()
if PERP.y > 0:
    PERP = -PERP
log('impact point', tuple(round(c, 2) for c in I_PT), 'from', tuple(round(c, 3) for c in U_SRC))


def rkt(S):
    return I_PT - D_RKT * V_RKT * (T_IMP - S)


# hide intact mech at impact
for o in MECH:
    for f, h in ((1, False), (sf(T_IMP), True)):
        o.hide_render = h
        o.hide_viewport = h
        o.keyframe_insert('hide_render', frame=f)
        o.keyframe_insert('hide_viewport', frame=f)
    for fc in F.fcurves_of(o.animation_data.action):
        if fc.data_path.startswith('hide'):
            for k in fc.keyframe_points:
                k.interpolation = 'CONSTANT'
    o.hide_render = o.hide_viewport = False

# =============================================================================== 2. vehicles + props
log('vehicles')
with bpy.data.libraries.load(os.path.join(ROOT, 'vehicles.blend'), link=False) as (src, dst):
    dst.collections = [n for n in src.collections if n in ('VEH_truck', 'VEH_apc', 'VEH_jeep', 'VEH_wreck')]
CV = F.coll('CINE_vehicles')
for c in dst.collections:
    CV.children.link(c)


def hide_tree(o):
    o.hide_render = o.hide_viewport = True
    for ch in o.children:
        hide_tree(ch)


for o in list(bpy.data.objects):
    if o.name.startswith('PH_'):
        hide_tree(o)
for v, s in (('truck', 'VEH_slot_truck'), ('apc', 'VEH_slot_apc'), ('wreck', 'VEH_slot_wreck')):
    bpy.data.objects[v + '_root'].matrix_world = bpy.data.objects[s].matrix_world.copy()
bpy.data.objects['jeep_root'].matrix_world = Matrix.Translation(
    (JEEP_XY[0], JEEP_XY[1], ground_z(*JEEP_XY))) @ Matrix.Rotation(math.radians(90), 4, 'Z')
bpy.context.view_layer.update()
for v in ('truck', 'apc', 'jeep', 'wreck'):
    for o in list(bpy.data.collections['VEH_' + v].all_objects):
        if o.parent is not None and o.parent.name == v + '_root':
            M = o.matrix_world.copy()
            o.parent = None
            o.matrix_world = M
bpy.context.view_layer.update()
HULL = bpy.data.objects['VEH_apc_hull']
for nm in ('VEH_apc_turret', 'VEH_apc_door_L', 'VEH_apc_door_R', 'VEH_apc_hatch_commander', 'VEH_apc_hatch_driver',
           'VEH_apc_hatch_troop_L', 'VEH_apc_hatch_troop_R'):
    o = bpy.data.objects.get(nm)
    if o is None:
        continue
    M = o.matrix_world.copy()
    o.parent = HULL
    o.matrix_parent_inverse = HULL.matrix_world.inverted()
    o.matrix_basis = M
bpy.context.view_layer.update()
TRUCK = [o for o in bpy.data.collections['VEH_truck'].all_objects if o.type == 'MESH']
JEEP = [o for o in bpy.data.collections['VEH_jeep'].all_objects if o.type == 'MESH']
WRECK = [o for o in bpy.data.collections['VEH_wreck'].all_objects if o.type == 'MESH']
APC_BODIES = [HULL] + [o for o in bpy.data.collections['VEH_apc'].all_objects if 'wheel' in o.name and o.type == 'MESH']


def realize(name, coll_name, M):
    src = bpy.data.collections[coll_name]
    obs = [o for o in src.all_objects if o.type == 'MESH']
    o0 = obs[0]
    ob = bpy.data.objects.new(name, o0.data)
    C_SIM.objects.link(ob)
    ob.matrix_world = M @ Matrix.Translation(-src.instance_offset) @ o0.matrix_world
    return ob


BLK_A = realize('CINE_block_A', 'AST_jersey_striped', Matrix.Translation(
    (BLOCK_A.x, BLOCK_A.y, ground_z(BLOCK_A.x, BLOCK_A.y))))
BLK_B = realize('CINE_block_B', 'AST_jersey_plain', Matrix.Translation(
    (BLOCK_B.x, BLOCK_B.y, ground_z(BLOCK_B.x, BLOCK_B.y))))
PROPS = []
for e in list(bpy.data.collections['ENV_props'].objects):
    d = (e.matrix_world.translation.xy - E_PT.xy).length
    if d > 62:
        continue
    if e.type == 'EMPTY' and e.instance_type == 'COLLECTION' and e.instance_collection:
        cn = e.instance_collection.name
        if cn in ('AST_machine_gun',):
            continue
        ob = realize('CINE_' + e.name, cn, e.matrix_world)
        e.hide_render = e.hide_viewport = True
        PROPS.append(ob)
    elif e.type == 'MESH' and not any(m.type == 'NODES' for m in e.modifiers) and max(e.dimensions) < 12:
        PROPS.append(e)
log('props realized', len(PROPS))

# =============================================================================== 3. fracture buildings
log('fracture')
cap = F.concrete_cap_material()


def frac(name, n, seed, bias_point=None, bias=0.0):
    ob = bpy.data.objects[name]
    pcs = F.fracture(ob, n_pieces=n, seed=seed, cap_mat=cap, bias_point=bias_point, bias=bias,
                     prefix='FR_' + name)
    for p in pcs:
        C_SIM.objects.link(p)
    ob.hide_render = ob.hide_viewport = True
    return pcs


BLD = frac('BLD_target', 120 if QUICK else 220, 11, bias_point=(6.0, 26.0, 8.0), bias=1.0)
BAL = frac('B2_balconies', 10 if QUICK else 20, 12)
B2C = bpy.data.objects['B2_collapsed']
B1 = frac('B1_shell', 25 if QUICK else 60, 13)
B3 = frac('B3_shell', 20 if QUICK else 50, 14)
log('fractured', len(BLD), len(BAL), len(B1), len(B3))

# ground collider (terrain cropped around the checkpoint)
dg = bpy.context.evaluated_depsgraph_get()
bm = bmesh.new()
bm.from_mesh(TER.evaluated_get(dg).to_mesh())
bm.transform(TER.matrix_world)
GC = Vector((5.0, 0.0, 0.0))
kill = [f for f in bm.faces if (f.calc_center_median().xy - GC.xy).length > 120]
bmesh.ops.delete(bm, geom=kill, context='FACES')
gme = bpy.data.meshes.new('SIM_ground')
bm.to_mesh(gme)
bm.free()
GROUND = bpy.data.objects.new('SIM_ground', gme)
C_HELP.objects.link(GROUND)
GROUND.hide_render = True
PASSIVE_EXTRA = [bpy.data.objects[n] for n in ('B2_rubble', 'B1_rubble', 'B3_rubble_in', 'B3_rubble_out')
                 if n in bpy.data.objects]


# =============================================================================== sim helpers
def stash(ob):
    out = []
    ad = ob.animation_data
    if ad and ad.action:
        for fc in F.fcurves_of(ad.action):
            n = len(fc.keyframe_points)
            if n == 0:
                continue
            co = np.empty(2 * n)
            fc.keyframe_points.foreach_get('co', co)
            out.append((fc.data_path, fc.array_index, co[0::2].copy(), co[1::2].copy(),
                        fc.keyframe_points[0].interpolation, fc.extrapolation))
    return out


def prepare_bodies(objs, f_story):
    """evaluate pose at story frame, stash animation, clear it and pose statically for the sim."""
    sc.frame_set(int(f_story), subframe=f_story - int(f_story))
    mats = {o.name: o.matrix_world.copy() for o in objs}
    st = {}
    for o in objs:
        st[o.name] = stash(o)
        o.animation_data_clear()
        o.rotation_mode = 'QUATERNION'
        o.matrix_world = mats[o.name]
        o.hide_viewport = False
    bpy.context.view_layer.update()
    return st


def bake_merge(objs, rec, times, f0, stashes, kill_z=-12.0):
    frames = f0 + times * FPS
    for j, ob in enumerate(objs):
        ob.animation_data_clear()
        st = stashes.get(ob.name, [])
        old = {(p, i): (x, y) for (p, i, x, y, ip, ex) in st}
        M = rec[j]
        loc = M[:, :3, 3].astype(float)
        dec = [Matrix(m.tolist()).decompose() for m in M]
        qs = np.array([tuple(d[1]) for d in dec])
        ob.rotation_mode = 'QUATERNION'
        ob.scale = dec[0][2]
        qo = [old.get(('rotation_quaternion', k)) for k in range(4)]
        if all(q is not None for q in qo):
            m = qo[0][0] < frames[0] - 1e-4
            if m.any():
                last = np.array([qo[k][1][m][-1] for k in range(4)])
                if np.dot(last, qs[0]) < 0:
                    qs[0] = -qs[0]
        for i in range(1, len(qs)):
            if np.dot(qs[i], qs[i - 1]) < 0:
                qs[i] = -qs[i]
        for path, arr, nk in (('location', loc, 3), ('rotation_quaternion', qs, 4)):
            for k in range(nk):
                x, y = old.get((path, k), (np.zeros(0), np.zeros(0)))
                m = x < frames[0] - 1e-4
                F.set_keys_fast(ob, path, k, np.concatenate([x[m], frames]), np.concatenate([y[m], arr[:, k]]))
        for (p, i, x, y, ip, ex) in st:
            if p in ('location', 'rotation_quaternion', 'rotation_euler') or 'rigid_body' in p:
                continue
            fc = F.set_keys_fast(ob, p, i, x, y, interp=ip)
            fc.extrapolation = ex
        # anything that falls through the world: hide from then on
        bad = np.nonzero(loc[:, 2] < kill_z)[0]
        if len(bad):
            fk = frames[bad[0]]
            for f, h in ((fk - 0.01, False), (fk, True)):
                ob.hide_render = h
                ob.keyframe_insert('hide_render', frame=f)
            for fc in F.fcurves_of(ob.animation_data.action):
                if fc.data_path == 'hide_render':
                    for kp in fc.keyframe_points:
                        kp.interpolation = 'CONSTANT'
            ob.hide_render = False
    log(f'  baked {len(objs)} bodies from frame {f0:.2f}')


def run_sim(bodies, launches, S_start, dur, passive=(), masses=None, shape='CONVEX_HULL'):
    """launches: {name: (v, w, S_release)}; story time S_start == sim frame 10."""
    f_story0 = sf(S_start)
    st = prepare_bodies(bodies, f_story0)
    sim = F.RigidSim(FPS, oversample=OS, substeps=4 if not QUICK else 3, iterations=15)
    sim.add(GROUND, passive=True, shape='MESH', friction=0.8, margin=0.02)
    for p in passive:
        sim.add(p, passive=True, shape='MESH', friction=0.8, margin=0.02)
    for o in bodies:
        dims = o.dimensions
        vol = max(dims.x * dims.y * dims.z, 0.01)
        m = (masses or {}).get(o.name, min(max(vol * 350.0, 5.0), 8000.0))
        sim.add(o, mass=m, shape=shape, friction=0.65, bounce=0.12, margin=0.03, lin_damp=0.08, ang_damp=0.25)
    for nm, (v, w, S_rel) in launches.items():
        fs = 10 + max(1, int(round((S_rel - S_start) * FPS * OS)))
        sim.launch(bpy.data.objects[nm], Vector(v), Vector(w), fs)
    n = int(dur * FPS * OS)
    rec, times = sim.run(10, n, log=log)
    order = list(sim.bodies)
    sim.teardown()
    # passive objects lost their rigid bodies in teardown -- fine
    f0 = f_story0
    bake_merge(order, rec, times, f0, st)
    sc.frame_start = 1
    return rec, times, order


rnd = random.Random(5)


def rv(a, b):
    return rnd.uniform(a, b)


def rand_w(a, b):
    return Vector((rv(-1, 1), rv(-1, 1), rv(-1, 1))).normalized() * rv(a, b)


# =============================================================================== 4. sim: truck
log('sim truck')
TC = Vector((TRUCK_C.x, TRUCK_C.y, ground_z(TRUCK_C.x, TRUCK_C.y) + 1.2))
spec = {'body': (7.0, 2.0, (2.5, 0, 0.6)), 'canvas': (11.0, 4.0, None), 'door': (4.0, 12.0, None),
        'hood': (14.0, 3.0, None), 'wheel': (6.0, 10.0, None), 'spare': (9.0, 6.0, None)}
la = {}
masses = {}
for o in TRUCK:
    key = next((k for k in spec if k in o.name), 'body')
    up, rad, w = spec[key]
    c = o.matrix_world @ (sum((Vector(b) for b in o.bound_box), Vector()) / 8)
    r = (c - TC)
    r.z = 0
    r = r.normalized() if r.length > 0.1 else Vector((rv(-1, 1), rv(-1, 1), 0)).normalized()
    v = (r * rad + Vector((0, 0, up))) * 1.35 * rv(0.85, 1.15)
    ww = Vector(w) if w else rand_w(2, 7)
    la[o.name] = (v, ww, T_TRUCK)
    masses[o.name] = 3500.0 if key == 'body' else 300.0 if key == 'canvas' else 60.0
REC_TRUCK, TT, ORD_T = run_sim(TRUCK, la, T_TRUCK - 2 / (FPS * OS), 6.0, masses=masses)
jb = ORD_T.index(bpy.data.objects['VEH_truck_body'])
TRUCK_REST = Vector(REC_TRUCK[jb, -1, :3, 3].tolist())

# =============================================================================== 5. sim: building + blocks
log('sim building')
DETS = []
for i, (t, lname, tgt, size) in enumerate(MISSILES):
    DETS.append((t + T_FLY + 0.06, tgt + Vector((0, 1.4, 0)), size))
DETS.append((T_CORE, BLD_C, 9.0))
la = {}
for o in BLD + BAL + [B2C]:
    c = o.matrix_world.translation if o.name.startswith('FR_') else o.matrix_world @ (
        sum((Vector(b) for b in o.bound_box), Vector()) / 8)
    best = None
    for (t, p, s) in DETS:
        r = (c - p).length
        if r < 7.5 and (best is None or t < best[0]):
            best = (t, p, r)
    if best is None:
        t, p, s = DETS[-1]
        best = (t + rv(0.0, 0.08), p, (c - p).length)
    t, p, r = best
    d = (c - p)
    d = d.normalized() if d.length > 0.05 else Vector((0, 1, 0))
    sp = min(25.0 * math.exp(-r / 8.0) * 1.5, 32.0)
    v = d * sp + Vector((0, 3.0, rv(6, 14)))
    la[o.name] = (v, rand_w(1.5, 6), t)
la[BLK_A.name] = (Vector((4.5, 7.5, 3.5)), Vector((2, -3, 4)), T_KICK_A)
la[BLK_B.name] = (Vector((-0.8, 6.0, 1.6)), Vector((1, 0, 1.5)), T_KICK_B)
S_B0 = min(T_KICK_A, DETS[0][0]) - 0.05
bodies = BLD + BAL + [B2C, BLK_A, BLK_B]
masses = {BLK_A.name: 2000.0, BLK_B.name: 2000.0}
REC_B, TB, ORD_B = run_sim(bodies, la, S_B0, T_IMP + 0.1 - S_B0, passive=[p for p in PASSIVE_EXTRA if p.name == 'B2_rubble'],
                           masses=masses)
for nm in ('B2_rebar',):
    o = bpy.data.objects.get(nm)
    if o:
        for f, h in ((1, False), (sf(DETS[0][0]), True)):
            o.hide_render = h
            o.keyframe_insert('hide_render', frame=f)
        F.set_interp(o, 'CONSTANT')
        o.hide_render = False


# =============================================================================== 6. mech break-up pieces
def islands(nv, ed):
    lab = np.arange(nv)
    for _ in range(4000):
        m = np.minimum(lab[ed[:, 0]], lab[ed[:, 1]])
        new = lab.copy()
        np.minimum.at(new, ed[:, 0], m)
        np.minimum.at(new, ed[:, 1], m)
        new = new[new]
        new = new[new]
        if np.array_equal(new, lab):
            break
        lab = new
    return lab


def kmeans(X, k, seed=0, iters=12):
    rng = np.random.default_rng(seed)
    k = min(k, len(X))
    C = [X[rng.integers(len(X))]]
    d = ((X - C[0]) ** 2).sum(1)
    for _ in range(k - 1):
        p = d / d.sum() if d.sum() > 0 else None
        C.append(X[rng.choice(len(X), p=p)])
        d = np.minimum(d, ((X - C[-1]) ** 2).sum(1))
    C = np.array(C)
    lab = np.zeros(len(X), int)
    for _ in range(iters):
        D = ((X[:, None, :] - C[None]) ** 2).sum(-1)
        lab = D.argmin(1)
        for j in range(k):
            m = lab == j
            if m.any():
                C[j] = X[m].mean(0)
    return lab


def split_part(ob, k, seed, coll):
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
    me.transform(ob.matrix_world)
    nv, nf = len(me.vertices), len(me.polygons)
    co = np.empty(nv * 3); me.vertices.foreach_get('co', co); co = co.reshape(-1, 3)
    ls = np.empty(nf, int); me.polygons.foreach_get('loop_start', ls)
    lt = np.empty(nf, int); me.polygons.foreach_get('loop_total', lt)
    lv = np.empty(len(me.loops), int); me.loops.foreach_get('vertex_index', lv)
    mi = np.empty(nf, int); me.polygons.foreach_get('material_index', mi)
    smf = np.empty(nf, bool); me.polygons.foreach_get('use_smooth', smf)
    fc = np.empty(nf * 3); me.polygons.foreach_get('center', fc); fc = fc.reshape(-1, 3)
    ed = np.empty(len(me.edges) * 2, int); me.edges.foreach_get('vertices', ed); ed = ed.reshape(-1, 2)
    lab = islands(nv, ed)
    flab = lab[lv[ls]]
    uq, inv = np.unique(flab, return_inverse=True)
    cnt = np.bincount(inv)
    cen = np.stack([np.bincount(inv, fc[:, i]) for i in range(3)], 1) / cnt[:, None]
    mn = np.full((len(uq), 3), np.inf); mx = np.full((len(uq), 3), -np.inf)
    np.minimum.at(mn, inv, fc); np.maximum.at(mx, inv, fc)
    diag = np.linalg.norm(mx - mn, axis=1)
    pd = np.linalg.norm(co.max(0) - co.min(0))
    thr = 0.75 * pd / max(k, 1) ** (1 / 3)
    key = np.where((diag[inv] < thr)[:, None], cen[inv], fc)
    labf = kmeans(key, k, seed)
    mats = list(me.materials)
    out = []
    for j in range(labf.max() + 1):
        sel = np.nonzero(labf == j)[0]
        if len(sel) < 4:
            continue
        tots = lt[sel]
        starts = ls[sel]
        offs = np.cumsum(tots) - tots
        li = np.arange(tots.sum()) - np.repeat(offs, tots) + np.repeat(starts, tots)
        vids = lv[li]
        uv, newv = np.unique(vids, return_inverse=True)
        verts = co[uv]
        c = verts.mean(0)
        faces = [a.tolist() for a in np.split(newv, np.cumsum(tots)[:-1])]
        pm = bpy.data.meshes.new(f'PC_{ob.name}_{j:02d}')
        pm.from_pydata((verts - c).tolist(), [], faces)
        for m in mats:
            pm.materials.append(m)
        pm.polygons.foreach_set('material_index', mi[sel])
        pm.polygons.foreach_set('use_smooth', smf[sel])
        po = bpy.data.objects.new(pm.name, pm)
        coll.objects.link(po)
        po.location = Vector(c.tolist())
        out.append(po)
    bpy.data.meshes.remove(me)
    return out


log('mech pieces')
sc.frame_set(int(sf(T_IMP)) - 1)
C_PC = F.coll('CINE_mech_pieces')
NPC = dict(torso=40, cockpit=25, launcher_L=15, launcher_R=15, arm_L=12, arm_R=12, fist_L=15, cannon_R=15, hip=12,
           thigh_L=8, thigh_R=8, shin_L=8, shin_R=8, foot_L=8, foot_R=8, shoulder_L=3, shoulder_R=3)
PIECES = []
PIECE_OF = {}
for i, o in enumerate(MECH):
    k = NPC.get(o.name, 6)
    if QUICK:
        k = max(2, k // 2)
    ps = split_part(o, k, i, C_PC)
    for p in ps:
        PIECE_OF[p.name] = o.name
    PIECES += ps
log('pieces', len(PIECES))
for p in PIECES:
    F._hide_keys(p, int(sf(T_IMP)))
LEGS = ('thigh', 'shin', 'foot')
la = {}
for p in PIECES:
    c = p.location
    r = (c - I_PT).length
    d = (c - I_PT).normalized() if r > 0.05 else D_RKT
    v = d * 28.0 * math.exp(-r / 4.0) + Vector((0, 0, 4.0)) + D_RKT * 10.0 * math.exp(-r / 5.0)
    w = rand_w(2, 8)
    if any(s in PIECE_OF[p.name] for s in LEGS):
        v = v * 0.15 + Vector((0, 0, 0.5))
        w = w * 0.3
    la[p.name] = (v * 1.3 * rv(0.8, 1.2), w, T_IMP)

# =============================================================================== 7. sim: shock wave (impact + nuke)
log('sim shock')


def shock_t(d):
    return T_NUKE + (max(d, 0.5) / 105.0) ** (1 / 0.62)


others = TRUCK + BLD + BAL + [B2C, BLK_A, BLK_B] + APC_BODIES + WRECK + PROPS + B1 + B3
for o in others:
    c = o.matrix_world.translation
    hv = Vector((c.x - E_PT.x, c.y - E_PT.y, 0))
    dd = hv.length
    hv = hv.normalized() if dd > 0.1 else Vector((1, 0, 0))
    a = math.exp(-dd / 40.0)
    v = hv * 30.0 * a * 1.4 + Vector((0, 0, 6.0 * a * 1.4 + rv(0, 2.5)))
    la[o.name] = (v, rand_w(0.5, 4) * (0.4 + a), shock_t(dd) + rv(0, 0.02))
for nm, base in (('B1_rebar', B1), ('B3_trusses', B3), ('B2_rebar', None)):
    o = bpy.data.objects.get(nm)
    if o and base is not None:
        tt = shock_t((o.matrix_world.translation.xy - E_PT.xy).length)
        for f, h in ((1, False), (sf(tt), True)):
            o.hide_render = h
            o.keyframe_insert('hide_render', frame=f)
        F.set_interp(o, 'CONSTANT')
        o.hide_render = False
S_S0 = T_IMP - 2 / (FPS * OS)
REC_S, TS, ORD_S = run_sim(PIECES + others, la, S_S0, T_END - S_S0 + 0.05, passive=PASSIVE_EXTRA,
                           masses={BLK_A.name: 2000.0, BLK_B.name: 2000.0, HULL.name: 9000.0,
                                   'VEH_truck_body': 3500.0})
PIDX = {o.name: j for j, o in enumerate(ORD_S)}


def piece_pos(name, S):
    j = PIDX[name]
    i = int(round((S - S_S0) * FPS * OS))
    i = min(max(i, 0), REC_S.shape[1] - 1)
    return Vector(REC_S[j, i, :3, 3].tolist())


# =============================================================================== 8. FX (story time)
log('fx')


def dust_ring(name, loc, S0, size=1.0, life=3.0, height=0.5):
    M = F.get_fx_mats()
    ds = F.volume_domain(name, C_FX, kind='cyl')
    ds.data.materials.append(M['dust'])
    ds['seed'] = rnd.uniform(0, 100)
    f0 = int(round(sf(S0)))
    for f in range(f0, f0 + int(life * FPS) + 1):
        t = (f - f0) / FPS
        R = size * 3.0 * (1 - math.exp(-t / 0.35)) + 0.3
        H = height * (0.4 + 0.6 * (1 - math.exp(-t / 0.8))) + 0.2
        ds.scale = (R, R, H)
        ds.location = (loc.x, loc.y, loc.z - 0.15)
        ds['age'] = t
        ds['dens'] = min(1.0, t / 0.08) * max(0.0, 1 - t / life) ** 1.5
        ds['erode'] = min(1.0, t / life) * 0.5
        for pth in ('scale', 'location', '["age"]', '["dens"]', '["erode"]'):
            ds.keyframe_insert(pth, frame=f)
    F._hide_keys(ds, f0, f0 + int(life * FPS))
    F.set_interp(ds, 'LINEAR')
    for fc in F.fcurves_of(ds.animation_data.action):
        if fc.data_path.startswith('hide'):
            for k in fc.keyframe_points:
                k.interpolation = 'CONSTANT'
    return ds


def boom(name, loc, S, size, **kw):
    gz = kw.pop('ground_z', ground_z(loc.x, loc.y))
    objs = F.explosion(name, loc, int(round(sf(S))), FPS, C_FX, size=size, ground_z=gz, **kw)
    EV['explosions'].append(dict(name=name, story_s=round(S, 4), pos=[round(c, 2) for c in loc], size=size))
    return objs


def emis_mat(name, col, strength):
    m = bpy.data.materials.get(name)
    if m:
        return m
    m = F.new_mat(name)
    T = F.NT(m.node_tree)
    out = T.n('ShaderNodeOutputMaterial')
    e = T.n('ShaderNodeEmission')
    F.inp(e, 'Color').default_value = (*col, 1)
    F.inp(e, 'Strength').default_value = strength
    T.L(e.outputs[0], out.inputs[0])
    return m


def streak(name, p0, p1, S0, S1, length=3.0, width=0.07, mat=None):
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=(width, width, length), verts=bm.verts)
    bmesh.ops.translate(bm, vec=(0, 0, -length / 2), verts=bm.verts)
    bm.to_mesh(me)
    bm.free()
    me.materials.append(mat or emis_mat('FX_tracer', (1.0, 0.7, 0.25), 60.0))
    ob = bpy.data.objects.new(name, me)
    C_FX.objects.link(ob)
    d = (p1 - p0).normalized()
    ob.rotation_euler = d.to_track_quat('Z', 'Y').to_euler()
    ob.visible_shadow = False
    for f, p in ((sf(S0), p0), (sf(S1), p1)):
        ob.location = p
        ob.keyframe_insert('location', frame=f)
    F._hide_keys(ob, int(math.floor(sf(S0))), int(math.ceil(sf(S1))) + 1)
    for fc in F.fcurves_of(ob.animation_data.action):
        if fc.data_path == 'location':
            for k in fc.keyframe_points:
                k.interpolation = 'LINEAR'
            fc.extrapolation = 'LINEAR'
    return ob


# ---- footsteps
for (t, ft, ph, k) in STEPS:
    if t >= T_IMP:
        continue
    M = MW(ft, t)
    p = M @ Vector((0, -1.0, 0))
    gz = ground_z(p.x, p.y)
    dust_ring(f'DUST_step_{ft}_{t:.2f}', Vector((p.x, p.y, gz)), t, size=1.1, life=2.6, height=0.7)
    EV['steps'].append(dict(foot=ft, story_s=round(t, 4), phase=ph, step=k, pos=[round(p.x, 2), round(p.y, 2)]))

# ---- cannon shot at the truck
Mc = MW('cannon_R', T_FIRE)
MZ = Mc @ MUZZLE_L
aim = (TC - MZ).normalized()
boom('EXP_muzzle', MZ + aim * 0.8, T_FIRE, 1.1, smoke_life=3.0, dust=False, fire_life=0.25, light_energy=1.2e5,
     smoke_size=0.9)
F.burst('SPK_muzzle', MZ + aim * 0.6, sf(T_FIRE), FPS, C_FX, 'spark', count=160, seed=3, speed=(25, 70), up=0.0,
        direction=tuple(aim), life=(0.1, 0.35), size=0.03, radius=0.2)
streak('TRC_shell', MZ, TC, T_FIRE, T_TRUCK, length=6.0, width=0.18,
       mat=emis_mat('FX_shell', (1.0, 0.55, 0.15), 120.0))
EV['impacts'].append(dict(name='cannon_shell_truck', story_s=T_TRUCK, pos=[round(c, 2) for c in TC]))
# ---- truck explosion + burning
boom('EXP_truck', TC, T_TRUCK, 4.5, smoke_life=14.0, smoke_size=2.0, light_energy=2.0e6, fire_life=2.2)
boom('EXP_truck2', TC + Vector((2.5, 0.5, -0.3)), T_TRUCK + 0.35, 3.3, smoke_life=12.0, smoke_size=1.8,
     light_energy=1.2e6, dust=False)
F.burst('SPK_truck', TC, sf(T_TRUCK), FPS, C_FX, 'spark', count=700, seed=4, speed=(10, 45), up=0.5,
        life=(0.4, 1.6), size=0.04, radius=0.8, ground_z=ground_z(TC.x, TC.y))
F.burst('DEB_truck', TC, sf(T_TRUCK), FPS, C_FX, 'debris', count=180, seed=5, speed=(6, 24), up=0.8,
        life=(5, 9), size=0.16, radius=1.0, ground_z=ground_z(TC.x, TC.y))
try:
    import veh_lib
    veh_lib.burn_objects(TRUCK, amount=1.0, soot=0.9)
    seen = set()
    for o in TRUCK:
        for m in o.data.materials:
            if m is None or m.name in seen or not m.name.endswith('_burnt'):
                continue
            seen.add(m.name)
            nd = next((n for n in m.node_tree.nodes if n.name == 'burn_amount' or n.label == 'burn_amount'), None)
            if nd is None:
                continue
            for f, v in ((sf(T_TRUCK) - 1, 0.0), (sf(T_TRUCK + 0.9), 1.0)):
                nd.outputs[0].default_value = v
                nd.outputs[0].keyframe_insert('default_value', frame=f)
    log('truck burn materials', len(seen))
except Exception as ex:
    log('burn failed', ex)
fire_at = Vector((TRUCK_REST.x, TRUCK_REST.y, ground_z(TRUCK_REST.x, TRUCK_REST.y) + 0.8))
t = T_TRUCK + 1.3
i = 0
while t < T_NUKE:
    boom(f'EXP_truckfire_{i:02d}', fire_at + Vector((rv(-1.2, 1.2), rv(-1.2, 1.2), 0)), t, rv(1.4, 2.0),
         smoke_life=6.0, dust=False, fire_life=1.4, light_energy=1.2e5, smoke_size=1.3, rise=3.0)
    t += rv(0.8, 1.1)
    i += 1
pts, births = F.column_points(fire_at + Vector((0, 0, 1.5)), 0.0, T_END - T_TRUCK - 0.5, rate=5.0, jitter=0.8)
F.trail('TRL_truck_smoke', pts, births, C_FX, sf(T_TRUCK + 0.5), FPS, T_END - T_TRUCK - 0.5, life=12.0, r0=0.9,
        grow=1.6, rise=3.2, wind=(1.0, 0.5, 0.0), voxel=0.35, density=1.0)

# ---- missiles
mis_mat = F.new_mat('FX_missile_body')
T_ = F.NT(mis_mat.node_tree)
_o = T_.n('ShaderNodeOutputMaterial'); _b = T_.n('ShaderNodeBsdfPrincipled')
F.inp(_b, 'Base Color').default_value = (0.12, 0.13, 0.1, 1); F.inp(_b, 'Roughness').default_value = 0.5
T_.L(_b.outputs[0], _o.inputs[0])
for i, (t0, lname, tgt, size) in enumerate(MISSILES):
    Ml = MW(lname, t0)
    p0 = Ml @ LAUNCH_L[lname]
    t_hit = t0 + T_FLY
    p_det = tgt + Vector((0, 1.4, 0))
    me = bpy.data.meshes.new(f'MSL_{i}')
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=12, radius1=0.13, radius2=0.13, depth=1.3)
    bmesh.ops.create_cone(bm, cap_ends=True, segments=12, radius1=0.13, radius2=0.0, depth=0.35,
                          matrix=Matrix.Translation((0, 0, 0.82)))
    bm.to_mesh(me)
    bm.free()
    me.materials.append(mis_mat)
    ob = bpy.data.objects.new(f'MSL_{i}', me)
    C_FX.objects.link(ob)
    fl = bpy.data.objects.new(f'MSL_{i}_flame', bpy.data.meshes.new(f'MSL_{i}_flame'))
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=10, radius1=0.12, radius2=0.0, depth=1.4,
                          matrix=Matrix.Translation((0, 0, -1.35)) @ Matrix.Rotation(math.pi, 4, 'X'))
    bm.to_mesh(fl.data)
    bm.free()
    fl.data.materials.append(emis_mat('FX_missile_flame', (1.0, 0.6, 0.2), 80.0))
    C_FX.objects.link(fl)
    fl.parent = ob
    fl.visible_shadow = False
    # arc: bezier-ish path p0 -> p_det with a lift
    mid = p0.lerp(p_det, 0.5) + Vector((0, 0, 2.5))
    pts_, births_ = [], []
    f_a, f_b = sf(t0), sf(t_hit + 0.06)
    nfr = int(math.ceil(f_b - f_a)) + 1
    for k in range(nfr + 1):
        u = min(1.0, k / nfr)
        P = (1 - u) ** 2 * p0 + 2 * (1 - u) * u * mid + u ** 2 * p_det
        dP = 2 * (1 - u) * (mid - p0) + 2 * u * (p_det - mid)
        ob.location = P
        ob.rotation_euler = dP.normalized().to_track_quat('Z', 'Y').to_euler()
        f = f_a + (f_b - f_a) * u
        ob.keyframe_insert('location', frame=f)
        ob.keyframe_insert('rotation_euler', frame=f)
    F.set_interp(ob, 'LINEAR')
    F._hide_keys(ob, int(math.floor(f_a)), int(math.ceil(f_b)))
    F._hide_keys(fl, int(math.floor(f_a)), int(math.ceil(f_b)))
    for k in range(120):
        u = k / 119
        P = (1 - u) ** 2 * p0 + 2 * (1 - u) * u * mid + u ** 2 * p_det
        pts_.append(P)
        births_.append((t0 + (t_hit + 0.06 - t0) * u) - t0)
    F.trail(f'TRL_msl_{i}', pts_, births_, C_FX, sf(t0), FPS, 7.0, life=5.0, r0=0.35, grow=0.8, rise=0.6,
            wind=(0.6, 0.3, 0), voxel=0.14, density=1.0,
            material=F.trail_material('FX_trail_msl', col=(0.2, 0.19, 0.18), dens=5.0))
    F.burst(f'SPK_launch_{i}', p0, sf(t0), FPS, C_FX, 'spark', count=90, seed=10 + i, speed=(4, 16), up=0.4,
            life=(0.15, 0.5), size=0.025, radius=0.2)
    boom(f'EXP_bld_{i}', p_det, t_hit + 0.06, size, smoke_life=14.0, smoke_size=2.0, light_energy=2.5e6,
         fire_life=2.2, dust=False, ground_z=0.0)
    F.burst(f'SPK_bld_{i}', p_det - Vector((0, 1.6, 0)), sf(t_hit + 0.06), FPS, C_FX, 'spark', count=500,
            seed=20 + i, speed=(12, 50), up=0.3, life=(0.4, 1.8), size=0.05, radius=1.0, ground_z=0.0)
    F.burst(f'DEB_bld_{i}', p_det, sf(t_hit + 0.06), FPS, C_FX, 'debris', count=260, seed=30 + i,
            speed=(8, 30), up=0.6, life=(6, 10), size=0.22, radius=2.0, ground_z=0.0)
    EV['impacts'].append(dict(name=f'missile_{i}', launch_story_s=t0, story_s=round(t_hit, 4),
                              pos=[round(c, 2) for c in tgt]))
boom('EXP_bld_core', BLD_C, T_CORE, 9.0, smoke_life=16.0, smoke_size=2.2, light_energy=4e6, fire_life=2.6,
     dust=True, ground_z=0.0)
F.burst('DEB_bld_core', BLD_C, sf(T_CORE), FPS, C_FX, 'debris', count=500, seed=41, speed=(10, 34), up=0.7,
        life=(6, 10), size=0.3, radius=4.0, ground_z=0.0)
dust_ring('DUST_bld_big', Vector((BLD_C.x, BLD_C.y - 4, 0.0)), T_CORE + 0.15, size=10.0, life=8.0, height=9.0)
pts, births = F.column_points(lambda tt: BLD_C + Vector((rv(-4, 4), rv(-3, 3), -2.0)), 0.0, T_END - T_CORE - 0.6,
                              rate=4.0, jitter=1.0)
F.trail('TRL_bld_smoke', pts, births, C_FX, sf(T_CORE + 0.6), FPS, T_END - T_CORE - 0.6, life=12.0, r0=2.0,
        grow=2.4, rise=3.8, wind=(1.2, 0.6, 0.0), voxel=0.5, density=1.0)

# ---- APC: turret aim + tracer bursts
TUR = bpy.data.objects['VEH_apc_turret']
MG = bpy.data.objects.get('VEH_apc_mg')
bpy.context.view_layer.update()
z0_t = TUR.rotation_euler.z
hull_yaw = HULL.matrix_world.to_euler().z
Mt_rest_inv = TUR.matrix_world.inverted()
if MG:
    mv = np.array([tuple(MG.matrix_world @ v.co) for v in MG.data.vertices])
    fwd_t = TUR.matrix_world.to_3x3() @ Vector((0, -1, 0))
    MZL_T = Mt_rest_inv @ Vector(mv[np.argmax(mv @ np.array(fwd_t))].tolist())
else:
    MZL_T = Vector((0, -2.5, 0.3))
PIV = TUR.matrix_world.translation.copy()


def turret_yaw(S):
    tg = MW('torso', min(S, T_IMP - 0.01)).translation + Vector((0, 0, 0.5))
    d = tg - PIV
    return math.atan2(d.x, -d.y) - hull_yaw


for f in range(int(sf(18.3)), int(sf(T_IMP)) + 1):
    S = (f - 1) / FPS
    TUR.rotation_euler.z = z0_t + turret_yaw(S)
    TUR.keyframe_insert('rotation_euler', index=2, frame=f)
F.set_interp(TUR, 'LINEAR')


def mg_muzzle(S):
    yaw = turret_yaw(S)
    M = HULL.matrix_world @ (TUR.matrix_parent_inverse if TUR.parent else Matrix()) @ Matrix.Translation(TUR.location) @ \
        Euler((TUR.rotation_euler.x, TUR.rotation_euler.y, z0_t + yaw), 'XYZ').to_matrix().to_4x4()
    return M @ MZL_T


fl_light = bpy.data.lights.new('APC_flash', 'POINT')
fl_light.color = (1.0, 0.7, 0.35)
fl_light.shadow_soft_size = 0.2
flo = bpy.data.objects.new('APC_flash', fl_light)
C_FX.objects.link(flo)
fl_light.energy = 0.0
fl_light.keyframe_insert('energy', frame=1)
for b, tb in enumerate(APC_BURSTS):
    for k in range(8):
        S0 = tb + k * 0.075
        P0 = mg_muzzle(S0)
        tg = MW('torso', S0).translation + Vector((rv(-1.4, 1.4), rv(-1.4, 1.4), rv(-0.5, 1.8)))
        S1 = S0 + (tg - P0).length / 300.0
        streak(f'TRC_apc_{b}_{k}', P0, tg, S0, S1, length=3.5, width=0.06)
        F.burst(f'SPK_hit_{b}_{k}', tg, sf(S1), FPS, C_FX, 'spark', count=40, seed=100 + b * 10 + k,
                speed=(5, 20), up=0.3, life=(0.1, 0.45), size=0.025, radius=0.1)
        flo.location = P0
        flo.keyframe_insert('location', frame=sf(S0))
        for f, e in ((sf(S0) - 0.01, 0.0), (sf(S0), 2.0e4), (sf(S0) + 0.9, 0.0)):
            fl_light.energy = e
            fl_light.keyframe_insert('energy', frame=f)
    EV['impacts'].append(dict(name=f'apc_burst_{b}', story_s=tb, shots=8))
F.set_interp(fl_light, 'LINEAR')
F.set_interp(flo, 'CONSTANT')

# ---- jeep crush (GN) driven by an empty that follows the sole until landing, then stays
CR = bpy.data.objects.new('CRUSH_sole', None)
C_HELP.objects.link(CR)
for f in range(int(sf(T_CRUSH - 0.8)), int(sf(T_CRUSH)) + 2):
    S = min((f - 1) / FPS, T_CRUSH)
    CR.matrix_world = MW(CRUSH_FOOT, S) @ Matrix.Translation(SOLE_L)
    CR.keyframe_insert('location', frame=f)
    CR.keyframe_insert('rotation_euler', frame=f)
F.set_interp(CR, 'LINEAR')


def crush_group():
    G = F.GN('CINE_crush')
    G.add_out('Geometry', 'NodeSocketGeometry')
    G.add_in('Geometry', 'NodeSocketGeometry')
    G.add_in('Sole', 'NodeSocketObject')
    G.add_in('HX', 'NodeSocketFloat', 1.2)
    G.add_in('HY', 'NodeSocketFloat', 2.0)
    G.add_in('Floor', 'NodeSocketFloat', 0.12)
    G.add_in('Soft', 'NodeSocketFloat', 0.9)
    oi = G.n('GeometryNodeObjectInfo', transform_space='RELATIVE')
    G.L(G.I('Sole'), F.inp(oi, 'Object'))
    inv = G.n('FunctionNodeInvertMatrix')
    G.L(F.outp(oi, 'Transform'), inv.inputs[0])
    pos = G.n('GeometryNodeInputPosition').outputs[0]
    tp = G.n('FunctionNodeTransformPoint')
    G.L(pos, F.inp(tp, 'Vector'))
    G.L(F.outp(inv, 'Matrix'), F.inp(tp, 'Transform'))
    x, y, z = G.sep(F.outp(tp, 'Vector'))
    dx = G.math('MAXIMUM', G.math('SUBTRACT', G.math('ABSOLUTE', x), G.I('HX')), 0.0)
    dy = G.math('MAXIMUM', G.math('SUBTRACT', G.math('ABSOLUTE', y), G.I('HY')), 0.0)
    dout = G.math('SQRT', G.math('ADD', G.math('MULTIPLY', dx, dx), G.math('MULTIPLY', dy, dy)))
    allow = G.math('ADD', G.I('Floor'), G.math('MULTIPLY', dout, G.I('Soft')))
    zn = G.math('MINIMUM', z, allow)
    dz = G.math('SUBTRACT', z, zn)
    spread = G.math('MULTIPLY', dz, 0.22)
    xn = G.math('ADD', x, G.math('MULTIPLY', G.math('DIVIDE', x, G.math('ADD', G.math('ABSOLUTE', x), 0.6)), spread))
    yn = G.math('ADD', y, G.math('MULTIPLY', G.math('DIVIDE', y, G.math('ADD', G.math('ABSOLUTE', y), 0.6)), spread))
    tb = G.n('FunctionNodeTransformPoint')
    G.L(G.comb(xn, yn, zn), F.inp(tb, 'Vector'))
    G.L(F.outp(oi, 'Transform'), F.inp(tb, 'Transform'))
    sp = G.n('GeometryNodeSetPosition')
    G.L(G.I('Geometry'), F.inp(sp, 'Geometry'))
    G.L(F.outp(tb, 'Vector'), F.inp(sp, 'Position'))
    G.L(F.outp(sp, 'Geometry'), G.go.inputs[0])
    return G.ng


cg = crush_group()
ids = {s.name: s.identifier for s in cg.interface.items_tree if getattr(s, 'in_out', '') == 'INPUT'}
for o in JEEP:
    if o.data.users > 1:
        o.data = o.data.copy()
    sub = o.modifiers.new('subd', 'SUBSURF') if len(o.data.polygons) < 3000 else None
    if sub:
        sub.levels = sub.render_levels = 1
        sub.subdivision_type = 'SIMPLE'
    md = o.modifiers.new('crush', 'NODES')
    md.node_group = cg
    F.md_set(md, ids['Sole'], CR)
    F.md_set(md, ids['HX'], SOLE_HX * 0.95)
    F.md_set(md, ids['HY'], SOLE_HY * 0.95)
jc = Vector((JEEP_XY[0], JEEP_XY[1], ground_z(*JEEP_XY) + 0.6))
F.burst('SPK_crush', jc, sf(T_CRUSH - 0.03), FPS, C_FX, 'spark', count=220, seed=61, speed=(4, 18), up=0.3,
        life=(0.2, 0.8), size=0.03, radius=1.5)
F.burst('DEB_crush', jc, sf(T_CRUSH - 0.03), FPS, C_FX, 'debris', count=90, seed=62, speed=(3, 11), up=0.5,
        life=(3, 6), size=0.07, radius=1.5, ground_z=ground_z(*JEEP_XY))
dust_ring('DUST_crush', Vector((jc.x, jc.y, jc.z - 0.6)), T_CRUSH, size=2.2, life=3.5, height=1.4)
EV['impacts'].append(dict(name='jeep_crush', story_s=round(T_CRUSH, 4), pos=[round(c, 2) for c in jc]))
for nm, tk, blk in (('block_A_kick', T_KICK_A, BLOCK_A), ('block_B_push', T_KICK_B, BLOCK_B)):
    F.burst('SPK_' + nm, blk + Vector((0, 0, 0.5)), sf(tk), FPS, C_FX, 'spark', count=60, seed=70, speed=(3, 10),
            up=0.5, life=(0.2, 0.6), size=0.025, radius=0.5)
    dust_ring('DUST_' + nm, Vector((blk.x, blk.y, ground_z(blk.x, blk.y))), tk, size=1.2, life=2.5, height=0.8)
    EV['impacts'].append(dict(name=nm, story_s=round(tk, 4), pos=[round(blk.x, 2), round(blk.y, 2)]))

# ---- the rocket
log('rocket')
RK, RFL, RHZ, RLT = N.build_rocket(C_FX)
S_R0 = T_IMP - 3.5
RK.rotation_mode = 'QUATERNION'
RK.rotation_quaternion = D_RKT.to_track_quat('X', 'Z')
for S in (S_R0, T_IMP):
    RK.location = rkt(S)
    RK.keyframe_insert('location', frame=sf(S))
F.set_interp(RK, 'LINEAR')
for _o in (RK, RFL, RLT):
    F._hide_keys(_o, int(sf(S_R0)), int(round(sf(T_IMP))))
for o in (RFL, RHZ):
    for S, v in ((S_R0, 0.0), (T_IMP, 3.5 * 22.0)):
        o['flick'] = v
        o.keyframe_insert('["flick"]', frame=sf(S))
    F.set_interp(o, 'LINEAR')
RT_MAT = F.trail_material('FX_trail_rocket', col=(0.30, 0.29, 0.27), dens=3.0)


def rocket_trail(name, S0, S1, step, voxel, r0, grow, dens):
    pts, births = [], []
    S = S0
    while S < S1:
        pts.append(rkt(S) - D_RKT * 2.25 + Vector((rv(-.04, .04), rv(-.04, .04), rv(-.04, .04))))
        births.append(S - S_R0)
        S += step / V_RKT
    F.trail(name, pts, births, C_FX, sf(S_R0), FPS, T_NUKE - S_R0 + 0.2, life=7.0, r0=r0, grow=grow,
            rise=0.25, wind=(0.35, 0.15, 0.0), voxel=voxel, density=dens, material=RT_MAT)


rocket_trail('TRL_rocket_far', S_R0, S_MID - 0.6, 1.4, 0.5, 0.7, 1.2, 1.4)
rocket_trail('TRL_rocket_mid1', S_MID - 0.6, S_MID - 0.12, 0.35, 0.16, 0.42, 1.0, 1.8)
rocket_trail('TRL_rocket_near', S_MID - 0.12, S_MID + 0.22, 0.1, 0.07, 0.3, 0.9, 2.2)
rocket_trail('TRL_rocket_mid2', S_MID + 0.22, T_IMP, 0.35, 0.16, 0.42, 1.0, 1.8)
S = S_MID - 0.07
k = 0
while S < S_MID + 0.06:
    F.burst(f'SPK_rkt_{k:02d}', rkt(S) - D_RKT * 2.2, sf(S), FPS, C_FX, 'spark', count=26, seed=200 + k,
            speed=(1.5, 7), up=0.2, direction=tuple(-D_RKT), life=(0.4, 1.4), size=0.012, radius=0.12,
            gravity=3.0)
    S += 0.5 / V_RKT
    k += 1
EV['impacts'].append(dict(name='rocket_launch', story_s=S_R0, pos=[round(c, 1) for c in rkt(S_R0)]))
EV['impacts'].append(dict(name='rocket_chest_impact', story_s=T_IMP, pos=[round(c, 2) for c in I_PT]))

# ---- impact explosion + burning pieces
boom('EXP_impact', I_PT, T_IMP, 5.0, smoke_life=8.0, smoke_size=1.6, light_energy=3e6, fire_life=1.6, dust=True)
F.burst('SPK_impact', I_PT, sf(T_IMP), FPS, C_FX, 'spark', count=1500, seed=301, speed=(10, 60), up=0.3,
        life=(0.4, 2.0), size=0.05, radius=0.8)
F.burst('DEB_impact', I_PT, sf(T_IMP), FPS, C_FX, 'debris', count=400, seed=302, speed=(5, 35), up=0.4,
        life=(4, 8), size=0.08, radius=1.0)
cands = sorted([p for p in PIECES if not any(s in PIECE_OF[p.name] for s in LEGS)],
               key=lambda p: -(la[p.name][0].length))[:12]
fire_mat = F.get_fx_mats()['fire']
for i, p in enumerate(cands):
    pts, births = [], []
    for k in range(int(3.0 * 30)):
        S = T_IMP + k / 30.0
        pts.append(piece_pos(p.name, S))
        births.append(S - T_IMP)
    F.trail(f'TRL_piece_{i:02d}', pts, births, C_FX, sf(T_IMP), FPS, 8.0, life=5.0, r0=0.25, grow=0.9,
            rise=0.8, wind=(0.6, 0.3, 0), voxel=0.15, density=1.2)
    fb = F.volume_domain(f'FIRE_piece_{i:02d}', C_FX)
    fb.data.materials.append(fire_mat)
    fb['seed'] = rv(0, 100)
    f0 = int(sf(T_IMP))
    for f in range(f0, f0 + int(2.6 * FPS)):
        t = (f - f0) / FPS
        fb.location = piece_pos(p.name, T_IMP + t)
        R = 0.9 + 0.5 * math.sin(t * 9 + i)
        fb.scale = (R, R, R)
        fb['age'] = t * 2.0
        fb['heat'] = max(0.0, 1.0 - t / 2.6)
        fb['dens'] = 1.0
        fb['erode'] = min(0.6, t / 2.6 * 0.6)
        for pth in ('location', 'scale', '["age"]', '["heat"]', '["erode"]', '["dens"]'):
            fb.keyframe_insert(pth, frame=f)
    F.set_interp(fb, 'LINEAR')
    F._hide_keys(fb, f0, f0 + int(2.6 * FPS) - 1)

# ---- nuke
log('nuke')
NUKE_OBJS = N.nuke(E_PT, sf(T_NUKE), FPS, C_FX, sf(T_END) + 2, ground_z=E_PT.z)
EV['explosions'].append(dict(name='NUKE', story_s=T_NUKE, pos=[round(c, 2) for c in E_PT], size='W-12 0.3kt'))
EV['impacts'].append(dict(name='nuke_shock_wave', story_s=T_NUKE, note='ground ring r(t)=105*t^0.62 m'))

# =============================================================================== 9. retime (story -> render)
log('retime')
dR = 1.0 / (FPS * 40)


def integrate(Rb0):
    """returns arrays R, S and the key render times."""
    Rs, Ss = [0.0], [0.0]
    R, S = 0.0, 0.0
    marks = {}
    Rb1 = Rb0 + 0.25 + 2.3
    st = 'pre'
    while True:
        if st == 'pre':
            if R < Rb0:
                v = 1.0
            elif R < Rb0 + 0.25:
                v = 1.0 + (0.05 - 1.0) * smooth((R - Rb0) / 0.25)
            elif R < Rb1:
                v = 0.05
            elif R < Rb1 + 0.08:
                v = 0.05 + 0.95 * smooth((R - Rb1) / 0.08)
            else:
                v = 1.0
            if S >= T_IMP:
                st = 'imp'
                marks['R_imp'] = R
        if st == 'imp':
            v = 1.0 + (0.2 - 1.0) * smooth((R - marks['R_imp']) / 0.125)
            if S >= T_NUKE and 'R_flash' not in marks:
                marks['R_flash'] = R
            if 'R_flash' in marks and R >= marks['R_flash'] + 0.12:
                st = 'shock'
                marks['R_c1'] = R
        if st == 'shock':
            v = 0.45
            if R >= marks['R_c1'] + 3.3:
                st = 'wide'
                marks['R_c2'] = R
        if st == 'wide':
            v = 1.0
            if S >= T_END - 0.05 or R >= marks['R_c2'] + 7.5:
                marks['R_end'] = R
                break
        R += dR
        S += v * dR
        Rs.append(R)
        Ss.append(S)
        if R > 80:
            break
    marks['Rb0'] = Rb0
    marks['Rb1'] = Rb1
    return np.array(Rs), np.array(Ss), marks


lo, hi = S_MID - 1.0, S_MID
for _ in range(30):
    mid = (lo + hi) / 2
    Ra, Sa, mk = integrate(mid)
    s_at = np.interp(mid + 0.25 + 1.15, Ra, Sa)
    if s_at < S_MID:
        lo = mid
    else:
        hi = mid
RA, SA, MK = integrate((lo + hi) / 2)
log('retime marks', {k: round(v, 3) for k, v in MK.items()})
NR = int(math.floor(MK['R_end'] * FPS)) + 1
r_frames = np.arange(1, NR + 1, dtype=float)
S_of_r = np.interp((r_frames - 1) / FPS, RA, SA)
SF_of_r = 1.0 + S_of_r * FPS


def S_of_R(R):
    return float(np.interp(R, RA, SA))


def R_of_S(S):
    return float(np.interp(S, SA, RA))


def write_fc(fc, x, y, interp):
    fc.keyframe_points.clear()
    n = len(x)
    fc.keyframe_points.add(n)
    co = np.empty(2 * n)
    co[0::2] = x
    co[1::2] = y
    fc.keyframe_points.foreach_set('co', co)
    ip = bpy.types.Keyframe.bl_rna.properties['interpolation'].enum_items[interp].value
    fc.keyframe_points.foreach_set('interpolation', [ip] * n)
    fc.update()


nfc = 0
nkeys = 0
for act in list(bpy.data.actions):
    for fc in F.fcurves_of(act):
        n = len(fc.keyframe_points)
        if n == 0:
            continue
        co = np.empty(2 * n)
        fc.keyframe_points.foreach_get('co', co)
        x, y = co[0::2].copy(), co[1::2].copy()
        order = np.argsort(x, kind='stable')
        x, y = x[order], y[order]
        const = fc.keyframe_points[0].interpolation == 'CONSTANT' or fc.data_path.startswith('hide') or \
            'kinematic' in fc.data_path
        if const:
            xr = np.interp(x, SF_of_r, r_frames, left=None, right=None)
            below = x < SF_of_r[0]
            xr[below] = x[below] - SF_of_r[0] + 1.0
            above = x > SF_of_r[-1]
            xr[above] = NR + (x[above] - SF_of_r[-1])
            for i in range(1, len(xr)):
                if xr[i] <= xr[i - 1]:
                    xr[i] = xr[i - 1] + 1e-3
            write_fc(fc, xr, y, 'CONSTANT')
            nkeys += len(xr)
        else:
            i0 = max(int(np.searchsorted(SF_of_r, x[0])) - 1, 0)
            i1 = min(int(np.searchsorted(SF_of_r, x[-1])) + 1, NR - 1)
            idx = np.arange(i0, i1 + 1)
            s = SF_of_r[idx]
            v = np.interp(s, x, y)
            if fc.extrapolation == 'LINEAR' and n >= 2:
                s0 = (y[1] - y[0]) / max(x[1] - x[0], 1e-9)
                s1 = (y[-1] - y[-2]) / max(x[-1] - x[-2], 1e-9)
                v = np.where(s < x[0], y[0] + (s - x[0]) * s0, v)
                v = np.where(s > x[-1], y[-1] + (s - x[-1]) * s1, v)
            write_fc(fc, r_frames[idx], v, 'LINEAR')
            nkeys += len(idx)
        nfc += 1
log(f'retimed {nfc} fcurves, {nkeys} keys, render frames {NR} ({NR / FPS:.2f}s)')
sc.frame_start, sc.frame_end = 1, NR

# =============================================================================== 10. cameras (render time)
log('cameras')
R_IMP, R_FLASH, R_C1, R_C2, R_END = MK['R_imp'], MK['R_flash'], MK['R_c1'], MK['R_c2'], MK['R_end']
SHAKES = []        # (R, amp_rad, decay_s, freq, pos)
for ex in EV['explosions']:
    sz = ex['size'] if isinstance(ex['size'], (int, float)) else 30.0
    SHAKES.append((R_of_S(ex['story_s']), 0.006 * sz, 0.35, 11.0, Vector(ex['pos'])))
for st_ in EV['steps']:
    SHAKES.append((R_of_S(st_['story_s']), 0.012, 0.25, 7.0, Vector((st_['pos'][0], st_['pos'][1], 0))))
SHAKES.append((R_IMP, 0.05, 0.6, 9.0, I_PT))


def shake_at(R, pos, seed):
    a = Vector((0, 0, 0))
    for (Rt, amp, dec, fr, p) in SHAKES:
        if R < Rt or R > Rt + dec * 6:
            continue
        dist = (pos - p).length
        k = amp * min(1.0, 14.0 / max(dist, 1.0))
        dt = R - Rt
        e = math.exp(-dt / dec) * k
        a += Vector((math.sin(2 * math.pi * fr * dt + seed), math.sin(2 * math.pi * fr * 1.37 * dt + 1.1 + seed),
                     math.sin(2 * math.pi * fr * 0.71 * dt + 2.3))) * e
    return a


def handheld(R, seed, amp):
    return Vector((math.sin(R * 1.13 + seed) + 0.5 * math.sin(R * 2.71 + 2 * seed),
                   math.sin(R * 0.87 + 3 * seed) + 0.5 * math.sin(R * 2.23 + seed),
                   0.4 * math.sin(R * 1.61 + seed))) * amp


CAMS = []


def add_shot(name, r0, r1, fn, hand=0.003, shake_k=1.0, dof=None, clip=(0.1, 3000)):
    cd = bpy.data.cameras.new('CAM_' + name)
    cd.sensor_width = 36.0
    cd.clip_start, cd.clip_end = clip
    cam = bpy.data.objects.new('CAM_' + name, cd)
    C_CAM.objects.link(cam)
    f0 = int(math.floor(r0 * FPS)) + 1
    f1 = min(int(math.ceil(r1 * FPS)) + 1, NR)
    fr = np.arange(max(f0 - 1, 1), min(f1 + 2, NR + 1))
    L, Rt, Ln = [], [], []
    prev = None
    seed = len(CAMS) * 1.7
    for f in fr:
        R = (f - 1) / FPS
        S = S_of_R(R)
        loc, tgt, lens = fn(R, S)
        loc, tgt = Vector(loc), Vector(tgt)
        q = (tgt - loc).to_track_quat('-Z', 'Y')
        e = q.to_euler('XYZ', prev) if prev else q.to_euler('XYZ')
        h = handheld(R, seed, hand) + shake_at(R, loc, seed) * shake_k
        e2 = Euler((e.x + h.x, e.y + h.z, e.z + h.y), 'XYZ')
        prev = e
        L.append(tuple(loc))
        Rt.append(tuple(e2))
        Ln.append(lens)
    L, Rt, Ln = np.array(L), np.array(Rt), np.array(Ln)
    for k in range(3):
        F.set_keys_fast(cam, 'location', k, fr.astype(float), L[:, k])
        F.set_keys_fast(cam, 'rotation_euler', k, fr.astype(float), Rt[:, k])
    F.set_keys_fast(cd, 'lens', 0, fr.astype(float), Ln)
    if dof:
        cd.dof.use_dof = True
        if isinstance(dof[0], bpy.types.Object):
            cd.dof.focus_object = dof[0]
        else:
            cd.dof.focus_distance = dof[0]
        cd.dof.aperture_fstop = dof[1]
    m = sc.timeline_markers.new('SH_' + name, frame=f0)
    m.camera = cam
    CAMS.append(cam)
    EV['shots'].append(dict(name=name, render_start_s=round(r0, 3), render_end_s=round(r1, 3), frame_start=f0,
                            frame_end=min(int(math.floor(r1 * FPS)) + 1, NR), story_start_s=round(S_of_R(r0), 3),
                            story_end_s=round(S_of_R(r1), 3), camera=cam.name))
    return cam


def V(*a):
    return Vector(a)


def torso(S):
    return MW('torso', min(S, T_IMP - 1e-3)).translation


def cut(S):
    return R_of_S(S)


R3A = cut(T_FIRE + 0.12)
R4A = 14.0
R4B = cut(MISSILES[1][0] + 0.12)
R5A, R5B, R6A, R6B, R6C = 19.7, cut(T_KICK_A - 0.05), 23.0, 24.45, 25.25
add_shot('01_establish', 0.0, 4.0, lambda R, S: (
    V(-42, -78, 17).lerp(V(-31, -61, 11.5), smooth(R / 4.0)), V(torso(S).x * 0.3, torso(S).y, 4.5), 30.0),
    hand=0.0015)
add_shot('02_track', 4.0, 8.4, lambda R, S: (
    V(5.0, torso(S).y + 14.0 - 3.0 * (R - 4.0) / 4.4, 1.3), torso(S) + V(0, 0, -1.2), 24.0), hand=0.003)
add_shot('03a_overshoulder', 8.4, R3A, lambda R, S: (
    torso(S) + V(-7.5, -9.5, 2.0), torso(S).lerp(V(18.5, -6.2, 2.0), 0.35 + 0.65 * smooth((R - 8.4) / 1.1)), 24.0),
    hand=0.003)
add_shot('03b_truck', R3A, R4A, lambda R, S: (
    V(7.0, -19.5, 2.0).lerp(V(6.2, -20.6, 2.3), (R - R3A) / (R4A - R3A)), V(18.0, -6.0, 3.2), 22.0), hand=0.004)
add_shot('04a_behind', R4A, R4B, lambda R, S: (
    torso(S) + V(3.5, -12.0, 1.5), V(6.0, 26.0, 8.0), 26.0), hand=0.003)
add_shot('04b_building', R4B, R5A, lambda R, S: (
    V(-22.0, 2.0, 3.0).lerp(V(-20.5, 3.5, 3.4), (R - R4B) / (R5A - R4B)), V(6.5, 30.0, 8.5), 20.0), hand=0.003)
add_shot('05a_jeep', R5A, R5B, lambda R, S: (
    V(JEEP_XY[0] - 7.5, JEEP_XY[1] - 3.0, 1.1), V(JEEP_XY[0] + 0.2, JEEP_XY[1], 1.9), 22.0), hand=0.004,
    shake_k=1.5)
APC_DIR = Vector((torso(21.5).x - PIV.x, torso(21.5).y - PIV.y, 0)).normalized()
APC_PERP = Vector((-APC_DIR.y, APC_DIR.x, 0))
add_shot('05b_apc', R5B, R6A, lambda R, S: (
    PIV - APC_DIR * 3.6 + V(0, 0, 1.5) + APC_PERP * 0.9, torso(S) + V(0, 0, -1.0), 38.0), hand=0.004)
PT = torso(T_SNAP)
UP_ = Vector((-U_SRC.y, U_SRC.x, 0))
add_shot('06a_turn', R6A, R6B, lambda R, S: (
    PT + U_SRC * (12.0 - 1.5 * smooth((R - R6A) / (R6B - R6A))) + UP_ * 4.5 + V(0, 0, -2.0),
    PT + V(0, 0, 0.3), 28.0), hand=0.003, shake_k=1.5)
add_shot('06b_pov', R6B, R6C, lambda R, S: (
    MW('cockpit', S).translation - U_SRC * 3.0 + V(0, 0, 2.2) + UP_ * 0.8, rkt(max(S, T_IMP - 3.4)), 180.0),
    hand=0.004)
Q0 = rkt(S_MID) + PERP * 2.4 + V(0, 0, 0.35)


def bullet_cam(R, S):
    loc = Q0 + D_RKT * (V_RKT * (S - S_MID)) * 0.5
    return loc, rkt(S) + D_RKT * 0.5, 30.0


add_shot('06c_bullet', R6C, R_IMP - 0.1, bullet_cam, hand=0.0015, dof=(RK, 4.0))
add_shot('07_impact', R_IMP - 0.1, R_C1, lambda R, S: (
    I_PT + V(2.5, -16.5, -3.0).lerp(V(2.3, -15.2, -3.0), (R - R_IMP) / (R_C1 - R_IMP)), I_PT + V(1.5, 0, -0.8),
    26.0), hand=0.002, shake_k=1.0)
CAM7B = V(42.0, -57.0, 2.2)
SHAKES.append((R_of_S(T_NUKE + ((CAM7B.xy - E_PT.xy).length / 105.0) ** (1 / 0.62)), 0.06, 0.8, 8.0, CAM7B))
add_shot('07b_shock', R_C1, R_C2, lambda R, S: (CAM7B, V(E_PT.x, E_PT.y, 14.0), 24.0), hand=0.002)
add_shot('08_mushroom', R_C2, R_END, lambda R, S: (
    V(75, -160, 26).lerp(V(71, -154, 25.5), (R - R_C2) / (R_END - R_C2)), V(E_PT.x, E_PT.y + 5, 42), 24.0),
    hand=0.0015)
# cameras made after their shakes -> shot 7b shake added before its camera; fine.

# exposure flashes + motion-blur shutter (render time)
vs = sc.view_settings
ex_keys = [(1, 0.0), (int(R_IMP * FPS) + 1, 0.0), (int(R_IMP * FPS) + 2, 0.6), (int(R_IMP * FPS) + 8, 0.0)]
fF = int(R_FLASH * FPS) + 1
ex_keys += [(fF - 1, 0.0), (fF, 6.0), (fF + 1, 7.0), (fF + 2, 5.5), (fF + 4, 3.0)]
fC1 = int(R_C1 * FPS) + 1
ex_keys += [(fC1, 1.6), (fC1 + 6, 0.6), (fC1 + 24, 0.1), (fC1 + 48, 0.0)]
ex_keys = sorted(dict(ex_keys).items())
for f, v in ex_keys:
    vs.exposure = v
    sc.keyframe_insert('view_settings.exposure', frame=f)
sc.render.use_motion_blur = True
for f, v in ((1, 0.5), (int(MK['Rb0'] * FPS), 0.5), (int(MK['Rb0'] * FPS) + 6, 0.12), (int(MK['Rb1'] * FPS), 0.12),
             (int(MK['Rb1'] * FPS) + 3, 0.5)):
    sc.render.motion_blur_shutter = v
    sc.keyframe_insert('render.motion_blur_shutter', frame=f)
F.set_interp(sc, 'LINEAR')
vs.exposure = 0.0

# =============================================================================== 11. render settings + save + events
e = sc.eevee
sc.render.engine = 'BLENDER_EEVEE'
e.taa_render_samples = 16
e.volumetric_tile_size = '8'
e.volumetric_samples = 64
e.volumetric_end = 700.0
e.use_volumetric_shadows = True
try:
    e.use_raytracing = True
except Exception:
    pass
sc.render.resolution_x, sc.render.resolution_y = 1920, 1080
sc.render.resolution_percentage = 100
sc.render.image_settings.file_format = 'PNG'
sc.render.filepath = os.path.join(ROOT, 'renders', 'cine', 'frames', 'f_')
sc.camera = CAMS[0]
for nm in ('CAM_wide', 'CAM_hero', 'CAM_top'):
    pass


def rs(S):
    return round(R_of_S(S), 3)


for k in ('explosions', 'impacts', 'steps'):
    for ev_ in EV[k]:
        if 'story_s' in ev_:
            ev_['render_s'] = rs(ev_['story_s'])
            ev_['frame'] = int(round(R_of_S(ev_['story_s']) * FPS)) + 1
EV['retime'] = dict(bullet_time=dict(ramp_start_s=round(MK['Rb0'], 3), hold_end_s=round(MK['Rb1'], 3), speed=0.05),
                    impact_slowmo=dict(start_s=round(R_IMP, 3), speed=0.2), shock=dict(start_s=round(R_C1, 3), speed=0.45),
                    wide=dict(start_s=round(R_C2, 3), speed=1.0), end_s=round(R_END, 3), frames=NR)
EV['key_moments_render_s'] = dict(cannon_fire=rs(T_FIRE), truck_explosion=rs(T_TRUCK),
                                  missiles=[rs(m[0]) for m in MISSILES], building_core=rs(T_CORE),
                                  jeep_crush=rs(T_CRUSH), block_kicks=[rs(T_KICK_A), rs(T_KICK_B)],
                                  torso_snap=rs(T_SNAP), rocket_impact=round(R_IMP, 3), nuke_flash=round(R_FLASH, 3))
os.makedirs(os.path.dirname(EVENTS), exist_ok=True)
json.dump(EV, open(EVENTS, 'w'), indent=1)
os.makedirs(os.path.dirname(OUT_BLEND), exist_ok=True)
bpy.ops.wm.save_as_mainfile(filepath=OUT_BLEND, copy=False)
log('saved', OUT_BLEND, 'frames', NR, 'events', EVENTS)

# Build the abandoned-checkpoint environment around the heavy mech.
# Run headless:
#   /Applications/Blender.app/Contents/MacOS/Blender -b --factory-startup --python scripts/env/build_env.py [-- --nosave]
import bpy, sys, os, time, random, importlib, math

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import env_common, env_materials, env_ground, env_lighting
for m in (env_common, env_materials, env_ground, env_lighting):
    importlib.reload(m)
from env_common import get_coll, layer_coll, ROOT, tri_count_mesh

ARGS = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
OUT = os.path.join(ROOT, 'environment.blend')
MECH = os.path.join(ROOT, 'heavy_mech_v3.blend')
T0 = time.time()


def log(*a):
    print('[ENV %6.1fs]' % (time.time() - T0), *a, flush=True)


def clear_scene():
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob, do_unlink=True)
    for c in list(bpy.data.collections):
        bpy.data.collections.remove(c)
    for blk in (bpy.data.meshes, bpy.data.materials, bpy.data.lights, bpy.data.cameras, bpy.data.node_groups,
                bpy.data.curves):
        for d in list(blk):
            blk.remove(d)


COLLS = ['ENV_ground', 'ENV_road', 'ENV_buildings', 'ENV_props', 'ENV_vegetation', 'ENV_backdrop', 'ENV_lights',
         'ENV_slots', 'ENV_placeholders', 'ENV_cameras', 'ENV_assets', 'ENV_debug']


def make_colls():
    root = get_coll('ENVIRONMENT')
    C = {n: get_coll(n, root) for n in COLLS}
    return C


def append_mech():
    with bpy.data.libraries.load(MECH, link=False) as (src, dst):
        dst.collections = [c for c in src.collections if c == 'HeavyMech']
    for c in dst.collections:
        if c is not None and c.name not in bpy.context.scene.collection.children:
            bpy.context.scene.collection.children.link(c)
    mc = bpy.data.collections.get('HeavyMech')
    root = bpy.data.objects.get('mech_root')
    if root:
        root.location = (0, 0, 0)
    tris = sum(tri_count_mesh(o.data) for o in mc.all_objects if o.type == 'MESH') if mc else 0
    log('mech appended, tris', tris)
    return mc


def stage(name, fn, *a, **k):
    t = time.time()
    r = fn(*a, **k)
    log('stage %-22s %.1fs' % (name, time.time() - t))
    return r


def main():
    clear_scene()
    C = make_colls()
    rnd = random.Random(7)
    M = stage('materials', env_materials.build_all)
    G = env_ground
    terrain = stage('terrain', G.build_terrain, C['ENV_ground'], M)
    road = stage('road', G.build_road, C['ENV_road'], M)
    apron = stage('apron', G.build_apron, C['ENV_ground'], M, rnd)
    ground = stage('raycaster', G.Ground, [terrain, road, apron])
    stage('puddles', G.build_puddles, C['ENV_road'], M, ground)
    stage('ruts', G.build_ruts, C['ENV_ground'], M, ground)
    mods = {}
    for nm in ('env_buildings', 'env_props', 'env_scatter', 'env_backdrop'):
        if os.path.exists(os.path.join(HERE, nm + '.py')) and nm not in ARGS:
            mods[nm] = importlib.reload(importlib.import_module(nm))
    if 'env_buildings' in mods:
        stage('buildings', mods['env_buildings'].build, C, M, ground, rnd)
    if 'env_props' in mods:
        stage('props', mods['env_props'].build, C, M, ground, rnd)
    if 'env_scatter' in mods:
        stage('scatter', mods['env_scatter'].build, C, M, ground, rnd)
    if 'env_backdrop' in mods:
        stage('backdrop', mods['env_backdrop'].build, C, M, ground, rnd)
    L = env_lighting
    L.build_world()
    L.build_sun(C['ENV_lights'])
    L.build_haze(C['ENV_lights'], M)
    if '--nosmoke' not in ARGS:
        L.build_smoke(C['ENV_backdrop'], M)
    L.build_cameras(C['ENV_cameras'])
    L.render_settings()
    stage('mech', append_mech)
    # prototypes collection is not rendered directly
    lc = layer_coll('ENV_assets')
    if lc:
        lc.exclude = True
    C['ENV_debug'].hide_render = True
    layer_coll('ENV_debug').exclude = True
    if '--nouv' not in ARGS:
        stage('uv', smart_uv_all)
    stats = tri_stats()
    log('TRIS', stats)
    if '--nosave' not in ARGS:
        bpy.ops.wm.save_as_mainfile(filepath=OUT, compress=True)
        log('saved', OUT)


def smart_uv_all():
    obs = [o for o in bpy.data.objects if o.type == 'MESH' and len(o.data.polygons) and not o.data.uv_layers
           and not o.name.startswith(('mech', 'MECH')) and o.users_collection
           and not any(c.name == 'HeavyMech' or c.name.startswith('HeavyMech') for c in o.users_collection)]
    meshes = {}
    for o in obs:
        meshes.setdefault(o.data.name, o)
    obs = list(meshes.values())
    if not obs:
        return
    # temporarily make the asset collection visible so its objects can enter edit mode
    lc = layer_coll('ENV_assets')
    if lc:
        lc.exclude = False
    vl = bpy.context.view_layer
    obs = [o for o in obs if o.name in vl.objects]
    for o in vl.objects:
        o.select_set(False)
    for o in obs:
        o.select_set(True)
    vl.objects.active = obs[0]
    with bpy.context.temp_override(active_object=obs[0], selected_objects=obs, selected_editable_objects=obs):
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.uv.smart_project(angle_limit=math.radians(66), island_margin=0.003, scale_to_bounds=False)
        bpy.ops.object.mode_set(mode='OBJECT')
    if lc:
        lc.exclude = True
    log('smart uv on', len(obs), 'meshes')


def tri_stats():
    dg = bpy.context.evaluated_depsgraph_get()
    mc = bpy.data.collections.get('HeavyMech')
    mech_names = {o.name for o in mc.all_objects} if mc else set()
    cache = {}
    per = {}
    total_env = 0
    total_mech = 0
    for inst in dg.object_instances:
        ob = inst.object
        if ob.type != 'MESH':
            continue
        key = ob.data.name if not inst.is_instance else ('I', ob.original.data.name)
        if key not in cache:
            try:
                me = ob.data
                me.calc_loop_triangles()
                cache[key] = len(me.loop_triangles)
            except Exception:
                cache[key] = 0
        n = cache[key]
        src = inst.parent.original if inst.is_instance and inst.parent else ob.original
        cname = src.users_collection[0].name if src.users_collection else '?'
        if src.name in mech_names:
            total_mech += n
            continue
        if src.name in ('ENV_haze_volume', 'ENV_smoke_column'):
            continue
        per[cname] = per.get(cname, 0) + n
        total_env += n
    return {'env_total': total_env, 'mech': total_mech, 'per_coll': per}


main()

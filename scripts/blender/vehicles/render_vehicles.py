# Studio + camera + Cycles(Metal) helpers for the vehicle renders.
# As a script (final renders):  Blender -b --factory-startup vehicles.blend --python render_vehicles.py -- [final|quick]
#   -> renders/veh_<name>.png, renders/vehicles_lineup.png, renders/vehicles_scale_mech.png
#   The mech is appended into a throw-away scene only for the scale shot; nothing is saved.
import bpy, math, os, sys, time
from mathutils import Vector, Matrix

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import veh_lib as V

NAMES = ['truck', 'apc', 'jeep', 'wreck']


def setup_render(scene, samples=96, res=(1280, 720), exposure=0.0, look='AgX - Medium High Contrast', engine='CYCLES'):
    if engine == 'CYCLES':
        scene.render.engine = 'CYCLES'
        try:
            prefs = bpy.context.preferences.addons['cycles'].preferences
            prefs.compute_device_type = 'METAL'
            prefs.get_devices()
            for d in prefs.devices:
                d.use = d.type == 'METAL'
            scene.cycles.device = 'GPU'
        except Exception as e:
            print('GPU setup failed', e)
        c = scene.cycles
        c.samples = samples
        c.use_adaptive_sampling = True
        c.adaptive_threshold = 0.02
        c.use_denoising = True
        try:
            c.denoiser = 'OPENIMAGEDENOISE'
        except Exception:
            pass
        c.max_bounces = 8
        c.diffuse_bounces = 3
        c.glossy_bounces = 3
        c.transmission_bounces = 6
        c.transparent_max_bounces = 8
        c.caustics_reflective = False
        c.caustics_refractive = False
    else:
        scene.render.engine = 'BLENDER_EEVEE'
    scene.render.resolution_x, scene.render.resolution_y = res
    scene.render.resolution_percentage = 100
    scene.render.film_transparent = False
    scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.color_mode = 'RGB'
    vs = scene.view_settings
    vs.view_transform = 'AgX'
    try:
        vs.look = look
    except Exception as e:
        print('look', e)
    vs.exposure = exposure


def _coll(name, scene):
    c = bpy.data.collections.get(name)
    if c is None:
        c = bpy.data.collections.new(name)
        scene.collection.children.link(c)
    return c


def studio(scene, az=35.0, target=(0, 0, 0), size=60.0, grey=0.2, key=3.2, name='VEH_Studio'):
    """neutral cyclorama facing the camera azimuth + sun key / rim + grey world"""
    coll = _coll(name, scene)
    for o in list(coll.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    import bmesh
    bm = bmesh.new()
    prof = [(-size, 0.0), (size * 0.15, 0.0)]
    rr = size * 0.18
    for k in range(1, 9):
        a = math.radians(90 * k / 8)
        prof.append((size * 0.15 + rr * math.sin(a), rr * (1 - math.cos(a))))
    prof.append((size * 0.15 + rr, size * 0.6))
    rows = []
    for d, z in prof:
        rows.append([bm.verts.new((x, d, z)) for x in (-size, -size / 3, size / 3, size)])
    for r0, r1 in zip(rows, rows[1:]):
        for i in range(3):
            bm.faces.new((r0[i], r0[i + 1], r1[i + 1], r1[i]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new('studio_cyc')
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = True
    ob = bpy.data.objects.new('studio_cyc', me)
    coll.objects.link(ob)
    # backdrop "behind" (+d) must point away from the camera
    ob.rotation_euler = (0, 0, math.radians(az))
    ob.location = (target[0], target[1], 0)
    m = bpy.data.materials.get('studio_grey') or bpy.data.materials.new('studio_grey')
    m.use_nodes = True
    b = next(n for n in m.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
    b.inputs['Base Color'].default_value = (grey, grey, grey, 1)
    b.inputs['Roughness'].default_value = 0.75
    me.materials.append(m)
    for nm, rx, rz, e, ang in (('studio_key', 48, az + 62, key, 6.0), ('studio_rim', 30, az + 200, key * 0.55, 4.0),
                               ('studio_fill', 20, az - 60, key * 0.18, 20.0)):
        ld = bpy.data.lights.new(nm, 'SUN')
        ld.energy = e
        ld.angle = math.radians(ang)
        lo = bpy.data.objects.new(nm, ld)
        # sun points along -Z; aim from direction (azimuth rz, elevation rx) toward the target
        el, azr = math.radians(rx), math.radians(rz)
        d = Vector((math.sin(azr) * math.cos(el), -math.cos(azr) * math.cos(el), math.sin(el)))
        lo.rotation_euler = d.to_track_quat('Z', 'Y').to_euler()
        coll.objects.link(lo)
    w = scene.world or bpy.data.worlds.new('World')
    scene.world = w
    w.use_nodes = True
    bg = next(n for n in w.node_tree.nodes if n.type == 'BACKGROUND')
    bg.inputs['Color'].default_value = (0.055, 0.057, 0.06, 1)
    bg.inputs['Strength'].default_value = 1.0
    return coll


def bbox_points(objs):
    pts = []
    for o in objs:
        if o.type != 'MESH':
            continue
        for c in o.bound_box:
            pts.append(o.matrix_world @ Vector(c))
    return pts


def fit_camera(scene, objs, az=35.0, el=22.0, lens=50.0, margin=0.9, name='veh_cam', target_z=None):
    bpy.context.view_layer.update()
    pts = bbox_points(objs)
    lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    c = (lo + hi) / 2
    if target_z is not None:
        c.z = target_z
    a, e = math.radians(az), math.radians(el)
    d = Vector((math.sin(a) * math.cos(e), -math.cos(a) * math.cos(e), math.sin(e)))
    cam = bpy.data.objects.get(name)
    if cam is None:
        cam = bpy.data.objects.new(name, bpy.data.cameras.new(name))
        scene.collection.objects.link(cam)
    cam.data.lens = lens
    cam.data.sensor_fit = 'HORIZONTAL'
    cam.data.sensor_width = 36.0
    cam.data.clip_end = 1000
    rx, ry = scene.render.resolution_x, scene.render.resolution_y
    tx = math.tan(math.atan(18.0 / lens)) * margin
    ty = tx * ry / rx
    fwd = -d
    right = fwd.cross(Vector((0, 0, 1))).normalized()
    up = right.cross(fwd).normalized()
    for _ in range(3):
        D = 0.0
        for p in pts:
            q = p - c
            D = max(D, q.dot(d) + abs(q.dot(right)) / tx, q.dot(d) + abs(q.dot(up)) / ty)
        sx = [(p - c).dot(right) / (D - (p - c).dot(d)) for p in pts]
        sy = [(p - c).dot(up) / (D - (p - c).dot(d)) for p in pts]
        c += right * ((max(sx) + min(sx)) / 2 * D) + up * ((max(sy) + min(sy)) / 2 * D)
    cam.location = c + d * D
    cam.rotation_euler = fwd.to_track_quat('-Z', 'Y').to_euler()
    scene.camera = cam
    return cam


def render(scene, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    scene.render.filepath = path
    t = time.time()
    bpy.ops.render.render(write_still=True)
    print('RENDERED', path, '%.1fs' % (time.time() - t))


def lineup_positions(roots, az=35.0, gap=1.4):
    """place roots side by side along the camera-right vector (all keep facing -Y)"""
    a = math.radians(az)
    right = Vector((math.cos(a), math.sin(a), 0))
    ext = []
    for r in roots:
        pts = bbox_points([o for o in V.vehicle_objects(r) if o.type == 'MESH'])
        loc = r.matrix_world.translation
        q = [(p - loc).dot(right) for p in pts]
        ext.append((min(q), max(q)))
    t = 0.0
    pos = []
    for k, (mn, mx) in enumerate(ext):
        if k == 0:
            t = -mn
        else:
            t += gap - mn
        pos.append(t)
        t += mx
    shift = (pos[0] + ext[0][0] + pos[-1] + ext[-1][1]) / 2
    for r, t in zip(roots, pos):
        r.location = right * (t - shift)
        r['pivot_world'] = list(r.location)
    bpy.context.view_layer.update()


def hide_except(scene, keep_roots):
    keep = set()
    for r in keep_roots:
        keep.update(V.vehicle_objects(r))
    for o in scene.objects:
        if o.name.startswith(tuple(n + '_' for n in NAMES) + tuple('VEH_' + n + '_' for n in NAMES)):
            o.hide_render = o not in keep


def main():
    argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    mode = argv[0] if argv else 'final'
    q = mode != 'final'
    if mode == 'lineup50':
        return lineup_only(bpy.context.scene)
    samples, res = (48, (1280, 720)) if q else (192, (1920, 1080))
    sc = bpy.context.scene
    setup_render(sc, samples=samples, res=res, exposure=-0.1)
    roots = {n: bpy.data.objects[n + '_root'] for n in NAMES if bpy.data.objects.get(n + '_root')}
    saved = {n: r.location.copy() for n, r in roots.items()}
    az, el = 35.0, 20.0
    # --- per vehicle
    for n, r in roots.items():
        hide_except(sc, [r])
        old = r.location.copy()
        r.location = (0, 0, 0)
        studio(sc, az=az)
        fit_camera(sc, [o for o in V.vehicle_objects(r) if o.type == 'MESH'], az=az, el=el, lens=55)
        render(sc, os.path.join(V.RENDER_DIR, 'veh_%s.png' % n))
        r.location = old
    # --- lineup
    order = [roots[n] for n in NAMES if n in roots]
    hide_except(sc, order)
    lineup_positions(order, az=az, gap=1.2)
    studio(sc, az=az)
    allm = [o for r in order for o in V.vehicle_objects(r) if o.type == 'MESH']
    fit_camera(sc, allm, az=az, el=17, lens=50, margin=0.93)
    sc.render.resolution_x, sc.render.resolution_y = (2400, 1000) if not q else (1600, 666)
    render(sc, os.path.join(V.RENDER_DIR, 'vehicles_lineup.png'))
    for n, r in roots.items():
        r.location = saved[n]
    # --- scale vs the mech (appended into this unsaved session only)
    scale_shot(sc, roots, q)


def lineup_only(sc, samples=64):
    setup_render(sc, samples=samples, res=(1200, 500), exposure=0.1)
    order = [bpy.data.objects[n + '_root'] for n in NAMES if bpy.data.objects.get(n + '_root')]
    lineup_positions(order, az=35.0, gap=1.2)
    studio(sc, az=35.0)
    allm = [o for r in order for o in V.vehicle_objects(r) if o.type == 'MESH']
    fit_camera(sc, allm, az=35.0, el=17, lens=50, margin=0.93)
    render(sc, os.path.join(V.RENDER_DIR, 'vehicles_lineup.png'))


def scale_shot(sc, roots, q):
    with bpy.data.libraries.load(V.MECH_BLEND, link=False) as (src, dst):
        dst.collections = ['HeavyMech']
    mc = dst.collections[0]
    sc.collection.children.link(mc)
    hide_except(sc, list(roots.values()))
    lay = {'truck': (8.6, -2.2), 'apc': (-9.0, -1.6), 'jeep': (4.2, -7.6), 'wreck': (-4.6, -7.9)}
    for n, r in roots.items():
        r.location = (*lay.get(n, (0, 0)), 0)
        r['pivot_world'] = list(r.location)
    if 'wreck' in roots:
        roots['wreck'].rotation_euler = (0, 0, math.radians(-28))
    if 'jeep' in roots:
        roots['jeep'].rotation_euler = (0, 0, math.radians(14))
    bpy.context.view_layer.update()
    studio(sc, az=30, size=90)
    objs = [o for r in roots.values() for o in V.vehicle_objects(r) if o.type == 'MESH']
    objs += [o for o in mc.all_objects if o.type == 'MESH']
    fit_camera(sc, objs, az=30, el=14, lens=40, margin=0.92)
    sc.render.resolution_x, sc.render.resolution_y = (2400, 1350) if not q else (1600, 900)
    render(sc, os.path.join(V.RENDER_DIR, 'vehicles_scale_mech.png'))


if __name__ == '__main__':
    main()

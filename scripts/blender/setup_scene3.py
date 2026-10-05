# v3 stage: lights, beauty camera (matches reference-heavy-mech.webp), ortho camera for the sheet views,
# reference image empties. Registers mech_setview / mech_render in bpy.app.driver_namespace.
import bpy, math, os
from mathutils import Vector

ROOT = os.path.expanduser('~/Documents/learning/mech-test')
sc = bpy.context.scene
TUNE = globals().get('TUNE', {})


def tv(k, d):
    return TUNE.get(k, d)


def get_coll(name):
    c = bpy.data.collections.get(name)
    if c is None:
        c = bpy.data.collections.new(name)
        sc.collection.children.link(c)
    for o in list(c.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    return c


coll = get_coll('MechStage')
TARGET = Vector((0, -0.3, 4.6))


def look_at(ob, target):
    d = Vector(target) - ob.location
    ob.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()


def area(name, loc, energy, size, color, target=TARGET):
    ld = bpy.data.lights.new(name, 'AREA')
    ld.energy = energy
    ld.size = size
    ld.color = color
    o = bpy.data.objects.new(name, ld)
    o.location = loc
    coll.objects.link(o)
    look_at(o, target)
    return o


area('Key', (-10, -12, 13), tv('key', 7000), 6, (1.0, 0.93, 0.84))
area('Fill', (12, -10, 4), tv('fill', 2200), 9, (0.78, 0.86, 1.0))
area('RimWarm', tuple(tv('rim_loc', (9, 10, 9))), tv('rim', 9000), 5, tuple(tv('rim_col', (1.0, 0.72, 0.45))))
area('RimWarm2', tuple(tv('rim2_loc', (-11, 8, 6))), tv('rim2', 5000), 5, tuple(tv('rim2_col', (1.0, 0.78, 0.55))))
area('Under', (0, -9, -1.5), tv('under', 600), 8, (0.9, 0.85, 0.8), target=Vector((0, 0, 3)))
kd = bpy.data.lights.new('SunKey', 'SUN')
kd.energy = tv('sunkey', 3.0)
kd.angle = math.radians(4)
kd.color = (1.0, 0.95, 0.88)
sunkey = bpy.data.objects.new('SunKey', kd)
coll.objects.link(sunkey)
sunkey.rotation_euler = (-Vector(tv('sunkey_dir', (-0.55, -0.75, 0.75)))).to_track_quat('-Z', 'Y').to_euler()
sd = bpy.data.lights.new('SunOrtho', 'SUN')
sd.energy = tv('sun', 3.2)
sd.angle = math.radians(8)
sun = bpy.data.objects.new('SunOrtho', sd)
coll.objects.link(sun)


def lights_mode(ortho, view=None):
    for o in coll.objects:
        if o.type == 'LIGHT':
            o.hide_render = (o.name == 'SunOrtho') != ortho
    bg.inputs[0].default_value = (0.32, 0.32, 0.33, 1) if ortho else (0.012, 0.012, 0.013, 1)
    sc.view_settings.exposure = tv('ortho_exposure', -0.2) if ortho else tv('exposure', 0.0)
    if ortho:
        dx, dy = ORTHO[view]
        d = Vector((dx, dy, 0))
        side = Vector((-dy, dx, 0))  # image-left of the camera
        src = d * 1.0 + side * 0.55 + Vector((0, 0, 0.9))
        sun.rotation_euler = (-src).to_track_quat('-Z', 'Y').to_euler()

w = sc.world or bpy.data.worlds.new('World')
sc.world = w
w.use_nodes = True
bg = next(n for n in w.node_tree.nodes if n.type == 'BACKGROUND')
bg.inputs[0].default_value = (0.012, 0.012, 0.013, 1)
bg.inputs[1].default_value = 1.0

# beauty camera
cd = bpy.data.cameras.new('MechCam')
cd.lens = tv('lens', 40)
cam = bpy.data.objects.new('MechCam', cd)
coll.objects.link(cam)
# ortho camera
od = bpy.data.cameras.new('OrthoCam')
od.type = 'ORTHO'
od.ortho_scale = 12.5
ocam = bpy.data.objects.new('OrthoCam', od)
coll.objects.link(ocam)
sc.camera = cam

ORTHO = {'front': (0, -1), 'back': (0, 1), 'sideR': (1, 0), 'sideL': (-1, 0)}


LIGHT_KEYS = {'Key': ('key', 7000), 'Fill': ('fill', 2200), 'RimWarm': ('rim', 9000), 'RimWarm2': ('rim2', 5000),
              'Under': ('under', 600), 'SunKey': ('sunkey', 3.0)}


def apply_tune():
    for nm, (k, d) in LIGHT_KEYS.items():
        o = bpy.data.objects.get(nm)
        if o:
            o.data.energy = tv(k, d)
    for nm, k in (('RimWarm', 'rim_col'), ('RimWarm2', 'rim2_col'), ('Key', 'key_col')):
        o = bpy.data.objects.get(nm)
        if o and k in TUNE:
            o.data.color = tuple(TUNE[k])
    sunkey.rotation_euler = (-Vector(tv('sunkey_dir', (-0.55, -0.75, 0.75)))).to_track_quat('-Z', 'Y').to_euler()
    try:
        sc.view_settings.look = tv('look', 'AgX - Medium High Contrast')
    except Exception as e:
        print('look', e)


def set_beauty():
    apply_tune()
    az = math.radians(tv('az', -38.0))  # angle from -Y toward -X
    dist = tv('dist', 26.0)
    v = Vector((math.sin(az), -math.cos(az), 0))
    t = Vector(tv('target', (0, -0.3, 4.6)))
    cam.location = t + v * dist
    cam.location.z = tv('cam_h', 1.6)
    cd.lens = tv('lens', 40)
    look_at(cam, t)
    sc.camera = cam
    lights_mode(False)
    r = sc.render
    r.resolution_x, r.resolution_y = 1375, 1144
    r.film_transparent = False


def set_ortho(name):
    dx, dy = ORTHO[name]
    ocam.location = Vector((dx * 40, dy * 40, 4.5))
    look_at(ocam, Vector((0, 0, 4.5)))
    sc.camera = ocam
    lights_mode(True, name)
    r = sc.render
    r.resolution_x = r.resolution_y = 1000
    r.film_transparent = True


def mech_setview(name):
    if name in ORTHO:
        set_ortho(name)
    else:
        set_beauty()


def mech_render(name, path, samples=None):
    mech_setview(name)
    if samples:
        try:
            sc.eevee.taa_render_samples = samples
        except Exception:
            pass
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)


bpy.app.driver_namespace['mech_setview'] = mech_setview
bpy.app.driver_namespace['mech_render'] = mech_render

# render settings
try:
    sc.render.engine = 'BLENDER_EEVEE'
except TypeError as e:
    print('engine', e)
r = sc.render
r.resolution_percentage = 100
r.image_settings.file_format = 'PNG'
r.image_settings.color_mode = 'RGBA'
ee = sc.eevee
for attr, val in (('taa_render_samples', 48), ('use_raytracing', True), ('use_shadows', True),
                  ('shadow_ray_count', 2), ('shadow_step_count', 8), ('use_gtao', True)):
    if hasattr(ee, attr):
        try:
            setattr(ee, attr, val)
        except Exception as e:
            print('skip', attr, e)
try:
    sc.view_settings.view_transform = 'AgX'
    sc.view_settings.look = tv('look', 'AgX - Medium High Contrast')
except Exception as e:
    print('look', e)

# reference image empties (front + cannon side crops from the sheet)
rc = get_coll('MechRef')
H = 9.0
for nm, f, loc, rot_deg, xoff in (('REF_front', 'ref_front.png', (0.065, 6.0, 4.5), (90, 0, 0), 0.0),
                                  ('REF_sideR', 'ref_sideR.png', (-6.0, -1.12, 4.5), (90, 0, 90), 0.0)):
    path = os.path.join(ROOT, 'blender/ref_sheet', f)
    if not os.path.exists(path):
        continue
    img = bpy.data.images.load(path, check_existing=True)
    w_, h_ = img.size
    e = bpy.data.objects.new(nm, None)
    e.empty_display_type = 'IMAGE'
    e.data = img
    e.empty_display_size = H * max(w_, h_) / h_
    e.empty_image_offset = (-0.5, -0.5)
    e.location = loc
    e.rotation_euler = [math.radians(a) for a in rot_deg]
    e.hide_render = True
    try:
        e.empty_image_side = 'FRONT'
        e.color[3] = 0.5
        e.use_empty_image_alpha = True
    except Exception:
        pass
    rc.objects.link(e)
set_beauty()

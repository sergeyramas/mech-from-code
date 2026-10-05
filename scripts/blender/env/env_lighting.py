# Environment kit - world (Sky Texture + procedural overcast), sun, haze volume, smoke column, cameras, render.
import bpy, math
from mathutils import Vector
from env_common import nn, o, mth, mix, ramp, sstep, sepxyz, noi, mapv, get_coll

SUN_DIR = Vector((-0.86, -0.42, 0.205)).normalized()   # direction TO the sun (WSW, ~12 deg)


def _set(obj, name, val):
    if hasattr(obj, name):
        try:
            setattr(obj, name, val)
            return True
        except Exception:
            return False
    return False


def build_world(cloud_cover=0.62, strength=1.0):
    w = bpy.data.worlds.get('ENV_world') or bpy.data.worlds.new('ENV_world')
    bpy.context.scene.world = w
    w.use_nodes = True
    nt = w.node_tree
    nt.nodes.clear()
    sky = nn(nt, 'ShaderNodeTexSky')
    types = [i.identifier for i in sky.bl_rna.properties['sky_type'].enum_items]
    for t in ('MULTIPLE_SCATTERING', 'NISHITA', 'SINGLE_SCATTERING'):
        if t in types:
            sky.sky_type = t
            break
    el = math.asin(SUN_DIR.z)
    az = math.atan2(SUN_DIR.x, SUN_DIR.y)      # calibrated in test: rotation measured from +Y towards +X
    _set(sky, 'sun_elevation', el)
    _set(sky, 'sun_rotation', az % (2 * math.pi))
    _set(sky, 'sun_disc', False)
    _set(sky, 'altitude', 50.0)
    _set(sky, 'air_density', 1.3)
    for nm in ('aerosol_density', 'dust_density'):
        _set(sky, nm, 3.5)
    _set(sky, 'ozone_density', 1.0)
    skyc = o(sky, 'Color')
    skyc = mix(nt, 1.0, skyc, (0.22, 0.22, 0.24), 'MULTIPLY')

    # view direction
    tc = nn(nt, 'ShaderNodeTexCoord')
    d = o(tc, 'Generated')
    dx, dy, dz = sepxyz(nt, d)
    dzc = mth(nt, 'MAXIMUM', dz, 0.035)
    px = mth(nt, 'DIVIDE', dx, dzc)
    py = mth(nt, 'DIVIDE', dy, dzc)
    pv = o(nn(nt, 'ShaderNodeCombineXYZ', {'X': px, 'Y': py, 'Z': 0.0}), 'Vector')
    n1 = noi(nt, mapv(nt, pv, (1.0, 1.6, 1.0)), 0.55, 8, 0.62, 0.35)
    n2 = noi(nt, pv, 2.4, 6, 0.6)
    nc = mth(nt, 'ADD', n1, mth(nt, 'MULTIPLY', mth(nt, 'SUBTRACT', n2, 0.5), 0.35))
    lo = 0.62 - cloud_cover * 0.32
    cov = sstep(nt, nc, lo, lo + 0.14)
    # sun facing term
    sd = nn(nt, 'ShaderNodeVectorMath', {0: d, 1: tuple(SUN_DIR)}, operation='DOT_PRODUCT')
    sdot = o(sd, 'Value')
    glow = mth(nt, 'POWER', mth(nt, 'MAXIMUM', sdot, 0.0), 6.0)
    glow2 = mth(nt, 'POWER', mth(nt, 'MAXIMUM', sdot, 0.0), 40.0)
    # cloud colour: dark grey bellies, warm lit edges toward the sun
    thick = sstep(nt, nc, lo + 0.05, lo + 0.45)
    belly = mix(nt, thick, (0.42, 0.42, 0.44), (0.2, 0.2, 0.215))
    warm = mix(nt, mth(nt, 'MULTIPLY', glow, mth(nt, 'SUBTRACT', 1.15, thick)), belly, (1.5, 0.95, 0.55))
    warm = mix(nt, mth(nt, 'MULTIPLY', glow2, 0.8), warm, (4.0, 2.4, 1.2))
    # horizon dust band
    hz = mth(nt, 'SUBTRACT', 1.0, sstep(nt, dz, -0.02, 0.22))
    sky_cl = mix(nt, cov, skyc, warm)
    hcol = mix(nt, glow, (0.46, 0.42, 0.38), (1.1, 0.78, 0.5))
    sky_cl = mix(nt, mth(nt, 'MULTIPLY', hz, 0.85), sky_cl, hcol)
    # below horizon: dusty ground bounce colour
    below = mth(nt, 'LESS_THAN', dz, -0.02)
    sky_cl = mix(nt, below, sky_cl, (0.16, 0.14, 0.12))
    bg = nn(nt, 'ShaderNodeBackground', {'Color': sky_cl, 'Strength': strength})
    out = nn(nt, 'ShaderNodeOutputWorld')
    nt.links.new(o(bg, 'Background'), out.inputs['Surface'])
    return w


def build_sun(coll, strength=4.2, color=(1.0, 0.7, 0.44), angle=1.2):
    ob = bpy.data.objects.get('ENV_sun')
    if ob:
        bpy.data.objects.remove(ob, do_unlink=True)
    ld = bpy.data.lights.new('ENV_sun', 'SUN')
    ld.energy = strength
    ld.color = color
    ld.angle = math.radians(angle)
    ob = bpy.data.objects.new('ENV_sun', ld)
    ob.rotation_euler = (-SUN_DIR).to_track_quat('-Z', 'Y').to_euler()
    ob.location = SUN_DIR * 60
    coll.objects.link(ob)
    return ob


def box_obj(name, coll, mn, mx, mat, origin=None):
    """axis aligned box with applied transforms; origin defaults to the box centre"""
    c = Vector([(a + b) / 2 for a, b in zip(mn, mx)]) if origin is None else Vector(origin)
    vs = [(x - c.x, y - c.y, z - c.z) for x in (mn[0], mx[0]) for y in (mn[1], mx[1]) for z in (mn[2], mx[2])]
    fs = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
    old = bpy.data.objects.get(name)
    if old:
        bpy.data.objects.remove(old, do_unlink=True)
    me = bpy.data.meshes.new(name)
    me.from_pydata(vs, [], fs)
    me.materials.append(mat)
    me.update()
    ob = bpy.data.objects.new(name, me)
    ob.location = c
    coll.objects.link(ob)
    return ob


def build_haze(coll, mats):
    ob = box_obj('ENV_haze_volume', coll, (-380, -380, -10), (380, 380, 110), mats['ENV_haze'])
    ob.display_type = 'BOUNDS'
    ob.visible_shadow = False
    return ob


def build_smoke(coll, mats, base=(46.0, 118.0, 0.0), H=120.0):
    # material works in object space with origin at the plume base; plume drifts to -x
    ob = box_obj('ENV_smoke_column', coll, (base[0] - 58, base[1] - 30, base[2] - 2),
                 (base[0] + 20, base[1] + 22, base[2] + H), mats['ENV_smoke'], origin=base)
    ob.display_type = 'BOUNDS'
    return ob


def look_at(ob, target):
    d = Vector(target) - ob.location
    ob.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()


def camera(name, coll, loc, target, lens=28.0, ortho=None, shift=(0, 0)):
    ob = bpy.data.objects.get(name)
    if ob:
        bpy.data.objects.remove(ob, do_unlink=True)
    cd = bpy.data.cameras.new(name)
    cd.lens = lens
    cd.clip_start = 0.1
    cd.clip_end = 2000.0
    cd.sensor_width = 36.0
    cd.shift_x, cd.shift_y = shift
    if ortho:
        cd.type = 'ORTHO'
        cd.ortho_scale = ortho
    ob = bpy.data.objects.new(name, cd)
    ob.location = loc
    coll.objects.link(ob)
    look_at(ob, target)
    return ob


CAMS = {
    'wide': dict(loc=(-27.0, -64.0, 13.5), target=(6.0, 6.0, 3.0), lens=26.0),
    'hero': dict(loc=(10.5, -15.5, 1.15), target=(-0.5, 0.0, 5.2), lens=21.0, shift=(-0.05, 0.08)),
    'top': dict(loc=(4.0, -2.0, 220.0), target=(4.0, -2.0, 0.0), lens=50.0, ortho=118.0),
}


def build_cameras(coll):
    out = {}
    for k, c in CAMS.items():
        out[k] = camera('CAM_' + k, coll, c['loc'], c['target'], c.get('lens', 28), c.get('ortho'),
                        c.get('shift', (0, 0)))
    bpy.context.scene.camera = out['wide']
    return out


def render_settings(samples=160, res=(1920, 1080), time_limit=170.0):
    sc = bpy.context.scene
    sc.render.engine = 'CYCLES'
    try:
        prefs = bpy.context.preferences.addons['cycles'].preferences
        prefs.compute_device_type = 'METAL'
        prefs.get_devices()
        for d in prefs.devices:
            d.use = True
        sc.cycles.device = 'GPU'
    except Exception as e:
        print('GPU setup failed', e)
    cy = sc.cycles
    cy.samples = samples
    cy.use_adaptive_sampling = True
    cy.adaptive_threshold = 0.02
    cy.adaptive_min_samples = 16
    cy.use_denoising = True
    try:
        cy.denoiser = 'OPENIMAGEDENOISE'
    except Exception:
        pass
    _set(cy, 'denoising_input_passes', 'RGB_ALBEDO_NORMAL')
    _set(cy, 'use_light_tree', True)
    cy.max_bounces = 6
    cy.diffuse_bounces = 3
    cy.glossy_bounces = 3
    cy.transmission_bounces = 4
    cy.volume_bounces = 1
    cy.transparent_max_bounces = 8
    _set(cy, 'caustics_reflective', False)
    _set(cy, 'caustics_refractive', False)
    _set(cy, 'blur_glossy', 1.0)
    _set(cy, 'sample_clamp_indirect', 6.0)
    _set(cy, 'volume_biased', True)          # ray-marched; unbiased null-scattering is far too slow here
    _set(cy, 'volume_step_rate', 4.0)
    _set(cy, 'volume_max_steps', 256)
    _set(cy, 'time_limit', time_limit)
    sc.render.use_persistent_data = True
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.resolution_percentage = 100
    sc.render.film_transparent = False
    sc.render.image_settings.file_format = 'PNG'
    sc.render.image_settings.color_depth = '8'
    vs = sc.view_settings
    try:
        sc.display_settings.display_device = 'sRGB'
    except Exception:
        pass
    for vt in ('AgX', 'Filmic'):
        try:
            vs.view_transform = vt
            break
        except Exception:
            pass
    for lk in ('AgX - Medium High Contrast', 'AgX - Base Contrast', 'Medium High Contrast'):
        try:
            vs.look = lk
            break
        except Exception:
            pass
    vs.exposure = 0.0
    vs.gamma = 1.0

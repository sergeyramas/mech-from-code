# Render environment shots.
#   Blender -b environment.blend --python scripts/env/render_env.py -- wide hero top [--pct 50] [--samples 128]
#        [--suffix _it1] [--noplace] [--limit 170]
import bpy, sys, os, time, json

ROOT = os.path.expanduser('~/Documents/learning/mech-test/blender')
ARGS = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []


def opt(name, default, cast=str):
    if name in ARGS:
        return cast(ARGS[ARGS.index(name) + 1])
    return default


PCT = opt('--pct', 100, int)
SAMPLES = opt('--samples', 0, int)
SUFFIX = opt('--suffix', '')
LIMIT = opt('--limit', 0.0, float)
SHOTS = [a for a in ARGS if a in ('wide', 'hero', 'top') or a.startswith('dbg:')] or ['wide', 'hero', 'top']
sc = bpy.context.scene


def gpu():
    try:
        prefs = bpy.context.preferences.addons['cycles'].preferences
        prefs.compute_device_type = 'METAL'
        prefs.get_devices()
        for d in prefs.devices:
            d.use = d.type != 'CPU' or len([x for x in prefs.devices if x.type != 'CPU']) == 0
        sc.cycles.device = 'GPU'
        print('devices', [(d.name, d.type, d.use) for d in prefs.devices])
    except Exception as e:
        print('gpu fail', e)


def set_vis(name, render):
    ob = bpy.data.objects.get(name)
    if ob:
        ob.hide_render = not render


def coll_vis(name, render):
    c = bpy.data.collections.get(name)
    if c:
        c.hide_render = not render


def dbg_cam(spec):
    from mathutils import Vector
    _, name, p, t, lens = spec.split(':')
    p = Vector([float(v) for v in p.split(',')])
    t = Vector([float(v) for v in t.split(',')])
    cd = bpy.data.cameras.new('dbg')
    cd.lens = float(lens)
    cd.clip_end = 2000
    ob = bpy.data.objects.new('CAM_dbg_' + name, cd)
    sc.collection.objects.link(ob)
    ob.location = p
    ob.rotation_euler = (t - p).to_track_quat('-Z', 'Y').to_euler()
    return ob


def setup(shot):
    top = shot == 'top'
    if shot.startswith('dbg:'):
        sc.camera = dbg_cam(shot)
        shot = 'wide'
    else:
        sc.camera = bpy.data.objects['CAM_' + shot]
    set_vis('ENV_haze_volume', not top and '--nohaze' not in ARGS)
    set_vis('ENV_smoke_column', not top and '--nosmoke' not in ARGS)
    coll_vis('ENV_placeholders', top or '--noplace' not in ARGS)
    coll_vis('ENV_backdrop', not top)
    sun = bpy.data.objects.get('ENV_sun')
    if sun is not None:
        if top:
            sun['_rot'] = list(sun.rotation_euler)
            sun.rotation_euler = (0.35, 0.15, 0.6)
            sun.data.energy = 3.0
            sun.data.color = (1.0, 0.93, 0.85)
        elif '_rot' in sun.keys():
            sun.rotation_euler = sun['_rot']
    vs = sc.view_settings
    vs.exposure = {'wide': 0.0, 'hero': 0.0, 'top': 0.0}[shot] + opt('--exp', 0.0, float)


def main():
    gpu()
    sc.render.resolution_percentage = PCT
    if SAMPLES:
        sc.cycles.samples = SAMPLES
    if LIMIT:
        sc.cycles.time_limit = LIMIT
    log = []
    for shot in SHOTS:
        setup(shot)
        nm = shot.split(':')[1] if shot.startswith('dbg:') else shot
        sub = 'dbg/' if shot.startswith('dbg:') else ''
        out = os.path.join(ROOT, 'renders', sub + 'env_%s%s.png' % (nm if nm != 'hero' else 'mech_hero', SUFFIX))
        sc.render.filepath = out
        t = time.time()
        bpy.ops.render.render(write_still=True)
        dt = time.time() - t
        print('[RENDER] %s %.1fs -> %s' % (shot, dt, out), flush=True)
        log.append({'shot': shot, 'seconds': round(dt, 1), 'pct': PCT, 'samples': sc.cycles.samples, 'file': out})
    lp = os.path.join(ROOT, 'renders', 'env_render_log.jsonl')
    with open(lp, 'a') as f:
        for r in log:
            f.write(json.dumps(r) + '\n')


main()

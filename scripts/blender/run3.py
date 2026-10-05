# Headless driver: blender -b --factory-startup --python run3.py -- OUTDIR VIEWS [SAVE.blend] [TUNE.json]
# VIEWS: comma list of front,back,sideL,sideR,beauty ; '-' = none
import bpy, sys, json, os, time
argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
out = argv[0]
views = [] if argv[1] == '-' else argv[1].split(',')
save = argv[2] if len(argv) > 2 and argv[2] != '-' else None
tune = json.load(open(argv[3])) if len(argv) > 3 else {}
S = os.path.expanduser('~/Documents/learning/mech-test/blender/scripts/')
os.makedirs(out, exist_ok=True)
# clean factory scene
for o in list(bpy.data.objects):
    bpy.data.objects.remove(o, do_unlink=True)
t0 = time.time()
g = {'__name__': '__main__', 'TUNE': tune}
exec(open(S + 'build_mech3.py').read(), g)
print('build %.1fs' % (time.time() - t0))
g2 = {'__name__': '__main__', 'TUNE': tune}
exec(open(S + 'setup_scene3.py').read(), g2)
if tune.get('post'):
    exec(open(tune['post']).read(), {'__name__': '__main__', 'TUNE': tune})
for v in views:
    t1 = time.time()
    samples = tune.get('beauty_samples', 64) if v == 'beauty' else tune.get('ortho_samples', 16)
    g2['mech_render'](v, os.path.join(out, v + '.png'), samples)
    print('render', v, '%.1fs' % (time.time() - t1))
for k, prm in enumerate(tune.get('cam_trials', [])):
    tune.update(prm)
    bpy.context.scene.view_settings.exposure = tune.get('exposure', 0.0)
    g2['mech_render']('beauty', os.path.join(out, 'beauty_%d.png' % k), 32)
    print('trial', k, prm)
if save:
    bpy.ops.wm.save_as_mainfile(filepath=save)
    print('saved', save)

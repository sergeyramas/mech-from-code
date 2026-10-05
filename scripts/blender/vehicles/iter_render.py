# Iteration driver: build the listed vehicles in a fresh session and render quick 3/4 views.
# Blender -b --factory-startup --python iter_render.py -- <names,comma> <out_prefix> [samples] [WxH] [views]
#   views: "az:el:lens;az:el:lens"  (az=35 front-left 3/4, 145 = rear-left, el high = game camera)
import bpy, sys, os, time, importlib
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import veh_lib as V
import render_vehicles as RV

argv = sys.argv[sys.argv.index('--') + 1:]
names = argv[0].split(',')
out = argv[1]
samples = int(argv[2]) if len(argv) > 2 else 64
w, h = (int(x) for x in (argv[3] if len(argv) > 3 else '1280x720').split('x'))
views = [tuple(float(x) for x in v.split(':')) for v in (argv[4] if len(argv) > 4 else '35:20:50').split(';')]
for o in list(bpy.data.objects):
    bpy.data.objects.remove(o, do_unlink=True)
t0 = time.time()
V.build_materials(ao_samples=6)
roots = []
for n in names:
    mod = importlib.import_module('build_' + n)
    coll, root = mod.build()
    roots.append(root)
    objs = V.vehicle_objects(root)
    tc = V.tri_count(objs)
    print('TRIS %s %d' % (n, tc))
    for o in sorted(objs, key=lambda o: -V.tri_count([o]))[:8]:
        print('   %-28s %6d' % (o.name, V.tri_count([o])))
print('build %.1fs' % (time.time() - t0))
if len(roots) > 1:
    RV.lineup_positions(roots, az=views[0][0])
sc = bpy.context.scene
RV.setup_render(sc, samples=samples, res=(w, h), exposure=float(os.environ.get('EXPO', '0.2')))
meshes = [o for r in roots for o in V.vehicle_objects(r) if o.type == 'MESH']
for k, (az, el, lens) in enumerate(views):
    RV.studio(sc, az=az)
    RV.fit_camera(sc, meshes, az=az, el=el, lens=lens)
    RV.render(sc, '%s_v%d.png' % (out, k))

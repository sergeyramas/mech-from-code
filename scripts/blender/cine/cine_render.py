"""cine_render.py -- render cinematic/mech_cinematic.blend (read-only use; never saved).

Blender -b cinematic/mech_cinematic.blend --python scripts/cine/cine_render.py -- \
    [--pct 50] [--samples 8] [--frames 1,20,300 | --range 1-1033] [--step N] [--out DIR] [--tile 8] [--stills]
"""
import bpy, sys, os, json, time

ROOT = os.path.expanduser('~/Documents/learning/mech-test/blender')
A = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []


def arg(k, d=None):
    return A[A.index(k) + 1] if k in A else d


sc = bpy.context.scene
pct = int(arg('--pct', 100))
sc.render.resolution_percentage = pct
sc.eevee.taa_render_samples = int(arg('--samples', 16))
sc.eevee.volumetric_tile_size = arg('--tile', '8')
out = arg('--out', os.path.join(ROOT, 'renders/cine/frames'))
os.makedirs(out, exist_ok=True)
step = int(arg('--step', 1))
ev = json.load(open(os.path.join(ROOT, 'renders/cine/events.json')))
if '--stills' in A:
    frames = []
    names = []
    for s in ev['shots']:
        f = (s['frame_start'] + s['frame_end']) // 2
        frames.append(f)
        names.append(s['name'])
elif arg('--frames'):
    frames = [int(x) for x in arg('--frames').split(',')]
    names = None
else:
    a, b = (int(x) for x in arg('--range', f'{sc.frame_start}-{sc.frame_end}').split('-'))
    frames = list(range(a, b + 1, step))
    names = None
skip = '--skip-existing' in A
t0 = time.time()
for i, f in enumerate(frames):
    fn = os.path.join(out, (f'{names[i]}_f{f:04d}' if names else f'f_{f:04d}') + '.png')
    if skip and os.path.exists(fn):
        continue
    sc.frame_set(f)
    sc.render.filepath = fn
    t1 = time.time()
    bpy.ops.render.render(write_still=True)
    print(f'[render] frame {f} ({i + 1}/{len(frames)}) {time.time() - t1:.1f}s total {time.time() - t0:.0f}s',
          flush=True)
print(f'[render] done {len(frames)} frames in {time.time() - t0:.0f}s', flush=True)

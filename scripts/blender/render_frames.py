"""Render selected frames:  Blender -b anim.blend --python render_frames.py -- OUTDIR f1 f2 ... [--samples N]"""
import bpy, sys, os
a = sys.argv[sys.argv.index('--') + 1:]
out = a[0]
samples = None
fr = []
i = 1
while i < len(a):
    if a[i] == '--samples':
        samples = int(a[i + 1]); i += 2
    else:
        fr.append(int(a[i])); i += 1
os.makedirs(out, exist_ok=True)
sc = bpy.context.scene
if samples:
    sc.eevee.taa_render_samples = samples
for f in fr:
    sc.frame_set(f)
    sc.render.filepath = os.path.join(out, 'fr_%04d.png' % f)
    bpy.ops.render.render(write_still=True)

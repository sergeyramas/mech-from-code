import bpy, sys, os, time, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fx_lib as F, cine_nuke as N
from mathutils import Vector
OUT = os.path.expanduser('~/Documents/learning/mech-test/blender/renders/cine/test/')
sc = bpy.context.scene
sc.render.engine = 'BLENDER_EEVEE'
e = sc.eevee; e.taa_render_samples = 12; e.volumetric_tile_size = '8'; e.volumetric_samples = 48
e.volumetric_end = 800; e.use_volumetric_shadows = True; e.use_raytracing = True
sc.render.resolution_x, sc.render.resolution_y = 800, 450
for o in bpy.data.objects:
    if o.name.startswith('ENV_haze'): o.hide_render = True
c = F.coll('CINE_test')
fps = 24
rk, fl, hz, lt = N.build_rocket(c)
rk.location = (0, -20, 3.0)
fl['flick'] = 3.0; hz['flick'] = 3.0
cam_d = bpy.data.cameras.new('tc'); cam_d.lens = 35
cam = bpy.data.objects.new('TCAM', cam_d); c.objects.link(cam)
def look(cam, pos, tgt):
    cam.location = pos
    d = Vector(tgt) - Vector(pos)
    cam.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
sc.camera = cam
for nm, pos in (('rkt_side', (-0.2, -16.0, 3.3)), ('rkt_3q', (2.5, -17.0, 3.8)), ('rkt_tail', (-5.0, -18.3, 3.4))):
    look(cam, pos, (-0.3 if nm != 'rkt_tail' else -1.5, -20, 3.0))
    sc.frame_set(1)
    sc.render.filepath = OUT + nm + '.png'; t = time.time(); bpy.ops.render.render(write_still=True); print('TIME', nm, time.time() - t)
rk.hide_render = True; fl.hide_render = True; hz.hide_render = True; lt.hide_render = True
E = Vector((6, 32, 0))
N.nuke(E, 100, fps, c, 100 + 6 * fps, ground_z=0.0)
look(cam, (70, -150, 30), (6, 32, 45)); cam_d.lens = 28
for tt in (0.05, 0.5, 1.5, 3.0, 5.0):
    sc.frame_set(100 + int(tt * fps))
    sc.render.filepath = OUT + f'nuke_{tt}.png'; t = time.time(); bpy.ops.render.render(write_still=True); print('TIME', tt, time.time() - t)

import bpy, sys, os, math, time
sys.path.insert(0, os.path.dirname(__file__))
import fx_lib as F
from mathutils import Vector
ROOT = os.path.expanduser('~/Documents/learning/mech-test/blender')
OUT = os.path.join(ROOT, 'renders/cine/test')
argv = sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else []
frames = [int(a) for a in argv] or [13, 20, 34, 70, 130]
sc = bpy.context.scene
for o in list(bpy.data.objects): bpy.data.objects.remove(o)
sc.render.engine = 'BLENDER_EEVEE'
ee = sc.eevee
ee.taa_render_samples = 24
ee.volumetric_tile_size = '4'
ee.volumetric_samples = 96
ee.volumetric_end = 250
ee.use_volumetric_shadows = True
ee.volumetric_shadow_samples = 12
ee.use_raytracing = True
sc.render.resolution_x, sc.render.resolution_y = 960, 540
try: sc.view_settings.view_transform = 'AgX'
except Exception as e: print(e)
w = bpy.data.worlds.new('W'); sc.world = w; w.use_nodes = True
bg = next(n for n in w.node_tree.nodes if n.type=='BACKGROUND'); bg.inputs[0].default_value=(0.35,0.33,0.3,1); bg.inputs[1].default_value=1.0
bpy.ops.mesh.primitive_plane_add(size=300); g=bpy.context.object
m=bpy.data.materials.new('g'); m.use_nodes=True; m.node_tree.nodes['Principled BSDF'].inputs[0].default_value=(0.2,0.17,0.13,1); g.data.materials.append(m)
bpy.ops.object.light_add(type='SUN', rotation=(math.radians(50),0,math.radians(30))); bpy.context.object.data.energy=4
# a box (truck stand-in)
bpy.ops.mesh.primitive_cube_add(size=2, location=(0,0,1.2)); bpy.context.object.scale=(4,1.3,1.2)
cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam')); sc.collection.objects.link(cam); sc.camera=cam
cam.location=(0,-38,5); cam.rotation_euler=(math.radians(84),0,0); cam.data.lens=30
C = F.coll('FX')
t0=time.time()
F.explosion('EXA', (0,0,0.5), 10, 24, C, size=4.0, ground_z=0.0)
F.burst('EXA_sp', (0,0,1.5), 10, 24, C, kind='spark', count=300, seed=2, ground_z=0)
F.burst('EXA_db', (0,0,1.5), 10, 24, C, kind='debris', count=120, seed=3, size=0.25, speed=(6,22), life=(8,9), ground_z=0, drag=0.4)
pts,b = F.column_points((6,3,2), 0.0, 6.0, rate=8)
F.trail('EXA_col', pts, b, C, 10, 24, 6.0, life=5.0, r0=0.5, grow=1.2, rise=2.5)
# a flying-piece trail
import random
pp=[];bb=[]
for i in range(60):
    t=i/24*0.5; pp.append(Vector((-2-12*t, 0, 2+14*t-4.9*t*t))); bb.append(t)
F.trail('EXA_tr', pp, bb, C, 10, 24, 6.0, life=3.0, r0=0.2, grow=0.6, rise=0.5)
print('build', time.time()-t0)
for f in frames:
    sc.frame_set(f); sc.render.filepath=os.path.join(OUT, f'fx_{f:03d}.png')
    t1=time.time(); bpy.ops.render.render(write_still=True); print('RENDER', f, round(time.time()-t1,1),'s')
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(ROOT,'cinematic/test_fx.blend'))

import bpy, sys, os, math, time, random
sys.path.insert(0, os.path.dirname(__file__))
import fx_lib as F
import numpy as np
from mathutils import Vector
ROOT = os.path.expanduser('~/Documents/learning/mech-test/blender')
OUT = os.path.join(ROOT, 'renders/cine/test')
sc = bpy.context.scene
for o in list(bpy.data.objects): bpy.data.objects.remove(o)
sc.render.engine = 'BLENDER_EEVEE'; sc.eevee.taa_render_samples = 16
sc.render.resolution_x, sc.render.resolution_y = 960, 540
w = bpy.data.worlds.new('W'); sc.world = w; w.use_nodes = True
bg = next(n for n in w.node_tree.nodes if n.type=='BACKGROUND'); bg.inputs[0].default_value=(0.35,0.33,0.3,1)
bpy.ops.mesh.primitive_plane_add(size=300); g=bpy.context.object
bpy.ops.object.light_add(type='SUN', rotation=(math.radians(50),0,math.radians(30))); bpy.context.object.data.energy=4
bpy.ops.mesh.primitive_cube_add(size=1, location=(0,0,2.5)); wall=bpy.context.object; wall.scale=(8,0.5,5)
m=bpy.data.materials.new('plaster'); m.use_nodes=True; m.node_tree.nodes['Principled BSDF'].inputs[0].default_value=(0.6,0.55,0.5,1); wall.data.materials.append(m)
t0=time.time()
C=F.coll('FRAC')
pcs=F.fracture(wall, 90, seed=1, cap_mat=F.concrete_cap_material(), bias_point=(0,0,2), bias=2.0)
print('fracture', len(pcs), round(time.time()-t0,2),'s')
bpy.data.objects.remove(wall)
for p in pcs: C.objects.link(p)
fps=24; OS=4; f0=20
S=F.RigidSim(fps=fps, oversample=OS)
S.add(g, passive=True, shape='BOX' if False else 'MESH')
imp=Vector((0,-1.0,2.0))
rnd=random.Random(2)
for p in pcs:
    vol=max(1e-3, p.dimensions.x*p.dimensions.y*p.dimensions.z)
    S.add(p, mass=vol*2000)
    d=(p.location-imp); r=d.length
    v=d.normalized()*(14*math.exp(-r/3.0))+Vector((0,0,3*math.exp(-r/4)))
    S.add  # noqa
    S.launch(p, v, Vector((rnd.uniform(-1,1) for _ in range(3)))*6*math.exp(-r/3), f0*OS)
t0=time.time()
rec,times=S.run(f0*OS, 3*fps*OS)
print('sim', round(time.time()-t0,1),'s')
# check launch velocity of first piece
j=0; p=S.bodies[j]
exp_v=S.vel[p.name][0]
dv=(rec[j,8,:3,3]-rec[j,4,:3,3])/(4/(fps*OS))
print('LAUNCH expected', tuple(round(x,2) for x in exp_v), 'measured', np.round(dv,2))
minz=min(float(np.min(rec[:,:,2,3])) for _ in [0]); print('min centre z', minz)
S.teardown()
F.bake_records(S.bodies, rec, times, f0, fps, step=1)
cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam')); sc.collection.objects.link(cam); sc.camera=cam
cam.location=(10,-22,4); cam.rotation_euler=(math.radians(84),0,math.radians(25)); cam.data.lens=30
for f in (19,22,26,34,60,90):
    sc.frame_set(f); sc.render.filepath=os.path.join(OUT, f'fr_{f:03d}.png'); bpy.ops.render.render(write_still=True)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(ROOT,'cinematic/test_frac.blend'))

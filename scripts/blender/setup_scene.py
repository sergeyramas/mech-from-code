import bpy, math
from mathutils import Vector

sc = bpy.context.scene
COLL = 'MechStage'
coll = bpy.data.collections.get(COLL)
if coll:
    for o in list(coll.objects):
        bpy.data.objects.remove(o, do_unlink=True)
else:
    coll = bpy.data.collections.new(COLL)
    sc.collection.children.link(coll)
for n in ('Light', 'Camera'):
    o = bpy.data.objects.get(n)
    if o and o.users_collection and o.users_collection[0] == sc.collection:
        bpy.data.objects.remove(o, do_unlink=True)

TARGET = Vector((0, -0.7, 4.4))


def look_at(ob, target):
    d = Vector(target) - ob.location
    ob.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()


def area(name, loc, energy, size, color=(1, 1, 1)):
    ld = bpy.data.lights.new(name, 'AREA')
    ld.energy = energy
    ld.size = size
    ld.color = color
    o = bpy.data.objects.new(name, ld)
    o.location = loc
    coll.objects.link(o)
    look_at(o, TARGET)
    return o


area('Key', (-9, -11, 12), 6000, 7, (1.0, 0.93, 0.85))
area('Fill', (12, -8, 5), 2500, 9, (0.8, 0.88, 1.0))
area('Rim', (4, 12, 10), 7000, 6, (0.9, 0.95, 1.0))
area('Rim2', (-10, 9, 6), 3000, 6, (1.0, 0.9, 0.8))

# floor (neutral concrete)
bpy.ops.mesh.primitive_circle_add(vertices=64, radius=40, fill_type='NGON', location=(0, 0, 0))
fl = bpy.context.active_object
fl.name = 'Floor'
for c in fl.users_collection:
    c.objects.unlink(fl)
coll.objects.link(fl)
m = bpy.data.materials.get('STAGE_floor') or bpy.data.materials.new('STAGE_floor')
m.use_nodes = True
nt = m.node_tree
nt.nodes.clear()
out = nt.nodes.new('ShaderNodeOutputMaterial')
b = nt.nodes.new('ShaderNodeBsdfPrincipled')
nt.links.new(b.outputs[0], out.inputs[0])
nz = nt.nodes.new('ShaderNodeTexNoise')
next(s for s in nz.inputs if s.identifier == 'Scale').default_value = 0.6
rp = nt.nodes.new('ShaderNodeValToRGB')
rp.color_ramp.elements[0].color = (0.03, 0.03, 0.03, 1)
rp.color_ramp.elements[1].color = (0.06, 0.058, 0.056, 1)
nt.links.new(nz.outputs[0], rp.inputs[0])
nt.links.new(rp.outputs[0], next(s for s in b.inputs if s.identifier == 'Base Color'))
next(s for s in b.inputs if s.identifier == 'Roughness').default_value = 0.85
fl.data.materials.append(m)

# world: soft neutral studio colour
w = sc.world or bpy.data.worlds.new('World')
sc.world = w
w.use_nodes = True
bg = next(n for n in w.node_tree.nodes if n.type == 'BACKGROUND')
bg.inputs[0].default_value = (0.055, 0.06, 0.068, 1)
bg.inputs[1].default_value = 1.0

# camera
cd = bpy.data.cameras.new('MechCam')
cd.lens = 50
cam = bpy.data.objects.new('MechCam', cd)
coll.objects.link(cam)
sc.camera = cam

VIEWS = {
    'front': (0, -1),
    'three_quarter': (-0.62, -0.78),
    'side': (-1, 0),
    'back': (0.25, 1),
}


def set_view(name, dist=27.0, height=3.2):
    dx, dy = VIEWS[name]
    v = Vector((dx, dy, 0)).normalized()
    cam.location = TARGET + v * dist
    cam.location.z = height
    look_at(cam, TARGET + Vector((0, 0, 0.0)))


set_view('three_quarter')

# render settings
r = sc.render
r.resolution_x, r.resolution_y, r.resolution_percentage = 1600, 1200, 100
r.image_settings.file_format = 'PNG'
ee = sc.eevee
for attr, val in (('taa_render_samples', 64), ('use_raytracing', True), ('use_shadows', True),
                  ('shadow_ray_count', 2), ('shadow_step_count', 8)):
    if hasattr(ee, attr):
        try:
            setattr(ee, attr, val)
        except Exception as e:
            print('skip', attr, e)
try:
    sc.view_settings.view_transform = 'AgX'
    sc.view_settings.look = 'AgX - Medium High Contrast'
except Exception as e:
    print('look', e)

import bpy, bmesh, os
from mathutils import Vector
OUTDIR = os.path.expanduser('~/Documents/learning/mech-test/blender/')
coll = bpy.data.collections['HeavyMech']
# simple box-projection UVs (for Unity texturing / lightmaps later)
for o in coll.objects:
    if o.type != 'MESH':
        continue
    me = o.data
    bm = bmesh.new(); bm.from_mesh(me)
    uvl = bm.loops.layers.uv.verify()
    for f in bm.faces:
        n = f.normal; a = max(range(3), key=lambda i: abs(n[i]))
        u, v = [i for i in range(3) if i != a]
        for l in f.loops:
            l[uvl].uv = (l.vert.co[u] * 0.5, l.vert.co[v] * 0.5)
    bm.to_mesh(me); bm.free()
bpy.ops.wm.save_as_mainfile(filepath=OUTDIR + 'heavy_mech.blend')
# FBX for Unity
bpy.ops.object.select_all(action='DESELECT')
for o in coll.objects:
    o.select_set(True)
bpy.context.view_layer.objects.active = coll.objects['mech_root']
bpy.ops.export_scene.fbx(filepath=OUTDIR + 'heavy_mech.fbx', use_selection=True,
    object_types={'EMPTY', 'MESH'}, apply_unit_scale=True, apply_scale_options='FBX_SCALE_UNITS',
    bake_space_transform=True, axis_forward='-Z', axis_up='Y', mesh_smooth_type='FACE',
    use_mesh_modifiers=True, add_leaf_bones=False, path_mode='AUTO')
print('saved', os.path.getsize(OUTDIR + 'heavy_mech.fbx'))

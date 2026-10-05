# post-script for run3.py (final v3): box-projection UVs, tune stored in the scene, FBX export for Unity.
import bpy, bmesh, os, json
TUNE = globals().get('TUNE', {})
OUT = os.path.expanduser('~/Documents/learning/mech-test/blender/')
coll = bpy.data.collections['HeavyMech']
for o in coll.objects:
    if o.type != 'MESH':
        continue
    me = o.data
    bm = bmesh.new()
    bm.from_mesh(me)
    uvl = bm.loops.layers.uv.verify()
    for f in bm.faces:
        n = f.normal
        a = max(range(3), key=lambda i: abs(n[i]))
        u, v = [i for i in range(3) if i != a]
        for l in f.loops:
            l[uvl].uv = (l.vert.co[u] * 0.5, l.vert.co[v] * 0.5)
    bm.to_mesh(me)
    bm.free()
sc = bpy.context.scene
sc['v3_tune'] = json.dumps({k: v for k, v in TUNE.items() if k != 'post'})
bpy.ops.object.select_all(action='DESELECT')
for o in coll.objects:
    o.select_set(True)
bpy.context.view_layer.objects.active = coll.objects['mech_root']
fbx = OUT + 'heavy_mech_v3.fbx'
bpy.ops.export_scene.fbx(filepath=fbx, use_selection=True,
                         object_types={'EMPTY', 'MESH'}, apply_unit_scale=True, apply_scale_options='FBX_SCALE_UNITS',
                         bake_space_transform=True, axis_forward='-Z', axis_up='Y', mesh_smooth_type='FACE',
                         use_mesh_modifiers=True, add_leaf_bones=False, path_mode='AUTO')
bpy.ops.object.select_all(action='DESELECT')
print('FBX', fbx, os.path.getsize(fbx))

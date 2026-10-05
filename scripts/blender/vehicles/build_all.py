# Build all four vehicles, check closed meshes + triangle budget, smart-UV, save vehicles.blend, write vehicles.DONE.
# Blender -b --factory-startup --python build_all.py [-- fbx]
import bpy, sys, os, json, importlib, inspect, math
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import veh_lib as V
import render_vehicles as RV

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
for o in list(bpy.data.objects):
    bpy.data.objects.remove(o, do_unlink=True)
V.build_materials(ao_samples=8)
NAMES = ['truck', 'apc', 'jeep', 'wreck']
PIVOT = {'wheel': 'axle', 'door': 'hinge', 'hood': 'hinge', 'hatch': 'hinge', 'turret': 'turret ring axis',
         'mg': 'trunnion (elevation axis), child of the turret', 'trunk': 'hinge', 'spare': 'wheel centre',
         'bumper': 'centre', 'canvas': 'vehicle origin', 'body': 'vehicle origin', 'hull': 'vehicle origin'}
import bmesh
from mathutils import Vector
def fix_closed(o):
    bm = bmesh.new(); bm.from_mesh(o.data)
    # non-manifold (>2 faces) edges: split them so each piece can be capped
    nm = [e for e in bm.edges if len(e.link_faces) > 2]
    if nm:
        bmesh.ops.split_edges(bm, edges=nm)
    bnd = {f for e in bm.edges if len(e.link_faces) != 2 for f in e.link_faces}
    if bnd:  # flat stencil decals -> each face rebuilt as a 1.5 mm closed prism pushed into the surface
        bm.normal_update()
        for f in list(bnd):
            n, mi, sm = f.normal.copy(), f.material_index, f.smooth
            co = [v.co.copy() for v in f.verts]
            top = [bm.verts.new(c) for c in co]
            bot = [bm.verts.new(c - n * 0.0015) for c in co]
            k = len(co)
            new = [bm.faces.new(top), bm.faces.new(bot[::-1])]
            new += [bm.faces.new((top[i], bot[i], bot[(i + 1) % k], top[(i + 1) % k])[::-1]) for i in range(k)]
            for nf in new:
                nf.material_index, nf.smooth = mi, sm
            bm.faces.remove(f)
        bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context='VERTS')
        bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    bmesh.ops.triangulate(bm, faces=[f for f in bm.faces if len(f.verts) > 3])
    bm.to_mesh(o.data); bm.free(); o.data.update()

info = {'collections': [], 'roots': [], 'vehicles': {}}
roots = []
for n in NAMES:
    coll, root = importlib.import_module('build_' + n).build()
    roots.append(root)
    objs = [o for o in V.vehicle_objects(root) if o.type == 'MESH']
    for o in objs:
        for _ in range(6):
            if not V.open_edges(o):
                break
            fix_closed(o)
    parts, bad = [], []
    for o in objs:
        oe = V.open_edges(o)
        if oe:
            bad.append((o.name, oe))
        key = o.name.split('_')[2] if o.name.count('_') >= 2 else o.name
        parts.append({'name': o.name, 'parent': o.parent.name if o.parent else None, 'tris': V.tri_count([o]),
                      'pivot': PIVOT.get(key, 'centre'), 'pivot_world': [round(c, 3) for c in o.get('pivot_world', o.location)],
                      'closed': oe == 0})
    tc = V.tri_count(objs)
    print('TRIS %s %d  parts %d  open %s' % (n, tc, len(objs), bad))
    info['collections'].append(coll.name)
    info['roots'].append(root.name)
    info['vehicles'][n] = {'collection': coll.name, 'root': root.name, 'tris': tc, 'parts': parts}
RV.lineup_positions(roots, az=35.0, gap=2.0)
for r in roots:
    V.uv_unwrap(r)
bpy.context.scene.name = 'Vehicles'
bpy.ops.wm.save_as_mainfile(filepath=V.BLEND_OUT, compress=True)
print('SAVED', V.BLEND_OUT)
if 'fbx' in argv:
    for n, r in zip(NAMES, roots):
        V.export_fbx(r, os.path.join(V.EXPORT_DIR, n + '.fbx'))
info['burn_function'] = {'module': 'scripts/vehicles/veh_lib.py',
                         'name': 'burn_material', 'signature': 'burn_material' + str(inspect.signature(V.burn_material)),
                         'helper': 'burn_objects' + str(inspect.signature(V.burn_objects)),
                         'note': "returns/assigns '<mat>_burnt' copies; Value node 'burn_amount' (0..1) is keyframable"}
info['blend'] = V.BLEND_OUT
info['conventions'] = {'front': '-Y', 'up': '+Z', 'units': 'm', 'vehicle_left': '+X',
                       'root': '<name>_root empty at ground level, centre of the footprint',
                       'part_names': 'VEH_<vehicle>_<part>'}
with open(os.path.join(V.ROOT, 'vehicles.DONE'), 'w') as f:
    json.dump(info, f, indent=1, ensure_ascii=False)
print('DONE written')

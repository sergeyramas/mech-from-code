import bpy
sc = bpy.context.scene
VIEW = globals().get('VIEW', 'three_quarter')
PCT = globals().get('PCT', 40)
OUT = globals().get('OUT', '/tmp/prev_%s.png' % VIEW)
bpy.app.driver_namespace['mech_setview'](VIEW)
sc.render.resolution_percentage = PCT
sc.eevee.taa_render_samples = globals().get('SAMPLES', 16)
sc.render.filepath = OUT
bpy.ops.render.render(write_still=True)
sc.render.resolution_percentage = 100
print('saved', OUT)

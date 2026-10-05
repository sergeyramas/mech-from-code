import bpy, time, os
sc=bpy.context.scene
try: sc.render.engine='BLENDER_EEVEE'
except TypeError as e: print(e)
e=sc.eevee
e.taa_render_samples=16
e.volumetric_tile_size='8'; e.volumetric_samples=64; e.volumetric_end=600
e.use_volumetric_shadows=True
try: e.use_raytracing=True
except Exception as ex: print(ex)
sc.render.resolution_x,sc.render.resolution_y=960,540
for cam in ['CAM_wide','CAM_hero']:
    sc.camera=bpy.data.objects[cam]
    sc.render.filepath=os.path.expanduser(f'~/Documents/learning/mech-test/blender/renders/cine/test/eevee_{cam}.png')
    t=time.time(); bpy.ops.render.render(write_still=True); print('TIME',cam,round(time.time()-t,2))

import bpy, sys, os, json, math
sys.path.insert(0, os.path.dirname(__file__))
import cine_mech as CM
SCRIPT=[('idle',0.4),('walk',7),('wait',0.35),('torso',0.8,-80,1.2),('torso',0.9,0,0.2),
        ('walk',3),('wait',0.3),('torso',0.4,-9,2.0),('torso',0.6,0,0.2),('walk',4),('wait',0.6),('torso',0.4,75,3.0)]
ev,ctx,g=CM.animate(SCRIPT, y0=-21.0, z0=-0.07)
print('PHASES',[(n,round((a-1)/24,2),round((b-1)/24,2)) for n,a,b in [(p['name'],p['start_frame'],p['end_frame']) for p in ev['phases']]])
print('END', ctx['pl']['end_c'], 'dur', ev['duration_s'])
sc=bpy.context.scene
for fd in ev['foot_down']:
    sc.frame_set(fd['frame']); o=bpy.data.objects[fd['foot']]
    print('FD',fd['foot'],fd['time_s'],tuple(round(x,2) for x in o.matrix_world.translation))

"""cine_mech.py -- mech walk/aim/snap-turn animation for the cinematic.

Re-uses scripts/animate_mech.py (read-only import: its source is exec'd without the trailing main()),
replacing only plan() (custom script of walks / stops / torso aims) and dress_scene() (no-op).
The mech is animated in the planner frame (facing -Y from the origin); `MECH_path` (rot z = 180 deg)
moves it into the world so it walks +Y towards BLD_target.
"""
import bpy, math, os, types
import numpy as np
from mathutils import Vector, Euler, Matrix

ROOT = os.path.expanduser('~/Documents/learning/mech-test/blender')


def load_animate_mech():
    src = open(os.path.join(ROOT, 'scripts/animate_mech.py')).read()
    lines = src.rstrip().split('\n')
    assert lines[-1].strip() == 'main()', lines[-1]
    g = {'__name__': 'animate_mech_lib', '__file__': os.path.join(ROOT, 'scripts/animate_mech.py')}
    exec(compile('\n'.join(lines[:-1]), 'animate_mech.py', 'exec'), g)
    return g


def make_plan(g, script):
    """script: list of ('idle', s) | ('walk', n) | ('torso', dur, deg, hold) | ('wait', s)."""
    fwd_dir, lat_dir = g['fwd_dir'], g['lat_dir']

    def plan(rig, p):
        fps = p['fps']
        L = rig.L
        Pl = p['step_frac'] * L
        sx = rig.thigh_x + p['stance_extra']
        H = p['lift_frac'] * L
        q = lambda s: int(round(s * fps)) / fps
        steps = {'L': [], 'R': []}
        pos = {'L': np.array([-sx, 0.0]), 'R': np.array([sx, 0.0])}
        yaw = {'L': 0.0, 'R': 0.0}
        side = {'L': -1.0, 'R': +1.0}
        other = {'L': 'R', 'R': 'L'}
        phases = []
        st = dict(c=np.array([0.0, 0.0]), t=0.0, cur=0.0, first='L')
        torso_segs = []
        psi = 0.0

        def add(foot, t_lift, dur, xy, yw, h, kind, phase, idx):
            tl = q(t_lift)
            steps[foot].append(dict(t_lift=tl, t_land=tl + q(dur), from_xy=pos[foot].copy(),
                                    to_xy=np.array(xy, dtype=float), from_yaw=yaw[foot], to_yaw=yw, H=h,
                                    kind=kind, phase=phase, idx=idx))
            pos[foot] = np.array(xy, dtype=float)
            yaw[foot] = yw

        wi = 0
        for item in script:
            kind = item[0]
            if kind in ('idle', 'wait'):
                phases.append((kind, st['t'], st['t'] + item[1]))
                st['t'] = q(st['t'] + item[1])
            elif kind == 'walk':
                n = item[1]
                lifts = item[2] if len(item) > 2 else {}
                t0 = st['t']
                fcoord = {'L': 0.0, 'R': 0.0}
                f = st['first']
                for k in range(n):
                    o = other[f]
                    new = fcoord[o] + Pl if k < n - 1 else fcoord[o]
                    tgt = st['c'] + fwd_dir(psi) * new + lat_dir(psi) * side[f] * sx
                    add(f, t0 + k * p['walk_period'], p['walk_swing'], tgt, psi, lifts.get(k, H), 'walk', f'walk{wi}', k)
                    fcoord[f] = new
                    f = o
                st['first'] = f
                st['c'] = st['c'] + fwd_dir(psi) * (0.5 * (fcoord['L'] + fcoord['R']))
                t_e = q(t0 + (n - 1) * p['walk_period'] + p['walk_swing'])
                phases.append((f'walk{wi}', t0, t_e))
                wi += 1
                st['t'] = t_e
            elif kind == 'torso':
                _, dur, deg, hold = item
                torso_segs.append(dict(t_start=q(st['t']), t_end=q(st['t'] + dur), from_deg=st['cur'], to_deg=deg))
                phases.append((f'torso{len(torso_segs)}', st['t'], st['t'] + dur))
                st['cur'] = deg
                st['t'] = q(st['t'] + dur + hold)
        duration = q(st['t'])
        phases.append(('end', duration, duration))
        return dict(steps=steps, torso=torso_segs, phases=phases, duration=duration,
                    init=(np.array([-sx, 0.0]), np.array([sx, 0.0])), step_len=Pl, lift_h=H, stance_x=sx,
                    end_c=st['c'].copy())
    return plan


def fc_find(ob, path, index):
    from fx_lib import fcurves_of
    for fc in fcurves_of(ob.animation_data.action):
        if fc.data_path == path and fc.array_index == index:
            return fc
    return None


def fc_arrays(fc):
    n = len(fc.keyframe_points)
    co = np.empty(2 * n)
    fc.keyframe_points.foreach_get('co', co)
    return co[0::2].copy(), co[1::2].copy()


def fc_write(fc, fr, vals):
    n = len(fc.keyframe_points)
    co = np.empty(2 * n)
    co[0::2] = fr
    co[1::2] = vals
    fc.keyframe_points.foreach_set('co', co)
    fc.update()


def add_to_channel(ob, path, index, func, fps):
    """add func(t_story_seconds) to an existing per-frame keyed channel (frame 1 == t 0)."""
    from fx_lib import set_keys_fast
    fc = fc_find(ob, path, index)
    if fc is None:
        raise RuntimeError(f'no fcurve {ob.name} {path}[{index}]')
    fr, v = fc_arrays(fc)
    t = (fr - 1) / fps
    fc_write(fc, fr, v + func(t))


def animate(script, y0, z0, params=None):
    g = load_animate_mech()
    g['plan'] = make_plan(g, script)
    g['dress_scene'] = lambda *a, **k: None
    args = types.SimpleNamespace(names=None, params=None, save=None, events=None, frames=None, no_verify=True)
    if params:
        g['P'].update(params)
    ev, ctx = g['build'](args)
    # world placement
    path = bpy.data.objects.get('MECH_path') or bpy.data.objects.new('MECH_path', None)
    if path.name not in bpy.context.scene.collection.objects:
        bpy.context.scene.collection.objects.link(path)
    path.location = (0.0, y0, z0)
    path.rotation_euler = (0, 0, math.pi)
    root = bpy.data.objects['mech_root']
    root.parent = path
    root.matrix_parent_inverse = Matrix.Identity(4)
    return ev, ctx, g


def snap_turn(ctx, t0, deg, dur=0.38, over_deg=11.0, fps=24):
    """replace the torso yaw with a hard servo snap (overshoot + jolt back) starting at story t0."""
    torso = bpy.data.objects['torso']
    fc = fc_find(torso, 'rotation_euler', 2)
    fr, v = fc_arrays(fc)
    t = (fr - 1) / fps
    base0 = np.interp(t0, t, v)
    u = np.clip((t - t0) / dur, 0, 1)
    ease = u * u * (3 - 2 * u) if False else 1 - (1 - u) ** 3            # fast start, decelerating
    tgt = base0 + math.radians(deg) * ease
    # overshoot bump + jolt back (damped oscillation after arrival)
    ta = t - (t0 + dur * 0.8)
    osc = np.where(ta > 0, np.sin(2 * math.pi * 2.4 * ta) * np.exp(-ta / 0.22), 0.0)
    tgt = tgt + math.radians(over_deg) * osc
    w = np.clip((t - t0 + 0.05) / 0.05, 0, 1) * np.clip((t0 + 3.0 - t) / 0.4, 0, 1)
    # after the window the planner's own torso target (same deg) takes over
    newv = v * (1 - w) + tgt * w
    fc_write(fc, fr, newv)
    # cockpit lifts a little, arms twitch
    ck = bpy.data.objects['cockpit']
    ck.rotation_mode = 'XYZ'
    lift = lambda tt: np.where(tt > t0, 1.0, 0.0) * (1 - np.exp(-np.maximum(tt - t0, 0) / 0.12)) * \
        np.exp(-np.maximum(tt - t0 - 1.6, 0) / 0.8)
    from fx_lib import set_keys_fast
    rx0 = ck.rotation_euler.x
    lz0 = ck.location.z
    set_keys_fast(ck, 'rotation_euler', 0, fr, rx0 + math.radians(-7.0) * lift(t))
    set_keys_fast(ck, 'location', 2, fr, lz0 + 0.12 * lift(t))
    tw = lambda tt, a, f, ph: np.where(tt > t0 + ph, math.radians(a) * np.sin(2 * math.pi * f * (tt - t0 - ph)) *
                                       np.exp(-(tt - t0 - ph) / 0.3), 0.0)
    for nm, a, f_, ph in (('arm_R', 9.0, 3.1, 0.05), ('arm_L', -7.0, 2.7, 0.08), ('cannon_R', 6.0, 4.3, 0.1),
                          ('launcher_L', 3.0, 5.0, 0.12), ('launcher_R', 3.0, 5.0, 0.1)):
        add_to_channel(bpy.data.objects[nm], 'rotation_euler', 0, lambda tt: tw(tt, a, f_, ph), fps)


def recoil(t_fire, fps=24, arm='arm_R', part='cannon_R', kick_deg=-8.0, slide=0.35):
    """cannon recoil: barrel slides back along local +Y, arm kicks up."""
    ob = bpy.data.objects[part]
    from fx_lib import set_keys_fast
    def env(tt):
        x = np.maximum(tt - t_fire, 0)
        return np.where(tt >= t_fire, (1 - np.exp(-x / 0.02)) * np.exp(-x / 0.25), 0.0)
    fc = fc_find(ob, 'rotation_euler', 0)
    fr, _ = fc_arrays(fc)
    t = (fr - 1) / fps
    y0 = ob.location.y
    set_keys_fast(ob, 'location', 1, fr, y0 + slide * env(t))
    add_to_channel(bpy.data.objects[arm], 'rotation_euler', 0, lambda tt: math.radians(kick_deg) * env(tt), fps)

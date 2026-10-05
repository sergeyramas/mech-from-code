"""
animate_mech.py  --  parametric walk / torso-turn / turn-in-place animation for the heavy mech.

Run (headless, on a COPY; the source .blend is never overwritten):

  /Applications/Blender.app/Contents/MacOS/Blender -b heavy_mech_v2_procedural.blend \
      --python animate_mech.py -- --save mech_walk_v2_anim.blend \
      --events renders/anim_events.json

Everything is driven by OBJECT NAMES (see NAMES) and by values measured from the rig itself:
  * leg bone lengths     : |shin.location| and |foot.location|   (thigh -> knee -> ankle)
  * thigh offset         : thigh_L/R .location.x
  * ankle height         : foot pivot z - lowest vertex of the foot mesh
  * step length          : STEP_FRAC * leg length  (nothing is hard-coded in metres)
  * hip height           : derived every frame from a constant stance leg length (LC_*)
So a v3 model with the same part names (and the same hierarchy / pivots-at-joints convention,
mech faces -Y, hinge axes = local X, limbs hang along -Z) is animated without edits.
Use `--names names.json` to remap object names, `--params p.json` to override the P dict
(timeline, amplitudes, camera, samples), `--help` for the other options.

Pipeline:
  1. plan   : step list (foot, lift time, land time, target xy, yaw) for idle / walk / torso turn /
              turn-in-place / walk.  Times are quantised to whole frames, so foot_down is an exact frame.
  2. signals: feet trajectories -> body path (smoothed foot mid-point), yaw, weight shift, hip height
              (constant stance leg length), impact sag, torso lean/twist, spring-driven arms/cannon.
  3. bake   : two-bone IK (pole = forward) + planted flat feet, one LINEAR key per frame.
  4. camera, lights rig, big floor, render settings, anim_events.json, verification pass.
"""
import bpy
import sys, os, json, math, argparse
import numpy as np
from mathutils import Vector, Matrix, Euler

# --------------------------------------------------------------------------- names / parameters
NAMES = dict(
    root='mech_root', hip='hip', torso='torso',
    thigh_L='thigh_L', thigh_R='thigh_R', shin_L='shin_L', shin_R='shin_R',
    foot_L='foot_L', foot_R='foot_R',
    shoulder_L='shoulder_L', shoulder_R='shoulder_R',
    arm_L='arm_L', arm_R='arm_R', fist_L='fist_L', cannon_R='cannon_R',
    launcher_L='launcher_L', launcher_R='launcher_R',
    # scene helpers (created if missing)
    camera='MechCam', floor='Floor',
    lights=['Key', 'Fill', 'Rim', 'Rim2'],
)

P = dict(
    fps=24,
    sub=5,                      # internal oversampling for smoothing / springs
    seed=7,
    # ---- geometry derived from the rig ----
    lc_stand=0.95,              # stance leg length / full leg length (standing)
    lc_walk=0.925,              # ... while stepping (more knee bend)
    lmax_frac=0.975,            # leg reach limit for the airborne foot
    step_frac=0.55,             # step length (foot-to-foot) / leg length
    stance_extra=0.15,          # feet slightly wider than the hips
    lift_frac=0.225,            # foot lift height / leg length (walk)
    # ---- timeline (seconds) ----
    idle_s=1.0,
    walk1_steps=4, walk_period=1.2, walk_swing=0.78,
    settle1_s=0.95,
    torso_pre_s=0.2,
    torso_segments=[            # (duration, target_deg, hold_after_s)   + = turn left (CCW from above)
        (0.95, +55.0, 0.30),
        (1.45, -55.0, 0.30),
        (0.85, 0.0, 0.40),
    ],
    turn_yaws=[30, 30, 60, 60, 90, 90],     # landing yaw of successive turn steps (alternating feet)
    turn_period=0.80, turn_swing=0.52, turn_lift_scale=0.62,
    settle2_s=0.65,
    walk2_steps=2,
    tail_s=2.0,                 # idle after the last landing
    first_foot='L',
    # ---- body mechanics ----
    sway_m=0.30, roll_deg=3.6, pelvis_yaw_deg=3.2,
    sag_m=0.13, sag_tau=0.11,
    breathe_hz=0.26, breathe_m=0.035,
    lean_deg=3.0, lean_accel_deg=1.2, impact_pitch_deg=1.1,
    arm_swing_deg=7.0,
    peak_deg=dict(arm=9.0, fist=6.0, cannon=5.5, launcher=2.2),
    torso_servo_hz=1.9, torso_servo_zeta=0.72,
    # ---- camera ----
    cam_dist=21.5, cam_height=1.6, cam_target_z=4.5, cam_lens=35.0, cam_azimuth_deg=-30.0,
    cam_azimuth_follow=0.0, cam_smooth_s=0.55, cam_shake_m=0.05,
    # ---- render ----
    res=(1280, 720), samples=24, floor_radius=400.0, floor_fade=(18.0, 80.0),
)


def log(*a):
    print('[animate_mech]', *a, flush=True)


# --------------------------------------------------------------------------- math helpers
def gsmooth(a, sigma_s, fs):
    """zero-phase Gaussian smoothing (edge-hold) of a 1-D or 2-D (n, k) array."""
    a = np.asarray(a, dtype=float)
    s = sigma_s * fs
    if s < 0.5:
        return a.copy()
    r = int(math.ceil(4 * s))
    x = np.arange(-r, r + 1)
    k = np.exp(-0.5 * (x / s) ** 2)
    k /= k.sum()
    if a.ndim == 1:
        return np.convolve(np.pad(a, (r, r), mode='edge'), k, mode='valid')
    return np.stack([gsmooth(a[:, j], sigma_s, fs) for j in range(a.shape[1])], 1)


def smoothstep(x):
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3 - 2 * x)


def second_order(target, f_hz, zeta, fs):
    """under-damped follower of a target series (heavy turret servo)."""
    w = 2 * math.pi * f_hz
    dt = 1.0 / fs
    x = float(target[0])
    v = 0.0
    out = np.empty(len(target))
    for i, tg in enumerate(target):
        a = w * w * (tg - x) - 2 * zeta * w * v
        v += a * dt
        x += v * dt
        out[i] = x
    return out


def pendulum(drive, w0, zeta, fs, kicks=()):
    """x'' = -w0^2 x - 2 zeta w0 x' + drive(t);  kicks = [(sample_index, dv)] velocity impulses."""
    n = len(drive)
    dt = 1.0 / fs
    kd = {}
    for i, dv in kicks:
        kd[i] = kd.get(i, 0.0) + dv
    x = v = 0.0
    out = np.zeros(n)
    for i in range(n):
        if i in kd:
            v += kd[i]
        a = drive[i] - w0 * w0 * x - 2 * zeta * w0 * v
        v += a * dt
        x += v * dt
        out[i] = x
    return out


def normalise_peak(x, peak_rad):
    m = np.max(np.abs(x))
    return x * (peak_rad / m) if m > 1e-9 else x


def d2(x, fs):
    return np.gradient(np.gradient(x, axis=0) * fs, axis=0) * fs


def rot2(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, -s], [s, c]])


def fwd_dir(psi):
    """mech faces -Y; +psi (CCW from above) turns it left."""
    return np.array([math.sin(psi), -math.cos(psi)])


def lat_dir(psi):
    """local +X axis in world."""
    return np.array([math.cos(psi), math.sin(psi)])


def mat_t(v):
    return Matrix.Translation(Vector(v))


def mat_r(e):
    return Euler(e, 'XYZ').to_matrix().to_4x4()


# --------------------------------------------------------------------------- rig measurement
class Rig:
    def __init__(self, names):
        self.n = names
        g = bpy.data.objects.get
        self.ob = {k: g(v) for k, v in names.items() if isinstance(v, str)}
        for k in ('root', 'hip', 'torso', 'thigh_L', 'thigh_R', 'shin_L', 'shin_R', 'foot_L', 'foot_R'):
            if self.ob.get(k) is None:
                raise RuntimeError(f'required object missing: {names[k]}')
        for k, o in self.ob.items():
            if o is not None and k not in ('camera', 'floor'):
                if o.animation_data:
                    o.animation_data_clear()
                o.rotation_mode = 'XYZ'
        # rest transforms (local), keyed by ROLE
        self.rest_loc = {k: o.location.copy() for k, o in self.ob.items() if o is not None}
        self.rest_rot = {k: Euler(o.rotation_euler) for k, o in self.ob.items() if o is not None}
        self.thigh_x = abs(self.ob['thigh_L'].location.x)
        self.L1 = self.ob['shin_L'].location.length
        self.L2 = self.ob['foot_L'].location.length
        self.L = self.L1 + self.L2
        # foot mesh: lowest point relative to the ankle pivot, sole clearance table under pitch
        me = self.ob['foot_L'].data
        co = np.empty(len(me.vertices) * 3)
        me.vertices.foreach_get('co', co)
        co = co.reshape(-1, 3)
        self.foot_co = co
        self.ankle_h = -co[:, 2].min()
        self.foot_toe_y = co[:, 1].min()
        self._pitch_grid = np.radians(np.linspace(-25, 40, 261))
        yy, zz = co[:, 1][None, :], co[:, 2][None, :]
        zr = yy * np.sin(self._pitch_grid)[:, None] + zz * np.cos(self._pitch_grid)[:, None]
        self._clear_tab = -zr.min(axis=1)
        # arm pivots (world x at rest) for yaw-acceleration coupling
        self.pivot_x = {}
        for k in ('arm_L', 'arm_R', 'fist_L', 'cannon_R', 'launcher_L', 'launcher_R'):
            o = self.ob.get(k)
            self.pivot_x[k] = o.matrix_world.translation.x if o is not None else 0.0
        log(f'rig: L1={self.L1:.3f} L2={self.L2:.3f} L={self.L:.3f} thigh_x={self.thigh_x:.3f} '
            f'ankle_h={self.ankle_h:.3f} foot_toe_y={self.foot_toe_y:.3f} foot_verts={len(co)}')

    def clearance(self, pitch_rad):
        return np.interp(pitch_rad, self._pitch_grid, self._clear_tab)


# --------------------------------------------------------------------------- planner
def plan(rig, p):
    fps = p['fps']
    L = rig.L
    Pl = p['step_frac'] * L
    sx = rig.thigh_x + p['stance_extra']
    H = p['lift_frac'] * L
    q = lambda s: int(round(s * fps)) / fps          # quantise to frames
    steps = {'L': [], 'R': []}
    pos = {'L': np.array([-sx, 0.0]), 'R': np.array([sx, 0.0])}
    yaw = {'L': 0.0, 'R': 0.0}
    side = {'L': -1.0, 'R': +1.0}
    other = {'L': 'R', 'R': 'L'}
    phases = []
    c = np.array([0.0, 0.0])
    psi = 0.0

    def add(foot, t_lift, dur, xy, yw, h, kind, phase, idx):
        tl = q(t_lift)
        steps[foot].append(dict(t_lift=tl, t_land=tl + q(dur), from_xy=pos[foot].copy(),
                                to_xy=np.array(xy, dtype=float), from_yaw=yaw[foot], to_yaw=yw, H=h,
                                kind=kind, phase=phase, idx=idx))
        pos[foot] = np.array(xy, dtype=float)
        yaw[foot] = yw

    t = q(p['idle_s'])
    phases.append(('idle', 0.0, t))

    def walk(n, t0, name):
        nonlocal c
        fcoord = {'L': 0.0, 'R': 0.0}
        f = p['first_foot']
        for k in range(n):
            o = other[f]
            new = fcoord[o] + Pl if k < n - 1 else fcoord[o]      # last step: bring the foot level
            tgt = c + fwd_dir(psi) * new + lat_dir(psi) * side[f] * sx
            add(f, t0 + k * p['walk_period'], p['walk_swing'], tgt, psi, H, 'walk', name, k)
            fcoord[f] = new
            f = o
        c = c + fwd_dir(psi) * (0.5 * (fcoord['L'] + fcoord['R']))
        t_e = q(t0 + (n - 1) * p['walk_period'] + p['walk_swing'])
        phases.append((name, t0, t_e))
        return t_e

    t_end = walk(p['walk1_steps'], t, 'walk1')
    t = q(t_end + p['settle1_s'])
    # ---- torso turret turns (relative to the hip) ----
    tt = q(t + p['torso_pre_s'])
    torso_segs = []
    cur = 0.0
    t_cur = tt
    for dur, tgt, hold in p['torso_segments']:
        torso_segs.append(dict(t_start=q(t_cur), t_end=q(t_cur + dur), from_deg=cur, to_deg=tgt))
        cur = tgt
        t_cur = q(t_cur + dur + hold)
    phases.append(('torso_turn', tt, torso_segs[-1]['t_end']))
    t = q(t_cur)
    # ---- turn in place by stepping ----
    t_turn0 = t
    foot = p['first_foot']
    for k, yw_deg in enumerate(p['turn_yaws']):
        yw = math.radians(yw_deg)
        tgt = c + rot2(yw) @ np.array([side[foot] * sx, 0.0])
        add(foot, t_turn0 + k * p['turn_period'], p['turn_swing'], tgt, yw, H * p['turn_lift_scale'],
            'turn', 'turn', k)
        foot = other[foot]
    psi = math.radians(p['turn_yaws'][-1])
    t_end = q(t_turn0 + (len(p['turn_yaws']) - 1) * p['turn_period'] + p['turn_swing'])
    phases.append(('turn', t_turn0, t_end))
    t = q(t_end + p['settle2_s'])
    t_end = walk(p['walk2_steps'], t, 'walk2')
    duration = q(t_end + p['tail_s'])
    phases.append(('end', t_end, duration))
    return dict(steps=steps, torso=torso_segs, phases=phases, duration=duration,
                init=(np.array([-sx, 0.0]), np.array([sx, 0.0])), step_len=Pl, lift_h=H, stance_x=sx)


# --------------------------------------------------------------------------- foot trajectories
def pitch_profile(tau):
    """deg, + = toe down: toe-off hump, then slight heel-up before landing, flat at both ends."""
    a = 14.0 * np.sin(np.pi * np.clip(tau / 0.4, 0, 1))
    b = -6.0 * np.sin(np.pi * np.clip((tau - 0.4) / 0.6, 0, 1))
    return np.where(tau < 0.4, a, b)


def foot_series(t, init_xy, steps, rig):
    n = len(t)
    xy = np.tile(np.asarray(init_xy, float), (n, 1))
    yaw = np.zeros(n)
    lift = np.zeros(n)
    pitch = np.zeros(n)
    swing = np.zeros(n, bool)
    for s in steps:
        m_sw = (t >= s['t_lift']) & (t < s['t_land'])
        m_af = t >= s['t_land']
        tau = (t[m_sw] - s['t_lift']) / (s['t_land'] - s['t_lift'])
        u = smoothstep(tau)
        xy[m_sw] = s['from_xy'][None, :] + (s['to_xy'] - s['from_xy'])[None, :] * u[:, None]
        yaw[m_sw] = s['from_yaw'] + (s['to_yaw'] - s['from_yaw']) * u
        pp = 1.3 * tau - 0.3 * tau * tau
        lift[m_sw] = s['H'] * np.sin(np.pi * pp)
        pitch[m_sw] = np.radians(pitch_profile(tau))
        swing[m_sw] = True
        xy[m_af] = s['to_xy']
        yaw[m_af] = s['to_yaw']
        lift[m_af] = 0.0
        pitch[m_af] = 0.0
    ankle_z = rig.clearance(pitch) + lift
    ankle_z[~swing] = rig.ankle_h
    return dict(xy=xy, yaw=yaw, lift=lift, pitch=pitch, swing=swing, ankle_z=ankle_z)


# --------------------------------------------------------------------------- IK
def solve_leg(A, T, L1, L2, pole):
    """two-bone IK in the hip frame. A = thigh pivot, T = ankle target.  Returns
    (R_thigh 3x3 Matrix, knee_angle, clamp_err).  Hinge axis of the knee = thigh local X."""
    v = T - A
    d = v.length
    dmax = (L1 + L2) * 0.9995
    dmin = abs(L1 - L2) * 1.05 + 0.05
    err = 0.0
    if d > dmax:
        err = d - dmax
        d = dmax
    elif d < dmin:
        err = dmin - d
        d = dmin
    vh = v.normalized()
    n = pole.cross(vh)
    if n.length < 1e-6:
        n = Vector((1, 0, 0))
    n.normalize()
    ca = max(-1.0, min(1.0, (L1 * L1 + d * d - L2 * L2) / (2 * L1 * d)))
    al = math.acos(ca)
    cands = [Matrix.Rotation(sgn * al, 3, n) @ vh for sgn in (1, -1)]
    u = max(cands, key=lambda w: w.dot(pole))
    zt = -u
    xt = n
    yt = zt.cross(xt)
    R = Matrix(((xt.x, yt.x, zt.x), (xt.y, yt.y, zt.y), (xt.z, yt.z, zt.z)))
    K = A + L1 * u
    Tc = A + vh * d
    w = (Tc - K).normalized()
    wl = R.transposed() @ w
    phi = math.atan2(wl.y, -wl.z)
    return R, phi, err


# --------------------------------------------------------------------------- main build
def build(args):
    names = dict(NAMES)
    if args.names:
        names.update(json.load(open(args.names)))
    p = dict(P)
    if args.params:
        p.update(json.load(open(args.params)))
    sc = bpy.context.scene
    fps = p['fps']
    sc.render.fps = fps
    sc.render.fps_base = 1.0
    SUB = p['sub']
    FS = fps * SUB
    rig = Rig(names)
    rng = np.random.default_rng(p['seed'])
    bpy.context.preferences.edit.keyframe_new_interpolation_type = 'LINEAR'

    pl = plan(rig, p)
    D = pl['duration']
    nfr = int(round(D * fps)) + 1
    n = (nfr - 1) * SUB + 1
    t = np.arange(n) / FS
    log(f'plan: duration {D:.2f}s, {nfr} frames, step_len {pl["step_len"]:.2f} m, lift {pl["lift_h"]:.2f} m')

    # ---------------- feet
    fS = {}
    for key, init in zip(('L', 'R'), pl['init']):
        fS[key] = foot_series(t, init, pl['steps'][key], rig)
    swing_any = fS['L']['swing'] | fS['R']['swing']

    mid = 0.5 * (fS['L']['xy'] + fS['R']['xy'])
    root_xy = gsmooth(mid, 0.30, FS)
    psi = gsmooth(0.5 * (fS['L']['yaw'] + fS['R']['yaw']), 0.25, FS)
    fwd = np.stack([np.sin(psi), -np.cos(psi)], 1)
    lat = np.stack([np.cos(psi), np.sin(psi)], 1)

    # load distribution (weight shift)
    wl_ = gsmooth((~fS['L']['swing']).astype(float), 0.12, FS)
    wr_ = gsmooth((~fS['R']['swing']).astype(float), 0.12, FS)
    wsum = np.maximum(wl_ + wr_, 1e-6)
    wl_, wr_ = wl_ / wsum, wr_ / wsum
    wmove = np.clip(gsmooth(swing_any.astype(float), 0.5, FS) * 1.6, 0, 1)

    sway = p['sway_m'] * (wr_ - wl_) * (0.35 + 0.65 * wmove)       # + = toward +X (mech local frame)
    roll = np.radians(p['roll_deg']) * (wl_ - wr_)                  # +Y rotation lowers the +X side
    # pelvis yaw from the forward offset difference of the feet
    fl = np.einsum('ij,ij->i', fS['L']['xy'] - root_xy, fwd)
    fr = np.einsum('ij,ij->i', fS['R']['xy'] - root_xy, fwd)
    delta = gsmooth(np.clip((fl - fr) / pl['step_len'], -1.2, 1.2), 0.2, FS)
    pel_yaw = np.radians(p['pelvis_yaw_deg']) * delta

    landings = []   # (t, foot, step)
    for key in ('L', 'R'):
        for s in pl['steps'][key]:
            landings.append((s['t_land'], key, s))
    landings.sort(key=lambda x: x[0])

    # ---------------- hip height (constant stance leg length) + sag + breathing
    Lc = (p['lc_stand'] - (p['lc_stand'] - p['lc_walk']) * wmove) * rig.L
    Lmax = p['lmax_frac'] * rig.L
    hip_xy = root_xy + lat * sway[:, None]
    cands = []
    for key, sgn in (('L', -1.0), ('R', 1.0)):
        ang = psi + pel_yaw
        piv = hip_xy + sgn * rig.thigh_x * np.stack([np.cos(ang), np.sin(ang)], 1)
        dh = np.linalg.norm(fS[key]['xy'] - piv, axis=1)
        Lf = np.where(fS[key]['swing'], Lmax, Lc)
        cands.append(fS[key]['ankle_z'] + np.sqrt(np.maximum(Lf * Lf - dh * dh, (0.35 * Lf) ** 2)))
    z_base = gsmooth(np.minimum(cands[0], cands[1]), 0.06, FS)
    breathe = p['breathe_m'] * np.sin(2 * math.pi * p['breathe_hz'] * t + 0.5) * (1 - 0.6 * wmove)
    sag = np.zeros(n)
    pitch_kick = np.zeros(n)
    tau = p['sag_tau']
    for (tl, key, s) in landings:
        wgt = 1.0 if s['kind'] == 'walk' else 0.7
        x = np.maximum(t - tl, 0.0) / tau
        sag += p['sag_m'] * wgt * np.where(t >= tl, x * np.exp(1 - x), 0.0)
        x2 = np.maximum(t - tl, 0.0) / (tau * 1.4)
        pitch_kick += np.radians(p['impact_pitch_deg']) * wgt * np.where(t >= tl, x2 * np.exp(1 - x2), 0.0)
    hip_z = z_base + breathe - sag

    # ---------------- torso
    vel = np.gradient(root_xy, axis=0) * FS
    acc = np.gradient(vel, axis=0) * FS
    speed = np.einsum('ij,ij->i', vel, fwd)
    v_walk = pl['step_len'] / p['walk_period']
    acc_f = np.einsum('ij,ij->i', acc, fwd)
    lean = np.radians(p['lean_deg']) * np.clip(speed / v_walk, -0.3, 1.3) + \
        np.radians(p['lean_accel_deg']) * np.clip(acc_f, -3, 3)
    torso_pitch = gsmooth(lean, 0.08, FS) + pitch_kick
    torso_roll = -0.55 * roll
    pel_pitch = 0.35 * pitch_kick

    # torso turret (spring servo, slight overshoot)
    tgt_deg = np.zeros(n)
    for sg in pl['torso']:
        m = (t >= sg['t_start']) & (t < sg['t_end'])
        u = smoothstep((t[m] - sg['t_start']) / (sg['t_end'] - sg['t_start']))
        tgt_deg[m] = sg['from_deg'] + (sg['to_deg'] - sg['from_deg']) * u
        tgt_deg[t >= sg['t_end']] = sg['to_deg']
    torso_twist = np.radians(second_order(tgt_deg, p['torso_servo_hz'], p['torso_servo_zeta'], FS))
    torso_yaw = torso_twist - 0.65 * pel_yaw                       # counter-rotation of the pelvis yaw

    # ---------------- secondary motion (arms, fist, cannon, launchers)
    yaw_total = psi + pel_yaw + torso_yaw
    alpha_yaw = d2(yaw_total, FS)
    alpha_pitch = d2(torso_pitch + pel_pitch, FS)
    a_loc_y = np.einsum('ij,ij->i', acc, np.stack([-np.sin(psi), np.cos(psi)], 1))
    a_z = d2(hip_z, FS)
    kicks_idx = [(int(round(tl * FS)), s) for (tl, key, s) in landings]
    sec = {}

    def sec_part(px, ell, w0, zeta, kick, vert, peak_deg):
        drive = -(a_loc_y + px * alpha_yaw) / ell - alpha_pitch + vert * a_z / ell
        kk = [(i, kick * (1.0 if s['kind'] == 'walk' else 0.55) * (0.85 + 0.3 * rng.random()))
              for i, s in kicks_idx]
        out = pendulum(drive, w0, zeta, FS, kk)
        return normalise_peak(out, math.radians(peak_deg))

    pk = p['peak_deg']
    for nm, ell, w0, ze, kick, vert, peak in (
            ('arm_L', 1.7, 3.4, 0.17, -0.40, 0.0, pk['arm']),
            ('arm_R', 1.7, 3.2, 0.17, -0.40, 0.0, pk['arm']),
            ('fist_L', 1.4, 4.4, 0.15, -0.30, 0.0, pk['fist']),
            ('cannon_R', 3.2, 4.8, 0.13, +0.30, 1.0, pk['cannon']),
            ('launcher_L', 2.0, 8.0, 0.2, -0.10, 0.6, pk['launcher']),
            ('launcher_R', 2.0, 8.0, 0.2, -0.10, 0.6, pk['launcher'])):
        if rig.ob.get(nm) is not None:
            sec[nm] = sec_part(rig.pivot_x.get(nm, 0.0), ell, w0, ze, kick, vert, peak)
    swing_arm = np.radians(p['arm_swing_deg']) * delta * (0.4 + 0.6 * wmove)
    breath_arm = np.radians(0.6) * np.sin(2 * math.pi * p['breathe_hz'] * t + 1.3)

    # ---------------- camera / light-rig signals
    focus_xy = gsmooth(root_xy, p['cam_smooth_s'], FS)
    az = math.radians(p['cam_azimuth_deg']) + p['cam_azimuth_follow'] * gsmooth(psi, 0.8, FS)
    cam_xy = focus_xy + p['cam_dist'] * np.stack([np.cos(az), np.sin(az)], 1)
    shake = np.zeros(n)
    for (tl, key, s) in landings:
        dt_ = np.maximum(t - tl, 0.0)
        shake += np.where(t >= tl, np.exp(-dt_ / 0.18) * np.sin(2 * math.pi * 6.5 * dt_), 0.0) * \
            p['cam_shake_m'] * (1.0 if s['kind'] == 'walk' else 0.5)

    # ---------------- sample at frame instants and bake
    idx = np.arange(nfr) * SUB
    ob = rig.ob
    ink = lambda o, path, f: o.keyframe_insert(path, frame=f)
    rest_rot, rest_loc = rig.rest_rot, rig.rest_loc
    L1, L2 = rig.L1, rig.L2
    poles = {'L': Vector((-0.12, -1.0, 0.0)).normalized(), 'R': Vector((0.12, -1.0, 0.0)).normalized()}
    A_loc = {'L': rest_loc['thigh_L'].copy(), 'R': rest_loc['thigh_R'].copy()}
    prev_e = {k: Euler((0, 0, 0), 'XYZ') for k in ('thigh_L', 'thigh_R', 'foot_L', 'foot_R')}
    ik_err, fk_err = [], []
    for fi in range(nfr):
        i = idx[fi]
        f = fi + 1
        rx, ry = root_xy[i]
        ps = psi[i]
        M_root = mat_t((rx, ry, 0)) @ mat_r((0, 0, ps))
        hip_loc = Vector((sway[i], 0.0, hip_z[i]))
        hip_rot = (pel_pitch[i], roll[i], pel_yaw[i])
        M_hip = M_root @ mat_t(hip_loc) @ mat_r(hip_rot)
        Minv = M_hip.inverted()
        ob['root'].location = (rx, ry, 0.0)
        ob['root'].rotation_euler = (0.0, 0.0, ps)
        ink(ob['root'], 'location', f)
        ink(ob['root'], 'rotation_euler', f)
        ob['hip'].location = hip_loc
        ob['hip'].rotation_euler = hip_rot
        ink(ob['hip'], 'location', f)
        ink(ob['hip'], 'rotation_euler', f)
        for key in ('L', 'R'):
            Tw = Vector((fS[key]['xy'][i][0], fS[key]['xy'][i][1], fS[key]['ankle_z'][i]))
            Th = Minv @ Tw
            R, phi, err = solve_leg(A_loc[key], Th, L1, L2, poles[key])
            ik_err.append(err)
            th, sh, ft = 'thigh_' + key, 'shin_' + key, 'foot_' + key
            e_th = R.to_euler('XYZ', prev_e[th])
            prev_e[th] = e_th
            ob[th].rotation_euler = e_th
            ob[sh].rotation_euler = (phi, 0.0, 0.0)
            R_par = M_hip.to_3x3() @ R @ Euler((phi, 0, 0), 'XYZ').to_matrix()
            R_foot_w = Euler((0, 0, fS[key]['yaw'][i]), 'XYZ').to_matrix() @ \
                Euler((fS[key]['pitch'][i], 0, 0), 'XYZ').to_matrix()
            e_ft = (R_par.transposed() @ R_foot_w).to_euler('XYZ', prev_e[ft])
            prev_e[ft] = e_ft
            ob[ft].rotation_euler = e_ft
            for nm in (th, sh, ft):
                ink(ob[nm], 'rotation_euler', f)
            M_th = M_hip @ mat_t(rest_loc[th]) @ R.to_4x4()                # self-check FK
            M_sh = M_th @ mat_t(rest_loc[sh]) @ mat_r((phi, 0, 0))
            M_ft = M_sh @ mat_t(rest_loc[ft])
            fk_err.append((M_ft.translation - Tw).length)
        to = ob['torso']
        to.rotation_euler = (torso_pitch[i], torso_roll[i], torso_yaw[i])
        ink(to, 'rotation_euler', f)
        for nm, sgn in (('arm_L', +1.0), ('arm_R', -1.0)):     # L arm goes back when the L foot leads
            o = ob.get(nm)
            if o is None:
                continue
            e = Euler(rest_rot[nm])
            e.x = rest_rot[nm].x + sgn * swing_arm[i] + sec[nm][i] + breath_arm[i]
            o.rotation_euler = e
            ink(o, 'rotation_euler', f)
        for nm in ('fist_L', 'cannon_R', 'launcher_L', 'launcher_R'):
            o = ob.get(nm)
            if o is None:
                continue
            e = Euler(rest_rot[nm])
            e.x = rest_rot[nm].x + sec[nm][i]
            o.rotation_euler = e
            ink(o, 'rotation_euler', f)

    # ---------------- events
    def fr_of(tsec):
        return int(round(tsec * fps)) + 1
    ev = dict(fps=fps, frame_start=1, frame_end=nfr, duration_s=round(D, 4),
              time_convention='time_s = (frame - 1) / fps; foot_down = first frame the foot is planted flat',
              step_length_m=round(pl['step_len'], 3), leg_length_m=round(rig.L, 3),
              foot_down=[], foot_lift=[], turn_steps=[], torso_turns=[], phases=[])
    for (tl, key, s) in landings:
        ev['foot_down'].append(dict(foot='foot_' + key, frame=fr_of(tl), time_s=round(tl, 4),
                                    phase=s['phase'], step=s['idx'], weight=1.0 if s['kind'] == 'walk' else 0.7))
        ev['foot_lift'].append(dict(foot='foot_' + key, frame=fr_of(s['t_lift']), time_s=round(s['t_lift'], 4),
                                    phase=s['phase'], step=s['idx']))
        if s['kind'] == 'turn':
            ev['turn_steps'].append(dict(foot='foot_' + key, start_frame=fr_of(s['t_lift']),
                                         land_frame=fr_of(tl), yaw_deg=round(math.degrees(s['to_yaw']), 1)))
    for k in ('foot_down', 'foot_lift'):
        ev[k].sort(key=lambda e: e['frame'])
    ev['turn_steps'].sort(key=lambda e: e['start_frame'])
    for sg in pl['torso']:
        ev['torso_turns'].append(dict(start_frame=fr_of(sg['t_start']), end_frame=fr_of(sg['t_end']),
                                      start_s=round(sg['t_start'], 4), end_s=round(sg['t_end'], 4),
                                      from_deg=sg['from_deg'], to_deg=sg['to_deg']))
    ev['torso_turn'] = dict(start_frame=ev['torso_turns'][0]['start_frame'],
                            end_frame=ev['torso_turns'][-1]['end_frame'])
    for nm, a, b in pl['phases']:
        ev['phases'].append(dict(name=nm, start_frame=fr_of(a), end_frame=fr_of(b)))
    ev['report'] = dict(max_ik_clamp_m=float(np.max(ik_err)), max_fk_err_m=float(np.max(fk_err)))

    dress_scene(args, p, sc, names, nfr, idx, focus_xy, cam_xy, shake, rig)

    sc.frame_start, sc.frame_end = 1, nfr
    sc.frame_set(1)
    return ev, dict(t=t, fS=fS, root_xy=root_xy, psi=psi, hip_z=hip_z, idx=idx, nfr=nfr, p=p, rig=rig, pl=pl)


# --------------------------------------------------------------------------- scene dressing
def make_floor_material(p_fade=(45.0, 150.0)):
    mat = bpy.data.materials.get('STAGE_floor_grid') or bpy.data.materials.new('STAGE_floor_grid')
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()

    def sock(node, name, kind='inputs'):
        for s in getattr(node, kind):
            if s.identifier == name:
                return s
        for s in getattr(node, kind):
            if s.name == name:
                return s
        raise KeyError(name)
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    bsdf = nt.nodes.new('ShaderNodeBsdfPrincipled')
    tc = nt.nodes.new('ShaderNodeTexCoord')
    brick = nt.nodes.new('ShaderNodeTexBrick')
    noise = nt.nodes.new('ShaderNodeTexNoise')
    ramp = nt.nodes.new('ShaderNodeValToRGB')
    brick.offset = 0.0
    brick.squash = 1.0
    sock(brick, 'Scale').default_value = 1.0 / 7.0
    sock(brick, 'Mortar Size').default_value = 0.006
    sock(brick, 'Mortar Smooth').default_value = 0.4
    sock(brick, 'Brick Width').default_value = 1.0
    sock(brick, 'Row Height').default_value = 1.0
    sock(brick, 'Color1').default_value = (0.070, 0.070, 0.072, 1)
    sock(brick, 'Color2').default_value = (0.055, 0.056, 0.058, 1)
    sock(brick, 'Mortar').default_value = (0.010, 0.010, 0.011, 1)
    sock(noise, 'Scale').default_value = 0.35
    sock(noise, 'Detail').default_value = 6.0
    ramp.color_ramp.elements[0].color = (0.55, 0.55, 0.55, 1)
    ramp.color_ramp.elements[1].color = (1.0, 1.0, 1.0, 1)
    nt.links.new(tc.outputs['Object'], sock(brick, 'Vector'))
    nt.links.new(tc.outputs['Object'], sock(noise, 'Vector'))
    nt.links.new(noise.outputs[0], ramp.inputs[0])
    base = sock(bsdf, 'Base Color')
    try:
        mix = nt.nodes.new('ShaderNodeMix')
        mix.data_type = 'RGBA'
        mix.blend_type = 'MULTIPLY'
        sock(mix, 'Factor_Float').default_value = 1.0
        nt.links.new(brick.outputs['Color'], sock(mix, 'A_Color'))
        nt.links.new(ramp.outputs['Color'], sock(mix, 'B_Color'))
        nt.links.new(sock(mix, 'Result_Color', 'outputs'), base)
    except Exception as e:                     # fall back: plain brick colour
        log('floor mix node failed, using plain bricks:', e)
        nt.links.new(brick.outputs['Color'], base)
    sock(bsdf, 'Roughness').default_value = 0.8
    # distance fade: far floor melts into the world colour (no black band at the horizon)
    bgc = (0.055, 0.06, 0.068, 1.0)
    try:
        w = bpy.context.scene.world
        bgn = next(n for n in w.node_tree.nodes if n.type == 'BACKGROUND')
        bgc = tuple(bgn.inputs[0].default_value)
    except Exception:
        pass
    try:
        geo = nt.nodes.new('ShaderNodeNewGeometry')
        xy = nt.nodes.new('ShaderNodeVectorMath')
        xy.operation = 'MULTIPLY'
        xy.inputs[1].default_value = (1.0, 1.0, 0.0)
        ln = nt.nodes.new('ShaderNodeVectorMath')
        ln.operation = 'LENGTH'
        mr = nt.nodes.new('ShaderNodeMapRange')
        mr.clamp = True
        mr.interpolation_type = 'SMOOTHSTEP'
        sock(mr, 'From Min').default_value = p_fade[0]
        sock(mr, 'From Max').default_value = p_fade[1]
        sock(mr, 'To Min').default_value = 0.0
        sock(mr, 'To Max').default_value = 1.0
        emi = nt.nodes.new('ShaderNodeEmission')
        sock(emi, 'Color').default_value = bgc
        sock(emi, 'Strength').default_value = 1.0
        msh = nt.nodes.new('ShaderNodeMixShader')
        nt.links.new(geo.outputs['Position'], xy.inputs[0])
        nt.links.new(xy.outputs[0], ln.inputs[0])
        nt.links.new(sock(ln, 'Value', 'outputs'), sock(mr, 'Value'))
        nt.links.new(sock(mr, 'Result', 'outputs'), msh.inputs[0])
        nt.links.new(bsdf.outputs[0], msh.inputs[1])
        nt.links.new(emi.outputs[0], msh.inputs[2])
        # ambient fill so the mid-distance floor never drops below the horizon colour (no dark ring)
        mr2 = nt.nodes.new('ShaderNodeMapRange')
        mr2.clamp = True
        mr2.interpolation_type = 'SMOOTHSTEP'
        sock(mr2, 'From Min').default_value = p_fade[0]
        sock(mr2, 'From Max').default_value = p_fade[1]
        sock(mr2, 'To Min').default_value = 0.85
        sock(mr2, 'To Max').default_value = 0.0
        emi2 = nt.nodes.new('ShaderNodeEmission')
        sock(emi2, 'Color').default_value = bgc
        add = nt.nodes.new('ShaderNodeAddShader')
        nt.links.new(sock(ln, 'Value', 'outputs'), sock(mr2, 'Value'))
        nt.links.new(sock(mr2, 'Result', 'outputs'), sock(emi2, 'Strength'))
        nt.links.new(msh.outputs[0], add.inputs[0])
        nt.links.new(emi2.outputs[0], add.inputs[1])
        nt.links.new(add.outputs[0], out.inputs[0])
    except Exception as e:
        log('floor fade failed, plain bsdf:', e)
        nt.links.new(bsdf.outputs[0], out.inputs[0])
    return mat


def dress_scene(args, p, sc, names, nfr, idx, focus_xy, cam_xy, shake, rig):
    # --- big floor with a panel grid (cue for the eye that the mech really moves)
    fl = bpy.data.objects.get(names['floor'])
    R = p['floor_radius']
    if fl is None:
        me = bpy.data.meshes.new('Floor')
        nv = 96
        vs = [(R * math.cos(2 * math.pi * i / nv), R * math.sin(2 * math.pi * i / nv), 0) for i in range(nv)]
        me.from_pydata(vs, [], [list(range(nv))])
        fl = bpy.data.objects.new(names['floor'], me)
        sc.collection.objects.link(fl)
    else:
        r0 = max(math.hypot(v.co.x, v.co.y) for v in fl.data.vertices)
        if r0 > 1e-6 and abs(r0 - R) > 1e-3:
            k = R / r0
            for v in fl.data.vertices:
                v.co.x *= k
                v.co.y *= k
    fl.data.update()
    fl.animation_data_clear()
    fl.data.materials.clear()
    fl.data.materials.append(make_floor_material(tuple(p['floor_fade'])))

    # --- hide leftover default scene objects that would disturb the lighting
    for nm in ('Light', 'Camera', 'Cube'):
        o = bpy.data.objects.get(nm)
        if o is not None and o is not fl:
            o.hide_render = True
            o.hide_viewport = True

    # --- light rig: lights follow the (smoothed) mech position, keep their relative placement
    old = bpy.data.objects.get('LightRig')
    if old:
        bpy.data.objects.remove(old, do_unlink=True)
    rigo = bpy.data.objects.new('LightRig', None)
    rigo.empty_display_type = 'PLAIN_AXES'
    sc.collection.objects.link(rigo)
    target = Vector((0, -0.7, 4.4))
    placement = {'Key': (6, -12, 12), 'Fill': (-12, -7, 5), 'Rim': (-4, 12, 10), 'Rim2': (10, 9, 6)}
    for nm in names['lights']:
        lo = bpy.data.objects.get(nm)
        if lo is None:
            continue
        lo.animation_data_clear()
        if nm in placement:
            lo.location = Vector(placement[nm])
        lo.parent = rigo
        lo.matrix_parent_inverse = Matrix.Identity(4)
        lo.rotation_euler = (target - lo.location).to_track_quat('-Z', 'Y').to_euler()
    f0 = focus_xy[0].copy()
    for fi in range(nfr):
        i = idx[fi]
        rigo.location = (focus_xy[i][0] - f0[0], focus_xy[i][1] - f0[1], 0.0)
        rigo.keyframe_insert('location', frame=fi + 1)

    # --- camera + focus empty
    old = bpy.data.objects.get('CamFocus')
    if old:
        bpy.data.objects.remove(old, do_unlink=True)
    foc = bpy.data.objects.new('CamFocus', None)
    foc.empty_display_type = 'SPHERE'
    foc.empty_display_size = 0.5
    sc.collection.objects.link(foc)
    cam = bpy.data.objects.get(names['camera'])
    if cam is None:
        cam = bpy.data.objects.new(names['camera'], bpy.data.cameras.new(names['camera']))
        sc.collection.objects.link(cam)
    cam.animation_data_clear()
    cam.parent = None
    cam.data.lens = p['cam_lens']
    cam.data.clip_start = 0.5
    cam.data.clip_end = 1500.0
    cam.data.dof.use_dof = False
    for c in list(cam.constraints):
        cam.constraints.remove(c)
    tr = cam.constraints.new('TRACK_TO')
    tr.target = foc
    tr.track_axis = 'TRACK_NEGATIVE_Z'
    tr.up_axis = 'UP_Y'
    sc.camera = cam
    for fi in range(nfr):
        i = idx[fi]
        f = fi + 1
        foc.location = (focus_xy[i][0], focus_xy[i][1], p['cam_target_z'])
        foc.keyframe_insert('location', frame=f)
        cam.location = (cam_xy[i][0], cam_xy[i][1], p['cam_height'] + shake[i])
        cam.keyframe_insert('location', frame=f)

    # --- render settings
    r = sc.render
    r.resolution_x, r.resolution_y = p['res']
    r.resolution_percentage = 100
    r.image_settings.file_format = 'PNG'
    r.image_settings.color_mode = 'RGB'
    r.film_transparent = False
    ee = sc.eevee
    for attr, val in (('taa_render_samples', p['samples']), ('use_raytracing', True), ('use_shadows', True)):
        if hasattr(ee, attr):
            try:
                setattr(ee, attr, val)
            except Exception as e:
                log('skip', attr, e)
    r.filepath = os.path.join(args.frames, 'f_')


# --------------------------------------------------------------------------- verification pass
def verify(ev, ctx, args):
    sc = bpy.context.scene
    rig = ctx['rig']
    fS = ctx['fS']
    idx = ctx['idx']
    nfr = ctx['nfr']
    co = np.hstack([rig.foot_co, np.ones((len(rig.foot_co), 1))])
    minz = {'L': np.zeros(nfr), 'R': np.zeros(nfr)}
    piv = {'L': np.zeros((nfr, 3)), 'R': np.zeros((nfr, 3))}
    for fi in range(nfr):
        sc.frame_set(fi + 1)
        dg = bpy.context.evaluated_depsgraph_get()
        for k in ('L', 'R'):
            o = rig.ob['foot_' + k].evaluated_get(dg)
            M = np.array(o.matrix_world)
            w = (M @ co.T).T
            minz[k][fi] = w[:, 2].min()
            piv[k][fi] = M[:3, 3]
    rep = {'min_sole_z_m': float(min(minz['L'].min(), minz['R'].min()))}
    drift = dev = 0.0
    for k in ('L', 'R'):
        planted = ~fS[k]['swing'][idx]
        d = np.linalg.norm(piv[k][:, :2] - fS[k]['xy'][idx], axis=1)
        drift = max(drift, float(d[planted].max()))
        dev = max(dev, float(np.abs(minz[k][planted]).max()))
    rep['max_planted_xy_drift_m'] = drift
    rep['max_planted_sole_z_dev_m'] = dev
    rep['max_swing_sole_height_m'] = float(max(minz['L'].max(), minz['R'].max()))
    chk = []
    for e in ev['foot_down']:
        k = e['foot'][-1]
        fi = e['frame'] - 1
        chk.append(dict(frame=e['frame'], foot=e['foot'], sole_z_at_frame=round(float(minz[k][fi]), 4),
                        sole_z_prev_frame=round(float(minz[k][fi - 1]), 4)))
    rep['foot_down_contact'] = chk
    ev['report'].update(rep)
    sc.frame_set(1)
    return rep


# --------------------------------------------------------------------------- entry
def main():
    argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    here = os.path.dirname(bpy.data.filepath) or os.getcwd()
    ap = argparse.ArgumentParser()
    ap.add_argument('--save', default=os.path.join(here, 'mech_walk_v2_anim.blend'))
    ap.add_argument('--events', default=os.path.join(here, 'renders', 'anim_events.json'))
    ap.add_argument('--frames', default=os.path.join(here, 'renders', 'frames'))
    ap.add_argument('--names', default=None, help='json {role: object name} overrides')
    ap.add_argument('--params', default=None, help='json overrides of the P dict')
    ap.add_argument('--no-verify', action='store_true')
    args = ap.parse_args(argv)
    src = os.path.realpath(bpy.data.filepath) if bpy.data.filepath else ''
    if src and os.path.realpath(args.save) == src:
        raise SystemExit('refusing to overwrite the source .blend; pass a different --save')
    ev, ctx = build(args)
    if not args.no_verify:
        rep = verify(ev, ctx, args)
        log('verify:', {k: v for k, v in rep.items() if k != 'foot_down_contact'})
    os.makedirs(os.path.dirname(args.events), exist_ok=True)
    with open(args.events, 'w') as fh:
        json.dump(ev, fh, indent=1)
    os.makedirs(args.frames, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=args.save)
    log('saved', args.save, '| events', args.events, '| frames', ev['frame_end'])


main()

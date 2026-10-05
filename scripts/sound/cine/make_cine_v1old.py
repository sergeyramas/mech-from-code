"""Soundtrack of mech_cinematic_v1.mp4, synthesised by code and synced to events.json.

  sounds/.venv/bin/python sounds/cine/make_cine.py [--no-mux]

Writes (relative to video/audio/):  cine_mix.wav (48 kHz stereo, -14 LUFS, TP <= -1 dBTP),
cine_sfx_stems/*.wav (float32 stems, sum == the pre-master mix), and the muxed mp4.
Frame -> seconds = (frame-1)/24; all event times are taken from events.json (render_s).
"""
import os
import sys
import json
import argparse
import subprocess
import numpy as np
from scipy import signal
from scipy.io import wavfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import fx                                   # noqa: E402
from fx import *                            # noqa: E402,F401,F403
import dsp                                  # noqa: E402

ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
EVENTS = os.path.join(ROOT, 'blender/renders/cine/events.json')
VIDEO_IN = os.path.join(ROOT, 'blender/renders/mech_cinematic_v1.mp4')
VIDEO_OUT = os.path.join(ROOT, 'blender/renders/mech_cinematic_v1_sound.mp4')
AUDIO = os.path.join(ROOT, 'video/audio')
ONE = os.path.join(ROOT, 'sounds/oneshots')
FFMPEG = '/opt/homebrew/bin/ffmpeg'
OUT_SR = 48000
TAIL = 3.0                      # seconds beyond the picture, trimmed at the end

ev = json.load(open(EVENTS))
DUR = ev['retime']['end_s'] + 0.0     # 42.759 (last frame time); video is 42.79 s
VID_DUR = 1027 / 24.0


def oneshot(name):
    sr, x = wavfile.read(os.path.join(ONE, name + '.wav'))
    x = x.astype(np.float64) / 32768.0
    return x if x.ndim == 1 else x.mean(1)


def nm(x, peak=1.0):
    return x / (np.max(np.abs(x)) + 1e-12) * peak


def slow(x, ratio):
    """tape-style playback at `ratio` speed (<1 = lower and longer)"""
    d = int(round(100 * ratio))
    return signal.resample_poly(x, 100, d, axis=0)


def db(v):
    return 10 ** (v / 20)


def far(x, dist):
    """distance: air absorption (lowpass) only; level is set by the caller"""
    return lp(x, float(np.clip(17000 / (1 + 0.1 * dist), 1800, 17000)), 2)


class Stem:
    def __init__(self, name):
        self.name = name
        self.buf = np.zeros((N(DUR + TAIL + 1.0), 2))

    def add(self, x, t, pan=0.0, gain=1.0, lpf=None):
        if lpf:
            x = lp(x, lpf, 2)
        if x.ndim == 1:
            x = pan2(x, pan)
        place(self.buf, x * gain, t)


stems = {k: Stem(k) for k in ['ambience', 'mech', 'weapons', 'explosions', 'debris', 'rocket', 'nuke', 'gen', 'gen_nuke']}
S_AMB, S_MECH, S_WPN, S_EXP, S_DEB, S_ROC, S_NUKE, S_GEN, S_GENN = [stems[k] for k in
                                                       ['ambience', 'mech', 'weapons', 'explosions', 'debris', 'rocket', 'nuke', 'gen', 'gen_nuke']]

R = {e['name']: e for e in ev['explosions']}
IM = {e['name']: e for e in ev['impacts']}
KM = ev['key_moments_render_s']
T_FLASH = KM['nuke_flash']                  # 31.836
T_IMPACT = KM['rocket_impact']              # 28.343
BT0, BT1 = ev['retime']['bullet_time']['ramp_start_s'], ev['retime']['bullet_time']['hold_end_s']


def pan_x(x, c=6.5, k=0.07):
    return float(np.clip((x - c) * k, -0.8, 0.8))


# =========================================================== 1. ambience (wind, distant rumble, fire)
def build_ambience():
    n = N(DUR + TAIL)
    d = DUR + TAIL
    w = fx.wind(d, 1.0)
    rum = np.stack([lp(brown(n), 75, 2), lp(brown(n), 75, 2)], 1)
    rum /= np.std(rum) + 1e-9
    amb = w * 0.055 + rum * 0.04
    # distant artillery thuds
    for tt_, g in [(2.7, 0.9), (6.6, 0.7), (11.9, 0.5), (18.4, 0.45), (24.1, 0.5), (36.2, 0.5), (40.0, 0.35)]:
        e = fx.explosion(2.2, 0.35, 3.0)
        e = lp(e, 380, 2)
        place(amb, e * g * 0.08, tt_)
    # burning truck: low flame roar + crackle from 10.1 to the flash, pan slightly right
    t0 = 10.1
    dd = T_FLASH - t0 + 0.2
    m = N(dd)
    tc = tt(m)
    flick = 0.7 + 0.3 * lp(white(m), 9, 1) / 0.12
    roar = tv_biquad(pink(m), 240 + 120 * np.sin(tc * 2), 0.8, 'bp', 256) * flick
    roar /= np.std(roar) + 1e-9
    crack = granular(dd, 55, 1200, 6000, (0.0015, 0.006), env=[(0, 0.3), (1.0, 1.0), (dd, 0.7)])
    crack_lp = lp(crack, 7000, 2)
    swell = np.minimum(tc / 0.8, 1)
    fire = (roar * 0.05 + crack_lp * 0.05) * swell
    place(amb, pan2(fire, 0.25), t0)
    # bullet time / flash / aftermath: tonal shaping of the whole bed
    t = tt(len(amb))
    g = curve(len(amb), [(0, 1.0), (BT0 - 0.15, 1.0), (BT0 + 0.3, 0.55), (BT1, 0.55), (BT1 + 0.2, 1.0), (T_FLASH - 0.05, 1.0),
                         (T_FLASH - 0.012, 0.0), (T_FLASH + 1.9, 0.0), (T_FLASH + 3.2, 0.55), (T_FLASH + 6.5, 0.9),
                         (d, 0.9)], smooth=False)
    fc = curve(len(amb), [(0, 9000), (BT0 - 0.1, 9000), (BT0 + 0.4, 450), (BT1, 450), (BT1 + 0.25, 9000), (T_FLASH + 3.2, 700),
                          (T_FLASH + 8, 1800), (d, 1800)], smooth=False)
    out = np.stack([tv_biquad(amb[:, c], fc, 0.7, 'lp', 512) for c in range(2)], 1) * g[:, None]
    S_AMB.add(out, 0.0, gain=1.0)


# =========================================================== 2. mech: steps, hydraulics, servos
STEP_LVL = {0: 0.30, 1: 0.38, 2: 0.52, 3: 0.72, 4: 0.92, 5: 1.0, 6: 1.0, 7: 0.9, 8: 0.9, 9: 0.9, 10: 1.0, 11: 1.0, 12: 1.0, 13: 1.0}
STEP_DIST = {0: 45, 1: 36, 2: 26, 3: 18, 4: 12, 5: 8, 6: 7}


def build_steps():
    steps_wav = [oneshot(f'step_{i}') for i in range(1, 5)]
    hh = oneshot('hydraulic_hiss')
    leg = oneshot('servo_leg')
    sk = 0
    for i, s in enumerate(ev['steps']):
        t = s['render_s']
        w = steps_wav[sk % 4]
        sk += 1
        # pitch +-3 %, level +-1.5 dB, alternate feet pan
        w = slow(w, rng.uniform(0.97, 1.03))
        lvl = STEP_LVL.get(i, 1.0) * db(rng.uniform(-1.5, 1.5))
        pan = -0.18 if s['foot'] == 'foot_L' else 0.18
        dist = STEP_DIST.get(i, 7)
        if i == 11:
            lvl *= 1.15   # step onto the jeep: heavier (the crush layer sits on top)
        S_MECH.add(far(w, dist) if dist > 12 else w, t, pan, 0.55 * lvl)
        S_MECH.add(far(hh, dist), t + rng.uniform(0.10, 0.16), pan * 0.5, 0.20 * lvl * (0.5 if i < 4 else 1))
        if i >= 3:
            S_MECH.add(far(leg, 10), t - 0.62, pan, 0.10 * lvl)
        # far steps also shake the ground: add a bit of extra sub with the loud ones
    # idle reactor hum + hydraulic pump bed (quiet) from the first close shot
    n = N(DUR)
    ph = 2 * np.pi * np.cumsum(np.full(n, 52.0) * (1 + 0.01 * np.sin(2 * np.pi * 0.4 * tt(n)))) / SR
    hum = (np.sin(ph) + 0.4 * np.sin(2 * ph) + 0.15 * np.sin(3 * ph)) * 0.012
    hum *= curve(n, [(0, 0), (3.0, 0.2), (5.0, 1.0), (T_FLASH - 0.4, 1.0), (T_FLASH - 0.05, 0.0)], smooth=False)
    hum *= curve(n, [(0, 1), (BT0, 1), (BT0 + 0.5, 0.35), (BT1, 0.35), (BT1 + 0.2, 1), (n / SR, 1)], smooth=False)
    S_MECH.add(hum, 0.0, 0.0, 1.0)


def servo_move(t0, dur, f_lo=150, f_hi=520, pan=0.0, gain=1.0, whine=0.4, creak_amt=0.2, stop_clunk=True):
    """servo for a joint move of given length: spin-up, plateau, spin-down, then a brake clunk"""
    head = min(0.3, dur * 0.3)
    tail_ = min(0.45, dur * 0.35)
    f_pts = [(0, f_lo * 0.6), (head, f_hi), (dur - tail_, f_hi * 1.05), (dur, f_lo)]
    vel = [(0, 0.1), (head, 1.0), (dur - tail_, 1.0), (dur, 0.1)]
    n = N(dur)
    sv = servo(dur, f_pts, harm=10, whine=whine, load=0.9, gear=0.8, vel_pts=vel)
    sv *= curve(n, [(0, 0), (min(0.18, head), 1), (dur - tail_, 1), (dur, 0)])
    cr = creak(dur, [(0, 10), (dur * 0.7, 45), (dur, 8)], 1050, [(0, 0), (dur * 0.3, 0.8), (dur - tail_, 0.6), (dur, 0)])
    hs = hiss(dur, [(0, 0), (0.3 * dur, 0.3), (dur - tail_, 0.2), (dur, 0)], ((0, 4500), (dur, 5200)))
    y = nm(sv * 0.5 + cr * creak_amt + hs * 0.05)
    S_MECH.add(y, t0, pan, 0.20 * gain)
    if stop_clunk:
        S_MECH.add(oneshot('servo_stop'), t0 + dur - 0.03, pan, 0.28 * gain)


def build_servos():
    # gun-arm raise while aiming (over-the-shoulder shot), 8.3-9.5
    servo_move(8.30, 1.15, 160, 420, pan=-0.30, gain=1.0)
    S_MECH.add(oneshot('hydraulic_hiss'), 9.50, -0.3, 0.2)
    # cannon recoil: piston stroke + settle
    S_MECH.add(hydraulic_piston(1.6, True, 0.6), 9.78, 0.0, 0.18)
    # slight torso correction toward the building / APC while the truck burns
    servo_move(14.05, 0.95, 120, 300, pan=0.2, gain=0.8)
    servo_move(15.55, 0.5, 140, 260, pan=-0.3, gain=0.6, stop_clunk=False)
    # SURPRISED TURN: pre-whine, sharp screech snapping at torso_snap, brake clunk
    ts = KM['torso_snap']      # 23.46
    pre = servo(0.4, [(0, 140), (0.4, 380)], harm=8, whine=0.4, load=0.8)
    pre *= curve(N(0.4), [(0, 0), (0.15, 1), (0.4, 1)])
    S_MECH.add(nm(pre), ts - 0.55, 0.0, 0.16)
    n = N(0.5)
    sc = creak(0.5, [(0, 95), (0.3, 180), (0.5, 120)], 2900, [(0, 0), (0.04, 1.0), (0.3, 0.9), (0.5, 0)])
    sc2 = tv_biquad(white(n), curve(n, [(0, 1800), (0.14, 5200), (0.5, 2600)]), 12, 'bp', 32)
    sc2 /= np.std(sc2) + 1e-9
    sw = servo(0.5, [(0, 300), (0.12, 1500), (0.5, 800)], harm=10, whine=0.9, load=0.4, gear=1.0, casing=False)
    env = curve(n, [(0, 0), (0.025, 1), (0.3, 0.8), (0.5, 0)])
    y = nm(sc * 0.5 + sc2 * 0.35 * env + sw * 0.45 * env) * env
    S_MECH.add(y, ts - 0.12, 0.0, 0.32)
    S_MECH.add(oneshot('servo_turn')[:N(0.9)], ts - 0.15, -0.1, 0.20)
    S_MECH.add(oneshot('servo_stop'), ts + 0.30, 0.0, 0.5)
    S_MECH.add(metal_hit(380, 1.0, 0.25, 1.4, PLATE, 7000, 1.0, sizzle=0.05), ts + 0.31, 0.0, 0.15)
    # arm raise to the sky (gun + rocket pod), 24.0 - 25.1
    servo_move(24.00, 1.05, 160, 480, pan=0.25, gain=0.9)
    S_MECH.add(oneshot('hydraulic_hiss'), 25.1, 0.2, 0.15)
    # death of the mech's drives after the rocket hit: falling whine
    n = N(2.6)
    f_pts = [(0, 700), (0.4, 520), (2.6, 35)]
    dw = servo(2.6, f_pts, harm=8, whine=0.5, load=0.5, gear=0.6)
    dw *= curve(n, [(0, 0), (0.06, 1), (1.8, 0.5), (2.6, 0)])
    S_MECH.add(dw, T_IMPACT + 0.1, 0.0, 0.16)
    S_MECH.add(far(hiss(1.6, [(0, 0), (0.02, 1), (0.3, 0.6), (1.6, 0)], ((0, 7000), (1.6, 2500))), 3), T_IMPACT + 0.08, 0.0, 0.20)


# =========================================================== 3. weapons
def build_weapons():
    # --- cannon shot (mech, close): crack + boom + recoil clank, landscape echoes
    t = KM['cannon_fire']
    e = fx.explosion(2.4, 1.3, 2.6)
    bang = hp(white(N(0.05)), 900, 2) * expdec(N(0.05), 0.006)
    boom = e + st2(np.pad(bang, (0, len(e) - len(bang))) * 0.8)
    boom = fx.echo_taps(boom, [(0.42, 0.28, 2500), (0.85, 0.16, 1500), (1.5, 0.08, 900)])
    S_WPN.add(nm(boom), t - 0.01, 0.0, 0.85)
    S_WPN.add(metal_hit(240, 1.0, 0.18, 1.4, PLATE, 6000, 1.0, sizzle=0.05), t + 0.02, 0.0, 0.25)   # breech clank
    S_WPN.add(metal_hit(900, 0.7, 0.12, 1.2, PLATE, 8000, 1.0, sizzle=0.0), t + 0.03, -0.1, 0.12)
    # shell flying: short crack-whistle
    n = N(0.07)
    sh = tv_biquad(white(n), curve(n, [(0, 4500), (0.07, 2500)]), 4, 'bp', 16) * np.hanning(n)
    S_WPN.add(nm(sh), t + 0.0, 0.0, 0.2)

    # --- missile salvo from the mech (04a_behind): launches, flights, impacts
    for i in range(4):
        m = IM[f'missile_{i}']
        tl = m['render_s'] - (m['story_s'] - m['launch_story_s'])        # launch time
        p0 = [-0.55, -0.45, -0.35, -0.25][i]
        S_WPN.add(nm(fx.missile_launch()), tl, p0, 0.62)
        fl = fx.missile_flight(m['render_s'] - tl, p0, pan_x(m['pos'][0]) * 0.8)
        S_WPN.add(nm(fl), tl + 0.05, 0, 0.45)
        S_WPN.add(nm(fx.whoosh_snap(0.3, 0.7)), m['render_s'] - 0.25, pan_x(m['pos'][0]) * 0.8, 0.15)   # incoming hiss at the end

    # --- APC bursts + armour sparks
    for key, pan in [('apc_burst_0', 0.55), ('apc_burst_1', 0.45), ('apc_burst_2', 0.4)]:
        b = IM[key]
        t0 = b['render_s']
        for k in range(b['shots']):
            tk = t0 + k * 0.105 + rng.normal(0, 0.003)
            sh = fx.autocannon_shot(rng.uniform(0.85, 1.0))
            S_WPN.add(sh, tk, pan, 0.55, lpf=9000 if key == 'apc_burst_0' else None)
            if key != 'apc_burst_0':
                S_WPN.add(armor_ping(), tk + 0.045, -0.05 + rng.uniform(-0.1, 0.1), 0.18 * rng.uniform(0.5, 1))
            else:
                S_WPN.add(armor_ping(), tk + 0.06, rng.uniform(-0.2, 0.2), 0.05)
        # slap-back echo of the whole burst
        n = N(0.105 * b['shots'] + 0.1)
        # (echo handled by reverb bus)
    # sparks shower on the armour around the jeep crush
    for tk in np.sort(rng.uniform(20.52, 21.0, 9)):
        S_WPN.add(armor_ping(), tk, rng.uniform(-0.2, 0.2), 0.10 * np.exp(-(tk - 20.5) * 2))

    # --- block kicks / push
    for key, pan in [('block_A_kick', 0.3), ('block_B_push', -0.3)]:
        t0 = IM[key]['render_s']
        m = N(1.0)
        th = thump(m, 120, 48, 0.03, 0.14) * 1.2 + lp(white(m), 2200, 2) * expdec(m, 0.04) * 0.8
        S_DEB.add(th, t0, pan, 0.8 if key == 'block_B_push' else 0.7)
        S_DEB.add(scrape(0.9 if key == 'block_B_push' else 0.45, 600, [(0, 1.0), (0.3, 0.8), (0.9, 0.1)], 0.8), t0 + 0.04, pan, 0.20)
        S_DEB.add(debris(1.6, 18, (0.15, 0.7, 0.15), (200, 1200), 1.0, 0.4), t0 + 0.08, 0.0, 0.5)


# =========================================================== 4. explosions
def build_explosions():
    def exp_at(name, gain, bright=1.0, tail=None, pan=None, echo=False, size=None):
        e = R[name]
        sz = size or (e['size'] if not isinstance(e['size'], str) else 5)
        y = fx.explosion(sz, bright, tail)
        if echo:
            y = fx.echo_taps(y, [(0.45, 0.22, 1800), (0.95, 0.12, 1000)])
        p = pan if pan is not None else pan_x(e['pos'][0], 18 if name.startswith('EXP_truck') else 6, 0.04)
        yy = nm(y)
        bal = np.array([np.cos((p + 1) * np.pi / 4), np.sin((p + 1) * np.pi / 4)]) * np.sqrt(2)
        place(S_EXP.buf, yy * bal * gain, e['render_s'])

    # truck: cannon shell hit (big), secondary, then small fire pops
    exp_at('EXP_truck', 1.0, 1.0, None, 0.0, echo=True)
    exp_at('EXP_truck2', 0.70, 0.9, None, 0.1)
    for k in range(17):
        name = f'EXP_truckfire_{k:02d}'
        e = R[name]
        tsec = e['render_s']
        # fireball whump (low) + puff; the slow-mo one at 29.5 is stretched
        gscale = 0.10 * (e['size'] / 1.6)
        if tsec > T_FLASH:
            continue
        y = nm(fx.explosion(e['size'] * 0.5, 0.35, 1.8))
        y = lp(y, 900, 2)
        if 28.3 < tsec < T_FLASH:
            y = slow(y, 0.5)
            gscale *= 0.8
        # a car is far back: attenuated, slightly right
        bal = np.array([np.cos(0.55 * np.pi / 4 * 1.0 + np.pi / 4 * 0.9), np.sin(0.55 * np.pi / 4 * 1.0 + np.pi / 4 * 0.9)]) * np.sqrt(2)
        place(S_EXP.buf, y * bal * gscale, tsec)
    # muzzle: already in weapons; salvo into the building
    for i in range(4):
        e = R[f'EXP_bld_{i}']
        exp_at(f'EXP_bld_{i}', 0.92, 1.0, 3.2, pan_x(e['pos'][0], 6.5, 0.07) * 0.8, echo=(i == 3))
    exp_at('EXP_bld_core', 1.0, 1.1, 5.5, -0.05, echo=True)
    # collapse: starts with the core, rolls for ~4 s
    c = fx.collapse(5.0, 1.1)
    S_DEB.add(nm(c), R['EXP_bld_core']['render_s'] + 0.1, 0.0, 0.62)
    # falling debris / dust rain afterwards
    S_DEB.add(debris(3.5, 70, (0.4, 0.3, 0.3), (400, 2400), 1.5, 0.5), R['EXP_bld_core']['render_s'] + 0.6, 0.0, 0.5)
    # truck wreck metal debris shower (after the shell)
    S_DEB.add(debris(2.8, 55, (0.7, 0.15, 0.15), (350, 2800), 1.3, 0.7, 0.5), 9.9, 0.1, 0.55)
    S_DEB.add(debris(2.0, 30, (0.7, 0.15, 0.15), (300, 2400), 1.3, 0.6, 0.4), 10.25, 0.15, 0.4)

    # jeep crush: foot slam + sheet-metal crunch + glass + tyre hiss
    t = IM['jeep_crush']['render_s']
    S_EXP.add(nm(fx.sheet_metal_crunch(1.4, 1.2)), t - 0.02, 0.0, 0.55)
    m = N(1.0)
    th = thump(m, 100, 36, 0.04, 0.2) * 1.2
    S_EXP.add(th, t, 0.0, 0.55)
    S_EXP.add(hiss(1.2, [(0, 0), (0.05, 1), (0.4, 0.5), (1.2, 0)], ((0, 5500), (1.2, 2500))), t + 0.1, 0.1, 0.07)
    S_EXP.add(nm(debris(2.0, 28, (0.8, 0.1, 0.1), (400, 3200), 1.0, 0.6)), t + 0.05, 0.0, 0.35)
    S_EXP.add(metal_hit(160, 1.2, 0.3, 1.5, PLATE, 5000, 1.0, sizzle=0.0), t, 0.0, 0.25)


# =========================================================== 5. rocket + bullet time + impact
def build_rocket():
    tl = IM['rocket_launch']['render_s']          # 22.5 (launch, 290 m away to the left)
    # distant launch
    ln = nm(fx.missile_launch(1.4))
    S_ROC.add(far(ln, 120), tl, -0.85, 0.08)
    # approach: whistle + roar rising until the camera lock-in at BT0
    d = BT0 - tl + 0.15
    ap = fx.rocket_approach(d)
    L = st2(ap)
    panc = curve(len(L), [(0, -0.85), (d * 0.6, -0.5), (d, 0.0)])
    ap_st = pan2(ap, panc)
    ap_st = ap_st * (curve(len(L), [(0, 0.18), (d, 1.0)]))[:, None] if False else ap_st
    S_ROC.add(ap_st, tl + 0.3, 0.0, 0.50)
    # bullet time: stretched drone + heartbeat + the whistle falling to a moan
    d2 = BT1 - BT0 + 0.5
    dr = fx.drone_bullet_time(d2)
    S_ROC.add(nm(dr) * 1.0, BT0 - 0.12, 0.0, 0.70)
    hb = fx.heartbeat(T_FLASH - BT0 - 0.4, [(0, 1.15), (BT1 - BT0, 0.85), (T_IMPACT - BT0 + 0.3, 1.1), (T_FLASH - BT0, 1.8)],
                      [(0, 0), (0.8, 0.5), (1.6, 0.9), (T_FLASH - BT0 - 0.6, 1.0)])
    S_ROC.add(hb, BT0 + 0.0, 0.0, 0.62)
    # speed snap-back: sharp whoosh peaking right before the hit
    wh = fx.whoosh_snap(0.34, 1.0)
    S_ROC.add(nm(wh), BT1 - 0.02, 0.0, 0.62)
    S_ROC.add(nm(fx.rocket_approach(0.5)), T_IMPACT - 0.45, 0.0, 0.25)

    # chest impact (slow-mo 0.2x aftermath): heavy metal + blast pitched down
    t = T_IMPACT
    ex = nm(fx.explosion(5.0, 0.9, 4.0))
    ex_slow = slow(ex, 0.55)
    S_ROC.add(nm(ex_slow), t, 0.0, 0.95)
    S_ROC.add(nm(ex[:N(1.2)]), t, 0.0, 0.45)
    hit = metal_hit(150, 3.0, 0.8, 1.5, PLATE, 5500, 1.0, sizzle=0.0)
    S_ROC.add(slow(hit, 0.7), t, 0.0, 0.50)
    hit2 = metal_hit(420, 3.0, 0.5, 1.2, PLATE, 6000, 1.0, sizzle=0.0)
    S_ROC.add(slow(hit2, 0.6), t + 0.01, -0.1, 0.30)
    S_ROC.add(nm(debris(3.2, 70, (0.75, 0.15, 0.1), (200, 1500), 0.6, 0.8, 0.8)), t + 0.05, 0.0, 0.52)
    # slow-mo shards: pitched-down ricochet zings (sparks flying in slow motion)
    for k in range(16):
        tk = t + 0.12 + 2.9 * rng.random() ** 1.3
        z = slow(armor_ping(rng.uniform(1600, 3800)), 0.4)
        S_ROC.add(z, tk, rng.uniform(-0.8, 0.8), 0.12 * np.exp(-(tk - t) / 2.4))
    # creak of tearing steel stretched in slow motion
    S_ROC.add(slow(creak(1.6, [(0, 6), (1.6, 14)], 520, [(0, 0), (0.4, 1), (1.6, 0)]), 0.5), t + 0.3, -0.2, 0.15)
    S_ROC.add(slow(creak(1.6, [(0, 5), (1.6, 11)], 380, [(0, 0), (0.6, 1), (1.6, 0)]), 0.5), t + 1.4, 0.3, 0.14)
    # rising tension towards the flash
    d3 = T_FLASH - (T_IMPACT + 1.0) - 0.03
    n = N(d3)
    tt_ = tt(n)
    f = curve(n, [(0, 55), (d3, 520)])
    ph = 2 * np.pi * np.cumsum(f) / SR
    ris = (np.sin(ph) + 0.5 * signal.sawtooth(ph * 1.005)) * (tt_ / d3) ** 2.2
    ris = lp(ris, 1400, 2)
    S_ROC.add(pan2(ris, 0.0), T_IMPACT + 1.0, 0.0, 0.12)


# =========================================================== 6. the nuke
def build_nuke():
    tf = T_FLASH
    # tinnitus: starts at the flash, fades over 3.4 s
    S_NUKE.add(nm(fx.tinnitus(3.6)), tf - 0.01, 0.0, 0.045)
    # a fraction of cotton-wool low pressure under the silence
    n = N(1.2)
    S_NUKE.add(nm(lp(brown(n), 60, 2)) * curve(n, [(0, 0), (0.3, 1), (1.2, 0.3)]), tf, 0.0, 0.10)
    # sub boom when the shock front reaches the camera
    TB = tf + 0.8
    sb = fx.sub_boom(5.0)
    S_NUKE.add(nm(sb), TB, 0.0, 1.0)
    crack = nm(fx.explosion(9.0, 0.45, 6.5))
    S_NUKE.add(crack, TB - 0.02, 0.0, 0.95)
    # rolling rumble of the shock wave
    S_NUKE.add(nm(fx.rolling_rumble(7.0, 1.0)), TB + 0.1, 0.0, 0.95)
    # parts and debris clatter after the wave
    S_NUKE.add(nm(debris(5.5, 120, (0.55, 0.25, 0.2), (180, 2200), 1.0, 0.9, 0.95, 7000)), TB + 0.35, 0.0, 0.62)
    for k in range(18):
        tk = TB + 0.8 + 4.6 * rng.random() ** 1.1
        m = N(1.2)
        f0 = rng.uniform(120, 420)
        y = metal_hit(f0, 1.4, rng.uniform(0.15, 0.5), 1.4, PLATE, 5500, 1.0, sizzle=0.0)
        y = lp(y, 5500, 2)
        th = thump(m, 90, 40, 0.03, 0.2) * 0.8
        y[:len(th)] += th * 0.7
        S_NUKE.add(y, tk, rng.uniform(-0.85, 0.85), 0.30 * np.exp(-(tk - TB) / 3.8))
    # long low rumble under the mushroom cloud (35.26 -> end)
    tm = ev['retime']['wide']['start_s']
    dm = VID_DUR - tm + 0.3
    S_NUKE.add(nm(fx.tremble_rumble(dm + 0.0, 1.0)), tm - 1.0, 0.0, 0.60)
    # distant crumbling after the cloud rises
    S_NUKE.add(nm(debris(5.0, 28, (0.3, 0.5, 0.2), (150, 900), 2.5, 0.8, 0.9, 3500)), tm + 0.8, 0.0, 0.14)


# =========================================================== generated (ElevenLabs SFX) layers
GEN = os.path.join(ROOT, 'video/audio/gen_sfx')


def gen_load(name):
    sr, x = wavfile.read(os.path.join(GEN, name + '.wav'))
    x = x.astype(np.float64) / 32768.0
    return x if x.ndim == 2 else np.stack([x, x], 1)


def gen_onset(x, mode='first'):
    m = np.abs(x).mean(1)
    e = uniform_env(m, N(0.005))
    return (np.argmax(e > 0.25 * e.max()) if mode == 'first' else int(np.argmax(e))) / SR


def uniform_env(m, w):
    return np.sqrt(np.convolve(m ** 2, np.ones(w) / w, mode='same'))


def build_generated():
    """generated layers sit UNDER the code-made hits (they add weight); aligned by their detected onset / peak"""
    for name, t, g, stem in [('explosion_big', 9.8, 0.40, S_GEN), ('building_collapse', R['EXP_bld_core']['render_s'], 0.34, S_GEN),
                             ('metal_impact_heavy', T_IMPACT, 0.45, S_GEN), ('nuke_boom', T_FLASH + 0.8, 0.55, S_GENN)]:
        x = nm(gen_load(name))
        stem.add(x, t - gen_onset(x), 0.0, g)
    x = nm(gen_load('rocket_flyby'))
    S_GEN.add(x, BT0 - 0.1 - gen_onset(x, 'peak'), 0.0, 0.30)


# =========================================================== mix / master
def reverb_bus(buf, ir, wet):
    n = len(buf)
    out = np.zeros((n + len(ir) - 1, 2))
    for c in range(2):
        out[:, c] = signal.fftconvolve(buf[:, c], ir[:, c])
    return out[:n] * wet


def duck_curve(n, hits, rel=0.8, att=0.004):
    """multiplicative gain (1 = no duck): dips by `dB` at each (t, dB) hit, ~5 ms attack, exponential recovery"""
    g = np.ones(n)
    for t0, dbv in hits:
        i = int(t0 * SR)
        k = np.arange(0, int(rel * 5 * SR))
        depth = 1 - db(-dbv)
        d = depth * np.exp(-k / (rel * SR)) * np.minimum(k / (att * SR), 1)
        e = min(n, i + len(k))
        g[i:e] = np.minimum(g[i:e], 1 - d[:e - i])
    return g


def gate_curve(n):
    """silence before the flash: everything except the nuke stem is cut in 36 ms and returns slowly"""
    return curve(n, [(0, 1.0), (T_FLASH - 0.05, 1.0), (T_FLASH - 0.012, 0.0), (T_FLASH + 1.0, 0.0), (T_FLASH + 1.5, 0.35),
                     (T_FLASH + 3.2, 0.8), (T_FLASH + 5.0, 1.0), (60, 1.0)], smooth=False)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--no-mux', action='store_true')
    ap.add_argument('--target', type=float, default=-14.0)
    a = ap.parse_args()
    os.makedirs(os.path.join(AUDIO, 'cine_sfx_stems'), exist_ok=True)
    print('building ...')
    build_ambience(); print(' ambience')
    build_steps(); build_servos(); print(' mech')
    build_weapons(); print(' weapons')
    build_explosions(); print(' explosions')
    build_rocket(); print(' rocket')
    build_nuke(); print(' nuke')
    build_generated(); print(' generated')

    nout = N(VID_DUR)
    ir_big = make_ir(2.4, 0.03, (1.3, 1.0, 0.35))
    ir_small = make_ir(1.0, 0.015, (1.2, 1.0, 0.4))
    wet = dict(ambience=0.0, mech=0.10, weapons=0.20, explosions=0.22, debris=0.15, rocket=0.20, nuke=0.15, gen=0.10, gen_nuke=0.0)
    gain = dict(ambience=1.0, mech=1.0, weapons=1.0, explosions=1.0, debris=1.0, rocket=1.0, nuke=1.0)
    gate = gate_curve(len(S_AMB.buf))
    gated = {'ambience': False, 'mech': True, 'weapons': True, 'explosions': True, 'debris': True, 'rocket': True, 'nuke': False, 'gen': True, 'gen_nuke': False}
    duck = duck_curve(len(S_AMB.buf), [(KM['cannon_fire'] - 0.01, 8.0), (R['EXP_bld_0']['render_s'], 4.0), (R['EXP_bld_core']['render_s'], 8.0),
                                      (KM['jeep_crush'], 6.0), (T_IMPACT, 9.0)] +
                      [(R[f'EXP_bld_{i}']['render_s'], 4.0) for i in range(1, 4)], rel=0.9)
    ducked = {'ambience': 1.0, 'mech': 0.8, 'debris': 0.0, 'weapons': 0.0, 'explosions': 0.0, 'rocket': 0.0, 'nuke': 0.0, 'gen': 0.0, 'gen_nuke': 0.0}
    proc = {}
    for k, s in stems.items():
        b = s.buf.copy()
        if wet[k] > 0:
            b = b + reverb_bus(b, ir_big if k in ('explosions', 'weapons', 'rocket', 'nuke', 'debris', 'gen') else ir_small, wet[k])
        if gated[k]:
            b *= gate[:, None]
        if ducked[k]:
            b *= (1 - ducked[k] * (1 - duck))[:, None]
        proc[k] = b
    total = sum(proc.values())
    # master: HP 20 Hz, gentle glue compression, low-shelf trim, loudness-match with look-ahead limiter
    hp20 = signal.butter(2, 20, 'highpass', fs=SR, output='sos')
    total = signal.sosfilt(hp20, total, axis=0)
    total = total[:N(VID_DUR) + N(0.5)]
    total = fx.compress(total, -20.0, 1.6, 0.03, 0.4)
    # fade tail
    nf = N(1.4)
    seg = total[:nout]
    seg[-nf:] *= (0.5 + 0.5 * np.cos(np.linspace(0, np.pi, nf)))[:, None] ** 1.2
    seg48 = signal.resample_poly(seg, 160, 147, axis=0)
    def master(g):
        up = signal.resample_poly(seg48 * g, 4, 1, axis=0)             # 192 kHz: limit inter-sample peaks too
        up = fx.limiter(up, -1.4, 0.003, 0.10, sr=OUT_SR * 4)
        return np.clip(signal.resample_poly(up, 1, 4, axis=0), -0.95, 0.95)
    g = 1.0
    for it in range(8):
        y48 = master(g)
        L = fx.lufs(y48, OUT_SR)
        tp = fx.true_peak_db(y48, OUT_SR)
        err = a.target - L
        print(f'  iter {it}: gain {20*np.log10(g):+.2f} dB -> {L:.2f} LUFS, tp {tp:.2f}')
        if abs(err) < 0.08 and tp <= -1.0:
            break
        g *= 10 ** (err / 20)
    wavfile.write(os.path.join(AUDIO, 'cine_mix.wav'), OUT_SR, (y48 * 32767).astype(np.int16))
    # stems: same linear gain, no limiter (float32), so they sum to the pre-limiter mix
    lin = g
    for k in stems:
        b = proc[k]
        b = signal.sosfilt(hp20, b, axis=0)[:nout] * lin
        b48 = signal.resample_poly(b, 160, 147, axis=0).astype(np.float32)
        wavfile.write(os.path.join(AUDIO, 'cine_sfx_stems', f'{k}.wav'), OUT_SR, b48)
    print('mix written', y48.shape, 'LUFS', fx.lufs(y48, OUT_SR), 'TP', fx.true_peak_db(y48, OUT_SR))
    if not a.no_mux:
        mux()


def mux():
    cmd = [FFMPEG, '-y', '-v', 'error', '-i', VIDEO_IN, '-i', os.path.join(AUDIO, 'cine_mix.wav'),
           '-map', '0:v:0', '-map', '1:a:0', '-c:v', 'copy', '-c:a', 'aac', '-b:a', '256k', '-ar', '48000',
           '-t', f'{VID_DUR:.4f}', '-movflags', '+faststart', VIDEO_OUT]
    subprocess.run(cmd, check=True)
    print('muxed ->', VIDEO_OUT)


if __name__ == '__main__':
    main()

"""Voices (source-filter), animals, ground/body foley. All procedural."""
import numpy as np
from dsp import *


# ======================= glottal source + formant filter =======================
def glottal(n, f0, tn=0.12, tp=0.40, jitter=0.01, shimmer=0.05, vib_rate=5.5, vib_depth=0.015,
            sub=0.0, rough_hz=0.0, rough_depth=0.0, breath=0.05, vamp=1.0):
    t = tt(n)
    j = lp(white(n), 40, 2)
    j /= np.std(j) + 1e-9
    vib = 1 + vib_depth * np.sin(2 * np.pi * vib_rate * t + rng.uniform(0, 6.28))
    f = np.maximum(f0 * vib * (1 + jitter * j), 20)
    if sub > 0:
        ph2 = np.cumsum(f / 2) / SR
        p = (2 * ph2) % 1
        alt = np.floor(2 * ph2) % 2
        amp_alt = 1 - sub * alt
    else:
        p = (np.cumsum(f) / SR) % 1
        amp_alt = 1.0
    g = np.where(p < tp, 0.5 * (1 - np.cos(np.pi * p / tp)),
                 np.where(p < tp + tn, np.cos(np.pi / 2 * (p - tp) / tn), 0.0))
    d = np.diff(g, prepend=0) * SR / f
    sh = 1 + shimmer * lp(white(n), 30, 2) / 0.2
    src = d * amp_alt * sh
    if rough_hz > 0:
        rj = 1 + 0.2 * lp(white(n), 8, 1) / 0.2
        ph = np.cumsum(rough_hz * rj) / SR
        src = src * (1 - rough_depth * (0.5 + 0.5 * np.sin(2 * np.pi * ph)))
    src = lp(src, 9000, 1)
    src /= np.std(src) + 1e-9
    va = curve(n, vamp)
    br = curve(n, breath)
    nz = hp(white(n), 500, 1)
    nz /= np.std(nz)
    nz *= (0.4 + 0.6 * np.clip(g, 0, 1) / (np.max(g) + 1e-9))
    return src * va + nz * br


VOW = {  # adult male, Hz
    'a': (730, 1090, 2440, 3400, 4300), 'o': (500, 870, 2500, 3400, 4300),
    'e': (550, 1750, 2500, 3400, 4300), 'u': (330, 800, 2400, 3400, 4300),
    'i': (300, 2200, 2900, 3500, 4300), 'ae': (660, 1720, 2410, 3400, 4300),
    'schwa': (500, 1400, 2400, 3300, 4200),
}
BW = (70, 100, 140, 220, 320)
GN = (1.0, 0.75, 0.42, 0.28, 0.18)


def voice(dur, f0, F, bw_scale=1.0, gains=GN, bw=BW, drive=1.0, amp=None, block=96, low_boost=0.0, **gl):
    n = N(dur)
    f0c = curve(n, f0)
    src = glottal(n, f0c, **gl)
    out = np.zeros(n)
    for k, Fk in enumerate(F):
        fc = curve(n, Fk)
        q = fc / (bw[k] * bw_scale)
        out += gains[k] * tv_biquad(src, fc, q, 'bp', block)
    if low_boost:
        out += low_boost * lp(src, 280, 2)
    out /= np.std(out) + 1e-9
    if drive != 1.0:
        out = np.tanh(out * drive * 0.8) / np.tanh(drive * 0.8)
    if amp is not None:
        out = out * curve(n, amp)
    return out


def vf(vow, scale=1.0, to=None, dur=1.0, t_morph=None):
    """formant list (curves) for vowel with optional morph."""
    a = np.array(VOW[vow]) * scale
    if to is None:
        return [float(x) for x in a]
    b = np.array(VOW[to]) * scale
    tm = t_morph if t_morph is not None else dur * 0.4
    return [[(0, a[i]), (tm, b[i]), (dur, b[i])] for i in range(5)]


# ======================= human male voices =======================
def shout_a(dur=2.2, f0=130, scale=1.0, vowel='a', intensity=1.0):
    """Sustained battle cry 'AAA!': pressed phonation, rising pitch, vibrato, noise, strain."""
    F = vf(vowel, scale * 1.06)
    F[0] = [(0, 520 * scale), (0.12, 800 * scale), (dur, 760 * scale)]
    pts = [(0, f0 * 0.82), (0.12, f0 * 1.18), (0.45 * dur, f0 * 1.22), (0.8 * dur, f0 * 1.1), (dur, f0 * 0.88)]
    amp = [(0, 0), (0.03, 0.9), (0.15, 1.0), (dur * 0.8, 0.85), (dur, 0.0)]
    return voice(dur, pts, F, bw_scale=1.4, tn=0.06, jitter=0.012, shimmer=0.1, vib_rate=5.8,
                 vib_depth=0.02, rough_hz=70, rough_depth=0.12 * intensity, breath=[(0, 0.25), (0.2, 0.12), (dur, 0.2)],
                 drive=2.0 * intensity, amp=amp)


def shout_ha(dur=0.5, f0=140, scale=1.0, intensity=1.0):
    F = vf('a', scale)
    pts = [(0, f0 * 1.05), (0.1, f0 * 1.2), (dur, f0 * 0.8)]
    return voice(dur, pts, F, bw_scale=1.3, tn=0.07, jitter=0.012, breath=[(0, 1.2), (0.08, 1.0), (0.14, 0.12), (dur, 0.15)],
                 vamp=[(0, 0), (0.07, 0.05), (0.13, 1.0), (0.3, 0.7), (dur, 0)], drive=2.2 * intensity,
                 amp=[(0, 0.4), (0.06, 1.0), (0.25, 0.8), (dur, 0.0)])


def grunt_effort(dur=0.25, f0=105, scale=1.0):
    F = vf('schwa', scale)
    return voice(dur, [(0, f0 * 1.1), (dur, f0 * 0.75)], F, bw_scale=1.5, tn=0.1, jitter=0.03, breath=0.25,
                 sub=0.2, drive=1.8, amp=[(0, 0), (0.02, 1.0), (dur * 0.5, 0.7), (dur, 0)])


def groan(dur=1.0, f0=125, scale=1.0, vowel='o'):
    F = vf(vowel, scale, to='u', dur=dur)
    pts = [(0, f0 * 1.05), (0.3 * dur, f0 * 1.0), (dur, f0 * 0.68)]
    return voice(dur, pts, F, bw_scale=1.2, tn=0.15, jitter=0.02, breath=[(0, 0.1), (dur, 0.3)], vib_depth=0.03,
                 vib_rate=4.8, sub=[(0, 0.0), (dur, 0.3)][0] if False else 0.1, drive=1.4,
                 amp=[(0, 0), (0.08, 0.9), (0.6 * dur, 0.8), (dur, 0)])


def pain_scream(dur=1.3, f0=240, scale=1.0):
    F = vf('ae', scale * 1.12, to='a', dur=dur)
    pts = [(0, f0 * 0.9), (0.1, f0 * 1.5), (0.4 * dur, f0 * 1.7), (dur, f0 * 0.95)]
    return voice(dur, pts, F, bw_scale=1.3, tn=0.05, jitter=0.02, vib_depth=0.04, vib_rate=6.5, rough_hz=60,
                 rough_depth=0.2, breath=0.2, drive=2.4, amp=[(0, 0), (0.03, 1.0), (dur * 0.7, 0.9), (dur, 0)])


# ======================= animals =======================
def boar_grunt(dur=0.32, f0=105, power=1.0):
    F = [[(0, 430), (dur, 520)], [(0, 1250), (dur, 950)], 2300, 3300, 4200]
    return voice(dur, [(0, f0 * 1.2), (dur * 0.35, f0), (dur, f0 * 0.7)], F, bw_scale=1.8, tn=0.16, jitter=0.04,
                 shimmer=0.2, sub=0.3, rough_hz=48, rough_depth=0.4, breath=0.35, drive=2.2 * power,
                 amp=[(0, 0), (0.015, 1), (dur * 0.5, 0.75), (dur, 0)], low_boost=0.25)


def boar_squeal(dur=1.1, f0=1500):
    F = [[(0, 700), (dur, 950)], 2300, 3600, 4800, 6200]
    pts = [(0, f0 * 0.4), (0.10 * dur, f0 * 1.15), (0.35 * dur, f0), (0.7 * dur, f0 * 0.82), (dur, f0 * 0.45)]
    return voice(dur, pts, F, bw_scale=1.0, tn=0.2, jitter=0.035, shimmer=0.15, vib_rate=9, vib_depth=0.05,
                 sub=0.12, rough_hz=90, rough_depth=0.25, breath=[(0, 0.2), (dur, 0.35)], drive=1.6,
                 amp=[(0, 0), (0.02, 1), (dur * 0.7, 0.9), (dur, 0)], gains=(1.0, 0.9, 0.6, 0.4, 0.25))


def boar_snort(dur=0.2):
    n = N(dur)
    x = white(n)
    fc = curve(n, [(0, 900), (dur, 500)])
    y = tv_biquad(x, fc, 1.5, 'bp') + 0.7 * tv_biquad(x, curve(n, [(0, 2400), (dur, 1600)]), 2.0, 'bp')
    y *= adsr(n, 0.01, 0.05, 0.4, 0.08)
    return y / (np.std(y) + 1e-9) * 0.8


def bear_growl(dur=2.0, f0=62, power=1.0):
    F = [[(0, 300), (dur / 2, 380), (dur, 320)], [(0, 700), (dur / 2, 850), (dur, 750)], 1500, 2300, 3100]
    pts = [(0, f0 * 0.95), (dur * 0.5, f0 * 1.15), (dur, f0 * 0.85)]
    return voice(dur, pts, F, bw_scale=1.8, tn=0.1, jitter=0.05, shimmer=0.2, sub=0.5, rough_hz=26, rough_depth=0.75,
                 breath=0.18, drive=2.4 * power, vib_depth=0.04, vib_rate=3.5,
                 amp=[(0, 0), (0.2, 0.7), (dur * 0.5, 1.0), (dur * 0.9, 0.6), (dur, 0)], low_boost=0.3)


def bear_roar(dur=2.3, f0=75, power=1.0):
    F = [[(0, 380), (0.2 * dur, 700), (0.6 * dur, 640), (dur, 420)],
         [(0, 900), (0.2 * dur, 1300), (0.6 * dur, 1200), (dur, 850)],
         [(0, 1700), (0.3 * dur, 2000), (dur, 1700)], 2900, 3800]
    pts = [(0, f0 * 0.8), (0.12 * dur, f0 * 1.25), (0.4 * dur, f0 * 1.35), (0.75 * dur, f0 * 1.1), (dur, f0 * 0.7)]
    amp = [(0, 0), (0.05, 0.6), (0.18 * dur, 1.0), (0.7 * dur, 0.95), (dur, 0)]
    main = voice(dur, pts, F, bw_scale=1.7, tn=0.08, jitter=0.05, shimmer=0.18, sub=0.45, rough_hz=32,
                 rough_depth=0.6, breath=[(0, 0.3), (dur, 0.35)], drive=2.8 * power, vib_depth=0.03, vib_rate=4.2,
                 amp=amp, low_boost=0.25)
    # upper throat layer (chaotic, harsher)
    thr = voice(dur, [(t, v * 2.03) for t, v in pts], F, bw_scale=2.0, tn=0.06, jitter=0.09, rough_hz=57,
                rough_depth=0.5, breath=0.5, drive=3.0, amp=amp)
    n = N(dur)
    hiss = tv_biquad(white(n), curve(n, [(0, 1800), (dur, 1200)]), 0.8, 'bp') * curve(n, amp) * 0.5
    chest = lp(main, 160, 2) * 0.5
    return main + 0.35 * thr + 0.22 * hiss / (np.std(hiss) + 1e-9) + chest


def bear_huff(dur=0.35):
    n = N(dur)
    x = lp(white(n), 1800, 2)
    y = x * adsr(n, 0.02, 0.08, 0.35, 0.15)
    return y / (np.std(y) + 1e-9) * 0.7


# ======================= ground & body foley =======================
def thump(n, f1, f2, tau_f, tau_a, atk=0.002):
    t = tt(n)
    f = f2 + (f1 - f2) * np.exp(-t / tau_f)
    ph = 2 * np.pi * np.cumsum(f) / SR
    return np.sin(ph) * np.exp(-t / tau_a) * (1 - np.exp(-t / atk))


def granular(dur, density, f_lo, f_hi, grain=(0.004, 0.014), env=None):
    n = N(dur)
    out = np.zeros(n)
    k = int(density * dur)
    for _ in range(k):
        gl = max(16, N(rng.uniform(*grain)))
        pos = rng.integers(0, max(1, n - gl))
        g = white(gl) * np.hanning(gl)
        g = bp(g, rng.uniform(f_lo, f_lo * 1.5), rng.uniform(f_hi * 0.6, f_hi))
        out[pos:pos + gl] += g * rng.uniform(0.2, 1.0)
    if env is not None:
        out *= curve(n, env)
    return out


def hoof(w=1.0):
    n = N(0.5)
    a = thump(n, 150, 70, 0.012, 0.05 * w ** 0.5) * 1.0 * w
    b = bp(white(n), 700, 3500) * expdec(n, 0.02) * 0.9
    tick = hp(white(n), 2800, 2) * expdec(n, 0.004) * 0.5
    low = lp(white(n), 250, 2) * expdec(n, 0.07) * 0.8 * w
    gr = granular(0.12, 500, 1500, 5000, (0.002, 0.006), env=[(0, 1), (0.12, 0)])
    out = a + b + tick + low
    out[:len(gr)] += gr * 0.5
    return out * rng.uniform(0.85, 1.1)


def ground_step(w=1.0, hard=0.5):
    """body-weight footfall on earth: boom + dirt grit"""
    n = N(0.8)
    boom = thump(n, 90 / w ** 0.3, 38 / w ** 0.3, 0.04, 0.16 * w ** 0.5) * w
    low = lp(brown(n), 140, 2) * expdec(n, 0.18) * 1.2 * w
    grit = granular(0.25, 700, 600, 4000, (0.003, 0.012), env=[(0, 1), (0.06, .7), (0.25, 0)])
    crunch = bp(white(n), 500, 2500) * expdec(n, 0.03) * (0.4 + hard)
    out = boom + low + crunch
    out[:len(grit)] += grit * (0.5 + hard)
    return out * rng.uniform(0.9, 1.1)


def human_step(hard=0.5):
    n = N(0.35)
    a = thump(n, 120, 55, 0.02, 0.05) * 0.8
    g = granular(0.14, 600, 800, 5000, (0.002, 0.008), env=[(0, 1), (0.14, 0)])
    b = bp(white(n), 400, 2200) * expdec(n, 0.025) * (0.5 + hard * 0.4)
    out = a + b
    out[:len(g)] += g * 0.7
    return out * rng.uniform(0.8, 1.15)


def body_hit(w=1.0, crack=0.5):
    n = N(0.8)
    t = tt(n)
    a = thump(n, 130, 40, 0.05, 0.16 * w ** 0.5, atk=0.003) * 1.3 * w
    b = lp(white(n), 900, 2) * expdec(n, 0.05) * 0.8
    c = bp(white(n), 1500, 4500) * expdec(n, 0.012) * crack
    d = bp(white(n), 200, 1800) * expdec(n, 0.14) * 0.3 * (1 - np.exp(-t / 0.01))
    return (a + b + c + d) * rng.uniform(0.9, 1.1)


def whoosh(dur=0.4, f_lo=400, f_hi=2500, peak=0.5):
    n = N(dur)
    fc = curve(n, [(0, f_lo), (dur * peak, f_hi), (dur, f_lo * 1.5)])
    y = tv_biquad(white(n), fc, 1.2, 'bp')
    e = np.sin(np.pi * np.clip(np.arange(n) / n, 0, 1) ** 0.8) ** 2
    return y * e / (np.std(y) + 1e-9)


def paw_swipe(w=1.0):
    wh = whoosh(0.4, 300, 1800, 0.55) * 0.7
    n = N(1.0)
    hit = body_hit(w * 0.9, 0.6)
    claw = np.zeros(n)
    for k in range(3):
        c = hp(white(N(0.08)), 3000, 2) * expdec(N(0.08), 0.015) * 0.5
        place(claw, c, 0.0 + k * 0.012)
    out = np.zeros(n)
    place(out, wh, 0)
    place(out, hit, 0.3)
    place(out, claw, 0.27)
    return out


def tusk_clack():
    n = N(0.15)
    ir = modal_ir([1300, 2150, 3400, 5100], [1, .8, .5, .3], [0.03, 0.02, 0.012, 0.008], 0.15)
    return excite(ir, burst(0.001, 12000)) * 3 + hp(white(n), 3000, 2) * expdec(n, 0.003) * 0.6


def rustle(dur=1.0, density=300, env=None):
    return granular(dur, density * dur, 2000, 7000, (0.003, 0.02), env=env) + 0.4 * granular(dur, density * dur * 0.5, 600, 2500, (0.01, 0.04), env=env)


def gallop_times(t0, t1, hz_pts, w_pts=None):
    """hoof events of a 4-beat gait: returns list[(time, weight)]"""
    evs = []
    t = t0
    offs = [0.0, 0.16, 0.26, 0.40]
    ws = [0.8, 0.6, 0.7, 1.0]
    while t < t1:
        hz = float(np.interp(t, [p[0] for p in hz_pts], [p[1] for p in hz_pts]))
        per = 1.0 / hz
        for o, w in zip(offs, ws):
            if t + o * per < t1:
                evs.append((t + o * per + rng.normal(0, 0.003), w * rng.uniform(0.85, 1.15)))
        t += per
    return evs


def metal_jingle(dur=0.5, level=1.0):
    """small armour/gear rattles: tiny modal pings"""
    n = N(dur)
    out = np.zeros(n)
    for _ in range(int(10 * dur)):
        f0 = rng.uniform(1800, 5200)
        ir = modal_ir([f0, f0 * 2.76, f0 * 5.4], [1, .5, .25], [rng.uniform(.02, .07), .03, .015], 0.2)
        place(out, excite(ir, burst(0.001, 10000)) * rng.uniform(.1, .6), rng.uniform(0, dur))
    return out * level

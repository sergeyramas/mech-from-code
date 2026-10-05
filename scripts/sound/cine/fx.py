"""New synthesis blocks for the cinematic soundtrack (explosions, collapse, rocket, nuke, mastering).

Built on top of the existing toolkit (dsp.py / metal.py / organic.py) - nothing in those files is changed.
Everything is formulas: no samples. Internal rate 44.1 kHz (dsp.SR); make_cine.py resamples to 48 kHz.
"""
import os
import sys
import numpy as np
from scipy import signal
from scipy.ndimage import minimum_filter1d, uniform_filter1d

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from dsp import *                       # noqa: E402,F401,F403
from metal import *                     # noqa: E402,F401,F403
from organic import thump, granular, body_hit, whoosh   # noqa: E402,F401
from build import valve                 # noqa: E402,F401
import dsp                              # noqa: E402

rng = dsp.rng


def st2(x):
    return np.stack([x, x], 1) if x.ndim == 1 else x


def stereo_of(fn):
    """two independent takes of a noisy mono generator -> decorrelated stereo"""
    a, b = fn(), fn()
    n = min(len(a), len(b))
    return np.stack([a[:n], b[:n]], 1)


def panned(x, p):
    return pan2(x, p) if x.ndim == 1 else x


def echo_taps(x, taps):
    """x stereo. taps = [(delay_s, gain, lp_hz)] -> landscape slap-back echoes (appended, longer array)"""
    x = st2(x)
    mx = max(d for d, _, _ in taps)
    out = np.zeros((len(x) + N(mx) + 8, 2))
    out[:len(x)] += x
    for d, g, fc in taps:
        y = lp(x, fc, 2) * g
        out[N(d):N(d) + len(y)] += y[:, ::-1] if rng.random() < 0.5 else y
    return out


def peaking(x, fc, gain_db, q=1.0):
    A = 10 ** (gain_db / 40)
    w0 = 2 * np.pi * fc / SR
    al = np.sin(w0) / (2 * q)
    c = np.cos(w0)
    b = [1 + al * A, -2 * c, 1 - al * A]
    a = [1 + al / A, -2 * c, 1 - al / A]
    sos = signal.tf2sos(np.array(b) / a[0], np.array(a) / a[0])
    return signal.sosfilt(sos, x, axis=0)


def highshelf(x, fc, gain_db, S=0.8):
    A = 10 ** (gain_db / 40)
    w0 = 2 * np.pi * fc / SR
    c, s_ = np.cos(w0), np.sin(w0)
    al = s_ / 2 * np.sqrt((A + 1 / A) * (1 / S - 1) + 2)
    sq = 2 * np.sqrt(A) * al
    b0 = A * ((A + 1) + (A - 1) * c + sq)
    b1 = -2 * A * ((A - 1) + (A + 1) * c)
    b2 = A * ((A + 1) + (A - 1) * c - sq)
    a0 = (A + 1) - (A - 1) * c + sq
    a1 = 2 * ((A - 1) - (A + 1) * c)
    a2 = (A + 1) - (A - 1) * c - sq
    return signal.sosfilt(np.array([[b0 / a0, b1 / a0, b2 / a0, 1, a1 / a0, a2 / a0]]), x, axis=0)


# ------------------------------------------------------------------ explosions / debris
def explosion(size=1.0, bright=1.0, tail=None):
    """stereo, peak-normalised. size ~ 1 (grenade) .. 9 (building core)."""
    s = size
    tail = tail or min(1.2 + 1.8 * s ** 0.6, 7.0)
    n = N(tail)
    t = tt(n)
    sub = thump(n, 95, 26, 0.10 * s ** 0.4, 0.45 * s ** 0.55, atk=0.004) * 1.2
    sub += 0.5 * thump(n, 60, 32, 0.2, 0.9 * s ** 0.5, atk=0.01) * (t > 0.02)
    fc = np.maximum(4500 * bright * np.exp(-t / (0.22 * s ** 0.4)), 140) + 0
    def body():
        y = tv_biquad(white(n), fc, 0.8, 'lp', block=128)
        return y * np.exp(-t / (0.30 * s ** 0.5)) * (1 - np.exp(-t / 0.003))
    def rumble():
        y = lp(brown(n), 160, 2) * np.exp(-t / (0.9 * s ** 0.6)) * (1 - np.exp(-t / 0.05))
        return y / (np.std(y[:N(0.5)]) + 1e-9)
    crack = hp(white(n), 2200, 2) * np.exp(-t / 0.010) * (0.9 * bright)
    L = body() * 0.9 + rumble() * 1.3
    R = body() * 0.9 + rumble() * 1.3
    out = np.stack([L, R], 1)
    out += (sub * 1.0 + crack)[:, None]
    # debris rain tail
    g = granular(min(tail, 2.2 + s * 0.2), 120 * s ** 0.5, 400, 4200, (0.003, 0.02),
                 env=[(0, 0), (0.12, 0.5), (0.5, 0.35), (min(tail, 2.2 + s * 0.2), 0)])
    out[:len(g)] += (g * 0.25)[:, None] * np.array([1.0, 0.8])
    return out / (np.max(np.abs(out)) + 1e-9)


def debris(dur=2.5, count=40, mix=(0.5, 0.25, 0.25), f_range=(500, 2600), decay=1.6, level=1.0, spread=0.8, hard=8000):
    """stereo shower of falling pieces: metal pings / concrete thuds / wood knocks. Denser at the start."""
    n = N(dur)
    out = np.zeros((n, 2))
    for _ in range(count):
        td = dur * rng.random() ** 1.8 * 0.92
        g = level * np.exp(-td * decay / dur * 2.0) * rng.uniform(0.25, 1.0)
        k = rng.choice(3, p=np.array(mix) / sum(mix))
        if k == 0:
            f0 = rng.uniform(*f_range)
            y = metal_hit(f0, 0.45, rng.uniform(0.03, 0.16), 1.0, PLATE[:9], hard, 1.0, sizzle=0.0)
        elif k == 1:
            m = N(0.3)
            y = thump(m, rng.uniform(110, 170), rng.uniform(50, 75), 0.02, 0.07) + bp(white(m), 300, 2200) * expdec(m, 0.025) * 0.7
        else:
            y = wood_thud(rng.uniform(0.8, 1.6), 0.5, 1.0)
        dist_lp = rng.uniform(5000, 14000)
        y = lp(y, dist_lp, 2)
        place(out, pan2(y * g, rng.uniform(-spread, spread)), td)
    return out


def sheet_metal_crunch(dur=1.2, power=1.0):
    """crumpling thin metal: dense modal hits, scrape, glass-like tinkle"""
    n = N(dur)
    out = np.zeros(n)
    for _ in range(int(55 * power)):
        td = dur * rng.random() ** 1.5 * 0.85
        f0 = rng.uniform(260, 3800)
        y = metal_hit(f0, 0.35, rng.uniform(0.02, 0.09), 1.0, PLATE[:8], 9000, rng.uniform(0.15, 0.7) * np.exp(-td * 2.2), sizzle=0.0)
        place(out, y, td)
    place(out, scrape(0.7 * dur, 1700, [(0, 0.6), (0.2, 1.0), (0.7 * dur, 0.2)], 0.8), 0.0)
    gl = granular(0.6, 900, 3500, 11000, (0.001, 0.004), env=[(0, 1), (0.15, 0.7), (0.6, 0)])
    place(out, gl * 0.5, 0.02)
    return out


def collapse(dur=4.0, power=1.0):
    """building collapse: low rumble swell, wood cracks, concrete, dust hiss, metal groans"""
    n = N(dur)
    t = tt(n)
    out = np.zeros((n, 2))
    sw = np.minimum(t / 0.25, 1) * np.exp(-np.maximum(t - 0.4, 0) / (dur * 0.38))
    for c in range(2):
        out[:, c] += lp(brown(n), 120, 2) * sw * 1.8 + lp(pink(n), 700, 2) * sw * 0.35
        out[:, c] += tv_biquad(pink(n), curve(n, [(0, 2500), (dur, 5200)]), 0.6, 'bp', 256) * np.minimum(t / 0.6, 1) * np.exp(-t / (dur * 0.5)) * 0.15
    # wood / plank cracks
    for _ in range(int(32 * power)):
        td = dur * 0.8 * rng.random() ** 1.3
        y = wood_thud(rng.uniform(0.7, 1.7), rng.uniform(0.4, 0.9), rng.uniform(0.3, 1.0))
        place(out, pan2(lp(y, 9000, 2) * np.exp(-td / (dur * 0.6)), rng.uniform(-0.6, 0.6)), td)
    # heavy slabs
    for k in range(int(7 * power)):
        td = 0.05 + dur * 0.7 * rng.random() ** 1.2
        m = N(0.8)
        y = thump(m, 80, 34, 0.04, 0.25) * 1.2 + lp(white(m), 1800, 2) * expdec(m, 0.06) * 0.6
        place(out, pan2(y * 0.8, rng.uniform(-0.5, 0.5)), td)
    # groaning steel
    for k in range(3):
        c = creak(1.4, [(0, 6), (1.4, 14)], rng.uniform(380, 700), [(0, 0), (0.5, 0.9), (1.4, 0)]) * 0.12
        place(out, pan2(c, rng.uniform(-0.5, 0.5)), 0.2 + k * 0.7)
    out += debris(dur, int(40 * power), (0.35, 0.4, 0.25), (300, 2200), 1.2, 0.5)[:n]
    return out


def autocannon_shot(power=1.0):
    n = N(0.4)
    t = tt(n)
    crack = hp(white(n), 1800, 2) * np.exp(-t / 0.006) * 0.9
    body = tv_biquad(white(n), np.maximum(3500 * np.exp(-t / 0.03), 300), 0.8, 'lp', block=32) * np.exp(-t / 0.05)
    th = thump(n, 160, 60, 0.012, 0.07) * 1.1
    ring = lp(hp(white(n), 700, 2), 3000, 2) * np.exp(-t / 0.12) * 0.12
    y = crack + body * 0.8 + th + ring
    return y / (np.max(np.abs(y)) + 1e-9) * power


def armor_ping(f0=None):
    """ricochet / spark on armour: bright ping + zing"""
    f0 = f0 or rng.uniform(1400, 3200)
    y = metal_hit(f0, 0.5, rng.uniform(0.04, 0.09), 1.1, PLATE[:9], 11000, 1.0, sizzle=0.1)
    zn = N(0.22)
    f = curve(zn, [(0, rng.uniform(5500, 7500)), (0.22, rng.uniform(1800, 2600))])
    z = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-tt(zn) / 0.05) * 0.25
    y[:zn] += z
    return y / (np.max(np.abs(y)) + 1e-9)


def missile_launch(dur=0.9):
    """rack launch: ignition thump + hot hiss swelling then trailing off (flight)"""
    n = N(dur)
    t = tt(n)
    ig = thump(n, 130, 45, 0.02, 0.10) * 0.8
    ht = tv_biquad(white(n), curve(n, [(0, 1800), (0.12, 3800), (dur, 1400)]), 0.7, 'bp', 64)
    ht *= np.minimum(t / 0.012, 1) * np.exp(-t / 0.55) * 1.4
    lw = lp(white(n), 500, 2) * np.minimum(t / 0.02, 1) * np.exp(-t / 0.4) * 0.8
    return st2(ig + ht / (np.std(ht) + 1e-9) * 0.5 + lw)[:, 0]


def missile_flight(dur=0.55, p0=-0.6, p1=0.2):
    """in-flight hiss, travelling away: band narrows & darkens, doppler-ish downward"""
    n = N(dur)
    t = tt(n)
    y = tv_biquad(white(n), curve(n, [(0, 4200), (dur, 1700)]), 1.0, 'bp', 64) * np.exp(-t / 0.35)
    y /= np.std(y) + 1e-9
    g = (1.0 - 0.45 * t / dur) * np.minimum(t / 0.03, 1)
    return pan2(y * g, curve(n, [(0, p0), (dur, p1)]))


# ------------------------------------------------------------------ rocket / bullet-time
def rocket_approach(dur=3.05, final_pass=True):
    """distant launch -> approaching whistle and roar. Rises in pitch and level, Doppler drop at the very end."""
    n = N(dur)
    t = tt(n)
    k = (t / dur) ** 2.2
    f = 500 + 2200 * k
    ph = 2 * np.pi * np.cumsum(f) / SR
    whistle = np.sin(ph + 0.9 * np.sin(ph * 0.5)) * 0.5 + 0.25 * np.sin(2 * ph + 0.3)
    wn = tv_biquad(white(n), f * 1.05, 14, 'bp', 32)
    wn /= np.std(wn) + 1e-9
    roar = tv_biquad(white(n), 140 + 700 * k, 0.9, 'bp', 128) * (0.12 + 3.0 * k)
    roar /= np.std(roar) + 1e-9
    sub = lp(brown(n), 90, 2)
    sub /= np.std(sub) + 1e-9
    amp = 0.03 + 0.97 * k ** 1.2
    y = (whistle * 0.35 + wn * 0.35) * amp * (0.4 + 0.6 * k) + roar * amp * 0.7 + sub * amp ** 1.3 * 0.9
    y *= np.minimum(t / 0.1, 1)
    return y / (np.max(np.abs(y)) + 1e-9)


def heartbeat(dur, rate_pts, gain_pts, f_lo=44):
    """lub-dub heartbeat as a low thump pair; rate in beats/s over time"""
    n = N(dur)
    out = np.zeros(n)
    t, g = 0.0, curve(n, gain_pts)
    while t < dur:
        r = float(np.interp(t, [p[0] for p in rate_pts], [p[1] for p in rate_pts]))
        gg = g[min(n - 1, int(t * SR))]
        lub = thump(N(0.4), 78, f_lo, 0.04, 0.10) * 1.0 + lp(white(N(0.4)), 380, 2) * expdec(N(0.4), 0.03) * 0.3
        dub = thump(N(0.4), 68, f_lo * 0.9, 0.04, 0.09) * 0.7
        place(out, lub * gg, t)
        place(out, dub * gg, t + 0.17 / max(r, 0.4) * 1.25)
        t += 1.0 / r
    return out


def drone_bullet_time(dur=2.7):
    """slowed, stretched, drone-like rocket: sub saw cluster + dark smeared noise, slow beating."""
    n = N(dur)
    t = tt(n)
    f0 = curve(n, [(0, 62), (dur * 0.5, 48), (dur, 40)])
    out = np.zeros((n, 2))
    for i, (ratio, det, a) in enumerate([(1, 0, 1.0), (1.005, 0.4, 0.8), (1.5, -0.3, 0.35), (2.01, 0.2, 0.3), (3.0, 0.0, 0.12)]):
        ph = 2 * np.pi * np.cumsum(f0 * ratio * (1 + 0.003 * det)) / SR + i
        saw = signal.sawtooth(ph) * 0.6 + np.sin(ph)
        pan = [-0.3, 0.3, -0.5, 0.5, 0][i]
        out += pan2(saw * a, pan)
    out = lp(out, 360, 4)
    # smeared whistle, slowed to a low moan: sweeping resonant band, falling
    w = tv_biquad(white(n), curve(n, [(0, 520), (dur, 130)]), 22, 'bp', 64)
    w /= np.std(w) + 1e-9
    out += pan2(w * 0.5 * (0.4 + 0.6 * np.sin(np.pi * t / dur)), 0.0)
    # slow tide of dark noise (the roar at 5 % speed)
    tide = tv_biquad(pink(n), 180 + 120 * np.sin(2 * np.pi * t * 0.31), 1.2, 'lp', 256)
    out += np.stack([tide, np.roll(tide, N(0.013))], 1) * 0.5
    return out * np.minimum(t / 0.35, 1)[:, None]


def whoosh_snap(dur=0.32, power=1.0):
    """sharp whoosh as time snaps back to speed: fast upward noise sweep + dopplered tail"""
    n = N(dur)
    t = tt(n)
    fc = curve(n, [(0, 250), (dur * 0.55, 6200), (dur, 1800)])
    y = tv_biquad(white(n), fc, 1.4, 'bp', 32)
    y /= np.std(y) + 1e-9
    e = (np.minimum(t / 0.05, 1) ** 1.5) * np.exp(-np.maximum(t - dur * 0.55, 0) / 0.05)
    extra = hp(white(n), 7000, 2) * e * 0.3
    return pan2((y + extra) * e, 0.0) * power


# ------------------------------------------------------------------ nuke
def tinnitus(dur=3.2):
    """high ringing in the ears: pure tones + slow beating, long smooth fade"""
    n = N(dur)
    t = tt(n)
    y = np.sin(2 * np.pi * 7150 * t) + 0.7 * np.sin(2 * np.pi * 7230 * t + 1.0) + 0.4 * np.sin(2 * np.pi * 4410 * t) \
        + 0.25 * np.sin(2 * np.pi * 10600 * t)
    y *= 1 + 0.15 * np.sin(2 * np.pi * 3.1 * t)
    env = np.minimum(t / 0.04, 1) * np.exp(-t / (dur * 0.42)) * np.clip((dur - t) / 0.6, 0, 1)
    return y / np.max(np.abs(y)) * env


def sub_boom(dur=5.0):
    """pressure wave: sub thump with long falling tail + slow low-frequency crumble"""
    n = N(dur)
    t = tt(n)
    f = 22 + 38 * np.exp(-t / 0.45)
    ph = 2 * np.pi * np.cumsum(f) / SR
    y = np.sin(ph) * (1 - np.exp(-t / 0.03)) * np.exp(-t / 1.6)
    y += 0.6 * np.sin(2 * np.pi * np.cumsum(55 + 40 * np.exp(-t / 0.25)) / SR) * np.exp(-t / 0.9) * (1 - np.exp(-t / 0.01))
    nz = lp(white(n), 180, 2) * np.exp(-t / 0.5) * (1 - np.exp(-t / 0.005)) * 1.2
    return (y + nz * 0.5) / np.max(np.abs(y + nz * 0.5))


def rolling_rumble(dur=6.0, level=1.0):
    """shock wave rolling over: slow cresting AM'd brown noise, cutoff falling, a few slow 'rolls'"""
    n = N(dur)
    t = tt(n)
    def ch():
        x = brown(n)
        fc = curve(n, [(0, 520), (dur * 0.3, 260), (dur, 70)])
        y = tv_biquad(x, fc, 0.8, 'lp', 256)
        roll = 0.65 + 0.35 * np.sin(2 * np.pi * np.cumsum(5.5 - 3.0 * t / dur) / SR + rng.uniform(0, 6))
        return y * roll
    out = np.stack([ch(), ch()], 1)
    env = (1 - np.exp(-t / 0.35)) * np.exp(-np.maximum(t - 0.5, 0) / (dur * 0.42)) * np.clip((dur - t) / 0.5, 0, 1)
    out /= np.std(out[N(0.5):N(2.5)]) + 1e-9
    return out * env[:, None] * level


def tremble_rumble(dur, level=1.0, f_start=90, f_end=38):
    """deep long rumble under the mushroom cloud: sub bed with slow throbbing"""
    n = N(dur)
    t = tt(n)
    def ch():
        y = tv_biquad(brown(n), curve(n, [(0, 160), (dur, 55)]), 0.9, 'lp', 256)
        return y
    out = np.stack([ch(), ch()], 1)
    out /= np.std(out) + 1e-9
    f = curve(n, [(0, f_start), (dur, f_end)])
    tone = np.sin(2 * np.pi * np.cumsum(f) / SR) * (0.8 + 0.2 * np.sin(2 * np.pi * 0.23 * t))
    out += tone[:, None] * 0.9
    env = (1 - np.exp(-t / 1.0)) * np.clip((dur - t) / (dur * 0.5), 0, 1) ** 1.3
    return out * env[:, None] * level


def wind(dur, level=1.0, seed_shift=0):
    n = N(dur)
    t = tt(n)
    def ch():
        x = pink(n)
        g = lp(white(n), 0.25, 1)
        g = (g / (np.std(g) + 1e-9)) * 0.5 + 1.0
        fc = 380 + 260 * np.clip(g, 0, 2)
        y = tv_biquad(x, fc, 0.9, 'bp', 512) * np.clip(g, 0.2, 2) ** 1.5
        return y / (np.std(y) + 1e-9)
    out = np.stack([ch(), ch()], 1)
    # thin whistle through the debris, comes and goes
    wh = tv_biquad(white(n), 1500 + 400 * np.sin(2 * np.pi * 0.07 * t), 25, 'bp', 128)
    wh /= np.std(wh) + 1e-9
    wmod = np.clip(lp(white(n), 0.3, 1) / 0.25, 0, 1)
    out += pan2(wh * wmod * 0.12, 0.2)
    return out * level


# ------------------------------------------------------------------ mastering
def compress(x, thr_db=-20.0, ratio=2.5, att=0.03, rel=0.35):
    """simple smooth stereo-linked feed-forward compressor (RMS-ish)"""
    p = np.mean(x ** 2, axis=1)
    a = np.exp(-1 / (att * SR))
    r = np.exp(-1 / (rel * SR))
    # one-pole with separate attack / release, vectorised through a two-pass approximation
    env = signal.lfilter([1 - r], [1, -r], p)           # release-ish smoother
    env_fast = signal.lfilter([1 - a], [1, -a], p)
    e = np.maximum(env, env_fast)
    lvl = 10 * np.log10(e + 1e-12)
    over = np.maximum(lvl - thr_db, 0)
    gr = -over * (1 - 1 / ratio)
    g = 10 ** (gr / 20)
    return x * g[:, None]


def limiter(x, ceil_db=-1.5, look=0.004, rel=0.10, sr=None):
    """look-ahead peak limiter: min-filter + moving average of the needed gain, then slow release."""
    from scipy.ndimage import maximum_filter1d
    sr = sr or SR
    ceil = 10 ** (ceil_db / 20)
    w = max(2, int(look * sr))
    pk = np.max(np.abs(x), axis=1)
    need = np.minimum(1.0, ceil / (pk + 1e-12))
    m = minimum_filter1d(need, size=w * 2 + 1, mode='nearest')
    m = uniform_filter1d(m, size=w * 2 + 1, mode='nearest')
    red = 1 - m
    r = np.exp(-1 / (rel * sr))
    red_h = maximum_filter1d(red, size=int(0.03 * sr) * 2 + 1, mode='nearest')
    red_s = np.maximum(signal.filtfilt([1 - r], [1, -r], red_h), red)
    return x * (1 - red_s)[:, None]


def true_peak_db(x, sr):
    up = signal.resample_poly(x, 4, 1, axis=0)
    return 20 * np.log10(np.max(np.abs(up)) + 1e-12)


def lufs(x, sr):
    import pyloudnorm as pyln
    return pyln.Meter(sr).integrated_loudness(x)

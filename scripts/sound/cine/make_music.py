"""Calm tech/documentary music bed for video 2 (code-made): pulse, pads, light percussion, mids carved out for a voice.
96 BPM, A minor, 210 s = 84 bars.  intro 0-10 s | build ~0:55 | build ~2:15 | finale ~3:05 | ring-out to 3:30.
.venv/bin/python cine/make_music.py  ->  video/audio/music_bed_v2.wav (48 kHz stereo, ~-18 LUFS, TP<=-1 dBTP)"""
import os, sys
import numpy as np
from scipy import signal
from scipy.io import wavfile
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import fx
from fx import *
OUT = os.path.abspath(os.path.join(HERE, '..', '..', 'video/audio/music_bed_v2.wav'))
BPM = 96; BEAT = 60 / BPM; BAR = 4 * BEAT; NB = 84; D = NB * BAR      # 210.0 s
buf = np.zeros((N(D + 4), 2))
mtr = np.zeros(N(D + 4))        # nothing, kept for symmetry


def hz(m):
    return 440.0 * 2 ** ((m - 69) / 12)


# chord per 2 bars (midi): root, triad
CH = {'Am': (45, [57, 60, 64]), 'F': (41, [53, 57, 60]), 'C': (48, [60, 64, 67]), 'G': (43, [55, 59, 62]),
      'Em': (40, [52, 55, 59]), 'Dm': (38, [50, 53, 57])}
PROG_A = ['Am', 'F', 'C', 'G']
PROG_C = ['F', 'G', 'Am', 'Em']


def prog(bar):
    if bar < 54 or bar >= 74:
        p = PROG_A
    else:
        p = PROG_C
    return p[(bar // 2) % 4]


def inten(bar):
    """0..1 energy by bar (section map)"""
    if bar < 4: return 0.25
    if bar < 22: return 0.45 + 0.1 * (bar - 4) / 18
    if bar < 54: return 0.75
    if bar < 74: return 0.9
    if bar < 80: return 1.0
    return 0.5 - 0.5 * (bar - 80) / 4


def saw_bl(f, n, ph0=0.0):
    """band-limited-ish saw (additive up to 3.5 kHz)"""
    t = np.arange(n) / SR
    y = np.zeros(n)
    for k in range(1, int(min(3500 / f, 24)) + 1):
        y += np.sin(2 * np.pi * f * k * t + ph0 * k) / k
    return y * 0.6


# ---------- pads (per 2-bar chord, overlapped, slow attack/release)
def pads():
    for b in range(0, NB, 2):
        name = prog(b)
        root, tri = CH[name]
        I = inten(b)
        dur = 2 * BAR + 2.2
        n = N(dur)
        y = np.zeros(n)
        for m_ in tri + [root + 12]:
            for det in (-0.06, 0.0, 0.07):
                f = hz(m_) * 2 ** (det / 12)
                y += saw_bl(f, n, rng.uniform(0, 6))
        y /= 12
        fc = 600 + 1500 * I
        y = hp(lp(y, fc, 2), 170, 2)
        att = 1.6 if b > 0 else 3.0
        env = np.minimum(np.arange(n) / SR / att, 1) ** 1.5 * np.clip((dur - np.arange(n) / SR) / 2.2, 0, 1) ** 1.2
        ph = np.arange(n) / SR
        st = np.stack([y * (1 + 0.06 * np.sin(2 * np.pi * 0.11 * ph)), y * (1 + 0.06 * np.sin(2 * np.pi * 0.13 * ph + 2))], 1)
        place(buf, st * env[:, None] * (0.55 + 0.45 * I), b * BAR - 0.8 if b else 0)


# ---------- sub bass
def bass():
    for b in range(4, 80):
        root = CH[prog(b)][0]
        I = inten(b)
        pat = [(0, 1.5), (1.5, 0.5), (2, 1.5), (3.5, 0.5)] if I > 0.7 else [(0, 3.0)]
        for off, ln in pat:
            n = N(ln * BEAT + 0.15)
            t = np.arange(n) / SR
            f = hz(root + (12 if off == 1.5 and I > 0.7 else 0))
            y = np.sin(2 * np.pi * f * t) + 0.25 * np.sin(4 * np.pi * f * t)
            env = np.minimum(t / 0.015, 1) * np.clip((ln * BEAT + 0.1 - t) / 0.12, 0, 1) * np.exp(-t / 2.5)
            place(buf, (y * env * 0.12 * (0.5 + 0.5 * I))[:, None] * np.array([1, 1]), b * BAR + off * BEAT)


# ---------- plucked pulse
def pluck(f, I):
    n = N(0.5)
    t = np.arange(n) / SR
    y = saw_bl(f, n) * 0.5 + signal.square(2 * np.pi * f * t) * 0.15
    cutoff = 700 + 1500 * I
    y = tv_biquad(y, curve(n, [(0, cutoff * 2.2), (0.25, cutoff * 0.6)]), 1.8, 'lp', 64)
    return y * np.exp(-t / 0.13) * np.minimum(t / 0.003, 1)


def pulse():
    ARP = [0, 1, 2, 3, 2, 1, 2, 1]
    for b in range(2, 80):
        I = inten(b)
        name = prog(b)
        tri = CH[name][1]
        notes = [tri[0] + 12, tri[1] + 12, tri[2] + 12, tri[0] + 24]
        step = 0.5 if I < 0.85 or b >= 74 else 0.25
        k = 0
        pos = 0.0
        a_lvl = 0.34 + 0.3 * I if b >= 4 else 0.2
        while pos < 4:
            idx = ARP[(k) % 8]
            m_ = notes[idx]
            acc = 1.0 if (pos % 1) == 0 else 0.65
            y = pluck(hz(m_), I) * a_lvl * acc * (0.8 + 0.2 * rng.random())
            pan = [-0.5, -0.15, 0.15, 0.5][idx]
            place(buf, pan2(y, pan), b * BAR + pos * BEAT)
            pos += step; k += 1


def delay_bus():
    """ping-pong dotted-eighth echo of the plucks only (re-render plucks into a separate bus)"""
    global buf
    bus = np.zeros_like(buf)
    saved = buf
    buf = bus
    pulse()
    buf = saved
    d = 0.75 * BEAT
    out = np.zeros_like(bus)
    for k in range(1, 6):
        s = N(d * k)
        y = lp(bus, 3200 / (1 + 0.4 * k), 2) * (0.42 ** k)
        y = y[:, ::-1] if k % 2 else y
        out[s:] += y[:len(out) - s]
    buf += out * 0.7


# ---------- percussion
def kick(gain=1.0):
    n = N(0.45)
    return thump(n, 115, 44, 0.025, 0.16, atk=0.002) * gain


def hat(open_=False, g=1.0):
    n = N(0.18 if open_ else 0.05)
    return hp(white(n), 7000, 2) * expdec(n, 0.06 if open_ else 0.012) * g


def click(g=1.0):
    n = N(0.08)
    t = tt(n)
    return (np.sin(2 * np.pi * 1900 * t) * np.exp(-t / 0.008) * 0.6 + bp(white(n), 2500, 6000) * expdec(n, 0.01) * 0.4) * g


def perc():
    for b in range(4, 80):
        I = inten(b)
        base = b * BAR
        if b >= 10 and I >= 0.45:                          # off-beat hats
            for e in range(4):
                place(buf, pan2(hat(g=0.05 * (0.6 + I)), 0.3), base + (e + 0.5) * BEAT)
        if b >= 22:                                        # light kick: 1, 3, plus pickup
            for bt, g in [(0, 1.0), (2, 0.8), (3.5, 0.5)] if I < 0.95 else [(0, 1.0), (1, 0.6), (2, 0.9), (3, 0.6)]:
                place(buf, pan2(kick(0.30 * g), 0.0), base + bt * BEAT)
            for bt in (1, 3):
                place(buf, pan2(click(0.07), -0.25 if bt == 1 else 0.25), base + bt * BEAT)
            if b >= 54:
                for e in range(8):
                    place(buf, pan2(hat(g=0.035), -0.3), base + e * 0.5 * BEAT + 0.25 * BEAT)
        if b % 4 == 3 and 4 <= b < 22:                    # tiny data blips
            for k in range(3):
                m_ = CH[prog(b)][1][k % 3] + 24
                f = hz(m_)
                n = N(0.1)
                y = np.sin(2 * np.pi * f * tt(n)) * expdec(n, 0.03)
                place(buf, pan2(y * 0.03, rng.uniform(-0.7, 0.7)), base + (2.5 + k * 0.25) * BEAT)


# ---------- risers / impacts at section points
def rise(t_end, bars=3):
    d = bars * BAR
    n = N(d)
    t = tt(n)
    nz = tv_biquad(white(n), curve(n, [(0, 400), (d, 8500)]), 0.9, 'bp', 128)
    nz /= np.std(nz) + 1e-9
    tone = np.sin(2 * np.pi * np.cumsum(curve(n, [(0, 220), (d, 880)])) / SR) * 0.4
    e = (t / d) ** 2.2
    place(buf, pan2((nz * 0.10 + tone * 0.05) * e, 0.0), t_end - d)
    # snare-ish roll in the last bar (soft)
    for k in range(int(BAR / (BEAT / 4))):
        tk = t_end - BAR + k * BEAT / 4
        g = 0.03 + 0.07 * k / (BAR / (BEAT / 4))
        place(buf, pan2(bp(white(N(0.06)), 1500, 6000) * expdec(N(0.06), 0.02) * g, 0.0), tk)


def impact(t, g=1.0, long=False):
    n = N(5.0 if long else 2.5)
    th = thump(n, 90, 32, 0.07, 1.2 if long else 0.7) * 0.5 * g
    cr = hp(white(n), 4000, 2) * expdec(n, 0.25 if long else 0.15) * 0.05 * g
    place(buf, pan2(th + cr, 0.0), t)


def hits():
    for b in (22, 54):
        rise(b * BAR, 3)
        impact(b * BAR, 1.0)
    rise(74 * BAR, 3)
    impact(74 * BAR, 1.3, True)
    # downbeat reverse-ish swell into section starts is already in the pad attack


def main():
    print('pads'); pads()
    print('bass'); bass()
    print('pulse'); pulse()
    print('delay'); delay_bus()
    print('perc'); perc()
    hits()
    # reverb on the whole bed (soft, long)
    ir = make_ir(3.2, 0.02, (1.3, 1.0, 0.5))
    x = buf[:N(D)]
    wet = np.zeros_like(x)
    for c in range(2):
        wet[:, c] = signal.fftconvolve(x[:, c], ir[:, c])[:len(x)]
    x = x + wet * 0.35
    # mid carve for the voice (300 Hz - 3.4 kHz), small air lift; keep low end and sparkle
    x = fx.peaking(x, 420, -5.0, 0.8)
    x = fx.peaking(x, 1100, -6.0, 0.8)
    x = fx.peaking(x, 2600, -5.0, 1.0)
    x = fx.highshelf(x, 7000, 1.5)
    x = signal.sosfilt(signal.butter(2, 28, 'highpass', fs=SR, output='sos'), x, axis=0)
    # slow fade-in, long fade-out
    n = len(x)
    x[:N(1.5)] *= np.linspace(0, 1, N(1.5))[:, None] ** 2
    x[-N(6):] *= (np.linspace(1, 0, N(6)) ** 1.5)[:, None]
    x48 = signal.resample_poly(x, 160, 147, axis=0)
    g = 1.0
    for it in range(8):
        up = signal.resample_poly(x48 * g, 4, 1, axis=0)
        up = fx.limiter(up, -1.4, 0.003, 0.2, sr=192000)
        y = np.clip(signal.resample_poly(up, 1, 4, axis=0), -0.95, 0.95)
        L = fx.lufs(y, 48000); tp = fx.true_peak_db(y, 48000)
        print(f' iter {it}: {L:.2f} LUFS tp {tp:.2f}')
        if abs(L + 18) < 0.1 and tp <= -1.0: break
        g *= 10 ** ((-18 - L) / 20)
    wavfile.write(OUT, 48000, (y * 32767).astype(np.int16))
    # carve report: share of energy 300-3400 Hz
    f, P = signal.welch(y.mean(1), 48000, nperseg=8192)
    def band(a, b): return P[(f >= a) & (f < b)].sum()
    for a_,b_ in [(20,100),(100,300),(300,800),(800,3400),(3400,8000),(8000,20000)]: print(f'  {a_}-{b_}: {10*np.log10(band(a_,b_)/P.sum()+1e-12):.1f} dB')
    print(f'{len(y) / 48000:.1f}s  energy 300-3400 Hz = {100 * band(300, 3400) / P.sum():.1f} % of total; <300 Hz {100 * band(20, 300) / P.sum():.1f} %; >3.4k {100 * band(3400, 20000) / P.sum():.1f} %')


if __name__ == '__main__':
    main()

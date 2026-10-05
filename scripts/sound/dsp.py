"""Core DSP toolkit: noise, filters, envelopes, modal synthesis, reverb, spatialisation.
Everything is synthesised from formulas. No samples."""
import numpy as np
from scipy import signal
from scipy.io import wavfile
from scipy.interpolate import PchipInterpolator

SR = 44100
rng = np.random.default_rng(20261004)


def N(d):
    return int(round(d * SR))


def tt(n):
    return np.arange(n) / SR


def white(n):
    return rng.standard_normal(n)


def spec_noise(n, shape):
    """Noise with a given magnitude spectrum shape(f_hz). Periodic over n samples."""
    f = np.fft.rfftfreq(n, 1 / SR)
    mag = shape(np.maximum(f, 1e-3))
    ph = rng.uniform(0, 2 * np.pi, len(f))
    X = mag * np.exp(1j * ph)
    X[0] = 0
    x = np.fft.irfft(X, n)
    return x / (np.std(x) + 1e-12)


def pink(n):
    return spec_noise(n, lambda f: 1 / np.sqrt(f))


def brown(n):
    return spec_noise(n, lambda f: 1 / f)


def _fc(f):
    return float(np.clip(f, 10, SR * 0.45))


def lp(x, fc, order=4):
    return signal.sosfilt(signal.butter(order, _fc(fc), 'lowpass', fs=SR, output='sos'), x, axis=0)


def hp(x, fc, order=4):
    return signal.sosfilt(signal.butter(order, _fc(fc), 'highpass', fs=SR, output='sos'), x, axis=0)


def bp(x, lo, hi, order=2):
    return signal.sosfilt(signal.butter(order, [_fc(lo), _fc(hi)], 'bandpass', fs=SR, output='sos'), x, axis=0)


def tv_biquad(x, fc, q, kind='bp', block=64):
    """Time-varying RBJ biquad (bp = constant 0 dB peak, lp, hp). fc, q: scalars or arrays."""
    n = len(x)
    fc = np.broadcast_to(np.asarray(fc, float), (n,))
    q = np.broadcast_to(np.asarray(q, float), (n,))
    y = np.empty(n)
    zi = np.zeros((1, 2))
    for s in range(0, n, block):
        e = min(n, s + block)
        m = (s + e) // 2
        f = _fc(fc[m])
        Q = max(q[m], 0.1)
        w0 = 2 * np.pi * f / SR
        al = np.sin(w0) / (2 * Q)
        c = np.cos(w0)
        if kind == 'bp':
            b = (al, 0.0, -al)
        elif kind == 'lp':
            b = ((1 - c) / 2, 1 - c, (1 - c) / 2)
        else:
            b = ((1 + c) / 2, -(1 + c), (1 + c) / 2)
        a0 = 1 + al
        sos = np.array([[b[0] / a0, b[1] / a0, b[2] / a0, 1.0, -2 * c / a0, (1 - al) / a0]])
        y[s:e], zi = signal.sosfilt(sos, x[s:e], zi=zi)
    return y


def curve(n, pts, smooth=True):
    """Piecewise curve over time (seconds). pts = [(t, v), ...] or scalar."""
    if np.isscalar(pts):
        return np.full(n, float(pts))
    if isinstance(pts, np.ndarray):
        return pts
    ts = np.array([p[0] for p in pts], float)
    vs = np.array([p[1] for p in pts], float)
    t = np.clip(np.arange(n) / SR, ts[0], ts[-1])
    if smooth and len(ts) >= 3:
        return PchipInterpolator(ts, vs)(t)
    return np.interp(t, ts, vs)


def expdec(n, tau):
    return np.exp(-np.arange(n) / SR / tau)


def adsr(n, a, d, s, r):
    e = np.ones(n) * s
    na, nd, nr = N(a), N(d), N(r)
    if na > 0:
        e[:na] = np.linspace(0, 1, na) ** 1.5 if na > 1 else 1
    if nd > 0:
        seg = e[na:na + nd]
        e[na:na + len(seg)] = s + (1 - s) * np.linspace(1, 0, nd)[:len(seg)] ** 2
    if nr > 0 and nr < n:
        e[-nr:] *= np.linspace(1, 0, nr) ** 1.5
    return e


def fade(x, fin=0.005, fout=0.02):
    x = x.copy()
    a, b = N(fin), N(fout)
    if a > 0 and a < len(x):
        x[:a] *= 0.5 - 0.5 * np.cos(np.pi * np.arange(a) / a)
    if b > 0 and b < len(x):
        x[-b:] *= 0.5 + 0.5 * np.cos(np.pi * np.arange(b) / b)
    return x


def norm(x, peak=1.0):
    m = np.max(np.abs(x)) + 1e-12
    return x * (peak / m)


def place(buf, x, start_s):
    s = int(round(start_s * SR))
    if s >= len(buf):
        return
    if s < 0:
        x = x[-s:]
        s = 0
    e = min(len(buf), s + len(x))
    if e > s:
        buf[s:e] += x[:e - s]


def pan2(x, p):
    p = np.clip(p, -1, 1)
    th = (np.asarray(p) + 1) * np.pi / 4
    return np.stack([x * np.cos(th), x * np.sin(th)], 1)


class Mix:
    def __init__(self, dur):
        self.buf = np.zeros((N(dur), 2))

    def add(self, x, t, pan=0.0, gain=1.0):
        if x.ndim == 1:
            x = pan2(x, pan)
        place(self.buf, x * gain, t)

    def add_dist(self, x, t, dist, pan=0.0, gain=1.0):
        """static distance: gain + air absorption"""
        g = 1.0 / max(dist, 1.0) ** 0.9
        y = lp(x, max(2500, 17000 / (1 + 0.12 * dist)), 2) if dist > 2 else x
        self.add(y, t, pan, gain * g)


# ---------- modal / metal ----------
def modal_ir(freqs, amps, taus, dur, phases=None):
    n = N(dur)
    t = tt(n)
    out = np.zeros(n)
    for i, (f, a, tau) in enumerate(zip(freqs, amps, taus)):
        if f >= SR * 0.46:
            continue
        ph = rng.uniform(0, 0.6) if phases is None else phases[i]
        k = int(min(n, tau * 9 * SR))
        out[:k] += a * np.exp(-t[:k] / tau) * np.sin(2 * np.pi * f * t[:k] + ph)
    return out


def burst(dur=0.002, cutoff=9000, kind='noise'):
    n = max(8, N(dur))
    x = white(n) * np.hanning(n) if kind == 'noise' else np.hanning(n)
    return lp(x, cutoff, 2) if cutoff < 20000 else x


def excite(ir, ex):
    return signal.fftconvolve(ex, ir)[:len(ir)]


# ---------- reverb ----------
def make_ir(rt60=1.2, pre=0.012, damp=(1.25, 1.0, 0.45), early=0.25, dur=None, spread=1.0):
    dur = dur or min(rt60 * 1.35, 6.0)
    n = N(dur)
    t = tt(n)
    chans = []
    for _ in range(2):
        x = np.zeros(n)
        bands = [(20, 400), (400, 4000), (4000, 16000)]
        for (lo, hi), m in zip(bands, damp):
            nz = bp(white(n), lo, hi, 2) if lo > 20 else lp(white(n), hi, 2)
            nz /= np.std(nz) + 1e-9
            x += nz * np.exp(-6.9 * t / (rt60 * m)) * (0.9 if lo > 20 else 1.0)
        x[:N(pre)] = 0
        x = np.roll(x, 0)
        # ramp-in after predelay
        ramp = np.clip((t - pre) / 0.02, 0, 1)
        x *= ramp
        # early reflections
        for _k in range(14):
            td = pre + rng.uniform(0.003, 0.09) * spread
            i = int(td * SR)
            if i < n:
                x[i] += early * rng.choice([-1, 1]) * 4 * np.exp(-td * 9) * rng.uniform(0.4, 1)
        chans.append(x)
    ir = np.stack(chans, 1)
    mid = ir.mean(1, keepdims=True)
    side = hp(ir - mid, 250, 2)
    ir = mid + side
    ir /= np.sqrt(np.sum(ir ** 2, axis=0, keepdims=True)) + 1e-9
    return ir


def reverb(x, ir, wet=0.25, tail=None):
    """x: (n,2) or (n,). Returns longer array (n+len(ir)) dry+wet."""
    if x.ndim == 1:
        x = np.stack([x, x], 1)
    n = len(x)
    out = np.zeros((n + len(ir) - 1, 2))
    out[:n] += x * (1 - wet * 0.5)
    for c in range(2):
        out[:, c] += wet * 1.6 * signal.fftconvolve(x[:, c], ir[:, c])
    return out


def reverb_circ(x, ir, wet=0.25):
    n = len(x)
    out = x * (1 - wet * 0.5)
    for c in range(2):
        H = np.fft.rfft(ir[:, c], n)
        out[:, c] += wet * 1.6 * np.fft.irfft(np.fft.rfft(x[:, c]) * H, n)
    return out


def fold(buf, n):
    out = buf[:n].copy()
    rest = buf[n:]
    while len(rest):
        k = min(n, len(rest))
        out[:k] += rest[:k]
        rest = rest[k:]
    return out


# ---------- movement ----------
def mover(x, px, py):
    """x mono. px, py: arrays (metres) of source position relative to listener (x right, y front).
    Doppler by variable delay, 1/r gain, air absorption, pan."""
    n = len(x)
    dist = np.hypot(px, py)
    delay = dist / 343.0 * SR
    idx = np.arange(n) - delay
    y = np.interp(idx, np.arange(n), x, left=0.0)
    g = 1.0 / np.maximum(dist, 1.2) ** 0.95
    fcut = np.clip(17000 / (1 + 0.1 * dist), 2200, 17000)
    y = tv_biquad(y, fcut, 0.7, 'lp', block=256)
    return pan2(y * g, px / np.maximum(dist, 1.0))


# ---------- output ----------
def lowshelf(x, fc, gain_db, S=1.0):
    A = 10 ** (gain_db / 40)
    w0 = 2 * np.pi * fc / SR
    c, s_ = np.cos(w0), np.sin(w0)
    al = s_ / 2 * np.sqrt((A + 1 / A) * (1 / S - 1) + 2)
    sq = 2 * np.sqrt(A) * al
    b0 = A * ((A + 1) - (A - 1) * c + sq)
    b1 = 2 * A * ((A - 1) - (A + 1) * c)
    b2 = A * ((A + 1) - (A - 1) * c - sq)
    a0 = (A + 1) + (A - 1) * c + sq
    a1 = -2 * ((A - 1) + (A + 1) * c)
    a2 = (A + 1) + (A - 1) * c - sq
    sos = np.array([[b0 / a0, b1 / a0, b2 / a0, 1, a1 / a0, a2 / a0]])
    return signal.sosfilt(sos, x, axis=0)


def finalize(st, name, outdir, target_lufs=-15.0, peak_db=-1.0, fin=0.01, fout=0.08, low_db=-6.0, lufs_info=None):
    import pyloudnorm as pyln
    st = st.copy()
    if low_db:
        st = lowshelf(st, 150, low_db)
    # DC removal
    st = signal.sosfilt(signal.butter(2, 18, 'highpass', fs=SR, output='sos'), st, axis=0)
    st[:N(fin)] *= np.linspace(0, 1, N(fin))[:, None]
    nf = N(fout)
    st[-nf:] *= (np.linspace(1, 0, nf) ** 1.5)[:, None]
    ceil = 10 ** (peak_db / 20)
    meter = pyln.Meter(SR)
    st = st / (np.max(np.abs(st)) + 1e-12)
    best = None
    for g in [1, 1.3, 1.7, 2.2, 2.8, 3.5, 4.5, 6]:
        y = np.tanh(st * g) / np.tanh(g)
        y = y * ceil / np.max(np.abs(y))
        lu = meter.integrated_loudness(y)
        best = (y, lu, g)
        if lu >= target_lufs:
            break
    y, lu, g = best
    # mild limiter safety
    y = np.clip(y, -ceil, ceil)
    wavfile.write(f"{outdir}/{name}.wav", SR, (y * 32767).astype(np.int16))
    return dict(name=name, dur=len(y) / SR, lufs=lu, peak=20 * np.log10(np.max(np.abs(y))), drive=g)


def finalize_loop(st, name, outdir, target_lufs=-15.0, peak_db=-1.0):
    """no fades (seamless loop)."""
    import pyloudnorm as pyln
    ceil = 10 ** (peak_db / 20)
    st = lowshelf(np.concatenate([st, st, st]), 150, -7.0)[len(st):2 * len(st)]
    st = st / (np.max(np.abs(st)) + 1e-12)
    meter = pyln.Meter(SR)
    for g in [1, 1.3, 1.7, 2.2, 2.8, 3.5, 4.5, 6]:
        y = np.tanh(st * g) / np.tanh(g)
        y = y * ceil / np.max(np.abs(y))
        lu = meter.integrated_loudness(y)
        if lu >= target_lufs:
            break
    wavfile.write(f"{outdir}/{name}.wav", SR, (y * 32767).astype(np.int16))
    return dict(name=name, dur=len(y) / SR, lufs=lu, peak=20 * np.log10(np.max(np.abs(y))), drive=g)


def addp(a, b):
    n = max(len(a), len(b))
    return np.pad(a, (0, n - len(a))) + np.pad(b, (0, n - len(b)))

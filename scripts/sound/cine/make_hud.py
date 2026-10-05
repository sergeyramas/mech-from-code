"""HUD one-shots for infographics (code-made): typing beeps, target lock, alarm, missile-lock beeping, signal-loss glitch.
.venv/bin/python cine/make_hud.py  ->  video/audio/hud/*.wav (48 kHz stereo 16 bit, peak -3 dBFS)"""
import os, sys
import numpy as np
from scipy import signal
from scipy.io import wavfile
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import fx
from fx import *
OUT = os.path.abspath(os.path.join(HERE, '..', '..', 'video/audio/hud')); os.makedirs(OUT, exist_ok=True)


def save(name, x, peak=-3.0):
    x = st2(x)
    x = signal.sosfilt(signal.butter(2, 40, 'highpass', fs=SR, output='sos'), x, axis=0)
    x = x / (np.abs(x).max() + 1e-12) * 10 ** (peak / 20)
    y = signal.resample_poly(x, 160, 147, axis=0)
    wavfile.write(f'{OUT}/{name}.wav', 48000, (np.clip(y, -1, 1) * 32767).astype(np.int16))
    print(f'{name:28s} {len(y) / 48000:5.2f}s')


def blip(f, dur=0.03, wave='sq', a=1.0, glide=None):
    n = N(dur); t = tt(n)
    ff = f if glide is None else np.linspace(f, glide, n)
    ph = 2 * np.pi * np.cumsum(np.broadcast_to(ff, (n,))) / SR
    y = np.sign(np.sin(ph)) * 0.6 + np.sin(ph) * 0.4 if wave == 'sq' else np.sin(ph)
    return y * np.minimum(t / 0.002, 1) * np.exp(-t / (dur * 0.45)) * np.clip((dur - t) / 0.004, 0, 1) * a


def seq(items, total):
    out = np.zeros(N(total))
    for t, y in items:
        place(out, y, t)
    return out


# typing: three single keys + a burst of 14 characters at irregular pace
for i, f in enumerate([1850, 2100, 1650], 1):
    save(f'typing_beep_{i}', lp(blip(f, 0.035, 'sq'), 6000, 2))
t = 0; items = []
for k in range(14):
    f = [1650, 1850, 2100, 2350][int(rng.integers(0, 4))]
    items.append((t, lp(blip(f, 0.03, 'sq', rng.uniform(0.7, 1)), 6500, 2)))
    t += rng.uniform(0.045, 0.11) + (0.12 if k in (5, 9) else 0)
save('typing_burst', seq(items, t + 0.1))
# target lock: searching ticks closing in, then a lock chirp + double confirm
items = [(0.0 + k * 0.16 - 0.002 * k ** 2 * 3, blip(1200 + k * 90, 0.045, 'sq', 0.6)) for k in range(6)]
items.append((1.05, blip(1600, 0.09, 'sq', 0.9)))
items.append((1.20, blip(2400, 0.22, 'sine', 1.0, glide=2500)))
items.append((1.20, blip(3600, 0.22, 'sine', 0.35)))
x = seq(items, 1.6)
save('target_lock', lp(x, 9000, 2))
# target destroyed (confirm): falling two-tone
save('target_destroyed', seq([(0, blip(1400, 0.12, 'sq', 0.9)), (0.14, blip(900, 0.28, 'sq', 0.9, glide=700))], 0.5))
# alarm: two-tone klaxon, 4 cycles, with a little overdrive (loopable by cycle length)
n = N(3.2); t = tt(n); per = 0.8
f = np.where((t % per) < per / 2, 760, 560)
f = signal.sosfilt(signal.butter(1, 30, 'low', fs=SR, output='sos'), f)
ph = 2 * np.pi * np.cumsum(f) / SR
y = np.tanh(2.2 * (np.sin(ph) + 0.35 * np.sin(2 * ph) + 0.2 * np.sin(3 * ph)))
y *= np.minimum(t / 0.01, 1) * np.clip((3.2 - t) / 0.05, 0, 1)
save('alarm', lp(y, 5000, 2))
# missile lock: beeps with accelerating rate (2 -> 16 Hz) ending in a continuous tone
items = []; t = 0.0; dur = 4.0
while t < dur - 0.4:
    r = 2 + 14 * (t / (dur - 0.4)) ** 1.8
    items.append((t, blip(1760, min(0.07, 0.5 / r), 'sq', 0.9)))
    t += 1 / r
tone = blip(1760, 0.8, 'sq', 0.9); tone = np.sin(2 * np.pi * 1760 * tt(N(0.8))) * 0.9 * np.minimum(tt(N(0.8)) / 0.005, 1) * np.clip((0.8 - tt(N(0.8))) / 0.05, 0, 1)
items.append((t, tone))
save('missile_lock_beeping', lp(seq(items, t + 0.85), 8000, 2))
# signal loss: stutter + bitcrush + static + collapsing tone
n = N(1.5); t = tt(n)
tone = np.sin(2 * np.pi * np.cumsum(1400 * np.exp(-t / 0.5) + 80) / SR)
nz = white(n) * (0.2 + 0.8 * (t / 1.5) ** 1.2)
x = tone * np.exp(-t / 0.7) * 0.7 + nz * 0.5
# stutter: repeat tiny slices
out = np.zeros(n); i = 0
while i < n:
    L = int(rng.uniform(0.006, 0.05) * SR); rep = int(rng.integers(1, 5))
    sl = x[i:i + L]
    for _ in range(rep):
        if i >= n: break
        e = min(n, i + len(sl)); out[i:e] = sl[:e - i]; i = e
# bitcrush: sample hold + 5-bit
hold = 6; out = np.repeat(out[::hold], hold)[:n]
out = np.round(out * 12) / 12
out *= curve(n, [(0, 1), (1.0, 0.8), (1.5, 0)], smooth=False)
save('signal_loss_glitch', out)

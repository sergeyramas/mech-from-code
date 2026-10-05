"""One-shots for the mech walk video (step x4, servo_turn, servo_stop, servo_leg, hydraulic_hiss).

Everything is synthesised with the existing toolkit (dsp.py / metal.py / build.valve) - no samples.
Output: sounds/oneshots/*.wav (mono, 44.1 kHz, 16 bit, peak -3 dBFS, dry) + oneshots.json (fit markers
that mix_audio.py uses to stretch / trim the servo to the length of a turn).

Run:  sounds/.venv/bin/python sounds/make_oneshots.py
"""
import os
import sys
import json
import numpy as np
from scipy import signal
from scipy.io import wavfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from dsp import *            # noqa: E402,F401  (SR, N, place, hp, curve, ...)
from metal import *          # noqa: E402,F401  (mech_step, servo, creak, hiss, metal_hit, PLATE, thump ...)
from build import valve      # noqa: E402

OUT = os.path.join(HERE, 'oneshots')
os.makedirs(OUT, exist_ok=True)
META = {}


def save(name, x, peak_db=-3.0):
    x = signal.sosfilt(signal.butter(2, 20, 'highpass', fs=SR, output='sos'), x)
    x = x / (np.max(np.abs(x)) + 1e-12) * 10 ** (peak_db / 20)
    wavfile.write(os.path.join(OUT, name + '.wav'), SR, (x * 32767).astype(np.int16))
    print(f'{name:16s} {len(x) / SR:5.2f}s  peak {20 * np.log10(np.max(np.abs(x))):5.1f} dBFS')


def tail_fade(x, sec):
    x = x.copy()
    k = N(sec)
    x[-k:] *= 0.5 + 0.5 * np.cos(np.pi * np.arange(k) / k)
    return x


def main():
    # ---- 4 step variants: a heavy foot plant. (weight, body-boom frequency): slightly different "feet"
    for i, (w, fb) in enumerate([(1.00, 46), (1.08, 44), (0.92, 50), (1.04, 42)], start=1):
        s = mech_step(w, 0.0, 0.0, 0.0, 2.6, fb)          # no servo / hiss: they are separate one-shots
        s = tail_fade(s[:N(2.1)], 0.5)
        save(f'step_{i}', s)

    # ---- short hydraulic hiss after a step: valve tick + pressure release
    D = 0.9
    h = hiss(D, [(0, 0), (0.02, 1), (0.18, 0.6), (D, 0)], ((0, 6800), (D, 3600)), 0.7) * 0.5
    out = np.zeros(N(D))
    place(out, h, 0)
    place(out, valve(0.5), 0)
    save('hydraulic_hiss', out)

    # ---- servo for a torso turn: head (spin-up) | plateau | tail (spin-down). The plateau has a flat pitch,
    #      so mix_audio.py can cut it out or loop it to fit the real length of a turn
    D = 1.6
    HEAD, MID_END = 0.30, 1.10
    f_pts = [(0, 110), (HEAD, 520), (MID_END, 560), (D, 130)]
    vel = [(0, 0.1), (HEAD, 1.0), (MID_END, 1.0), (D, 0.1)]
    n = N(D)
    sv = servo(D, f_pts, harm=10, whine=0.4, load=0.9, gear=0.8, vel_pts=vel)
    sv = sv * curve(n, [(0, 0), (0.18, 1), (MID_END, 1), (D, 0)])
    cr = creak(D, [(0, 10), (0.8, 55), (D, 8)], 1050, [(0, 0), (0.4, 0.8), (MID_END, 0.6), (D, 0)])
    hs = hiss(D, [(0, 0), (0.3, 0.3), (MID_END, 0.2), (D, 0)], ((0, 4500), (D, 5200)))
    save('servo_turn', sv * 0.5 + cr * 0.2 + hs * 0.05)
    META['servo_turn'] = dict(head_s=HEAD, tail_s=D - MID_END, dur_s=D)

    # ---- lock / brake clunk when the turret reaches its stop
    D = 0.9
    out = np.zeros(N(D))
    place(out, metal_hit(260, D, 0.16, 1.5, PLATE, 5000, 1.0, sizzle=0.0), 0)
    place(out, thump(N(0.8), 100, 44, 0.04, 0.14), 0)
    place(out, hiss(0.5, [(0, 0), (0.03, 1), (0.5, 0)]) * 0.15, 0.01)
    save('servo_stop', tail_fade(out, 0.2))

    # ---- quiet leg-swing servo (used between foot lift and touchdown)
    D = 0.85
    sv = servo(D, [(0, 230), (0.4, 480), (D, 260)], whine=0.35, load=0.7)
    sv = sv * adsr(len(sv), 0.12, 0, 1, 0.3)
    cr = creak(D, [(0, 14), (D, 24)], 1100, [(0, 0), (0.2, 1), (D, 0)])
    save('servo_leg', sv * 0.5 + cr * 0.1)

    with open(os.path.join(OUT, 'oneshots.json'), 'w') as f:
        json.dump(META, f, indent=1)


if __name__ == '__main__':
    main()

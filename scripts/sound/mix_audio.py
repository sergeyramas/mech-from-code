"""Mix the soundtrack of the mech animation from anim_events.json and mux it with the video.

Layers (all synthesised, see make_oneshots.py):
  * step_1..4        on every foot_down; variants alternate, volume +-1.5 dB, pitch +-3 %; turn steps are lighter
  * hydraulic_hiss   0.10-0.16 s after every step
  * servo_leg        quiet, from foot_lift to foot_down
  * servo_turn       over each torso_turns segment, cut / looped (cross-faded plateau) to the exact length;
                     servo_stop clunk + hiss at the end of the segment
  * hum              reactor / hydraulic pump, quiet, breathing at the same rate as the animation
Master: light room reverb, 20 Hz high-pass, soft limiter, peak -1 dBFS (no clipping), written as 16 bit wav,
then ffmpeg muxes it with the silent video (video stream is copied, audio AAC 192k).

Usage (sounds venv):
  .venv/bin/python mix_audio.py --events ../blender/renders/anim_events.json \
      --video ../blender/renders/mech_walk_v2_silent.mp4 --out ../blender/renders/mech_walk_v2.mp4
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
import dsp                                   # noqa: E402
from dsp import SR, N, tt, place, pan2, make_ir, reverb, finalize, lp, hp, brown, spec_noise  # noqa: E402

FFMPEG = '/opt/homebrew/bin/ffmpeg'
FFPROBE = '/opt/homebrew/bin/ffprobe'


def load(oneshots, name):
    sr, x = wavfile.read(os.path.join(oneshots, name + '.wav'))
    assert sr == SR, (name, sr)
    x = x.astype(np.float64) / 32768.0
    return x if x.ndim == 1 else x.mean(1)


def repitch(x, ratio):
    """play back at `ratio` speed (pitch and duration change together); ratio quantised to 1 %"""
    down = int(round(100 * ratio))
    if down == 100:
        return x
    return signal.resample_poly(x, 100, down)


def db(v):
    return 10 ** (v / 20.0)


def put(out, seg, start, fin, fout):
    """add seg at sample `start` with equal-power fade-in / fade-out (samples)"""
    seg = seg.copy()
    if fin > 0:
        k = min(fin, len(seg))
        seg[:k] *= np.sin(0.5 * np.pi * np.arange(k) / k)
    if fout > 0:
        k = min(fout, len(seg))
        seg[-k:] *= np.cos(0.5 * np.pi * np.arange(k) / k)
    e = min(len(out), start + len(seg))
    if e > start:
        out[start:e] += seg[:e - start]


def fit_servo(x, dur_s, head_s, tail_s, xf_s=0.05):
    """Stretch / trim the servo one-shot to exactly dur_s without changing its pitch:
    head (spin-up) + plateau (cut or cross-fade-looped) + tail (spin-down, anchored at the end)."""
    L, h, t, xf = N(dur_s), N(head_s), N(tail_s), N(xf_s)
    head, mid, tail = x[:h], x[h:len(x) - t], x[len(x) - t:]
    out = np.zeros(L)
    tl = min(t, L)
    put(out, tail[len(tail) - tl:], L - tl, xf, 0)
    left_end = L - tl + xf
    pos, first = 0, True
    segs = iter([head] + [mid] * 64)
    for seg in segs:
        end = min(pos + len(seg), left_end)
        seg = seg[:end - pos]
        put(out, seg, pos, 0 if first else xf, xf)
        first = False
        if end >= left_end:
            break
        pos = end - xf
    return out


def hum_bed(n, breathe_hz, rng):
    t = np.arange(n) / SR
    f0 = 48.0
    h = np.zeros(n)
    for k, a in [(1, 1.0), (2, 0.6), (3, 0.4), (4, 0.25), (5, 0.12)]:
        h += a * np.sin(2 * np.pi * f0 * k * (1 + 0.0008 * k) * t + rng.uniform(0, 6.28))
    h *= 1 + 0.16 * np.sin(2 * np.pi * 4.1 * t) + 0.10 * np.sin(2 * np.pi * 0.37 * t + 1.0)
    rum = lp(brown(n), 180, 2)
    rum /= np.std(rum) + 1e-9
    hf = hp(lp(dsp.white(n), 6000, 2), 1500, 2)
    hf /= np.std(hf) + 1e-9
    bed = h / np.std(h) * 0.55 + rum * 0.45 + hf * 0.05
    bed /= np.std(bed)
    bed *= 1 + 0.19 * np.sin(2 * np.pi * breathe_hz * t - 1.2)          # +-1.5 dB breathing, same rate as the animation
    return bed


def build_mix(ev, oneshots, seed, breathe_hz, log=print):
    rng = np.random.default_rng(seed)
    fps = ev['fps']
    nfr = ev['frame_end'] - ev['frame_start'] + 1
    D = nfr / fps
    tail = 3.0
    buf = np.zeros((N(D + tail), 2))
    T = lambda fr: (fr - ev['frame_start']) / fps             # frame -> seconds on the video timeline
    meta = json.load(open(os.path.join(oneshots, 'oneshots.json')))
    steps = [load(oneshots, f'step_{i}') for i in range(1, 5)]
    hs = load(oneshots, 'hydraulic_hiss')
    sv = load(oneshots, 'servo_turn')
    stop = load(oneshots, 'servo_stop')
    leg = load(oneshots, 'servo_leg')

    def add(x, t, pan, gain):
        place(buf, pan2(x * gain, pan), t)

    placed = []
    downs = sorted(ev['foot_down'], key=lambda e: e['frame'])
    lifts = {(e['phase'], e['step'], e['foot']): e for e in ev['foot_lift']}
    for i, e in enumerate(downs):
        t = T(e['frame'])
        w = e.get('weight', 1.0)
        side = -1 if e['foot'].endswith('L') else 1
        var = i % 4
        pitch = rng.uniform(0.97, 1.03) * (1 + 0.10 * (1 - w))
        gain = db(rng.uniform(-1.5, 1.0)) * w
        pan = 0.18 * side + rng.uniform(-0.04, 0.04)
        add(repitch(steps[var], pitch), t, pan, gain)
        # hydraulic hiss after the step (pressure release as the leg takes the weight)
        th = t + rng.uniform(0.10, 0.16)
        add(repitch(hs, rng.uniform(0.96, 1.05)), th, pan * 0.7, 0.34 * w * db(rng.uniform(-1.5, 1.0)))
        # quiet servo whisper for the swing that ended with this step
        lf = lifts.get((e['phase'], e['step'], e['foot']))
        if lf is not None:
            t0 = T(lf['frame'])
            d = max(0.2, t - t0)
            x = repitch(leg, rng.uniform(0.95, 1.05))[:N(d)]
            x = x * np.minimum(1, np.arange(len(x)) / N(0.1)) * np.minimum(1, (len(x) - np.arange(len(x))) / N(min(0.35, d * 0.5)))
            add(x, t0, -0.5 * side, 0.15)
        placed.append(dict(frame=e['frame'], foot=e['foot'], t=round(t, 4), var=var + 1, gain=round(float(gain), 3),
                           pitch=round(float(pitch), 3)))

    for seg in ev['torso_turns']:
        t0, t1 = T(seg['start_frame']), T(seg['end_frame'])
        dur = t1 - t0 + 0.04
        x = fit_servo(repitch(sv, rng.uniform(0.96, 1.05)), dur, meta['servo_turn']['head_s'], meta['servo_turn']['tail_s'])
        sign = np.sign(seg['to_deg'] - seg['from_deg'])
        add(x, t0 - 0.04, 0.2 * sign, 0.34)
        amp = min(1.0, abs(seg['to_deg'] - seg['from_deg']) / 80.0 + 0.4)
        end_zero = abs(seg['to_deg']) < 1.0                 # returning to the centre: a softer click-in
        add(repitch(stop, rng.uniform(0.97, 1.04)), t1, 0.1 * sign, 0.55 * amp * (0.8 if end_zero else 1.0))
        placed.append(dict(torso_segment=[seg['start_frame'], seg['end_frame']], servo_s=round(dur, 3)))

    # reactor / pump hum under everything
    hum = hum_bed(len(buf), breathe_hz, rng)
    buf += pan2(hum, 0) * db(-31.0)                         # ~ -31 dBFS rms before the master
    return buf, D, placed


def master(buf, D, outdir, name, target_lufs=-18.0):
    ir = make_ir(1.5, pre=0.015, damp=(1.3, 1.0, 0.5))
    st = reverb(buf, ir, 0.16)[:N(D)]
    return finalize(st, name, outdir, target_lufs=target_lufs, peak_db=-1.0, fin=0.01, fout=0.6, low_db=-4.0)


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError(' '.join(cmd) + '\n' + r.stderr[-2000:])
    return r.stdout


def main():
    ap = argparse.ArgumentParser()
    b = os.path.join(HERE, '..', 'blender', 'renders')
    ap.add_argument('--events', default=os.path.join(b, 'anim_events.json'))
    ap.add_argument('--oneshots', default=os.path.join(HERE, 'oneshots'))
    ap.add_argument('--video', default=os.path.join(b, 'mech_walk_v2_silent.mp4'))
    ap.add_argument('--out', default=os.path.join(b, 'mech_walk_v2.mp4'))
    ap.add_argument('--wav-name', default='mech_walk_v2_audio')
    ap.add_argument('--breathe-hz', type=float, default=0.26)
    ap.add_argument('--seed', type=int, default=11)
    a = ap.parse_args()

    ev = json.load(open(a.events))
    buf, D, placed = build_mix(ev, a.oneshots, a.seed, a.breathe_hz)
    outdir = os.path.dirname(os.path.abspath(a.out))
    info = master(buf, D, outdir, a.wav_name)
    print('master:', {k: (round(v, 2) if isinstance(v, float) else v) for k, v in info.items()})
    json.dump(dict(master=info, placed=placed), open(os.path.join(outdir, a.wav_name + '_log.json'), 'w'), indent=1)
    wav = os.path.join(outdir, a.wav_name + '.wav')
    if os.path.exists(a.video):
        vdur = float(run([FFPROBE, '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', a.video]))
        run([FFMPEG, '-y', '-loglevel', 'error', '-i', a.video, '-i', wav, '-map', '0:v:0', '-map', '1:a:0',
             '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k', '-t', f'{vdur:.6f}', '-movflags', '+faststart', a.out])
        print('muxed ->', a.out)
    else:
        print('video not found, wav only:', wav)


if __name__ == '__main__':
    main()

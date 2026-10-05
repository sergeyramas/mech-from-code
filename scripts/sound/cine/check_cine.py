"""Sync / level check of the muxed cinematic: decode audio from the mp4, find onsets near key events, draw a
spectrogram with event markers.  .venv/bin/python cine/check_cine.py [out.png]"""
import sys, os, json, subprocess
import numpy as np
from scipy import signal
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
MP4 = os.path.join(ROOT, 'blender/renders/mech_cinematic_v1_sound.mp4')
EV = json.load(open(os.path.join(ROOT, 'blender/renders/cine/events.json')))
SR = 48000
raw = subprocess.run(['/opt/homebrew/bin/ffmpeg', '-v', 'error', '-i', MP4, '-vn', '-ac', '2', '-ar', str(SR), '-f', 'f32le', '-'],
                     capture_output=True).stdout
x = np.frombuffer(raw, np.float32).reshape(-1, 2).astype(float)
m = x.mean(1)
print('decoded', len(m) / SR, 's')
km = EV['key_moments_render_s']
events = [('cannon', km['cannon_fire']), ('truck', km['truck_explosion']), ('missile0', 16.41), ('bld_core', km['building_core']),
          ('jeep', km['jeep_crush']), ('block_kick', km['block_kicks'][0]), ('torso_snap', km['torso_snap']),
          ('rocket_hit', km['rocket_impact']), ('nuke_flash', km['nuke_flash'])]
# onset = biggest rise of the 2 ms energy over the mean of the preceding 60 ms (broadband, >80 Hz), +-0.25 s around the event
xh = signal.sosfilt(signal.butter(4, 80, 'high', fs=SR, output='sos'), m)
hop = int(0.002 * SR)
E = np.sqrt(np.add.reduceat(xh ** 2, np.arange(0, len(xh) - hop, hop)) / hop)
print(f'{"event":12s} {"video_s":>8s} {"audio_onset_s":>14s} {"diff_ms":>8s}  frame')
res = []
for name, tv in events:
    i0, i1 = int((tv - 0.25) / 0.002), int((tv + 0.25) / 0.002)
    best, bi = -1, i0
    for i in range(i0, i1):
        prev = E[i - 30:i].mean() + 1e-5
        r = E[i:i + 3].mean() / prev
        if r > best:
            best, bi = r, i
    ta = bi * 0.002
    res.append((name, tv, ta))
    print(f'{name:12s} {tv:8.3f} {ta:14.3f} {(ta - tv) * 1000:8.1f}  {int(round(tv * 24)) + 1}  rise x{best:.1f}')
fig, ax = plt.subplots(2, 1, figsize=(20, 9), sharex=True)
t = np.arange(len(m)) / SR
ax[0].plot(t[::40], m[::40], lw=0.4)
f, tt_, S = signal.spectrogram(m, SR, nperseg=2048, noverlap=1536)
ax[1].pcolormesh(tt_, f, 10 * np.log10(S + 1e-12), vmin=-110, vmax=-30, shading='auto')
ax[1].set_yscale('symlog', linthresh=200); ax[1].set_ylim(20, 20000)
for name, tv in events:
    for a_ in ax:
        a_.axvline(tv, color='r', lw=0.6)
    ax[0].text(tv, 0.9, name, rotation=90, fontsize=7, color='r')
plt.tight_layout()
plt.savefig(sys.argv[1] if len(sys.argv) > 1 else '/tmp/cine_spec.png', dpi=60)

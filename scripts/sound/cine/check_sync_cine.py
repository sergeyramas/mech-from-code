"""Sync proof: (1) mp4 audio vs cine_mix.wav cross-correlation lag, (2) per-event audio onset (from the stem that carries the
event) vs the frame where the picture changes (mean-luma jump from ffmpeg signalstats)."""
import os, json, subprocess, numpy as np
from scipy import signal
from scipy.io import wavfile
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
A = os.path.join(ROOT, 'video/audio'); MP4 = os.path.join(ROOT, 'blender/renders/mech_cinematic_v1_sound.mp4')
FF = '/opt/homebrew/bin/ffmpeg'
sr, w = wavfile.read(A + '/cine_mix.wav'); w = w.astype(float).mean(1) / 32768
raw = subprocess.run([FF, '-v', 'error', '-i', MP4, '-vn', '-ac', '2', '-ar', '48000', '-f', 'f32le', '-'], capture_output=True).stdout
d = np.frombuffer(raw, np.float32).reshape(-1, 2).mean(1)
n = min(len(w), len(d), 48000 * 40)
c = signal.correlate(d[:n], w[:n], 'full', method='fft'); lag = np.argmax(c) - (n - 1)
print(f'mp4-vs-wav lag: {lag / 48:.2f} ms (AAC decode)')
# picture luma per frame
out = subprocess.run([FF, '-v', 'error', '-i', os.path.join(ROOT, 'blender/renders/mech_cinematic_v1.mp4'), '-vf', 'scale=160:-1,signalstats,metadata=print:key=lavfi.signalstats.YAVG',
                      '-an', '-f', 'null', '-'], capture_output=True, text=True, stderr=subprocess.STDOUT).stdout if False else None
p = subprocess.run([FF, '-v', 'info', '-i', os.path.join(ROOT, 'blender/renders/mech_cinematic_v1.mp4'), '-vf', 'scale=160:-1,signalstats,metadata=print:key=lavfi.signalstats.YAVG', '-an', '-f', 'null', '-'], capture_output=True, text=True)
ys = np.array([float(l.split('=')[1]) for l in p.stderr.splitlines() if 'YAVG' in l])
dy = np.diff(ys)
def stem(k):
    s, x = wavfile.read(f'{A}/cine_sfx_stems/{k}.wav'); return x.astype(float).mean(1)
def onset(x, t, w_=0.25):
    xh = signal.sosfilt(signal.butter(4, 80, 'high', fs=48000, output='sos'), x); hop = 96
    E = np.sqrt(np.add.reduceat(xh ** 2, np.arange(0, len(xh) - hop, hop)) / hop); best, bi = -1, 0
    for i in range(int((t - w_) / 0.002), int((t + w_) / 0.002)):
        r = E[i:i + 3].mean() / (E[i - 30:i].mean() + 1e-6)
        if r > best: best, bi = r, i
    return bi * 0.002
tests = [('cannon/muzzle flash', 'weapons', 9.75, 235), ('truck explosion', 'explosions', 9.80, 236), ('bld core', 'explosions', 17.35, 417),
         ('jeep crush', 'explosions', 20.5, 493), ('rocket impact', 'rocket', 28.343, 681), ('nuke flash (silence cut)', 'nuke', 31.836, 765)]
print(f'{"event":26s} {"event_frame":>11s} {"video_t":>8s} {"audio_onset":>11s} {"diff_ms":>8s}  max-luma-jump frame within +-6f')
for name, k, t, fr in tests:
    x = stem(k); ta = onset(x, t, 0.08 if fr in (417, 681) else 0.25)
    lo = max(0, fr - 7); hi = fr + 5; jf = lo + 1 + int(np.argmax(dy[lo:hi])) + 1 - 1
    print(f'{name:26s} {fr:11d} {t:8.3f} {ta:11.3f} {(ta - t) * 1000:8.1f}  frame {jf + 1} (t={jf / 24:.3f}, dY={dy[jf - 1] if jf>0 else 0:+.1f})')

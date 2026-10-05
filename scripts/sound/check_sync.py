"""Verify the muxed mp4: stream durations, video frame timestamps and step-onset sync.

For every foot_down event (anim_events.json) the audio is decoded back from the mp4 and the onset of the
step transient is located; its time is compared with the presentation time of the touchdown frame
(frame f is shown at (f-1)/fps). Prints a table, exit code 1 if |offset| > --tol-ms for any step.

Usage: .venv/bin/python check_sync.py ../blender/renders/mech_walk_v2.mp4 ../blender/renders/anim_events.json
"""
import sys
import json
import argparse
import subprocess
import numpy as np
from scipy import signal

FFMPEG = '/opt/homebrew/bin/ffmpeg'
FFPROBE = '/opt/homebrew/bin/ffprobe'
SR = 44100


def probe(path):
    out = subprocess.run([FFPROBE, '-v', 'error', '-show_entries',
                          'stream=index,codec_type,codec_name,width,height,r_frame_rate,nb_frames,duration,sample_rate,channels,pix_fmt,start_time',
                          '-show_entries', 'format=duration', '-of', 'json', path], capture_output=True, text=True).stdout
    return json.loads(out)


def frame_times(path, n=None):
    out = subprocess.run([FFPROBE, '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'frame=pts_time',
                          '-of', 'csv=p=0', path], capture_output=True, text=True).stdout.split()
    return np.array([float(v.split(',')[0]) for v in out if v.strip(',')])


def decode(path):
    raw = subprocess.run([FFMPEG, '-v', 'error', '-i', path, '-vn', '-ac', '1', '-ar', str(SR), '-f', 'f32le', '-'],
                         capture_output=True).stdout
    return np.frombuffer(raw, dtype=np.float32).astype(np.float64)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('mp4')
    ap.add_argument('events')
    ap.add_argument('--tol-ms', type=float, default=21.0)        # half a frame at 24 fps
    a = ap.parse_args()
    ev = json.load(open(a.events))
    info = probe(a.mp4)
    for s in info['streams']:
        print({k: s.get(k) for k in ('codec_type', 'codec_name', 'width', 'height', 'r_frame_rate', 'nb_frames',
                                     'duration', 'sample_rate', 'channels', 'pix_fmt', 'start_time')})
    print('format duration', info['format']['duration'])
    ft = frame_times(a.mp4)
    nfr = ev['frame_end'] - ev['frame_start'] + 1
    print(f'video frames {len(ft)} (expected {nfr}); first pts {ft[0]:.4f}, last pts {ft[-1]:.4f}')
    x = decode(a.mp4)
    print(f'decoded audio {len(x) / SR:.4f} s')
    # transient detector: 150 Hz - 3 kHz band, 1.5 ms smoothed envelope
    y = signal.sosfilt(signal.butter(4, [150, 3000], 'bandpass', fs=SR, output='sos'), x)
    env = signal.sosfilt(signal.butter(2, 300, 'lowpass', fs=SR, output='sos'), np.abs(y))
    bad = 0
    print(f'{"frame":>5} {"foot":7} {"video_t":>8} {"audio_on":>9} {"diff_ms":>8}')
    for e in sorted(ev['foot_down'], key=lambda e: e['frame']):
        tv = ft[e['frame'] - ev['frame_start']] if e['frame'] - ev['frame_start'] < len(ft) else (e['frame'] - 1) / ev['fps']
        i0, i1 = int((tv - 0.10) * SR), int((tv + 0.12) * SR)
        seg = env[i0:i1]
        base = np.median(env[max(0, i0 - int(0.3 * SR)):i0]) if i0 > 0 else 0
        pk = seg.max()
        thr = base + 0.2 * (pk - base)
        k = int(np.argmax(seg > thr))
        ta = (i0 + k) / SR
        d = (ta - tv) * 1000
        flag = '' if abs(d) <= a.tol_ms else '  <-- OFF'
        bad += bool(flag)
        print(f'{e["frame"]:5d} {e["foot"]:7} {tv:8.4f} {ta:9.4f} {d:8.1f}{flag}')
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()

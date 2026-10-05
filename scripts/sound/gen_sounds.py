#!/usr/bin/env python3
"""
Sound synthesis for demo: animal fight, armed combat, mech robot.
Tools: numpy + scipy only (no external audio libs needed).
Output: WAV files, 44100 Hz, mono, 3-5 seconds each.
"""

import numpy as np
from scipy.io import wavfile
from scipy.signal import butter, lfilter, sosfilt, butter
import os

SR = 44100
OUT_DIR = os.path.dirname(os.path.abspath(__file__))


def save(name, audio, sr=SR):
    audio = np.clip(audio, -1.0, 1.0)
    data = (audio * 32767).astype(np.int16)
    path = os.path.join(OUT_DIR, name)
    wavfile.write(path, sr, data)
    print(f"  saved: {path}  ({len(data)/sr:.2f}s)")


def butter_bandpass(lowcut, highcut, fs, order=4):
    nyq = fs / 2
    low = lowcut / nyq
    high = highcut / nyq
    b, a = butter(order, [low, high], btype='band')
    return b, a


def butter_lowpass(cutoff, fs, order=4):
    nyq = fs / 2
    b, a = butter(order, cutoff / nyq, btype='low')
    return b, a


def butter_highpass(cutoff, fs, order=4):
    nyq = fs / 2
    b, a = butter(order, cutoff / nyq, btype='high')
    return b, a


def envelope(t, attack, decay, sustain_level, release, total):
    """Simple ADSR envelope."""
    env = np.ones_like(t)
    a_samp = int(attack * SR)
    d_samp = int(decay * SR)
    r_samp = int(release * SR)
    total_samp = len(t)

    env[:a_samp] = np.linspace(0, 1, a_samp)
    if a_samp + d_samp < total_samp:
        env[a_samp:a_samp + d_samp] = np.linspace(1, sustain_level, d_samp)
        env[a_samp + d_samp:total_samp - r_samp] = sustain_level
        env[total_samp - r_samp:] = np.linspace(sustain_level, 0, r_samp)
    return env


def noise_burst(duration, color='pink'):
    n = int(duration * SR)
    white = np.random.randn(n)
    if color == 'pink':
        # Pink noise via 1/f shaping
        freqs = np.fft.rfftfreq(n)
        freqs[0] = 1e-6
        spectrum = np.fft.rfft(white)
        spectrum /= np.sqrt(freqs)
        return np.fft.irfft(spectrum)[:n]
    elif color == 'brown':
        return np.cumsum(white) * 0.01
    return white


# ---------------------------------------------------------------------------
# 1. BOAR ATTACK — squeal + crunch + impact thuds
# ---------------------------------------------------------------------------
def gen_boar_attack():
    print("Generating: boar_attack.wav")
    dur = 4.0
    t = np.linspace(0, dur, int(dur * SR))

    # High-pitched squeal (pig-like): FM modulated
    squeal_freq = 900 + 400 * np.sin(2 * np.pi * 5 * t)
    squeal = np.sin(2 * np.pi * squeal_freq * t)
    squeal_env = envelope(t, 0.02, 0.1, 0.8, 0.4, dur)
    squeal *= squeal_env * 0.5

    # Crunching impacts — 3 hits
    impact = np.zeros_like(t)
    for hit_t in [0.3, 1.2, 2.5]:
        hit_n = int(hit_t * SR)
        hit_len = int(0.12 * SR)
        if hit_n + hit_len < len(t):
            burst = np.random.randn(hit_len)
            env_hit = np.exp(-np.linspace(0, 15, hit_len))
            impact[hit_n:hit_n + hit_len] += burst * env_hit * 0.8

    b, a = butter_lowpass(600, SR)
    impact = lfilter(b, a, impact)

    # Grunt growl — low rumble with pitch variation
    grunt_freq = 120 + 60 * np.sin(2 * np.pi * 1.5 * t) + 30 * np.random.randn(len(t)) * 0.01
    grunt = np.sin(2 * np.pi * grunt_freq * t) * 0.3
    grunt += 0.15 * np.tanh(3 * grunt)  # saturation for growl character
    grunt_env = envelope(t, 0.05, 0.2, 0.6, 0.5, dur)
    grunt *= grunt_env

    # Rustle / brush noise
    noise = noise_burst(dur, 'pink') * 0.15
    b2, a2 = butter_bandpass(200, 3000, SR)
    noise = lfilter(b2, a2, noise)
    noise_env = np.exp(-t * 0.3) * 0.5 + 0.2
    noise *= noise_env

    mix = squeal + impact + grunt + noise
    mix /= np.max(np.abs(mix) + 1e-9) * 1.1
    save("boar_attack.wav", mix)


# ---------------------------------------------------------------------------
# 2. BEAR ATTACK — roar + paw swipe + heavy thud
# ---------------------------------------------------------------------------
def gen_bear_attack():
    print("Generating: bear_attack.wav")
    dur = 4.5
    t = np.linspace(0, dur, int(dur * SR))

    # Roar: low FM sweep + harmonics
    roar_base = 80 + 40 * np.sin(2 * np.pi * 0.8 * t)
    roar = np.sin(2 * np.pi * roar_base * t)
    roar += 0.5 * np.sin(2 * np.pi * roar_base * 2 * t)
    roar += 0.25 * np.sin(2 * np.pi * roar_base * 3 * t)
    roar += 0.6 * np.tanh(2 * roar)  # growl distortion
    roar_env = envelope(t, 0.1, 0.3, 0.85, 0.8, dur)
    roar *= roar_env * 0.45

    # Paw swipe — broadband whoosh
    swipe_t = 1.8
    swipe_n = int(swipe_t * SR)
    swipe_len = int(0.4 * SR)
    swipe = np.zeros_like(t)
    if swipe_n + swipe_len < len(t):
        burst = np.random.randn(swipe_len)
        swipe_env_local = np.hanning(swipe_len)
        swipe[swipe_n:swipe_n + swipe_len] = burst * swipe_env_local * 0.6
        b, a = butter_bandpass(500, 8000, SR)
        swipe = lfilter(b, a, swipe)

    # Heavy body impact thuds
    thud = np.zeros_like(t)
    for ht in [0.4, 2.3]:
        hn = int(ht * SR)
        hl = int(0.25 * SR)
        if hn + hl < len(t):
            n = np.random.randn(hl)
            env_t = np.exp(-np.linspace(0, 20, hl))
            thud[hn:hn + hl] += n * env_t * 0.9
    b2, a2 = butter_lowpass(300, SR)
    thud = lfilter(b2, a2, thud)
    # Add sub-rumble
    for ht in [0.4, 2.3]:
        hn = int(ht * SR)
        hl = int(0.3 * SR)
        sub_t_local = np.arange(hl) / SR
        sub = np.sin(2 * np.pi * 45 * sub_t_local) * np.exp(-sub_t_local * 12)
        if hn + hl < len(t):
            thud[hn:hn + hl] += sub * 0.5

    # Breathing / snort at start
    snort_len = int(0.3 * SR)
    snort = np.random.randn(snort_len)
    snort_env_local = np.hanning(snort_len) * np.exp(-np.linspace(0, 5, snort_len))
    snort = snort * snort_env_local
    b3, a3 = butter_bandpass(300, 1500, SR)
    snort = lfilter(b3, a3, snort)
    full_snort = np.zeros_like(t)
    full_snort[:snort_len] = snort * 0.4

    mix = roar + swipe + thud + full_snort
    mix /= np.max(np.abs(mix) + 1e-9) * 1.1
    save("bear_attack.wav", mix)


# ---------------------------------------------------------------------------
# 3. ARMED SKIRMISH — sword clashes + battle cries + running troops
# ---------------------------------------------------------------------------
def gen_armed_skirmish():
    print("Generating: armed_skirmish.wav")
    dur = 5.0
    t = np.linspace(0, dur, int(dur * SR))
    mix = np.zeros_like(t)

    # Sword/axe clashes — metallic ring
    clash_times = [0.2, 0.75, 1.3, 1.9, 2.8, 3.5, 4.2]
    for ct in clash_times:
        cn = int(ct * SR)
        cl = int(0.6 * SR)
        if cn + cl >= len(t):
            break
        cl_t = np.arange(cl) / SR

        # Metal ring: multiple partials with fast decay
        ring = np.zeros(cl)
        for f, amp in [(1800, 0.6), (3200, 0.4), (2400, 0.35), (4500, 0.2), (900, 0.3)]:
            ring += amp * np.sin(2 * np.pi * f * cl_t) * np.exp(-cl_t * 8)
        # Transient click
        click = np.random.randn(cl) * np.exp(-cl_t * 80)
        b, a = butter_highpass(1500, SR)
        click = lfilter(b, a, click) * 0.5
        mix[cn:cn + cl] += (ring + click) * 0.5

    # Running boots — rhythmic low thumps
    step_interval = 0.22  # seconds between steps
    step_t = 0.0
    while step_t < dur:
        sn = int(step_t * SR)
        sl = int(0.08 * SR)
        if sn + sl < len(t):
            step_burst = np.random.randn(sl) * np.exp(-np.linspace(0, 30, sl))
            mix[sn:sn + sl] += step_burst * 0.25
        step_t += step_interval + np.random.uniform(-0.02, 0.02)

    # Low rumble of many feet
    rumble = noise_burst(dur, 'brown')
    b2, a2 = butter_lowpass(150, SR)
    rumble = lfilter(b2, a2, rumble)
    # Swell envelope
    rumble_env = np.linspace(0, 0.3, len(t)) * np.clip(np.sin(np.pi * t / dur), 0, 1)
    mix += rumble * rumble_env * 0.4

    # Battle shouts — formant-like noise bursts (simplified vocal)
    shout_times = [0.5, 1.5, 2.4, 3.8]
    for st in shout_times:
        sn = int(st * SR)
        sl = int(0.35 * SR)
        if sn + sl >= len(t):
            break
        shout_t_local = np.arange(sl) / SR
        # Voiced noise: pitched excitation through formant filter
        pitch = 180 + np.random.uniform(-30, 30)
        excitation = np.sin(2 * np.pi * pitch * shout_t_local)
        excitation += 0.3 * np.random.randn(sl)
        b3, a3 = butter_bandpass(400, 2500, SR)
        shaped = lfilter(b3, a3, excitation)
        env_s = np.hanning(sl) * 0.6
        mix[sn:sn + sl] += shaped * env_s * 0.55

    mix /= np.max(np.abs(mix) + 1e-9) * 1.1
    save("armed_skirmish.wav", mix)


# ---------------------------------------------------------------------------
# 4. MECH ROBOT — heavy steps + torso rotation + servos
# ---------------------------------------------------------------------------
def gen_mech_robot():
    print("Generating: mech_robot.wav")
    dur = 5.0
    t = np.linspace(0, dur, int(dur * SR))
    mix = np.zeros_like(t)

    # Heavy footsteps: 3 steps
    for step_t in [0.3, 1.6, 3.0]:
        sn = int(step_t * SR)
        sl = int(0.5 * SR)
        if sn + sl >= len(t):
            break
        st_arr = np.arange(sl) / SR

        # Sub-bass thud
        sub = np.sin(2 * np.pi * 40 * st_arr) * np.exp(-st_arr * 10) * 0.8
        # Metal clang on impact
        clang_freqs = [320, 650, 980, 1400]
        clang = sum(np.sin(2 * np.pi * f * st_arr) * np.exp(-st_arr * 5) * 0.3
                    for f in clang_freqs)
        # Hydraulic hiss after step
        hiss = np.random.randn(sl) * np.exp(-st_arr * 6) * 0.2
        b, a = butter_bandpass(2000, 8000, SR)
        hiss = lfilter(b, a, hiss)
        # Ground shake rumble
        shake = np.random.randn(sl) * np.exp(-st_arr * 4) * 0.3
        b2, a2 = butter_lowpass(200, SR)
        shake = lfilter(b2, a2, shake)

        mix[sn:sn + sl] += sub + clang + hiss + shake

    # Torso rotation (1.0s to 2.5s): hydraulic groan
    rot_start = int(1.0 * SR)
    rot_len = int(1.5 * SR)
    rot_t = np.arange(rot_len) / SR
    # Slow FM sweep down: hydraulic pressure sound
    rot_freq = 180 - 80 * (rot_t / 1.5)
    rot_signal = np.sin(2 * np.pi * rot_freq * rot_t)
    rot_signal += 0.4 * np.sin(2 * np.pi * rot_freq * 2 * rot_t)
    # Servo whine on top
    servo_freq = 3500 + 500 * np.sin(2 * np.pi * 2 * rot_t)
    rot_signal += 0.15 * np.sin(2 * np.pi * servo_freq * rot_t)
    rot_env = np.hanning(rot_len) * 0.5
    mix[rot_start:rot_start + rot_len] += rot_signal * rot_env

    # Continuous servo whirr throughout
    servo_whirr = np.sin(2 * np.pi * (4200 + 200 * np.sin(2 * np.pi * 3 * t)) * t)
    servo_whirr += 0.3 * np.sin(2 * np.pi * (2100 + 100 * np.sin(2 * np.pi * 7 * t)) * t)
    servo_env = 0.08 + 0.04 * np.sin(2 * np.pi * 0.5 * t)
    mix += servo_whirr * servo_env

    # Mechanical gear clunks
    for gt in [0.8, 2.0, 3.7, 4.5]:
        gn = int(gt * SR)
        gl = int(0.06 * SR)
        if gn + gl < len(t):
            gt_arr = np.arange(gl) / SR
            gear = np.sin(2 * np.pi * 800 * gt_arr) * np.exp(-gt_arr * 60)
            gear += np.random.randn(gl) * np.exp(-gt_arr * 40) * 0.3
            mix[gn:gn + gl] += gear * 0.4

    # Low idle hum / engine
    idle_freq = 60 + 5 * np.sin(2 * np.pi * 0.2 * t)
    idle = np.sin(2 * np.pi * idle_freq * t) * 0.12
    idle += 0.06 * np.sin(2 * np.pi * idle_freq * 2 * t)
    idle += 0.03 * np.sin(2 * np.pi * idle_freq * 3 * t)
    mix += idle

    mix /= np.max(np.abs(mix) + 1e-9) * 1.1
    save("mech_robot.wav", mix)


# ---------------------------------------------------------------------------
# Run all
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print(f"Output directory: {OUT_DIR}\n")
    gen_boar_attack()
    gen_bear_attack()
    gen_armed_skirmish()
    gen_mech_robot()
    print("\nDone.")

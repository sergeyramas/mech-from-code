"""Metal / wood / mech synthesis: modal banks, servos, hydraulics."""
import numpy as np
from scipy import signal
from dsp import *
from organic import thump, granular, body_hit

BAR = [1, 2.756, 5.404, 8.933, 13.344, 18.64, 24.8]
PLATE = [1, 1.59, 2.14, 2.30, 2.65, 2.92, 3.16, 3.5, 4.06, 4.15, 5.0, 5.9, 6.7, 8.2]
BELL = [1, 2.0, 2.4, 3.0, 4.07, 5.4, 6.8, 8.9]


def metal_hit(f0, dur=1.2, tau=0.35, bright=1.0, ratios=BAR, hard=9000, amp=1.0, beat=True, sizzle=0.25):
    fr, am, ta = [], [], []
    for r in ratios:
        for k in range(2 if beat else 1):
            f = f0 * r * (1 + rng.uniform(-0.012, 0.012)) * (1 + (0.0015 + 0.003 * rng.random() if k else 0))
            fr.append(f)
            am.append(r ** (-0.55 / bright) * (0.65 if k else 1.0) * rng.uniform(0.6, 1.2))
            ta.append(tau * rng.uniform(0.6, 1.3) / (1 + 0.22 * r))
    ir = modal_ir(fr, am, ta, dur)
    ex = addp(burst(0.0015, hard), 0.3 * burst(0.006, hard * 0.4))
    y = excite(ir, ex)
    n = len(y)
    y /= np.max(np.abs(y)) + 1e-9
    click = hp(white(n), 3500, 2) * expdec(n, 0.003) * 0.5
    siz = bp(white(n), 5000, 12000) * expdec(n, 0.12) * sizzle * (1 - np.exp(-np.arange(n) / SR / 0.004))
    return (y + click + siz) * amp


def scrape(dur=0.6, f0=2200, vel=[(0, 0.2), (0.15, 1.0), (0.6, 0.4)], power=1.0):
    """metal-on-metal slide: stick-slip pulses into high-Q ringing modes + hiss"""
    n = N(dur)
    v = curve(n, vel)
    rate = 50 + 260 * v
    ph = np.cumsum(rate) / SR
    imp = np.zeros(n)
    idx = np.where(np.diff(np.floor(ph + rng.random(n) * 0.0)) > 0)[0]
    imp[idx] = rng.uniform(0.3, 1.0, len(idx))
    out = np.zeros(n)
    for r, a in zip([1, 2.756, 5.4], [1, .7, .4]):
        sos = signal.tf2sos(*signal.iirpeak(min(f0 * r, 18000), 60, fs=SR))
        out += a * signal.sosfilt(sos, imp + 0.15 * white(n))
    out /= np.std(out) + 1e-9
    hiss = tv_biquad(white(n), curve(n, [(0, 4000), (dur, 7500)]), 0.9, 'bp') * 0.5
    return (out + hiss) * v * adsr(n, 0.02, 0.0, 1.0, 0.1) * power


def wood_thud(size=1.0, crack=0.6, amp=1.0):
    n = N(0.5)
    ir = modal_ir([160 * size, 290 * size, 470 * size, 700 * size, 1050 * size],
                  [1, .8, .6, .4, .25], [0.07, 0.05, 0.035, 0.025, 0.015], 0.5)
    ex = addp(burst(0.004, 3000), 0.3 * burst(0.0015, 8000))
    y = excite(ir, ex)
    y /= np.max(np.abs(y)) + 1e-9
    cr = bp(white(n), 900, 3500) * expdec(n, 0.01) * crack
    lowb = thump(n, 110, 55, 0.03, 0.08) * 0.6
    return (y + cr + lowb) * amp


def clang_clash(f0=2600, strength=1.0, reverse_wood=False):
    """two axes meeting: bright metal + body clank + wood haft knock + scrape"""
    dur = 1.6
    n = N(dur)
    out = np.zeros(n)
    a = metal_hit(f0, dur, 0.55, 1.0, BAR, 11000, 1.0)
    b = metal_hit(f0 * rng.uniform(0.82, 1.2), dur, 0.45, 0.9, BAR, 10000, 0.8)
    c = metal_hit(f0 * 0.28, dur, 0.18, 1.3, PLATE, 5000, 0.55, sizzle=0.0)  # lower clank body
    place(out, a, 0)
    place(out, b, 0.004)
    place(out, c, 0)
    place(out, wood_thud(1.4, 0.3, 0.25), 0.002)
    place(out, scrape(rng.uniform(0.25, 0.5), f0 * 0.8, power=0.35), 0.03)
    return out * strength


# ================= MECH =================
def servo(dur, f_pts, harm=9, whine=0.35, load=0.5, gear=0.6, vel_pts=None, casing=True):
    n = N(dur)
    t = tt(n)
    f = curve(n, f_pts)
    ph = 2 * np.pi * np.cumsum(f) / SR
    out = np.zeros(n)
    for k in range(1, harm + 1):
        m = (k * f < 16000).astype(float)
        out += m * np.sin(k * ph + k * 0.7) / k ** 0.85
    # gear mesh sidebands (AM at shaft*reduction) + high whine with FM
    tooth = np.sin(2 * np.pi * np.cumsum(f * 0.0625) / SR)
    out *= 1 + gear * 0.35 * tooth
    out += whine * np.sin(7.31 * ph + 0.8 * np.sin(2.01 * ph)) * 0.6
    out += whine * 0.5 * np.sin(11.03 * ph + 0.4 * np.sin(ph * 3.0))
    v = curve(n, vel_pts) if vel_pts else np.clip((f - f.min()) / (np.ptp(f) + 1e-9), 0.2, 1)
    ld = tv_biquad(white(n), 900 + 1500 * v, 1.2, 'bp') * load * v
    out = out / (np.std(out) + 1e-9) + ld / (np.std(ld) + 1e-9) * 0.35 * load
    if casing:  # housing resonances
        c = np.zeros(n)
        for fc, q, g in [(640, 8, 1.0), (1450, 10, 0.8), (2900, 12, 0.6)]:
            c += g * signal.sosfilt(signal.tf2sos(*signal.iirpeak(fc, q, fs=SR)), out)
        out = out * 0.55 + c / (np.std(c) + 1e-9) * 0.5
    return out / (np.std(out) + 1e-9)


def creak(dur, rate_pts, f0=900, amp_env=None, power=1.0):
    """stick-slip squeal: irregular pulse train driving high-Q ringing"""
    n = N(dur)
    rate = curve(n, rate_pts)
    ph = np.cumsum(rate * (1 + 0.25 * lp(white(n), 15, 1) / 0.2)) / SR
    imp = np.zeros(n)
    idx = np.where(np.diff(np.floor(ph)) > 0)[0]
    imp[idx] = rng.uniform(0.2, 1.0, len(idx))
    out = np.zeros(n)
    for r, a, q in [(1, 1, 55), (1.92, .6, 70), (3.1, .35, 80)]:
        fc = f0 * r * (1 + 0.1 * lp(white(n), 5, 1) / 0.2 * 0.3)
        out += a * tv_biquad(imp, fc, q, 'bp', 32)
    out /= np.std(out) + 1e-9
    e = curve(n, amp_env) if amp_env else 1.0
    return out * e * power


def hiss(dur, env_pts, f_pts=((0, 3500), (1, 7000)), q=0.7, extra_hi=True):
    n = N(dur)
    fc = curve(n, list(f_pts))
    x = pink(n) + 0.5 * white(n)
    y = tv_biquad(x, fc, q, 'bp') + 0.5 * hp(white(n), 6000, 2) * 0.5
    y *= curve(n, env_pts)
    return y / (np.std(y) + 1e-9)


def mech_step(w=1.0, side=0, servo_amt=0.5, hiss_amt=1.0, dur=2.6, f_body=46):
    n = N(dur)
    out = np.zeros(n)
    t = tt(n)
    # heel strike + settle (two-stage), boom + ground rumble
    for dt, g in [(0.0, 1.0), (0.13, 0.55)]:
        boom = thump(n, f_body * 2.2, f_body, 0.045, 0.30 * w ** 0.5, atk=0.004) * w * g * 1.2
        rum = lp(brown(n), 110, 2) * expdec(n, 0.55) * w * g * 1.5
        crush = bp(white(n), 500, 3000) * expdec(n, 0.05) * g * 0.7
        gr = granular(0.3, 900, 600, 4500, (0.003, 0.012), env=[(0, 1), (0.3, 0)]) * g * 0.8
        s = boom + rum + crush
        s[:len(gr)] += gr
        place(out, s, dt)
    # metal foot + armour plate clangs (modal)
    place(out, metal_hit(rng.uniform(300, 380), 1.4, 0.45 * w, 1.4, PLATE, 6000, 0.9 * w, sizzle=0.1), 0.0)
    place(out, metal_hit(rng.uniform(780, 1100), 1.0, 0.25, 1.2, PLATE, 8000, 0.45), 0.006)
    place(out, metal_hit(rng.uniform(1700, 2400), 0.8, 0.14, 1.0, BAR, 9000, 0.25), 0.012)
    # loose armour rattle after impact
    for k in range(int(8 * w + 3)):
        td = rng.uniform(0.03, 0.45)
        f0 = rng.uniform(900, 4200)
        place(out, metal_hit(f0, 0.35, rng.uniform(0.04, 0.12), 1.0, PLATE[:8], 8000,
                             rng.uniform(0.08, 0.28) * np.exp(-td * 3), sizzle=0.0), td)
    # hydraulic hiss: pressure release as leg settles
    place(out, hiss(1.0, [(0, 0), (0.06, 0.9), (0.18, 0.55), (1.0, 0)], ((0, 3800), (1.0, 7800))) * 0.22 * hiss_amt, 0.05)
    place(out, bp(white(N(0.5)), 800, 2500) * np.sin(np.linspace(0, np.pi, N(0.5))) ** 2 * 0.12 * hiss_amt, 0.2)
    # servo swing whine before & after
    if servo_amt > 0:
        sv = servo(0.7, [(0, 260), (0.3, 520), (0.7, 330)], whine=0.3, load=0.6)
        sv *= adsr(len(sv), 0.1, 0.0, 1.0, 0.25)
        place(out, sv * 0.16 * servo_amt, 0.0)
    return out


def hydraulic_piston(dur=2.2, extend=True, power=1.0):
    n = N(dur)
    out = np.zeros(n)
    sgn = 1 if extend else -1
    # pump whine pitch follows load
    f_pts = [(0, 180), (0.2, 360), (dur * 0.7, 420 if extend else 330), (dur, 190)]
    pw = servo(dur, f_pts, harm=6, whine=0.15, load=0.3, gear=0.4)
    pw *= adsr(n, 0.15, 0.0, 1.0, 0.3)
    out += pw * 0.22
    # fluid flow noise
    fl = tv_biquad(pink(n), curve(n, [(0, 500), (dur * 0.5, 1400), (dur, 600)]), 0.8, 'bp') * adsr(n, 0.1, 0, 1, 0.35)
    out += fl / (np.std(fl) + 1e-9) * 0.28
    # stroke chug: low pulsing (pump cycles)
    rate = 12 + 6 * np.sin(np.linspace(0, np.pi, n))
    pulse = 0.55 + 0.45 * np.sin(2 * np.pi * np.cumsum(rate) / SR) ** 2
    out *= 0.75 + 0.25 * pulse
    # stroke rubbing: seal squeal
    out += creak(dur, [(0, 18), (dur, 30)], f0=2300 if extend else 1900,
                 amp_env=[(0, 0), (0.1, 0.12), (dur - 0.3, 0.1), (dur, 0)]) * 0.12
    # end-stop clunk
    ck = metal_hit(rng.uniform(180, 240), 0.8, 0.14, 1.5, PLATE, 5000, 1.0, sizzle=0.0)
    ck = addp(ck, thump(N(0.6), 90, 42, 0.03, 0.14) * 0.9)
    place(out, ck * 0.65 * power, dur - 0.35)
    return out

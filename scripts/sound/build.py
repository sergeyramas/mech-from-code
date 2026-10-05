"""Builds all 10 procedural sounds. Usage: python build.py [name ...]"""
import sys, json, os
import numpy as np
from dsp import *
from organic import *
from metal import *

OUT = os.path.dirname(os.path.abspath(__file__)) + "/wav"
os.makedirs(OUT, exist_ok=True)
RESULTS = []


def with_reverb(mix, rt, wet, **kw):
    ir = make_ir(rt, **kw)
    return reverb(mix.buf, ir, wet)


def spatial(layer, pts_x, pts_y, dur):
    n = len(layer)
    return mover(layer, curve(n, pts_x), curve(n, pts_y))


def bed_wind(dur, level=0.05):
    n = N(dur)
    return lp(pink(n), 700, 2) * level * (0.6 + 0.4 * lp(white(n), 0.7, 1) / 0.15)


# ============================ A1 boar attack ============================
def boar_attack():
    D = 9.6
    n = N(D)
    b = np.zeros(n)
    for t, f in [(1.0, 98), (1.55, 106), (2.05, 100), (2.5, 110)]:
        place(b, boar_grunt(rng.uniform(0.28, 0.38), f), t)
    for t, w in gallop_times(1.9, 4.95, [(1.9, 2.1), (4.9, 3.5)]):
        place(b, hoof(w * 1.15), t)
    for i, t in enumerate(np.arange(2.3, 4.9, 0.36)):
        place(b, boar_snort(0.17) * 0.5, t + rng.normal(0, 0.01))
    place(b, boar_squeal(1.0, 1500) * 0.45, 3.55)
    place(b, boar_grunt(0.4, 92, 1.2) * 0.9, 4.5)
    # after hit: angry grunts, stomping, then runs away
    for t, f in [(5.35, 90), (5.8, 95), (6.5, 100)]:
        place(b, boar_grunt(rng.uniform(0.3, 0.45), f, 1.1) * 0.8, t)
    place(b, boar_squeal(0.8, 1700) * 0.4, 6.8)
    for t, w in gallop_times(5.6, 8.9, [(5.6, 1.5), (8.9, 3.2)]):
        place(b, hoof(w), t)
    for t in np.arange(5.8, 8.7, 0.4):
        place(b, boar_snort(0.15) * 0.4, t)
    b = np.pad(b, (0, 0))
    px = [(0, -9), (1.8, -7.5), (3.5, -4), (4.9, -0.5), (5.05, 0.4), (5.7, 2.3), (6.6, 5.5), (9.6, 16)]
    py = [(0, 28), (1.8, 22), (3.5, 9), (4.9, 1.5), (5.05, 1.0), (5.7, 1.7), (6.6, 3.5), (9.6, 12)]
    st = spatial(b, px, py, D)
    m = Mix(D)
    m.buf += st * 1.0
    # listener-side layers: impact
    ti = 5.0
    m.add(body_hit(2.1, 0.7), ti, -0.1, 1.15)
    m.add(thump(N(1.0), 70, 30, 0.08, 0.35) * 1.2, ti, 0, 0.9)
    m.add(rustle(0.7, 500, [(0, 1), (0.7, 0)]), ti, 0.2, 0.18)
    m.add(grunt_effort(0.3, 100) * 0.35, ti + 0.02, 0.1, 0.5)
    m.add(rustle(1.0, 350, [(0, 0), (0.3, 1), (1, 0)]), 1.1, 0.7, 0.05)
    m.add(bed_wind(D), 0, 0, 1)
    ir = make_ir(0.9, pre=0.015)
    st = reverb(m.buf, ir, 0.2)
    return finalize(st, "boar_attack", OUT, low_db=-9)


# ============================ A2 bear attack ============================
def bear_attack():
    D = 11.0
    n = N(D)
    b = np.zeros(n)
    place(b, bear_growl(2.3, 60, 0.9) * 0.8, 0.3)
    for t, w in [(1.0, 1.1), (1.95, 1.2), (2.8, 1.3), (3.55, 1.4)]:
        place(b, ground_step(w, 0.6) * 0.9, t)
        place(b, rustle(0.4, 400, [(0, 1), (0.4, 0)]) * 0.25, t + 0.03)
    place(b, bear_huff(0.35) * 0.7, 3.95)
    place(b, bear_roar(2.4, 72, 1.0), 4.35)
    t = 4.8
    gap = 0.46
    while t < 6.3:
        place(b, ground_step(1.5, 0.8) * 0.9, t)
        t += gap
        gap *= 0.93
    place(b, bear_roar(1.6, 80, 1.1) * 0.9, 6.95)
    place(b, bear_growl(2.2, 55, 0.9) * 0.8, 8.5)
    place(b, bear_huff(0.4) * 0.5, 10.4)
    px = [(0, -6), (1.5, -3.5), (4.0, -1.8), (6.0, -0.8), (11, -0.5)]
    py = [(0, 15), (1.5, 9), (4.0, 4.0), (6.0, 2.2), (11, 1.6)]
    st = spatial(b, px, py, D)
    m = Mix(D)
    m.buf += st
    ts = 6.5
    m.add(paw_swipe(1.5), ts - 0.3, -0.15, 1.0)
    m.add(body_hit(2.4, 0.5), ts, 0.0, 0.8)
    m.add(thump(N(1.2), 65, 28, 0.09, 0.4) * 1.3, ts, 0, 0.9)
    m.add(hp(white(N(0.35)), 700, 2) * expdec(N(0.35), 0.12) * 0.25, ts + 0.03, 0.2)  # cloth tear
    m.add(rustle(1.0, 400, [(0, 1), (1, 0)]), ts + 0.1, 0.1, 0.16)
    m.add(grunt_effort(0.35, 100) * 0.4, ts + 0.05, 0.1, 0.5)
    m.add(bed_wind(D, 0.04), 0, 0, 1)
    ir = make_ir(1.3, pre=0.02)
    st = reverb(m.buf, ir, 0.22)
    return finalize(st, "bear_attack", OUT, low_db=-8)


# ============================ A3 boar vs bear fight ============================
def boar_vs_bear():
    D = 14.8
    n = N(D)
    bear = np.zeros(n)
    boar = np.zeros(n)
    m = Mix(D)
    # bear
    place(bear, bear_growl(2.6, 58, 0.85) * 0.8, 0.2)
    for t in [0.9, 1.85, 2.8]:
        place(bear, ground_step(1.4, 0.5) * 0.85, t)
    place(bear, bear_roar(1.9, 70, 1.0), 3.85)
    place(bear, bear_roar(2.3, 66, 1.2) * 1.0, 8.4)
    for t, d in [(4.55, 0.55), (5.35, 0.5), (6.15, 0.55), (6.95, 0.5), (7.7, 0.5)]:
        place(bear, bear_growl(d + 0.1, rng.uniform(60, 78), 1.0) * 0.8, t)
    place(bear, bear_roar(1.8, 74, 1.0) * 0.9, 11.8)
    place(bear, bear_growl(2.4, 54, 0.8) * 0.7, 12.4)
    place(bear, bear_huff(0.4) * 0.6, 10.2)
    for t in np.arange(4.5, 8.3, 0.55):
        place(bear, ground_step(1.3, 0.7) * 0.6, t + rng.normal(0, 0.05))
    # boar
    for t, f in [(0.6, 100), (1.2, 108), (1.9, 98)]:
        place(boar, boar_grunt(0.32, f), t)
    place(boar, boar_snort(0.2) * 0.6, 2.2)
    for t, w in gallop_times(2.4, 3.95, [(2.4, 2.4), (3.9, 3.5)]):
        place(boar, hoof(w * 1.1), t)
    place(boar, boar_squeal(0.9, 1500) * 0.45, 3.3)
    for t, d, f0 in [(4.4, 0.7, 1700), (5.8, 0.9, 1500), (7.1, 0.6, 1800), (8.9, 1.3, 1600)]:
        place(boar, boar_squeal(d, f0) * 0.45, t)
    for t in [4.7, 5.2, 6.4, 6.8, 7.6, 8.1]:
        place(boar, boar_grunt(0.3, rng.uniform(90, 115), 1.2) * 0.8, t)
    for t in np.arange(4.5, 8.7, 0.45):
        place(boar, hoof(rng.uniform(0.7, 1.1)) * 0.7, t + rng.normal(0, 0.04))
    place(boar, boar_squeal(1.3, 1900) * 0.45, 11.45)
    for t, w in gallop_times(11.2, 14.4, [(11.2, 3.0), (14.4, 3.6)]):
        place(boar, hoof(w), t)
    # spatialise: bear left, boar right
    bx = [(0, -3.5), (3.8, -2.6), (8, -3.0), (11, -3.6), (15, -4)]
    by = [(0, 6.5), (3.8, 5.5), (8, 6.0), (11, 6.5), (15, 7)]
    gx = [(0, 5), (2.3, 5.5), (3.9, -1.8), (4.4, 0.8), (8.0, 1.5), (10.4, 2.5), (11.2, 4), (14.8, 22)]
    gy = [(0, 7), (2.3, 7), (3.9, 5.5), (4.4, 5.0), (8.0, 5.6), (10.4, 6.5), (11.2, 7), (14.8, 22)]
    m.buf += spatial(bear, bx, by, D) + spatial(boar, gx, gy, D)
    # collision + scuffle foley (near stage)
    m.add_dist(body_hit(2.6, 0.8), 3.95, 5.5, -0.1, 1.5)
    m.add_dist(thump(N(1.2), 70, 28, 0.08, 0.4) * 1.5, 3.95, 5.5, 0, 1.2)
    m.add_dist(tusk_clack() * 0.8, 4.05, 5.5, 0.0, 0.8)
    hits = [4.3, 4.95, 5.55, 6.05, 6.6, 7.3, 7.95, 9.1, 9.6, 10.35]
    for i, t in enumerate(hits):
        w = rng.uniform(1.0, 2.0)
        m.add_dist(body_hit(w, 0.6), t, 5.5, rng.uniform(-0.5, 0.5), 0.9)
    for t in [5.0, 6.75, 9.9]:
        m.add_dist(paw_swipe(1.6), t - 0.28, 5.5, -0.4, 0.9)
    for t in [5.65, 7.5, 8.0]:
        m.add_dist(tusk_clack(), t, 5.5, 0.3, 0.7)
    m.add_dist(granular(4.0, 900, 700, 5000, (0.004, 0.02), env=[(0, 0), (0.5, 1), (3.5, 0.8), (4, 0)]) * 0.5, 4.3, 5.5, 0, 1)
    m.add_dist(rustle(5.0, 300, [(0, 0), (1, 1), (4, 0.7), (5, 0)]) * 0.3, 4.0, 5.5, 0.1, 1)
    # thrown boar: tumbling thuds
    for t, w in [(10.55, 2.2), (10.95, 1.5), (11.2, 0.9)]:
        m.add_dist(body_hit(w, 0.4), t, 7, 0.5, 0.9)
    m.add(bed_wind(D, 0.035), 0, 0, 1)
    ir = make_ir(1.1, pre=0.018)
    st = reverb(m.buf, ir, 0.2)
    return finalize(st, "boar_vs_bear_fight", OUT, low_db=-8)


# ============================ B4 axe clash ============================
def axe_clash():
    D = 10.5
    m = Mix(D)
    ev = [(0.4, 2400, 1.0, -0.4), (1.5, 3000, 0.85, 0.35), (3.1, 2100, 1.0, -0.2), (3.28, 2750, 0.9, 0.3),
          (3.42, 3300, 0.7, 0.0), (5.4, 2300, 1.0, 0.0), (6.65, 2900, 0.9, -0.3), (6.85, 2500, 0.9, 0.3),
          (7.1, 3200, 0.8, -0.1), (8.2, 2000, 1.2, 0.0)]
    for t, f, s, p in ev:
        m.add(clang_clash(f, s), t, p, 0.9)
    # shield hits (wood) with metal rim ping, splinter crack
    for t, size, p in [(2.3, 1.0, 0.2), (4.35, 0.85, -0.3), (4.7, 0.95, 0.3), (7.7, 1.1, 0.0)]:
        m.add(wood_thud(size, 0.9, 1.0), t, p, 1.0)
        m.add(body_hit(0.9, 0.2), t, p, 0.4)
        m.add(metal_hit(2800, 0.6, 0.15, 1.0, BELL, 8000, 0.3), t + 0.003, p, 0.6)
        m.add(granular(0.25, 500, 1500, 6000, (0.002, 0.008), env=[(0, 1), (0.25, 0)]), t + 0.01, p, 0.3)
    # scraping slide after a clash
    m.add(scrape(1.2, 2300, [(0, 0.3), (0.3, 1.0), (1.2, 0.2)], 0.9), 5.45, 0.1, 0.7)
    m.add(scrape(0.7, 3000, [(0, 0.9), (0.7, 0.2)], 0.8), 8.25, -0.2, 0.5)
    # big final strike with long ring
    m.add(metal_hit(1500, 3.0, 1.0, 0.9, BAR, 12000, 0.9), 8.2, 0, 0.8)
    m.add(thump(N(0.8), 100, 45, 0.04, 0.12) * 0.9, 8.2, 0, 0.7)
    # boots shuffle underneath
    for t in np.arange(0.3, 10, 0.31):
        m.add(human_step(0.4), t + rng.normal(0, 0.03), rng.uniform(-0.6, 0.6), 0.12)
    ir = make_ir(0.8, pre=0.01)
    st = reverb(m.buf, ir, 0.18)
    return finalize(st, "axe_clash", OUT)


# ============================ B5 battle shouts ============================
def chorus(m, t0, n_voices, kind, spread=0.12, pan_w=0.8, gain=0.5, dist=0):
    for i in range(n_voices):
        f0 = rng.uniform(88, 165)
        sc = rng.uniform(0.9, 1.1)
        dt = rng.uniform(0, spread)
        if kind == 'a':
            x = shout_a(rng.uniform(1.7, 2.8), f0, sc, rng.choice(['a', 'a', 'ae', 'o']))
        else:
            x = shout_ha(rng.uniform(0.35, 0.55), f0 * 1.05, sc)
        p = rng.uniform(-pan_w, pan_w)
        if dist:
            m.add_dist(x, t0 + dt, dist, p, gain)
        else:
            m.add(x, t0 + dt, p, gain)


def battle_shouts():
    D = 11.0
    m = Mix(D)
    # runners
    for r in range(5):
        p = rng.uniform(-0.8, 0.8)
        t = rng.uniform(0, 0.3)
        per = rng.uniform(0.27, 0.33)
        while t < D - 1:
            lvl = 0.12 + 0.22 * min(1, t / 5)
            m.add(human_step(0.7), t, p, lvl)
            t += per * rng.uniform(0.95, 1.05)
    m.add(metal_jingle(10.5, 0.15), 0.2, -0.3, 1.0)
    m.add(metal_jingle(10.5, 0.12), 0.5, 0.4, 1.0)
    chorus(m, 0.5, 7, 'a', 0.35, 0.85, 0.34)
    for t in [4.0, 4.55, 5.05]:
        chorus(m, t, 6, 'ha', 0.08, 0.8, 0.4)
    chorus(m, 5.8, 8, 'a', 0.25, 0.9, 0.3)
    for t in [8.9, 9.35]:
        chorus(m, t, 7, 'ha', 0.06, 0.85, 0.42)
    ir = make_ir(1.0, pre=0.02)
    st = reverb(m.buf, ir, 0.22)
    return finalize(st, "battle_shouts", OUT)


# ============================ B6 skirmish scene ============================
def skirmish_scene():
    D = 15.5
    m = Mix(D)
    # approach: running steps crescendo from distance
    for r in range(7):
        p = rng.uniform(-0.9, 0.9)
        t = rng.uniform(0, 0.3)
        per = rng.uniform(0.26, 0.34)
        while t < 11.5:
            d = max(4, 26 - 4.5 * t) if t < 4 else 6
            lvl = 0.35 if t < 11 else 0.35 * (11.5 - t) / 0.5 + 0.01
            m.add_dist(human_step(0.7), t, d, p, lvl)
            t += per * rng.uniform(0.95, 1.05)
    m.add_dist(metal_jingle(4, 0.2), 0.5, 18, 0.2, 1.0)
    # distant war cry
    chorus(m, 0.6, 5, 'a', 0.4, 0.8, 0.5, dist=22)
    chorus(m, 2.4, 5, 'a', 0.3, 0.9, 0.5, dist=11)
    # contact
    chorus(m, 3.9, 4, 'ha', 0.05, 0.8, 0.45, dist=5)
    m.add_dist(clang_clash(2500, 1.0), 4.0, 6, -0.3, 1.0)
    m.add_dist(wood_thud(1.0, 0.9), 4.1, 5, 0.4, 1.0)
    m.add_dist(body_hit(1.2, 0.5), 4.25, 4, 0.0, 0.9)
    # melee: randomised event stream
    t = 4.5
    while t < 11.6:
        dist = rng.uniform(3, 12)
        p = rng.uniform(-0.9, 0.9)
        r = rng.random()
        if r < 0.30:
            m.add_dist(clang_clash(rng.uniform(1900, 3400), rng.uniform(0.6, 1.0)), t, dist, p, 0.9)
        elif r < 0.52:
            m.add_dist(wood_thud(rng.uniform(0.8, 1.2), 0.8), t, dist, p, 1.0)
            m.add_dist(body_hit(0.8, 0.2), t, dist, p, 0.3)
        elif r < 0.72:
            m.add_dist(body_hit(rng.uniform(0.8, 1.5), 0.7), t, dist, p, 0.9)
            m.add_dist(grunt_effort(0.25, rng.uniform(95, 130), rng.uniform(.92, 1.1)), t + 0.03, dist, p, 0.8)
        elif r < 0.82:
            m.add_dist(shout_ha(0.45, rng.uniform(100, 160), rng.uniform(.92, 1.1)), t, dist, p, 0.7)
        elif r < 0.88:
            m.add_dist(pain_scream(rng.uniform(0.9, 1.4), rng.uniform(190, 260), rng.uniform(.95, 1.1)), t, dist, p, 0.7)
            m.add_dist(body_hit(1.1, 0.9), t - 0.05, dist, p, 0.7)
        else:
            m.add_dist(groan(rng.uniform(0.7, 1.2), rng.uniform(100, 140), rng.uniform(.92, 1.1)), t, dist, p, 0.7)
        t += rng.uniform(0.22, 0.65)
    # scuffle floor noise
    m.add(granular(7, 800, 600, 4500, (0.003, 0.012), env=[(0, 0), (1, 1), (6, 0.8), (7, 0)]), 4.4, 0, 0.12)
    m.add(metal_jingle(7, 0.25), 4.5, 0.2, 0.7)
    # aftermath
    for t, f, d, p in [(11.6, 105, 5, -0.4), (12.7, 118, 7, 0.5), (13.7, 98, 9, 0.1)]:
        m.add_dist(groan(rng.uniform(1.0, 1.5), f, rng.uniform(.95, 1.05)), t, d, p, 0.8)
    for t in [12.2, 13.0, 14.0]:
        m.add_dist(human_step(0.4), t, 12, rng.uniform(-.6, .6), 0.25)
    m.add_dist(clang_clash(2200, 0.6), 12.2, 10, 0.6, 0.6)
    m.add_dist(shout_a(1.6, 120, 1.0), 12.4, 28, -0.6, 0.5)
    m.add(bed_wind(D, 0.04), 0, 0, 1)
    ir = make_ir(1.2, pre=0.02)
    st = reverb(m.buf, ir, 0.22)
    return finalize(st, "skirmish_scene", OUT)


# ============================ C7 mech step ============================
def mech_steps():
    D = 11.2
    m = Mix(D)
    vars_ = [(1.0, -0.25, 0.5, 46), (1.12, 0.25, 0.5, 44), (0.75, -0.1, 0.3, 54), (1.5, 0.0, 0.9, 38)]
    for i, (w, p, sv, fb) in enumerate(vars_):
        m.add(mech_step(w, p, sv, 1.0 if i != 2 else 0.6, 2.6, fb), 0.2 + i * 2.7, p, 1.0)
    ir = make_ir(1.7, pre=0.02, damp=(1.3, 1.0, 0.5))
    st = reverb(m.buf, ir, 0.2)
    return finalize(st, "mech_step", OUT, low_db=-9)


# ============================ C8 walk loop ============================
def mech_walk_loop():
    D = 6.0
    n = N(D)
    tail = 3.0
    m = Mix(D + tail)
    steps = [(0.0, -0.3, 1.0, 46), (1.5, 0.3, 1.1, 44), (3.0, -0.3, 1.05, 45), (4.5, 0.3, 1.1, 43)]
    for t, p, w, fb in steps:
        m.add(mech_step(w, p, 0.0, 1.0, 2.6, fb), t, p, 1.0)
        # leg swing servo between steps
        sv = servo(0.85, [(0, 230), (0.4, 480), (0.85, 260)], whine=0.35, load=0.7)
        sv *= adsr(len(sv), 0.12, 0, 1, 0.3)
        m.add(sv, t + 0.55, -p, 0.075)
        m.add(creak(0.8, [(0, 14), (0.8, 24)], 1100 + 150 * p, [(0, 0), (0.2, 1), (0.8, 0)]), t + 0.6, -p, 0.04)
        m.add(hiss(0.7, [(0, 0), (0.1, 1), (0.7, 0)], ((0, 5000), (0.7, 3500))), t + 0.7, -p, 0.045)
    buf = fold(m.buf, n)
    # periodic bed: motor hum (frequencies are multiples of 1/6 Hz) + sub rumble
    t = tt(n)
    hum = np.zeros(n)
    for k, a in [(48, 1.0), (96, 0.6), (144, 0.4), (192, 0.25)]:
        hum += a * np.sin(2 * np.pi * k * t + k)
    am = 1 + 0.3 * np.sin(2 * np.pi * (4 / 6) * t) + 0.12 * np.sin(2 * np.pi * (8 / 6) * t + 1)
    hum = hum * am
    rum = spec_noise(n, lambda f: np.where((f > 25) & (f < 180), 1 / np.sqrt(f), 0.0))
    rum *= 1 + 0.4 * np.sin(2 * np.pi * (2 / 6) * t)
    rum2 = spec_noise(n, lambda f: np.where((f > 1500) & (f < 6000), 1.0, 0.02)) * 0.02
    bed = (hum / np.std(hum) * 0.045 + rum / np.std(rum) * 0.06 + rum2)
    buf += pan2(bed, 0)
    ir = make_ir(1.4, pre=0.015, damp=(1.3, 1.0, 0.5))
    st = reverb_circ(buf, ir, 0.2)
    return finalize_loop(st, "mech_walk_loop", OUT)


# ============================ C9 mech turn ============================
def bell(n):
    x = np.linspace(0, 1, n)
    return 10 * x ** 3 - 15 * x ** 4 + 6 * x ** 5  # min-jerk position


def turn_pass(dur, f_lo, f_hi, creak_f, whine=0.4):
    n = N(dur)
    x = np.linspace(0, 1, n)
    v = np.sin(np.pi * x) ** 1.4  # speed profile
    f_pts = [(float(tt_), float(f_lo + (f_hi - f_lo) * vv)) for tt_, vv in zip(np.linspace(0, dur, 40), np.sin(np.pi * np.linspace(0, 1, 40)) ** 1.4)]
    vel_pts = [(float(tt_), float(vv)) for tt_, vv in zip(np.linspace(0, dur, 40), v[np.linspace(0, n - 1, 40).astype(int)])]
    sv = servo(dur, f_pts, harm=10, whine=whine, load=0.9, gear=0.8, vel_pts=vel_pts)
    sv *= np.clip(v * 3, 0, 1) ** 0.7 * 0.9 + 0.1 * (v > 0.01)
    cr = creak(dur, [(0, 10), (dur * 0.5, 55), (dur, 8)], creak_f, [(0, 0), (dur * 0.25, 0.8), (dur * 0.75, 0.6), (dur, 0)])
    return sv, cr


def mech_turn():
    D = 9.0
    m = Mix(D)
    # latch release
    m.add(metal_hit(900, 0.5, 0.1, 1.2, PLATE, 9000, 0.9, sizzle=0.1), 0.25, 0, 0.6)
    m.add(hiss(0.6, [(0, 0), (0.03, 1), (0.6, 0)]), 0.28, 0, 0.2)
    # turn 1
    sv, cr = turn_pass(3.0, 110, 560, 1050)
    m.add(sv, 0.6, -0.15, 0.5)
    m.add(cr, 0.6, -0.15, 0.2)
    m.add(hiss(3.0, [(0, 0), (0.3, 0.3), (1.5, 0.15), (3, 0)], ((0, 4500), (3, 5200))), 0.6, 0.1, 0.05)
    # arrive: brake clunk
    m.add(metal_hit(240, 1.0, 0.18, 1.5, PLATE, 5000, 1.0, sizzle=0.0), 3.6, 0, 0.7)
    m.add(thump(N(0.8), 100, 44, 0.04, 0.14) * 1.0, 3.6, 0, 0.7)
    m.add(hiss(0.8, [(0, 0), (0.04, 1), (0.8, 0)]), 3.62, 0, 0.18)
    # return turn, faster, different pitch
    sv, cr = turn_pass(2.2, 140, 700, 1400, 0.5)
    m.add(sv, 4.9, 0.15, 0.5)
    m.add(cr, 4.9, 0.15, 0.2)
    m.add(hiss(2.2, [(0, 0), (0.2, 0.3), (1.1, 0.2), (2.2, 0)], ((0, 5000), (2.2, 4300))), 4.9, -0.1, 0.05)
    m.add(metal_hit(300, 1.2, 0.2, 1.4, PLATE, 5500, 1.0, sizzle=0.0), 7.15, 0, 0.8)
    m.add(thump(N(0.9), 110, 46, 0.04, 0.15) * 1.0, 7.15, 0, 0.8)
    m.add(metal_hit(1700, 0.6, 0.1, 1.0, PLATE, 9000, 0.4), 7.16, 0, 0.5)
    m.add(hiss(1.2, [(0, 0), (0.05, 1), (1.2, 0)], ((0, 5500), (1.2, 3500))), 7.17, 0, 0.2)
    ir = make_ir(1.5, pre=0.015, damp=(1.3, 1.0, 0.5))
    st = reverb(m.buf, ir, 0.2)
    return finalize(st, "mech_turn", OUT)


# ============================ C10 hydraulics ============================
def valve(power=1.0):
    n = N(0.4)
    c = metal_hit(rng.uniform(1900, 2500), 0.2, 0.025, 1.0, BELL, 10000, 0.7, sizzle=0.0)
    ts = hiss(0.25, [(0, 0), (0.01, 1), (0.25, 0)], ((0, 7000), (0.25, 4000))) * 0.5
    out = np.zeros(n)
    place(out, c, 0)
    place(out, ts, 0.005)
    place(out, thump(N(0.15), 220, 110, 0.01, 0.03) * 0.5, 0)
    return out * power


def mech_hydraulics():
    D = 12.0
    m = Mix(D)
    # pump spin-up + pressure build
    pump = servo(2.6, [(0, 40), (0.6, 110), (1.6, 190), (2.6, 230)], harm=8, whine=0.2, load=0.8, gear=0.5, casing=True)
    pump *= adsr(len(pump), 0.4, 0, 1, 0.5)
    m.add(pump, 0.2, 0, 0.35)
    m.add(hiss(2.4, [(0, 0), (1.2, 0.2), (2.4, 0.5)], ((0, 2500), (2.4, 6500))), 0.4, 0, 0.12)
    # valve + piston extend
    m.add(valve(), 2.6, -0.3, 0.8)
    m.add(hydraulic_piston(2.3, True), 2.75, -0.3, 0.9)
    # relief valve psssht
    m.add(hiss(1.3, [(0, 0), (0.02, 1), (0.25, 0.7), (1.3, 0)], ((0, 7500), (1.3, 3800)), 0.6), 5.35, 0.2, 0.4)
    m.add(valve(0.6), 5.33, 0.2, 0.6)
    # second small cylinder
    m.add(valve(0.9), 6.2, 0.35, 0.8)
    m.add(hydraulic_piston(1.4, True, 0.7), 6.3, 0.35, 0.65)
    # retract big piston, lower pitch
    m.add(valve(), 7.7, -0.3, 0.8)
    m.add(hydraulic_piston(2.2, False), 7.85, -0.3, 0.9)
    # final lock and release
    m.add(metal_hit(380, 1.2, 0.2, 1.3, PLATE, 6000, 1.0, sizzle=0.0), 10.15, 0, 0.8)
    m.add(thump(N(0.8), 100, 40, 0.04, 0.16), 10.15, 0, 0.9)
    m.add(hiss(1.8, [(0, 0), (0.03, 1), (0.4, 0.6), (1.8, 0)], ((0, 6500), (1.8, 3000)), 0.7), 10.2, 0, 0.35)
    ir = make_ir(1.5, pre=0.015, damp=(1.3, 1.0, 0.5))
    st = reverb(m.buf, ir, 0.18)
    return finalize(st, "mech_hydraulics", OUT)


ALL = dict(boar_attack=boar_attack, bear_attack=bear_attack, boar_vs_bear_fight=boar_vs_bear, axe_clash=axe_clash,
           battle_shouts=battle_shouts, skirmish_scene=skirmish_scene, mech_step=mech_steps,
           mech_walk_loop=mech_walk_loop, mech_turn=mech_turn, mech_hydraulics=mech_hydraulics)

if __name__ == "__main__":
    names = sys.argv[1:] or list(ALL)
    import time
    for nm in names:
        t0 = time.time()
        r = ALL[nm]()
        print(f"{r['name']:22s} {r['dur']:6.2f}s  LUFS {r['lufs']:6.1f}  peak {r['peak']:5.1f}  drive {r['drive']}  [{time.time()-t0:.1f}s]", flush=True)
        RESULTS.append(r)

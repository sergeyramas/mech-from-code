# Environment kit - procedural materials (Cycles). All ENV_* materials are built here.
import bpy, math
from env_common import (new_mat, nn, o, texco, attr, objrand, mapv, noi, vor, ramp, mth, mix, sstep, sepxyz,
                        bump, bsdf, out_mat)

MAT = {}


def rand_co(nt, co, k=1.0):
    r = objrand(nt)
    rv = o(nn(nt, 'ShaderNodeCombineXYZ', {'X': mth(nt, 'MULTIPLY', r, 37.1 * k), 'Y': mth(nt, 'MULTIPLY', r, 91.7 * k),
                                             'Z': mth(nt, 'MULTIPLY', r, 13.3 * k)}), 'Vector')
    return o(nn(nt, 'ShaderNodeVectorMath', {0: co, 1: rv}, operation='ADD'), 'Vector')


def weathered(name, lo, hi, scale=0.6, rough=0.82, metal=0.0, rust=0.0, rust_col=(0.11, 0.045, 0.018), streak=0.3,
              grime=0.5, grime_h=1.5, chip=0.0, chip_col=(0.3, 0.29, 0.27), chip_metal=0.0, bump_s=0.15, fine=40.0,
              randomize=True, soot=False, moss=0.0, custom=None, extra_rough=None, spec=0.4):
    m, nt = new_mat(name)
    co0 = texco(nt, 'Object')
    co = rand_co(nt, co0) if randomize else co0
    n1 = noi(nt, co, scale, 4, 0.55)
    base = ramp(nt, n1, [(0.3, lo), (0.72, hi)])
    n2 = noi(nt, co, scale * 7, 3, 0.5)
    base = mix(nt, 0.25, base, ramp(nt, n2, [(0.35, (0.4, 0.4, 0.4)), (0.65, (0.62, 0.62, 0.62))]), 'OVERLAY')
    mask_metal = None
    if custom:
        base, mask_metal = custom(nt, co0, co, base)
    # vertical streaks
    if streak > 0:
        ns = noi(nt, mapv(nt, co, (9, 9, 0.35)), 2.2, 4, 0.6)
        sm = mth(nt, 'MULTIPLY', ramp(nt, ns, [(0.5, 0.0), (0.72, 1.0)]), streak)
        base_d = mix(nt, 1.0, base, (0.55, 0.53, 0.5), 'MULTIPLY')
        base = mix(nt, sm, base, base_d)
    # rust patches
    rp = None
    if rust > 0:
        nr = noi(nt, co, 1.7, 8, 0.66)
        lo_ = 0.64 - 0.1 * rust
        rp = ramp(nt, nr, [(lo_, 0.0), (lo_ + 0.07, 1.0)])
        rc = ramp(nt, noi(nt, co, 14, 6, 0.7), [(0.3, tuple(c * 0.55 for c in rust_col)), (0.7, rust_col)])
        base = mix(nt, rp, base, rc)
    # chips
    cm = None
    if chip > 0:
        vc = vor(nt, co, 9.0, 'F1', 'Distance')
        cm = mth(nt, 'MULTIPLY', ramp(nt, vc, [(0.0, 1.0), (0.09 * chip, 0.0)]),
                 ramp(nt, noi(nt, co, 3.0, 2, 0.5), [(0.48, 0.0), (0.6, 1.0)]))
        base = mix(nt, cm, base, chip_col)
    # soot from attribute
    if soot:
        sa = attr(nt, 'soot')
        sn = noi(nt, mapv(nt, co0, (3, 3, 0.8)), 2.0, 5, 0.6)
        sk = mth(nt, 'MULTIPLY', sa, ramp(nt, sn, [(0.25, 0.35), (0.6, 1.0)]), True)
        sk = mth(nt, 'POWER', sk, 0.8)
        base = mix(nt, sk, base, (0.012, 0.011, 0.01))
    # grime near the ground (object z)
    _, _, z = sepxyz(nt, co0)
    if grime > 0:
        g = mth(nt, 'MULTIPLY', mth(nt, 'SUBTRACT', 1.0, sstep(nt, z, 0.0, grime_h)), grime)
        gn = noi(nt, mapv(nt, co, (4, 4, 1.5)), 1.5, 3, 0.5)
        g = mth(nt, 'MULTIPLY', g, ramp(nt, gn, [(0.3, 0.6), (0.7, 1.0)]))
        base = mix(nt, g, base, (0.13, 0.11, 0.085))
    if moss > 0:
        mm = mth(nt, 'MULTIPLY', mth(nt, 'SUBTRACT', 1.0, sstep(nt, z, 0.0, 0.5)),
                 ramp(nt, noi(nt, co, 2.5, 4, 0.6), [(0.45, 0.0), (0.65, moss)]))
        base = mix(nt, mm, base, (0.06, 0.07, 0.035))
    rough_s = rough
    if rp is not None:
        rough_s = mth(nt, 'ADD', mth(nt, 'MULTIPLY', rp, 0.15), rough)
    rough_s = mth(nt, 'ADD', rough_s, mth(nt, 'MULTIPLY', n2, 0.1))
    if extra_rough is not None:
        rough_s = extra_rough(nt, rough_s)
    metal_s = metal
    if rp is not None and metal > 0:
        metal_s = mth(nt, 'MULTIPLY', metal, mth(nt, 'SUBTRACT', 1.0, rp), True)
    if cm is not None and chip_metal > 0:
        metal_s = mth(nt, 'MAXIMUM', metal_s if not isinstance(metal_s, float) else mth(nt, 'ADD', metal_s, 0.0),
                      mth(nt, 'MULTIPLY', cm, chip_metal))
    if mask_metal is not None:
        metal_s = mth(nt, 'MAXIMUM', metal_s if not isinstance(metal_s, float) else mth(nt, 'ADD', metal_s, 0.0),
                      mask_metal)
    h = mth(nt, 'MULTIPLY', noi(nt, co, fine, 4, 0.6), 0.4)
    h = mth(nt, 'ADD', h, mth(nt, 'MULTIPLY', n1, 0.6))
    if rp is not None:
        h = mth(nt, 'ADD', h, mth(nt, 'MULTIPLY', rp, 0.4))
    if cm is not None:
        h = mth(nt, 'SUBTRACT', h, mth(nt, 'MULTIPLY', cm, 0.5))
    nrm = bump(nt, h, bump_s, 0.02)
    s = bsdf(nt, base, rough_s, metal_s, nrm, spec)
    out_mat(nt, s)
    m.diffuse_color = (*lo, 1)
    MAT[name] = m
    return m


def stripes_custom(period=0.5, axis='X', diag=0.0, red=(0.32, 0.025, 0.015), white=(0.58, 0.56, 0.5), wear=0.5,
                   under=(0.09, 0.085, 0.08)):
    def f(nt, co0, co, base):
        x, y, z = sepxyz(nt, co0)
        a = {'X': x, 'Y': y, 'Z': z}[axis]
        if diag:
            a = mth(nt, 'ADD', a, mth(nt, 'MULTIPLY', z if axis != 'Z' else x, diag))
        s = mth(nt, 'LESS_THAN', mth(nt, 'FRACT', mth(nt, 'DIVIDE', a, period)), 0.5)
        col = mix(nt, s, white, red)
        col = mix(nt, 0.35, col, base, 'MULTIPLY')
        col = mix(nt, 0.5, col, mix(nt, 1.0, col, (1.6, 1.6, 1.6), 'MULTIPLY'))
        # paint wear: under-surface shows through
        w = ramp(nt, noi(nt, co, 4.0, 6, 0.65), [(0.62 - 0.2 * wear, 0.0), (0.66 - 0.2 * wear, 1.0)])
        col = mix(nt, w, col, base)
        return col, None
    return f


def mat_ground():
    m, nt = new_mat('ENV_ground')
    co = texco(nt, 'Object')
    x, y, z = sepxyz(nt, co)
    gr = attr(nt, 'gravel')
    gs = attr(nt, 'grass')
    wt = attr(nt, 'wet')
    big = noi(nt, co, 0.05, 4, 0.55)
    dirt = ramp(nt, big, [(0.3, (0.105, 0.085, 0.06)), (0.5, (0.15, 0.125, 0.09)), (0.72, (0.19, 0.165, 0.125))])
    mid = noi(nt, co, 0.7, 5, 0.6)
    dirt = mix(nt, 0.35, dirt, ramp(nt, mid, [(0.3, (0.32, 0.32, 0.32)), (0.7, (0.68, 0.68, 0.68))]), 'OVERLAY')
    # gravel: pebbles from voronoi cells
    pv = vor(nt, co, 22.0, 'F1', 'Color')
    pc = ramp(nt, o(nn(nt, 'ShaderNodeSeparateColor', {'Color': pv}), 0),
              [(0.0, (0.1, 0.095, 0.085)), (0.5, (0.2, 0.19, 0.17)), (1.0, (0.3, 0.285, 0.26))])
    pd = vor(nt, co, 22.0, 'F1', 'Distance')
    grav_n = noi(nt, co, 1.2, 4, 0.6)
    gmask = sstep(nt, mth(nt, 'ADD', gr, mth(nt, 'MULTIPLY', mth(nt, 'SUBTRACT', grav_n, 0.5), 0.8)), 0.35, 0.6)
    col = mix(nt, gmask, dirt, pc)
    # dry grass tint
    gn = noi(nt, co, 0.35, 4, 0.6)
    gcol = ramp(nt, gn, [(0.3, (0.17, 0.14, 0.07)), (0.7, (0.26, 0.21, 0.11))])
    gmask2 = sstep(nt, mth(nt, 'ADD', gs, mth(nt, 'MULTIPLY', mth(nt, 'SUBTRACT', mid, 0.5), 0.6)), 0.25, 0.75)
    col = mix(nt, mth(nt, 'MULTIPLY', gmask2, 0.85), col, gcol)
    # wet / mud
    wm = sstep(nt, mth(nt, 'ADD', wt, mth(nt, 'MULTIPLY', mth(nt, 'SUBTRACT', mid, 0.5), 0.5)), 0.3, 0.7)
    col = mix(nt, wm, col, mix(nt, 1.0, col, (0.45, 0.42, 0.38), 'MULTIPLY'))
    # scorch around crater + wreck (world space)
    sc = scorch_mask(nt, co)
    col = mix(nt, sc, col, (0.018, 0.016, 0.014))
    rough = mth(nt, 'SUBTRACT', 0.92, mth(nt, 'MULTIPLY', wm, 0.5))
    h = mth(nt, 'MULTIPLY', noi(nt, co, 3.0, 5, 0.6), 0.5)
    h = mth(nt, 'ADD', h, mth(nt, 'MULTIPLY', mth(nt, 'MULTIPLY', pd, -1.2), gmask))
    h = mth(nt, 'ADD', h, mth(nt, 'MULTIPLY', noi(nt, co, 30.0, 3, 0.6), 0.25))
    s = bsdf(nt, col, rough, 0.0, bump(nt, h, 0.4, 0.03), 0.3)
    out_mat(nt, s)
    m.diffuse_color = (0.15, 0.13, 0.1, 1)
    MAT['ENV_ground'] = m
    return m


SCORCH = [((-12.5, 5.0), 3.2, 6.5), ((-27.5, -21.5), 1.5, 4.5)]


def scorch_mask(nt, co):
    x, y, z = sepxyz(nt, co)
    n = noi(nt, co, 0.6, 4, 0.6)
    tot = None
    for (cx, cy), r0, r1 in SCORCH:
        dx = mth(nt, 'SUBTRACT', x, cx)
        dy = mth(nt, 'SUBTRACT', y, cy)
        d = mth(nt, 'SQRT', mth(nt, 'ADD', mth(nt, 'MULTIPLY', dx, dx), mth(nt, 'MULTIPLY', dy, dy)))
        d = mth(nt, 'ADD', d, mth(nt, 'MULTIPLY', mth(nt, 'SUBTRACT', n, 0.5), r1 * 0.6))
        s = mth(nt, 'SUBTRACT', 1.0, sstep(nt, d, r0, r1))
        tot = s if tot is None else mth(nt, 'MAXIMUM', tot, s)
    return mth(nt, 'MULTIPLY', tot, 0.92)


def mat_asphalt():
    m, nt = new_mat('ENV_asphalt')
    co = texco(nt, 'Object')
    uv = texco(nt, 'UV')
    u, v, _ = sepxyz(nt, uv)
    d = mth(nt, 'MULTIPLY', mth(nt, 'SUBTRACT', u, 0.5), 8.0)  # meters from centre
    al = mth(nt, 'MULTIPLY', v, 8.0)  # meters along
    ad = mth(nt, 'ABSOLUTE', d)
    big = noi(nt, co, 0.12, 4, 0.55)
    col = ramp(nt, big, [(0.3, (0.05, 0.05, 0.05)), (0.7, (0.095, 0.092, 0.088))])
    agg = vor(nt, co, 90.0, 'F1', 'Color')
    agg = o(nn(nt, 'ShaderNodeSeparateColor', {'Color': agg}), 0)
    col = mix(nt, mth(nt, 'MULTIPLY', ramp(nt, agg, [(0.75, 0.0), (0.9, 1.0)]), 0.5), col, (0.2, 0.19, 0.18))
    # lighter worn / bleached areas and dark patch repairs
    wn = noi(nt, co, 0.35, 5, 0.6)
    col = mix(nt, ramp(nt, wn, [(0.55, 0.0), (0.72, 0.6)]), col, (0.15, 0.145, 0.135))
    pn = noi(nt, mapv(nt, co, (0.4, 1.0, 1.0)), 0.25, 1, 0.3)
    patch = ramp(nt, pn, [(0.66, 0.0), (0.67, 1.0)])
    col = mix(nt, mth(nt, 'MULTIPLY', patch, 0.8), col, (0.03, 0.03, 0.03))
    # tyre lanes: darker polished bands
    lane = mth(nt, 'SUBTRACT', 1.0, sstep(nt, mth(nt, 'ABSOLUTE', mth(nt, 'SUBTRACT', ad, 2.0)), 0.3, 1.0))
    col = mix(nt, mth(nt, 'MULTIPLY', lane, 0.25), col, (0.035, 0.035, 0.035))
    # markings (faded)
    centre = mth(nt, 'LESS_THAN', ad, 0.07)
    dash = mth(nt, 'LESS_THAN', mth(nt, 'FRACT', mth(nt, 'DIVIDE', al, 9.0)), 0.36)
    edge = mth(nt, 'LESS_THAN', mth(nt, 'ABSOLUTE', mth(nt, 'SUBTRACT', ad, 3.55)), 0.075)
    mark = mth(nt, 'MAXIMUM', mth(nt, 'MULTIPLY', centre, dash), edge)
    mw = ramp(nt, noi(nt, co, 3.0, 6, 0.7), [(0.38, 0.0), (0.5, 1.0)])
    mw2 = ramp(nt, noi(nt, co, 0.3, 2, 0.5), [(0.3, 0.25), (0.7, 1.0)])
    mark = mth(nt, 'MULTIPLY', mth(nt, 'MULTIPLY', mark, mw), mw2)
    # cracks: long voronoi edges + alligator cracking near edges
    ce = vor(nt, mapv(nt, co, (0.5, 1.0, 1.0)), 0.55, 'DISTANCE_TO_EDGE', 'Distance')
    cr = ramp(nt, ce, [(0.0, 1.0), (0.012, 0.0)])
    cn = ramp(nt, noi(nt, co, 0.4, 3, 0.5), [(0.45, 0.0), (0.55, 1.0)])
    cr = mth(nt, 'MULTIPLY', cr, cn)
    ce2 = vor(nt, co, 2.5, 'DISTANCE_TO_EDGE', 'Distance')
    cr2 = ramp(nt, ce2, [(0.0, 1.0), (0.03, 0.0)])
    em = sstep(nt, ad, 2.6, 3.9)
    cr2 = mth(nt, 'MULTIPLY', cr2, mth(nt, 'MULTIPLY', em, ramp(nt, noi(nt, co, 0.8, 3, 0.5), [(0.4, 0.0), (0.6, 1.0)])))
    crack = mth(nt, 'MAXIMUM', cr, cr2)
    col = mix(nt, mark, col, (0.42, 0.4, 0.35))
    col = mix(nt, crack, col, (0.012, 0.011, 0.01))
    # dust/sand along the edges + inside potholes
    dust = mth(nt, 'MULTIPLY', sstep(nt, ad, 3.0, 4.1), ramp(nt, noi(nt, co, 1.0, 4, 0.6), [(0.3, 0.4), (0.7, 1.0)]))
    col = mix(nt, dust, col, (0.17, 0.15, 0.115))
    ph = attr(nt, 'pothole')
    phm = sstep(nt, ph, 0.05, 0.35)
    pcol = ramp(nt, o(nn(nt, 'ShaderNodeSeparateColor', {'Color': vor(nt, co, 25.0, 'F1', 'Color')}), 0),
                [(0.0, (0.05, 0.045, 0.04)), (1.0, (0.16, 0.15, 0.13))])
    col = mix(nt, phm, col, pcol)
    sc = scorch_mask(nt, co)
    col = mix(nt, mth(nt, 'MULTIPLY', sc, 0.8), col, (0.015, 0.014, 0.013))
    rough = mth(nt, 'ADD', 0.86, mth(nt, 'MULTIPLY', crack, 0.1))
    rough = mth(nt, 'SUBTRACT', rough, mth(nt, 'MULTIPLY', lane, 0.12))
    rough = mth(nt, 'SUBTRACT', rough, mth(nt, 'MULTIPLY', mark, 0.15))
    h = mth(nt, 'MULTIPLY', noi(nt, co, 60.0, 3, 0.6), 0.25)
    h = mth(nt, 'SUBTRACT', h, mth(nt, 'MULTIPLY', crack, 0.8))
    h = mth(nt, 'ADD', h, mth(nt, 'MULTIPLY', mark, 0.15))
    h = mth(nt, 'ADD', h, mth(nt, 'MULTIPLY', ramp(nt, agg, [(0.6, 0.0), (1.0, 1.0)]), 0.25))
    s = bsdf(nt, col, rough, 0.0, bump(nt, h, 0.35, 0.02), 0.35)
    out_mat(nt, s)
    m.diffuse_color = (0.07, 0.07, 0.07, 1)
    MAT['ENV_asphalt'] = m
    return m


def mat_water():
    m, nt = new_mat('ENV_water')
    co = texco(nt, 'Object')
    rip = noi(nt, mapv(nt, co, (1, 1, 1)), 3.0, 2, 0.4)
    s = bsdf(nt, (0.012, 0.012, 0.011), 0.035, 0.0, bump(nt, rip, 0.03, 0.01), 0.6, {'IOR': 1.33})
    out_mat(nt, s)
    m.diffuse_color = (0.02, 0.02, 0.02, 1)
    MAT['ENV_water'] = m
    return m


def mat_apron():
    m, nt = new_mat('ENV_concrete_apron')
    co = texco(nt, 'Object')
    co_r = rand_co(nt, co, 0.0)
    big = noi(nt, co, 0.25, 4, 0.55)
    col = ramp(nt, big, [(0.3, (0.2, 0.195, 0.18)), (0.7, (0.3, 0.29, 0.27))])
    col = mix(nt, 0.3, col, ramp(nt, noi(nt, co, 4.0, 4, 0.6), [(0.3, 0.38), (0.7, 0.62)]), 'OVERLAY')
    # oil / water stains
    st = ramp(nt, noi(nt, co, 0.5, 6, 0.7, 0.4), [(0.62, 0.0), (0.72, 0.8)])
    col = mix(nt, st, col, (0.07, 0.066, 0.06))
    # cracks
    ce = vor(nt, co, 0.45, 'DISTANCE_TO_EDGE', 'Distance')
    cr = mth(nt, 'MULTIPLY', ramp(nt, ce, [(0.0, 1.0), (0.01, 0.0)]),
             ramp(nt, noi(nt, co, 0.5, 3, 0.5), [(0.42, 0.0), (0.52, 1.0)]))
    col = mix(nt, cr, col, (0.02, 0.019, 0.017))
    # dirt and weeds at slab edges (attribute 'edge')
    ea = attr(nt, 'edge')
    em = mth(nt, 'MULTIPLY', sstep(nt, ea, 0.0, 1.0), ramp(nt, noi(nt, co, 2.0, 5, 0.6), [(0.3, 0.3), (0.7, 1.0)]))
    col = mix(nt, em, col, (0.11, 0.095, 0.07))
    # aggregate speckles
    ag = o(nn(nt, 'ShaderNodeSeparateColor', {'Color': vor(nt, co, 70.0, 'F1', 'Color')}), 0)
    col = mix(nt, mth(nt, 'MULTIPLY', ramp(nt, ag, [(0.7, 0.0), (1.0, 1.0)]), 0.35), col, (0.42, 0.4, 0.37))
    sc = scorch_mask(nt, co)
    col = mix(nt, sc, col, (0.016, 0.015, 0.013))
    rough = mth(nt, 'ADD', 0.84, mth(nt, 'MULTIPLY', st, -0.25))
    h = mth(nt, 'MULTIPLY', noi(nt, co, 40.0, 3, 0.6), 0.3)
    h = mth(nt, 'SUBTRACT', h, mth(nt, 'MULTIPLY', cr, 0.8))
    h = mth(nt, 'ADD', h, mth(nt, 'MULTIPLY', big, 0.3))
    s = bsdf(nt, col, rough, 0.0, bump(nt, h, 0.3, 0.02), 0.35)
    out_mat(nt, s)
    m.diffuse_color = (0.26, 0.25, 0.23, 1)
    MAT['ENV_concrete_apron'] = m
    return m


def seam_custom(fh=2.8, bw=3.0):
    def f(nt, co0, co, base):
        x, y, z = sepxyz(nt, co0)
        hz = mth(nt, 'FRACT', mth(nt, 'DIVIDE', z, fh))
        hs = mth(nt, 'MAXIMUM', mth(nt, 'LESS_THAN', hz, 0.008), mth(nt, 'GREATER_THAN', hz, 0.992))
        a = mth(nt, 'FRACT', mth(nt, 'DIVIDE', mth(nt, 'ADD', x, y), bw))
        vs = mth(nt, 'MAXIMUM', mth(nt, 'LESS_THAN', a, 0.007), mth(nt, 'GREATER_THAN', a, 0.993))
        s = mth(nt, 'MAXIMUM', hs, vs)
        # per-panel tint
        pan = o(nn(nt, 'ShaderNodeCombineXYZ', {'X': mth(nt, 'FLOOR', mth(nt, 'DIVIDE', mth(nt, 'ADD', x, y), bw)),
                                                  'Y': mth(nt, 'FLOOR', mth(nt, 'DIVIDE', z, fh))}), 'Vector')
        pt = o(nn(nt, 'ShaderNodeTexWhiteNoise', {'Vector': pan}), 'Value')
        base = mix(nt, mth(nt, 'MULTIPLY', pt, 0.35), base, mix(nt, 1.0, base, (0.75, 0.74, 0.72), 'MULTIPLY'))
        base = mix(nt, mth(nt, 'MULTIPLY', s, 0.85), base, (0.05, 0.048, 0.045))
        # spalling: fresh lighter concrete
        sp = ramp(nt, noi(nt, co, 1.2, 8, 0.7), [(0.66, 0.0), (0.69, 1.0)])
        base = mix(nt, mth(nt, 'MULTIPLY', sp, 0.6), base, (0.36, 0.35, 0.33))
        return base, None
    return f


def mat_volume_haze(density=0.0035):
    m, nt = new_mat('ENV_haze')
    v = nn(nt, 'ShaderNodeVolumePrincipled', {'Color': (0.82, 0.78, 0.72), 'Density': density, 'Anisotropy': 0.55})
    out_mat(nt, None, o(v, 'Volume'))
    MAT['ENV_haze'] = m
    return m


def mat_smoke(H=120.0):
    m, nt = new_mat('ENV_smoke')
    co = texco(nt, 'Object')
    x, y, z = sepxyz(nt, co)
    t = mth(nt, 'DIVIDE', z, H, True)
    # wind drift (+x, slightly +y) growing with height
    t2 = mth(nt, 'MULTIPLY', t, t)
    xd = mth(nt, 'SUBTRACT', x, mth(nt, 'MULTIPLY', t2, 34.0))
    yd = mth(nt, 'SUBTRACT', y, mth(nt, 'MULTIPLY', t2, 8.0))
    r = mth(nt, 'SQRT', mth(nt, 'ADD', mth(nt, 'MULTIPLY', xd, xd), mth(nt, 'MULTIPLY', yd, yd)))
    rad = mth(nt, 'ADD', 2.5, mth(nt, 'MULTIPLY', mth(nt, 'POWER', t, 0.7), 15.0))
    p = o(nn(nt, 'ShaderNodeCombineXYZ', {'X': xd, 'Y': yd, 'Z': z}), 'Vector')
    nz = noi(nt, mapv(nt, p, (1, 1, 0.6)), 0.07, 6, 0.62, 1.2)
    rn = mth(nt, 'ADD', mth(nt, 'DIVIDE', r, rad), mth(nt, 'MULTIPLY', mth(nt, 'SUBTRACT', nz, 0.5), 0.9))
    fall = mth(nt, 'SUBTRACT', 1.0, sstep(nt, rn, 0.35, 1.0))
    top = mth(nt, 'SUBTRACT', 1.0, sstep(nt, t, 0.7, 1.0))
    d = mth(nt, 'MULTIPLY', mth(nt, 'MULTIPLY', fall, top), ramp(nt, nz, [(0.35, 0.0), (0.65, 1.0)]))
    d = mth(nt, 'MULTIPLY', d, 0.55)
    fire = mth(nt, 'MULTIPLY', mth(nt, 'SUBTRACT', 1.0, sstep(nt, z, 1.0, 7.0)), fall)
    v = nn(nt, 'ShaderNodeVolumePrincipled', {'Color': (0.05, 0.045, 0.04), 'Density': d, 'Anisotropy': 0.3,
                                               'Emission Color': (1.0, 0.35, 0.06),
                                               'Emission Strength': mth(nt, 'MULTIPLY', fire, 6.0)})
    out_mat(nt, None, o(v, 'Volume'))
    try:
        m.cycles.volume_step_rate = 6.0
    except Exception:
        pass
    MAT['ENV_smoke'] = m
    return m


def mat_grass():
    m, nt = new_mat('ENV_grass')
    co = texco(nt, 'Object')
    _, _, z = sepxyz(nt, co)
    r = objrand(nt)
    c = ramp(nt, r, [(0.0, (0.2, 0.17, 0.08)), (0.35, (0.3, 0.24, 0.11)), (0.6, (0.17, 0.16, 0.075)),
                     (0.85, (0.26, 0.2, 0.12)), (1.0, (0.34, 0.29, 0.16))])
    g = sstep(nt, z, 0.0, 0.45)
    c = mix(nt, mth(nt, 'SUBTRACT', 1.0, g), c, mix(nt, 1.0, c, (0.35, 0.33, 0.25), 'MULTIPLY'))
    b = bsdf(nt, c, 0.65, 0.0, None, 0.35)
    tr = o(nn(nt, 'ShaderNodeBsdfTranslucent', {'Color': mix(nt, 1.0, c, (0.9, 0.8, 0.5), 'MULTIPLY')}), 0)
    ms = nn(nt, 'ShaderNodeMixShader', {0: 0.3, 1: b, 2: tr})
    out_mat(nt, o(ms, 0))
    m.diffuse_color = (0.25, 0.2, 0.1, 1)
    MAT['ENV_grass'] = m
    return m


def mat_rut():
    m, nt = new_mat('ENV_decal_rut')
    co = texco(nt, 'Object')
    uv = texco(nt, 'UV')
    u, v, _ = sepxyz(nt, uv)
    tread = mth(nt, 'LESS_THAN', mth(nt, 'FRACT', mth(nt, 'MULTIPLY', v, 7.0)), 0.45)
    col = ramp(nt, noi(nt, co, 1.5, 4, 0.6), [(0.3, (0.05, 0.042, 0.03)), (0.7, (0.1, 0.085, 0.062))])
    col = mix(nt, mth(nt, 'MULTIPLY', tread, 0.25), col, (0.03, 0.026, 0.02))
    a = mth(nt, 'MULTIPLY', sstep(nt, u, 0.0, 0.3), mth(nt, 'SUBTRACT', 1.0, sstep(nt, u, 0.7, 1.0)))
    a = mth(nt, 'MULTIPLY', a, ramp(nt, noi(nt, co, 0.8, 4, 0.6), [(0.3, 0.0), (0.5, 0.85)]))
    s = bsdf(nt, col, 0.75, 0.0, bump(nt, tread, 0.25, 0.02), 0.4)
    tr = o(nn(nt, 'ShaderNodeBsdfTransparent'), 0)
    ms = nn(nt, 'ShaderNodeMixShader', {0: a, 1: tr, 2: s})
    out_mat(nt, o(ms, 0))
    MAT['ENV_decal_rut'] = m
    return m


def mat_corrugated():
    def cust(nt, co0, co, base):
        r = objrand(nt)
        paint = ramp(nt, r, [(0.0, (0.1, 0.16, 0.15)), (0.3, (0.16, 0.16, 0.15)), (0.55, (0.22, 0.21, 0.2)),
                             (0.8, (0.12, 0.13, 0.1)), (1.0, (0.2, 0.08, 0.05))], 'CONSTANT')
        pm = ramp(nt, noi(nt, co, 1.2, 6, 0.65), [(0.42, 0.0), (0.5, 1.0)])
        base = mix(nt, pm, base, paint)
        return base, mth(nt, 'MULTIPLY', mth(nt, 'SUBTRACT', 1.0, pm), 0.5)
    return weathered('ENV_corrugated', (0.16, 0.16, 0.155), (0.28, 0.28, 0.27), scale=0.8, rough=0.55, metal=0.0,
                     rust=1.6, rust_col=(0.13, 0.052, 0.018), streak=0.8, grime=0.6, grime_h=1.0, custom=cust,
                     bump_s=0.12)


def mat_simple(name, col, rough=0.5, metal=0.0, emit=None, strength=0.0):
    m, nt = new_mat(name)
    ex = {}
    if emit:
        ex = {'Emission Color': (*emit, 1.0), 'Emission Strength': strength}
    s = bsdf(nt, col, rough, metal, None, 0.5, ex)
    out_mat(nt, s)
    m.diffuse_color = (*col, 1)
    MAT[name] = m
    return m


def mat_label():
    m, nt = new_mat('ENV_label')
    e = nn(nt, 'ShaderNodeEmission', {'Color': (1.0, 0.85, 0.2, 1.0), 'Strength': 6.0})
    out_mat(nt, o(e, 0))
    MAT['ENV_label'] = m
    return m


def mat_barrel():
    def cust(nt, co0, co, base):
        r = objrand(nt)
        paint = ramp(nt, r, [(0.0, (0.06, 0.07, 0.035)), (0.3, (0.05, 0.09, 0.16)), (0.5, (0.25, 0.04, 0.02)),
                             (0.72, (0.08, 0.08, 0.05)), (0.9, (0.2, 0.16, 0.05))], 'CONSTANT')
        base = mix(nt, 0.85, base, paint)
        return base, None
    return weathered('ENV_barrel', (0.1, 0.1, 0.1), (0.2, 0.2, 0.2), scale=1.5, rough=0.5, rust=1.3,
                     rust_col=(0.12, 0.05, 0.018), chip=1.0, chip_col=(0.08, 0.075, 0.07), chip_metal=0.6,
                     streak=0.6, grime=0.7, grime_h=0.4, custom=cust)


def mat_haze_backdrop():
    # far ruins: concrete with dark window grid
    def cust(nt, co0, co, base):
        x, y, z = sepxyz(nt, co0)
        a = mth(nt, 'FRACT', mth(nt, 'DIVIDE', mth(nt, 'ADD', x, y), 3.2))
        b = mth(nt, 'FRACT', mth(nt, 'DIVIDE', z, 2.9))
        w = mth(nt, 'MULTIPLY', mth(nt, 'LESS_THAN', mth(nt, 'ABSOLUTE', mth(nt, 'SUBTRACT', a, 0.5)), 0.22),
                mth(nt, 'LESS_THAN', mth(nt, 'ABSOLUTE', mth(nt, 'SUBTRACT', b, 0.55)), 0.25))
        w = mth(nt, 'MULTIPLY', w, mth(nt, 'GREATER_THAN', z, 1.0))
        base = mix(nt, w, base, (0.015, 0.015, 0.016))
        return base, None
    return weathered('ENV_backdrop', (0.14, 0.14, 0.135), (0.22, 0.215, 0.205), scale=0.05, rough=0.9, streak=0.6,
                     grime=0.0, custom=cust, randomize=False, bump_s=0.05)


def build_all():
    mat_ground()
    mat_asphalt()
    mat_water()
    mat_apron()
    weathered('ENV_concrete', (0.2, 0.195, 0.185), (0.31, 0.3, 0.28), scale=0.35, rough=0.88, streak=0.75,
              grime=0.6, grime_h=2.5, soot=True, moss=0.6, custom=seam_custom(2.8, 3.0), randomize=False, bump_s=0.2)
    weathered('ENV_concrete_broken', (0.24, 0.235, 0.22), (0.36, 0.35, 0.33), scale=2.0, rough=0.95, streak=0.0,
              grime=0.2, soot=True, randomize=False, bump_s=0.6, fine=25.0)
    weathered('ENV_concrete_prop', (0.22, 0.215, 0.2), (0.33, 0.32, 0.3), scale=0.7, rough=0.88, streak=0.5,
              grime=0.7, grime_h=0.7, moss=0.5, bump_s=0.25)
    weathered('ENV_jersey_paint', (0.22, 0.215, 0.2), (0.33, 0.32, 0.3), scale=0.7, rough=0.85, streak=0.4,
              grime=0.7, grime_h=0.6, moss=0.4, custom=stripes_custom(0.6, 'X', 1.0, wear=0.55), bump_s=0.25)

    def brick(nt, co0, co, base):
        x, y, z = sepxyz(nt, co0)
        bv = o(nn(nt, 'ShaderNodeCombineXYZ', {'X': mth(nt, 'ADD', x, y), 'Y': z}), 'Vector')
        b = nn(nt, 'ShaderNodeTexBrick', {'Vector': bv, 'Color1': (0.14, 0.115, 0.095), 'Color2': (0.18, 0.15, 0.125),
                                           'Mortar': (0.28, 0.27, 0.25), 'Scale': 1.0, 'Mortar Size': 0.012,
                                           'Bias': 0.0, 'Brick Width': 0.25, 'Row Height': 0.075},
               offset=0.5, offset_frequency=2, squash=1.0, squash_frequency=2)
        bc = o(b, 'Color')
        base = mix(nt, 0.55, bc, mix(nt, 1.0, bc, base, 'MULTIPLY'))
        base = mix(nt, 1.0, base, (1.25, 1.25, 1.25), 'MULTIPLY')
        return base, None
    weathered('ENV_brick', (0.25, 0.24, 0.23), (0.4, 0.38, 0.36), scale=0.5, rough=0.9, streak=0.6, grime=0.6,
              grime_h=2.0, soot=True, moss=0.5, custom=brick, randomize=False, bump_s=0.2)
    weathered('ENV_rust', (0.045, 0.035, 0.028), (0.09, 0.06, 0.04), scale=2.0, rough=0.62, metal=0.5, rust=2.2,
              rust_col=(0.12, 0.048, 0.017), streak=0.2, grime=0.4, grime_h=0.4, bump_s=0.3)
    weathered('ENV_steel_paint', (0.07, 0.08, 0.07), (0.12, 0.13, 0.11), scale=1.0, rough=0.6, rust=1.3,
              rust_col=(0.12, 0.05, 0.018), chip=0.8, chip_col=(0.06, 0.055, 0.05), chip_metal=0.7, streak=0.6,
              grime=0.4, grime_h=1.0)
    weathered('ENV_redwhite', (0.3, 0.3, 0.3), (0.4, 0.4, 0.4), scale=1.0, rough=0.55, rust=0.9,
              rust_col=(0.12, 0.05, 0.02), streak=0.4, grime=0.3, grime_h=0.6,
              custom=stripes_custom(0.5, 'X', 0.0, wear=0.5))
    weathered('ENV_paint_olive', (0.055, 0.058, 0.032), (0.1, 0.1, 0.06), scale=1.2, rough=0.6, rust=1.0,
              rust_col=(0.11, 0.045, 0.017), chip=1.0, chip_col=(0.07, 0.065, 0.06), chip_metal=0.6, streak=0.6,
              grime=0.6, grime_h=0.8)
    weathered('ENV_paint_white', (0.36, 0.35, 0.32), (0.5, 0.48, 0.44), scale=1.0, rough=0.6, rust=1.1,
              rust_col=(0.12, 0.05, 0.02), chip=1.2, chip_col=(0.08, 0.075, 0.07), streak=1.0, grime=0.7,
              grime_h=1.0)
    weathered('ENV_wood', (0.11, 0.085, 0.06), (0.22, 0.2, 0.17), scale=1.0, rough=0.85, streak=0.3, grime=0.5,
              grime_h=0.3, bump_s=0.3,
              custom=lambda nt, c0, c, b: (mix(nt, 0.5, b, ramp(nt, noi(nt, mapv(nt, c, (1.0, 18.0, 18.0)), 2.0, 3,
                                                                           0.5), [(0.3, 0.3), (0.7, 0.75)]),
                                               'MULTIPLY'), None))
    weathered('ENV_sandbag', (0.13, 0.11, 0.075), (0.22, 0.19, 0.13), scale=1.5, rough=0.95, streak=0.2, grime=0.6,
              grime_h=0.5, bump_s=0.3, fine=120.0)
    weathered('ENV_rubber', (0.012, 0.012, 0.012), (0.03, 0.03, 0.028), scale=2.0, rough=0.82, streak=0.0, grime=0.5,
              grime_h=0.4, bump_s=0.2)
    weathered('ENV_rubble', (0.17, 0.16, 0.15), (0.3, 0.29, 0.27), scale=1.0, rough=0.95, streak=0.0, grime=0.3,
              grime_h=0.5, bump_s=0.5, fine=20.0,
              custom=lambda nt, c0, c, b: (mix(nt, ramp(nt, objrand(nt), [(0.7, 0.0), (0.72, 0.8)]), b,
                                               (0.2, 0.08, 0.05)), None))
    weathered('ENV_bark', (0.05, 0.045, 0.04), (0.11, 0.1, 0.09), scale=3.0, rough=0.9, streak=0.0, grime=0.2,
              bump_s=0.4)
    weathered('ENV_hills', (0.06, 0.058, 0.042), (0.12, 0.11, 0.075), scale=0.02, rough=0.95, streak=0.0, grime=0.0,
              randomize=False, bump_s=0.05)
    mat_barrel()
    mat_corrugated()
    mat_haze_backdrop()
    mat_grass()
    mat_rut()
    mat_simple('ENV_glass', (0.015, 0.017, 0.018), 0.12, 0.2)
    mat_simple('ENV_wire', (0.02, 0.02, 0.02), 0.5, 0.6)
    mat_simple('ENV_placeholder', (0.3, 0.3, 0.3), 0.7)
    mat_simple('ENV_placeholder_dark', (0.08, 0.075, 0.07), 0.8)
    mat_simple('ENV_fire', (0.05, 0.02, 0.01), 0.5, 0.0, (1.0, 0.4, 0.08), 18.0)
    mat_simple('ENV_path', (0.05, 0.25, 0.6), 0.5, 0.0, (0.1, 0.45, 1.0), 2.5)
    mat_label()
    mat_volume_haze()
    mat_smoke()
    return MAT

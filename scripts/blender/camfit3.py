# post-script for run3.py: fit beauty camera to the reference silhouette (alpha of reference-heavy-mech.webp)
# coordinate descent over az/dist/cam_h/lens/target using fast Workbench silhouette renders.
import bpy, numpy as np, json, os
TUNE = globals().get('TUNE', {})
sc = bpy.context.scene
REF = np.load(TUNE['camfit_mask'])  # (286,344) top-down bool
H_, W_ = REF.shape
setview = bpy.app.driver_namespace['mech_setview']
tmp = TUNE.get('camfit_tmp', '/tmp/camfit.png')
eng = sc.render.engine
hidden = []


def render_mask():
    setview('beauty')
    r = sc.render
    r.engine = 'BLENDER_WORKBENCH'
    r.film_transparent = True
    r.resolution_percentage = 25
    r.filepath = tmp
    bpy.ops.render.render(write_still=True)
    img = bpy.data.images.load(tmp, check_existing=False)
    a = np.empty(img.size[0] * img.size[1] * 4, np.float32)
    img.pixels.foreach_get(a)
    a = a.reshape(img.size[1], img.size[0], 4)[::-1, :, 3] > 0.5
    bpy.data.images.remove(img)
    return a


def score(p):
    TUNE.update(p)
    m = render_mask()
    if m.shape != REF.shape:
        return 0.0
    return float((m & REF).sum() / max(1, (m | REF).sum()))


def fit(p0, fixed):
    keys = [k for k in ['az', 'dist', 'cam_h', 'lens', 'tx', 'tz'] if k not in fixed]
    steps = {'az': 4.0, 'dist': 1.5, 'cam_h': 0.6, 'lens': 4.0, 'tx': 0.3, 'tz': 0.3}
    p = dict(p0)
    best = ev(p)
    for rnd_ in range(5):
        for k in keys:
            for sgn in (1, -1):
                while True:
                    q = dict(p)
                    q[k] += sgn * steps[k]
                    if k == 'dist' and q[k] < 6:
                        break
                    s_ = ev(q)
                    if s_ > best + 1e-4:
                        p, best = q, s_
                    else:
                        break
        for k in steps:
            steps[k] *= 0.5
    return p, best


def ev(q):
    t = dict(q)
    t['target'] = [q['tx'], TUNE['target'][1], q['tz']]
    return score({k: t[k] for k in ('az', 'dist', 'cam_h', 'lens', 'target')})


p0 = {k: TUNE[k] for k in ('az', 'dist', 'cam_h', 'lens')}
p0['tx'], p0['tz'] = TUNE['target'][0], TUNE['target'][2]
starts = TUNE.get('camfit_starts', [{}])
fixed = TUNE.get('camfit_fix', [])
allres = []
for st in starts:
    q0 = dict(p0)
    q0.update(st)
    # keep the same framing when lens changes: scale distance with focal length
    if 'lens' in st and 'dist' not in st:
        q0['dist'] = p0['dist'] * st['lens'] / p0['lens']
    pp, bb = fit(q0, fixed)
    allres.append((bb, pp))
    print('CAMSTART', json.dumps(st), round(bb, 4), json.dumps({k: round(v, 3) for k, v in pp.items()}))
best, p = max(allres, key=lambda x: x[0])
res = {k: p[k] for k in ('az', 'dist', 'cam_h', 'lens')}
res['target'] = [p['tx'], TUNE['target'][1], p['tz']]
res['iou'] = best
json.dump(res, open(TUNE.get('camfit_out', '/tmp/camfit.json'), 'w'), indent=1)
print('CAMFIT', json.dumps(res))
TUNE.update({k: v for k, v in res.items() if k != 'iou'})
sc.render.engine = eng
sc.render.resolution_percentage = 100

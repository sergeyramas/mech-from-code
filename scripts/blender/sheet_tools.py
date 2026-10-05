"""v3 sheet tools: silhouette IoU vs 4-view sheet, overlay diffs, 2x2 sheet-layout compare grid.
usage: python sheet_tools.py <render_dir> <label> [out_compare.jpg]
render_dir must contain front.png back.png sideL.png sideR.png (RGBA, film_transparent ortho renders)"""
import sys, os, numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
REF = os.path.join(HERE, '..', 'ref_sheet')
LOG = os.path.join(HERE, '..', 'renders', 'v3_iou_log.tsv')
H_M = 9.0
VIEWS = ['front', 'back', 'sideL', 'sideR']
# component bboxes in sheet_a (y0, y1, x0, x1) inclusive-exclusive
BBOX = {'front': (8, 565, 74, 729), 'back': (8, 564, 753, 1334), 'sideL': (556, 1125, 263, 585), 'sideR': (556, 1126, 738, 1185)}


def mask_of(img):
    a = np.array(img.convert('RGBA'))
    return a[..., 3] > 128


def bbox(m):
    ys, xs = np.where(m)
    return ys.min(), ys.max() + 1, xs.min(), xs.max() + 1


def fit(ren_rgba, h):
    m = mask_of(ren_rgba)
    y0, y1, x0, x1 = bbox(m)
    crop = ren_rgba.crop((x0, y0, x1, y1))
    w = max(1, int(round((x1 - x0) * h / (y1 - y0))))
    crop = crop.resize((w, h), Image.LANCZOS)
    return crop, mask_of(crop)


def best_iou(R, Q):
    h, wr = R.shape
    wq = Q.shape[1]
    best = (-1, 0)
    for off in range(-wq + 1, wr):
        a0, a1 = max(0, off), min(wr, off + wq)
        if a1 - a0 < min(wr, wq) * 0.6:
            continue
        inter = np.logical_and(R[:, a0:a1], Q[:, a0 - off:a1 - off]).sum()
        union = R.sum() + Q.sum() - inter
        v = inter / union
        if v > best[0]:
            best = (v, off)
    return best


def profile_diff(R, Q, off, k):
    h, wr = R.shape
    W = max(wr, off + Q.shape[1]) - min(0, off)
    base = -min(0, off)
    A = np.zeros((h, W), bool)
    Bm = np.zeros((h, W), bool)
    A[:, base:base + wr] = R
    Bm[:, base + off:base + off + Q.shape[1]] = Q
    lines = []
    step = max(1, int(round(0.3 / k)))
    for r0 in range(0, h, step):
        a = A[r0:r0 + step].any(0)
        b = Bm[r0:r0 + step].any(0)
        if not a.any() and not b.any():
            continue
        z = (h - r0 - step / 2) * k
        xa = np.where(a)[0]
        xb = np.where(b)[0]
        ea = ((xa.min() - base) * k, (xa.max() - base) * k) if len(xa) else (np.nan, np.nan)
        eb = ((xb.min() - base) * k, (xb.max() - base) * k) if len(xb) else (np.nan, np.nan)
        ab = np.logical_and(A[r0:r0 + step], Bm[r0:r0 + step]).sum()
        ub = np.logical_or(A[r0:r0 + step], Bm[r0:r0 + step]).sum()
        lines.append('  z%5.2f ref[%5.2f,%5.2f] v3[%5.2f,%5.2f] fillref %.2f fillv3 %.2f iou %.2f' % (
            z, ea[0], ea[1], eb[0], eb[1], a.mean(), b.mean(), ab / max(ub, 1)))
    return lines, A, Bm


def main():
    rdir = sys.argv[1]
    label = sys.argv[2]
    out = sys.argv[3] if len(sys.argv) > 3 else os.path.join(rdir, 'sheet_compare.jpg')
    sheet = Image.open(os.path.join(REF, 'sheet_a_white.jpg')).convert('RGB')
    grid = Image.new('RGB', sheet.size, (255, 255, 255))
    res = {}
    diag = []
    overlays = []
    for v in VIEWS:
        p = os.path.join(rdir, v + '.png')
        if not os.path.exists(p):
            continue
        R = np.array(Image.open(os.path.join(REF, 'mask_%s.png' % v))) > 128
        h = R.shape[0]
        k = H_M / h
        ren = Image.open(p).convert('RGBA')
        crop, Q = fit(ren, h)
        iou, off = best_iou(R, Q)
        res[v] = iou
        lines, A, Bm = profile_diff(R, Q, off, k)
        diag.append('== %s IoU %.3f  (ref w %.2fm, v3 w %.2fm)' % (v, iou, R.shape[1] * k, Q.shape[1] * k))
        diag += lines
        ov = np.full(A.shape + (3,), 255, np.uint8)
        ov[A & Bm] = (150, 150, 150)
        ov[A & ~Bm] = (230, 40, 40)
        ov[~A & Bm] = (40, 90, 230)
        overlays.append(Image.fromarray(ov))
        y0, y1, x0, x1 = BBOX[v]
        white = Image.new('RGBA', crop.size, (255, 255, 255, 255))
        comp = Image.alpha_composite(white, crop).convert('RGB')
        grid.paste(comp, (x0 + off, y0), crop.split()[3])
    # overlay strip
    hh = max(o.size[1] for o in overlays)
    strip = Image.new('RGB', (sum(o.size[0] for o in overlays) + 20 * len(overlays), hh), (255, 255, 255))
    x = 0
    for o in overlays:
        strip.paste(o, (x, 0))
        x += o.size[0] + 20
    strip.save(os.path.join(rdir, 'overlay.png'))
    both = Image.new('RGB', (sheet.size[0] * 2 + 20, sheet.size[1]), (255, 255, 255))
    both.paste(sheet, (0, 0))
    both.paste(grid, (sheet.size[0] + 20, 0))
    both.save(out, quality=90)
    with open(os.path.join(rdir, 'diag.txt'), 'w') as f:
        f.write('\n'.join(diag))
    newlog = not os.path.exists(LOG)
    with open(LOG, 'a') as f:
        if newlog:
            f.write('label\t' + '\t'.join(VIEWS) + '\n')
        f.write(label + '\t' + '\t'.join('%.3f' % res.get(v, float('nan')) for v in VIEWS) + '\n')
    print(label, ' '.join('%s=%.3f' % (v, res[v]) for v in VIEWS if v in res))


if __name__ == '__main__':
    main()

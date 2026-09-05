"""
Automatic registration of the reference circuit map onto the OSM centreline.

No hand-read pixel coordinates and no OCR:

1.  The rasterised reference map is thresholded to a near-black mask.
2.  Connected components separate the track band (largest blob) from the 15
    circled turn-number labels (ring-shaped blobs of a characteristic size).
3.  A similarity transform world -> image is fitted by maximising the fraction
    of centreline samples that land on the track band, coarse-to-fine over a
    dilated mask pyramid, seeded from centroid / RMS-radius / PCA moments.
4.  Each label ring is projected back to world space and snapped to the lap.
    Turn numbers then follow from lap order alone (they must increase along the
    lap), so no digit recognition is needed.

Requires Blender's bundled numpy; run inside Blender.
"""

import math
import os

import numpy as np

from . import geo

REF_PNG = os.path.join(geo.DATA_DIR, "ref", "sepang_layout_detail.png")
# the compass rose lives here and is not track
EXCLUDE_BOXES = [(1540, 0, 1920, 300)]      # x0, y0, x1, y1 (top-left origin)
RING_PX = (55, 125)                          # plausible label-ring bbox size


def load_mask(path=REF_PNG, thresh=0.35):
    import bpy
    img = bpy.data.images.get(os.path.basename(path))
    if img is None:
        img = bpy.data.images.load(path, check_existing=True)
    W, H = img.size
    px = np.array(img.pixels[:], dtype=np.float32).reshape(H, W, 4)
    px = px[::-1]                            # bottom-up -> top-down
    dark = (px[:, :, 0] < thresh) & (px[:, :, 1] < thresh) & (px[:, :, 2] < thresh)
    dark &= px[:, :, 3] > 0.5
    for x0, y0, x1, y1 in EXCLUDE_BOXES:
        dark[y0:y1, x0:x1] = False
    return dark


def components(mask):
    """Union-find labelling over set pixels only (the mask is sparse)."""
    ys, xs = np.nonzero(mask)
    idx = {}
    for n, (y, x) in enumerate(zip(ys.tolist(), xs.tolist())):
        idx[(y, x)] = n
    parent = list(range(len(ys)))

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    for (y, x), n in idx.items():
        for dy, dx in ((0, -1), (-1, 0), (-1, -1), (-1, 1)):
            m = idx.get((y + dy, x + dx))
            if m is not None:
                union(n, m)

    groups = {}
    for (y, x), n in idx.items():
        r = find(n)
        g = groups.get(r)
        if g is None:
            groups[r] = g = {"n": 0, "sx": 0, "sy": 0,
                             "x0": x, "x1": x, "y0": y, "y1": y}
        g["n"] += 1
        g["sx"] += x
        g["sy"] += y
        g["x0"] = min(g["x0"], x)
        g["x1"] = max(g["x1"], x)
        g["y0"] = min(g["y0"], y)
        g["y1"] = max(g["y1"], y)
    out = []
    for g in groups.values():
        g["cx"] = g["sx"] / g["n"]
        g["cy"] = g["sy"] / g["n"]
        g["w"] = g["x1"] - g["x0"] + 1
        g["h"] = g["y1"] - g["y0"] + 1
        g["fill"] = g["n"] / float(g["w"] * g["h"])
        out.append(g)
    out.sort(key=lambda g: -g["n"])
    return out


def find_label_rings(comps):
    rings = []
    for g in comps[1:]:
        if not (RING_PX[0] <= g["w"] <= RING_PX[1] and RING_PX[0] <= g["h"] <= RING_PX[1]):
            continue
        if abs(g["w"] - g["h"]) > 0.25 * max(g["w"], g["h"]):
            continue
        if g["fill"] > 0.6:                  # rings are hollow
            continue
        rings.append(g)
    return rings


def dilate(mask, k):
    if k <= 0:
        return mask
    out = mask.copy()
    for s in range(1, k + 1):
        out[:-s, :] |= mask[s:, :]
        out[s:, :] |= mask[:-s, :]
        out[:, :-s] |= mask[:, s:]
        out[:, s:] |= mask[:, :-s]
    return out


def track_mask(mask, comps):
    big = comps[0]
    out = np.zeros_like(mask)
    # rebuild the largest component by flood-restricting to its bbox and
    # removing ring/digit blobs, which is enough for fitting purposes
    out[big["y0"]:big["y1"] + 1, big["x0"]:big["x1"] + 1] = \
        mask[big["y0"]:big["y1"] + 1, big["x0"]:big["x1"] + 1]
    for g in comps[1:]:
        if g["n"] < big["n"] * 0.5:
            out[g["y0"]:g["y1"] + 1, g["x0"]:g["x1"] + 1] = False
    return out


class Fit:
    """image = s * R(theta) * M * world + t   (M = optional x-mirror)"""

    def __init__(self, s, theta, tx, ty, mirror):
        self.s, self.theta, self.tx, self.ty, self.mirror = s, theta, tx, ty, mirror

    def to_image(self, pts):
        c, si = math.cos(self.theta), math.sin(self.theta)
        m = -1.0 if self.mirror else 1.0
        out = []
        for x, y in pts:
            x = x * m
            out.append((self.s * (c * x - si * y) + self.tx,
                        self.s * (si * x + c * y) + self.ty))
        return out

    def to_world(self, px):
        c, si = math.cos(self.theta), math.sin(self.theta)
        m = -1.0 if self.mirror else 1.0
        out = []
        for X, Y in px:
            u = (X - self.tx) / self.s
            v = (Y - self.ty) / self.s
            x = c * u + si * v
            y = -si * u + c * v
            out.append((x * m, y))
        return out

    def as_tuple(self):
        return (self.s, self.theta, self.tx, self.ty, self.mirror)


def score(fit, pts, mask):
    H, W = mask.shape
    hit = 0
    for X, Y in fit.to_image(pts):
        xi, yi = int(X), int(Y)
        if 0 <= xi < W and 0 <= yi < H and mask[yi, xi]:
            hit += 1
    return hit / float(len(pts))


def fit_transform(pts, mask):
    ys, xs = np.nonzero(mask)
    mcx, mcy = xs.mean(), ys.mean()
    mrad = math.sqrt(((xs - mcx) ** 2 + (ys - mcy) ** 2).mean())

    wx = sum(p[0] for p in pts) / len(pts)
    wy = sum(p[1] for p in pts) / len(pts)
    wrad = math.sqrt(sum((p[0] - wx) ** 2 + (p[1] - wy) ** 2 for p in pts) / len(pts))
    cen = [(p[0] - wx, p[1] - wy) for p in pts]

    s0 = mrad / wrad
    pyramid = [(dilate(mask, 22), 6.0), (dilate(mask, 10), 2.0), (mask, 0.0)]

    best = None
    for mirror in (False, True):
        for deg in range(0, 360, 3):
            f = Fit(s0, math.radians(deg), mcx, mcy, mirror)
            sc = score(f, cen[::6], pyramid[0][0])
            if best is None or sc > best[0]:
                best = (sc, f)
    sc, f = best

    for level, (m, _) in enumerate(pyramid):
        step_deg = (3.0, 0.75, 0.25)[level]
        step_px = (14.0, 5.0, 1.5)[level]
        step_s = (0.05, 0.015, 0.004)[level]
        cur = score(f, cen, m)
        for _ in range(60):
            improved = False
            for dth in (-step_deg, step_deg):
                cand = Fit(f.s, f.theta + math.radians(dth), f.tx, f.ty, f.mirror)
                v = score(cand, cen, m)
                if v > cur:
                    cur, f, improved = v, cand, True
            for dx, dy in ((step_px, 0), (-step_px, 0), (0, step_px), (0, -step_px)):
                cand = Fit(f.s, f.theta, f.tx + dx, f.ty + dy, f.mirror)
                v = score(cand, cen, m)
                if v > cur:
                    cur, f, improved = v, cand, True
            for ds in (1 + step_s, 1 - step_s):
                cand = Fit(f.s * ds, f.theta, f.tx, f.ty, f.mirror)
                v = score(cand, cen, m)
                if v > cur:
                    cur, f, improved = v, cand, True
            if not improved:
                break
    # bake the world-centroid offset into the transform
    final = Fit(f.s, f.theta, f.tx, f.ty, f.mirror)
    final.wx, final.wy = wx, wy
    return final, score(f, cen, mask)


def main():
    d = geo.build_centreline(use_cache=False, write_cache=False)
    pts = [tuple(p) for p in d["points"]]
    sp = d["spacing_m"]
    n = len(pts)
    curv = d["curvature"]

    mask = load_mask()
    comps = components(mask)
    tmask = track_mask(mask, comps)
    rings = find_label_rings(comps)
    print("components: %d ; largest %d px ; rings found: %d"
          % (len(comps), comps[0]["n"], len(rings)))

    cen = [(p[0] - 0, p[1] - 0) for p in pts]
    fit, sc = fit_transform(pts, tmask)
    wx, wy = fit.wx, fit.wy
    print("fit: mirror=%s scale=%.4f px/m (%.4f m/px) rot=%.2f deg  inlier=%.1f%%"
          % (fit.mirror, fit.s, 1.0 / fit.s, math.degrees(fit.theta) % 360, sc * 100))

    # project rings into world space
    ring_px = [(g["cx"], g["cy"]) for g in rings]
    ring_w = fit.to_world(ring_px)
    ring_w = [(x + wx, y + wy) for x, y in ring_w]

    def nearest_s(p):
        best, bi = None, 0
        for i, q in enumerate(pts):
            dd = (p[0] - q[0]) ** 2 + (p[1] - q[1]) ** 2
            if best is None or dd < best:
                best, bi = dd, i
        return bi, math.sqrt(best)

    proj = []
    for p in ring_w:
        i, dist = nearest_s(p)
        proj.append((i, dist, p))
    proj.sort(key=lambda t: t[0])
    print("\nring -> lap position (sorted): turn number = rank")
    for k, (i, dist, p) in enumerate(proj, 1):
        print("  T%-3d s=%6.0f m  label offset %5.0f m" % (k, i * sp, dist))

    # --- apex per turn: strongest curvature near the verified label position
    label_i = [t[0] for t in proj]
    rows = []
    for k, li in enumerate(label_i, 1):
        prev_gap = ((li - label_i[k - 2]) % n) if k > 1 else n
        next_gap = ((label_i[k % len(label_i)] - li) % n) if k < len(label_i) else n
        win = int(min(15, max(5, prev_gap * 0.45), max(5, next_gap * 0.45)))
        cand = [(li + dd) % n for dd in range(-win, win + 1)]
        # prefer a genuine local curvature maximum; on a corner that tightens
        # continuously into the next turn there is none, and the registered
        # label position is then the better apex estimate.
        loc = [i for i in cand
               if all(abs(curv[i]) >= abs(curv[(i + d) % n]) for d in range(-5, 6))]
        if loc:
            a = max(loc, key=lambda i: abs(curv[i]))
        else:
            a = max([(li + dd) % n for dd in range(-6, 7)], key=lambda i: abs(curv[i]))
        i0, i1 = geo.corner_extent(curv, a, sp)
        kap = curv[a]
        hc = math.degrees(sum(curv[(i0 + t) % n] for t in range(((i1 - i0) % n) + 1)) * sp)
        rows.append(dict(id=k, i_label=li, i_apex=a, i_start=i0, i_end=i1,
                         radius_m=1.0 / abs(kap),
                         dir="left" if kap > 0 else "right",
                         heading_change_deg=hc))

    print("\nturn  s_label  s_apex   R       dir    heading  extent")
    for r in rows:
        print("T%-4d %6.0f  %6.0f  %6.1f  %-6s %7.1f %6.0f m"
              % (r["id"], r["i_label"] * sp, r["i_apex"] * sp, r["radius_m"],
                 r["dir"], r["heading_change_deg"], ((r["i_end"] - r["i_start"]) % n) * sp))

    print("\n# verified against %s (registration inlier %.1f%%, label offsets %.0f-%.0f m)"
          % (os.path.basename(REF_PNG), sc * 100,
             min(t[1] for t in proj), max(t[1] for t in proj)))
    print("VERIFIED_TURNS = [")
    for r in rows:
        print("    dict(id=%2d, s_apex_m=%6.1f, s_start_m=%6.1f, s_end_m=%6.1f, radius_m=%6.1f, dir=%-7r, heading_change_deg=%7.1f),"
              % (r["id"], r["i_apex"] * sp, r["i_start"] * sp, r["i_end"] * sp,
                 r["radius_m"], r["dir"], r["heading_change_deg"]))
    print("]")
    return rows, fit, proj


if __name__ == "__main__":
    main()

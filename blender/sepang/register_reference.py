"""
Register the FIA-style reference circuit map onto the OSM-derived centreline so
the 15 turn numbers are assigned from published ground truth instead of by eye.

Method
------
1.  Three hand-read correspondences (start/finish line, Turn 1 apex, Turn 15
    apex) give a similarity transform image -> world by complex least squares.
    Both mirror options are tried; the lower-residual one wins.
2.  The 15 turn-number label positions are mapped into world space.
3.  Candidate corner groups are extracted from the centreline curvature.
4.  Turn numbers are assigned to groups by monotonic (order-preserving) dynamic
    programming, which is what makes the result robust to the ~25 m error in
    the hand-read pixel coordinates: numbering must increase along the lap.

Run this once; paste the resulting apex table into geo.py as VERIFIED_TURNS.
"""

import math

from . import geo

# --- reference map: Circuit_Sepang_1999.svg rasterised at 1920x1440 --------
# pixel coords, origin top-left
REF_LABELS = {
    1: (1720, 1110), 2: (1420, 1045), 3: (1262, 1292), 4: (552, 1130),
    5: (786, 692), 6: (365, 684), 7: (255, 142), 8: (566, 45),
    9: (1118, 406), 10: (996, 122), 11: (1350, 38), 12: (1456, 430),
    13: (1756, 610), 14: (1686, 876), 15: (474, 236),
}
REF_SF = (1200, 790)        # checkered start/finish line
REF_T1_APEX = (1710, 1115)  # outer extreme of the Turn 1 right hairpin
REF_T15_APEX = (517, 337)   # extreme of the Turn 15 hairpin


def fit_similarity(src, dst):
    """Least-squares complex similarity dst = a*src + b; returns (a, b, rms)."""
    p = [complex(x, -y) for x, y in src]     # flip to a right-handed frame
    q = [complex(x, y) for x, y in dst]
    pm = sum(p) / len(p)
    qm = sum(q) / len(q)
    num = sum((qi - qm) * (pi - pm).conjugate() for pi, qi in zip(p, q))
    den = sum(abs(pi - pm) ** 2 for pi in p)
    a = num / den
    b = qm - a * pm
    rms = math.sqrt(sum(abs(a * pi + b - qi) ** 2 for pi, qi in zip(p, q)) / len(p))
    return a, b, rms


def fit_similarity_mirrored(src, dst):
    p = [complex(x, -y) for x, y in src]
    src2 = [(z.conjugate().real, -z.conjugate().imag) for z in p]
    return fit_similarity(src2, dst)


def group_apexes(curv, spacing, merge_m=150.0):
    """Merge curvature apexes that belong to one corner (same sign, overlapping)."""
    n = len(curv)
    ap = geo.detect_apexes(curv, spacing, kappa_min=1.0 / 380.0, min_sep_m=52.0)
    groups = []
    for a in ap:
        i0, i1 = geo.corner_extent(curv, a, spacing)
        same = None
        for g in groups:
            if (curv[a] > 0) == (curv[g["apex"]] > 0) and \
               min((a - g["apex"]) % n, (g["apex"] - a) % n) * spacing < merge_m:
                same = g
                break
        if same:
            if abs(curv[a]) > abs(curv[same["apex"]]):
                same["apex"] = a
            same["i0"] = min(same["i0"], i0, key=lambda i: (i - a) % n)
            same["i1"] = max(same["i1"], i1, key=lambda i: (i - a) % n)
            same["members"].append(a)
        else:
            groups.append({"apex": a, "i0": i0, "i1": i1, "members": [a]})
    groups.sort(key=lambda g: g["apex"])
    return groups


def assign_monotonic(labels_world, groups, pts):
    """
    Order-preserving assignment of turn numbers to corner groups.
    labels_world: list of 15 (x, y) in lap order; groups: candidates in lap order.
    Returns list of group indices, one per label.
    """
    L, G = len(labels_world), len(groups)
    INF = float("inf")
    cost = [[0.0] * G for _ in range(L)]
    for li, (lx, ly) in enumerate(labels_world):
        for gi, g in enumerate(groups):
            gx, gy = pts[g["apex"]]
            cost[li][gi] = math.hypot(lx - gx, ly - gy)
    dp = [[INF] * G for _ in range(L)]
    back = [[-1] * G for _ in range(L)]
    for gi in range(G):
        dp[0][gi] = cost[0][gi]
    for li in range(1, L):
        best, bgi = INF, -1          # prefix min over groups strictly before gi
        for gi in range(G):
            if best < INF:
                dp[li][gi] = best + cost[li][gi]
                back[li][gi] = bgi
            if dp[li - 1][gi] < best:
                best, bgi = dp[li - 1][gi], gi
    endgi = min(range(G), key=lambda gi: dp[L - 1][gi])
    out = [endgi]
    for li in range(L - 1, 0, -1):
        endgi = back[li][endgi]
        out.append(endgi)
    return list(reversed(out))


def main():
    d = geo.build_centreline(use_cache=False, write_cache=False)
    pts = [tuple(p) for p in d["points"]]
    sp = d["spacing_m"]
    n = len(pts)
    curv = d["curvature"]

    groups = group_apexes(curv, sp)

    # world anchors
    def at_s(s):
        return pts[int(round(s / sp)) % n]

    t1_s = min((g["apex"] * sp for g in groups), key=lambda s: abs(s - 670))
    t15_s = min((g["apex"] * sp for g in groups), key=lambda s: abs(s - 5164))
    src = [REF_SF, REF_T1_APEX, REF_T15_APEX]
    dst = [pts[0], at_s(t1_s), at_s(t15_s)]

    a1, b1, r1 = fit_similarity(src, dst)
    a2, b2, r2 = fit_similarity_mirrored(src, dst)
    mirrored = r2 < r1
    a, b, rms = (a2, b2, r2) if mirrored else (a1, b1, r1)

    def to_world(px):
        z = complex(px[0], -px[1])
        if mirrored:
            z = z.conjugate()
        w = a * z + b
        return (w.real, w.imag)

    labels_world = [to_world(REF_LABELS[i]) for i in range(1, 16)]
    pick = assign_monotonic(labels_world, groups, pts)

    print("similarity fit: mirrored=%s  scale=%.4f m/px  rot=%.1f deg  rms=%.1f m"
          % (mirrored, abs(a), math.degrees(math.atan2(a.imag, a.real)), rms))
    print("corner groups: %d" % len(groups))
    print()
    print("turn  s_apex   R      dir    heading   label_dist  extent")
    rows = []
    for tn, gi in zip(range(1, 16), pick):
        g = groups[gi]
        ap = g["apex"]
        k = curv[ap]
        i0, i1 = g["i0"], g["i1"]
        hc = math.degrees(sum(curv[(i0 + t) % n] for t in range(((i1 - i0) % n) + 1)) * sp)
        lx, ly = labels_world[tn - 1]
        gx, gy = pts[ap]
        rows.append(dict(id=tn, i_apex=ap, s_apex_m=ap * sp, i_start=i0, i_end=i1,
                         radius_m=1.0 / abs(k), dir="left" if k > 0 else "right",
                         heading_change_deg=hc))
        print("T%-4d %6.0f %6.1f %-6s %7.1f %9.0f %8.0f" % (
            tn, ap * sp, 1.0 / abs(k), "left" if k > 0 else "right", hc,
            math.hypot(lx - gx, ly - gy), ((i1 - i0) % n) * sp))
    unused = [g["apex"] * sp for i, g in enumerate(groups) if i not in pick]
    print("\nunassigned curvature features at s =", ["%.0f" % u for u in unused])
    print("\nVERIFIED_TURN_APEXES = [")
    for r in rows:
        print("    dict(id=%d, i_apex=%d, i_start=%d, i_end=%d, radius_m=%.1f, dir=%r, heading_change_deg=%.1f),"
              % (r["id"], r["i_apex"], r["i_start"], r["i_end"], r["radius_m"], r["dir"], r["heading_change_deg"]))
    print("]")
    return rows


if __name__ == "__main__":
    main()

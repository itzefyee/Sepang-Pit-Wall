"""
Sepang International Circuit centreline reconstruction.

Source of truth: OpenStreetMap survey geometry (ODbL) for the `highway=raceway`
ways that make up the Grand Prix layout, cached in ../data/sepang_osm.json.

Everything downstream (track mesh, race sim, animation) consumes the
`build_centreline()` result, which is a closed, arc-length-uniform polyline in
metres with per-sample curvature, elevation, corner ids and DRS flags.
"""

import json
import math
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA_DIR = os.path.join(ROOT, "data")
OSM_PATH = os.path.join(DATA_DIR, "sepang_osm.json")
ELEV_CACHE = os.path.join(DATA_DIR, "sepang_elevation.json")
CENTRELINE_CACHE = os.path.join(DATA_DIR, "sepang_centreline.json")

# The GP loop is stored in OSM as two oneway ways that share both end nodes.
CIRCUIT_WAYS = [23410503, 144359489]
# Pit lane: entry spur + the lane itself (runs inside the main straight).
PITLANE_WAYS = [144359482, 144359483]

OFFICIAL_LENGTH_M = 5543.0     # FIA-homologated GP layout length
TRACK_WIDTH_M = 16.0           # Sepang is unusually wide (15-22 m); 16 m nominal
SAMPLE_SPACING_M = 4.0
# Where the painted start/finish line sits along the pit straight, measured
# from the point the Turn 15 hairpin exit straightens out.
SF_AFTER_T15_EXIT_M = 300.0

EARTH_R = 6378137.0


# --------------------------------------------------------------------------
# OSM loading / projection
# --------------------------------------------------------------------------
def load_osm(path=OSM_PATH):
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def ways_by_id(osm):
    return {w["id"]: w for w in osm["elements"] if w["type"] == "way"}


def chain_ways(way_ids, table):
    """Stitch ways into a single node/coord chain using shared end nodes."""
    remaining = list(way_ids)
    first = table[remaining.pop(0)]
    nodes = list(first["nodes"])
    coords = [(g["lat"], g["lon"]) for g in first["geometry"]]

    while remaining:
        for i, wid in enumerate(remaining):
            w = table[wid]
            wn = list(w["nodes"])
            wc = [(g["lat"], g["lon"]) for g in w["geometry"]]
            if nodes[-1] == wn[0]:
                nodes += wn[1:]
                coords += wc[1:]
            elif nodes[-1] == wn[-1]:
                nodes += list(reversed(wn))[1:]
                coords += list(reversed(wc))[1:]
            elif nodes[0] == wn[-1]:
                nodes = wn[:-1] + nodes
                coords = wc[:-1] + coords
            elif nodes[0] == wn[0]:
                nodes = list(reversed(wn))[:-1] + nodes
                coords = list(reversed(wc))[:-1] + coords
            else:
                continue
            remaining.pop(i)
            break
        else:
            raise ValueError("ways do not form a chain: %s" % remaining)

    closed = nodes[0] == nodes[-1]
    if closed:
        nodes = nodes[:-1]
        coords = coords[:-1]
    return nodes, coords, closed


def projector(lat0, lon0):
    k = math.cos(math.radians(lat0))

    def to_xy(lat, lon):
        return (math.radians(lon - lon0) * EARTH_R * k,
                math.radians(lat - lat0) * EARTH_R)
    return to_xy


# --------------------------------------------------------------------------
# polyline maths
# --------------------------------------------------------------------------
def seg_lengths(pts, closed=True):
    n = len(pts)
    out = []
    last = n if closed else n - 1
    for i in range(last):
        ax, ay = pts[i]
        bx, by = pts[(i + 1) % n]
        out.append(math.hypot(bx - ax, by - ay))
    return out


def polyline_length(pts, closed=True):
    return sum(seg_lengths(pts, closed))


def resample_closed(pts, spacing):
    """Uniform arc-length resample of a closed polyline (linear interp)."""
    L = polyline_length(pts, True)
    n_out = max(16, int(round(L / spacing)))
    step = L / n_out
    segs = seg_lengths(pts, True)
    out = []
    si, acc = 0, 0.0
    for i in range(n_out):
        target = i * step
        while acc + segs[si] < target and si < len(segs) - 1:
            acc += segs[si]
            si += 1
        t = 0.0 if segs[si] == 0 else (target - acc) / segs[si]
        ax, ay = pts[si]
        bx, by = pts[(si + 1) % len(pts)]
        out.append((ax + (bx - ax) * t, ay + (by - ay) * t))
    return out


def resample_open(pts, spacing):
    """Uniform arc-length resample of an open polyline."""
    segs = seg_lengths(pts, False)
    L = sum(segs)
    n_out = max(2, int(round(L / spacing)))
    out = []
    si, acc = 0, 0.0
    for i in range(n_out + 1):
        target = min(i * (L / n_out), L)
        while si < len(segs) - 1 and acc + segs[si] < target:
            acc += segs[si]
            si += 1
        t = 0.0 if segs[si] == 0 else (target - acc) / segs[si]
        ax, ay = pts[si]
        bx, by = pts[si + 1]
        out.append((ax + (bx - ax) * t, ay + (by - ay) * t))
    return out


def gaussian_smooth_closed(pts, sigma_samples):
    if sigma_samples <= 0:
        return list(pts)
    radius = max(1, int(math.ceil(sigma_samples * 3)))
    kernel = [math.exp(-0.5 * (d / sigma_samples) ** 2)
              for d in range(-radius, radius + 1)]
    ks = sum(kernel)
    kernel = [k / ks for k in kernel]
    n = len(pts)
    out = []
    for i in range(n):
        sx = sy = 0.0
        for j, k in enumerate(kernel):
            p = pts[(i + j - radius) % n]
            sx += p[0] * k
            sy += p[1] * k
        out.append((sx, sy))
    return out


def scale_to_length(pts, target_len):
    L = polyline_length(pts, True)
    s = target_len / L
    cx = sum(p[0] for p in pts) / len(pts)
    cy = sum(p[1] for p in pts) / len(pts)
    return [((p[0] - cx) * s, (p[1] - cy) * s) for p in pts], s


def signed_curvature(pts, closed=True):
    """Menger curvature with sign (+ left turn, - right turn), 1/m."""
    n = len(pts)
    out = []
    for i in range(n):
        a = pts[(i - 1) % n]
        b = pts[i]
        c = pts[(i + 1) % n]
        ux, uy = b[0] - a[0], b[1] - a[1]
        vx, vy = c[0] - b[0], c[1] - b[1]
        cross = ux * vy - uy * vx
        la = math.hypot(ux, uy)
        lb = math.hypot(vx, vy)
        lc = math.hypot(c[0] - a[0], c[1] - a[1])
        denom = la * lb * lc
        out.append(0.0 if denom < 1e-9 else 2.0 * cross / denom)
    return out


def tangents(pts, closed=True):
    n = len(pts)
    out = []
    for i in range(n):
        a = pts[(i - 1) % n]
        c = pts[(i + 1) % n]
        dx, dy = c[0] - a[0], c[1] - a[1]
        L = math.hypot(dx, dy) or 1.0
        out.append((dx / L, dy / L))
    return out


def rotate(seq, k):
    k %= len(seq)
    return seq[k:] + seq[:k]


# --------------------------------------------------------------------------
# corner detection
# --------------------------------------------------------------------------
def detect_corners(pts, curv, spacing, kappa_on=1.0 / 260.0, min_gap_m=55.0):
    """Group contiguous above-threshold curvature runs into corner segments."""
    n = len(pts)
    mask = [abs(k) > kappa_on for k in curv]
    if not any(mask):
        return []
    # rotate so we start on a straight
    start = mask.index(False)
    idx = list(range(n))
    idx = rotate(idx, start)

    runs = []
    cur = []
    for i in idx:
        if mask[i]:
            cur.append(i)
        elif cur:
            runs.append(cur)
            cur = []
    if cur:
        runs.append(cur)

    # merge runs separated by a short straight (same corner, noisy curvature)
    merged = []
    for run in runs:
        if merged:
            gap = (run[0] - merged[-1][-1]) % n
            same_dir = (curv[run[len(run) // 2]] > 0) == (curv[merged[-1][len(merged[-1]) // 2]] > 0)
            if gap * spacing < min_gap_m and same_dir:
                merged[-1] = merged[-1] + [(merged[-1][-1] + g) % n for g in range(1, gap + 1)] + run
                continue
        merged.append(run)

    corners = []
    for run in merged:
        kmax = max(run, key=lambda i: abs(curv[i]))
        kappa = curv[kmax]
        # integrated heading change across the run
        turn = sum(curv[i] for i in run) * spacing
        corners.append({
            "i_start": run[0],
            "i_apex": kmax,
            "i_end": run[-1],
            "length_m": len(run) * spacing,
            "kappa": kappa,
            "radius_m": (1.0 / abs(kappa)) if kappa else 1e9,
            "dir": "left" if kappa > 0 else "right",
            "heading_change_deg": math.degrees(turn),
        })
    return corners


def detect_apexes(curv, spacing, kappa_min=1.0 / 380.0, min_sep_m=52.0, want=15):
    """
    Corner apexes = local maxima of |curvature| above a threshold, with
    non-maximum suppression. Unlike run-grouping this keeps double-apex
    complexes (Sepang T5/T6, T7/T8, T12/T13) as separate turns, which is how
    the FIA numbers them.
    """
    n = len(curv)
    win = max(2, int(round(20.0 / spacing)))
    cands = []
    for i in range(n):
        k = abs(curv[i])
        if k < kappa_min:
            continue
        if all(k >= abs(curv[(i + d) % n]) for d in range(-win, win + 1)):
            cands.append(i)
    # non-maximum suppression by separation
    cands.sort(key=lambda i: -abs(curv[i]))
    sep = int(round(min_sep_m / spacing))
    kept = []
    for i in cands:
        if all(min((i - j) % n, (j - i) % n) >= sep for j in kept):
            kept.append(i)
    kept.sort()
    return kept


def corner_extent(curv, apex, spacing, frac=0.30):
    """Walk out from an apex until curvature falls below a fraction of its peak."""
    n = len(curv)
    thr = max(abs(curv[apex]) * frac, 1.0 / 900.0)
    sign = 1 if curv[apex] > 0 else -1
    i = apex
    while abs(curv[(i - 1) % n]) > thr and (1 if curv[(i - 1) % n] > 0 else -1) == sign:
        i = (i - 1) % n
        if (apex - i) % n > int(300 / spacing):
            break
    j = apex
    while abs(curv[(j + 1) % n]) > thr and (1 if curv[(j + 1) % n] > 0 else -1) == sign:
        j = (j + 1) % n
        if (j - apex) % n > int(300 / spacing):
            break
    return i, j


def find_straights(curv, spacing, kappa_off=1.0 / 900.0):
    n = len(curv)
    mask = [abs(k) < kappa_off for k in curv]
    if not any(mask):
        return []
    start = mask.index(False) if False in mask else 0
    idx = rotate(list(range(n)), start)
    runs, cur = [], []
    for i in idx:
        if mask[i]:
            cur.append(i)
        elif cur:
            runs.append(cur)
            cur = []
    if cur:
        runs.append(cur)
    out = [{"i_start": r[0], "i_end": r[-1], "length_m": len(r) * spacing} for r in runs]
    out.sort(key=lambda s: -s["length_m"])
    return out


# --------------------------------------------------------------------------
# Verified corner table
# --------------------------------------------------------------------------
# Produced by sepang.register_image, which fits a similarity transform between
# this centreline and the rasterised FIA-style reference map, auto-detects the
# 15 circled turn-number labels as ring-shaped connected components, and
# projects them back onto the lap. Turn numbers follow from lap order, so no
# digit recognition and no hand-read pixel coordinates are involved.
#   registration inlier rate : 95.8 % of centreline samples inside the drawn band
#   label offsets            : 36-69 m (labels sit just outside the track edge)
# Distances are metres from the start/finish line in racing direction.
VERIFIED_TURNS = [
    dict(id=1,  s_apex_m=640.0,  s_start_m=604.0,  s_end_m=732.0,  radius_m=30.9,  dir="right", heading_change_deg=-192.5),
    dict(id=2,  s_apex_m=784.0,  s_start_m=760.0,  s_end_m=820.0,  radius_m=19.8,  dir="left",  heading_change_deg=128.0),
    dict(id=3,  s_apex_m=1088.0, s_start_m=992.0,  s_end_m=1192.0, radius_m=136.8, dir="right", heading_change_deg=-65.8),
    dict(id=4,  s_apex_m=1592.0, s_start_m=1564.0, s_end_m=1612.0, radius_m=22.3,  dir="right", heading_change_deg=-95.0),
    dict(id=5,  s_apex_m=1952.0, s_start_m=1824.0, s_end_m=2092.0, radius_m=103.9, dir="left",  heading_change_deg=125.9),
    dict(id=6,  s_apex_m=2188.0, s_start_m=2108.0, s_end_m=2280.0, radius_m=85.8,  dir="right", heading_change_deg=-95.2),
    dict(id=7,  s_apex_m=2572.0, s_start_m=2556.0, s_end_m=2592.0, radius_m=30.1,  dir="right", heading_change_deg=-56.1),
    dict(id=8,  s_apex_m=2680.0, s_start_m=2664.0, s_end_m=2704.0, radius_m=32.2,  dir="right", heading_change_deg=-56.8),
    dict(id=9,  s_apex_m=3172.0, s_start_m=3144.0, s_end_m=3192.0, radius_m=16.5,  dir="left",  heading_change_deg=129.7),
    dict(id=10, s_apex_m=3304.0, s_start_m=3256.0, s_end_m=3436.0, radius_m=76.2,  dir="right", heading_change_deg=-80.0),
    dict(id=11, s_apex_m=3520.0, s_start_m=3496.0, s_end_m=3560.0, radius_m=33.0,  dir="right", heading_change_deg=-88.2),
    dict(id=12, s_apex_m=3840.0, s_start_m=3824.0, s_end_m=3904.0, radius_m=57.7,  dir="left",  heading_change_deg=63.8),
    dict(id=13, s_apex_m=4112.0, s_start_m=3976.0, s_end_m=4272.0, radius_m=121.6, dir="right", heading_change_deg=-193.5),
    dict(id=14, s_apex_m=4236.0, s_start_m=4164.0, s_end_m=4260.0, radius_m=31.4,  dir="right", heading_change_deg=-117.4),
    dict(id=15, s_apex_m=5164.0, s_start_m=5104.0, s_end_m=5220.0, radius_m=31.2,  dir="left",  heading_change_deg=165.2),
]

# Corner character notes that are stable, widely-reported Sepang facts.
TURN_NOTES = {
    1: "Hard braking from ~330 kph into a wide right hairpin: the primary overtaking spot",
    2: "Tight left immediately on the Turn 1 exit; completes the double-apex turnaround",
    3: "Long fast right onto the run down the outside of the south loop",
    4: "Slow right, hardest single braking event after Turn 1",
    9: "Tightest corner on the lap; heavy lock-up risk and very low grip when wet",
    11: "Sustained right that loads the left-front hardest of any corner here",
    13: "Long right sweeper feeding the final complex",
    14: "Right-hander opening onto the back straight and DRS zone 2",
    15: "The final hairpin between the twin grandstand straights",
}


def classify_turn(radius_m, heading_change_deg):
    a = abs(heading_change_deg)
    if radius_m < 40.0 and a > 140.0:
        return "hairpin"
    if radius_m < 40.0:
        return "slow corner"
    if radius_m < 90.0:
        return "medium corner"
    if radius_m < 200.0:
        return "fast sweeper"
    return "kink"


# --------------------------------------------------------------------------
# elevation
# --------------------------------------------------------------------------
def load_elevation_cache():
    if os.path.exists(ELEV_CACHE):
        with open(ELEV_CACHE, "r", encoding="utf-8") as fh:
            return json.load(fh)
    return None


def elevation_for(latlons, cache=None):
    """Return elevation (m) per lat/lon using the cached SRTM query."""
    cache = cache or load_elevation_cache()
    if not cache:
        return None
    pts = cache["points"]  # [[lat, lon, elev], ...] along the same loop order
    if len(pts) < 4:
        return None
    # cache is sampled every `stride` centreline points; interpolate by index
    stride = cache["stride"]
    n = len(latlons)
    out = []
    for i in range(n):
        f = i / stride
        i0 = int(math.floor(f)) % len(pts)
        i1 = (i0 + 1) % len(pts)
        t = f - math.floor(f)
        out.append(pts[i0][2] * (1 - t) + pts[i1][2] * t)
    return out


def smooth_closed_scalar(vals, sigma_samples):
    if sigma_samples <= 0:
        return list(vals)
    radius = max(1, int(math.ceil(sigma_samples * 3)))
    kernel = [math.exp(-0.5 * (d / sigma_samples) ** 2) for d in range(-radius, radius + 1)]
    ks = sum(kernel)
    kernel = [k / ks for k in kernel]
    n = len(vals)
    return [sum(vals[(i + j - radius) % n] * k for j, k in enumerate(kernel))
            for i in range(n)]


# --------------------------------------------------------------------------
# main build
# --------------------------------------------------------------------------
def build_centreline(spacing=SAMPLE_SPACING_M, use_cache=True, write_cache=True):
    if use_cache and os.path.exists(CENTRELINE_CACHE):
        with open(CENTRELINE_CACHE, "r", encoding="utf-8") as fh:
            return json.load(fh)

    osm = load_osm()
    table = ways_by_id(osm)
    nodes, latlon, closed = chain_ways(CIRCUIT_WAYS, table)
    if not closed:
        raise ValueError("GP loop is not closed")
    _, pit_latlon, _ = chain_ways(PITLANE_WAYS, table)

    lat0 = sum(p[0] for p in latlon) / len(latlon)
    lon0 = sum(p[1] for p in latlon) / len(latlon)
    to_xy = projector(lat0, lon0)
    raw = [to_xy(la, lo) for la, lo in latlon]
    raw_len = polyline_length(raw, True)

    pre = resample_closed(raw, spacing * 0.5)
    pre = gaussian_smooth_closed(pre, sigma_samples=3.0)   # ~6 m sigma
    pre = resample_closed(pre, spacing)

    # single similarity transform (recentre + uniform scale to homologated length)
    cx = sum(p[0] for p in pre) / len(pre)
    cy = sum(p[1] for p in pre) / len(pre)
    scale = OFFICIAL_LENGTH_M / polyline_length(pre, True)

    def xform(p):
        return ((p[0] - cx) * scale, (p[1] - cy) * scale)

    pts = [xform(p) for p in pre]
    # OSM puts vertices hundreds of metres apart on straights, so densify the
    # pit lane before any nearest-distance query.
    pit = resample_open([xform(to_xy(la, lo)) for la, lo in pit_latlon], 5.0)
    n = len(pts)

    curv_s = smooth_closed_scalar(signed_curvature(pts), 2.0)

    # --- orient so the lap runs in the real racing direction --------------
    # Sepang is clockwise, so the net signed curvature over a lap is -360 deg.
    if sum(curv_s) > 0:
        pts = list(reversed(pts))
        curv_s = smooth_closed_scalar(signed_curvature(pts), 2.0)

    straights = find_straights(curv_s, spacing)

    # --- which long straight is the pit straight? -------------------------
    # Ground truth: the pit lane runs alongside the main straight (~20 m off
    # it at Sepang) and nowhere near the back straight. No guessing needed.
    def dist_to_pit(i):
        x, y = pts[i]
        return min(math.hypot(x - px, y - py) for px, py in pit)

    long2 = straights[:2]
    for st in long2:
        mid = (st["i_start"] + int((st["i_end"] - st["i_start"]) % n / 2)) % n
        probes = [(mid + d) % n for d in range(-30, 31, 10)]
        st["pit_offset_m"] = sum(dist_to_pit(i) for i in probes) / len(probes)
    main = min(long2, key=lambda s: s["pit_offset_m"])
    back = [s for s in long2 if s is not main][0]

    # Start/finish: on the pit straight, downstream of the Turn 15 hairpin exit.
    sf_index = int(main["i_start"] + SF_AFTER_T15_EXIT_M / spacing) % n

    pts = rotate(pts, sf_index)
    pit = pit  # unchanged: absolute coords
    curv_s = smooth_closed_scalar(signed_curvature(pts), 2.0)
    straights = find_straights(curv_s, spacing)

    # --- corners: the 15 FIA-numbered turns, from the verified table -------
    corners = []
    for ref in VERIFIED_TURNS:
        a = int(round(ref["s_apex_m"] / spacing)) % n
        i0 = int(round(ref["s_start_m"] / spacing)) % n
        i1 = int(round(ref["s_end_m"] / spacing)) % n
        kappa = curv_s[a]
        corners.append({
            "id": ref["id"],
            "name": "Turn %d" % ref["id"],
            "i_start": i0, "i_apex": a, "i_end": i1,
            "s_apex_m": ref["s_apex_m"],
            "length_m": ((i1 - i0) % n) * spacing,
            "kappa": kappa,
            "radius_m": ref["radius_m"],
            "dir": ref["dir"],
            "heading_change_deg": ref["heading_change_deg"],
            "kind": "%s %s" % (classify_turn(ref["radius_m"], ref["heading_change_deg"]),
                               ref["dir"]),
            "note": TURN_NOTES.get(ref["id"], ""),
        })
    corners.sort(key=lambda c: c["i_apex"])

    # --- elevation --------------------------------------------------------
    inv = 1.0 / scale
    k = math.cos(math.radians(lat0))
    latlons = []
    for x, y in pts:
        lo = lon0 + math.degrees((x * inv + cx) / (EARTH_R * k))
        la = lat0 + math.degrees((y * inv + cy) / EARTH_R)
        latlons.append((la, lo))
    elev = elevation_for(latlons)
    if elev:
        elev = smooth_closed_scalar(elev, 6.0)
        base = min(elev)
        elev = [e - base for e in elev]
    else:
        elev = [0.0] * n

    # --- DRS zones (Sepang runs two: pit straight and back straight) ------
    drs = []
    for label, st in (("DRS 1 (pit straight)", main), ("DRS 2 (back straight)", back)):
        i_start = (st["i_start"] - sf_index) % n
        i_end = (st["i_end"] - sf_index) % n
        drs.append({
            "name": label,
            "i_detect": (i_start - int(120 / spacing)) % n,
            "i_start": (i_start + int(60 / spacing)) % n,
            "i_end": i_end,
            "length_m": st["length_m"],
        })
    drs.sort(key=lambda d: d["i_start"])

    # --- timing sectors (published Sepang split lengths) -------------------
    sectors = []
    acc = 0.0
    for sid, seg_len in ((1, 1480.0), (2, 2210.0), (3, OFFICIAL_LENGTH_M - 1480.0 - 2210.0)):
        start = acc
        acc += seg_len
        sectors.append({"id": sid, "start_m": start, "end_m": acc,
                        "turns": [c["id"] for c in corners
                                  if "id" in c and start <= c["s_apex_m"] < acc]})

    data = {
        "spacing_m": spacing,
        "n": n,
        "length_m": polyline_length(pts, True),
        "raw_osm_length_m": raw_len,
        "scale_applied": scale,
        "track_width_m": TRACK_WIDTH_M,
        "origin_latlon": [lat0, lon0],
        "points": [[round(p[0], 4), round(p[1], 4)] for p in pts],
        "pit_lane": [[round(p[0], 4), round(p[1], 4)] for p in pit],
        "pit_offset_m": main["pit_offset_m"],
        "elevation_m": [round(e, 4) for e in elev],
        "curvature": [round(c, 7) for c in curv_s],
        "latlon": [[round(a, 7), round(b, 7)] for a, b in latlons],
        "corners": corners,
        "straights": [{k2: v2 for k2, v2 in s.items()} for s in straights[:6]],
        "main_straight_m": main["length_m"],
        "back_straight_m": back["length_m"],
        "drs_zones": drs,
        "sectors": sectors,
        "source": "OpenStreetMap raceway ways %s (ODbL); elevation SRTM 30 m via opentopodata" % CIRCUIT_WAYS,
    }
    if write_cache:
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(CENTRELINE_CACHE, "w", encoding="utf-8") as fh:
            json.dump(data, fh)
    return data


def summary(data=None):
    d = data or build_centreline()
    lines = []
    lines.append("Sepang GP layout from OSM survey")
    lines.append("  raw OSM loop length : %.1f m" % d["raw_osm_length_m"])
    lines.append("  homologated length  : %.1f m" % OFFICIAL_LENGTH_M)
    lines.append("  scale correction    : %.5f (%.2f%%)" % (d["scale_applied"], (d["scale_applied"] - 1) * 100))
    lines.append("  samples             : %d @ %.1f m" % (d["n"], d["spacing_m"]))
    lines.append("  elevation range     : %.1f m" % (max(d["elevation_m"]) - min(d["elevation_m"])))
    lines.append("  pit straight offset : %.1f m from pit lane" % d.get("pit_offset_m", -1))
    lines.append("  pit straight        : %.0f m   back straight: %.0f m" % (
        d.get("main_straight_m", 0), d.get("back_straight_m", 0)))
    lines.append("  corners detected    : %d" % len(d["corners"]))
    for c in d["corners"]:
        lines.append("    %-8s %-26s R=%6.1fm %6.1fdeg %-5s len=%4.0fm  s=%5.0fm" % (
            c.get("name", "?"), c.get("kind", ""), c["radius_m"], c["heading_change_deg"],
            c["dir"], c["length_m"], c["s_apex_m"]))
    for s in d["straights"][:3]:
        lines.append("  straight %5.0f m" % s["length_m"])
    for z in d["drs_zones"]:
        lines.append("  %s: %.0f m (s=%.0f..%.0f)" % (
            z["name"], z["length_m"], z["i_start"] * d["spacing_m"], z["i_end"] * d["spacing_m"]))
    for s in d.get("sectors", []):
        lines.append("  sector %d: %.0f-%.0f m turns %s" % (
            s["id"], s["start_m"], s["end_m"], s["turns"]))
    return "\n".join(lines)

"""
Circuit architecture: the twin grandstand that sits between Sepang's two long
straights (with its two tensile canopies), the pit building, the start/finish
gantry and satellite grandstands at Turn 1 and Turn 15.

Everything is swept along the real centreline, so the buildings land where the
survey says they should rather than at hand-placed coordinates.
"""

import math

import bpy

from . import bmat, geo
from .blender_util import (box, clear_collection, cylinder, get_collection,
                           make_mesh, smooth_closed)
from .build_track import (KERB_W, RUNOFF_W, TRACK_HALF, VERGE_W, ELEV_SIGMA_M,
                          frames, pit_side)

COLLECTION = "Sepang_Structures"
BARRIER_OFFSET = TRACK_HALF + KERB_W + RUNOFF_W + VERGE_W + 1.5


def sweep(name, stations, section, mats, mat_keys, col, close_ends=True):
    """
    Sweep a cross-section along station frames.

    stations: [(ox, oy, oz, ax, ay)] origin + unit "across" direction
    section:  [(across_offset, height)] in metres, ordered
    mat_keys: material key per band (len = len(section) - 1)
    """
    uniq = []
    for k in mat_keys:
        if k not in uniq:
            uniq.append(k)
    mat_list = [mats[k] for k in uniq]
    mi = {k: i for i, k in enumerate(uniq)}

    verts, faces, idx, uvs = [], [], [], []
    callable_section = callable(section)
    probe = section(0, len(stations)) if callable_section else section
    cols = len(probe)
    for si, (ox, oy, oz, ax, ay) in enumerate(stations):
        sec = section(si, len(stations)) if callable_section else section
        for (t, h) in sec:
            verts.append((ox + ax * t, oy + ay * t, oz + h))
    section = probe
    for i in range(len(stations) - 1):
        a = i * cols
        b = (i + 1) * cols
        for c in range(cols - 1):
            faces.append((a + c, b + c, b + c + 1, a + c + 1))
            idx.append(mi[mat_keys[c]])
            uvs.append([(i * 4.0, section[c][1]), ((i + 1) * 4.0, section[c][1]),
                        ((i + 1) * 4.0, section[c + 1][1]), (i * 4.0, section[c + 1][1])])
    if close_ends and len(stations) > 1:
        for end, a in ((0, 0), (1, (len(stations) - 1) * cols)):
            ring = [a + c for c in range(cols)]
            faces.append(tuple(ring if end == 0 else ring[::-1]))
            idx.append(0)
            uvs.append([(0.0, 0.0)] * cols)
    return make_mesh(name, verts, faces, col, mat_list, idx, uvs)


def station_frames(data, indices, side, offset, elev):
    """Frames offset laterally from the centreline; `across` points outward."""
    pts = data["points"]
    tan, nor = frames(pts)
    out = []
    for i in indices:
        px, py = pts[i]
        nx, ny = nor[i]
        ox = px + nx * side * offset
        oy = py + ny * side * offset
        out.append((ox, oy, elev[i], nx * side, ny * side))
    return out


def straight_ranges(data):
    """Index ranges of the pit straight and back straight, in racing order."""
    n = data["n"]
    sp = data["spacing_m"]
    # pit straight brackets the start/finish line at index 0
    main_len = data["main_straight_m"]
    back_len = data["back_straight_m"]
    from .geo import SF_AFTER_T15_EXIT_M
    pit_start = int(-SF_AFTER_T15_EXIT_M / sp) % n
    pit_count = int(main_len / sp)
    pit = [(pit_start + d) % n for d in range(pit_count)]

    z = sorted(data["drs_zones"], key=lambda d2: -d2["length_m"])
    back_zone = None
    for zz in data["drs_zones"]:
        if "back" in zz["name"]:
            back_zone = zz
    b0 = back_zone["i_start"] - int(60 / sp)
    back = [(b0 + d) % n for d in range(int(back_len / sp))]
    return pit, back


def build_twin_grandstand(data, mats, col):
    """
    Sepang's landmark: one grandstand block between the two straights, seating
    facing outwards on both sides, under two curved tensile canopies.
    """
    n = data["n"]
    sp = data["spacing_m"]
    pts = data["points"]
    elev = smooth_closed(data["elevation_m"], ELEV_SIGMA_M / sp)
    tan, nor = frames(pts)
    pit_idx, back_idx = straight_ranges(data)
    ps = pit_side(data)
    inner = -ps                      # the straights face each other on this side

    # for each pit-straight station find the matching back-straight station
    stations, widths = [], []
    for i in pit_idx:
        px, py = pts[i]
        nx, ny = nor[i]
        best = None
        for j in back_idx:
            qx, qy = pts[j]
            d = math.hypot(qx - px, qy - py)
            if best is None or d < best[0]:
                best = (d, j)
        gap, j = best
        avail = gap - 2.0 * BARRIER_OFFSET
        if avail < 24.0:
            widths.append(None)
            continue
        qx, qy = pts[j]
        mx, my = (px + qx) * 0.5, (py + qy) * 0.5
        stations.append((mx, my, (elev[i] + elev[j]) * 0.5,
                         nx * inner, ny * inner))
        widths.append(min(avail, 62.0))

    widths = [w for w in widths if w is not None]
    if len(stations) < 12:
        return []
    # trim to a continuous run and use one representative width
    half = min(widths) * 0.5
    half = max(12.0, min(half, 21.0))

    steps = 9
    rise, tread = 0.95, 1.5
    section = [(-half, 0.0)]
    for k in range(steps):
        section.append((-half + k * tread, k * rise))
        section.append((-half + (k + 1) * tread, k * rise))
    top_y = steps * rise
    section.append((-half + steps * tread, top_y))
    section.append((half - steps * tread, top_y))
    for k in range(steps - 1, -1, -1):
        section.append((half - (k + 1) * tread, k * rise))
        section.append((half - k * tread, k * rise))
    section.append((half, 0.0))
    keys = []
    for c in range(len(section) - 1):
        rising = section[c + 1][1] != section[c][1]
        keys.append("grandstand" if rising else "seats")

    made = [sweep("SEP_GrandstandTwin", stations, section, mats, keys, col)]

    # Two tensile canopies over the seating banks. Sepang's roofs are sails,
    # not tubes: they taper towards both ends and peak over the seating.
    span = len(stations)
    segs = 14
    over = 4.5

    def canopy_section(si, count):
        u = si / max(1, count - 1)
        taper = math.sin(math.pi * min(1.0, max(0.0, u))) ** 0.55
        sec = []
        for k in range(segs + 1):
            f = k / segs
            t = -half - over + f * (2.0 * (half + over))
            lift = math.sin(math.pi * f) ** 0.85
            h = top_y + 3.0 + (1.5 + 11.0 * lift) * taper
            sec.append((t, h))
        return sec

    keys_roof = ["roof_petronas"] + ["roof"] * (segs - 2) + ["roof_petronas"]
    for ci, (lo, hi) in enumerate(((3, span // 2 - 9), (span // 2 + 9, span - 4))):
        if hi - lo < 8:
            continue
        canopy_st = stations[lo:hi]
        made.append(sweep("SEP_Canopy%d" % (ci + 1), canopy_st, canopy_section,
                          mats, keys_roof, col, close_ends=False))
        for k in range(lo + 3, hi - 2, 9):
            ox, oy, oz, ax, ay = stations[k]
            u = (k - lo) / max(1, hi - lo - 1)
            taper = math.sin(math.pi * u) ** 0.30
            ph = top_y + 4.0 + 2.5 * taper
            for t in (-half - over + 1.5, half + over - 1.5):
                cylinder("SEP_CanopyPost", 0.40, ph,
                         (ox + ax * t, oy + ay * t, oz + ph / 2),
                         col, mats["gantry"], segments=10)
    return made


def build_pit_building(data, mats, col):
    """Garage row + upper hospitality deck alongside the pit lane."""
    lane = data["pit_lane"]
    if len(lane) < 8:
        return []
    sp = data["spacing_m"]
    pts = data["points"]
    elev = smooth_closed(data["elevation_m"], ELEV_SIGMA_M / sp)

    def nearest_elev(x, y):
        best, bz = None, 0.0
        for i, (px, py) in enumerate(pts):
            d = (px - x) ** 2 + (py - y) ** 2
            if best is None or d < best:
                best, bz = d, elev[i]
        return bz

    ps = pit_side(data)
    m = len(lane)
    step = max(1, m // 90)
    stations = []
    for i in range(0, m, step):
        a = lane[max(0, i - 1)]
        b = lane[min(m - 1, i + 1)]
        dx, dy = b[0] - a[0], b[1] - a[1]
        L = math.hypot(dx, dy) or 1.0
        nx, ny = -dy / L, dx / L
        # push away from the track: the pit lane's far side
        ax, ay = nx * ps, ny * ps
        ox, oy = lane[i][0] + ax * 9.0, lane[i][1] + ay * 9.0
        stations.append((ox, oy, nearest_elev(ox, oy), ax, ay))
    if len(stations) < 6:
        return []
    made = []
    garage = [(0.0, 0.0), (0.0, 6.6), (16.0, 7.4), (16.0, 0.0)]
    made.append(sweep("SEP_PitGarages", stations, garage, mats,
                      ["glass", "pit_building", "pit_building"], col))
    upper = [(1.5, 7.4), (1.5, 13.4), (14.0, 13.9), (14.0, 7.4)]
    made.append(sweep("SEP_PitUpper", stations, upper, mats,
                      ["glass", "roof", "pit_building"], col))
    return made


def build_gantry(data, mats, col):
    """Start/finish gantry with light panels over the grid."""
    n = data["n"]
    sp = data["spacing_m"]
    pts = data["points"]
    elev = smooth_closed(data["elevation_m"], ELEV_SIGMA_M / sp)
    tan, nor = frames(pts)
    i = 0
    px, py = pts[i]
    nx, ny = nor[i]
    tx, ty = tan[i]
    z = elev[i]
    ang = math.atan2(ty, tx)
    made = []
    post_h = 9.5
    for side in (-1.0, 1.0):
        t = side * (TRACK_HALF + 1.2)
        made.append(box("SEP_GantryPost", (1.1, 1.1, post_h),
                        (px + nx * t, py + ny * t, z + post_h / 2), col,
                        mats["gantry"], rotation_z=ang))
    span = 2.0 * (TRACK_HALF + 1.2)
    made.append(box("SEP_GantryBeam", (span, 1.6, 1.5),
                    (px, py, z + post_h + 0.75), col, mats["gantry"],
                    rotation_z=ang + math.pi / 2))
    for k in range(-2, 3):
        t = k * 3.0
        made.append(box("SEP_StartLight", (1.5, 0.5, 1.1),
                        (px + nx * t, py + ny * t, z + post_h - 0.4), col,
                        mats["led"], rotation_z=ang + math.pi / 2))
    return made


def build_side_grandstand(data, mats, col, s_centre, length_m, name, side=None):
    """Smaller grandstand on the outside of a corner."""
    n = data["n"]
    sp = data["spacing_m"]
    pts = data["points"]
    curv = data["curvature"]
    elev = smooth_closed(data["elevation_m"], ELEV_SIGMA_M / sp)
    i0 = int(s_centre / sp) % n
    if side is None:
        side = 1.0 if curv[i0] < 0 else -1.0      # outside of the corner
    count = int(length_m / sp)
    idx = [(i0 - count // 2 + d) % n for d in range(count)]
    stations = station_frames(data, idx, side, BARRIER_OFFSET + 3.0, elev)
    steps = 8
    rise, tread = 0.9, 1.45
    section = [(0.0, 0.0)]
    for k in range(steps):
        section.append((k * tread, k * rise))
        section.append(((k + 1) * tread, k * rise))
    section.append((steps * tread + 2.0, steps * rise))
    keys = []
    for c in range(len(section) - 1):
        rising = section[c + 1][1] != section[c][1]
        keys.append("grandstand" if rising else "seats")
    return [sweep(name, stations, section, mats, keys, col)]


def build(data=None, mats=None):
    data = data or geo.build_centreline()
    mats = mats or bmat.build_all()
    if "seats" not in mats:
        mats["seats"] = bmat.simple("SEP_Seats", (0.10, 0.13, 0.20), 0.7)
    clear_collection(COLLECTION)
    col = get_collection(COLLECTION)

    made = []
    made += build_twin_grandstand(data, mats, col)
    made += build_pit_building(data, mats, col)
    made += build_gantry(data, mats, col)
    made += build_side_grandstand(data, mats, col, 640.0, 320.0, "SEP_GrandstandT1")
    made += build_side_grandstand(data, mats, col, 5164.0, 240.0, "SEP_GrandstandT15")
    made += build_side_grandstand(data, mats, col, 3172.0, 200.0, "SEP_GrandstandT9")

    made = [m for m in made if m]
    tris = sum(len(o.data.polygons) for o in made if o.type == 'MESH')
    return made, ["structures: %d objects / %d faces" % (len(made), tris)]


if __name__ == "__main__":
    _, rep = build()
    print("\n".join(rep))

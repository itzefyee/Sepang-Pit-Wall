"""
Builds the Sepang International Circuit surface in Blender from the verified
centreline: asphalt, kerbs, run-off, verges, painted lines, barriers, the pit
lane and the surrounding graded terrain.

1 Blender unit = 1 metre. World origin = the start/finish line.
"""

import math

import bpy

from . import bmat, geo
from .blender_util import (clear_collection, get_collection, make_mesh,
                           smooth_closed)

COLLECTION = "Sepang_Track"

TRACK_HALF = 8.0          # 16 m racing surface
KERB_W = 1.6
RUNOFF_W = 11.0
VERGE_W = 10.0
KERB_RISE = 0.11
LINE_W = 0.20

ELEV_SIGMA_M = 100.0      # SRTM is noisy and picks up grandstand roofs
OFF_CAMBER_TURNS = {9}    # Turn 9 is famously off-camber


def frames(pts):
    """Unit tangent and left-hand normal for a closed polyline."""
    n = len(pts)
    tan, nor = [], []
    for i in range(n):
        ax, ay = pts[(i - 1) % n]
        bx, by = pts[(i + 1) % n]
        dx, dy = bx - ax, by - ay
        L = math.hypot(dx, dy) or 1.0
        tx, ty = dx / L, dy / L
        tan.append((tx, ty))
        nor.append((-ty, tx))          # +normal = left of travel
    return tan, nor


def corner_mask(data):
    """True where the surface should get a painted kerb (in a corner)."""
    n = data["n"]
    sp = data["spacing_m"]
    mask = [False] * n
    for c in data["corners"]:
        i0 = c["i_start"]
        i1 = c["i_end"]
        pad = int(round(25.0 / sp))
        span = (i1 - i0) % n
        for d in range(-pad, span + pad + 1):
            mask[(i0 + d) % n] = True
    return mask


def camber(data):
    """Cross-slope per sample: drainage crown on straights, banked in corners."""
    n = data["n"]
    curv = data["curvature"]
    turn_of = {}
    for c in data["corners"]:
        span = (c["i_end"] - c["i_start"]) % n
        for d in range(span + 1):
            turn_of[(c["i_start"] + d) % n] = c["id"]
    out = []
    for i in range(n):
        k = curv[i]
        bank = min(0.048, abs(k) * 2.6)            # up to ~2.7 deg of banking
        if turn_of.get(i) in OFF_CAMBER_TURNS:
            bank = -0.024
        sign = -1.0 if k < 0 else 1.0              # k<0 = right-hander
        out.append((-sign * bank, 0.016))          # (bank slope, crown slope)
    return smooth_closed([o[0] for o in out], 4.0), [o[1] for o in out]


def surface_profile(bank, crown, kerbed):
    """
    Cross-section as (t_offset, dz, band_material_key_for_band_that_starts_here).
    Bands run left (-t) to right (+t) in the returned order.
    """
    k_out = TRACK_HALF + KERB_W
    r_out = k_out + RUNOFF_W
    v_out = r_out + VERGE_W

    def track_dz(t):
        return bank * t - crown * abs(t)

    kerb_dz_in = track_dz(TRACK_HALF)
    kerb_dz_out = kerb_dz_in + (KERB_RISE if kerbed else 0.0)
    run_dz = kerb_dz_out - 0.02 - RUNOFF_W * 0.015
    verge_dz = run_dz - 0.28 - VERGE_W * 0.05

    left = [(-v_out, verge_dz), (-r_out, run_dz), (-k_out, kerb_dz_out),
            (-TRACK_HALF, track_dz(-TRACK_HALF))]
    mid = [(0.0, track_dz(0.0))]
    right = [(TRACK_HALF, track_dz(TRACK_HALF)), (k_out, kerb_dz_out),
             (r_out, run_dz), (v_out, verge_dz)]
    return left + mid + right


BAND_KEYS = ["grass", "runoff", "kerb", "asphalt", "asphalt", "kerb", "runoff", "grass"]


def build_surface(data, mats, col):
    n = data["n"]
    sp = data["spacing_m"]
    pts = data["points"]
    elev = smooth_closed(data["elevation_m"], ELEV_SIGMA_M / sp)
    tan, nor = frames(pts)
    bank, crown = camber(data)
    kerbed = corner_mask(data)

    verts = []
    for i in range(n):
        px, py = pts[i]
        nx, ny = nor[i]
        prof = surface_profile(bank[i], crown[i], kerbed[i])
        for t, dz in prof:
            verts.append((px + nx * t, py + ny * t, elev[i] + dz))

    ncols = 9
    order = ["grass", "runoff", "kerb", "asphalt", "line", "wall"]
    uniq = ["asphalt", "runoff", "kerb", "grass"]
    mat_list = [mats[k] for k in uniq]
    mi_of = {k: i for i, k in enumerate(uniq)}

    faces, mat_indices, face_uvs = [], [], []
    for i in range(n):
        j0 = i * ncols
        j1 = ((i + 1) % n) * ncols
        prof_a = surface_profile(bank[i], crown[i], kerbed[i])
        for b in range(ncols - 1):
            faces.append((j0 + b, j1 + b, j1 + b + 1, j0 + b + 1))
            key = BAND_KEYS[b]
            if key == "kerb" and not kerbed[i]:
                key = "runoff"
            mat_indices.append(mi_of[key])
            u0, u1 = i * sp, (i + 1) * sp
            t0 = prof_a[b][0]
            t1 = prof_a[b + 1][0]
            face_uvs.append([(u0, t0), (u1, t0), (u1, t1), (u0, t1)])

    return make_mesh("SEP_Surface", verts, faces, col, mat_list, mat_indices, face_uvs)


def build_painted_lines(data, mats, col):
    """White track-edge lines plus the start/finish line."""
    n = data["n"]
    sp = data["spacing_m"]
    pts = data["points"]
    elev = smooth_closed(data["elevation_m"], ELEV_SIGMA_M / sp)
    tan, nor = frames(pts)
    bank, crown = camber(data)

    def z_at(i, t):
        return elev[i] + bank[i] * t - crown[i] * abs(t) + 0.012

    verts, faces, uvs = [], [], []
    for side in (-1.0, 1.0):
        base = len(verts)
        t_in = side * (TRACK_HALF - LINE_W)
        t_out = side * TRACK_HALF
        for i in range(n):
            px, py = pts[i]
            nx, ny = nor[i]
            verts.append((px + nx * t_in, py + ny * t_in, z_at(i, t_in)))
            verts.append((px + nx * t_out, py + ny * t_out, z_at(i, t_out)))
        for i in range(n):
            a = base + i * 2
            b = base + ((i + 1) % n) * 2
            faces.append((a, b, b + 1, a + 1))
            uvs.append([(i * sp, 0.0), ((i + 1) * sp, 0.0),
                        ((i + 1) * sp, 1.0), (i * sp, 1.0)])

    # start/finish line: 0.5 m wide band across the full track width
    base = len(verts)
    width_i = max(1, int(round(0.5 / sp)))
    for k in (0, width_i):
        i = k % n
        px, py = pts[i]
        nx, ny = nor[i]
        for t in (-TRACK_HALF, TRACK_HALF):
            verts.append((px + nx * t, py + ny * t, z_at(i, t) + 0.004))
    faces.append((base, base + 2, base + 3, base + 1))
    uvs.append([(0, 0), (1, 0), (1, 1), (0, 1)])

    return make_mesh("SEP_Lines", verts, faces, col, [mats["line"]],
                     [0] * len(faces), uvs)


def barrier_mask(data, side):
    """
    Where a barrier belongs on one side of the track.

    Real circuits wall the OUTSIDE of corners and both sides of straights, and
    leave corner infields open - otherwise the walls of a hairpin close up in
    the middle of its own infield.
    """
    n = data["n"]
    sp = data["spacing_m"]
    curv = data["curvature"]
    straight_k = 1.0 / 500.0
    need = []
    for i in range(n):
        k = curv[i]
        outside = (side > 0 and k < 0) or (side < 0 and k > 0)
        need.append(outside or abs(k) < straight_k)
    # grow by 45 m so barriers run past corner entries/exits
    pad = int(round(45.0 / sp))
    grown = [False] * n
    for i in range(n):
        if need[i]:
            for d in range(-pad, pad + 1):
                grown[(i + d) % n] = True
    # drop runs shorter than 70 m
    out = list(grown)
    i = 0
    while i < n:
        if grown[i]:
            j = i
            while j < n and grown[j]:
                j += 1
            if (j - i) * sp < 70.0:
                for k2 in range(i, j):
                    out[k2] = False
            i = j
        else:
            i += 1
    return out


def build_barriers(data, mats, col):
    """Concrete wall + catch fence set back behind the verge."""
    n = data["n"]
    sp = data["spacing_m"]
    pts = data["points"]
    elev = smooth_closed(data["elevation_m"], ELEV_SIGMA_M / sp)
    tan, nor = frames(pts)
    offset = TRACK_HALF + KERB_W + RUNOFF_W + VERGE_W + 1.5
    wall_h, fence_h = 1.15, 2.7

    verts, faces, mat_idx, uvs = [], [], [], []
    for side in (-1.0, 1.0):
        mask = barrier_mask(data, side)
        t = side * offset
        for is_fence in (False, True):
            z0 = 0.0 if not is_fence else wall_h
            z1 = wall_h if not is_fence else wall_h + fence_h
            for i in range(n):
                j = (i + 1) % n
                if not (mask[i] and mask[j]):
                    continue
                base = len(verts)
                for idx in (i, j):
                    px, py = pts[idx]
                    nx, ny = nor[idx]
                    g = elev[idx] - 0.45
                    verts.append((px + nx * t, py + ny * t, g + z0))
                    verts.append((px + nx * t, py + ny * t, g + z1))
                faces.append((base, base + 2, base + 3, base + 1))
                mat_idx.append(1 if is_fence else 0)
                uvs.append([(i * sp, z0), ((i + 1) * sp, z0),
                            ((i + 1) * sp, z1), (i * sp, z1)])
    return make_mesh("SEP_Barriers", verts, faces, col,
                     [mats["wall"], mats["fence"]], mat_idx, uvs)


def pit_side(data):
    """Which side of the pit straight the pit lane sits on (+1 left, -1 right)."""
    pts = data["points"]
    tan, nor = frames(pts)
    px, py = pts[0]
    nx, ny = nor[0]
    best = None
    for qx, qy in data["pit_lane"]:
        d = math.hypot(qx - px, qy - py)
        if best is None or d < best[0]:
            best = (d, (qx - px) * nx + (qy - py) * ny)
    return 1.0 if best[1] > 0 else -1.0


def build_pit_lane(data, mats, col):
    """Pit lane ribbon + garage apron, elevation matched to the adjacent track."""
    lane = data["pit_lane"]
    if len(lane) < 4:
        return None
    pts = data["points"]
    sp = data["spacing_m"]
    elev = smooth_closed(data["elevation_m"], ELEV_SIGMA_M / sp)

    def nearest_elev(x, y):
        best, bz = None, 0.0
        for i, (px, py) in enumerate(pts):
            d = (px - x) ** 2 + (py - y) ** 2
            if best is None or d < best:
                best, bz = d, elev[i]
        return bz

    m = len(lane)
    tanl, norl = [], []
    for i in range(m):
        a = lane[max(0, i - 1)]
        b = lane[min(m - 1, i + 1)]
        dx, dy = b[0] - a[0], b[1] - a[1]
        L = math.hypot(dx, dy) or 1.0
        tanl.append((dx / L, dy / L))
        norl.append((-dy / L, dx / L))

    half = 6.0
    apron = 13.0
    side = pit_side(data)
    verts, faces, mat_idx, uvs = [], [], [], []
    s_acc = [0.0]
    for i in range(1, m):
        s_acc.append(s_acc[-1] + math.hypot(lane[i][0] - lane[i - 1][0],
                                            lane[i][1] - lane[i - 1][1]))
    for i in range(m):
        px, py = lane[i]
        nx, ny = norl[i]
        z = nearest_elev(px, py) + 0.02
        for t in (-half, 0.0, half, half + apron if side > 0 else -(half + apron)):
            verts.append((px + nx * t, py + ny * t, z))
    cols = 4
    for i in range(m - 1):
        a = i * cols
        b = (i + 1) * cols
        for k in range(cols - 1):
            faces.append((a + k, b + k, b + k + 1, a + k + 1))
            mat_idx.append(0 if k < 2 else 1)
            uvs.append([(s_acc[i], 0), (s_acc[i + 1], 0),
                        (s_acc[i + 1], 1), (s_acc[i], 1)])
    return make_mesh("SEP_PitLane", verts, faces, col,
                     [mats["asphalt"], mats["runoff"]], mat_idx, uvs)


def build_backdrop(data, mats, col, half=6000.0, terrain_margin=900.0):
    """
    Ground beyond the graded terrain, so the horizon isn't a void.

    This is a RING, not a plane: a solid plane at the site's mean height would
    sit above every part of the circuit that runs below that height and hide it.
    The inner edge matches the graded terrain's outer edge exactly, so the seam
    is invisible.
    """
    import numpy as np
    pts = np.array(data["points"], dtype=np.float64)
    sp = data["spacing_m"]
    elev = np.array(smooth_closed(data["elevation_m"], ELEV_SIGMA_M / sp))
    base = float(np.median(elev)) - 1.2

    x0 = float(pts[:, 0].min()) - terrain_margin
    x1 = float(pts[:, 0].max()) + terrain_margin
    y0 = float(pts[:, 1].min()) - terrain_margin
    y1 = float(pts[:, 1].max()) + terrain_margin
    cx, cy = (x0 + x1) * 0.5, (y0 + y1) * 0.5
    ox0, ox1 = cx - half, cx + half
    oy0, oy1 = cy - half, cy + half

    verts = [(x0, y0, base), (x1, y0, base), (x1, y1, base), (x0, y1, base),
             (ox0, oy0, base), (ox1, oy0, base), (ox1, oy1, base), (ox0, oy1, base)]
    faces = [(4, 5, 1, 0), (5, 6, 2, 1), (6, 7, 3, 2), (7, 4, 0, 3)]
    uvs = [[(verts[i][0], verts[i][1]) for i in f] for f in faces]
    return make_mesh("SEP_Backdrop", verts, faces, col, [mats["grass"]],
                     [0] * len(faces), uvs)


def build_terrain(data, mats, col, cell=26.0, margin=900.0):
    """
    Graded ground plane. Height at each grid node is an inverse-distance blend
    of nearby centreline elevations, so the terrain hugs the circuit instead of
    the track floating over a flat slab.
    """
    import numpy as np

    pts = np.array(data["points"], dtype=np.float64)
    sp = data["spacing_m"]
    elev = np.array(smooth_closed(data["elevation_m"], ELEV_SIGMA_M / sp))

    x0, x1 = pts[:, 0].min() - margin, pts[:, 0].max() + margin
    y0, y1 = pts[:, 1].min() - margin, pts[:, 1].max() + margin
    nx = int((x1 - x0) / cell) + 1
    ny = int((y1 - y0) / cell) + 1
    gx = np.linspace(x0, x1, nx)
    gy = np.linspace(y0, y1, ny)

    base = float(np.median(elev))
    zz = np.empty((ny, nx), dtype=np.float64)
    for r in range(ny):
        dx = gx[:, None] - pts[None, :, 0]
        dy = gy[r] - pts[None, :, 1]
        d2 = dx * dx + dy * dy
        w = 1.0 / (d2 + 900.0) ** 2
        zz[r] = (w * elev[None, :]).sum(axis=1) / w.sum(axis=1)
        # fade to the site's mean height far from the circuit
        dmin = np.sqrt(d2.min(axis=1))
        f = np.clip((dmin - 120.0) / 260.0, 0.0, 1.0)
        zz[r] = zz[r] * (1.0 - f) + base * f
    zz -= 1.2   # sit just under the verge so the track reads as raised

    verts, faces, uvs = [], [], []
    for r in range(ny):
        for c in range(nx):
            verts.append((float(gx[c]), float(gy[r]), float(zz[r, c])))
    for r in range(ny - 1):
        for c in range(nx - 1):
            a = r * nx + c
            b = (r + 1) * nx + c
            faces.append((a, b, b + 1, a + 1))
            uvs.append([(gx[c], gy[r]), (gx[c], gy[r + 1]),
                        (gx[c + 1], gy[r + 1]), (gx[c + 1], gy[r])])
    return make_mesh("SEP_Terrain", verts, faces, col, [mats["grass"]],
                     [0] * len(faces), uvs)


def build(data=None, mats=None):
    data = data or geo.build_centreline()
    mats = mats or bmat.build_all()
    clear_collection(COLLECTION)
    col = get_collection(COLLECTION)

    made = {
        "backdrop": build_backdrop(data, mats, col),
        "terrain": build_terrain(data, mats, col),
        "surface": build_surface(data, mats, col),
        "lines": build_painted_lines(data, mats, col),
        "barriers": build_barriers(data, mats, col),
        "pit_lane": build_pit_lane(data, mats, col),
    }
    report = []
    for k, ob in made.items():
        if ob:
            report.append("%s: %d verts / %d faces" % (k, len(ob.data.vertices),
                                                       len(ob.data.polygons)))
    return made, report


if __name__ == "__main__":
    _, rep = build()
    print("\n".join(rep))

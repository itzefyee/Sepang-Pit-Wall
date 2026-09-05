"""
Parametric 2026-regulation Formula 1 car, built for the Scuderia Ferrari entries
at Sepang.

Local frame: +X forward, +Y left, +Z up, origin on the ground at the centre of
the wheelbase. Dimensions follow the 2026 chassis rules:
    wheelbase 3400 mm, overall width 1900 mm, body height 950 mm,
    18-inch rims, front tyre 355 mm wide / 715 mm dia,
    rear tyre 405 mm wide / 725 mm dia.

The tyre sidewall band is a separate object per car so the compound colour can be
re-assigned every stint straight from the race simulation.
"""

import math

import bpy

from . import bmat
from .blender_util import get_collection, clear_collection, make_mesh, join

COLLECTION = "Sepang_Cars"

WHEELBASE = 3.40
AXLE_F = WHEELBASE / 2.0
AXLE_R = -WHEELBASE / 2.0
HALF_WIDTH = 0.95
TYRE_F_W, TYRE_F_R = 0.355, 0.3575
TYRE_R_W, TYRE_R_R = 0.405, 0.3625
RIM_R = 0.4572 / 2.0
FLOOR_Z = 0.045

COMPOUND_COLOURS = {
    "soft": (0.75, 0.03, 0.03),
    "medium": (0.85, 0.68, 0.05),
    "hard": (0.88, 0.88, 0.88),
    "intermediate": (0.05, 0.55, 0.12),
    "wet": (0.03, 0.22, 0.75),
}


# --------------------------------------------------------------------------
# geometry helpers
# --------------------------------------------------------------------------
def rounded_rect(hw, z0, z1, r, per_corner=3):
    """Closed profile in (y, z), counter-clockwise, with rounded corners."""
    r = max(0.0, min(r, min(hw, (z1 - z0) / 2.0) * 0.95))
    pts = []
    cs = [(hw - r, z0 + r, -math.pi / 2, 0.0),
          (hw - r, z1 - r, 0.0, math.pi / 2),
          (-hw + r, z1 - r, math.pi / 2, math.pi),
          (-hw + r, z0 + r, math.pi, 1.5 * math.pi)]
    for (cy, cz, a0, a1) in cs:
        for k in range(per_corner + 1):
            a = a0 + (a1 - a0) * k / per_corner
            pts.append((cy + r * math.cos(a), cz + r * math.sin(a)))
    # drop duplicate seam points
    out = [pts[0]]
    for p in pts[1:]:
        if abs(p[0] - out[-1][0]) > 1e-6 or abs(p[1] - out[-1][1]) > 1e-6:
            out.append(p)
    return out


def loft(name, axis, sections, mat, col, cap=True, smooth=True):
    """
    Loft equal-length closed profiles.
    axis: 'X' | 'Y' | 'Z'; sections: [(along, [(a, b), ...])]
    For 'X' the profile pair is (y, z); 'Y' -> (x, z); 'Z' -> (x, y).
    """
    cols = len(sections[0][1])
    verts = []
    for along, prof in sections:
        assert len(prof) == cols, "profiles must have equal point counts"
        for (a, b) in prof:
            if axis == 'X':
                verts.append((along, a, b))
            elif axis == 'Y':
                verts.append((a, along, b))
            else:
                verts.append((a, b, along))
    faces = []
    for i in range(len(sections) - 1):
        s0 = i * cols
        s1 = (i + 1) * cols
        for c in range(cols):
            c2 = (c + 1) % cols
            faces.append((s0 + c, s1 + c, s1 + c2, s0 + c2))
    if cap:
        faces.append(tuple(range(cols))[::-1])
        base = (len(sections) - 1) * cols
        faces.append(tuple(base + c for c in range(cols)))
    return make_mesh(name, verts, faces, col, [mat], [0] * len(faces),
                     shade_smooth=smooth)


def revolve(name, profile, centre, axis, mat, col, segments=24, smooth=True,
            cap=True):
    """
    Revolve a profile of (axial_offset, radius) around an axis through `centre`.
    axis: 'X' | 'Y' | 'Z' -- the axle direction.

    cap=False leaves the ends open, which is what an annular band (a tyre
    sidewall marking) needs - capping it would fill the ring into a solid disc.
    """
    verts, faces = [], []
    m = len(profile)
    for k in range(segments):
        a = 2.0 * math.pi * k / segments
        ca, sa = math.cos(a), math.sin(a)
        for (off, rad) in profile:
            if axis == 'Y':
                v = (centre[0] + rad * ca, centre[1] + off, centre[2] + rad * sa)
            elif axis == 'X':
                v = (centre[0] + off, centre[1] + rad * ca, centre[2] + rad * sa)
            else:
                v = (centre[0] + rad * ca, centre[1] + rad * sa, centre[2] + off)
            verts.append(v)
    for k in range(segments):
        k2 = (k + 1) % segments
        for i in range(m - 1):
            faces.append((k * m + i, k2 * m + i, k2 * m + i + 1, k * m + i + 1))
    if cap:
        for i in (0, m - 1):
            ring = [k * m + i for k in range(segments)]
            faces.append(tuple(ring if i == 0 else ring[::-1]))
    return make_mesh(name, verts, faces, col, [mat], [0] * len(faces),
                     shade_smooth=smooth)


def tube(name, points, radius, mat, col, segments=8, smooth=True):
    """Round tube through a 3D polyline (halo, suspension, roll hoop)."""
    import mathutils
    verts, faces = [], []
    n = len(points)
    up = mathutils.Vector((0, 0, 1))
    for i, p in enumerate(points):
        p = mathutils.Vector(p)
        if i == 0:
            d = mathutils.Vector(points[1]) - p
        elif i == n - 1:
            d = p - mathutils.Vector(points[-2])
        else:
            d = mathutils.Vector(points[i + 1]) - mathutils.Vector(points[i - 1])
        d.normalize()
        ref = up if abs(d.dot(up)) < 0.95 else mathutils.Vector((1, 0, 0))
        u = d.cross(ref).normalized()
        v = d.cross(u).normalized()
        for k in range(segments):
            a = 2.0 * math.pi * k / segments
            verts.append(tuple(p + u * (radius * math.cos(a)) + v * (radius * math.sin(a))))
    for i in range(n - 1):
        for k in range(segments):
            k2 = (k + 1) % segments
            a = i * segments
            b = (i + 1) * segments
            faces.append((a + k, b + k, b + k2, a + k2))
    return make_mesh(name, verts, faces, col, [mat], [0] * len(faces),
                     shade_smooth=smooth)


def airfoil(chord, thick, camber=0.10, n=8):
    """Thin cambered aerofoil section as (x, z) offsets, closed loop."""
    top, bot = [], []
    for k in range(n + 1):
        f = k / n
        x = f * chord
        camb = camber * chord * math.sin(math.pi * f) ** 0.9
        t = thick * chord * math.sin(math.pi * max(f, 1e-4) ** 0.7)
        top.append((x, camb + t * 0.5))
        bot.append((x, camb - t * 0.5))
    return top + bot[::-1][1:-1]


def wing_element(name, x_le, z, half_span, chord, thick, aoa_deg, mat, col,
                 taper=0.85, camber=0.12, dihedral=0.0):
    """One wing plane, lofted spanwise with taper and a little tip rise."""
    sections = []
    stations = [-1.0, -0.6, -0.25, 0.0, 0.25, 0.6, 1.0]
    a = math.radians(aoa_deg)
    for f in stations:
        y = f * half_span
        sc = 1.0 - (1.0 - taper) * abs(f)
        prof = airfoil(chord * sc, thick, camber)
        zz = z + dihedral * abs(f)
        rot = []
        for (px, pz) in prof:
            cx = px - chord * 0.35
            rx = cx * math.cos(a) - pz * math.sin(a)
            rz = cx * math.sin(a) + pz * math.cos(a)
            rot.append((x_le + rx, zz + rz))
        sections.append((y, rot))
    return loft(name, 'Y', sections, mat, col, cap=True)


# --------------------------------------------------------------------------
# car materials
# --------------------------------------------------------------------------
def car_materials(livery):
    m = {}
    body = bmat.simple("CAR_%s_Body" % livery["tag"], livery["primary"], 0.22,
                       metallic=0.35)
    m["body"] = body
    m["dark"] = bmat.simple("CAR_%s_Dark" % livery["tag"], livery["secondary"],
                            0.42, metallic=0.2)
    m["carbon"] = bmat.simple("CAR_Carbon", (0.017, 0.018, 0.020), 0.35,
                              metallic=0.45)
    m["white"] = bmat.simple("CAR_White", (0.88, 0.88, 0.86), 0.30)
    m["rubber"] = bmat.simple("CAR_Rubber", (0.016, 0.016, 0.017), 0.80)
    m["rim"] = bmat.simple("CAR_Rim", (0.28, 0.29, 0.31), 0.30, metallic=0.9)
    m["metal"] = bmat.simple("CAR_Metal", (0.55, 0.56, 0.58), 0.28, metallic=1.0)
    m["visor"] = bmat.simple("CAR_Visor", (0.02, 0.02, 0.03), 0.08, metallic=0.7)
    m["helmet"] = bmat.simple("CAR_%s_Helmet" % livery["tag"],
                              livery["helmet"], 0.20, metallic=0.3)
    m["led"] = bmat.simple("CAR_Rearlight", (0.02, 0.0, 0.0), 0.3,
                           emission=(1.0, 0.05, 0.02), emission_strength=8.0)
    for cname, col in COMPOUND_COLOURS.items():
        m["cmp_" + cname] = bmat.simple("CAR_Compound_%s" % cname, col, 0.55)
    return m


# --------------------------------------------------------------------------
# car parts
# --------------------------------------------------------------------------
BODY_SECTIONS = [
    # (x, half width, z bottom, z top, corner radius)
    (2.62, 0.075, 0.105, 0.170, 0.035),
    (2.40, 0.115, 0.085, 0.235, 0.055),
    (2.05, 0.175, 0.070, 0.310, 0.075),
    (1.62, 0.255, 0.060, 0.400, 0.095),
    (1.15, 0.350, 0.055, 0.480, 0.110),
    (0.62, 0.425, 0.050, 0.540, 0.115),
    (0.10, 0.470, 0.050, 0.585, 0.115),
    (-0.32, 0.520, 0.050, 0.735, 0.130),
    (-0.62, 0.545, 0.050, 0.930, 0.150),
    (-1.02, 0.515, 0.050, 0.865, 0.150),
    (-1.50, 0.400, 0.060, 0.715, 0.130),
    (-1.95, 0.290, 0.080, 0.590, 0.110),
    (-2.22, 0.200, 0.100, 0.480, 0.090),
]


def _interp_body(x, idx):
    """Interpolate a BODY_SECTIONS column at longitudinal position x."""
    xs = [s[0] for s in BODY_SECTIONS]
    if x >= xs[0]:
        return BODY_SECTIONS[0][idx]
    if x <= xs[-1]:
        return BODY_SECTIONS[-1][idx]
    for k in range(len(xs) - 1):
        if xs[k] >= x >= xs[k + 1]:
            f = (xs[k] - x) / (xs[k] - xs[k + 1])
            return BODY_SECTIONS[k][idx] * (1 - f) + BODY_SECTIONS[k + 1][idx] * f
    return BODY_SECTIONS[-1][idx]


def body_top(x):
    return _interp_body(x, 3)


def body_half_width(x):
    return _interp_body(x, 1)


def build_body(mats, col):
    sections = []
    for (x, hw, z0, z1, r) in BODY_SECTIONS:
        sections.append((x, rounded_rect(hw, z0, z1, r)))
    return loft("CAR_Body", 'X', sections, mats["body"], col)


def build_cockpit_opening(mats, col):
    """Dark inset panel reading as the cockpit aperture, plus the airbox mouth."""
    out = []
    sections = []
    for x in (0.90, 0.72, 0.50, 0.25, 0.00, -0.14):
        zt = body_top(x)
        hw = body_half_width(x) * 0.60
        sections.append((x, rounded_rect(hw, zt - 0.055, zt + 0.006, 0.035)))
    out.append(loft("CAR_CockpitInset", 'X', sections, mats["dark"], col))

    airbox = []
    for x, hwf, dz in ((-0.42, 0.20, 0.055), (-0.56, 0.26, 0.012),
                       (-0.70, 0.24, 0.020)):
        zt = body_top(x)
        airbox.append((x, rounded_rect(body_half_width(x) * hwf,
                                       zt - 0.115, zt + dz, 0.045)))
    out.append(loft("CAR_Airbox", 'X', airbox, mats["dark"], col))
    return out


def build_shark_fin(mats, col):
    """Engine-cover fin with the white team stripe along its top edge."""
    out = []
    xs = [-0.72, -1.00, -1.30, -1.60, -1.88, -2.05]
    fin, stripe = [], []
    for x in xs:
        zt = body_top(x)
        fin.append((x, [(0.016, zt - 0.06), (-0.016, zt - 0.06),
                        (-0.016, zt + 0.135), (0.016, zt + 0.135)]))
        stripe.append((x, [(0.019, zt + 0.100), (-0.019, zt + 0.100),
                           (-0.019, zt + 0.138), (0.019, zt + 0.138)]))
    out.append(loft("CAR_SharkFin", 'X', fin, mats["body"], col, smooth=False))
    out.append(loft("CAR_FinStripe", 'X', stripe, mats["white"], col, smooth=False))
    return out


def build_sidepods(mats, col):
    """Sidepod volumes with the 2026 undercut, mirrored left/right."""
    spec = [
        (0.72, 0.40, 0.50, 0.16, 0.34),
        (0.40, 0.42, 0.66, 0.13, 0.46),
        (0.00, 0.44, 0.76, 0.11, 0.475),
        (-0.45, 0.44, 0.775, 0.10, 0.455),
        (-0.90, 0.42, 0.70, 0.10, 0.395),
        (-1.30, 0.38, 0.52, 0.10, 0.315),
        (-1.55, 0.34, 0.40, 0.10, 0.270),
    ]
    out = []
    for side in (1.0, -1.0):
        sections = []
        for (x, yi, yo, z0, z1) in spec:
            hw = (yo - yi) / 2.0
            mid = (yo + yi) / 2.0
            prof = rounded_rect(hw, z0, z1, min(hw, (z1 - z0) / 2) * 0.7)
            prof = [(side * (mid + py), pz) for (py, pz) in prof]
            if side < 0:
                prof = prof[::-1]
            sections.append((x, prof))
        out.append(loft("CAR_Sidepod%s" % ("L" if side > 0 else "R"),
                        'X', sections, mats["body"], col))
    return out


def build_floor(mats, col):
    """Flat floor with the diffuser ramp at the rear."""
    spec = [
        (1.45, 0.30, FLOOR_Z),
        (1.05, 0.44, FLOOR_Z),
        (0.30, 0.50, FLOOR_Z),
        (-0.60, 0.50, FLOOR_Z),
        (-1.25, 0.50, FLOOR_Z + 0.01),
        (-1.60, 0.49, FLOOR_Z + 0.09),
        (-1.90, 0.46, FLOOR_Z + 0.22),
        (-2.10, 0.42, FLOOR_Z + 0.32),
    ]
    sections = []
    for (x, hw, z) in spec:
        sections.append((x, rounded_rect(hw, z - 0.022, z + 0.022, 0.018)))
    return loft("CAR_Floor", 'X', sections, mats["carbon"], col, smooth=False)


def build_front_wing(mats, col):
    out = []
    hs = 0.95
    out.append(wing_element("CAR_FW_Main", 2.44, 0.075, hs, 0.30, 0.055, -3.0,
                            mats["body"], col, taper=0.8, camber=0.13,
                            dihedral=0.012))
    out.append(wing_element("CAR_FW_Flap1", 2.30, 0.135, hs * 0.98, 0.22, 0.05,
                            -10.0, mats["body"], col, taper=0.8, camber=0.16,
                            dihedral=0.015))
    out.append(wing_element("CAR_FW_Flap2", 2.20, 0.195, hs * 0.94, 0.17, 0.05,
                            -17.0, mats["dark"], col, taper=0.8, camber=0.18,
                            dihedral=0.018))
    # endplates, kept inside the 1900 mm legal width
    for side in (1.0, -1.0):
        prof = [(2.52, 0.050), (2.16, 0.050), (2.10, 0.295),
                (2.40, 0.310), (2.52, 0.215)]
        spec = [(side * (hs - 0.038), prof), (side * hs, prof)]
        out.append(loft("CAR_FW_Endplate%s" % ("L" if side > 0 else "R"),
                        'Y', spec, mats["dark"], col, smooth=False))
    return out


def build_rear_wing(mats, col):
    out = []
    hs = 0.75
    out.append(wing_element("CAR_RW_Main", -2.05, 0.82, hs, 0.28, 0.06, 12.0,
                            mats["body"], col, taper=0.95, camber=0.14))
    out.append(wing_element("CAR_RW_Flap", -2.22, 0.965, hs * 0.98, 0.19, 0.05,
                            22.0, mats["dark"], col, taper=0.95, camber=0.16))
    out.append(wing_element("CAR_RW_Beam", -2.02, 0.40, hs * 0.82, 0.20, 0.05,
                            14.0, mats["carbon"], col, taper=0.9, camber=0.12))
    for side in (1.0, -1.0):
        prof = [(-1.92, 0.36), (-2.36, 0.42), (-2.36, 1.03), (-1.96, 1.00),
                (-1.90, 0.72)]
        spec = [(side * hs, prof), (side * (hs + 0.03), prof)]
        out.append(loft("CAR_RW_Endplate%s" % ("L" if side > 0 else "R"),
                        'Y', spec, mats["dark"], col, smooth=False))
    # rain light
    out.append(loft("CAR_RainLight", 'X',
                    [(-2.24, rounded_rect(0.055, 0.60, 0.70, 0.02)),
                     (-2.30, rounded_rect(0.055, 0.60, 0.70, 0.02))],
                    mats["led"], col, smooth=False))
    return out


def build_halo(mats, col):
    pts_side = []
    for side in (1.0, -1.0):
        pts = []
        for k in range(13):
            f = k / 12.0
            # from the front centre pillar, sweeping back over the cockpit
            ang = math.pi * f
            x = 0.92 - 1.05 * f
            y = side * 0.40 * math.sin(math.pi * min(1.0, f * 1.15))
            z = 0.80 + 0.135 * math.sin(math.pi * f) - 0.05 * f
            pts.append((x, y, z))
        pts_side.append(tube("CAR_Halo%s" % ("L" if side > 0 else "R"),
                             pts, 0.028, mats["carbon"], col))
    pts_side.append(tube("CAR_HaloPillar",
                         [(0.94, 0.0, 0.545), (0.93, 0.0, 0.70), (0.92, 0.0, 0.80)],
                         0.032, mats["carbon"], col))
    return pts_side


def build_cockpit(mats, col, livery):
    out = []
    # headrest / cockpit surround
    out.append(loft("CAR_Headrest", 'X',
                    [(0.10, rounded_rect(0.34, 0.50, 0.60, 0.06)),
                     (-0.12, rounded_rect(0.36, 0.50, 0.66, 0.07)),
                     (-0.30, rounded_rect(0.34, 0.50, 0.64, 0.07))],
                    mats["dark"], col))
    # helmet
    out.append(revolve("CAR_Helmet",
                       [(-0.125, 0.0), (-0.11, 0.055), (-0.06, 0.105),
                        (0.0, 0.122), (0.06, 0.105), (0.11, 0.055), (0.125, 0.0)],
                       (0.40, 0.0, 0.655), 'X', mats["helmet"], col, segments=18))
    out.append(loft("CAR_Visor", 'X',
                    [(0.47, rounded_rect(0.085, 0.63, 0.70, 0.025)),
                     (0.52, rounded_rect(0.070, 0.635, 0.695, 0.022))],
                    mats["visor"], col))
    # mirrors
    for side in (1.0, -1.0):
        out.append(loft("CAR_Mirror%s" % ("L" if side > 0 else "R"), 'Y',
                        [(side * 0.30, [(0.66, 0.545), (0.60, 0.545),
                                        (0.60, 0.585), (0.66, 0.585)]),
                         (side * 0.44, [(0.67, 0.550), (0.59, 0.550),
                                        (0.59, 0.600), (0.67, 0.600)])],
                        mats["dark"], col, smooth=False))
    return out


def build_wheel(mats, col, x, y, radius, width, compound, tag):
    """
    One wheel as its own object with the mesh built around the hub and the
    object placed at the hub. That way spinning it is a rotation about its own
    local Y axis; a single joined wheel-set object would orbit all four wheels
    around the car instead.

    Returns (wheel_object, band_object) with the band parented to the wheel.
    """
    hw = width / 2.0
    outboard_sign = 1.0 if y > 0 else -1.0
    parts = []
    # tyre: rim seat -> sidewall -> shoulder -> tread -> back down
    tyre_profile = [
        (-hw * 0.86, RIM_R), (-hw, RIM_R + 0.030), (-hw, radius - 0.075),
        (-hw * 0.90, radius - 0.020), (-hw * 0.62, radius),
        (hw * 0.62, radius), (hw * 0.90, radius - 0.020),
        (hw, radius - 0.075), (hw, RIM_R + 0.030), (hw * 0.86, RIM_R),
    ]
    parts.append(revolve("CAR_Tyre_%s" % tag, tyre_profile, (0, 0, 0), 'Y',
                         mats["rubber"], col, segments=28))
    rim_profile = [(-hw * 0.84, 0.062), (-hw * 0.84, RIM_R),
                   (hw * 0.84, RIM_R), (hw * 0.84, 0.062)]
    parts.append(revolve("CAR_Rim_%s" % tag, rim_profile, (0, 0, 0), 'Y',
                         mats["rim"], col, segments=22))
    face = hw * 0.845 * outboard_sign
    for k in range(6):
        a = 2.0 * math.pi * k / 6.0
        ca, sa = math.cos(a), math.sin(a)
        r0, r1, wsp = 0.075, RIM_R - 0.012, 0.030
        verts = []
        for rr in (r0, r1):
            for sgn in (-1.0, 1.0):
                verts.append((rr * ca - sgn * wsp * sa * 0.5, face,
                              rr * sa + sgn * wsp * ca * 0.5))
        parts.append(make_mesh("CAR_Spoke_%s_%d" % (tag, k), verts,
                               [(0, 1, 3, 2)], col, [mats["metal"]], [0]))
    disc = [(-0.032, 0.078), (-0.032, 0.142), (0.032, 0.142), (0.032, 0.078)]
    parts.append(revolve("CAR_Disc_%s" % tag, disc, (0, 0, 0), 'Y',
                         mats["metal"], col, segments=16, smooth=False))
    wheel = join(parts, "CAR_Wheel_%s" % tag)
    wheel.location = (x, y, radius)

    band_axial = hw * 1.004 * outboard_sign
    band = revolve("CAR_Band_%s" % tag,
                   [(band_axial, RIM_R + 0.045), (band_axial, RIM_R + 0.100)],
                   (0, 0, 0), 'Y', mats["cmp_" + compound], col, segments=28,
                   smooth=False, cap=False)
    band.parent = wheel
    band.matrix_parent_inverse.identity()
    band.location = (0, 0, 0)
    return wheel, band


def build_suspension(mats, col, mats_key="carbon"):
    out = []
    m = mats[mats_key]
    corners = [(AXLE_F, 0.7725, 0.34, "F"), (AXLE_R, 0.7475, 0.38, "R")]
    for (ax, ay, chassis_hw, tag) in corners:
        for side in (1.0, -1.0):
            y = side * ay
            hub = (ax, y * 0.86, 0.30)
            # lower wishbone (two legs)
            for dx in (0.26, -0.26):
                out.append(tube("CAR_Susp%s_Low" % tag,
                                [(ax + dx, side * chassis_hw * 0.55, 0.13), hub],
                                0.022, m, col, segments=6))
            # upper wishbone
            for dx in (0.22, -0.22):
                out.append(tube("CAR_Susp%s_Up" % tag,
                                [(ax + dx, side * chassis_hw * 0.62, 0.31),
                                 (ax, y * 0.86, 0.44)],
                                0.020, m, col, segments=6))
            # push-rod
            out.append(tube("CAR_Susp%s_Push" % tag,
                            [(ax - 0.05, y * 0.84, 0.16),
                             (ax + 0.30, side * chassis_hw * 0.5, 0.42)],
                            0.019, m, col, segments=6))
            # track rod
            out.append(tube("CAR_Susp%s_Track" % tag,
                            [(ax + 0.12, side * chassis_hw * 0.5, 0.22),
                             (ax + 0.10, y * 0.86, 0.30)],
                            0.015, m, col, segments=6))
    return out


def build_livery_details(mats, col, livery):
    """White nose flash and Ferrari-style dark engine-cover panel."""
    out = []
    nose = []
    for x in (2.30, 2.10, 1.86, 1.66):
        hw = body_half_width(x)
        zt = body_top(x)
        nose.append((x, rounded_rect(hw * 0.85, zt - 0.10, zt + 0.004, 0.03)))
    out.append(loft("CAR_NoseFlash", 'X', nose, mats["white"], col))
    return out


# --------------------------------------------------------------------------
# assembly
# --------------------------------------------------------------------------
LIVERIES = {
    "LEC": dict(tag="LEC", number=16, driver="Leclerc", team="Ferrari",
                primary=(0.62, 0.015, 0.015), secondary=(0.035, 0.035, 0.038),
                helmet=(0.75, 0.05, 0.20)),
    "HAM": dict(tag="HAM", number=44, driver="Hamilton", team="Ferrari",
                primary=(0.62, 0.015, 0.015), secondary=(0.035, 0.035, 0.038),
                helmet=(0.85, 0.80, 0.05)),
}


def build_car(livery_key="LEC", compound="medium", parent_collection=None):
    livery = LIVERIES[livery_key]
    root = parent_collection or get_collection(COLLECTION)
    col = get_collection("Car_%s" % livery["tag"], root)
    mats = car_materials(livery)

    parts = []
    parts.append(build_body(mats, col))
    parts += build_sidepods(mats, col)
    parts.append(build_floor(mats, col))
    parts += build_front_wing(mats, col)
    parts += build_rear_wing(mats, col)
    parts += build_halo(mats, col)
    parts += build_cockpit(mats, col, livery)
    parts += build_cockpit_opening(mats, col)
    parts += build_shark_fin(mats, col)
    parts += build_suspension(mats, col)
    parts += build_livery_details(mats, col, livery)

    wheels, bands = [], []
    for (x, r, w, tag) in ((AXLE_F, TYRE_F_R, TYRE_F_W, "FL"),
                           (AXLE_F, TYRE_F_R, TYRE_F_W, "FR"),
                           (AXLE_R, TYRE_R_R, TYRE_R_W, "RL"),
                           (AXLE_R, TYRE_R_R, TYRE_R_W, "RR")):
        y = (0.7725 if x > 0 else 0.7475) * (1.0 if tag.endswith("L") else -1.0)
        wheel, band = build_wheel(mats, col, x, y, r, w, compound,
                                  "%s_%s" % (livery["tag"], tag))
        wheels.append(wheel)
        bands.append(band)

    chassis = join(parts, "CAR_%s_Chassis" % livery["tag"])

    empty = bpy.data.objects.new("CAR_%s" % livery["tag"], None)
    empty.empty_display_type = 'ARROWS'
    empty.empty_display_size = 1.5
    col.objects.link(empty)
    if chassis:
        chassis.parent = empty
    for wheel in wheels:
        wheel.parent = empty
        wheel.matrix_parent_inverse.identity()
    empty["driver"] = livery["driver"]
    empty["number"] = livery["number"]
    empty["compound"] = compound
    return empty, dict(chassis=chassis, wheels=wheels, bands=bands,
                       materials=mats, collection=col)


def set_compound(car_parts, compound):
    """Re-colour a car's tyre sidewall bands for a new stint."""
    bands = car_parts.get("bands") or []
    mats = car_parts.get("materials")
    if not bands or not mats:
        return False
    mat = mats.get("cmp_" + compound)
    if mat is None:
        return False
    for band in bands:
        band.data.materials.clear()
        band.data.materials.append(mat)
    return True


TEAM_COLOURS = {
    "Ferrari": (0.62, 0.015, 0.015),
    "Red Bull": (0.025, 0.045, 0.30),
    "McLaren": (0.85, 0.28, 0.01),
    "Mercedes": (0.42, 0.46, 0.48),
    "Aston Martin": (0.015, 0.20, 0.14),
    "Williams": (0.02, 0.18, 0.55),
    "Alpine": (0.02, 0.28, 0.62),
    "Racing Bulls": (0.10, 0.16, 0.55),
    "Haas": (0.62, 0.62, 0.64),
    "Kick Sauber": (0.05, 0.55, 0.10),
}


def spawn_from_template(code, team, template, compound, root):
    """
    Linked duplicate of the template car with an object-level livery override.
    Mesh data is shared, so a full grid costs almost nothing in memory.
    """
    col = get_collection("Car_%s" % code, root)
    body_mat = bmat.simple("CAR_%s_Body" % code,
                           TEAM_COLOURS.get(team, (0.5, 0.5, 0.5)), 0.22,
                           metallic=0.35)
    band_mat = bmat.simple("CAR_%s_Band_%s" % (code, compound),
                           COMPOUND_COLOURS[compound], 0.55)
    empty = bpy.data.objects.new("CAR_%s" % code, None)
    empty.empty_display_type = 'ARROWS'
    empty.empty_display_size = 1.5
    col.objects.link(empty)

    def clone(src, name, parent, override_band=False):
        ob = bpy.data.objects.new(name, src.data)
        col.objects.link(ob)
        ob.parent = parent
        ob.matrix_parent_inverse.identity()
        ob.location = src.location
        ob.rotation_euler = src.rotation_euler
        for slot in ob.material_slots:
            slot.link = 'OBJECT'
        for i, slot in enumerate(ob.material_slots):
            base = src.data.materials[i] if i < len(src.data.materials) else None
            nm = base.name if base else ""
            if override_band or "Compound" in nm:
                slot.material = band_mat
            elif "Body" in nm:
                slot.material = body_mat
            else:
                slot.material = base
        return ob

    made = {"wheels": [], "bands": []}
    if template.get("chassis"):
        made["chassis"] = clone(template["chassis"], "CAR_%s_Chassis" % code, empty)
    for i, src_wheel in enumerate(template.get("wheels") or []):
        w = clone(src_wheel, "CAR_%s_Wheel%d" % (code, i), empty)
        made["wheels"].append(w)
        for src_band in (template.get("bands") or []):
            if src_band.parent is src_wheel:
                made["bands"].append(
                    clone(src_band, "CAR_%s_Band%d" % (code, i), w,
                          override_band=True))
    empty["team"] = team
    empty["code"] = code
    empty["compound"] = compound
    return dict(root=empty, band_material=band_mat, body_material=body_mat, **made)


def set_compound_material(car, compound):
    """Swap a spawned car's sidewall colour for a new stint."""
    bands = car.get("bands") or []
    if not bands:
        return False
    code = car["root"].get("code", car["root"].name)
    mat = bmat.simple("CAR_%s_Band_%s" % (code, compound),
                      COMPOUND_COLOURS[compound], 0.55)
    for band in bands:
        for slot in band.material_slots:
            slot.link = 'OBJECT'
            slot.material = mat
    car["band_material"] = mat
    return True


def build(compound="medium", grid=None):
    """
    grid: [(code, team)] to spawn beyond the two works Ferraris.
    """
    clear_collection(COLLECTION)
    root = get_collection(COLLECTION)
    cars = {}
    for key in ("LEC", "HAM"):
        empty, parts = build_car(key, compound, root)
        cars[key] = dict(root=empty, **parts)
    template = cars["LEC"]
    for code, team in (grid or []):
        if code in cars:
            continue
        cars[code] = spawn_from_template(code, team, template, compound, root)
    faces = sum(len(o.data.polygons) for o in bpy.data.objects
                if o.type == 'MESH' and o.name.startswith("CAR_"))
    return cars, ["cars: %d on the grid, %d faces total" % (len(cars), faces)]


if __name__ == "__main__":
    _, rep = build()
    print("\n".join(rep))

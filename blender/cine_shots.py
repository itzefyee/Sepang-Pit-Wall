"""The 1-minute Sepang highlight: shot list, build, probe, render.

Structure
---------
Exactly 1440 frames at 24 fps = 60.0 s, in three acts that follow the
simulation's own weather timeline (dry through f6999, heavy rain f7000-9799,
full monsoon f9800+):

    Act 1  DRY POWER      456 fr  19.0 s   sun 4.0, hard shadows
    Act 2  THE SKY BREAKS 432 fr  18.0 s   sun 1.8, storm 0.68
    Act 3  MONSOON        552 fr  23.0 s   sun 0.7, storm 1.0

Editing rules applied
---------------------
* Pace escalates: 4.0 s opening shots tighten to 1.5 s at the climax, then
  one long 5.75 s hold to resolve.
* No two adjacent shots share a shot size. Wide -> tight -> medium -> low
  -> aerial, cycled deliberately.
* Focal length carries the emotion: 20-24 mm immersive onboard, 34-55 mm
  chase and medium, 85-200 mm compressed trackside for the speed sensation.
* Depth of field only on the long lenses, where subject separation reads.

Geometry note
-------------
`side` / `ahead` / `height` are metres in CAR-LOCAL space, not world space.
`ahead` near 0 places the car level with the camera at the shot's mid-frame,
so a trackside shot naturally becomes approach -> pass -> depart.
"""

import bpy
import os

from cine_rig import (build_track_cam, build_rider_cam, setup_look,
                      add_glare, verify_output, _coll, FPS)

HERO = "CAR_LEC"
OUT = r"c:\Users\spoop\OneDrive\Documents\Class\hackathon\F1\blender\out"


# Per-act base exposure. The simulation drops the sun from 4.0 to 0.72 between
# the dry and monsoon acts, which is dramatically correct but leaves Act 3
# around 0.11 mean — too dark to read. Lifting exposure per act keeps the
# luminance descent while holding detail in the storm.
ACT_EXPOSURE = {1: -0.85, 2: -0.55, 3: -0.10}


def S(n, act, label, kind, start, dur, lens, side, ahead, height,
      fstop=None, aim_height=1.2, aim_ahead=12.0, exposure=None, note=""):
    return dict(n=n, act=act, label=label, kind=kind, start=start, dur=dur,
                lens=lens, side=side, ahead=ahead, height=height,
                fstop=fstop, aim_height=aim_height, aim_ahead=aim_ahead,
                exposure=exposure if exposure is not None else ACT_EXPOSURE[act],
                note=note, cam="CINE_%02d_%s" % (n, label))


SHOTS = [
    # ── ACT 1 — DRY POWER ──────────────────────────────────────── 456 fr ──
    S( 1, 1, "aerial_establish", "TRACK", 1800,  96,  35,   40,  30,  90.0,
       aim_height=1.0, note="high crane wide, establishes circuit scale"),
    # Barriers sit ~25 m off the centreline, so the original 55 m standoff was
    # outside the wall. Shooting from 20 m keeps the long-lens compression.
    # Height raised to 2.4 m: at 1.0 m the barrier ate the bottom third.
    S( 2, 1, "low_speed_tele",   "TRACK",  620,  72, 105,   20,   8,   2.4,
       fstop=2.8, aim_height=0.9, note="ground-level long lens, compressed speed"),
    S( 3, 1, "onboard_dry",      "RIDER", 2600,  66,  22,  0.0, 0.30, 1.15,
       aim_ahead=25.0, aim_height=1.0, note="cockpit, immersive wide"),
    S( 4, 1, "t1_braking",       "TRACK",  160,  60,  50,  -45,   5,  14.0,
       note="high three-quarter over T1 braking zone"),
    S( 5, 1, "t15_sweep",        "TRACK",  945,  60,  50,  -35,  10,  20.0,
       note="hairpin from above, shows the line"),
    S( 6, 1, "tyre_detail",      "RIDER", 3400,  48,  40,  2.2, -1.6,  0.50,
       fstop=2.2, aim_ahead=2.0, aim_height=0.3, note="wheel-level texture beat"),
    S( 7, 1, "chase_dry",        "RIDER", 4200,  54,  34,  0.0, -9.0,  3.00,
       aim_ahead=15.0, note="chase, dry, sets the baseline"),

    # ── ACT 2 — THE SKY BREAKS ─────────────────────────────────── 432 fr ──
    # Pulled down from 120 m and tightened from 28 mm: at the original framing
    # the cars were specks and the storm had nothing to dwarf.
    S( 8, 2, "aerial_storm",     "TRACK", 7060,  84,  40,   50,  40,  85.0,
       aim_height=1.0, note="widest shot of the film, storm scale"),
    S( 9, 2, "chase_first_rain", "RIDER", 7300,  72,  34,  0.0, -10.0, 3.20,
       aim_ahead=16.0, note="track going dark, first standing water"),
    S(10, 2, "spray_tele",       "TRACK", 7600,  60, 180,   95,   5,   2.5,
       fstop=3.2, aim_height=1.0, note="200mm-ish compression through spray"),
    S(11, 2, "onboard_rain",     "RIDER", 7900,  60,  22,  0.0, 0.30, 1.15,
       aim_ahead=25.0, aim_height=1.0, note="visibility collapsing"),
    S(12, 2, "low_wheel_spray",  "TRACK", 8300,  48,  50,   14,   0,   0.55,
       fstop=2.5, aim_height=0.8, note="ultra-low, rooster tail across frame"),
    S(13, 2, "t1_wet_pan",       "TRACK", 8700,  54,  85,  -40,   6,   9.0,
       fstop=3.5, note="trackside pan, wet line into T1"),
    S(14, 2, "chase_battle",     "RIDER", 9300,  54,  34,  1.5, -11.0, 2.40,
       aim_ahead=20.0, note="wheel to wheel, offset for the second car"),

    # ── ACT 3 — MONSOON ────────────────────────────────────────── 552 fr ──
    S(15, 3, "aerial_monsoon",   "TRACK", 9880,  72,  24,   45,  35, 105.0,
       aim_height=1.0, note="full storm from height, sun down to 0.7"),
    # Lifted to 1.45 m and aimed further out: at 1.15 m the car's own bodywork
    # filled the lower half of frame and buried the rain.
    S(16, 3, "onboard_monsoon",  "RIDER",10200,  60,  22,  0.0, 0.30, 1.45,
       aim_ahead=30.0, aim_height=1.4, note="halo framing, worst visibility"),
    S(17, 3, "spray_curtain",    "TRACK",10650,  48, 200,  110,   0,   3.0,
       fstop=3.2, aim_height=1.0, note="longest lens, rain curtain"),
    S(18, 3, "low_hero_monsoon", "TRACK",11050,  42,  35,   16,  -4,   0.60,
       fstop=2.8, aim_height=0.9, note="low and aggressive, car fills frame"),
    S(19, 3, "chase_monsoon",    "RIDER",11500,  42,  34,  0.0, -9.5,  3.00,
       aim_ahead=15.0, note="chase at peak storm"),
    S(20, 3, "tyre_water",       "RIDER",12000,  36,  40,  2.2, -1.8,  0.45,
       fstop=2.0, aim_ahead=2.0, aim_height=0.25, note="aquaplaning detail"),
    S(21, 3, "onboard_climax",   "RIDER",12500,  36,  20,  0.0, 0.35, 1.12,
       aim_ahead=18.0, aim_height=1.0, note="fastest cut, widest onboard"),
    S(22, 3, "t15_monsoon_pan",  "TRACK",13000,  36, 100,  -45,   8,  16.0,
       fstop=4.0, note="hairpin, long lens, storm"),
    S(23, 3, "chase_final_push", "RIDER",13600,  42,  34,  0.0, -8.5,  2.80,
       aim_ahead=14.0, note="last hard cut before the resolve"),
    # Converted from TRACK to RIDER. As a trackside pan this ran 5.75 s while
    # whipping round to follow a car 30 m away, and the angular rate smeared
    # the whole frame. Riding alongside instead holds the car rock steady and
    # lets the background streak, which is what a closing beauty shot wants.
    # f/8 rather than f/2.8 so the car stays crisp end to end.
    S(24, 3, "hero_beauty_hold", "RIDER",14600, 138,  55,  9.0, -5.0,  2.60,
       fstop=8.0, aim_ahead=10.0, aim_height=0.9,
       note="long hold, resolution beat, car steady, background streaming"),
]

ACT_NAMES = {1: "DRY POWER", 2: "THE SKY BREAKS", 3: "MONSOON"}


# ─────────────────────────────────────────────────────────────────────────────

def plan():
    total = sum(s["dur"] for s in SHOTS)
    print("=" * 78)
    print("SEPANG 1-MINUTE HIGHLIGHT  —  %d shots, %d frames, %.2f s @ %d fps"
          % (len(SHOTS), total, total / FPS, FPS))
    print("=" * 78)
    t = 0
    cur = None
    for s in SHOTS:
        if s["act"] != cur:
            cur = s["act"]
            af = sum(x["dur"] for x in SHOTS if x["act"] == cur)
            print("\n── ACT %d  %s   (%d fr / %.1f s) ──"
                  % (cur, ACT_NAMES[cur], af, af / FPS))
            print("  %-4s %-18s %-6s %-13s %-5s %-5s %s"
                  % ("tc", "shot", "kind", "src frames", "len", "dur", "note"))
        print("  %-4s %-18s %-6s %-13s %-5s %-5.2f %s"
              % ("%d:%02d" % (t // FPS // 60, (t // FPS) % 60),
                 s["label"], s["kind"],
                 "%d-%d" % (s["start"], s["start"] + s["dur"] - 1),
                 "%dmm" % s["lens"], s["dur"] / FPS, s["note"]))
        t += s["dur"]
    print("\nTotal: %d frames = %.2f s" % (total, total / FPS))
    return total


def build_all(glare=False):
    """Build the full 24-camera rig.

    `glare` is off by default. A correctly wired Glare node group still renders
    black on this Blender 5.2 build — the scene compositor does not feed the
    render result into a node group's Group Input the way the 4.x Render Layers
    node did. The look is carried by AgX Punchy, exposure and motion blur
    instead, and `verify_output` below will clear the compositor if it ever
    swallows the image again.
    """
    setup_look(samples=32)
    if glare:
        add_glare()
    car = bpy.data.objects[HERO]
    print("\nbuilding %d cameras on %s ..." % (len(SHOTS), HERO))
    rescued, failed = [], []
    for s in SHOTS:
        if s["kind"] == "TRACK":
            _cam, attempt = build_track_cam(s, car)
        else:
            _cam, attempt = build_rider_cam(s, car)
        tag = "ok"
        if attempt > 0:
            tag = "rescued(step %d)" % attempt
            rescued.append(s["label"])
        elif attempt < 0:
            tag = "OCCLUDED"
            failed.append(s["label"])
        print("  %-22s %-6s %s" % (s["label"], s["kind"], tag))
    print("\nrescued from occlusion: %s" % (", ".join(rescued) or "none"))
    print("still occluded:         %s" % (", ".join(failed) or "none"))

    # Tripwire: catch a black output chain before committing to 1440 frames.
    s0 = SHOTS[0]
    verify_output(s0["cam"], s0["start"] + s0["dur"] // 2)
    return failed


def probe_all(res=(960, 540), samples=12):
    """One still per shot at its mid-frame, for eyeball verification."""
    sc = bpy.context.scene
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.eevee.taa_render_samples = samples
    folder = os.path.join(OUT, "cine_probe")
    os.makedirs(folder, exist_ok=True)
    for s in SHOTS:
        mid = s["start"] + s["dur"] // 2
        sc.frame_set(mid)
        sc.camera = bpy.data.objects[s["cam"]]
        sc.view_settings.exposure = s["exposure"]
        sc.render.filepath = os.path.join(
            folder, "p%02d_%s.png" % (s["n"], s["label"]))
        bpy.ops.render.render(write_still=True)
        print("  probe %02d %s" % (s["n"], s["label"]))
    print("probes -> %s" % folder)


def render_all(samples=32):
    """Full render. Each shot writes into its own numbered folder so the
    stitch step can concatenate them in shot order."""
    import time
    sc = bpy.context.scene
    setup_look(samples=samples)
    root = os.path.join(OUT, "cine")
    wall = time.time()
    for s in SHOTS:
        folder = os.path.join(root, "%02d_%s" % (s["n"], s["label"]))
        os.makedirs(folder, exist_ok=True)
        sc.frame_start = s["start"]
        sc.frame_end = s["start"] + s["dur"] - 1
        sc.camera = bpy.data.objects[s["cam"]]
        sc.view_settings.exposure = s["exposure"]
        sc.render.filepath = os.path.join(folder, "f_####")
        t0 = time.time()
        bpy.ops.render.render(animation=True)
        print("  %02d %-20s %3d fr  %.0f s"
              % (s["n"], s["label"], s["dur"], time.time() - t0))
    print("\nall shots rendered in %.1f min" % ((time.time() - wall) / 60))

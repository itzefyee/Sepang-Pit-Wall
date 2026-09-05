"""
Export a compact, web-sized telemetry track for the three delivered clips.

The three mp4s are exact frame-for-frame concatenations of the 24 shots that
cine_render.py rendered, and extract_audio_telemetry.py already captured the
simulation state for every one of those frames. So the browser HUD does not
need to invent numbers: it can read the same speed and storm trace that drove
the engine audio.

    sepang_onboard_final.mp4    222 frames   03 -> 11 -> 16 -> 21
    sepang_pov_final.mp4        486 frames   07 03 09 11 14 19 16 23 21
    sepang_highlight_final.mp4 1440 frames   01 .. 24 in order

Edit orders are read from the stitch scripts, not guessed:
    stitch_cine.ps1     -> highlight
    stitch_onboard.ps1  -> pov
    (onboard = the four RIDER onboard_* shots in story order)

Run from the project root:  python scripts/export_clip_telemetry.py
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "blender" / "out" / "audio_telemetry.json"
DEST = ROOT / "src" / "pitwall" / "data" / "clip-telemetry.json"

# Edit orders, by shot number, taken from the stitch scripts.
EDITS = {
    "highlight": list(range(1, 25)),
    "pov": [7, 3, 9, 11, 14, 19, 16, 23, 21],
    "onboard": [3, 11, 16, 21],
}

# Human-facing shot titles and the corner each shot is looking at. The render
# labels are terse folder names; these are what the HUD puts on screen.
SHOT_META = {
    1:  ("Aerial establish",      "Start / finish straight", "DRY"),
    2:  ("Long lens, pit straight", "Main straight",         "DRY"),
    3:  ("Onboard, dry",          "Turn 1 to Turn 4",        "DRY"),
    4:  ("Turn 1 braking",        "Turn 1",                  "DRY"),
    5:  ("Turn 15 sweep",         "Turn 15",                 "DRY"),
    6:  ("Tyre detail",           "Turn 5 to Turn 6",        "DRY"),
    7:  ("Chase, dry",            "Sector 2 esses",          "DRY"),
    8:  ("Aerial, storm front",   "Whole circuit",           "RAIN"),
    9:  ("Chase, first rain",     "Turn 9",                  "RAIN"),
    10: ("Spray, long lens",      "Back straight",           "RAIN"),
    11: ("Onboard, rain",         "Turn 12 to Turn 14",      "RAIN"),
    12: ("Wheel spray, low",      "Turn 2",                  "RAIN"),
    13: ("Turn 1 wet pan",        "Turn 1",                  "RAIN"),
    14: ("Chase, wheel to wheel", "Turn 5",                  "RAIN"),
    15: ("Aerial, monsoon",       "Whole circuit",           "MONSOON"),
    16: ("Onboard, monsoon",      "Turn 7 to Turn 9",        "MONSOON"),
    17: ("Spray curtain",         "Back straight",           "MONSOON"),
    18: ("Hero, low and wide",    "Turn 15",                 "MONSOON"),
    19: ("Chase, monsoon",        "Sector 2",                "MONSOON"),
    20: ("Tyre through water",    "Turn 9",                  "MONSOON"),
    21: ("Onboard, climax",       "Back straight",           "MONSOON"),
    22: ("Turn 15 monsoon pan",   "Turn 15",                 "MONSOON"),
    23: ("Chase, final push",     "Turn 13 to Turn 14",      "MONSOON"),
    24: ("Hero beauty hold",      "Start / finish straight", "MONSOON"),
}


def main() -> None:
    raw = json.loads(SRC.read_text(encoding="utf-8"))
    fps = raw["fps"]

    shots: dict[str, dict] = {}
    for shot in raw["shots"]:
        n = shot["n"]
        frames = shot["frames"]
        title, corner, condition = SHOT_META[n]
        shots[str(n)] = {
            "n": n,
            "label": shot["label"],
            "title": title,
            "corner": corner,
            "condition": condition,
            "kind": shot["kind"],
            "act": shot["act"],
            "lens": shot["lens"],
            "frames": len(frames),
            # simulation speed is metres per second; the HUD wants km/h
            "speedKph": [round(f["speed"] * 3.6, 1) for f in frames],
            "storm": [round(f["storm"], 2) for f in frames],
            # camera/listener to hero-car distance in metres, and its radial
            # rate in m/s. These drove the audio Doppler and distance
            # attenuation — they are a camera range, NOT a gap to a rival.
            "camRangeM": [round(f["dist"], 1) for f in frames],
            "camClosingMps": [round(f["vrad"], 2) for f in frames],
            # how many rival cars were audible in the mix for this shot
            "rivalsInMix": max(len(f.get("rivals", [])) for f in frames),
        }

    edits = {}
    for clip, order in EDITS.items():
        cuts, cursor = [], 0
        for n in order:
            length = shots[str(n)]["frames"]
            cuts.append({"shot": n, "start": cursor, "frames": length})
            cursor += length
        edits[clip] = {"totalFrames": cursor, "cuts": cuts}

    out = {
        "generatedBy": "scripts/export_clip_telemetry.py",
        "source": "blender/out/audio_telemetry.json",
        "note": (
            "speedKph and storm are the simulation's own per-frame state, the same "
            "trace that synthesised the engine audio. camRangeM is the camera to "
            "car distance used for audio attenuation, not a gap to a rival. gear, "
            "rpm, throttle and brake are derived in the browser from the speed trace."
        ),
        "fps": fps,
        "shots": shots,
        "edits": edits,
    }

    DEST.parent.mkdir(parents=True, exist_ok=True)
    DEST.write_text(json.dumps(out, separators=(",", ":")), encoding="utf-8")

    print(f"wrote {DEST.relative_to(ROOT)}  ({DEST.stat().st_size / 1024:.1f} KB)")
    for clip, data in edits.items():
        print(f"  {clip:<10} {data['totalFrames']:>5} frames  "
              f"{data['totalFrames'] / fps:6.2f}s  {len(data['cuts'])} cuts")


if __name__ == "__main__":
    main()

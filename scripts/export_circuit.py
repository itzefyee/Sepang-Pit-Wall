"""
Export the surveyed Sepang centreline into a web-sized JSON for the pit wall UI.

Source: blender/data/sepang_centreline.json — the OpenStreetMap survey of the
circuit (ODbL), resampled to 1386 points at 4 m spacing and scaled to the
homologated 5543 m, with corners, straights, DRS zones and sector boundaries
already resolved by index, plus SRTM 30 m elevation per point.

The full 1386-point ring is kept at source resolution so that every corner,
DRS and sector index maps straight across with no remapping. Elevation and the
pit lane are thinned, because they only ever feed a chart and a background
stroke.

Run from the project root:  python scripts/export_circuit.py
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "blender" / "data" / "sepang_centreline.json"
DEST = ROOT / "src" / "pitwall" / "data" / "circuit-geometry.json"

ELEVATION_STRIDE = 6
PIT_STRIDE = 3

# Which sector each corner belongs to, from the sector boundaries in the source.
def sector_of(s_m: float, sectors: list[dict]) -> int:
    for sec in sectors:
        if sec["start_m"] <= s_m < sec["end_m"]:
            return sec["id"]
    return sectors[-1]["id"]


def main() -> None:
    d = json.loads(SRC.read_text(encoding="utf-8"))

    pts = [[round(x, 1), round(y, 1)] for x, y in d["points"]]
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]

    spacing = d["spacing_m"]
    n = d["n"]

    elevations = d["elevation_m"]
    elev_profile = [
        [round(i * spacing, 1), round(elevations[i], 1)]
        for i in range(0, n, ELEVATION_STRIDE)
    ]

    corners = []
    for c in d["corners"]:
        corners.append(
            {
                "id": c["id"],
                "name": c["name"],
                "apex": c["i_apex"],
                "entry": c["i_start"],
                "exit": c["i_end"],
                "sM": c["s_apex_m"],
                "lengthM": c["length_m"],
                "radiusM": c["radius_m"],
                "dir": c["dir"],
                "headingChangeDeg": round(abs(c["heading_change_deg"]), 1),
                "kind": c["kind"],
                "note": c["note"],
                "sector": sector_of(c["s_apex_m"], d["sectors"]),
            }
        )

    drs = [
        {
            "name": z["name"],
            "detect": z["i_detect"],
            "start": z["i_start"],
            "end": z["i_end"],
            "lengthM": z["length_m"],
        }
        for z in d["drs_zones"]
    ]
    # source lists DRS 2 first; present them in lap order
    drs.sort(key=lambda z: z["name"])

    sectors = []
    for s in d["sectors"]:
        sectors.append(
            {
                "id": s["id"],
                "startM": s["start_m"],
                "endM": s["end_m"],
                "lengthM": round(s["end_m"] - s["start_m"], 1),
                "turns": s["turns"],
                "startIdx": int(s["start_m"] / spacing),
                "endIdx": min(n - 1, int(s["end_m"] / spacing)),
            }
        )

    out = {
        "generatedBy": "scripts/export_circuit.py",
        "source": d["source"],
        "lengthM": d["length_m"],
        "rawOsmLengthM": round(d["raw_osm_length_m"], 1),
        "scaleApplied": round(d["scale_applied"], 6),
        "trackWidthM": d["track_width_m"],
        "spacingM": spacing,
        "n": n,
        "originLatLon": d["origin_latlon"],
        "pitOffsetM": round(d["pit_offset_m"], 1),
        "mainStraightM": d["main_straight_m"],
        "backStraightM": d["back_straight_m"],
        "bounds": {
            "minX": min(xs),
            "maxX": max(xs),
            "minY": min(ys),
            "maxY": max(ys),
        },
        "points": pts,
        "pitLane": [
            [round(x, 1), round(y, 1)] for x, y in d["pit_lane"][::PIT_STRIDE]
        ],
        "elevationProfile": elev_profile,
        "elevationRangeM": [
            round(min(elevations), 1),
            round(max(elevations), 1),
        ],
        "corners": corners,
        "drsZones": drs,
        "sectors": sectors,
        "straights": [
            {"start": s["i_start"], "end": s["i_end"], "lengthM": s["length_m"]}
            for s in d["straights"]
        ],
    }

    DEST.parent.mkdir(parents=True, exist_ok=True)
    DEST.write_text(json.dumps(out, separators=(",", ":")), encoding="utf-8")

    print(f"wrote {DEST.relative_to(ROOT)}  ({DEST.stat().st_size / 1024:.1f} KB)")
    print(f"  {n} centreline points, {len(corners)} corners, "
          f"{len(elev_profile)} elevation samples, {len(out['pitLane'])} pit-lane points")
    print(f"  elevation range {out['elevationRangeM'][0]}-{out['elevationRangeM'][1]} m "
          f"(span {out['elevationRangeM'][1] - out['elevationRangeM'][0]:.1f} m)")
    print(f"  bounds x {out['bounds']['minX']}..{out['bounds']['maxX']}  "
          f"y {out['bounds']['minY']}..{out['bounds']['maxY']}")


if __name__ == "__main__":
    main()

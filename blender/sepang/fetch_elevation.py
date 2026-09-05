"""
Fetch real terrain elevation for the Sepang centreline (SRTM 30 m via
opentopodata.org) and cache it so the track mesh has the circuit's actual
elevation profile instead of a guessed one.

Run once; results land in ../data/sepang_elevation.json.
"""

import json
import os
import time
import urllib.parse
import urllib.request

from . import geo

STRIDE = 8            # sample every Nth centreline point (~32 m)
BATCH = 100           # opentopodata public limit per request
DATASET = "srtm30m"


def fetch(latlons):
    out = []
    for i in range(0, len(latlons), BATCH):
        chunk = latlons[i:i + BATCH]
        locs = "|".join("%.6f,%.6f" % (a, b) for a, b in chunk)
        url = "https://api.opentopodata.org/v1/%s?%s" % (
            DATASET, urllib.parse.urlencode({"locations": locs}))
        req = urllib.request.Request(url, headers={
            "User-Agent": "SepangSimBuilder/1.0", "Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=60) as r:
            js = json.loads(r.read())
        if js.get("status") != "OK":
            raise RuntimeError("opentopodata: %s" % js)
        for pt, res in zip(chunk, js["results"]):
            e = res.get("elevation")
            out.append([pt[0], pt[1], float(e) if e is not None else 0.0])
        time.sleep(1.1)   # be polite to the public endpoint
    return out


def main():
    data = geo.build_centreline(use_cache=False, write_cache=False)
    latlons = data["latlon"][::STRIDE]
    pts = fetch(latlons)
    cache = {"dataset": DATASET, "stride": STRIDE, "points": pts}
    os.makedirs(geo.DATA_DIR, exist_ok=True)
    with open(geo.ELEV_CACHE, "w", encoding="utf-8") as fh:
        json.dump(cache, fh)
    elevs = [p[2] for p in pts]
    return "elevation cached: %d samples, %.1f..%.1f m (range %.1f m)" % (
        len(pts), min(elevs), max(elevs), max(elevs) - min(elevs))


if __name__ == "__main__":
    print(main())

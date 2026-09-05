"""Compare the synthesised engine against the reference recording.

Verifies that the fitted synth actually lands near the measured fingerprint,
rather than assuming the parameter changes had the intended effect. Compares
band energy distribution, spectral centroid and tonal fraction, and reports the
delta on each.

Run:  python scripts/compare_engine.py
"""

from __future__ import annotations

import os
import wave

import numpy as np
from scipy import signal

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REF = os.path.join(ROOT, "blender", "out", "ref", "f1_ref.wav")
SYN = os.path.join(ROOT, "blender", "out", "sepang_audio_full.wav")
SYN_ENGINE = os.path.join(ROOT, "blender", "out", "sepang_engine_only.wav")

BANDS = [(20, 80), (80, 200), (200, 500), (500, 1200),
         (1200, 3000), (3000, 8000), (8000, 16000)]


def load(path):
    with wave.open(path, "rb") as w:
        sr, n, ch = w.getframerate(), w.getnframes(), w.getnchannels()
        raw = w.readframes(n)
    x = np.frombuffer(raw, dtype="<i2").astype(np.float64) / 32768.0
    if ch > 1:
        x = x.reshape(-1, ch).mean(axis=1)
    return x, sr


def describe(x, sr, label):
    fr, psd = signal.welch(x, sr, nperseg=8192)
    total = psd.sum()
    centroid = (fr * psd).sum() / total
    sm = signal.medfilt(psd, kernel_size=31)
    tonal = np.clip(psd - sm, 0, None).sum() / total
    bands = {}
    for lo, hi in BANDS:
        m = (fr >= lo) & (fr < hi)
        bands[(lo, hi)] = psd[m].sum() / total
    print("\n%s" % label)
    print("  centroid       %7.0f Hz" % centroid)
    print("  tonal fraction %7.1f %%" % (tonal * 100))
    return centroid, tonal, bands


def main():
    for p in (REF, SYN):
        if not os.path.exists(p):
            raise SystemExit("missing: %s" % p)

    xr, sr_r = load(REF)
    c_r, t_r, b_r = describe(xr, sr_r, "REFERENCE (real F1 recording)")

    # Prefer the isolated engine layer when it exists. The full mix legitimately
    # differs, since it carries a music bed and rain that a bare engine
    # recording does not.
    if os.path.exists(SYN_ENGINE):
        xs, sr_s = load(SYN_ENGINE)
        label = "SYNTHESISED (engine layer only)"
    else:
        xs, sr_s = load(SYN)
        xs = xs[: int(19 * sr_s)]
        label = "SYNTHESISED (act 1 of full mix)"
    c_s, t_s, b_s = describe(xs, sr_s, label)

    print("\nband energy comparison")
    print("  %-14s %8s %8s %8s" % ("band (Hz)", "ref", "synth", "delta"))
    worst = 0.0
    for lo, hi in BANDS:
        r, s = b_r[(lo, hi)] * 100, b_s[(lo, hi)] * 100
        d = s - r
        worst = max(worst, abs(d))
        print("  %-14s %7.1f%% %7.1f%% %+7.1f%%"
              % ("%d-%d" % (lo, hi), r, s, d))

    print("\n  centroid delta       %+7.0f Hz (%.0f -> %.0f)"
          % (c_s - c_r, c_r, c_s))
    print("  tonal fraction delta %+7.1f %% (%.1f -> %.1f)"
          % ((t_s - t_r) * 100, t_r * 100, t_s * 100))
    print("  largest band delta   %7.1f %%" % worst)

    verdict = "close" if worst < 15 and abs(c_s - c_r) < 500 else "still divergent"
    print("\nverdict: %s" % verdict)


if __name__ == "__main__":
    main()

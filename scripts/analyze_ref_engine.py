"""Measure the spectral fingerprint of the reference F1 engine recording.

The synthesiser in synth_audio.py was built from first principles (V6 firing
order, harmonic stack, turbo whistle). This script measures what the real
recording actually does, so those parameters can be fitted to it rather than
guessed:

  * firing frequency over time  -> confirms the harmonic spacing / RPM range
  * harmonic amplitude profile  -> the roll-off exponent and odd/even balance
  * spectral centroid & tilt    -> how bright the engine sits
  * harmonic-to-noise ratio     -> how much of the sound is tonal vs broadband
  * band energy distribution    -> target EQ curve for the synth

Run:  python scripts/analyze_ref_engine.py
"""

from __future__ import annotations

import json
import os
import wave

import numpy as np
from scipy import signal

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REF = os.path.join(ROOT, "blender", "out", "ref", "f1_ref.wav")
OUT = os.path.join(ROOT, "blender", "out", "ref", "f1_ref_profile.json")


def load(path):
    with wave.open(path, "rb") as w:
        sr = w.getframerate()
        n = w.getnframes()
        ch = w.getnchannels()
        raw = w.readframes(n)
    x = np.frombuffer(raw, dtype="<i2").astype(np.float64) / 32768.0
    if ch > 1:
        x = x.reshape(-1, ch).mean(axis=1)
    return x, sr


def fundamental_track(x, sr, fmin=40.0, fmax=400.0, hop=2048, win=8192):
    """Track the firing fundamental via harmonic-product-spectrum."""
    freqs, times, Z = signal.stft(x, sr, nperseg=win, noverlap=win - hop)
    mag = np.abs(Z)
    f0s = []
    lo = int(fmin / (sr / 2) * (len(freqs) - 1))
    hi = int(fmax / (sr / 2) * (len(freqs) - 1))
    for t in range(mag.shape[1]):
        spec = mag[:, t]
        if spec.max() < 1e-6:
            f0s.append(np.nan)
            continue
        # Harmonic product spectrum: multiply decimated copies.
        hps = spec[:hi * 2].copy()
        for k in (2, 3, 4, 5):
            dec = spec[::k][:len(hps)]
            hps[:len(dec)] *= dec
        band = hps[lo:hi]
        f0s.append(freqs[lo + int(np.argmax(band))])
    return times, np.array(f0s)


def harmonic_profile(x, sr, f0, n_harm=20):
    """Amplitude of each harmonic of f0, averaged over the whole file."""
    win = 1 << 16
    if len(x) < win:
        x = np.pad(x, (0, win - len(x)))
    amps = np.zeros(n_harm)
    count = 0
    for start in range(0, len(x) - win, win // 2):
        seg = x[start:start + win] * np.hanning(win)
        spec = np.abs(np.rfft(seg)) if hasattr(np, "rfft") else np.abs(np.fft.rfft(seg))
        fr = np.fft.rfftfreq(win, 1.0 / sr)
        for k in range(1, n_harm + 1):
            target = f0 * k
            if target >= sr / 2:
                break
            # Peak-pick in a narrow window around the expected harmonic.
            band = np.where((fr > target * 0.97) & (fr < target * 1.03))[0]
            if len(band):
                amps[k - 1] += spec[band].max()
        count += 1
    if count:
        amps /= count
    return amps


def main():
    x, sr = load(REF)
    dur = len(x) / sr
    print("reference: %.2f s @ %d Hz  peak=%.3f  rms=%.4f"
          % (dur, sr, np.abs(x).max(), np.sqrt((x ** 2).mean())))

    # ── firing fundamental over time ───────────────────────────────────────
    times, f0 = fundamental_track(x, sr)
    good = f0[np.isfinite(f0)]
    f0_med = float(np.median(good))
    print("\nfiring fundamental: median %.1f Hz  range %.1f-%.1f Hz"
          % (f0_med, np.percentile(good, 5), np.percentile(good, 95)))
    # V6 four-stroke fires 3x per crank rev -> rpm = f_firing / 3 * 60
    print("  implies RPM: median %.0f  range %.0f-%.0f"
          % (f0_med / 3 * 60,
             np.percentile(good, 5) / 3 * 60,
             np.percentile(good, 95) / 3 * 60))

    # ── harmonic amplitude profile ────────────────────────────────────────
    amps = harmonic_profile(x, sr, f0_med)
    amps_n = amps / (amps.max() or 1.0)
    print("\nharmonic profile (normalised):")
    for k, a in enumerate(amps_n, start=1):
        if a > 0.005:
            print("  h%-2d %5.3f %s" % (k, a, "#" * int(a * 45)))

    # Fit amplitude ~ k^-alpha over the harmonics that carry real energy.
    ks = np.arange(1, len(amps_n) + 1)
    mask = amps_n > 0.02
    if mask.sum() >= 3:
        alpha = -np.polyfit(np.log(ks[mask]), np.log(amps_n[mask]), 1)[0]
    else:
        alpha = 1.0
    odd = amps_n[0::2].sum()
    even = amps_n[1::2].sum()
    print("\nroll-off exponent alpha = %.3f   (synth currently uses 0.85)" % alpha)
    print("odd/even harmonic energy ratio = %.3f" % (odd / (even + 1e-9)))

    # ── spectral shape ────────────────────────────────────────────────────
    fr, psd = signal.welch(x, sr, nperseg=8192)
    centroid = float((fr * psd).sum() / psd.sum())
    print("\nspectral centroid = %.0f Hz" % centroid)

    bands = [(20, 80), (80, 200), (200, 500), (500, 1200),
             (1200, 3000), (3000, 8000), (8000, 16000), (16000, 24000)]
    total = psd.sum()
    band_frac = {}
    print("band energy distribution:")
    for lo, hi in bands:
        m = (fr >= lo) & (fr < hi)
        frac = float(psd[m].sum() / total)
        band_frac["%d-%d" % (lo, hi)] = frac
        print("  %5d-%-5d Hz  %5.1f%%  %s"
              % (lo, hi, frac * 100, "#" * int(frac * 100)))

    # ── tonal vs broadband ────────────────────────────────────────────────
    # Compare the raw spectrum against a median-filtered (noise-floor) version.
    sm = signal.medfilt(psd, kernel_size=31)
    tonal = float(np.clip(psd - sm, 0, None).sum() / total)
    print("\ntonal (harmonic) fraction = %.1f%%   broadband = %.1f%%"
          % (tonal * 100, (1 - tonal) * 100))

    # ── turbo / intake whine: strong narrow peak above 1.5 kHz ────────────
    hi_mask = fr > 1500
    hi_fr, hi_psd = fr[hi_mask], psd[hi_mask]
    hi_sm = signal.medfilt(hi_psd, kernel_size=51)
    prom = hi_psd / (hi_sm + 1e-20)
    whine_i = int(np.argmax(prom))
    print("strongest high peak: %.0f Hz (%.1fx above local floor)"
          % (hi_fr[whine_i], prom[whine_i]))

    profile = {
        "duration": dur, "sr": sr,
        "f0_median": f0_med,
        "f0_p5": float(np.percentile(good, 5)),
        "f0_p95": float(np.percentile(good, 95)),
        "harmonics": amps_n.tolist(),
        "alpha": float(alpha),
        "odd_even_ratio": float(odd / (even + 1e-9)),
        "centroid": centroid,
        "bands": band_frac,
        "tonal_fraction": tonal,
        "whine_hz": float(hi_fr[whine_i]),
        "whine_prominence": float(prom[whine_i]),
        "rms": float(np.sqrt((x ** 2).mean())),
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as fh:
        json.dump(profile, fh, indent=2)
    print("\nwrote %s" % OUT)


if __name__ == "__main__":
    main()

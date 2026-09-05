"""Apply the real F1 engine recording to the three highlight clips.

The supplied recording is 10.06 s; the clips are 60.00 s, 20.25 s and 9.25 s.
Rather than dropping the clip in once and leaving silence, or looping it flatly
so it reads as an obvious repeat, this script:

  * builds a seamless loop  - the tail is crossfaded into the head, so modulo
    indexing never lands on a click
  * follows the on-screen speed - the read pointer advances at a rate derived
    from each shot's actual car speed, so the engine rises and falls with the
    picture instead of droning. This also breaks up the repeat, since each pass
    through the sample is played at a different rate
  * sets level per scene - gain comes from the real camera-to-car distance in
    the telemetry, scaled by camera type (onboard loudest, aerial quietest) and
    by act (the engine gives way to rain as the monsoon builds)
  * pans trackside pass-bys - level and stereo position track the car past the
    camera; riding cameras stay centred

The synthesised rain / wind / tyre / music stems are mixed underneath, with the
synth engine switched off so the two engines do not stack.

Usage:
    python scripts/synth_audio.py --reel full    --no-engine
    python scripts/synth_audio.py --reel pov     --no-engine
    python scripts/synth_audio.py --reel onboard --no-engine
    python scripts/apply_real_engine.py
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import wave

import numpy as np
from scipy import signal

SR = 48000
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_MP3 = os.path.join(ROOT, "public", "assets", "audio",
                       "wings_of_freedom-f1-racing-car-sound-430459.mp3")
REF_WAV = os.path.join(ROOT, "blender", "out", "ref", "f1_ref.wav")
TELEMETRY = os.path.join(ROOT, "blender", "out", "audio_telemetry.json")
OUT_DIR = os.path.join(ROOT, "blender", "out")

# Reel name -> (shot order, clip file, expected duration)
REELS = {
    "full":    ([1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17,
                 18, 19, 20, 21, 22, 23, 24],
                "sepang_cine_highlight.mp4", "sepang_highlight_final.mp4"),
    "pov":     ([7, 3, 9, 11, 14, 19, 16, 23, 21],
                "sepang_pov_reel.mp4", "sepang_pov_final.mp4"),
    "onboard": ([3, 11, 16, 21],
                "sepang_onboard_reel.mp4", "sepang_onboard_final.mp4"),
}

# Engine level by camera role. The reference recording was captured close to a
# car, so distant cameras need substantial reduction to stay believable.
ROLE_GAIN = {"onboard": 1.00, "chase": 0.82, "tyre": 0.95,
             "trackside_close": 0.88, "trackside_far": 0.62, "aerial": 0.34}

# The engine recedes as the storm takes over; rain carries act 3.
ACT_GAIN = {1: 1.00, 2: 0.88, 3: 0.72}


# ─────────────────────────────────────────────────────────────────────────────
# helpers
# ─────────────────────────────────────────────────────────────────────────────

def find_ffmpeg(name="ffmpeg"):
    from shutil import which
    p = which(name)
    if p:
        return p
    base = os.path.join(os.environ.get("LOCALAPPDATA", ""),
                        "Microsoft", "WinGet", "Packages")
    for root, _dirs, files in os.walk(base):
        if name + ".exe" in files:
            return os.path.join(root, name + ".exe")
    raise SystemExit("could not locate %s" % name)


def ensure_ref_wav():
    if os.path.exists(REF_WAV):
        return
    if not os.path.exists(SRC_MP3):
        raise SystemExit("missing source mp3: %s" % SRC_MP3)
    os.makedirs(os.path.dirname(REF_WAV), exist_ok=True)
    subprocess.run([find_ffmpeg(), "-y", "-loglevel", "error", "-i", SRC_MP3,
                    "-ac", "1", "-ar", str(SR), "-c:a", "pcm_s16le", REF_WAV],
                   check=True)
    print("decoded reference mp3 -> %s" % REF_WAV)


def load_wav(path):
    with wave.open(path, "rb") as w:
        sr, n, ch = w.getframerate(), w.getnframes(), w.getnchannels()
        raw = w.readframes(n)
    x = np.frombuffer(raw, dtype="<i2").astype(np.float64) / 32768.0
    if ch > 1:
        x = x.reshape(-1, ch)
    return x, sr


def write_wav(path, left, right):
    data = np.clip(np.stack([left, right], axis=1), -1.0, 1.0)
    pcm = (data * 32767.0).astype("<i2")
    with wave.open(path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())


def smooth(x, ms=25.0):
    if len(x) < 2:
        return x
    a = np.exp(-1.0 / (SR * ms / 1000.0))
    return signal.lfilter([1 - a], [1, -a], x)


def upsample(values, n_out):
    v = np.asarray(values, dtype=np.float64)
    if len(v) < 2:
        return np.full(n_out, v[0] if len(v) else 0.0)
    return np.interp(np.linspace(0, 1, n_out), np.linspace(0, 1, len(v)), v)


def make_seamless(x, xfade_s=0.35):
    """Crossfade the tail into the head so modulo indexing loops cleanly."""
    k = int(SR * xfade_s)
    if len(x) <= 2 * k:
        return x
    head, tail = x[:k], x[-k:]
    ramp = np.linspace(0.0, 1.0, k)
    blended = tail * (1.0 - ramp) + head * ramp
    return np.concatenate([blended, x[k:-k]])


def role_of(shot):
    """Classify the camera so its engine level matches what is on screen."""
    label, kind = shot["label"], shot["kind"]
    mean_d = float(np.mean([f["dist"] for f in shot["frames"]]))
    if "tyre" in label:
        return "tyre"
    if "onboard" in label:
        return "onboard"
    if kind == "RIDER":
        return "chase"
    if mean_d > 80.0:
        return "aerial"
    return "trackside_close" if mean_d < 30.0 else "trackside_far"


# ─────────────────────────────────────────────────────────────────────────────
# engine bed
# ─────────────────────────────────────────────────────────────────────────────

def engine_for_shot(loop, shot, fps, read_start):
    """One shot of real-recording engine, speed-driven and distance-levelled.

    Returns (left, right, next_read_position). The read position carries across
    shots so the sample keeps advancing rather than restarting each cut.
    """
    frames = shot["frames"]
    n = int(round(len(frames) / fps * SR))

    speed = smooth(upsample([f["speed"] for f in frames], n), 40.0)
    dist = smooth(upsample([f["dist"] for f in frames], n), 60.0)
    vrad = smooth(upsample([f["vrad"] for f in frames], n), 90.0)

    # ── playback rate follows road speed ─────────────────────────────────
    # The reference sits around 9,100 RPM at its median. Mapping speed to a
    # modest rate range keeps it recognisably the same engine while letting it
    # rev and fall with the footage.
    speed_kmh = speed * 3.6
    rate = np.clip(0.72 + (speed_kmh / 300.0) * 0.62, 0.70, 1.42)
    rate = smooth(rate, 120.0)

    # Integrate the rate to get a fractional read pointer, then wrap.
    read = read_start + np.cumsum(rate)
    idx = np.mod(read, len(loop) - 2)
    i0 = idx.astype(np.int64)
    frac = idx - i0
    body = loop[i0] * (1.0 - frac) + loop[i0 + 1] * frac
    next_read = float(read[-1])

    # ── level from real camera distance ──────────────────────────────────
    role = role_of(shot)
    d = np.clip(dist, 0.8, None)
    # Riding cameras hold a fixed distance, so their 1/d term is flat; trackside
    # cameras get the natural swell as the car approaches and passes.
    atten = 1.0 / (1.0 + (d / 14.0) ** 1.25)
    atten = atten / (np.percentile(atten, 95) or 1.0)     # normalise per shot
    atten = np.clip(atten, 0.0, 1.35)

    gain = ROLE_GAIN[role] * ACT_GAIN[shot["act"]]
    body = body * atten * gain

    # Air absorption with distance: distant engines lose their top end.
    cutoff = float(np.clip(15000.0 - np.mean(d) * 70.0, 1200.0, 15000.0))
    b, a = signal.butter(2, cutoff / (SR * 0.5), btype="low")
    body = signal.lfilter(b, a, body)

    # ── stereo ───────────────────────────────────────────────────────────
    if shot["kind"] == "TRACK":
        v = smooth(vrad, 150.0)
        scale = np.percentile(np.abs(v), 90) or 1.0
        pan = np.clip(v / (scale + 1e-9), -1.0, 1.0) * 0.7
    else:
        pan = np.zeros(n)
    left = body * np.clip(1.0 - pan * 0.5, 0.3, 1.3)
    right = body * np.clip(1.0 + pan * 0.5, 0.3, 1.3)

    # Short fades stop cuts from clicking.
    k = int(SR * 0.012)
    if 0 < k < n:
        ramp = np.linspace(0.0, 1.0, k)
        for ch in (left, right):
            ch[:k] *= ramp
            ch[-k:] *= ramp[::-1]

    return left, right, next_read, role


def build_engine_bed(loop, shots, fps):
    lefts, rights = [], []
    read = 0.0
    print("  %-22s %-16s %6s" % ("shot", "role", "sec"))
    for s in shots:
        L, R, read, role = engine_for_shot(loop, s, fps, read)
        lefts.append(L)
        rights.append(R)
        print("  %-22s %-16s %6.2f" % (s["label"], role, len(L) / SR))
    return np.concatenate(lefts), np.concatenate(rights)


# ─────────────────────────────────────────────────────────────────────────────
# mastering
# ─────────────────────────────────────────────────────────────────────────────

def compress(x, thresh=0.30, ratio=3.0, attack_ms=6.0, release_ms=150.0):
    env = np.abs(x)
    a = np.exp(-1.0 / (SR * attack_ms / 1000.0))
    r = np.exp(-1.0 / (SR * release_ms / 1000.0))
    sm = signal.lfilter([1 - r], [1, -r], env)
    sm = np.maximum(sm, signal.lfilter([1 - a], [1, -a], env))
    g = np.ones_like(x)
    over = sm > thresh
    g[over] = (thresh + (sm[over] - thresh) / ratio) / sm[over]
    return x * g


def main():
    ensure_ref_wav()

    ref, sr = load_wav(REF_WAV)
    if ref.ndim > 1:
        ref = ref.mean(axis=1)
    if sr != SR:
        raise SystemExit("reference must be %d Hz, got %d" % (SR, sr))
    loop = make_seamless(ref)
    print("reference: %.2f s -> seamless loop %.2f s"
          % (len(ref) / SR, len(loop) / SR))

    if not os.path.exists(TELEMETRY):
        raise SystemExit("missing telemetry: run extract_audio_telemetry.py")
    with open(TELEMETRY) as fh:
        tel = json.load(fh)
    fps = tel["fps"]
    by_n = {s["n"]: s for s in tel["shots"]}

    for reel, (order, clip, final) in REELS.items():
        shots = [by_n[i] for i in order if i in by_n]
        if not shots:
            print("skip %s: no telemetry" % reel)
            continue

        print("\n=== %s reel (%d shots) ===" % (reel, len(shots)))
        eL, eR = build_engine_bed(loop, shots, fps)
        n = len(eL)

        # Atmosphere stem, if it has been rendered.
        atmos = os.path.join(OUT_DIR, "sepang_audio_%s_atmos.wav" % reel)
        if os.path.exists(atmos):
            a, _sr = load_wav(atmos)
            aL = a[:, 0] if a.ndim > 1 else a
            aR = a[:, 1] if a.ndim > 1 else a
            m = min(n, len(aL))
            aL, aR = aL[:m], aR[:m]
            if m < n:
                aL = np.pad(aL, (0, n - m))
                aR = np.pad(aR, (0, n - m))
            print("  + atmosphere stem (rain / wind / music)")
        else:
            aL = aR = np.zeros(n)
            print("  ! no atmosphere stem; engine only")

        # Real engine leads, atmosphere sits under it.
        L = eL * 0.92 + aL * 0.55
        R = eR * 0.92 + aR * 0.55

        shared = max(float(np.max(np.abs(L))), float(np.max(np.abs(R)))) or 1.0
        L, R = compress(L / shared), compress(R / shared)
        peak = max(float(np.max(np.abs(L))), float(np.max(np.abs(R)))) or 1.0
        L, R = L * (0.97 / peak), R * (0.97 / peak)
        L, R = np.tanh(L * 1.03) * 0.985, np.tanh(R * 1.03) * 0.985

        out = os.path.join(OUT_DIR, "sepang_real_%s.wav" % reel)
        write_wav(out, L, R)
        print("  wrote %s  (%.2f s, target clip %s)"
              % (os.path.basename(out), n / SR, clip))


if __name__ == "__main__":
    main()

"""Procedural audio for the Sepang cinematic highlight.

Everything here is synthesised from scratch, driven by the per-frame telemetry
that extract_audio_telemetry.py pulled out of the Blender scene. Nothing is
sampled from real recordings, so there are no licensing concerns, and because
engine pitch / Doppler / level all come from the actual on-screen car speeds
and camera distances, the mix stays locked to the picture.

Signal chain per shot
---------------------
  engine (hero + 2 rivals)  V6 firing-order harmonic stack, Doppler-shifted,
                            distance-attenuated and air-absorption filtered
  tyre / road               speed-scaled filtered noise, wetter in the rain
  wind                      speed-scaled low noise, strongest on onboard cams
  rain                      bandpass noise scaled by the sim's storm factor
  cicadas                   FM chirps, dry act only (Malaysian jungle)
  thunder                   low rumble bursts during the monsoon
  music bed                 sub drone + kick + rolling 16th bass, per act
  transitions               risers and impacts on the act boundaries
  master                    soft compression, limiter, gentle stereo width

Design values for the engine harmonics, turbo whistle, rain band and cicada FM
follow src/audio/SepangAudioEngine.js so the rendered audio matches the sound
the web build already establishes.

Usage:
    python scripts/synth_audio.py                # full 60 s highlight
    python scripts/synth_audio.py --reel pov     # the 20 s POV reel
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import wave

import numpy as np
from scipy import signal

SR = 48000
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TELEMETRY = os.path.join(ROOT, "blender", "out", "audio_telemetry.json")
REF_PROFILE = os.path.join(ROOT, "blender", "out", "ref", "f1_ref_profile.json")

SPEED_OF_SOUND = 343.0

# ─────────────────────────────────────────────────────────────────────────────
# reference engine fingerprint
# ─────────────────────────────────────────────────────────────────────────────
# Measured from the supplied F1 recording by scripts/analyze_ref_engine.py.
# These defaults are the measured values, used if the profile JSON is absent.
#
# What the measurement changed versus the original first-principles synth:
#   * h2 dominates, not h1. The fundamental sits at only 0.10 of h2, so the
#     series is built on firing/2 and the table lets h2 (the true firing
#     frequency) carry the energy, with a weak half-order beneath it. That
#     half-order is what gives a real engine its lumpiness.
#   * Harmonics roll off as k^-0.66, not k^-0.85: noticeably brighter.
#   * EVEN harmonics dominate (odd/even 0.68). The original boosted odd
#     harmonics by 1.25x, which was backwards.
#   * Only 31% of the energy is tonal; 69% is broadband turbulence. The
#     original was almost entirely tonal, which is why it read as synthetic.
#   * Energy centres on 200-500 Hz (52%) with a 892 Hz centroid, so the engine
#     is mid-focused rather than sub-heavy.
REF_DEFAULT = {
    "harmonics": [0.103, 1.000, 0.400, 0.257, 0.244, 0.183, 0.136, 0.119,
                  0.108, 0.115, 0.100, 0.085, 0.088, 0.087, 0.088, 0.071,
                  0.063, 0.060, 0.058, 0.059],
    "tonal_fraction": 0.315,
    "centroid": 892.0,
    "bands": {"20-80": 0.001, "80-200": 0.003, "200-500": 0.520,
              "500-1200": 0.328, "1200-3000": 0.102, "3000-8000": 0.042,
              "8000-16000": 0.004, "16000-24000": 0.0},
}


def load_ref_profile():
    if os.path.exists(REF_PROFILE):
        try:
            with open(REF_PROFILE) as fh:
                p = json.load(fh)
            if p.get("harmonics"):
                return p
        except (ValueError, OSError):
            pass
    return REF_DEFAULT


REF = load_ref_profile()
HARMONICS = np.asarray(REF["harmonics"], dtype=np.float64)
TONAL_FRACTION = float(REF.get("tonal_fraction", 0.315))
REF_BANDS = REF.get("bands", REF_DEFAULT["bands"])

# Shot order for each deliverable, mirroring the stitch scripts.
ORDER_FULL = list(range(1, 25))
ORDER_POV = [7, 3, 9, 11, 14, 19, 16, 23, 21]
ORDER_ONBOARD = [3, 11, 16, 21]

REEL_ORDERS = {"full": ORDER_FULL, "pov": ORDER_POV, "onboard": ORDER_ONBOARD}


# ─────────────────────────────────────────────────────────────────────────────
# helpers
# ─────────────────────────────────────────────────────────────────────────────

def upsample(values, n_out):
    """Linear-interpolate a per-frame control signal to audio rate."""
    v = np.asarray(values, dtype=np.float64)
    if len(v) == 1:
        return np.full(n_out, v[0])
    x_in = np.linspace(0.0, 1.0, len(v))
    x_out = np.linspace(0.0, 1.0, n_out)
    return np.interp(x_out, x_in, v)


def smooth(x, ms=12.0):
    """One-pole smoothing to stop control signals from zippering."""
    if len(x) < 2:
        return x
    a = np.exp(-1.0 / (SR * ms / 1000.0))
    return signal.lfilter([1 - a], [1, -a], x)


def noise(n, seed):
    return np.random.default_rng(seed).standard_normal(n)


def lp(x, cutoff, order=2):
    cutoff = float(np.clip(cutoff, 30.0, SR * 0.45))
    b, a = signal.butter(order, cutoff / (SR * 0.5), btype="low")
    return signal.lfilter(b, a, x)


def hp(x, cutoff, order=2):
    cutoff = float(np.clip(cutoff, 20.0, SR * 0.45))
    b, a = signal.butter(order, cutoff / (SR * 0.5), btype="high")
    return signal.lfilter(b, a, x)


def bp(x, lo, hi, order=2):
    lo = float(np.clip(lo, 20.0, SR * 0.44))
    hi = float(np.clip(hi, lo * 1.05, SR * 0.45))
    b, a = signal.butter(order, [lo / (SR * 0.5), hi / (SR * 0.5)], btype="band")
    return signal.lfilter(b, a, x)


def varying_lp(x, cutoff_curve, blocks=64):
    """Time-varying lowpass, applied blockwise.

    A true per-sample time-varying IIR would be sequential and slow in numpy;
    processing in blocks at the block's mean cutoff is inaudible here and fast.
    """
    n = len(x)
    out = np.zeros(n)
    edges = np.linspace(0, n, blocks + 1).astype(int)
    for i in range(blocks):
        a, b = edges[i], edges[i + 1]
        if b <= a:
            continue
        pad = min(a, 2048)
        seg = x[a - pad:b]
        filtered = lp(seg, float(np.mean(cutoff_curve[a:b])))
        out[a:b] = filtered[pad:]
    return out


def fade(x, ms_in=8.0, ms_out=8.0):
    n_in = int(SR * ms_in / 1000.0)
    n_out = int(SR * ms_out / 1000.0)
    y = x.copy()
    if n_in > 0 and n_in < len(y):
        y[:n_in] *= np.linspace(0.0, 1.0, n_in)
    if n_out > 0 and n_out < len(y):
        y[-n_out:] *= np.linspace(1.0, 0.0, n_out)
    return y


# ─────────────────────────────────────────────────────────────────────────────
# engine
# ─────────────────────────────────────────────────────────────────────────────

GEARS = [(0, 90), (80, 140), (130, 190), (180, 235),
         (225, 270), (260, 300), (290, 322), (315, 340)]   # km/h bands

# RPM band fitted to the reference recording. The measured dominant harmonic
# sits at ~457 Hz, which for a V6 firing 3x per revolution implies ~9100 RPM.
# The original 9000-15500 band averaged nearer 13000 and pushed the engine's
# energy up into 500-1200 Hz, where the reference puts only a third of its
# energy. This band keeps the firing frequency centred in 200-500 Hz.
RPM_MIN, RPM_MAX = 6200.0, 11800.0
RPM_IDLE = 3400.0


def rpm_from_speed(speed_kmh):
    """Map road speed to RPM through a gear model.

    The gear bands give the characteristic rise-and-drop on each upshift, which
    is most of what makes an engine read as an engine rather than a siren.
    """
    rpm = np.zeros_like(speed_kmh)
    for lo, hi in GEARS:
        band = (speed_kmh >= lo) & (speed_kmh < hi)
        if not np.any(band):
            continue
        frac = (speed_kmh[band] - lo) / max(hi - lo, 1e-6)
        rpm[band] = RPM_MIN + np.clip(frac, 0.0, 1.0) * (RPM_MAX - RPM_MIN)
    rpm[speed_kmh >= GEARS[-1][1]] = RPM_MAX
    rpm[rpm < RPM_IDLE] = RPM_IDLE
    return rpm


def ref_shaped_noise(n, seed):
    """Broadband noise shaped to the reference recording's band distribution.

    The real engine is 69% broadband. Reproducing that spectral envelope, rather
    than adding flat noise, is what makes the synthetic engine sit in the same
    tonal space as the recording.
    """
    src = noise(n, seed)
    out = np.zeros(n)
    for band, frac in REF_BANDS.items():
        if frac <= 1e-4:
            continue
        lo, hi = (float(v) for v in band.split("-"))
        hi = min(hi, SR * 0.45)
        if hi <= lo:
            continue
        # Amplitude scales as sqrt of the energy fraction.
        out += bp(src, lo, hi) * np.sqrt(frac)
    peak = np.max(np.abs(out)) or 1.0
    return out / peak


def engine_voice(speed, dist, vrad, seed, level=1.0):
    """One car's engine, fitted to the measured reference fingerprint.

    The harmonic series is built on firing/2 so that the measured table's h2 -
    the true V6 firing frequency - carries the energy, while h1 supplies the
    weak half-order component that makes a real engine sound lumpy rather than
    like a siren.
    """
    n = len(speed)
    speed_kmh = speed * 3.6
    rpm = smooth(rpm_from_speed(speed_kmh), 45.0)

    # V6 four-stroke: 3 firing events per crank revolution.
    firing = rpm / 60.0 * 3.0

    # Doppler. vrad > 0 means receding, which lowers the pitch.
    doppler = SPEED_OF_SOUND / np.clip(SPEED_OF_SOUND + vrad, 60.0, None)

    # Series base is half the firing frequency (see module notes).
    f_base = np.clip(firing * 0.5 * doppler, 10.0, SR * 0.2)
    phase = np.cumsum(2.0 * np.pi * f_base / SR)

    mean_base = float(np.mean(f_base))
    tonal = np.zeros(n)
    for k, amp in enumerate(HARMONICS, start=1):
        if amp < 0.004:
            continue
        if k * mean_base > SR * 0.45:
            break
        # Scattered phases stop the partials from summing into a buzzy click.
        tonal += amp * np.sin(k * phase + 1.7 * k)
    tonal /= (np.max(np.abs(tonal)) or 1.0)

    # Broadband turbulence, amplitude-modulated at the firing rate so the noise
    # breathes with the engine instead of sitting behind it as a static hiss.
    turb = ref_shaped_noise(n, seed + 17)
    am = 0.65 + 0.35 * np.sin(phase * 2.0)      # 2*base = firing rate
    turb = turb * am

    # Mix tonal against broadband. Biased further toward noise than the raw
    # 31/69 measurement, because the harmonic stack is far more sharply peaked
    # than a real engine's partials and therefore reads as more tonal than its
    # amplitude share suggests.
    a_t = np.sqrt(TONAL_FRACTION * 0.88)
    a_n = np.sqrt(1.0 - TONAL_FRACTION * 0.88)
    body = tonal * a_t + turb * a_n

    # Intake/turbo whine, kept modest: the reference puts only ~10% of its
    # energy in the 1.2-3 kHz band.
    whine_f = np.clip(1400.0 + (rpm / RPM_MAX) * 1200.0, 200.0, SR * 0.4) * doppler
    whine = 0.022 * np.sin(np.cumsum(2.0 * np.pi * whine_f / SR))
    body += whine * np.clip(rpm / RPM_MAX, 0.0, 1.0)

    # The reference rolls off hard above 3 kHz (only 4% of energy in 3-8 kHz).
    body = lp(body, 5200.0, order=2)

    # Distance: inverse falloff plus air absorption on the top end.
    d = np.clip(dist, 0.8, None)
    atten = 1.0 / (1.0 + (d / 6.0) ** 1.15)
    cutoff = np.clip(16000.0 - d * 78.0, 900.0, 16000.0)
    body = varying_lp(body, cutoff)

    return body * atten * level


def engine_pan(dist, vrad):
    """Stereo sweep for a trackside pass-by.

    Approaching cars sit to one side, receding to the other, crossing centre at
    the closest point. Derived from the sign of radial velocity so it lines up
    with the Doppler flip automatically.
    """
    v = smooth(vrad, 120.0)
    scale = np.percentile(np.abs(v), 90) or 1.0
    return np.clip(v / (scale + 1e-6), -1.0, 1.0) * 0.75


# ─────────────────────────────────────────────────────────────────────────────
# environment layers
# ─────────────────────────────────────────────────────────────────────────────

def tyre_layer(speed, storm, dist, seed):
    n = len(speed)
    sp = np.clip(speed / 90.0, 0.0, 1.6)
    src = noise(n, seed)
    dry = bp(src, 220.0, 2600.0) * 0.5
    # Wet running adds a broad hiss of standing-water spray.
    wet = bp(noise(n, seed + 3), 900.0, 9000.0) * 0.85
    mix = dry * (1.0 - 0.35 * storm) + wet * storm
    atten = 1.0 / (1.0 + (np.clip(dist, 0.8, None) / 9.0) ** 1.2)
    return mix * sp * atten


def wind_layer(speed, seed, strength):
    n = len(speed)
    sp = np.clip(speed / 80.0, 0.0, 1.8) ** 1.3
    w = lp(noise(n, seed), 700.0) * 1.4
    w += bp(noise(n, seed + 5), 700.0, 3000.0) * 0.35
    return w * sp * strength


def rain_layer(storm, seed, closeness):
    n = len(storm)
    if float(np.max(storm)) <= 1e-4:
        return np.zeros(n)
    # Bandpass-filtered noise around 1100 Hz, matching the web audio engine.
    body = bp(noise(n, seed), 500.0, 3000.0) * 1.0
    splatter = bp(noise(n, seed + 11), 3000.0, 11000.0) * (0.55 * closeness)
    drum = lp(noise(n, seed + 23), 180.0) * 0.30 * closeness
    return (body + splatter + drum) * storm


def cicada_layer(n, seed, level):
    """Malaysian jungle ambience: FM chirps around 4.5 kHz, dry act only."""
    if level <= 0.0:
        return np.zeros(n)
    t = np.arange(n) / SR
    lfo = np.sin(2.0 * np.pi * 8.0 * t)
    f = 4500.0 + 1200.0 * lfo
    tone = np.sin(np.cumsum(2.0 * np.pi * f / SR))
    # Gate into bursts so it shimmers instead of droning.
    gate = (0.5 + 0.5 * np.sin(2.0 * np.pi * 0.7 * t)) ** 3
    warble = 0.6 + 0.4 * np.abs(noise(n, seed) * 0.2)
    return tone * gate * warble * level


def thunder_layer(n, seed, level, count=3):
    if level <= 0.0:
        return np.zeros(n)
    rng = np.random.default_rng(seed)
    out = np.zeros(n)
    for _ in range(count):
        start = rng.integers(0, max(n - SR * 2, 1))
        dur = int(SR * rng.uniform(1.1, 2.2))
        dur = min(dur, n - start)
        if dur <= 0:
            continue
        env = np.exp(-np.linspace(0.0, 5.0, dur)) * rng.uniform(0.6, 1.0)
        crack = lp(noise(dur, int(rng.integers(0, 1 << 30))), 140.0) * 3.0
        rumble = lp(noise(dur, int(rng.integers(0, 1 << 30))), 60.0) * 4.0
        out[start:start + dur] += (crack + rumble) * env
    return out * level


# ─────────────────────────────────────────────────────────────────────────────
# music bed
# ─────────────────────────────────────────────────────────────────────────────

def music_bed(n, act_curve, bpm=140.0, seed=7):
    """Sub drone + kick + rolling 16th bass, intensity following the act curve.

    Follows the synthwave shape of the project's web audio engine: four-on-the-
    floor kick and a driving sixteenth-note bass.
    """
    t = np.arange(n) / SR
    out = np.zeros(n)

    # Sustained sub drone, rising through the film. Kept low: the reference
    # engine puts only ~0.4% of its energy below 200 Hz, and an earlier mix at
    # 0.30 made the whole film sub-heavy relative to it.
    drone = (0.6 * np.sin(2.0 * np.pi * 55.0 * t)
             + 0.4 * np.sin(2.0 * np.pi * 82.5 * t + 0.4))
    drone += 0.25 * lp(noise(n, seed), 90.0)
    out += drone * 0.12 * act_curve

    beat = 60.0 / bpm
    step = beat / 4.0
    n_steps = int(n / SR / step)
    # A minor-ish rolling pattern; keeps momentum without fighting the engines.
    notes = [55.0, 55.0, 82.5, 55.0, 65.4, 55.0, 98.0, 82.5]

    for i in range(n_steps):
        s = int(i * step * SR)
        if s >= n:
            break
        intensity = act_curve[min(s, n - 1)]

        # Kick on every beat.
        if i % 4 == 0:
            dur = min(int(SR * 0.17), n - s)
            if dur > 0:
                env = np.exp(-np.linspace(0.0, 7.0, dur))
                f = 140.0 * np.exp(-np.linspace(0.0, 1.6, dur))
                out[s:s + dur] += (np.sin(np.cumsum(2.0 * np.pi * f / SR))
                                   * env * 0.55 * intensity)

        # Sixteenth bass.
        dur = min(int(SR * step * 0.9), n - s)
        if dur > 0:
            env = np.exp(-np.linspace(0.0, 3.2, dur))
            f = notes[i % len(notes)]
            saw = signal.sawtooth(2.0 * np.pi * f * np.arange(dur) / SR) \
                if hasattr(signal, "sawtooth") else \
                2.0 * ((f * np.arange(dur) / SR) % 1.0) - 1.0
            out[s:s + dur] += lp(saw * env, 400.0) * 0.22 * intensity

        # Off-beat hat for drive, only once the storm arrives.
        if i % 2 == 1:
            dur = min(int(SR * 0.05), n - s)
            if dur > 0:
                env = np.exp(-np.linspace(0.0, 9.0, dur))
                out[s:s + dur] += (hp(noise(dur, seed + i), 6000.0)
                                   * env * 0.10 * intensity)
    return out


def riser(n_total, at_sample, dur_s=1.6, level=0.5):
    """Upward noise sweep + impact, for act transitions."""
    out = np.zeros(n_total)
    dur = int(SR * dur_s)
    s = max(0, at_sample - dur)
    dur = min(dur, n_total - s)
    if dur <= 0:
        return out
    env = np.linspace(0.0, 1.0, dur) ** 2.2
    cutoff = np.linspace(400.0, 9000.0, dur)
    swept = varying_lp(noise(dur, 91), cutoff, blocks=24)
    out[s:s + dur] += swept * env * level

    # Impact on the downbeat.
    imp = min(int(SR * 0.8), n_total - at_sample)
    if imp > 0:
        e = np.exp(-np.linspace(0.0, 6.0, imp))
        f = 90.0 * np.exp(-np.linspace(0.0, 2.0, imp))
        out[at_sample:at_sample + imp] += (
            np.sin(np.cumsum(2.0 * np.pi * f / SR)) * e * level * 1.5)
        out[at_sample:at_sample + imp] += lp(noise(imp, 55), 200.0) * e * level
    return out


# ─────────────────────────────────────────────────────────────────────────────
# mastering
# ─────────────────────────────────────────────────────────────────────────────

def compress(x, thresh=0.28, ratio=3.4, attack_ms=6.0, release_ms=140.0):
    env = np.abs(x)
    a = np.exp(-1.0 / (SR * attack_ms / 1000.0))
    r = np.exp(-1.0 / (SR * release_ms / 1000.0))
    # Fast attack / slow release envelope follower.
    smoothed = signal.lfilter([1 - r], [1, -r], env)
    smoothed = np.maximum(smoothed, signal.lfilter([1 - a], [1, -a], env))
    gain = np.ones_like(x)
    over = smoothed > thresh
    gain[over] = (thresh + (smoothed[over] - thresh) / ratio) / smoothed[over]
    return x * gain


def limit(x, ceiling=0.97):
    """Normalise to the ceiling in both directions, then soft-clip.

    Scaling up as well as down matters here: after compression the mix peaked
    around 0.75, which left the delivered file needlessly quiet.
    """
    peak = float(np.max(np.abs(x))) or 1.0
    x = x * (ceiling / peak)
    return np.tanh(x * 1.04) * 0.985


def write_wav(path, left, right):
    data = np.stack([left, right], axis=1)
    data = np.clip(data, -1.0, 1.0)
    pcm = (data * 32767.0).astype("<i2")
    with wave.open(path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())


# ─────────────────────────────────────────────────────────────────────────────
# per-shot render
# ─────────────────────────────────────────────────────────────────────────────

def render_shot(shot, fps, include_engine=True):
    """Render one shot's audio.

    `include_engine=False` yields an atmosphere-only stem (tyre, wind, rain,
    cicadas, thunder). That is used when the real F1 recording supplies the
    engine instead of the synthesiser, so the two do not stack up.
    """
    frames = shot["frames"]
    n = int(round(len(frames) / fps * SR))
    kind = shot["kind"]
    act = shot["act"]

    speed = smooth(upsample([f["speed"] for f in frames], n), 30.0)
    dist = smooth(upsample([f["dist"] for f in frames], n), 40.0)
    vrad = smooth(upsample([f["vrad"] for f in frames], n), 60.0)
    storm = smooth(upsample([f["storm"] for f in frames], n), 200.0)

    seed = shot["n"] * 1000

    # Onboard and chase cameras ride with the car: close, loud, wind-heavy.
    onboard = kind == "RIDER" and dist.mean() < 2.5
    closeness = float(np.clip(3.0 / max(dist.mean(), 0.8), 0.0, 1.0))

    if include_engine:
        hero = engine_voice(speed, dist, vrad, seed, level=1.0)
        rivals = np.zeros(n)
        if frames[0].get("rivals"):
            for ri in range(len(frames[0]["rivals"])):
                r_d = smooth(upsample([f["rivals"][ri]["dist"] for f in frames], n), 40.0)
                r_v = smooth(upsample([f["rivals"][ri]["vrad"] for f in frames], n), 60.0)
                r_s = smooth(upsample([f["rivals"][ri]["speed"] for f in frames], n), 30.0)
                rivals += engine_voice(r_s, r_d, r_v, seed + 300 * (ri + 1),
                                       level=0.55)
    else:
        hero = np.zeros(n)
        rivals = np.zeros(n)

    tyre = tyre_layer(speed, storm, dist, seed + 41)
    wind = wind_layer(speed, seed + 61, strength=0.55 if onboard else 0.16)
    rain = rain_layer(storm, seed + 71, closeness if onboard else 0.45)
    cicada = cicada_layer(n, seed + 83, level=0.045 if act == 1 else 0.0)
    thunder = thunder_layer(n, seed + 97,
                            level=0.55 if act == 3 else (0.2 if act == 2 else 0.0),
                            count=2 if act == 3 else 1)

    # Onboard sits inside the car: helmet/bodywork dulls the top end and the
    # engine dominates. Trackside is airier and more distant.
    if onboard:
        engine_mix = hero * 1.15 + rivals * 0.5
        engine_mix = lp(engine_mix, 7200.0)
        body = engine_mix + tyre * 0.85 + wind * 1.0 + rain * 0.95
    else:
        engine_mix = hero + rivals
        body = engine_mix + tyre * 0.7 + wind * 0.6 + rain * 0.8

    body = body + cicada + thunder * 0.5

    # Stereo. Trackside pans across the pass-by; riding cams stay wide but centred.
    if kind == "TRACK":
        pan = engine_pan(dist, vrad)
    else:
        pan = np.full(n, 0.0)
    left = body * np.clip(0.5 * (1.0 - pan) + 0.5, 0.25, 1.25)
    right = body * np.clip(0.5 * (1.0 + pan) + 0.5, 0.25, 1.25)

    # Slight decorrelation for width.
    d = int(SR * 0.008)
    right = np.concatenate([np.zeros(d), right[:-d]]) * 0.85 + right * 0.15

    return fade(left, 12.0, 18.0), fade(right, 12.0, 18.0)


def render_engine_only(shot, fps):
    """Just the hero engine, no environment / bed / transitions.

    Used to verify the engine timbre against the reference recording in
    isolation, since the music bed and rain layers legitimately shift the full
    mix's spectrum away from a bare engine recording.
    """
    frames = shot["frames"]
    n = int(round(len(frames) / fps * SR))
    speed = smooth(upsample([f["speed"] for f in frames], n), 30.0)
    dist = smooth(upsample([f["dist"] for f in frames], n), 40.0)
    vrad = smooth(upsample([f["vrad"] for f in frames], n), 60.0)
    return engine_voice(speed, dist, vrad, shot["n"] * 1000, level=1.0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reel", choices=["full", "pov", "onboard"], default="full")
    ap.add_argument("--engine-only", action="store_true",
                    help="render the bare engine layer for spectral comparison")
    ap.add_argument("--no-engine", action="store_true",
                    help="atmosphere only (rain/wind/tyre/music), no synth engine; "
                         "use when the real recording supplies the engine")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    if args.engine_only:
        if not os.path.exists(TELEMETRY):
            sys.exit("missing telemetry")
        with open(TELEMETRY) as fh:
            tel = json.load(fh)
        by_n = {s["n"]: s for s in tel["shots"]}
        # Dry act only: the closest analogue to a dry-weather engine recording.
        dry = [by_n[i] for i in (7, 3, 4, 5, 2) if i in by_n]
        chunks = [render_engine_only(s, tel["fps"]) for s in dry]
        mono = np.concatenate(chunks)
        mono = mono / (np.max(np.abs(mono)) or 1.0) * 0.9
        out = args.out or os.path.join(ROOT, "blender", "out",
                                       "sepang_engine_only.wav")
        write_wav(out, mono, mono)
        print("wrote %s  (%.2f s, engine layer only)" % (out, len(mono) / SR))
        return

    if not os.path.exists(TELEMETRY):
        sys.exit("missing telemetry: run blender/extract_audio_telemetry.py first")

    with open(TELEMETRY) as fh:
        tel = json.load(fh)
    fps = tel["fps"]
    by_n = {s["n"]: s for s in tel["shots"]}

    order = REEL_ORDERS[args.reel]
    shots = [by_n[i] for i in order if i in by_n]

    print("synthesising %s reel: %d shots%s"
          % (args.reel, len(shots), "  (atmosphere only)" if args.no_engine else ""))

    lefts, rights, acts, bounds = [], [], [], []
    cursor = 0
    for s in shots:
        L, R = render_shot(s, fps, include_engine=not args.no_engine)
        lefts.append(L)
        rights.append(R)
        acts.append((cursor, cursor + len(L), s["act"]))
        cursor += len(L)
        bounds.append(cursor)
        print("  %-22s act%d %5.2fs" % (s["label"], s["act"], len(L) / SR))

    left = np.concatenate(lefts)
    right = np.concatenate(rights)
    n = len(left)

    # Intensity curve for the music bed, stepping up with each act.
    act_level = {1: 0.45, 2: 0.72, 3: 1.0}
    curve = np.zeros(n)
    for a, b, act in acts:
        curve[a:b] = act_level[act]
    curve = smooth(curve, 900.0)

    bed = music_bed(n, curve)

    # Risers on the act transitions.
    trans = np.zeros(n)
    prev = acts[0][2]
    for a, _b, act in acts:
        if act != prev:
            trans += riser(n, a, dur_s=1.8, level=0.55)
            prev = act
    trans += riser(n, 0, dur_s=0.9, level=0.35)   # opening hit

    # Engines carry the mix; the bed sits under them rather than competing.
    left = left * 1.00 + bed * 0.34 + trans * 0.60
    right = right * 1.00 + bed * 0.34 + trans * 0.60

    left = compress(hp(left, 28.0))
    right = compress(hp(right, 28.0))

    # Normalise both channels by a shared peak so the stereo balance is not
    # skewed by whichever side happened to be louder.
    shared = max(float(np.max(np.abs(left))), float(np.max(np.abs(right)))) or 1.0
    left, right = left / shared, right / shared
    left, right = limit(left), limit(right)

    suffix = "_atmos" if args.no_engine else ""
    out = args.out or os.path.join(
        ROOT, "blender", "out",
        "sepang_audio_%s%s.wav" % (args.reel, suffix))
    write_wav(out, left, right)
    print("\nwrote %s  (%.2f s, %.1f MB)"
          % (out, n / SR, os.path.getsize(out) / 1e6))


if __name__ == "__main__":
    main()

/**
 * Clip layer.
 *
 * The three delivered mp4s are exact frame-for-frame concatenations of the 24
 * shots rendered by blender/cine_render.py, so the per-frame simulation state
 * captured by blender/extract_audio_telemetry.py lines up with the picture.
 *
 * That means the HUD is not decoration: speed and storm state are read straight
 * off the trace that synthesised the engine audio. Gear, rpm, throttle and brake
 * are derived from that speed trace here, and labelled as derived wherever they
 * appear on screen.
 */

import telemetry from "./clip-telemetry.json";

export const TELEMETRY = telemetry;
export const FPS = telemetry.fps;

export const CLIPS = {
  onboard: {
    key: "onboard",
    src: "/assets/vid/sepang_onboard_final.mp4",
    poster: "/assets/img/posters/onboard_poster.webp",
    edit: "onboard",
    durationInFrames: telemetry.edits.onboard.totalFrames,
    width: 1920,
    height: 1080,
    kicker: "Onboard",
    title: "Four onboards, one storm",
    blurb:
      "Dry, first rain, monsoon, climax. The cockpit shots from all three acts cut together in story order.",
    runtime: "0:09",
    audio: "Real-engine mix, muted until you ask for it"
  },
  pov: {
    key: "pov",
    src: "/assets/vid/sepang_pov_final.mp4",
    poster: "/assets/img/posters/pov_poster.webp",
    edit: "pov",
    durationInFrames: telemetry.edits.pov.totalFrames,
    width: 1920,
    height: 1080,
    kicker: "Driver's eye",
    title: "Riding it out",
    blurb:
      "Chase and onboard alternating through the same chronology — watching the car, then riding in it, as the weather turns.",
    runtime: "0:20",
    audio: "Real-engine mix"
  },
  highlight: {
    key: "highlight",
    src: "/assets/vid/sepang_highlight_final.mp4",
    poster: "/assets/img/posters/highlight_poster.webp",
    edit: "highlight",
    durationInFrames: telemetry.edits.highlight.totalFrames,
    width: 1920,
    height: 1080,
    kicker: "The full film",
    title: "Sepang, three acts",
    blurb:
      "All 24 shots. Act one is dry power, act two is the sky breaking, act three is the monsoon that ends it.",
    runtime: "1:00",
    audio: "Real-engine mix"
  }
};

export const CLIP_ORDER = ["onboard", "pov", "highlight"];

export const ACTS = [
  { act: 1, name: "Dry power", condition: "DRY", blurb: "54 C asphalt, clean air, everything on the limit of the tyre." },
  { act: 2, name: "The sky breaks", condition: "RAIN", blurb: "Sector 2 goes wet first. Spray, then the crossover call." },
  { act: 3, name: "Monsoon", condition: "MONSOON", blurb: "Standing water past the aquaplaning threshold and a red flag in play." }
];

/* ------------------------------------------------------------------ *
 * frame lookup
 * ------------------------------------------------------------------ */

/** Which cut of an edit a frame falls in, and how far into it. */
export function cutAtFrame(editKey, frame) {
  const cuts = TELEMETRY.edits[editKey].cuts;
  const total = TELEMETRY.edits[editKey].totalFrames;
  const f = ((frame % total) + total) % total;
  for (let i = cuts.length - 1; i >= 0; i -= 1) {
    if (f >= cuts[i].start) {
      return {
        index: i,
        cut: cuts[i],
        shot: TELEMETRY.shots[String(cuts[i].shot)],
        localFrame: f - cuts[i].start,
        isFirstFrame: f === cuts[i].start,
        framesIntoClip: f,
        cutCount: cuts.length
      };
    }
  }
  const first = cuts[0];
  return {
    index: 0,
    cut: first,
    shot: TELEMETRY.shots[String(first.shot)],
    localFrame: 0,
    isFirstFrame: true,
    framesIntoClip: f,
    cutCount: cuts.length
  };
}

const GEAR_BANDS = [
  [0, 80, 1],
  [80, 120, 2],
  [120, 162, 3],
  [162, 205, 4],
  [205, 250, 5],
  [250, 291, 6],
  [291, 326, 7],
  [326, 400, 8]
];

function gearFor(kph) {
  for (const [lo, hi, g] of GEAR_BANDS) {
    if (kph < hi) return { gear: g, lo, hi };
  }
  const last = GEAR_BANDS[GEAR_BANDS.length - 1];
  return { gear: last[2], lo: last[0], hi: last[1] };
}

/**
 * Full HUD sample for a frame of an edit.
 *
 * speedKph and storm are read. gear, rpm, throttle and brake are derived:
 * gear from a fixed set of speed bands, rpm from where the speed sits inside
 * that band, and the pedals from the sign and size of the acceleration over a
 * three-frame window.
 */
export function sampleAtFrame(editKey, frame) {
  const ctx = cutAtFrame(editKey, frame);
  const { shot, localFrame } = ctx;
  const speeds = shot.speedKph;
  const n = speeds.length;
  const i = Math.min(n - 1, Math.max(0, localFrame));

  const speedKph = speeds[i];
  const prev = speeds[Math.max(0, i - 3)];
  const next = speeds[Math.min(n - 1, i + 3)];
  // kph per second, using the same 24 fps cadence as the picture
  const dv = ((next - prev) / 6) * FPS;
  const accelMs2 = dv / 3.6;

  const { gear, lo, hi } = gearFor(speedKph);
  const within = hi > lo ? (speedKph - lo) / (hi - lo) : 0.5;
  const rpm = Math.round(9200 + within * 4300);

  const throttle = Math.max(0, Math.min(1, accelMs2 / 7 + (Math.abs(accelMs2) < 0.6 ? 0.55 : 0)));
  const brake = Math.max(0, Math.min(1, -accelMs2 / 22));

  const storm = shot.storm[Math.min(shot.storm.length - 1, i)];
  const camRangeM = shot.camRangeM[Math.min(shot.camRangeM.length - 1, i)];

  return {
    ...ctx,
    speedKph,
    accelMs2,
    gear,
    rpm,
    rpmPct: Math.max(0, Math.min(1, (rpm - 9200) / 4300)),
    throttle,
    brake,
    storm,
    camRangeM,
    drs:
      storm > 0.25
        ? "DISABLED"
        : speedKph > 285 && accelMs2 > 0
          ? "ACTIVE"
          : "AVAILABLE",
    condition: shot.condition,
    shotTitle: shot.title,
    corner: shot.corner,
    lens: shot.lens,
    act: shot.act
  };
}

/** Full speed trace for an edit, for the trace strip under the player. */
export function speedTrace(editKey) {
  const { cuts, totalFrames } = TELEMETRY.edits[editKey];
  const out = new Array(totalFrames);
  for (const cut of cuts) {
    const shot = TELEMETRY.shots[String(cut.shot)];
    for (let i = 0; i < cut.frames; i += 1) {
      out[cut.start + i] = shot.speedKph[Math.min(shot.speedKph.length - 1, i)];
    }
  }
  return out;
}

export function clipStats(editKey) {
  const trace = speedTrace(editKey);
  const { cuts, totalFrames } = TELEMETRY.edits[editKey];
  return {
    frames: totalFrames,
    seconds: totalFrames / FPS,
    cuts: cuts.length,
    maxKph: Math.max(...trace),
    minKph: Math.min(...trace),
    avgKph: trace.reduce((a, b) => a + b, 0) / trace.length
  };
}

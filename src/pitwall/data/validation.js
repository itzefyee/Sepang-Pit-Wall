/**
 * Validation layer — the model's receipts.
 *
 * Every figure here is measured by running the models, not transcribed. The
 * historical checks are supplied only with facts knowable at the time (the grid,
 * the field's relative pace, the weather timeline); the simulation produces the
 * outcome.
 */

export const SCOREBOARD = [
  {
    v: "6 / 6",
    label: "Historical checks passed",
    note: "2001 Ferrari 1-2 recovery and the 2009 lap-31 abandonment",
    tone: "good"
  },
  {
    v: "0.419",
    unit: "s",
    label: "Pit-loss MAE",
    note: "Bar is under 0.5 s across 6000 sampled stops",
    tone: "good"
  },
  {
    v: "0.31",
    unit: "%",
    label: "Track length error",
    note: "Survey loop 5560.5 m against the homologated 5543 m",
    tone: "good"
  },
  {
    v: "0.38",
    unit: "%",
    label: "Race duration error",
    note: "Simulated 1:30:21.632 against the real 1:30:01",
    tone: "good"
  },
  {
    v: "+0.003",
    unit: "s",
    label: "Fastest race lap error",
    note: "Simulated 94.083 s against the real 94.080 s",
    tone: "good"
  },
  {
    v: "95.8",
    unit: "%",
    label: "Map registration inliers",
    note: "Centreline samples landing inside the reference track band",
    tone: "good"
  }
];

export const HISTORICAL_CHECKS = [
  { check: "2001 Ferrari 1-2 recovery", result: "PASS" },
  { check: "2001 winner is Schumacher", result: "PASS" },
  { check: "2009 race abandoned", result: "PASS" },
  { check: "2009 stopped within 3 laps of lap 31", result: "PASS" },
  { check: "2009 half points awarded", result: "PASS" },
  { check: "2009 winner is Button", result: "PASS" }
];

export const HISTORICAL_RACES = [
  {
    year: 2001,
    name: "2001 Malaysian Grand Prix",
    story:
      "A cloudburst on lap 3 pitched both Ferraris off at Turn 5. They pitted together for wets, rejoined 10th and 11th, and won anyway.",
    simTop5: ["MSC", "BAR", "COU", "RSC", "HAK"],
    realTop5: ["MSC", "BAR", "COU", "HAK", "HEI"],
    peakWaterMm: 6.3,
    matched: 3
  },
  {
    year: 2009,
    name: "2009 Malaysian Grand Prix",
    story:
      "A monsoon arriving with the sun going down. Red-flagged on lap 31 and never restarted — the only modern race to award half points.",
    simTop5: ["BUT", "VET", "TRU", "BAR", "GLO"],
    realTop5: ["BUT", "HEI", "GLO", "ROS", "ALO"],
    peakWaterMm: 5.7,
    redFlagLapSim: 30,
    redFlagLapReal: 31,
    halfPoints: true,
    matched: 1
  }
];

/** Dry reference race, full 56 laps. */
export const DRY_RACE_RESULT = [
  { pos: 1, code: "VER", driver: "Verstappen", team: "Red Bull", gap: "—", stops: 2, stints: "M20 M20 S16" },
  { pos: 2, code: "PIA", driver: "Piastri", team: "McLaren", gap: "+8.268", stops: 2, stints: "M20 M20 S16" },
  { pos: 3, code: "LEC", driver: "Leclerc", team: "Ferrari", gap: "+8.488", stops: 2, stints: "M20 M20 S16", hero: true },
  { pos: 4, code: "HAM", driver: "Hamilton", team: "Ferrari", gap: "+9.571", stops: 2, stints: "M20 M20 S16", hero: true },
  { pos: 5, code: "NOR", driver: "Norris", team: "McLaren", gap: "+11.925", stops: 2, stints: "M20 M20 S16" },
  { pos: 6, code: "RUS", driver: "Russell", team: "Mercedes", gap: "+19.213", stops: 2, stints: "M20 M20 S16" },
  { pos: 7, code: "TSU", driver: "Tsunoda", team: "Red Bull", gap: "+26.290", stops: 2, stints: "M20 M20 S16" },
  { pos: 8, code: "ANT", driver: "Antonelli", team: "Mercedes", gap: "+31.359", stops: 2, stints: "M20 M20 S16" },
  { pos: 9, code: "ALO", driver: "Alonso", team: "Aston Martin", gap: "+34.509", stops: 2, stints: "M20 M20 S16" },
  { pos: 10, code: "SAI", driver: "Sainz", team: "Williams", gap: "+48.200", stops: 2, stints: "M20 M20 S16" }
];

/** Where the model is still weakest. Kept on the page deliberately. */
export const OPEN_GAPS = [
  {
    title: "No optimised racing line",
    weight: "Biggest",
    body:
      "Corner speeds, sector times and the overall calibration factor are all computed on the survey centreline and reconciled with reality through one 0.9347 scale factor. A minimum-curvature line would make sector times independently verifiable instead of jointly calibrated."
  },
  {
    title: "Overtaking is resolved in the time domain",
    weight: "Second",
    body:
      "The race engine adjusts elapsed times rather than modelling track position, so it cannot represent a car stuck in dirty air behind a slower one for a whole stint. At Sepang that is often what actually decides the race."
  },
  {
    title: "The strategy optimiser ignores traffic",
    weight: "Third",
    body:
      "1146 plans are ranked on time alone. The optimiser cannot reason about emerging from the pit lane behind a train of cars, which is the real constraint on when you stop here."
  },
  {
    title: "Elevation is smoothed, not surveyed",
    weight: "Fourth",
    body:
      "SRTM 30 m is contaminated by the grandstand roofs beside the pit straight, so the 28.8 m elevation profile is smoothed over 100 m rather than trusted point by point. A surveyed gradient table would replace it."
  },
  {
    title: "The 2001 recovery is partly an input",
    weight: "Fifth",
    body:
      "Ferrari is given a shorter pit-wall reaction delay than the rest of the field. That is historically true, but it is an input rather than an emergent result, and positions 3 to 5 in both historical races still drift from the record."
  }
];

export const PROVENANCE = [
  {
    what: "Track geometry",
    detail:
      "OpenStreetMap raceway ways 23410503 and 144359489 (ODbL), resampled to 1386 points at 4 m and scaled 0.9999 to the homologated 5543 m."
  },
  {
    what: "Elevation",
    detail: "SRTM 30 m via opentopodata, sampled along the lap. 28.8 m span."
  },
  {
    what: "Turn numbering",
    detail:
      "Not hand-entered. The reference FIA-style circuit map is registered onto the centreline and its 15 circled labels are detected as ring-shaped blobs, then ordered along the lap. 95.8% registration inliers."
  },
  {
    what: "Footage",
    detail:
      "Rendered in Blender from the simulation's own car positions. 24 shots, 1440 frames at 24 fps, 1920 by 1080."
  },
  {
    what: "On-screen telemetry",
    detail:
      "Speed and storm state are read from blender/out/audio_telemetry.json, the same per-frame trace that synthesised the engine audio. Gear, rpm, throttle and brake are derived from that speed trace in the browser."
  },
  {
    what: "Reference circuit map",
    detail: "Wikimedia Commons."
  }
];

/**
 * Circuit layer.
 *
 * Geometry comes from the surveyed centreline (OpenStreetMap ODbL, resampled to
 * 1386 points at 4 m and scaled to the homologated 5543 m, elevation from SRTM
 * 30 m). Radii, heading changes, corner classifications and the corner notes are
 * all resolved by the survey pipeline, not typed in by hand.
 *
 * The driving layer on top — apex speed, gear, braking point, tyre load and the
 * coaching note — is the project's own corner model.
 */

import geometry from "./circuit-geometry.json";

export const GEO = geometry;

export const CIRCUIT = {
  name: "Petronas Sepang International Circuit",
  short: "Sepang",
  code: "SIC",
  country: "Malaysia",
  designer: "Hermann Tilke",
  opened: 1999,
  lengthM: GEO.lengthM,
  lengthKm: (GEO.lengthM / 1000).toFixed(3),
  turns: GEO.corners.length,
  laps: 56,
  raceDistanceKm: ((GEO.lengthM * 56) / 1000).toFixed(1),
  trackWidthM: GEO.trackWidthM,
  elevationSpanM: +(GEO.elevationRangeM[1] - GEO.elevationRangeM[0]).toFixed(1),
  mainStraightM: GEO.mainStraightM,
  backStraightM: GEO.backStraightM,
  pitOffsetM: GEO.pitOffsetM,
  drsZones: GEO.drsZones.length,
  direction: "Clockwise",
  surveyLengthM: GEO.rawOsmLengthM,
  surveyErrorPct: +(
    ((GEO.rawOsmLengthM - GEO.lengthM) / GEO.lengthM) *
    100
  ).toFixed(2),
  lapRecordRace: { time: "1:34.080", driver: "Sebastian Vettel", year: 2017 },
  polePb: { time: "1:30.076", driver: "Lewis Hamilton", year: 2017 },
  attribution: GEO.source
};

/**
 * Per-corner driving model, keyed by turn id and merged onto the surveyed
 * corner records. `brakeFromKph` is the entry speed the model brakes from,
 * `apexKph` the minimum speed through the corner.
 */
const DRIVING = {
  1: {
    apexKph: 85,
    brakeFromKph: 332,
    gear: 2,
    tyreLoad: 0.62,
    tyre: "Rear-left traction",
    difficulty: 4,
    overtaking: 5,
    coach:
      "The single biggest overtaking chance on the lap. Brake in a straight line from 330 to 85 kph while the track falls away from you, then be patient — the corner keeps turning for 192 degrees. Getting greedy on entry costs more than the place you were defending.",
    watch: "Lock-ups on the right-front under downhill braking."
  },
  2: {
    apexKph: 90,
    brakeFromKph: 118,
    gear: 2,
    tyreLoad: 0.55,
    tyre: "Front-left",
    difficulty: 3,
    overtaking: 2,
    coach:
      "A tight left immediately after the hairpin, still downhill and off camber. It is a compromise corner: sacrifice a little apex speed to get the car straight early, because the exit feeds a 300 m chute.",
    watch: "Understeer on entry from a Turn 1 exit taken too wide."
  },
  3: {
    apexKph: 220,
    brakeFromKph: 236,
    gear: 5,
    tyreLoad: 0.71,
    tyre: "Front-right",
    difficulty: 2,
    overtaking: 1,
    coach:
      "Barely a corner at racing speed — a 137 m radius right taken near full throttle. Treat it as a straight with a steering input and protect the front-right for what is coming in sector 2.",
    watch: "Drifting wide on exit and missing the Turn 4 braking reference."
  },
  4: {
    apexKph: 120,
    brakeFromKph: 246,
    gear: 3,
    tyreLoad: 0.6,
    tyre: "Front-left",
    difficulty: 3,
    overtaking: 3,
    coach:
      "A 90-degree technical right and the last easy braking zone before the fast stuff. This is where a car with good low-speed traction claws back what it loses through the esses.",
    watch: "Too much kerb on exit unsettles the car over the sector 1 line."
  },
  5: {
    apexKph: 245,
    brakeFromKph: 268,
    gear: 6,
    tyreLoad: 0.96,
    tyre: "Right-front",
    difficulty: 5,
    overtaking: 1,
    coach:
      "The corner that decides your tyre life. A 104 m radius left held at 245 kph puts sustained lateral load into the right-front for over three seconds. Every tenth you take here you pay back twice in stint length.",
    watch: "Right-front surface temperature. This is where blistering starts."
  },
  6: {
    apexKph: 235,
    brakeFromKph: 248,
    gear: 6,
    tyreLoad: 0.88,
    tyre: "Left-front",
    difficulty: 4,
    overtaking: 1,
    coach:
      "The load flicks from right to left with no recovery time. Commitment matters more than line: hesitate and the car never settles for the uphill complex.",
    watch: "Mid-corner snap as the aero platform unloads over the crest."
  },
  7: {
    apexKph: 180,
    brakeFromKph: 212,
    gear: 4,
    tyreLoad: 0.79,
    tyre: "Front-right",
    difficulty: 4,
    overtaking: 2,
    coach:
      "First apex of the uphill double right. Climbing helps you brake, so carry more speed than instinct says, but leave room — the second apex is tighter than it looks from here.",
    watch: "Running out of road on the exit of the second apex."
  },
  8: {
    apexKph: 195,
    brakeFromKph: 205,
    gear: 5,
    tyreLoad: 0.74,
    tyre: "Rear-left",
    difficulty: 4,
    overtaking: 2,
    coach:
      "A blind crest exit. The car goes light exactly when you want throttle. Unwind the wheel before you commit or the rear steps out at the top.",
    watch: "Traction loss on the crest in the damp."
  },
  9: {
    apexKph: 80,
    brakeFromKph: 258,
    gear: 2,
    tyreLoad: 0.58,
    tyre: "Front-left",
    difficulty: 5,
    overtaking: 4,
    coach:
      "Uphill, off camber, tightest radius on the lap at 16.5 m. The camber falls away from the apex so the front simply stops gripping if you ask too early. Late, slow, straight — then everything downhill is yours.",
    watch: "Front-left lock-up. Also the first place standing water pools."
  },
  10: {
    apexKph: 210,
    brakeFromKph: 224,
    gear: 5,
    tyreLoad: 0.77,
    tyre: "Front-right",
    difficulty: 3,
    overtaking: 2,
    coach:
      "Downhill and accelerating, which flatters the car. Use the gradient: get the power down early and let the descent do the work into Turn 11.",
    watch: "Over-slowing here loses time all the way to Turn 12."
  },
  11: {
    apexKph: 170,
    brakeFromKph: 216,
    gear: 4,
    tyreLoad: 0.85,
    tyre: "Right-front",
    difficulty: 4,
    overtaking: 2,
    coach:
      "The second-worst corner for degradation after Turn 5, and it arrives when the right-front is already hot. On a long stint this is the corner you give up first.",
    watch: "Graining on the right-front shoulder late in a stint."
  },
  12: {
    apexKph: 230,
    brakeFromKph: 242,
    gear: 6,
    tyreLoad: 0.83,
    tyre: "Left-front",
    difficulty: 4,
    overtaking: 1,
    coach:
      "A committed fast left that opens sector 3. Purely a confidence corner — the limit is what you are willing to hold, not what the car can do.",
    watch: "Lifting mid-corner scrubs speed you cannot recover before Turn 13."
  },
  13: {
    apexKph: 165,
    brakeFromKph: 228,
    gear: 4,
    tyreLoad: 0.8,
    tyre: "Front-right",
    difficulty: 3,
    overtaking: 2,
    coach:
      "A long 122 m radius right that turns almost 194 degrees. Entry into the final complex, so the priority is a clean line into Turn 14 rather than apex speed here.",
    watch: "Early apex leaves you fighting the car all the way to Turn 14."
  },
  14: {
    apexKph: 115,
    brakeFromKph: 208,
    gear: 3,
    tyreLoad: 0.64,
    tyre: "Rear-right traction",
    difficulty: 3,
    overtaking: 3,
    coach:
      "Heavy braking onto the back straight. Exit traction here is worth more than entry speed: every km/h you leave the corner with compounds down 808 m of DRS.",
    watch: "Wheelspin on exit in the wet, which kills the whole straight."
  },
  15: {
    apexKph: 75,
    brakeFromKph: 318,
    gear: 2,
    tyreLoad: 0.6,
    tyre: "Front-left",
    difficulty: 4,
    overtaking: 4,
    coach:
      "The iconic hairpin between the twin grandstands, and the second real overtaking spot. Brake from 318 kph with a full grandstand on both sides. Defend the inside, but a poor exit hands the place straight back down the pit straight.",
    watch: "Cold brakes on lap one and a locked front-left."
  }
};

/** Corners with the survey record and the driving model merged. */
export const TURNS = GEO.corners.map((c) => ({
  ...c,
  ...DRIVING[c.id],
  label: `T${c.id}`
}));

export const SECTORS = GEO.sectors.map((s) => {
  const meta = {
    1: {
      name: "Sector 1",
      span: "Start / finish to Turn 4",
      character: "Downhill heavy braking and a technical chicane",
      drainage: "Good",
      typicalTimeS: 24.8
    },
    2: {
      name: "Sector 2",
      span: "Turn 5 to Turn 11",
      character: "High-G sweepers, the uphill crest and the off-camber hairpin",
      drainage: "Poor — flash pooling at Turn 9",
      typicalTimeS: 36.4
    },
    3: {
      name: "Sector 3",
      span: "Turn 12 to Turn 15",
      character: "Twin straights and the dual grandstand hairpin",
      drainage: "Moderate",
      typicalTimeS: 29.6
    }
  }[s.id];
  return { ...s, ...meta };
});

export const DRS_ZONES = GEO.drsZones.map((z, i) => ({
  ...z,
  id: i + 1,
  worthS: i === 0 ? 0.31 : 0.26
}));

/** One calibrated lap of physics output, for the vitals rail. */
export const LAP_PHYSICS = {
  qualifyingLapS: 90.076,
  qualifyingTarget: 90.076,
  fastestRaceLapS: 94.083,
  fastestRaceLapReal: 94.08,
  topSpeedKph: 353,
  fuelEffectSPerKg: 0.032,
  drsWorthS: 0.57,
  raceTrimOffsetS: 3.22,
  timeScaleFactor: 0.9347,
  responseSurfaceMeanErrS: 0.055,
  responseSurfaceMaxErrS: 0.102
};

/** Straight-line geometry facts the UI quotes. */
export const STRAIGHTS = GEO.straights
  .slice()
  .sort((a, b) => b.lengthM - a.lengthM)
  .slice(0, 2);

/**
 * Tyre layer.
 *
 * Compound behaviour, stint quantiles and the wet crossover table are the
 * simulation's own measured output (350 Monte Carlo tyre sets for the
 * quantiles, a physics plus tread-depth model for the crossover). The per-lap
 * degradation coefficients below are fitted to those published stint losses:
 * a linear loss of k seconds per lap of age integrates to 16.1 s over 14 laps
 * of soft, 30.3 s over 20 laps of medium and 58.8 s over 28 laps of hard,
 * which is what the quantile study reports.
 */

export const COMPOUNDS = {
  soft: {
    key: "soft",
    name: "Soft",
    code: "C4",
    letter: "S",
    colour: "var(--c-soft)",
    hex: "#e62e2e",
    freshDeltaS: 0.0,
    degPerLapS: 0.177,
    cliffLap: 14,
    idealStint: 14,
    minStint: 8,
    maxStint: 20,
    optimalTempC: 105,
    blisterTempC: 122,
    waterLimitMm: 0.8,
    stint: { laps: 14, p10: 13.5, p50: 16.1, p90: 20.6 },
    character: "Fastest for a handful of laps, then it falls off a cliff.",
    sepang:
      "In 54 C track temperature the soft is a qualifying and a final-stint tyre only. Asking it to do 18 laps at Sepang turns it into a passenger."
  },
  medium: {
    key: "medium",
    name: "Medium",
    code: "C3",
    letter: "M",
    colour: "var(--c-medium)",
    hex: "#f5b002",
    freshDeltaS: 0.62,
    degPerLapS: 0.159,
    cliffLap: 21,
    idealStint: 20,
    minStint: 12,
    maxStint: 26,
    optimalTempC: 100,
    blisterTempC: 126,
    waterLimitMm: 1.0,
    stint: { laps: 20, p10: 27.7, p50: 30.3, p90: 34.5 },
    character: "The reference race tyre. Six tenths off the soft, half the wear.",
    sepang:
      "The backbone of every plan the optimiser likes. Two 20-lap mediums plus a short soft is the fastest way through 56 laps."
  },
  hard: {
    key: "hard",
    name: "Hard",
    code: "C2",
    letter: "H",
    colour: "var(--c-hard)",
    hex: "#eef2f6",
    freshDeltaS: 1.28,
    degPerLapS: 0.1556,
    cliffLap: 29,
    idealStint: 28,
    minStint: 18,
    maxStint: 34,
    optimalTempC: 95,
    blisterTempC: 130,
    waterLimitMm: 1.2,
    stint: { laps: 28, p10: 56.1, p50: 58.8, p90: 64.9 },
    character: "Slow but honest. Survives the heat and the long green stints.",
    sepang:
      "The insurance policy. Its 1.28 s deficit is a lot to give away over 28 laps, so it only wins when a safety car or a shower shortens the race."
  },
  inter: {
    key: "inter",
    name: "Intermediate",
    code: "INT",
    letter: "I",
    colour: "var(--c-inter)",
    hex: "#2ecc71",
    freshDeltaS: 4.8,
    degPerLapS: 0.31,
    cliffLap: 18,
    idealStint: 18,
    minStint: 4,
    maxStint: 24,
    optimalTempC: 80,
    blisterTempC: 105,
    optimalWaterMm: [1.2, 3.8],
    stint: null,
    character: "The tyre that wins wet Sepang races. Useful across a huge range.",
    sepang:
      "Correct from 0.4 mm all the way to 3 mm of standing water, which covers almost every state the monsoon model produces. On a dry hot track it shreds in a handful of laps."
  },
  wet: {
    key: "wet",
    name: "Full wet",
    code: "WET",
    letter: "W",
    colour: "var(--c-wet)",
    hex: "#3498db",
    freshDeltaS: 9.5,
    degPerLapS: 0.42,
    cliffLap: 24,
    idealStint: 24,
    minStint: 4,
    maxStint: 30,
    optimalTempC: 65,
    blisterTempC: 90,
    optimalWaterMm: [3.5, 8.0],
    stint: null,
    character: "Only correct once there is real standing water to clear.",
    sepang:
      "Below 5 mm the intermediate beats it. Above 5 mm it is the only tyre that keeps the car out of the barrier, and above 5.2 mm race control stops the race anyway."
  }
};

export const DRY_COMPOUNDS = ["soft", "medium", "hard"];
export const WET_COMPOUNDS = ["inter", "wet"];

/**
 * Wet crossover, measured. Lap time in seconds for each tyre at a given depth
 * of standing water, and which tyre is correct there.
 */
export const CROSSOVER = [
  { waterMm: 0.0, medium: 92.36, inter: 98.66, wet: 104.19, correct: "medium", slickPenaltyS: 0 },
  { waterMm: 0.4, medium: 98.64, inter: 96.85, wet: 106.75, correct: "inter", slickPenaltyS: 1.8 },
  { waterMm: 0.8, medium: 103.66, inter: 99.86, wet: 108.03, correct: "inter", slickPenaltyS: 3.8 },
  { waterMm: 1.2, medium: 108.32, inter: 102.53, wet: 108.97, correct: "inter", slickPenaltyS: 5.8 },
  { waterMm: 2.0, medium: 116.89, inter: 107.1, wet: 110.08, correct: "inter", slickPenaltyS: 9.8 },
  { waterMm: 3.0, medium: 121.68, inter: 111.88, wet: 112.71, correct: "inter", slickPenaltyS: 9.8 },
  { waterMm: 5.0, medium: 129.61, inter: 121.08, wet: 120.64, correct: "wet", slickPenaltyS: 9.0 },
  { waterMm: 7.0, medium: 136.57, inter: 129.31, wet: 127.6, correct: "wet", slickPenaltyS: 9.0 }
];

/** Linear interpolation into the measured crossover table. */
export function lapTimeAt(waterMm, tyre) {
  const t = tyre === "soft" || tyre === "hard" ? "medium" : tyre;
  const rows = CROSSOVER;
  if (waterMm <= rows[0].waterMm) return rows[0][t];
  if (waterMm >= rows[rows.length - 1].waterMm) return rows[rows.length - 1][t];
  for (let i = 1; i < rows.length; i += 1) {
    if (waterMm <= rows[i].waterMm) {
      const a = rows[i - 1];
      const b = rows[i];
      const f = (waterMm - a.waterMm) / (b.waterMm - a.waterMm);
      return a[t] + (b[t] - a[t]) * f;
    }
  }
  return rows[rows.length - 1][t];
}

/** Which of the three wet-relevant tyres is quickest at this depth. */
export function correctTyreAt(waterMm) {
  const options = ["medium", "inter", "wet"];
  let best = options[0];
  let bestT = Infinity;
  for (const o of options) {
    const t = lapTimeAt(waterMm, o);
    if (t < bestT) {
      bestT = t;
      best = o;
    }
  }
  return { tyre: best, lapS: bestT };
}

/**
 * Cumulative time lost to degradation after `age` laps on a compound,
 * relative to an ideal tyre. Linear wear plus a steep term past the cliff.
 */
export function degLossS(compoundKey, age) {
  const c = COMPOUNDS[compoundKey];
  if (!c) return 0;
  let loss = c.degPerLapS * age;
  if (age > c.cliffLap) {
    loss += 0.55 * Math.pow(age - c.cliffLap, 1.6);
  }
  return loss;
}

/** Per-lap pace of a compound at a given age, ignoring fuel. */
export function paceAtAge(compoundKey, age) {
  return COMPOUNDS[compoundKey].freshDeltaS + degLossS(compoundKey, age);
}

export const THERMAL = {
  trackTempC: 53.8,
  airTempC: 34.2,
  humidityPct: 88,
  worstTyre: "Right-front",
  worstCorners: [5, 11],
  note:
    "Sepang asphalt sits near 54 C in the dry. Turn 5 holds the right-front at sustained lateral load for over three seconds, and Turn 11 reloads it before it has cooled. Carcass temperature past the compound's blister threshold is what ends a stint here, not tread depth."
};

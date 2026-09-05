/**
 * Strategy layer.
 *
 * The pit model, the reference plan ranking and the Monte Carlo quantiles are
 * the simulation's measured output. The optimiser below is a live in-browser
 * re-implementation of the same idea: enumerate every feasible stint plan and
 * rank it on total race time.
 *
 * It is calibrated, not guessed. `BASE_LAP_S` is solved at module load so the
 * documented winning plan — medium 20, medium 20, soft 16 — reproduces the
 * documented race time of 1:27:25.872 exactly. Every other plan is then priced
 * against that same baseline, so the numbers on the page and the numbers you
 * get by dragging a slider come from one model.
 */

import { COMPOUNDS, DRY_COMPOUNDS, degLossS, lapTimeAt, correctTyreAt } from "./tyres.js";

export const PIT = {
  measuredLossS: 21.5,
  predictedLossS: 21.5,
  maeS: 0.419,
  barS: 0.5,
  sampledStops: 6000,
  speedLimitedM: 593,
  pitSpeedKph: 80,
  wetLossS: 18.55,
  note:
    "Pit loss is back-solved from the measured 21.5 s Sepang delta at the 80 kph limit, then validated across 6000 sampled stops. Mean absolute error 0.419 s against a 0.5 s bar."
};

export const FUEL = {
  startKg: 100,
  coefSPerKg: 0.032,
  note: "Fuel effect calibrated to the measured 0.032 s per kilogram."
};

export const RACE = {
  laps: 56,
  referencePlan: [
    { compound: "medium", laps: 20 },
    { compound: "medium", laps: 20 },
    { compound: "soft", laps: 16 }
  ],
  referenceTimeS: 5245.872, // 1:27:25.872
  dryWinnerTimeS: 5421.632, // 1:30:21.632, full-race dry reference
  dryWinnerTimeReal: 5401, // 1:30:01, the real 2017 race
  dryWinnerErrPct: 0.38
};

/** The documented exhaustive search result, kept as the reference ranking. */
export const REFERENCE_RANKING = [
  { rank: 1, plan: "M20 → M20 → S16", timeS: 5245.872, lossS: 0 },
  { rank: 2, plan: "M20 → S16 → M20", timeS: 5247.508, lossS: 1.64 },
  { rank: 3, plan: "S12 → M20 → M24", timeS: 5248.493, lossS: 2.62 },
  { rank: 4, plan: "M20 → S12 → M24", timeS: 5248.66, lossS: 2.79 },
  { rank: 5, plan: "S16 → M20 → M20", timeS: 5249.238, lossS: 3.37 },
  { rank: 6, plan: "M20 → M24 → S12", timeS: 5250.09, lossS: 4.22 }
];

export const UNCERTAINTY = {
  runs: 140,
  p10: "1:32:01.997",
  p50: "1:37:18.116",
  p90: "1:43:38.130",
  rainSeenPct: 94,
  unplannedStopsPerRace: 3.34,
  feasiblePlans: 1146,
  searchTimeS: 0.22,
  note:
    "140 Monte Carlo races with the monsoon timeline resampled each run. Rain appears in 94% of them, which is why the median race is nearly ten minutes slower than the dry optimum."
};

/* ------------------------------------------------------------------ *
 * live model
 * ------------------------------------------------------------------ */

function fuelKgAtLap(lapIndex, laps) {
  return FUEL.startKg * (1 - lapIndex / laps);
}

/**
 * Total on-track time for a plan, excluding pit loss, given a base lap time.
 * `stints` is [{ compound, laps }].
 */
function onTrackTimeS(stints, laps, base) {
  let total = 0;
  let lapIndex = 0;
  for (const stint of stints) {
    for (let age = 0; age < stint.laps; age += 1) {
      total +=
        base +
        COMPOUNDS[stint.compound].freshDeltaS +
        degLossS(stint.compound, age) +
        FUEL.coefSPerKg * fuelKgAtLap(lapIndex, laps);
      lapIndex += 1;
    }
  }
  return total;
}

/** Solve the base lap time so the documented reference plan reproduces exactly. */
function calibrateBase() {
  const withoutBase = onTrackTimeS(RACE.referencePlan, RACE.laps, 0);
  const stops = RACE.referencePlan.length - 1;
  const target = RACE.referenceTimeS - stops * PIT.measuredLossS - withoutBase;
  return target / RACE.laps;
}

export const BASE_LAP_S = calibrateBase();

/**
 * Read this before quoting a lap time off the optimiser.
 *
 * BASE_LAP_S is the pace of a fictional ideal tyre with an empty fuel tank, and
 * it is the residual of calibrating to the optimiser's reference total. It comes
 * out around 89.4 s, which is quicker than both the 90.076 s pole lap and the
 * 94.083 s fastest race lap the full race simulation produces — because the
 * optimiser deliberately prices plans in clean air with no traffic, no safety
 * cars and no engine management, exactly as the documented 1146-plan search did.
 *
 * So: totals and plan-to-plan deltas from this model are directly comparable to
 * the documented ranking. Absolute per-lap numbers from it are not comparable to
 * the race simulation, which is why the stint chart plots time lost per lap
 * rather than an absolute clock.
 */
export const PACE_BASELINE_NOTE =
  "The optimiser prices plans in clean air, with no traffic, safety cars or engine management — the same assumption as the documented 1146-plan search it is calibrated against. Race times are therefore comparable to that search, but quicker than the full race simulation, which adds a 3.22 s race-trim offset and resolves battles.";

/** Race time in seconds for a plan. */
export function raceTimeS(stints, laps = RACE.laps, pitLossS = PIT.measuredLossS) {
  const stops = Math.max(0, stints.length - 1);
  return onTrackTimeS(stints, laps, BASE_LAP_S) + stops * pitLossS;
}

/** Per-lap trace for a plan, for charting. */
export function lapTrace(stints, laps = RACE.laps) {
  const out = [];
  let lapIndex = 0;
  stints.forEach((stint, si) => {
    for (let age = 0; age < stint.laps; age += 1) {
      out.push({
        lap: lapIndex + 1,
        stint: si,
        compound: stint.compound,
        age,
        lapS:
          BASE_LAP_S +
          COMPOUNDS[stint.compound].freshDeltaS +
          degLossS(stint.compound, age) +
          FUEL.coefSPerKg * fuelKgAtLap(lapIndex, laps),
        pitAfter: age === stint.laps - 1 && si < stints.length - 1
      });
      lapIndex += 1;
    }
  });
  return out;
}

const CODE = { soft: "S", medium: "M", hard: "H" };

export function planLabel(stints) {
  return stints.map((s) => `${CODE[s.compound]}${s.laps}`).join(" → ");
}

/**
 * Exhaustive plan search.
 *
 * Stint lengths step in `stepLaps` and are bounded per compound by the tyre
 * model's min and max stint. A plan is only feasible if it covers the race
 * exactly and uses at least two different compounds, which is the dry-race
 * rule.
 */
export function optimise({
  laps = RACE.laps,
  pitLossS = PIT.measuredLossS,
  maxStops = 3,
  stepLaps = 2,
  allowed = DRY_COMPOUNDS,
  limit = 12
} = {}) {
  const results = [];
  let evaluated = 0;

  const minAllowed = Math.min(...allowed.map((c) => COMPOUNDS[c].minStint));

  const walk = (stints, lapsLeft) => {
    if (lapsLeft === 0) {
      if (stints.length < 2) return;
      const distinct = new Set(stints.map((s) => s.compound));
      if (distinct.size < 2) return;
      evaluated += 1;
      results.push({
        stints: stints.slice(),
        label: planLabel(stints),
        stops: stints.length - 1,
        timeS: raceTimeS(stints, laps, pitLossS)
      });
      return;
    }
    if (stints.length > maxStops) return;
    // cannot finish: not enough laps left for any legal stint
    if (lapsLeft < minAllowed) return;

    for (const compound of allowed) {
      const c = COMPOUNDS[compound];
      const hi = Math.min(c.maxStint, lapsLeft);
      for (let len = c.minStint; len <= hi; len += stepLaps) {
        const rest = lapsLeft - len;
        // either finish exactly, or leave room for one more legal stint
        if (rest !== 0 && rest < minAllowed) continue;
        stints.push({ compound, laps: len });
        walk(stints, rest);
        stints.pop();
      }
    }
  };

  walk([], laps);

  results.sort((a, b) => a.timeS - b.timeS);
  const best = results[0];
  return {
    evaluated,
    best,
    ranking: results.slice(0, limit).map((r, i) => ({
      ...r,
      rank: i + 1,
      lossS: best ? r.timeS - best.timeS : 0
    }))
  };
}

/* ------------------------------------------------------------------ *
 * monsoon crossover call
 * ------------------------------------------------------------------ */

/**
 * Should we stop now?
 *
 * Exactly the rule the race engine uses: compare the per-lap gain from being on
 * the correct tyre, over the laps that remain, against the pit loss. Lap times
 * come from the measured crossover table.
 */
export function crossoverCall({
  waterMm,
  currentTyre,
  lapsRemaining,
  pitLossS = PIT.wetLossS
}) {
  const now = lapTimeAt(waterMm, currentTyre);
  const target = correctTyreAt(waterMm);
  const perLapGain = now - target.lapS;
  const grossGain = perLapGain * lapsRemaining;
  const netGain = grossGain - pitLossS;
  const alreadyCorrect = target.tyre === (currentTyre === "soft" || currentTyre === "hard" ? "medium" : currentTyre);

  return {
    currentLapS: now,
    targetTyre: target.tyre,
    targetLapS: target.lapS,
    perLapGain,
    grossGain,
    netGain,
    pitLossS,
    lapsRemaining,
    alreadyCorrect,
    verdict: alreadyCorrect
      ? "stay-out"
      : netGain > 0
        ? "box-now"
        : "stay-out",
    reason: alreadyCorrect
      ? `Already on the quickest tyre for ${waterMm.toFixed(1)} mm of standing water.`
      : netGain > 0
        ? `Changing to ${target.tyre} gains ${perLapGain.toFixed(2)} s a lap. Over ${lapsRemaining} laps that is ${grossGain.toFixed(1)} s against a ${pitLossS.toFixed(1)} s pit loss — net ${netGain.toFixed(1)} s.`
        : `${target.tyre} is ${perLapGain.toFixed(2)} s a lap quicker, but only ${lapsRemaining} laps remain. ${grossGain.toFixed(1)} s of gain does not cover the ${pitLossS.toFixed(1)} s pit loss.`
  };
}

/* ------------------------------------------------------------------ *
 * formatting
 * ------------------------------------------------------------------ */

export function formatRaceTime(seconds) {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = seconds % 60;
  return `${h}:${String(m).padStart(2, "0")}:${s.toFixed(3).padStart(6, "0")}`;
}

export function formatLapTime(seconds) {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}:${s.toFixed(3).padStart(6, "0")}`;
}

export function formatDelta(seconds) {
  if (Math.abs(seconds) < 0.0005) return "—";
  return `${seconds > 0 ? "+" : "−"}${Math.abs(seconds).toFixed(3)}`;
}

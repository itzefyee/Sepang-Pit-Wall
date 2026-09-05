/**
 * Race weekend.
 *
 * This is the simulation's target event, not an entry on the published FIA
 * calendar — Sepang is not on the real 2026 championship schedule. The weekend
 * is laid out in the conventional format at the circuit's historical 15:00 local
 * start, so the countdown, the session plan and the strategy work all point at
 * one concrete date.
 *
 * All times are Malaysia time, UTC+8.
 */

export const EVENT = {
  name: "Malaysian Grand Prix",
  round: "Simulation target event",
  circuit: "Petronas Sepang International Circuit",
  locality: "Sepang, Selangor",
  timezone: "Malaysia time, UTC+8",
  laps: 56,
  disclaimer:
    "Target event for this simulation. Sepang does not appear on the published 2026 championship calendar; the weekend is laid out in the standard format at the circuit's historical 15:00 local start."
};

export const SESSIONS = [
  {
    key: "fp1",
    name: "Practice 1",
    short: "FP1",
    startsAt: "2026-09-25T11:30:00+08:00",
    durationMin: 60,
    focus: "Baseline in the heat. Long runs on the medium to see where the right-front gives up."
  },
  {
    key: "fp2",
    name: "Practice 2",
    short: "FP2",
    startsAt: "2026-09-25T15:00:00+08:00",
    durationMin: 60,
    focus: "Race-start conditions. Full fuel, race pace, and the first honest read on degradation."
  },
  {
    key: "fp3",
    name: "Practice 3",
    short: "FP3",
    startsAt: "2026-09-26T11:30:00+08:00",
    durationMin: 60,
    focus: "Low-fuel work and a wet programme if the squall arrives on schedule."
  },
  {
    key: "quali",
    name: "Qualifying",
    short: "QUALI",
    startsAt: "2026-09-26T15:00:00+08:00",
    durationMin: 60,
    focus: "One lap on the soft. Target is the 1:30.076 reference pole."
  },
  {
    key: "race",
    name: "Grand Prix",
    short: "RACE",
    startsAt: "2026-09-27T15:00:00+08:00",
    durationMin: 120,
    focus: "56 laps, 310.4 km. Two stops on paper and a 94% chance of rain deciding it instead.",
    isRace: true
  }
];

export const BRIEF = [
  {
    heading: "The plan on paper",
    body:
      "Medium 20, medium 20, soft 16. That is the fastest of 1146 feasible dry plans and it wins by 1.64 s over the next best, which is the same three stints in a different order. The margin is small enough that track position decides it, not tyres."
  },
  {
    heading: "The plan in reality",
    body:
      "Rain appears in 94% of simulated races here, and each one adds an average 3.34 stops the plan did not contain. The median race runs nearly ten minutes longer than the dry optimum. Plan for two stops, be ready for five."
  },
  {
    heading: "The corner that decides your race",
    body:
      "Turn 5. A 104 m radius left held at 245 kph loads the right-front for over three seconds, and Turn 11 reloads it before it has cooled. On 54 C asphalt that is what ends a stint here — carcass temperature, not tread depth."
  },
  {
    heading: "The number to watch",
    body:
      "1.4 mm of standing water. Below it, slicks. Above it, intermediates, and the penalty for being wrong climbs to nearly ten seconds a lap. Sector 2 crosses that line several minutes before the pit straight does."
  }
];

export const LEARNING_TRACKS = [
  {
    key: "rookie",
    name: "Never watched a race",
    minutes: 6,
    blurb: "What the flags mean, why they stop, and why the tyres are different colours.",
    steps: [
      "A Grand Prix is 56 laps of the same 5.543 km loop. First to finish wins; everything else is about how you spend your tyres.",
      "Tyres get slower as they wear. You must change them at least once, and each change costs about 21.5 s standing still plus the slow lap in and out.",
      "Softer tyres are quicker but die sooner. The whole game is choosing when to trade pace for a fresh set.",
      "Rain changes the answer entirely, because a slick tyre on a wet track is up to ten seconds a lap slower and cannot be driven safely.",
      "DRS is a flap on the rear wing that opens on the straights when you are within a second of the car ahead. Worth 0.57 s a lap here, and switched off in the wet."
    ]
  },
  {
    key: "strategist",
    name: "Learn the strategy",
    minutes: 10,
    blurb: "Pit windows, the crossover rule, and why the optimum is boring.",
    steps: [
      "Price a plan as one number: total race time. Sum every lap's time, then add the pit loss for each stop.",
      "A lap's time is base pace, plus the compound's fresh deficit, plus degradation for the age of the tyre, plus 0.032 s for every kilogram of fuel still on board.",
      "Because fuel burns off, later laps are quicker. That is why a short soft stint at the end beats the same stint at the start.",
      "The crossover rule for a tyre change is simple: the per-lap gain times the laps remaining must beat the pit loss. Nothing else.",
      "Exhaustive search beats intuition. 1146 plans price in 0.22 s, so there is no reason to guess — but the winner is within 4 s of five other plans, which is why traffic decides real races."
    ]
  },
  {
    key: "engineer",
    name: "Read the model",
    minutes: 14,
    blurb: "How lap time is computed, where it is calibrated, and where it is still wrong.",
    steps: [
      "Lap time is quasi-steady-state: corner speed from radius and available lateral grip, then a forward pass limited by power, traction and drag, and a backward pass limited by braking, iterated around the closed loop.",
      "Only two things are calibrated: the overall time scale to the 2017 pole lap, and tyre load sensitivity to the measured 0.032 s/kg fuel effect. Everything else falls out.",
      "The 0.9347 time-scale factor exists because the model drives the survey centreline, not an optimised racing line. That is the single biggest weakness in the whole stack.",
      "A response surface stands in for the full lap sim during strategy search, with 0.055 s mean error, which is what makes an exhaustive 1146-plan search take 0.22 s.",
      "Validation is adversarial: the 2001 and 2009 races are given only the grid, relative pace and the weather timeline. The outcome has to emerge. Six of six checks pass; positions 3 to 5 still drift."
    ]
  }
];

export const GLOSSARY = [
  { term: "Crossover", def: "The water depth at which a different tyre becomes quicker. At Sepang the slick-to-intermediate crossover sits at about 1.4 mm of standing water." },
  { term: "Pit loss", def: "Total time surrendered by making a stop, including the slow lap in and out, not just the stationary time. 21.5 s here in the dry, 18.55 s in the wet because racing speed is already lower." },
  { term: "Cliff", def: "The lap count past which a compound's degradation stops being linear and falls away sharply. Soft 14, medium 21, hard 29." },
  { term: "Blistering", def: "Tyre carcass overheating past its threshold, which lifts chunks of tread. Sepang's 54 C asphalt makes this the usual reason a stint ends." },
  { term: "DRS", def: "Drag Reduction System. A rear-wing flap that opens in designated zones when within a second of the car ahead. Worth 0.57 s a lap across both Sepang zones, and disabled once the track is wet." },
  { term: "Stint", def: "The laps run on one set of tyres, between stops." },
  { term: "Undercut", def: "Stopping earlier than a rival to use fresh-tyre pace while they are still on old rubber. Works at Sepang only if you clear the traffic you rejoin into." },
  { term: "P50 / P90", def: "Median and 90th-percentile outcomes across many simulated runs. The gap between them is the honest measure of how uncertain a prediction is." },
  { term: "Off camber", def: "A corner where the road surface tilts away from the turn instead of into it, so the car loses grip precisely when it needs it. Turn 9 is the example here." },
  { term: "Half points", def: "Awarded when a race is stopped before 75% distance. The 2009 Malaysian Grand Prix is the modern example, red-flagged on lap 31 of 56." }
];

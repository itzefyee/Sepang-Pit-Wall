/**
 * Monsoon layer.
 *
 * Rain adds depth and run-off removes a share of the standing water every lap,
 * so each rain intensity settles at a bounded equilibrium rather than
 * accumulating without limit. Sector 2 drains worst at Sepang and floods first.
 * Race control abandons above 5.2 mm mean depth.
 *
 * Both tables below are the weather engine's measured output.
 */

export const CLIMATE = {
  airTempC: 34.2,
  trackTempC: 53.8,
  humidityPct: 88,
  windKph: 14,
  windBearingDeg: 210,
  windFrom: "Malacca Strait",
  abandonThresholdMm: 5.2,
  aquaplaningThresholdMm: 4.2,
  drsCutoffWetness: 0.25,
  note:
    "Sepang sits 40 km inland from the Malacca Strait at 2.76 degrees north. Convective cells build over the afternoon and cross the circuit from the south-west, which is why sector 2 — the highest and least well drained part of the lap — gets wet several minutes before the pit straight does."
};

/** Standing water each rain intensity settles at, by sector. */
export const EQUILIBRIUM = [
  { intensity: 2, meanMm: 1.47, s1: 1.16, s2: 1.87, s3: 1.36, label: "Light rain" },
  { intensity: 4, meanMm: 2.93, s1: 2.32, s2: 3.74, s3: 2.73, label: "Light rain" },
  { intensity: 6, meanMm: 4.39, s1: 3.48, s2: 5.61, s3: 4.09, label: "Heavy rain" },
  { intensity: 8, meanMm: 5.86, s1: 4.64, s2: 7.48, s3: 5.46, label: "Monsoon" },
  { intensity: 10, meanMm: 7.33, s1: 5.8, s2: 9.35, s3: 6.82, label: "Monsoon" }
];

/** Mean depth by lap after a monsoon cell passes, peak 6.37 mm. */
export const DRYING_CURVE = [
  1.3, 3.38, 4.61, 5.34, 5.8, 6.08, 6.26, 6.37, 6.01, 5.37, 4.56, 3.64, 2.66,
  1.47, 0.58, 0.24, 0.05, 0, 0, 0, 0, 0, 0, 0
];

export const SECTOR_DRAINAGE = [
  {
    id: 1,
    name: "Sector 1",
    drainage: "Good",
    factor: 0.79,
    note: "Falls away from the start line, so water runs off the racing line quickly."
  },
  {
    id: 2,
    name: "Sector 2",
    drainage: "Poor",
    factor: 1.28,
    note: "The high point of the lap and the flattest camber. Turn 9 pools first and clears last."
  },
  {
    id: 3,
    name: "Sector 3",
    drainage: "Moderate",
    factor: 0.93,
    note: "The twin straights shed water well; the Turn 15 hairpin holds a damp inside line."
  }
];

/** Radar cell seeds, matching the engine's convective cell setup. */
export const RADAR_CELLS = [
  { x: 30, y: -40, radius: 28, dbz: 52, vx: -0.4, vy: 0.5, name: "Cell A" },
  { x: -50, y: -80, radius: 45, dbz: 62, vx: -0.2, vy: 0.7, name: "Cell B" },
  { x: 70, y: 30, radius: 20, dbz: 38, vx: -0.5, vy: 0.3, name: "Cell C" }
];

export const WEATHER_MODES = {
  sun: {
    key: "sun",
    name: "Tropical sun",
    cloud: 0.15,
    intensity: 0,
    airTempC: 34.8,
    trackTempC: 54.5,
    humidityPct: 84,
    cellDistanceKm: 15,
    sectorRain: [0, 0, 0],
    blurb: "54 C asphalt. Thermal degradation is the whole story."
  },
  squall: {
    key: "squall",
    name: "Approaching squall",
    cloud: 0.75,
    intensity: 0.25,
    airTempC: 31,
    trackTempC: 44,
    humidityPct: 92,
    cellDistanceKm: 3.5,
    sectorRain: [0.05, 0.45, 0],
    blurb: "Sector 2 is already wet while the pit straight is bone dry."
  },
  monsoon: {
    key: "monsoon",
    name: "Torrential monsoon",
    cloud: 1,
    intensity: 0.95,
    airTempC: 26.5,
    trackTempC: 29,
    humidityPct: 98,
    cellDistanceKm: 0,
    sectorRain: [0.85, 1, 0.9],
    blurb: "50 mm/h. Flash pooling at Turn 9 and a red flag in play."
  },
  drying: {
    key: "drying",
    name: "Drying track",
    cloud: 0.4,
    intensity: 0,
    airTempC: 32.5,
    trackTempC: 48,
    humidityPct: 89,
    cellDistanceKm: 9,
    sectorRain: [0, 0, 0],
    blurb: "Hot asphalt evaporates fast. The crossover back to slicks is coming."
  }
};

/** Equilibrium depth for an arbitrary intensity, interpolated. */
export function depthAtIntensity(intensity) {
  const rows = EQUILIBRIUM;
  if (intensity <= 0) return { meanMm: 0, s1: 0, s2: 0, s3: 0, label: "Dry" };
  if (intensity <= rows[0].intensity) {
    const f = intensity / rows[0].intensity;
    return {
      meanMm: rows[0].meanMm * f,
      s1: rows[0].s1 * f,
      s2: rows[0].s2 * f,
      s3: rows[0].s3 * f,
      label: f > 0.4 ? "Light rain" : "Damp"
    };
  }
  for (let i = 1; i < rows.length; i += 1) {
    if (intensity <= rows[i].intensity) {
      const a = rows[i - 1];
      const b = rows[i];
      const f = (intensity - a.intensity) / (b.intensity - a.intensity);
      const mix = (k) => a[k] + (b[k] - a[k]) * f;
      return {
        meanMm: mix("meanMm"),
        s1: mix("s1"),
        s2: mix("s2"),
        s3: mix("s3"),
        label: f > 0.5 ? b.label : a.label
      };
    }
  }
  const last = rows[rows.length - 1];
  return { ...last };
}

export function classifyDepth(mm) {
  if (mm < 0.2) return { label: "Dry", tone: "good" };
  if (mm < 0.8) return { label: "Damp", tone: "good" };
  if (mm < 1.4) return { label: "Crossover", tone: "warn" };
  if (mm < 3.5) return { label: "Wet", tone: "warn" };
  if (mm < CLIMATE.abandonThresholdMm) return { label: "Standing water", tone: "fail" };
  return { label: "Abandon", tone: "fail" };
}

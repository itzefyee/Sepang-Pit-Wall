/**
 * Turns the surveyed centreline into SVG paths.
 *
 * The source is 1386 points at 4 m spacing in metres from a local origin, so the
 * shape on screen is the real circuit rather than a traced impression of it. The
 * stroke is drawn from every second point — at any realistic display size that
 * is visually identical and halves the path data — while index lookups for
 * corner markers use the full-resolution array.
 */

import { GEO } from "../data/circuit.js";

const PAD = 46;

const { minX, maxX, minY, maxY } = GEO.bounds;
const spanX = maxX - minX;
const spanY = maxY - minY;

export const MAP = {
  width: spanX + PAD * 2,
  height: spanY + PAD * 2,
  viewBox: `0 0 ${(spanX + PAD * 2).toFixed(1)} ${(spanY + PAD * 2).toFixed(1)}`
};

/** Metres to SVG. y is flipped because SVG grows downward. */
export function toSvg([x, y]) {
  return [x - minX + PAD, maxY - y + PAD];
}

export function pointAt(index) {
  const p = GEO.points[((index % GEO.n) + GEO.n) % GEO.n];
  return toSvg(p);
}

function pathFrom(points, close) {
  let d = "";
  points.forEach((p, i) => {
    const [x, y] = p;
    d += `${i === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`;
  });
  return close ? `${d}Z` : d;
}

/** The whole lap, closed. */
export function lapPath(step = 2) {
  const pts = [];
  for (let i = 0; i < GEO.n; i += step) pts.push(toSvg(GEO.points[i]));
  return pathFrom(pts, true);
}

/**
 * A path over an index range that may wrap past the start/finish line —
 * the pit-straight DRS zone does exactly that.
 */
export function rangePath(from, to, step = 2) {
  const pts = [];
  const count = to >= from ? to - from : GEO.n - from + to;
  for (let k = 0; k <= count; k += step) {
    pts.push(toSvg(GEO.points[(from + k) % GEO.n]));
  }
  // always include the exact end point so the segment does not fall short
  pts.push(toSvg(GEO.points[((to % GEO.n) + GEO.n) % GEO.n]));
  return pathFrom(pts, false);
}

export function pitLanePath() {
  return pathFrom(GEO.pitLane.map(toSvg), false);
}

/**
 * Start/finish line: a short tick across the track at index 0, perpendicular to
 * the direction of travel there.
 */
export function startLine(halfWidth = 13) {
  const a = toSvg(GEO.points[GEO.n - 3]);
  const b = toSvg(GEO.points[3]);
  const dx = b[0] - a[0];
  const dy = b[1] - a[1];
  const len = Math.hypot(dx, dy) || 1;
  const nx = -dy / len;
  const ny = dx / len;
  const c = toSvg(GEO.points[0]);
  return {
    x1: c[0] + nx * halfWidth,
    y1: c[1] + ny * halfWidth,
    x2: c[0] - nx * halfWidth,
    y2: c[1] - ny * halfWidth
  };
}

/**
 * Where to put a corner's number so the label sits outside the track rather
 * than on it: push it along the outward normal at the apex.
 */
export function cornerLabelAt(apexIndex, distance = 26) {
  const prev = toSvg(GEO.points[(apexIndex - 8 + GEO.n) % GEO.n]);
  const next = toSvg(GEO.points[(apexIndex + 8) % GEO.n]);
  const apex = toSvg(GEO.points[apexIndex % GEO.n]);
  const mx = (prev[0] + next[0]) / 2;
  const my = (prev[1] + next[1]) / 2;
  let ox = apex[0] - mx;
  let oy = apex[1] - my;
  const len = Math.hypot(ox, oy);
  if (len < 0.001) {
    // a straight-ish section: fall back to the left-hand normal
    const dx = next[0] - prev[0];
    const dy = next[1] - prev[1];
    const dl = Math.hypot(dx, dy) || 1;
    ox = -dy / dl;
    oy = dx / dl;
  } else {
    ox /= len;
    oy /= len;
  }
  return {
    apex,
    label: [apex[0] + ox * distance, apex[1] + oy * distance]
  };
}

export const SECTOR_COLOURS = {
  1: "#f5b002",
  2: "#00a19b",
  3: "#8b6cf0"
};

/**
 * Charts.
 *
 * Hand-built inline SVG rather than a charting dependency: the whole point is
 * that these stay inspectable, scale crisply, and can be read straight out of
 * the DOM. Drawn in the "Wire" idiom — near-black ground, muted axes, one red
 * primary series, teal secondary, compound colours where a tyre is the subject.
 *
 * Every chart uses a fixed viewBox and scales with its container, so labels keep
 * their proportions instead of reflowing.
 */

import { useCallback, useMemo, useRef, useState } from "react";

const AXIS = "rgba(173,189,203,0.55)";
const GRID = "rgba(173,189,203,0.1)";
const INK = "#e9eff5";

function niceTicks(min, max, count = 5) {
  const span = max - min;
  if (span <= 0) return [min];
  const raw = span / count;
  const mag = Math.pow(10, Math.floor(Math.log10(raw)));
  const norm = raw / mag;
  const step = (norm >= 5 ? 10 : norm >= 2 ? 5 : norm >= 1 ? 2 : 1) * mag;
  const start = Math.ceil(min / step) * step;
  const out = [];
  for (let v = start; v <= max + step * 0.001; v += step) {
    out.push(+v.toFixed(10));
  }
  return out;
}

/* ================================================================== *
 * line chart with hover readout
 * ================================================================== */

export function LineChart({
  series,
  xDomain,
  yDomain,
  xLabel,
  yLabel,
  formatX = (v) => String(v),
  formatY = (v) => String(v),
  height = 300,
  width = 820,
  pad = { t: 18, r: 20, b: 44, l: 56 },
  bands = [],
  areaUnderFirst = false
}) {
  const [hover, setHover] = useState(null);
  const hostRef = useRef(null);

  const xs = series.flatMap((s) => s.points.map((p) => p[0]));
  const ys = series.flatMap((s) => s.points.map((p) => p[1]));
  const x0 = xDomain?.[0] ?? Math.min(...xs);
  const x1 = xDomain?.[1] ?? Math.max(...xs);
  const y0 = yDomain?.[0] ?? Math.min(...ys);
  const y1 = yDomain?.[1] ?? Math.max(...ys);

  const iw = width - pad.l - pad.r;
  const ih = height - pad.t - pad.b;
  const sx = (v) => pad.l + ((v - x0) / (x1 - x0 || 1)) * iw;
  const sy = (v) => pad.t + ih - ((v - y0) / (y1 - y0 || 1)) * ih;

  const xTicks = useMemo(() => niceTicks(x0, x1, 6), [x0, x1]);
  const yTicks = useMemo(() => niceTicks(y0, y1, 5), [y0, y1]);

  const onMove = useCallback(
    (e) => {
      const svg = hostRef.current;
      if (!svg) return;
      const r = svg.getBoundingClientRect();
      const px = ((e.clientX - r.left) / r.width) * width;
      const value = x0 + ((px - pad.l) / iw) * (x1 - x0);
      if (px < pad.l - 4 || px > pad.l + iw + 4) {
        setHover(null);
        return;
      }
      // nearest sample on the first series
      const base = series[0].points;
      let bi = 0;
      let bd = Infinity;
      base.forEach((p, i) => {
        const d = Math.abs(p[0] - value);
        if (d < bd) {
          bd = d;
          bi = i;
        }
      });
      setHover({ x: base[bi][0], index: bi });
    },
    [series, width, x0, x1, iw, pad.l]
  );

  const readout = hover
    ? series.map((s) => {
        const exact = s.points.find((p) => p[0] === hover.x);
        const pt = exact ?? s.points[Math.min(s.points.length - 1, hover.index)];
        return { name: s.name, colour: s.colour, value: pt?.[1], x: pt?.[0] };
      })
    : null;

  return (
    <div className="chart">
      <svg
        ref={hostRef}
        viewBox={`0 0 ${width} ${height}`}
        className="chart__svg"
        role="img"
        aria-label={`${yLabel ?? "value"} against ${xLabel ?? "x"}`}
        onPointerMove={onMove}
        onPointerLeave={() => setHover(null)}
      >
        {bands.map((b, i) => (
          <rect
            key={i}
            x={sx(b.from)}
            y={pad.t}
            width={Math.max(0, sx(b.to) - sx(b.from))}
            height={ih}
            fill={b.fill}
          />
        ))}

        {yTicks.map((t) => (
          <g key={`y${t}`}>
            <line x1={pad.l} y1={sy(t)} x2={pad.l + iw} y2={sy(t)} stroke={GRID} />
            <text
              x={pad.l - 9}
              y={sy(t)}
              fill={AXIS}
              fontSize="11"
              textAnchor="end"
              dominantBaseline="middle"
              fontFamily="var(--font-mono)"
            >
              {formatY(t)}
            </text>
          </g>
        ))}

        {xTicks.map((t) => (
          <g key={`x${t}`}>
            <line
              x1={sx(t)}
              y1={pad.t + ih}
              x2={sx(t)}
              y2={pad.t + ih + 5}
              stroke={AXIS}
            />
            <text
              x={sx(t)}
              y={pad.t + ih + 19}
              fill={AXIS}
              fontSize="11"
              textAnchor="middle"
              fontFamily="var(--font-mono)"
            >
              {formatX(t)}
            </text>
          </g>
        ))}

        <line
          x1={pad.l}
          y1={pad.t + ih}
          x2={pad.l + iw}
          y2={pad.t + ih}
          stroke={AXIS}
        />

        {areaUnderFirst && series[0] ? (
          <path
            d={`${series[0].points
              .map((p, i) => `${i ? "L" : "M"}${sx(p[0])},${sy(p[1])}`)
              .join("")}L${sx(series[0].points[series[0].points.length - 1][0])},${
              pad.t + ih
            }L${sx(series[0].points[0][0])},${pad.t + ih}Z`}
            fill={`${series[0].colour}22`}
          />
        ) : null}

        {series.map((s) => (
          <path
            key={s.name}
            d={s.points.map((p, i) => `${i ? "L" : "M"}${sx(p[0])},${sy(p[1])}`).join("")}
            fill="none"
            stroke={s.colour}
            strokeWidth={s.width ?? 2}
            strokeDasharray={s.dash ?? undefined}
            strokeLinejoin="round"
            strokeLinecap="round"
          />
        ))}

        {series.map((s) =>
          s.dots
            ? s.points.map((p) => (
                <circle
                  key={`${s.name}-${p[0]}`}
                  cx={sx(p[0])}
                  cy={sy(p[1])}
                  r="3"
                  fill="#0a0e13"
                  stroke={s.colour}
                  strokeWidth="1.6"
                />
              ))
            : null
        )}

        {hover ? (
          <>
            <line
              x1={sx(hover.x)}
              y1={pad.t}
              x2={sx(hover.x)}
              y2={pad.t + ih}
              stroke="rgba(233,239,245,0.4)"
              strokeDasharray="3 3"
            />
            {readout.map((r) =>
              r.value == null ? null : (
                <circle
                  key={r.name}
                  cx={sx(r.x)}
                  cy={sy(r.value)}
                  r="4"
                  fill={r.colour}
                  stroke="#0a0e13"
                  strokeWidth="1.5"
                />
              )
            )}
          </>
        ) : null}

        {yLabel ? (
          <text
            x={12}
            y={pad.t + ih / 2}
            fill={AXIS}
            fontSize="10.5"
            textAnchor="middle"
            transform={`rotate(-90 12 ${pad.t + ih / 2})`}
            letterSpacing="0.14em"
            fontFamily="var(--font-head)"
          >
            {yLabel.toUpperCase()}
          </text>
        ) : null}
        {xLabel ? (
          <text
            x={pad.l + iw / 2}
            y={height - 6}
            fill={AXIS}
            fontSize="10.5"
            textAnchor="middle"
            letterSpacing="0.14em"
            fontFamily="var(--font-head)"
          >
            {xLabel.toUpperCase()}
          </text>
        ) : null}
      </svg>

      <div className="chart__legend">
        {series.map((s) => (
          <span key={s.name} className="chart__key">
            <i style={{ background: s.colour }} />
            {s.name}
          </span>
        ))}
      </div>

      <div className="chart__readout mono" aria-live="polite">
        {readout ? (
          <>
            <strong>
              {formatX(hover.x)}
              {xLabel ? ` ${xLabel.split(" ").pop()}` : ""}
            </strong>
            {readout.map((r) =>
              r.value == null ? null : (
                <span key={r.name} style={{ color: r.colour }}>
                  {r.name} {formatY(r.value)}
                </span>
              )
            )}
          </>
        ) : (
          <span className="dim-2">Hover the chart for values.</span>
        )}
      </div>
    </div>
  );
}

/* ================================================================== *
 * bar chart
 * ================================================================== */

export function BarChart({
  data,
  height = 250,
  width = 820,
  pad = { t: 16, r: 16, b: 44, l: 56 },
  formatY = (v) => String(v),
  xLabel,
  yLabel,
  threshold
}) {
  const [hover, setHover] = useState(null);
  const max = Math.max(...data.map((d) => d.value), threshold?.value ?? 0);
  const iw = width - pad.l - pad.r;
  const ih = height - pad.t - pad.b;
  const bw = iw / data.length;
  const yTicks = niceTicks(0, max, 4);
  const sy = (v) => pad.t + ih - (v / (max || 1)) * ih;

  return (
    <div className="chart">
      <svg
        viewBox={`0 0 ${width} ${height}`}
        className="chart__svg"
        role="img"
        aria-label={`${yLabel ?? "value"} by ${xLabel ?? "category"}`}
      >
        {yTicks.map((t) => (
          <g key={t}>
            <line x1={pad.l} y1={sy(t)} x2={pad.l + iw} y2={sy(t)} stroke={GRID} />
            <text
              x={pad.l - 9}
              y={sy(t)}
              fill={AXIS}
              fontSize="11"
              textAnchor="end"
              dominantBaseline="middle"
              fontFamily="var(--font-mono)"
            >
              {formatY(t)}
            </text>
          </g>
        ))}

        {threshold ? (
          <>
            <line
              x1={pad.l}
              y1={sy(threshold.value)}
              x2={pad.l + iw}
              y2={sy(threshold.value)}
              stroke="#ff5a5f"
              strokeDasharray="5 4"
              strokeWidth="1.4"
            />
            <text
              x={pad.l + iw}
              y={sy(threshold.value) - 6}
              fill="#ff5a5f"
              fontSize="10.5"
              textAnchor="end"
              letterSpacing="0.1em"
              fontFamily="var(--font-head)"
            >
              {threshold.label.toUpperCase()}
            </text>
          </>
        ) : null}

        {data.map((d, i) => {
          const h = Math.max(1, pad.t + ih - sy(d.value));
          const active = hover === i;
          return (
            <g
              key={d.label ?? i}
              onPointerEnter={() => setHover(i)}
              onPointerLeave={() => setHover(null)}
            >
              <rect
                x={pad.l + i * bw}
                y={pad.t}
                width={bw}
                height={ih}
                fill="transparent"
              />
              <rect
                x={pad.l + i * bw + bw * 0.16}
                y={sy(d.value)}
                width={bw * 0.68}
                height={h}
                rx="2"
                fill={d.colour ?? "#d81f26"}
                opacity={hover == null || active ? 1 : 0.45}
              />
              {d.label ? (
                <text
                  x={pad.l + i * bw + bw / 2}
                  y={pad.t + ih + 18}
                  fill={active ? INK : AXIS}
                  fontSize="11"
                  textAnchor="middle"
                  fontFamily="var(--font-mono)"
                >
                  {d.label}
                </text>
              ) : null}
              {active ? (
                <text
                  x={pad.l + i * bw + bw / 2}
                  y={sy(d.value) - 7}
                  fill={INK}
                  fontSize="11.5"
                  textAnchor="middle"
                  fontFamily="var(--font-mono)"
                >
                  {formatY(d.value)}
                </text>
              ) : null}
            </g>
          );
        })}

        <line x1={pad.l} y1={pad.t + ih} x2={pad.l + iw} y2={pad.t + ih} stroke={AXIS} />

        {xLabel ? (
          <text
            x={pad.l + iw / 2}
            y={height - 6}
            fill={AXIS}
            fontSize="10.5"
            textAnchor="middle"
            letterSpacing="0.14em"
            fontFamily="var(--font-head)"
          >
            {xLabel.toUpperCase()}
          </text>
        ) : null}
        {yLabel ? (
          <text
            x={12}
            y={pad.t + ih / 2}
            fill={AXIS}
            fontSize="10.5"
            textAnchor="middle"
            transform={`rotate(-90 12 ${pad.t + ih / 2})`}
            letterSpacing="0.14em"
            fontFamily="var(--font-head)"
          >
            {yLabel.toUpperCase()}
          </text>
        ) : null}
      </svg>
    </div>
  );
}

/* ================================================================== *
 * stint timeline
 * ================================================================== */

export function StintTimeline({ stints, laps, pitLossS }) {
  const width = 820;
  const height = 96;
  const pad = { l: 8, r: 8, t: 26, b: 26 };
  const iw = width - pad.l - pad.r;
  let cursor = 0;

  return (
    <div className="chart">
      <svg
        viewBox={`0 0 ${width} ${height}`}
        className="chart__svg"
        role="img"
        aria-label="Stint plan across the race distance"
      >
        {stints.map((s, i) => {
          const x = pad.l + (cursor / laps) * iw;
          const w = (s.laps / laps) * iw;
          const mid = x + w / 2;
          const startLap = cursor + 1;
          const endLap = cursor + s.laps;
          cursor += s.laps;
          return (
            <g key={`${i}-${s.compound}`}>
              <rect
                x={x + 1}
                y={pad.t}
                width={Math.max(2, w - 2)}
                height={height - pad.t - pad.b}
                rx="3"
                fill={s.hex ?? "#d81f26"}
                opacity="0.85"
              />
              <text
                x={mid}
                y={pad.t + (height - pad.t - pad.b) / 2 + 4}
                fill="#06090d"
                fontSize="12.5"
                fontWeight="700"
                textAnchor="middle"
                fontFamily="var(--font-head)"
              >
                {s.letter}
                {s.laps}
              </text>
              <text
                x={mid}
                y={pad.t - 8}
                fill={AXIS}
                fontSize="10.5"
                textAnchor="middle"
                fontFamily="var(--font-mono)"
              >
                L{startLap}–{endLap}
              </text>
              {i < stints.length - 1 ? (
                <>
                  <line
                    x1={x + w}
                    y1={pad.t - 4}
                    x2={x + w}
                    y2={height - pad.b + 4}
                    stroke="#e9eff5"
                    strokeWidth="1.6"
                  />
                  <text
                    x={x + w}
                    y={height - pad.b + 17}
                    fill={INK}
                    fontSize="10.5"
                    textAnchor="middle"
                    fontFamily="var(--font-mono)"
                  >
                    +{pitLossS.toFixed(1)}s
                  </text>
                </>
              ) : null}
            </g>
          );
        })}
      </svg>
    </div>
  );
}

/* ================================================================== *
 * elevation profile with corner markers
 * ================================================================== */

export function ElevationChart({ profile, corners, activeTurn, onPick }) {
  const width = 820;
  const height = 220;
  const pad = { t: 22, r: 16, b: 42, l: 48 };
  const iw = width - pad.l - pad.r;
  const ih = height - pad.t - pad.b;

  const maxS = profile[profile.length - 1][0];
  const ys = profile.map((p) => p[1]);
  const y0 = Math.floor(Math.min(...ys));
  const y1 = Math.ceil(Math.max(...ys));

  const sx = (v) => pad.l + (v / maxS) * iw;
  const sy = (v) => pad.t + ih - ((v - y0) / (y1 - y0 || 1)) * ih;

  const d = profile.map((p, i) => `${i ? "L" : "M"}${sx(p[0]).toFixed(1)},${sy(p[1]).toFixed(1)}`).join("");

  return (
    <div className="chart">
      <svg
        viewBox={`0 0 ${width} ${height}`}
        className="chart__svg"
        role="img"
        aria-label="Elevation along the lap with corner markers"
      >
        {niceTicks(y0, y1, 4).map((t) => (
          <g key={t}>
            <line x1={pad.l} y1={sy(t)} x2={pad.l + iw} y2={sy(t)} stroke={GRID} />
            <text
              x={pad.l - 8}
              y={sy(t)}
              fill={AXIS}
              fontSize="11"
              textAnchor="end"
              dominantBaseline="middle"
              fontFamily="var(--font-mono)"
            >
              {t}
            </text>
          </g>
        ))}

        <path d={`${d}L${sx(maxS)},${pad.t + ih}L${pad.l},${pad.t + ih}Z`} fill="rgba(0,161,155,0.16)" />
        <path d={d} fill="none" stroke="#00a19b" strokeWidth="1.8" />

        {corners.map((c) => {
          const active = activeTurn === c.id;
          return (
            <g
              key={c.id}
              onClick={() => onPick?.(c.id)}
              style={{ cursor: onPick ? "pointer" : "default" }}
            >
              <line
                x1={sx(c.sM)}
                y1={pad.t}
                x2={sx(c.sM)}
                y2={pad.t + ih}
                stroke={active ? "#ff3b42" : "rgba(233,239,245,0.16)"}
                strokeWidth={active ? 1.8 : 1}
              />
              <text
                x={sx(c.sM)}
                y={pad.t - 7}
                fill={active ? "#ff3b42" : AXIS}
                fontSize="9.5"
                textAnchor="middle"
                fontFamily="var(--font-mono)"
              >
                {c.id}
              </text>
            </g>
          );
        })}

        {niceTicks(0, maxS, 6).map((t) => (
          <text
            key={`s${t}`}
            x={sx(t)}
            y={pad.t + ih + 18}
            fill={AXIS}
            fontSize="11"
            textAnchor="middle"
            fontFamily="var(--font-mono)"
          >
            {(t / 1000).toFixed(1)}
          </text>
        ))}

        <text
          x={pad.l + iw / 2}
          y={height - 5}
          fill={AXIS}
          fontSize="10.5"
          textAnchor="middle"
          letterSpacing="0.14em"
          fontFamily="var(--font-head)"
        >
          DISTANCE ALONG THE LAP (KM)
        </text>
        <text
          x={11}
          y={pad.t + ih / 2}
          fill={AXIS}
          fontSize="10.5"
          textAnchor="middle"
          transform={`rotate(-90 11 ${pad.t + ih / 2})`}
          letterSpacing="0.14em"
          fontFamily="var(--font-head)"
        >
          ELEVATION (M)
        </text>
      </svg>
    </div>
  );
}

/* ================================================================== *
 * horizontal ranked bars
 * ================================================================== */

export function RankBars({ rows, max, formatValue, colour = "#d81f26" }) {
  const top = max ?? Math.max(...rows.map((r) => r.value));
  return (
    <div className="rankbars">
      {rows.map((r) => (
        <div className="rankbars__row" key={r.label}>
          <span className="rankbars__label t-small">{r.label}</span>
          <span className="rankbars__track">
            <span
              className="rankbars__fill"
              style={{
                width: `${top > 0 ? (r.value / top) * 100 : 0}%`,
                background: r.colour ?? colour
              }}
            />
          </span>
          <span className="rankbars__value mono">
            {formatValue ? formatValue(r.value) : r.value}
          </span>
        </div>
      ))}
    </div>
  );
}

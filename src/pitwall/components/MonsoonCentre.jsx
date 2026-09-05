/**
 * Monsoon centre.
 *
 * The radar is a Canvas 2D reflectivity plot of the weather engine's convective
 * cells, suspended when off screen and frozen under prefers-reduced-motion.
 *
 * The crossover advisor is the same rule the race engine uses when it decides
 * whether to stop: per-lap gain times laps remaining, against the pit loss.
 * Nothing else. Lap times come from the measured crossover table.
 */

import { useEffect, useMemo, useRef, useState } from "react";

import { PIT, crossoverCall } from "../data/strategy.js";
import { COMPOUNDS } from "../data/tyres.js";
import {
  CLIMATE,
  DRYING_CURVE,
  EQUILIBRIUM,
  RADAR_CELLS,
  SECTOR_DRAINAGE,
  WEATHER_MODES,
  classifyDepth,
  depthAtIntensity
} from "../data/weather.js";
import { useInView, usePrefersReducedMotion } from "../hooks.js";
import { BarChart, LineChart } from "./charts.jsx";
import { Field, Panel, Pill, Reveal, Section, Segmented, Stat, Tyre } from "./ui.jsx";

/* ------------------------------------------------------------------ *
 * doppler radar
 * ------------------------------------------------------------------ */

function Radar({ mode }) {
  const canvasRef = useRef(null);
  const [hostRef, , visible] = useInView({ threshold: 0.15, rootMargin: "80px" });
  const reduced = usePrefersReducedMotion();

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const dpr = Math.min(2, window.devicePixelRatio || 1);
    const size = 460;
    canvas.width = size * dpr;
    canvas.height = size * dpr;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

    const cells = RADAR_CELLS.map((c) => ({ ...c }));
    const preset = WEATHER_MODES[mode];
    // a distant storm draws its cells further out; a monsoon has them overhead
    const spread = 0.35 + (preset.cellDistanceKm / 15) * 0.9;

    let raf = 0;
    let last = performance.now();

    const draw = (now) => {
      const dt = reduced ? 0 : Math.min(0.05, (now - last) / 1000);
      last = now;

      const w = size;
      const h = size;
      const cx = w / 2;
      const cy = h / 2;
      const radius = w * 0.45;

      ctx.fillStyle = "#070d13";
      ctx.fillRect(0, 0, w, h);

      // range rings
      ctx.strokeStyle = "rgba(0,161,155,0.24)";
      ctx.lineWidth = 1;
      for (let r = 1; r <= 3; r += 1) {
        ctx.beginPath();
        ctx.arc(cx, cy, (radius / 3) * r, 0, Math.PI * 2);
        ctx.stroke();
      }
      ctx.beginPath();
      ctx.moveTo(cx, cy - radius);
      ctx.lineTo(cx, cy + radius);
      ctx.moveTo(cx - radius, cy);
      ctx.lineTo(cx + radius, cy);
      ctx.stroke();

      ctx.fillStyle = "rgba(0,161,155,0.6)";
      ctx.font = "10px 'JetBrains Mono', monospace";
      [5, 10, 15].forEach((km, i) => {
        ctx.fillText(`${km} km`, cx + 4, cy - (radius / 3) * (i + 1) + 12);
      });

      // convective cells
      cells.forEach((cell) => {
        if (!reduced) {
          cell.x += cell.vx * dt * 2.4;
          cell.y += cell.vy * dt * 2.4;
          if (cell.x < -110) cell.x = 110;
          if (cell.y > 110) cell.y = -110;
        }
        const sx = cx + (cell.x / 100) * radius * spread;
        const sy = cy + (cell.y / 100) * radius * spread;
        const r = cell.radius * (0.7 + preset.intensity * 0.7);
        const g = ctx.createRadialGradient(sx, sy, 2, sx, sy, r);
        const punch = 0.35 + preset.intensity * 0.65;
        if (cell.dbz > 55) {
          g.addColorStop(0, `rgba(255,0,180,${0.85 * punch})`);
          g.addColorStop(0.3, `rgba(255,30,0,${0.75 * punch})`);
          g.addColorStop(0.6, `rgba(255,200,0,${0.5 * punch})`);
          g.addColorStop(1, "rgba(0,200,50,0)");
        } else if (cell.dbz > 40) {
          g.addColorStop(0, `rgba(255,60,0,${0.75 * punch})`);
          g.addColorStop(0.5, `rgba(255,220,0,${0.5 * punch})`);
          g.addColorStop(1, "rgba(0,180,80,0)");
        } else {
          g.addColorStop(0, `rgba(0,220,80,${0.6 * punch})`);
          g.addColorStop(1, "rgba(0,100,200,0)");
        }
        ctx.fillStyle = g;
        ctx.beginPath();
        ctx.arc(sx, sy, r, 0, Math.PI * 2);
        ctx.fill();
      });

      // circuit at the centre
      ctx.fillStyle = "#ffffff";
      ctx.beginPath();
      ctx.arc(cx, cy, 3.4, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = "#e9eff5";
      ctx.font = "700 11px 'Chakra Petch', sans-serif";
      ctx.fillText("SEPANG (SIC)", cx + 8, cy - 6);

      // sweep
      if (!reduced) {
        const angle = (now * 0.0016) % (Math.PI * 2);
        const sweep = ctx.createLinearGradient(
          cx,
          cy,
          cx + Math.cos(angle) * radius,
          cy + Math.sin(angle) * radius
        );
        sweep.addColorStop(0, "rgba(0,255,200,0.5)");
        sweep.addColorStop(1, "rgba(0,255,200,0)");
        ctx.strokeStyle = sweep;
        ctx.lineWidth = 1.6;
        ctx.beginPath();
        ctx.moveTo(cx, cy);
        ctx.lineTo(cx + Math.cos(angle) * radius, cy + Math.sin(angle) * radius);
        ctx.stroke();
      }

      // wind bearing
      const wind = ((CLIMATE.windBearingDeg - 90) * Math.PI) / 180;
      ctx.strokeStyle = "rgba(233,239,245,0.5)";
      ctx.lineWidth = 1.4;
      ctx.beginPath();
      ctx.moveTo(cx + Math.cos(wind) * (radius - 46), cy + Math.sin(wind) * (radius - 46));
      ctx.lineTo(cx + Math.cos(wind) * (radius - 12), cy + Math.sin(wind) * (radius - 12));
      ctx.stroke();
      ctx.fillStyle = "rgba(233,239,245,0.7)";
      ctx.font = "9px 'JetBrains Mono', monospace";
      ctx.fillText(
        `${CLIMATE.windKph} kph ${CLIMATE.windBearingDeg}°`,
        cx + Math.cos(wind) * (radius - 44) - 22,
        cy + Math.sin(wind) * (radius - 44) - 8
      );

      if (visible && !reduced) raf = requestAnimationFrame(draw);
    };

    raf = requestAnimationFrame(draw);
    return () => cancelAnimationFrame(raf);
  }, [mode, visible, reduced]);

  return (
    <div className="radar" ref={hostRef}>
      <canvas
        ref={canvasRef}
        className="radar__canvas"
        role="img"
        aria-label="Doppler radar showing convective cells around the circuit"
      />
      <div className="radar__scale" aria-hidden="true">
        <span className="t-overline dim-2">dBZ</span>
        <i style={{ background: "rgba(0,220,80,0.8)" }} />
        <i style={{ background: "rgba(255,220,0,0.85)" }} />
        <i style={{ background: "rgba(255,60,0,0.85)" }} />
        <i style={{ background: "rgba(255,0,180,0.85)" }} />
        <span className="t-caption dim-2">light → torrential</span>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ *
 * section
 * ------------------------------------------------------------------ */

export function MonsoonCentre() {
  const [mode, setMode] = useState("squall");
  const [intensity, setIntensity] = useState(6);
  const [currentTyre, setCurrentTyre] = useState("medium");
  const [lapsLeft, setLapsLeft] = useState(24);

  const preset = WEATHER_MODES[mode];
  const depth = useMemo(() => depthAtIntensity(intensity), [intensity]);
  const klass = classifyDepth(depth.meanMm);

  const call = useMemo(
    () =>
      crossoverCall({
        waterMm: depth.meanMm,
        currentTyre,
        lapsRemaining: lapsLeft,
        pitLossS: PIT.wetLossS
      }),
    [depth.meanMm, currentTyre, lapsLeft]
  );

  const abandoned = depth.meanMm > CLIMATE.abandonThresholdMm;

  const equilibriumSeries = useMemo(
    () => [
      {
        name: "Sector 1",
        colour: "#f5b002",
        points: EQUILIBRIUM.map((r) => [r.intensity, r.s1]),
        dots: true
      },
      {
        name: "Sector 2",
        colour: "#ff5a5f",
        points: EQUILIBRIUM.map((r) => [r.intensity, r.s2]),
        dots: true
      },
      {
        name: "Sector 3",
        colour: "#8b6cf0",
        points: EQUILIBRIUM.map((r) => [r.intensity, r.s3]),
        dots: true
      },
      {
        name: "Mean",
        colour: "#adbdcb",
        points: EQUILIBRIUM.map((r) => [r.intensity, r.meanMm]),
        dash: "5 4",
        width: 1.5
      }
    ],
    []
  );

  const dryingData = useMemo(
    () =>
      DRYING_CURVE.map((v, i) => ({
        key: `drying-${i + 1}`,
        label: i % 3 === 0 ? String(i + 1) : "",
        value: v,
        colour: v > CLIMATE.abandonThresholdMm ? "#ff5a5f" : v > 1.4 ? "#3498db" : "#00a19b"
      })),
    []
  );

  return (
    <Section
      id="monsoon"
      no="05 / Monsoon centre"
      title="The weather is the strategy"
      lede="Tropical rain rapidly floods the circuit before drainage reaches equilibrium. Poorly drained Sector 2 floods first and clears last."
      aside={
        <Segmented
          label="Weather state"
          value={mode}
          onChange={setMode}
          options={Object.values(WEATHER_MODES).map((m) => ({
            value: m.key,
            label: m.name
          }))}
        />
      }
    >
      {/* Visual Monsoon Storm Deck */}
      <Reveal delay={20}>
        <div className="visual-deck" style={{ marginBottom: "var(--s6)" }}>
          <div className="visual-deck__media" style={{ maxHeight: "380px" }}>
            <img
              src="/assets/img/monsoon_action.jpg"
              alt="Ferrari F1 car in torrential Sepang monsoon storm"
              className="visual-deck__img"
              loading="lazy"
            />
            <div className="visual-deck__scrim" />
            <div className="visual-deck__content">
              <div className="visual-deck__badges">
                <Pill tone="fail" live>Tropical Squall Live</Pill>
                <Pill tone="teal">Doppler Convective Radar</Pill>
                <Pill tone="warn">Aquaplaning Critical: {depth.meanMm.toFixed(2)} mm</Pill>
              </div>
              <h3 className="visual-deck__title">Equatorial Monsoon · Rapid Saturation Model</h3>
              <p className="visual-deck__lede">
                Convective squalls overwhelm tyre tread dispersion in 90 seconds, producing heavy standing water through Turns 7–9.
              </p>
              <div className="visual-deck__stats">
                <div className="visual-stat">
                  <span className="visual-stat__label">Current Mean Depth</span>
                  <span className="visual-stat__value">{depth.meanMm.toFixed(2)} mm</span>
                </div>
                <div className="visual-stat">
                  <span className="visual-stat__label">Classification</span>
                  <span className="visual-stat__value">{klass.name}</span>
                </div>
                <div className="visual-stat">
                  <span className="visual-stat__label">Optimal Tyre</span>
                  <span className="visual-stat__value">{klass.best}</span>
                </div>
                <div className="visual-stat">
                  <span className="visual-stat__label">Abandon Threshold</span>
                  <span className="visual-stat__value">{CLIMATE.abandonThresholdMm} mm</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </Reveal>

      <div className="monsoon">
        <Reveal className="monsoon__radar">
          <Panel
            title="Doppler radar"
            meta={`Cell front ${preset.cellDistanceKm.toFixed(1)} km out`}
            note={CLIMATE.note}
          >
            <Radar mode={mode} />
            <p className="t-small" style={{ marginTop: "var(--s4)" }}>
              <b>{preset.name}.</b> {preset.blurb}
            </p>
            <div className="grid cols-4" style={{ marginTop: "var(--s4)" }}>
              <Stat value={preset.airTempC} unit="°C" decimals={1} label="Air" animate={false} />
              <Stat value={preset.trackTempC} unit="°C" decimals={1} label="Track" animate={false} />
              <Stat value={preset.humidityPct} unit="%" label="Humidity" animate={false} />
              <Stat
                value={Math.round(preset.intensity * 60)}
                unit="mm/h"
                label="Rain rate"
                animate={false}
                tone={preset.intensity > 0.6 ? "hot" : undefined}
              />
            </div>
            <div className="monsoon__sectors">
              {SECTOR_DRAINAGE.map((s, i) => (
                <div className="monsoon__sector" key={s.id}>
                  <div className="monsoon__sectorhead">
                    <span className="t-overline">{s.name}</span>
                    <Pill tone={s.drainage === "Poor" ? "fail" : s.drainage === "Good" ? "pass" : "warn"}>
                      {s.drainage}
                    </Pill>
                  </div>
                  <div className="monsoon__bar">
                    <i style={{ width: `${Math.min(100, preset.sectorRain[i] * 100)}%` }} />
                  </div>
                  <p className="t-caption dim-2">{s.note}</p>
                </div>
              ))}
            </div>
          </Panel>
        </Reveal>

        <Reveal className="monsoon__call" delay={80}>
          <Panel
            title="Crossover advisor"
            meta="Live"
            note="Exactly the rule the race engine uses: per-lap gain times laps remaining, against the pit loss. No margin, no gut feel."
          >
            <Field
              label="Rain intensity"
              value={intensity}
              min={0}
              max={10}
              step={0.5}
              onChange={setIntensity}
              hint={`${intensity.toFixed(1)} / 10`}
            />
            <Field
              label="Laps remaining"
              value={lapsLeft}
              min={1}
              max={56}
              step={1}
              onChange={setLapsLeft}
              hint={`${lapsLeft} laps`}
            />
            <div className="field">
              <span className="field__row">
                <span className="field__l t-overline">Tyre currently fitted</span>
              </span>
              <Segmented
                label="Tyre currently fitted"
                value={currentTyre}
                onChange={setCurrentTyre}
                options={[
                  { value: "medium", label: "Slick" },
                  { value: "inter", label: "Inter" },
                  { value: "wet", label: "Wet" }
                ]}
              />
            </div>

            <div className="callout" data-tone={abandoned ? "fail" : call.verdict === "box-now" ? "warn" : "pass"}>
              <div className="callout__head">
                <span className="t-overline">
                  {abandoned
                    ? "Race control: red flag"
                    : call.verdict === "box-now"
                      ? "Box this lap"
                      : "Stay out"}
                </span>
                <Pill tone={klass.tone}>{klass.label}</Pill>
              </div>
              <p className="callout__body t-small">
                {abandoned
                  ? `Mean depth ${depth.meanMm.toFixed(2)} mm is past the ${CLIMATE.abandonThresholdMm} mm abandonment threshold. The tyre choice stops mattering — this race gets stopped, and if it is before three quarters distance it pays half points.`
                  : call.reason}
              </p>
              {!abandoned ? (
                <div className="callout__grid">
                  <div>
                    <span className="t-overline dim-2">On now</span>
                    <b className="mono">{call.currentLapS.toFixed(2)} s</b>
                  </div>
                  <div>
                    <span className="t-overline dim-2">Quickest tyre</span>
                    <b>
                      <Tyre compound={call.targetTyre} showName={false} />{" "}
                      <span className="mono">{call.targetLapS.toFixed(2)} s</span>
                    </b>
                  </div>
                  <div>
                    <span className="t-overline dim-2">Gain a lap</span>
                    <b className="mono">{call.perLapGain.toFixed(2)} s</b>
                  </div>
                  <div>
                    <span className="t-overline dim-2">Net over {lapsLeft} laps</span>
                    <b className="mono" style={{ color: call.netGain > 0 ? "var(--green)" : "var(--rose)" }}>
                      {call.netGain > 0 ? "+" : "−"}
                      {Math.abs(call.netGain).toFixed(1)} s
                    </b>
                  </div>
                </div>
              ) : null}
            </div>

            <div className="grid cols-3" style={{ marginTop: "var(--s5)" }}>
              <Stat
                value={depth.meanMm}
                unit="mm"
                decimals={2}
                label="Mean depth"
                animate={false}
                tone={depth.meanMm > CLIMATE.abandonThresholdMm ? "hot" : undefined}
              />
              <Stat
                value={depth.s2}
                unit="mm"
                decimals={2}
                label="Sector 2 depth"
                animate={false}
                tone="warn"
                note="Floods first"
              />
              <Stat
                value={PIT.wetLossS}
                unit="s"
                decimals={2}
                label="Wet pit loss"
                animate={false}
              />
            </div>

            <p className="panel__note">
              DRS is disabled by race control once mean wetness passes{" "}
              {CLIMATE.drsCutoffWetness}, and aquaplaning risk is flagged above{" "}
              {CLIMATE.aquaplaningThresholdMm} mm — both of which happen well before the
              abandonment threshold.
            </p>
          </Panel>
        </Reveal>
      </div>

      <div className="grid cols-2" style={{ marginTop: "var(--s6)" }}>
        <Reveal>
          <Panel
            title="Where each intensity settles"
            meta="Bounded equilibrium, by sector"
            note="Because run-off scales with depth, every intensity reaches a steady state. That is what makes the crossover call tractable: you are not chasing a number that grows without limit."
          >
            <LineChart
              series={equilibriumSeries}
              xLabel="Rain intensity (out of 10)"
              yLabel="Standing water (mm)"
              formatX={(v) => String(v)}
              formatY={(v) => v.toFixed(1)}
              height={290}
              bands={[
                {
                  from: 0,
                  to: 10,
                  fill: "transparent"
                }
              ]}
            />
            <div className="tbl-scroll" style={{ marginTop: "var(--s4)" }}>
              <table className="tbl">
                <thead>
                  <tr>
                    <th className="r">Intensity</th>
                    <th className="r">Mean</th>
                    <th className="r">S1</th>
                    <th className="r">S2</th>
                    <th className="r">S3</th>
                    <th>Classified</th>
                  </tr>
                </thead>
                <tbody>
                  {EQUILIBRIUM.map((r) => (
                    <tr key={r.intensity}>
                      <td className="r">{r.intensity}/10</td>
                      <td className="r">{r.meanMm.toFixed(2)}</td>
                      <td className="r">{r.s1.toFixed(2)}</td>
                      <td className="r" style={{ color: "var(--rose)" }}>
                        {r.s2.toFixed(2)}
                      </td>
                      <td className="r">{r.s3.toFixed(2)}</td>
                      <td className="dim">{r.label}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Panel>
        </Reveal>

        <Reveal delay={80}>
          <Panel
            title="Drying after a cell passes"
            meta="Mean depth by lap · peak 6.37 mm"
            note="Seventeen laps from first drops to a dry track. The window where an intermediate is the right tyre is wide going in and narrow coming out — which is where races are won."
          >
            <BarChart
              data={dryingData}
              xLabel="Laps since the cell arrived"
              yLabel="Mean depth (mm)"
              formatY={(v) => v.toFixed(1)}
              height={280}
              threshold={{
                value: CLIMATE.abandonThresholdMm,
                label: `Abandon ${CLIMATE.abandonThresholdMm} mm`
              }}
            />
            <div className="grid cols-3" style={{ marginTop: "var(--s4)" }}>
              <Stat value={6.37} unit="mm" decimals={2} label="Peak depth" />
              <Stat value={8} label="Lap of the peak" note="Then run-off wins" />
              <Stat value={17} label="Laps to fully dry" tone="good" />
            </div>
          </Panel>
        </Reveal>
      </div>
    </Section>
  );
}

/**
 * Tyre lab: compound behaviour, the degradation curves, and the stint quantiles.
 */

import { useMemo, useState } from "react";

import { COMPOUNDS, CROSSOVER, DRY_COMPOUNDS, THERMAL, degLossS } from "../data/tyres.js";
import { Reveal, Section, Panel, Pill, Field, Stat, Tyre } from "./ui.jsx";
import { LineChart, RankBars } from "./charts.jsx";

export function TyreLab() {
  const [stintLength, setStintLength] = useState(20);
  const [focus, setFocus] = useState("medium");

  const degSeries = useMemo(
    () =>
      DRY_COMPOUNDS.map((key) => {
        const c = COMPOUNDS[key];
        const points = [];
        for (let age = 0; age <= 36; age += 1) {
          points.push([age, +(c.freshDeltaS + degLossS(key, age)).toFixed(3)]);
        }
        return {
          name: `${c.name} (${c.code})`,
          colour: c.hex,
          points,
          width: key === focus ? 2.8 : 1.6
        };
      }),
    [focus]
  );

  const cumulativeSeries = useMemo(
    () =>
      DRY_COMPOUNDS.map((key) => {
        const c = COMPOUNDS[key];
        const points = [];
        let sum = 0;
        for (let age = 0; age <= 36; age += 1) {
          if (age > 0) sum += c.freshDeltaS + degLossS(key, age - 1);
          points.push([age, +sum.toFixed(2)]);
        }
        return {
          name: `${c.name} cumulative`,
          colour: c.hex,
          points,
          width: key === focus ? 2.8 : 1.6
        };
      }),
    [focus]
  );

  const stintCost = useMemo(
    () =>
      DRY_COMPOUNDS.map((key) => {
        const c = COMPOUNDS[key];
        let sum = 0;
        for (let age = 0; age < stintLength; age += 1) {
          sum += c.freshDeltaS + degLossS(key, age);
        }
        return { key, label: c.name, value: +sum.toFixed(1), colour: c.hex, cliff: c.cliffLap };
      }).sort((a, b) => a.value - b.value),
    [stintLength]
  );

  const crossSeries = useMemo(
    () => [
      {
        name: "Slick (medium)",
        colour: COMPOUNDS.medium.hex,
        points: CROSSOVER.map((r) => [r.waterMm, r.medium]),
        dots: true
      },
      {
        name: "Intermediate",
        colour: COMPOUNDS.inter.hex,
        points: CROSSOVER.map((r) => [r.waterMm, r.inter]),
        dots: true
      },
      {
        name: "Full wet",
        colour: COMPOUNDS.wet.hex,
        points: CROSSOVER.map((r) => [r.waterMm, r.wet]),
        dots: true
      }
    ],
    []
  );

  const best = stintCost[0];

  return (
    <Section
      id="tyres"
      no="04 / Tyre lab"
      title="On 54 degree asphalt, tyres are the whole argument"
      lede="Thermal degradation rules Sepang. High lateral loads in Turns 5 and 11 drive carcass temperatures past the blister threshold."
      aside={<Pill tone="warn">Track {THERMAL.trackTempC} °C</Pill>}
    >
      {/* Visual Tyre Bay Command Deck */}
      <Reveal delay={20}>
        <div className="visual-deck" style={{ marginBottom: "var(--s6)" }}>
          <div className="visual-deck__media" style={{ maxHeight: "360px" }}>
            <img
              src="/assets/img/tyre_garage.jpg"
              alt="Ferrari F1 Pit Garage Tyre Bay with Heated Blankets"
              className="visual-deck__img"
              loading="lazy"
            />
            <div className="visual-deck__scrim" />
            <div className="visual-deck__content">
              <div className="visual-deck__badges">
                <Pill tone="red">Pirelli Allocation</Pill>
                <Pill tone="warn">Electric Blankets: 100°C Active</Pill>
                <Pill tone="teal">Sepang High Abrasion Surface</Pill>
              </div>
              <h3 className="visual-deck__title">Tyre Thermal Management · The Right-Front Gauntlet</h3>
              <p className="visual-deck__lede">
                Asphalt surface reaches 54°C under the equatorial sun. High sustained lateral g-forces through the double-apex Turn 5–6 quickly overheat the shoulder ribs, making tyre conservation the defining factor of race pace.
                Track temps hit 54°C. Severe lateral loading through Turns 5–6 rapidly overheats the shoulder ribs, making thermal management vital.
              </p>
              <div className="visual-deck__stats">
                <div className="visual-stat">
                  <span className="visual-stat__label">Peak Track Temp</span>
                  <span className="visual-stat__value">{THERMAL.trackTempC}°C</span>
                </div>
                <div className="visual-stat">
                  <span className="visual-stat__label">Soft (C4) Cliff</span>
                  <span className="visual-stat__value">{COMPOUNDS.soft.cliffLap} Laps</span>
                </div>
                <div className="visual-stat">
                  <span className="visual-stat__label">Medium (C3) Cliff</span>
                  <span className="visual-stat__value">{COMPOUNDS.medium.cliffLap} Laps</span>
                </div>
                <div className="visual-stat">
                  <span className="visual-stat__label">Hard (C2) Cliff</span>
                  <span className="visual-stat__value">{COMPOUNDS.hard.cliffLap} Laps</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </Reveal>

      <div className="grid cols-auto" style={{ marginBottom: "var(--s6)" }}>
        {Object.values(COMPOUNDS).map((c, i) => (
          <Reveal key={c.key} delay={i * 50}>
            <button
              type="button"
              className="tyrecard"
              data-on={focus === c.key}
              onClick={() => setFocus(c.key)}
              aria-pressed={focus === c.key}
            >
              <span className="tyrecard__top">
                <Tyre compound={c.key} showName={false} />
                <span className="t-overline">{c.name}</span>
                <span className="t-caption dim-2">{c.code}</span>
              </span>
              <span className="tyrecard__nums">
                <span>
                  <b className="mono">
                    {c.freshDeltaS > 0 ? "+" : ""}
                    {c.freshDeltaS.toFixed(2)}
                  </b>
                  <i className="t-overline dim-2">fresh delta</i>
                </span>
                <span>
                  <b className="mono">{c.cliffLap}</b>
                  <i className="t-overline dim-2">cliff lap</i>
                </span>
                <span>
                  <b className="mono">{c.optimalTempC}°</b>
                  <i className="t-overline dim-2">optimal</i>
                </span>
              </span>
              <span className="t-small dim tyrecard__blurb">{c.character}</span>
            </button>
          </Reveal>
        ))}
      </div>

      <Reveal>
        <Panel title={`${COMPOUNDS[focus].name} at Sepang`} meta={COMPOUNDS[focus].code}>
          <p className="t-body">{COMPOUNDS[focus].sepang}</p>
        </Panel>
      </Reveal>

      <div className="grid cols-2" style={{ marginTop: "var(--s6)" }}>
        <Reveal>
          <Panel
            title="Pace as the tyre ages"
            meta="Seconds a lap slower than an ideal tyre"
            note="The steep tail past each cliff lap is the reason a plan that runs a soft 20 laps is never fast, whatever the average suggests."
          >
            <LineChart
              series={degSeries}
              xLabel="Tyre age (laps)"
              yLabel="Seconds a lap"
              formatX={(v) => String(Math.round(v))}
              formatY={(v) => v.toFixed(1)}
              height={290}
              bands={DRY_COMPOUNDS.map((k) => ({
                from: COMPOUNDS[k].cliffLap,
                to: COMPOUNDS[k].cliffLap + 0.25,
                fill: "rgba(255,90,95,0.35)"
              }))}
            />
          </Panel>
        </Reveal>

        <Reveal delay={80}>
          <Panel
            title="Cumulative cost of a stint"
            meta="Total seconds surrendered"
            note="Fitted to the published quantile study: 16.1 s over 14 laps of soft, 30.3 s over 20 laps of medium, 58.8 s over 28 laps of hard."
          >
            <LineChart
              series={cumulativeSeries}
              xLabel="Stint length (laps)"
              yLabel="Total seconds lost"
              formatX={(v) => String(Math.round(v))}
              formatY={(v) => String(Math.round(v))}
              height={290}
            />
          </Panel>
        </Reveal>
      </div>

      <div className="grid cols-2" style={{ marginTop: "var(--s6)" }}>
        <Reveal>
          <Panel title="Which tyre for this stint length?" meta="Live">
            <Field
              label="Stint length"
              value={stintLength}
              min={6}
              max={36}
              step={1}
              onChange={setStintLength}
              hint={`${stintLength} laps`}
            />
            <div style={{ marginTop: "var(--s5)" }}>
              <RankBars
                rows={stintCost.map((r) => ({
                  label: r.label,
                  value: r.value,
                  colour: r.colour
                }))}
                formatValue={(v) => `${v.toFixed(1)} s`}
              />
            </div>
            <p className="t-small" style={{ marginTop: "var(--s4)" }}>
              Over {stintLength} laps the <b>{best.label.toLowerCase()}</b> gives away the least,{" "}
              <span className="mono">{best.value.toFixed(1)} s</span>. Its cliff is at lap{" "}
              {best.cliff}
              {stintLength > best.cliff
                ? `, so you are ${stintLength - best.cliff} laps beyond it and paying for it.`
                : ", so this stint stays inside it."}
            </p>
            <p className="panel__note">
              Degradation only. Add the pit loss and the fuel effect in the strategy lab to price a
              whole race.
            </p>
          </Panel>
        </Reveal>

        <Reveal delay={80}>
          <Panel
            title="Stint quantiles"
            meta="350 Monte Carlo tyre sets"
            note="The band between P10 and P90 is the honest measure of how much of a stint you actually control. Roughly seven seconds of it, on every compound."
          >
            <div className="tbl-scroll">
              <table className="tbl">
                <thead>
                  <tr>
                    <th>Compound</th>
                    <th className="r">Laps</th>
                    <th className="r">P10</th>
                    <th className="r">P50</th>
                    <th className="r">P90</th>
                    <th className="r">Band</th>
                  </tr>
                </thead>
                <tbody>
                  {DRY_COMPOUNDS.map((k) => {
                    const c = COMPOUNDS[k];
                    return (
                      <tr key={k} className={k === focus ? "is-hero" : undefined}>
                        <td>
                          <Tyre compound={k} showCode />
                        </td>
                        <td className="r">{c.stint.laps}</td>
                        <td className="r">{c.stint.p10.toFixed(1)}</td>
                        <td className="r">{c.stint.p50.toFixed(1)}</td>
                        <td className="r">{c.stint.p90.toFixed(1)}</td>
                        <td className="r dim">
                          {(c.stint.p90 - c.stint.p10).toFixed(1)} s
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            <div className="grid cols-2" style={{ marginTop: "var(--s5)" }}>
              <Stat
                value={THERMAL.trackTempC}
                unit="°C"
                decimals={1}
                label="Track temperature"
                note={`Air ${THERMAL.airTempC} °C, humidity ${THERMAL.humidityPct}%`}
                tone="warn"
              />
              <Panel title="Worst-loaded tyre" lit={false}>
                <p className="stat__v">{THERMAL.worstTyre}</p>
                <p className="t-caption dim">
                  Turns {THERMAL.worstCorners.join(" and ")}
                </p>
              </Panel>
            </div>
          </Panel>
        </Reveal>
      </div>

      <Reveal delay={60} style={{ marginTop: "var(--s6)" }}>
        <Panel
          title="The wet crossover"
          meta="Lap time against standing water"
          note="The reference figure for slicks on a wet track is roughly ten seconds a lap. The model produces that from physics plus a tread term rather than as a constant — which is why the penalty stops growing past about 3 mm, where the slick is already sliding rather than gripping."
        >
          <LineChart
            series={crossSeries}
            xLabel="Standing water (mm)"
            yLabel="Lap time (s)"
            formatX={(v) => v.toFixed(1)}
            formatY={(v) => v.toFixed(0)}
            height={310}
            bands={[
              { from: 0, to: 0.3, fill: "rgba(245,176,2,0.09)" },
              { from: 1.4, to: 3.5, fill: "rgba(46,204,113,0.09)" },
              { from: 5.0, to: 7.0, fill: "rgba(52,152,219,0.1)" }
            ]}
          />
          <div className="chart__legend" style={{ marginTop: 0 }}>
            <span className="chart__key">
              <i style={{ background: "rgba(245,176,2,0.5)" }} />
              Slick territory
            </span>
            <span className="chart__key">
              <i style={{ background: "rgba(46,204,113,0.5)" }} />
              Intermediate territory
            </span>
            <span className="chart__key">
              <i style={{ background: "rgba(52,152,219,0.5)" }} />
              Full wet territory
            </span>
          </div>
          <div className="tbl-scroll" style={{ marginTop: "var(--s5)" }}>
            <table className="tbl">
              <thead>
                <tr>
                  <th className="r">Water</th>
                  <th className="r">Medium slick</th>
                  <th className="r">Intermediate</th>
                  <th className="r">Full wet</th>
                  <th>Correct tyre</th>
                  <th className="r">Slick penalty</th>
                </tr>
              </thead>
              <tbody>
                {CROSSOVER.map((r) => (
                  <tr key={r.waterMm}>
                    <td className="r">{r.waterMm.toFixed(1)} mm</td>
                    <td className="r">{r.medium.toFixed(2)}</td>
                    <td className="r">{r.inter.toFixed(2)}</td>
                    <td className="r">{r.wet.toFixed(2)}</td>
                    <td>
                      <Tyre compound={r.correct === "medium" ? "medium" : r.correct} />
                    </td>
                    <td className="r">
                      {r.slickPenaltyS ? `+${r.slickPenaltyS.toFixed(1)} s` : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Panel>
      </Reveal>
    </Section>
  );
}

/**
 * Strategy lab.
 *
 * The ranking on the right is computed in the browser, live, from the same model
 * that is calibrated to the documented 1146-plan search. Drag a slider and every
 * plan is repriced on the same frame.
 *
 * The stint chart plots time lost per lap rather than an absolute clock, for the
 * reason set out in PACE_BASELINE_NOTE: the optimiser's baseline is a clean-air
 * reference that is quicker than the full race simulation, so an absolute lap
 * time from it would not be comparable to anything else on this page.
 */

import { useMemo, useState } from "react";

import {
  PACE_BASELINE_NOTE,
  PIT,
  RACE,
  REFERENCE_RANKING,
  UNCERTAINTY,
  formatDelta,
  formatRaceTime,
  lapTrace,
  optimise,
  planLabel,
  raceTimeS
} from "../data/strategy.js";
import { COMPOUNDS, DRY_COMPOUNDS } from "../data/tyres.js";
import { Reveal, Section, Panel, Pill, Field, Segmented, Stat, GapNote, Tyre } from "./ui.jsx";
import { LineChart, StintTimeline } from "./charts.jsx";

function stintsForTimeline(stints) {
  return stints.map((s) => ({
    ...s,
    hex: COMPOUNDS[s.compound].hex,
    letter: COMPOUNDS[s.compound].letter
  }));
}

export function StrategyLab() {
  const [laps, setLaps] = useState(RACE.laps);
  const [pitLoss, setPitLoss] = useState(PIT.measuredLossS);
  const [maxStops, setMaxStops] = useState(3);
  const [allowHard, setAllowHard] = useState(true);
  const [selected, setSelected] = useState(0);

  const allowed = useMemo(
    () => (allowHard ? DRY_COMPOUNDS : DRY_COMPOUNDS.filter((c) => c !== "hard")),
    [allowHard]
  );

  const result = useMemo(
    () =>
      optimise({
        laps,
        pitLossS: pitLoss,
        maxStops,
        stepLaps: 2,
        allowed,
        limit: 8
      }),
    [laps, pitLoss, maxStops, allowed]
  );

  const chosen = result.ranking[Math.min(selected, result.ranking.length - 1)] ?? null;

  const trace = useMemo(
    () => (chosen ? lapTrace(chosen.stints, laps) : []),
    [chosen, laps]
  );

  const lossSeries = useMemo(() => {
    if (!trace.length) return [];
    const best = Math.min(...trace.map((t) => t.lapS));
    return [
      {
        name: "Time lost per lap",
        colour: "#d81f26",
        points: trace.map((t) => [t.lap, +(t.lapS - best).toFixed(3)])
      }
    ];
  }, [trace]);

  const pitBands = useMemo(() => {
    if (!chosen) return [];
    const out = [];
    let cursor = 0;
    chosen.stints.forEach((s, i) => {
      cursor += s.laps;
      if (i < chosen.stints.length - 1) {
        out.push({
          from: cursor + 0.5,
          to: cursor + 1.5,
          fill: "rgba(233,239,245,0.12)"
        });
      }
    });
    return out;
  }, [chosen]);

  const referenceTime = raceTimeS(RACE.referencePlan, RACE.laps, PIT.measuredLossS);
  const atDefaults =
    laps === RACE.laps && Math.abs(pitLoss - PIT.measuredLossS) < 0.01 && maxStops === 3 && allowHard;

  return (
    <Section
      id="strategy"
      no="03 / Strategy lab"
      title="Price every plan, then argue with it"
      lede="Adjust race laps, pit delta, and compound allocation to reprice all feasible stint strategies in real time."
      aside={<Pill tone="teal">{result.evaluated.toLocaleString("en-GB")} feasible plans</Pill>}
    >
      <div className="lab">
        <Reveal className="lab__controls">
          <Panel title="Race setup" meta="Live model">
            <div className="lab__fields">
              <Field
                label="Race laps"
                value={laps}
                min={30}
                max={70}
                step={2}
                onChange={(v) => {
                  setLaps(v);
                  setSelected(0);
                }}
                hint={`${laps} laps · ${((laps * 5.543)).toFixed(1)} km`}
              />
              <Field
                label="Pit loss"
                value={pitLoss}
                min={14}
                max={30}
                step={0.5}
                onChange={(v) => {
                  setPitLoss(v);
                  setSelected(0);
                }}
                hint={`${pitLoss.toFixed(1)} s`}
              />
              <div className="field">
                <span className="field__row">
                  <span className="field__l t-overline">Maximum stops</span>
                </span>
                <Segmented
                  label="Maximum stops"
                  value={maxStops}
                  onChange={(v) => {
                    setMaxStops(v);
                    setSelected(0);
                  }}
                  options={[
                    { value: 1, label: "1" },
                    { value: 2, label: "2" },
                    { value: 3, label: "3" }
                  ]}
                />
              </div>
              <div className="field">
                <span className="field__row">
                  <span className="field__l t-overline">Compounds available</span>
                </span>
                <Segmented
                  label="Compounds available"
                  value={allowHard}
                  onChange={(v) => {
                    setAllowHard(v);
                    setSelected(0);
                  }}
                  options={[
                    { value: true, label: "S · M · H" },
                    { value: false, label: "S · M only" }
                  ]}
                />
              </div>
            </div>

            <div className="lab__ref">
              <p className="t-caption dim-2">
                Reference: the documented exhaustive search found{" "}
                {UNCERTAINTY.feasiblePlans.toLocaleString("en-GB")} feasible plans in{" "}
                {UNCERTAINTY.searchTimeS} s and put{" "}
                <b style={{ color: "var(--ink-2)" }}>{planLabel(RACE.referencePlan)}</b> first at{" "}
                <span className="mono">{formatRaceTime(RACE.referenceTimeS)}</span>. This model is
                calibrated to reproduce that exactly — it currently gives{" "}
                <span className="mono">{formatRaceTime(referenceTime)}</span> for the same plan.
              </p>
              {!atDefaults ? (
                <button
                  type="button"
                  className="btn btn--ghost btn--sm"
                  onClick={() => {
                    setLaps(RACE.laps);
                    setPitLoss(PIT.measuredLossS);
                    setMaxStops(3);
                    setAllowHard(true);
                    setSelected(0);
                  }}
                >
                  Reset to the real race
                </button>
              ) : null}
            </div>
          </Panel>

          <Panel title="Pit model" meta={`MAE ${PIT.maeS} s`} className="lab__pit">
            <div className="grid cols-2">
              <Stat
                value={PIT.measuredLossS}
                unit="s"
                decimals={1}
                label="Dry pit loss"
                note="Measured Sepang delta"
              />
              <Stat
                value={PIT.wetLossS}
                unit="s"
                decimals={2}
                label="Wet pit loss"
                note="Lower, because racing speed already is"
              />
              <Stat
                value={PIT.speedLimitedM}
                unit="m"
                label="Speed-limited length"
                note={`Back-solved at the ${PIT.pitSpeedKph} kph limit`}
              />
              <Stat
                value={PIT.maeS}
                unit="s"
                decimals={3}
                label="Mean absolute error"
                note={`${PIT.sampledStops.toLocaleString("en-GB")} sampled stops · bar ${PIT.barS} s`}
                tone="good"
              />
            </div>
          </Panel>
        </Reveal>

        <Reveal className="lab__output" delay={80}>
          <Panel
            title="Ranked plans"
            meta={chosen ? `Best ${formatRaceTime(chosen.timeS)}` : "no feasible plan"}
          >
            {result.ranking.length === 0 ? (
              <p className="t-small dim">
                No plan can cover {laps} laps under these limits. Allow another stop, or put the
                hard tyre back in.
              </p>
            ) : (
              <div className="tbl-scroll">
                <table className="tbl">
                  <thead>
                    <tr>
                      <th>#</th>
                      <th>Plan</th>
                      <th className="r">Stops</th>
                      <th className="r">Race time</th>
                      <th className="r">Loss</th>
                    </tr>
                  </thead>
                  <tbody>
                    {result.ranking.map((r, i) => (
                      <tr
                        key={r.label}
                        className={i === selected ? "is-hero" : undefined}
                        onClick={() => setSelected(i)}
                        style={{ cursor: "pointer" }}
                      >
                        <td className="pos">{r.rank}</td>
                        <td>
                          <span className="lab__plan">
                            {r.stints.map((s, si) => (
                              <span className="lab__planpart" key={si}>
                                <Tyre compound={s.compound} showName={false} />
                                <span className="mono">{s.laps}</span>
                              </span>
                            ))}
                          </span>
                        </td>
                        <td className="r">{r.stops}</td>
                        <td className="r">{formatRaceTime(r.timeS)}</td>
                        <td className="r dim">{r.lossS < 0.0005 ? "—" : formatDelta(r.lossS)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Panel>

          {chosen ? (
            <>
              <Panel
                title="Selected plan"
                meta={`${chosen.label} · ${chosen.stops} stop${chosen.stops === 1 ? "" : "s"}`}
              >
                <StintTimeline
                  stints={stintsForTimeline(chosen.stints)}
                  laps={laps}
                  pitLossS={pitLoss}
                />
                <div className="lab__stints">
                  {chosen.stints.map((s, i) => {
                    const c = COMPOUNDS[s.compound];
                    const overCliff = s.laps > c.cliffLap;
                    return (
                      <div className="lab__stint" key={i}>
                        <Tyre compound={s.compound} showCode />
                        <span className="mono dim">{s.laps} laps</span>
                        {overCliff ? (
                          <Pill tone="warn">{s.laps - c.cliffLap} past the cliff</Pill>
                        ) : (
                          <Pill tone="pass">Inside the cliff</Pill>
                        )}
                      </div>
                    );
                  })}
                </div>
              </Panel>

              <Panel
                title="Where the time goes"
                meta="Time lost per lap against the plan's own quickest lap"
                note={PACE_BASELINE_NOTE}
              >
                <LineChart
                  series={lossSeries}
                  bands={pitBands}
                  xLabel="Lap"
                  yLabel="Seconds lost"
                  formatX={(v) => String(Math.round(v))}
                  formatY={(v) => v.toFixed(1)}
                  height={280}
                  areaUnderFirst
                />
                <p className="t-caption dim-2">
                  Each sawtooth is a stint: degradation climbing, then reset by a stop. The overall
                  downward drift is fuel burning off at {(0.032).toFixed(3)} s a kilogram — which is
                  why a short soft stint is worth more at the end of a race than at the start.
                </p>
              </Panel>
            </>
          ) : null}
        </Reveal>
      </div>

      <div className="grid cols-4" style={{ marginTop: "var(--s7)" }}>
        <Reveal>
          <Stat
            value={UNCERTAINTY.feasiblePlans}
            label="Plans in the reference search"
            note={`Priced exhaustively in ${UNCERTAINTY.searchTimeS} s`}
          />
        </Reveal>
        <Reveal delay={60}>
          <Stat
            value={UNCERTAINTY.unplannedStopsPerRace}
            decimals={2}
            label="Unplanned stops per race"
            note="Crossover calls the plan did not contain"
            tone="warn"
          />
        </Reveal>
        <Reveal delay={120}>
          <Panel title="Race time under uncertainty" lit={false}>
            <p className="stat__v mono">{UNCERTAINTY.p50}</p>
            <p className="t-caption dim">
              P50 across {UNCERTAINTY.runs} runs · P10 {UNCERTAINTY.p10} · P90 {UNCERTAINTY.p90}
            </p>
          </Panel>
        </Reveal>
        <Reveal delay={180}>
          <Panel title="Dry optimum" lit={false}>
            <p className="stat__v mono">{formatRaceTime(RACE.referenceTimeS)}</p>
            <p className="t-caption dim">
              {planLabel(RACE.referencePlan)} — and the next best plan is only{" "}
              {REFERENCE_RANKING[1].lossS} s away, which is why traffic decides real races.
            </p>
          </Panel>
        </Reveal>
      </div>

      <Reveal delay={60} style={{ marginTop: "var(--s6)" }}>
        <GapNote weight="Third" title="the optimiser ignores traffic">
          Plans are ranked on time alone. The search cannot reason about emerging from the pit lane
          behind a train of cars, which at Sepang is usually the real constraint on when you stop.
          Treat the top six as a shortlist, not an instruction.
        </GapNote>
      </Reveal>
    </Section>
  );
}

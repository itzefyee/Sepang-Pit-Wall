import {
  DRY_RACE_RESULT,
  HISTORICAL_CHECKS,
  HISTORICAL_RACES,
  OPEN_GAPS,
  PROVENANCE,
  SCOREBOARD
} from "../data/validation.js";
import { GapNote, Panel, Pill, Reveal, Section, Stat } from "./ui.jsx";

export function Validation() {
  return (
    <Section
      id="model"
      no="09 / The model"
      title="Show the receipts"
      lede="Validation is kept alongside the strategy recommendation, not hidden behind it. The historical scenarios receive only information available before the flag; the outcome belongs to the simulation."
      aside={<Pill tone="pass">Measured outputs</Pill>}
    >
      <div className="grid cols-3 validation__scoreboard">
        {SCOREBOARD.map((stat, index) => (
          <Reveal key={stat.label} delay={index * 55}>
            <Stat value={stat.v} unit={stat.unit} label={stat.label} note={stat.note} tone={stat.tone} />
          </Reveal>
        ))}
      </div>

      <div className="validation__grid">
        <Panel title="Historical checks" meta={<Pill tone="pass">6 / 6 pass</Pill>}>
          <table className="tbl validation__checks">
            <tbody>
              {HISTORICAL_CHECKS.map(({ check, result }) => (
                <tr key={check}>
                  <td>{check}</td>
                  <td className="r"><Pill tone="pass">{result}</Pill></td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="validation__races">
            {HISTORICAL_RACES.map((race) => (
              <article key={race.year}>
                <p className="t-overline hot">{race.year}</p>
                <h3 className="t-h3">{race.name}</h3>
                <p className="t-small dim">{race.story}</p>
                <div className="validation__racefact">
                  <span>Sim top 5</span><strong className="mono">{race.simTop5.join("  ")}</strong>
                </div>
                <div className="validation__racefact">
                  <span>Actual top 5</span><strong className="mono">{race.realTop5.join("  ")}</strong>
                </div>
                <div className="validation__racefact">
                  <span>Peak water</span><strong className="mono">{race.peakWaterMm.toFixed(1)} mm</strong>
                </div>
              </article>
            ))}
          </div>
        </Panel>

        <Panel title="Dry reference race" meta={<span className="t-overline">56 laps</span>}>
          <div className="tbl-scroll">
            <table className="tbl">
              <thead>
                <tr><th>Pos</th><th>Driver</th><th>Team</th><th className="r">Gap</th><th className="r">Stops</th><th>Stints</th></tr>
              </thead>
              <tbody>
                {DRY_RACE_RESULT.map((row) => (
                  <tr key={row.code} className={row.hero ? "is-hero" : undefined}>
                    <td className="pos">{row.pos}</td>
                    <td><strong>{row.code}</strong> <span className="dim-2">{row.driver}</span></td>
                    <td className="dim">{row.team}</td>
                    <td className="r">{row.gap}</td>
                    <td className="r">{row.stops}</td>
                    <td className="mono">{row.stints}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="validation__table-note">Race winner: 1:30:21.632. Real 2017 duration: 1:30:01, for a 0.38% error.</p>
        </Panel>
      </div>

      <div className="validation__gaps">
        <div>
          <p className="t-overline hot">Known limitations</p>
          <h3 className="t-h2">What the model still cannot say</h3>
        </div>
        <div>
          {OPEN_GAPS.map((gap) => (
            <GapNote key={gap.title} weight={gap.weight} title={gap.title}>{gap.body}</GapNote>
          ))}
        </div>
      </div>

      <Panel title="Provenance" meta={<span className="t-overline">Inputs and methods</span>} lit={false}>
        <dl className="validation__provenance">
          {PROVENANCE.map(({ what, detail }) => (
            <div key={what}>
              <dt>{what}</dt>
              <dd>{detail}</dd>
            </div>
          ))}
        </dl>
      </Panel>
    </Section>
  );
}

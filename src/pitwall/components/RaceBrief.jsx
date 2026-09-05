import { CIRCUIT } from "../data/circuit.js";
import { BRIEF, EVENT, SESSIONS } from "../data/schedule.js";
import { UNCERTAINTY } from "../data/strategy.js";
import { useCountdown } from "../hooks.js";
import { Panel, Pill, Reveal, Section, Stat } from "./ui.jsx";

const fmtDay = new Intl.DateTimeFormat("en-GB", {
  weekday: "short",
  day: "numeric",
  month: "short",
  timeZone: "Asia/Kuala_Lumpur"
});

const fmtTime = new Intl.DateTimeFormat("en-GB", {
  hour: "2-digit",
  minute: "2-digit",
  hour12: false,
  timeZone: "Asia/Kuala_Lumpur"
});

const fmtLocal = new Intl.DateTimeFormat(undefined, {
  weekday: "short",
  hour: "2-digit",
  minute: "2-digit",
  hour12: false
});

function SessionRow({ session }) {
  const t = useCountdown(session.startsAt);
  const d = new Date(session.startsAt);
  return (
    <tr className={session.isRace ? "is-hero" : undefined}>
      <td>
        <span className="t-overline" style={{ color: session.isRace ? "var(--red-bright)" : "var(--ink)" }}>
          {session.short}
        </span>
      </td>
      <td className="dim">{session.name}</td>
      <td className="r">{fmtDay.format(d)}</td>
      <td className="r">{fmtTime.format(d)}</td>
      <td className="r dim-2">{fmtLocal.format(d)}</td>
      <td className="r">
        {t.past ? (
          <span className="dim-2">done</span>
        ) : (
          `${t.days}d ${String(t.hours).padStart(2, "0")}h`
        )}
      </td>
    </tr>
  );
}

export function RaceBrief() {
  return (
    <Section
      id="brief"
      no="01 / Race brief"
      title="What this weekend actually asks of you"
      lede="54°C asphalt destroys the right-front, while afternoon squalls rewrite the strategy in seconds."
      aside={<Pill tone="red" live>Target event</Pill>}
    >
      {/* Live Track Condition Telemetry Ribbon */}
      <div className="telemetry-bar reveal">
        <div className="telemetry-bar__item">
          <span className="dot dot--live" style={{ color: "var(--green)" }} />
          <span className="telemetry-bar__label">Track Status:</span>
          <span className="telemetry-bar__value" style={{ color: "var(--green)" }}>GREEN FLAG</span>
        </div>
        <div className="telemetry-bar__sep" />
        <div className="telemetry-bar__item">
          <span className="telemetry-bar__label">Asphalt Temp:</span>
          <span className="telemetry-bar__value hot">54.0°C</span>
        </div>
        <div className="telemetry-bar__sep" />
        <div className="telemetry-bar__item">
          <span className="telemetry-bar__label">Ambient Air:</span>
          <span className="telemetry-bar__value">33.2°C</span>
        </div>
        <div className="telemetry-bar__sep" />
        <div className="telemetry-bar__item">
          <span className="telemetry-bar__label">Humidity:</span>
          <span className="telemetry-bar__value">84% (Tropical)</span>
        </div>
        <div className="telemetry-bar__sep" />
        <div className="telemetry-bar__item">
          <span className="telemetry-bar__label">Squall Risk:</span>
          <span className="telemetry-bar__value hot">78% Probability</span>
        </div>
      </div>

      {/* Visual Command Deck */}
      <Reveal delay={40}>
        <div className="visual-deck">
          <div className="visual-deck__media">
            <img
              src="/assets/img/pitwall_command.jpg"
              alt="Ferrari Pit Wall Command Centre at Sepang"
              className="visual-deck__img"
              loading="lazy"
            />
            <div className="visual-deck__scrim" />
            <div className="visual-deck__content">
              <div className="visual-deck__badges">
                <Pill tone="red" live>Live Command Feed</Pill>
                <Pill tone="teal">Sepang Pit Wall Unit</Pill>
                <Pill tone="warn">Tyre Thermal Critical</Pill>
              </div>
              <h3 className="visual-deck__title">Mission Control · Strategy Decision Matrix</h3>
              <p className="visual-deck__lede">
                Real-time telemetry telemetry streams link chassis #55 & #16 to the trackside engineers. High lateral energy through Turns 5-8 combined with extreme equatorial track temperatures demand disciplined stint execution.
                Live telemetry links chassis #55 & #16. Extreme heat and lateral loads through Turns 5–8 demand disciplined tyre management.
              </p>
              <div className="visual-deck__stats">
                <div className="visual-stat">
                  <span className="visual-stat__label">Circuit Length</span>
                  <span className="visual-stat__value">{CIRCUIT.lengthKm} km</span>
                </div>
                <div className="visual-stat">
                  <span className="visual-stat__label">Total Turns</span>
                  <span className="visual-stat__value">{CIRCUIT.turns}</span>
                </div>
                <div className="visual-stat">
                  <span className="visual-stat__label">Elevation Range</span>
                  <span className="visual-stat__value">{CIRCUIT.elevationSpanM} m</span>
                </div>
                <div className="visual-stat">
                  <span className="visual-stat__label">Race Distance</span>
                  <span className="visual-stat__value">{CIRCUIT.raceDistanceKm} km</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </Reveal>

      <div className="grid cols-4" style={{ marginBottom: "var(--s6)" }}>
        <Reveal delay={0}>
          <Stat
            value={CIRCUIT.laps}
            label="Race laps"
            note={`${CIRCUIT.raceDistanceKm} km at ${CIRCUIT.lengthKm} km a lap`}
          />
        </Reveal>
        <Reveal delay={60}>
          <Stat
            value={CIRCUIT.turns}
            label="Turns"
            note={`${CIRCUIT.drsZones} DRS zones, ${CIRCUIT.direction.toLowerCase()}`}
          />
        </Reveal>
        <Reveal delay={120}>
          <Stat
            value={CIRCUIT.elevationSpanM}
            unit="m"
            decimals={1}
            label="Elevation span"
            note="SRTM 30 m along the lap"
            tone="warn"
          />
        </Reveal>
        <Reveal delay={180}>
          <Stat
            value={UNCERTAINTY.rainSeenPct}
            unit="%"
            label="Races that saw rain"
            note={`${UNCERTAINTY.runs} Monte Carlo races`}
            tone="hot"
          />
        </Reveal>
      </div>

      <div className="brief">
        <Reveal className="brief__sessions">
          <Panel
            title="Session plan"
            meta={EVENT.timezone}
            note={EVENT.disclaimer}
          >
            <div className="tbl-scroll">
              <table className="tbl">
                <thead>
                  <tr>
                    <th>Code</th>
                    <th>Session</th>
                    <th className="r">Date</th>
                    <th className="r">Local</th>
                    <th className="r">Your time</th>
                    <th className="r">Countdown</th>
                  </tr>
                </thead>
                <tbody>
                  {SESSIONS.map((s) => (
                    <SessionRow key={s.key} session={s} />
                  ))}
                </tbody>
              </table>
            </div>

            <ul className="brief__focus">
              {SESSIONS.map((s) => (
                <li key={s.key}>
                  <span className="t-overline hot">{s.short}</span>
                  <span className="t-small dim">{s.focus}</span>
                </li>
              ))}
            </ul>
          </Panel>
        </Reveal>

        <div className="brief__notes">
          {BRIEF.map((b, i) => (
            <Reveal key={b.heading} delay={i * 70}>
              <Panel title={`0${i + 1} · ${b.heading}`}>
                <p className="t-body dim">{b.body}</p>
              </Panel>
            </Reveal>
          ))}
        </div>
      </div>
    </Section>
  );
}

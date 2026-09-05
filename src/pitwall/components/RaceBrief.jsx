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
      lede="Sepang is two problems stacked on top of each other: 54 degree asphalt that eats the right-front, and a monsoon that arrives most afternoons. The plan on paper and the plan you race are rarely the same document."
      aside={<Pill tone="red" live>Target event</Pill>}
    >
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

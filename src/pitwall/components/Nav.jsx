import { useEffect, useState } from "react";

import { EVENT, SESSIONS } from "../data/schedule.js";
import { useActiveSection, useCountdown, useScrollProgress } from "../hooks.js";

const LINKS = [
  { id: "brief", label: "Brief" },
  { id: "circuit", label: "Circuit" },
  { id: "strategy", label: "Strategy" },
  { id: "tyres", label: "Tyres" },
  { id: "monsoon", label: "Monsoon" },
  { id: "film", label: "Film room" },
  { id: "academy", label: "Academy" },
  { id: "model", label: "The model" }
];

const IDS = LINKS.map((l) => l.id);
const RACE = SESSIONS.find((s) => s.isRace);

export function Nav() {
  const progress = useScrollProgress();
  const active = useActiveSection(IDS);
  const [condensed, setCondensed] = useState(false);
  const [open, setOpen] = useState(false);
  const t = useCountdown(RACE.startsAt);

  useEffect(() => {
    const onScroll = () => setCondensed(window.scrollY > 40);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <header className="nav" data-condensed={condensed}>
      <div className="nav__inner">
        <a className="nav__brand" href="#top">
          <span className="nav__mark" aria-hidden="true" />
          <span className="nav__brandtext">
            <strong>Sepang</strong> Pit Wall
          </span>
        </a>

        <span className="nav__session" aria-label="Time to the race">
          <span className="dot dot--live" style={{ color: "var(--red-bright)" }} />
          <span className="nav__sessiontext mono">
            {t.past ? "Race underway" : `${t.days}d ${String(t.hours).padStart(2, "0")}h ${String(t.minutes).padStart(2, "0")}m to lights out`}
          </span>
        </span>

        <nav className="nav__links" aria-label="Sections">
          {LINKS.map((l) => (
            <a
              key={l.id}
              href={`#${l.id}`}
              className="nav__link"
              aria-current={active === l.id ? "true" : undefined}
            >
              {l.label}
            </a>
          ))}
        </nav>

        <button
          className="nav__burger"
          type="button"
          aria-expanded={open}
          aria-label="Sections"
          onClick={() => setOpen((v) => !v)}
        >
          <span />
          <span />
        </button>
      </div>

      {open ? (
        <nav className="nav__sheet" aria-label="Sections">
          {LINKS.map((l) => (
            <a key={l.id} href={`#${l.id}`} onClick={() => setOpen(false)}>
              {l.label}
            </a>
          ))}
          <p className="t-caption dim-2">{EVENT.timezone}</p>
        </nav>
      ) : null}

      <div className="nav__progress" style={{ transform: `scaleX(${progress})` }} />
    </header>
  );
}

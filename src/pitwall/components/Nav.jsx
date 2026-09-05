import { useEffect, useRef, useState } from "react";
import { animate } from "motion";

import { EVENT, SESSIONS } from "../data/schedule.js";
import { useActiveSection, useCountdown, usePrefersReducedMotion, useScrollProgress } from "../hooks.js";

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

/**
 * Spring-animated mobile nav sheet.
 *
 * Slides down from the nav bar bottom edge and reverses out the same path.
 * Uses Motion's animate() imperatively so mid-flight interrupts (rapid burger
 * taps) read the current on-screen translateY and re-target from there —
 * no "wait for animation to finish before reversing" snap.
 *
 * Critically damped (bounce: 0) because nav-level elements should settle
 * immediately; bounce on a menu feels wrong.
 */
function NavSheet({ open, onClose }) {
  const [mounted, setMounted] = useState(open);
  const sheetRef = useRef(null);
  const animRef = useRef(null);
  const reduced = usePrefersReducedMotion();

  // Mount before animating in; stay mounted through close animation.
  useEffect(() => {
    if (open) setMounted(true);
  }, [open]);

  useEffect(() => {
    const el = sheetRef.current;
    if (!el || !mounted) return;

    // Kill any running animation so we start from the current on-screen value.
    animRef.current?.stop?.();

    if (reduced) {
      el.style.opacity = open ? "1" : "0";
      el.style.transform = open ? "translateY(0)" : "translateY(-100%)";
      if (!open) setMounted(false);
      return;
    }

    if (open) {
      // Entering: slide down from above, fade in simultaneously.
      animRef.current = animate(
        el,
        { opacity: [0, 1], transform: ["translateY(-100%)", "translateY(0%)"] },
        { type: "spring", bounce: 0, duration: 0.32 }
      );
    } else {
      // Leaving: retract back up the same path it entered, then unmount.
      animRef.current = animate(
        el,
        { opacity: [1, 0], transform: ["translateY(0%)", "translateY(-100%)"] },
        { type: "spring", bounce: 0, duration: 0.28 }
      );
      animRef.current.finished.then(() => setMounted(false)).catch(() => {});
    }

    return () => animRef.current?.stop?.();
  }, [open, mounted, reduced]);

  if (!mounted) return null;

  return (
    <nav
      ref={sheetRef}
      className="nav__sheet"
      aria-label="Sections"
      style={{ opacity: 0, transform: "translateY(-100%)" }}
    >
      {LINKS.map((l) => (
        <a key={l.id} href={`#${l.id}`} onClick={onClose}>
          {l.label}
        </a>
      ))}
      <p className="t-caption dim-2">{EVENT.timezone}</p>
    </nav>
  );
}

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
          <img
            src="/assets/img/sepang_logo.jpg"
            alt="Sepang Pit Wall Logo"
            className="nav__logo"
          />
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
      <NavSheet open={open} onClose={() => setOpen(false)} />

      <div className="nav__progress" style={{ transform: `scaleX(${progress})` }} />
    </header>
  );
}

/**
 * The hero.
 *
 * The onboard clip is the whole first screen — a Remotion composition, not a
 * plain <video>, so the grade, the grain and the live telemetry HUD are all
 * composited on the same timeline as the picture.
 *
 * Motion (motion.dev) does the type key-in and the scroll parallax. It is the
 * one animation library in the prepared set that works without a wrapper here.
 */

import { useEffect, useRef } from "react";
import { animate, scroll, stagger } from "motion";

import { ClipStage } from "../cinema/ClipStage.jsx";
import { CIRCUIT, LAP_PHYSICS } from "../data/circuit.js";
import { CLIPS } from "../data/clips.js";
import { EVENT, SESSIONS } from "../data/schedule.js";
import { UNCERTAINTY } from "../data/strategy.js";
import { useCountdown, usePrefersReducedMotion } from "../hooks.js";

const RACE = SESSIONS.find((s) => s.isRace);
const TITLE = "Sepang Pit Wall";

function SplitTitle({ text }) {
  const ref = useRef(null);
  const reduced = usePrefersReducedMotion();

  useEffect(() => {
    const host = ref.current;
    if (!host) return;
    const chars = host.querySelectorAll("[data-ch]");
    if (reduced) {
      chars.forEach((c) => {
        c.style.opacity = "1";
        c.style.transform = "none";
      });
      return;
    }
    const controls = animate(
      chars,
      {
        opacity: [0, 1],
        transform: ["translateY(8px)", "translateY(0px)"],
        textShadow: [
          "-3px 0 0 rgba(255,0,0,.75), 3px 0 0 rgba(0,180,255,.75)",
          "0px 0 0 rgba(255,0,0,0), 0px 0 0 rgba(0,180,255,0)"
        ]
      },
      {
        delay: stagger(0.024, { startDelay: 0.15 }),
        duration: 0.62,
        ease: [0.16, 1, 0.3, 1]
      }
    );
    return () => controls.stop?.();
  }, [reduced]);

  return (
    <h1 className="hero__title t-display" ref={ref} aria-label={text}>
      {text.split(" ").map((word, wi) => (
        <span className="hero__word" key={`${word}-${wi}`}>
          {word.split("").map((ch, ci) => (
            <span data-ch key={`${ch}-${ci}`} aria-hidden="true">
              {ch}
            </span>
          ))}
        </span>
      ))}
    </h1>
  );
}

export function Hero() {
  const t = useCountdown(RACE.startsAt);
  const stageRef = useRef(null);
  const reduced = usePrefersReducedMotion();

  useEffect(() => {
    if (reduced) return;
    const el = stageRef.current;
    if (!el) return;
    // scrubbed directly by scroll position, so it tracks the wheel exactly
    const stop = scroll(
      animate(
        el,
        { transform: ["scale(1) translateY(0px)", "scale(1.08) translateY(-52px)"] },
        { ease: "linear" }
      ),
      { target: el.closest(".hero"), offset: ["start start", "end start"] }
    );
    return () => stop?.();
  }, [reduced]);

  const pad = (n) => String(n).padStart(2, "0");

  return (
    <section className="hero" id="top">
      <div className="hero__stage" ref={stageRef}>
        <ClipStage
          clipKey="onboard"
          variant="hero"
          letterbox={false}
          showTitles={false}
          transport={false}
          fill
          autoPlay
          loop
          soundControl
          soundLabel="Music"
        />
      </div>

      <div className="hero__scrim" aria-hidden="true" />

      <div className="hero__content wrap">
        <p className="hero__kicker t-overline">
          <span className="hero__flag" aria-hidden="true" />
          {EVENT.name} · {CIRCUIT.lengthKm} km · {CIRCUIT.turns} turns
        </p>

        <SplitTitle text={TITLE} />

        <p className="hero__lede">
          Strategy, learning and simulation for the {EVENT.name} at{" "}
          {CIRCUIT.short} — built on a circuit reconstructed from survey data, a
          lap model calibrated to a real pole time, and a monsoon that decides{" "}
          {UNCERTAINTY.rainSeenPct}% of the races it is asked to run.
        </p>

        <div className="hero__cta">
          <a className="btn" href="#strategy">
            Run the strategy
          </a>
          <a className="btn btn--ghost" href="#film">
            Open the film room
          </a>
        </div>

        <dl className="hero__rail">
          <div className="hero__railitem">
            <dt className="t-overline">Lights out in</dt>
            <dd className="mono">
              {t.past
                ? "Underway"
                : `${t.days}d ${pad(t.hours)}:${pad(t.minutes)}:${pad(t.seconds)}`}
            </dd>
          </div>
          <div className="hero__railitem">
            <dt className="t-overline">Reference pole</dt>
            <dd className="mono">1:30.076</dd>
          </div>
          <div className="hero__railitem">
            <dt className="t-overline">Top speed</dt>
            <dd className="mono">{LAP_PHYSICS.topSpeedKph} kph</dd>
          </div>
          <div className="hero__railitem">
            <dt className="t-overline">Rain likelihood</dt>
            <dd className="mono">{UNCERTAINTY.rainSeenPct}%</dd>
          </div>
        </dl>
      </div>

      <div className="hero__meta">
        <span className="t-caption dim-2 mono">
          Hero plate · {CLIPS.onboard.src.replace("/", "")} ·{" "}
          {CLIPS.onboard.durationInFrames} frames @ 24 fps · graded live in Remotion
        </span>
        <a className="hero__scroll t-overline" href="#brief">
          Scroll
          <span aria-hidden="true" />
        </a>
      </div>
    </section>
  );
}

import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { animate } from "motion";

import { GLOSSARY, LEARNING_TRACKS } from "../data/schedule.js";
import { usePrefersReducedMotion } from "../hooks.js";
import { Pill, Reveal, Section } from "./ui.jsx";

/**
 * Spring-animated accordion panel.
 *
 * Height is measured from the real DOM node (useLayoutEffect so it runs before
 * paint) and driven to 0 or its natural height with a critically-damped spring.
 * Clicking again mid-flight stops the current animation and reverses from the
 * current on-screen height — no "wait to finish then close" snap.
 */
function AccordionBody({ open, id, children }) {
  const innerRef = useRef(null);
  const wrapRef = useRef(null);
  const animRef = useRef(null);
  const naturalH = useRef(0);
  const reduced = usePrefersReducedMotion();

  // Measure the natural height before every paint so resize is handled.
  useLayoutEffect(() => {
    const inner = innerRef.current;
    if (!inner) return;
    const prev = inner.style.height;
    inner.style.height = "auto";
    naturalH.current = inner.scrollHeight;
    inner.style.height = prev;
  });

  useEffect(() => {
    const el = wrapRef.current;
    if (!el) return;

    animRef.current?.stop?.();

    const target = open ? naturalH.current : 0;

    if (reduced) {
      el.style.height = open ? "auto" : "0px";
      el.style.overflow = open ? "visible" : "hidden";
      return;
    }

    animRef.current = animate(
      el,
      { height: [`${el.offsetHeight}px`, `${target}px`] },
      { type: "spring", bounce: 0, duration: 0.38 }
    );

    // Once fully open, release to auto so the panel reflows on resize.
    animRef.current.finished
      .then(() => {
        if (open) el.style.height = "auto";
      })
      .catch(() => {});

    return () => animRef.current?.stop?.();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  return (
    <div
      ref={wrapRef}
      id={id}
      style={{ overflow: "hidden", height: open ? "auto" : 0 }}
      aria-hidden={!open}
      inert={!open}
    >
      <div ref={innerRef} className="academy__steps">
        {children}
      </div>
    </div>
  );
}

function Track({ track, index, open, onToggle }) {
  return (
    <article className="academy__track" data-open={open}>
      <button
        className="academy__trigger"
        type="button"
        aria-expanded={open}
        aria-controls={`track-${track.key}`}
        onClick={onToggle}
      >
        <span className="academy__index mono">{String(index + 1).padStart(2, "0")}</span>
        <span className="academy__trackcopy">
          <strong>{track.name}</strong>
          <span>{track.blurb}</span>
        </span>
        <span className="academy__minutes mono">{track.minutes} min</span>
        <span className="academy__chevron" aria-hidden="true" />
      </button>
      <AccordionBody open={open} id={`track-${track.key}`}>
        <ol>
          {track.steps.map((step) => (
            <li key={step}>{step}</li>
          ))}
        </ol>
      </AccordionBody>
    </article>
  );
}

export function Academy() {
  const [openTrack, setOpenTrack] = useState("rookie");
  return (
    <Section
      id="academy"
      no="08 / Academy"
      title="Learn the call before you make it"
      lede="Interactive race strategy guides covering tyre degradation, undercut math, and monsoon decision trees."
      aside={<Pill tone="teal">3 guided tracks</Pill>}
    >
      <div className="academy__tracks">
        {LEARNING_TRACKS.map((track, index) => (
          <Reveal key={track.key} delay={index * 70}>
            <Track
              track={track}
              index={index}
              open={openTrack === track.key}
              onToggle={() => setOpenTrack((current) => (current === track.key ? "" : track.key))}
            />
          </Reveal>
        ))}
      </div>

      <div className="academy__glossary">
        <div>
          <p className="t-overline hot">Field notes</p>
          <h3 className="t-h2">The vocabulary of the pit wall</h3>
        </div>
        <dl>
          {GLOSSARY.map(({ term, def }) => (
            <div key={term}>
              <dt>{term}</dt>
              <dd>{def}</dd>
            </div>
          ))}
        </dl>
      </div>
    </Section>
  );
}

/**
 * UI primitives. Presentation only — no data, no fetching.
 */

import { COMPOUNDS } from "../data/tyres.js";
import { useCountUp, useReveal, useSpotlight } from "../hooks.js";

export function Section({ id, no, title, lede, aside, children, className = "" }) {
  const ref = useReveal();
  return (
    <section id={id} className={`section ${className}`}>
      <div className="wrap">
        <header className="sec-head reveal" ref={ref}>
          <div>
            {no ? <div className="sec-head__no">{no}</div> : null}
            <h2 className="t-h1">{title}</h2>
            {lede ? <p className="sec-head__lede t-body">{lede}</p> : null}
          </div>
          {aside ? <div className="sec-head__aside">{aside}</div> : null}
        </header>
        {children}
      </div>
    </section>
  );
}

export function Reveal({ children, delay = 0, as: Tag = "div", className = "", ...rest }) {
  const ref = useReveal();
  return (
    <Tag
      ref={ref}
      className={`reveal ${className}`}
      style={{ "--delay": `${delay}ms` }}
      {...rest}
    >
      {children}
    </Tag>
  );
}

export function Panel({ title, meta, children, note, lit = true, className = "", bodyClass = "" }) {
  const { ref, handlers } = useSpotlight();
  return (
    <div
      ref={lit ? ref : undefined}
      {...(lit ? handlers : {})}
      className={`panel ${lit ? "panel--lit" : ""} ${className}`}
    >
      {title ? (
        <div className="panel__head">
          <span className="t-overline">{title}</span>
          {meta ? <span className="t-caption dim-2">{meta}</span> : null}
        </div>
      ) : null}
      <div className={`panel__body ${bodyClass}`}>
        {children}
        {note ? <p className="panel__note">{note}</p> : null}
      </div>
    </div>
  );
}

export function Stat({ value, unit, label, note, tone, decimals, animate = true }) {
  const numeric = typeof value === "number";
  const [ref, shown] = useCountUp(numeric && animate ? value : 0, {
    decimals: decimals ?? 0
  });
  const toneClass = tone ? `stat--${tone}` : "";
  return (
    <div className={`stat ${toneClass}`} ref={numeric && animate ? ref : undefined}>
      <div className="stat__v">
        {numeric && animate ? shown : value}
        {unit ? <span className="stat__u">{unit}</span> : null}
      </div>
      <div className="stat__l t-overline">{label}</div>
      {note ? <div className="stat__n">{note}</div> : null}
    </div>
  );
}

export function Pill({ tone, children, live = false }) {
  return (
    <span className={`pill ${tone ? `pill--${tone}` : ""}`}>
      {live ? <span className="dot dot--live" /> : null}
      {children}
    </span>
  );
}

/** Compound always renders as a coloured disc AND a letter, never colour alone. */
export function Tyre({ compound, showName = true, showCode = false }) {
  const c = COMPOUNDS[compound];
  if (!c) return null;
  return (
    <span className="tyre" style={{ color: c.hex }}>
      <span className="tyre__disc" aria-hidden="true">
        {c.letter}
      </span>
      {showName ? (
        <span style={{ color: "var(--ink)" }}>
          {c.name}
          {showCode ? <span className="dim-2"> · {c.code}</span> : null}
        </span>
      ) : null}
      <span className="sr-only">{c.name}</span>
    </span>
  );
}

export function Field({ label, value, min, max, step = 1, onChange, hint, disabled }) {
  const fill = max > min ? ((value - min) / (max - min)) * 100 : 0;
  return (
    <label className="field">
      <span className="field__row">
        <span className="field__l t-overline">{label}</span>
        <span className="field__v">{hint ?? value}</span>
      </span>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        disabled={disabled}
        onChange={(e) => onChange(Number(e.target.value))}
        style={{ "--fill": `${fill}%` }}
      />
    </label>
  );
}

export function Segmented({ options, value, onChange, label }) {
  return (
    <div className="seg" role="group" aria-label={label}>
      {options.map((o) => (
        <button
          key={o.value}
          type="button"
          className="seg__b"
          aria-pressed={value === o.value}
          onClick={() => onChange(o.value)}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

export function GapNote({ weight, title, children }) {
  return (
    <div className="gapnote">
      <b>
        {weight ? `${weight} gap` : "Remaining gap"}
        {title ? ` — ${title}` : ""}:
      </b>{" "}
      {children}
    </div>
  );
}

export function Kerb() {
  return <div className="kerb" aria-hidden="true" />;
}

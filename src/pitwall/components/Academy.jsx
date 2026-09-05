import { useState } from "react";

import { GLOSSARY, LEARNING_TRACKS } from "../data/schedule.js";
import { Pill, Reveal, Section } from "./ui.jsx";

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
      <div id={`track-${track.key}`} className="academy__steps" hidden={!open}>
        <ol>
          {track.steps.map((step) => (
            <li key={step}>{step}</li>
          ))}
        </ol>
      </div>
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
      lede="Start with the mechanics of a race, then move through a strategist's decision rules to the assumptions behind the model. Every lesson uses the numbers on this page."
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

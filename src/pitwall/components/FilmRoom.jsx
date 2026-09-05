import { CLIPS, CLIP_ORDER, clipStats } from "../data/clips.js";
import { ClipStage } from "../cinema/ClipStage.jsx";
import { Pill, Reveal, Section } from "./ui.jsx";

function ClipMeta({ clip }) {
  const stats = clipStats(clip.edit);
  return (
    <div className="film__meta">
      <span>{clip.runtime}</span>
      <span>{stats.cuts} cuts</span>
      <span>{Math.round(stats.maxKph)} kph max</span>
      <span>{clip.audio}</span>
    </div>
  );
}

function FilmCard({ clipKey, featured = false }) {
  const clip = CLIPS[clipKey];
  return (
    <article className={`film__card ${featured ? "film__card--featured" : ""}`}>
      <div className="film__copy">
        <div>
          <p className="t-overline hot">{clip.kicker}</p>
          <h3 className="t-h3">{clip.title}</h3>
        </div>
        <p className="t-small dim">{clip.blurb}</p>
        <ClipMeta clip={clip} />
      </div>
      <ClipStage
        clipKey={clipKey}
        variant={featured ? "feature" : "compact"}
        autoPlay={featured}
        showTitles={!featured}
      />
    </article>
  );
}

export function FilmRoom() {
  return (
    <Section
      id="film"
      no="06 / Film room"
      title="The simulation, played back"
      lede="These are Blender plates driven by the same car-position and weather traces used in the model. Speed and storm state are measured from the render trace; the remaining instruments are clearly marked as derived."
      aside={<Pill tone="red">24-frame telemetry</Pill>}
    >
      <Reveal>
        <FilmCard clipKey={CLIP_ORDER[2]} featured />
      </Reveal>
      <div className="film__grid">
        {CLIP_ORDER.slice(0, 2).map((clipKey, index) => (
          <Reveal key={clipKey} delay={(index + 1) * 90}>
            <FilmCard clipKey={clipKey} />
          </Reveal>
        ))}
      </div>
      <p className="film__note">
        Each stage runs one source video only. Bloom, grade, rain, grain and HUD layers
        are composited above it so the browser never has to decode duplicate plates.
      </p>
    </Section>
  );
}

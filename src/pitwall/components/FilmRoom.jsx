import { useState, useEffect } from "react";
import { CLIPS, CLIP_ORDER, clipStats } from "../data/clips.js";
import { ClipStage } from "../cinema/ClipStage.jsx";
import { Pill, Reveal, Section } from "./ui.jsx";

const BLENDER_SHOTS = [
  {
    id: "aerial",
    file: "/assets/img/sepang_shots/aerial.png",
    tag: "AERIAL SURVEY · Z: 850m",
    title: "Reconstructed Circuit Loop",
    desc: "1,386 registered GPS survey points spanning the 5.543 km loop and twin straights."
  },
  {
    id: "cam_carstudio",
    file: "/assets/img/sepang_shots/cam_carstudio.png",
    tag: "CHASSIS SPEC · 50mm PRIME",
    title: "2026 Ferrari SF-26 on Track",
    desc: "3400 mm wheelbase chassis with medium compound tyres and active aero simulation."
  },
  {
    id: "dry_chase",
    file: "/assets/img/sepang_shots/dry_chase.png",
    tag: "CHASE CAM · ACT 1 DRY",
    title: "Main Straight Chase Camera",
    desc: "Full-speed chase cam tracking down the main straight at 320+ km/h."
  },
  {
    id: "pit_overview",
    file: "/assets/img/sepang_shots/pit_overview.png",
    tag: "GRANDSTAND RIG · 35mm",
    title: "Twin Grandstand & Pit Complex",
    desc: "Twin grandstands, pit building complex, start gantry, and DRS Zone 1."
  },
  {
    id: "wet_chase_rain",
    file: "/assets/img/sepang_shots/wet_chase_rain.png",
    tag: "MONSOON · 85mm TEE",
    title: "Monsoon Spray & Wet Reflections",
    desc: "Torrential downpour with heavy tyre spray, specular reflections, and storm sky."
  },
  {
    id: "wet_onboard",
    file: "/assets/img/sepang_shots/wet_onboard.png",
    tag: "COCKPIT ONBOARD · HALO",
    title: "Heavy Wet Cockpit Point of View",
    desc: "Driver's eye cockpit POV behind the halo with high-velocity visor water streaks."
  }
];

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

function FilmCard({ clipKey, featured = false, lightweight = false }) {
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
        autoPlay={featured && !lightweight}
        showTitles={!featured}
        lightweight={lightweight}
      />
    </article>
  );
}

export function FilmRoom() {
  const [activeShot, setActiveShot] = useState(null);
  const [isMobile, setIsMobile] = useState(() =>
    typeof window !== "undefined" && window.matchMedia("(max-width: 768px)").matches
  );

  useEffect(() => {
    const mql = window.matchMedia("(max-width: 768px)");
    const onChange = (e) => setIsMobile(e.matches);
    mql.addEventListener("change", onChange);
    return () => mql.removeEventListener("change", onChange);
  }, []);

  return (
    <Section
      id="film"
      no="06 / Film room"
      title="The simulation, played back"
      lede="Blender 3D camera plates driven directly by telemetry and weather simulation traces."
      aside={<Pill tone="red">24-frame telemetry</Pill>}
    >
      <Reveal>
        <FilmCard clipKey={CLIP_ORDER[2]} featured lightweight={isMobile} />
      </Reveal>
      <div className="film__grid">
        {CLIP_ORDER.slice(0, 2).map((clipKey, index) => (
          <Reveal key={clipKey} delay={(index + 1) * 90}>
            <FilmCard clipKey={clipKey} lightweight={isMobile} />
          </Reveal>
        ))}
      </div>
      <p className="film__note">
        Each stage runs one source video only. Bloom, grade, rain, grain and HUD layers
        are composited above it so the browser never has to decode duplicate plates.
      </p>

      {/* 3D Blender Render Gallery */}
      <div className="gallery-section">
        <header className="sec-head" style={{ marginBottom: "var(--s5)" }}>
          <div>
            <div className="sec-head__no">Blender Plates</div>
            <h3 className="t-h2">High-Resolution Render Showcase</h3>
            <p className="sec-head__lede t-small dim">
              Keyframes from the Blender Cycles rendering pipeline. Click any plate to inspect the full-resolution camera perspective and lighting physics.
            </p>
          </div>
          <div className="sec-head__aside">
            <Pill tone="teal">Cycles 4K Photorealism</Pill>
          </div>
        </header>

        <div className="gallery-grid">
          {BLENDER_SHOTS.map((shot, idx) => (
            <Reveal key={shot.id} delay={idx * 60}>
              <div
                className="gallery-card"
                onClick={() => setActiveShot(shot)}
                role="button"
                tabIndex={0}
                onKeyDown={(e) => e.key === "Enter" && setActiveShot(shot)}
              >
                <div className="gallery-card__thumb">
                  <img
                    src={shot.file}
                    alt={shot.title}
                    className="gallery-card__img"
                    loading="lazy"
                  />
                  <span className="gallery-card__tag">{shot.tag}</span>
                </div>
                <div className="gallery-card__body">
                  <h4 className="gallery-card__title">{shot.title}</h4>
                  <p className="gallery-card__desc">{shot.desc}</p>
                </div>
              </div>
            </Reveal>
          ))}
        </div>
      </div>

      {/* Lightbox Modal */}
      {activeShot ? (
        <div
          className="modal-backdrop"
          onClick={() => setActiveShot(null)}
          role="dialog"
          aria-modal="true"
        >
          <div
            className="modal-content"
            onClick={(e) => e.stopPropagation()}
          >
            <button
              className="modal-close"
              type="button"
              onClick={() => setActiveShot(null)}
              aria-label="Close viewer"
            >
              ×
            </button>
            <img
              src={activeShot.file}
              alt={activeShot.title}
              className="modal-img"
            />
            <div className="modal-footer">
              <div>
                <span className="t-overline hot">{activeShot.tag}</span>
                <h4 className="t-h3" style={{ margin: "3px 0 0" }}>{activeShot.title}</h4>
                <p className="t-small dim" style={{ margin: "4px 0 0" }}>{activeShot.desc}</p>
              </div>
              <Pill tone="red">Cycles Engine</Pill>
            </div>
          </div>
        </div>
      ) : null}
    </Section>
  );
}

/**
 * The Remotion composition that turns a raw Blender render into a graded,
 * instrumented cinema surface.
 *
 * Design constraints, both deliberate:
 *
 *  1. Exactly one <video> element per composition. Two copies of the same file
 *     drift out of sync and double the decode cost, so bloom is done with
 *     backdrop-filter (which samples the plate already on screen) rather than a
 *     second decoder.
 *  2. Every effect is a pure function of useCurrentFrame(). The browser player
 *     and a headless Remotion render therefore produce the same pixels, and the
 *     look never depends on wall-clock timing.
 *
 * The intensity that drives contrast, chromatic aberration and the bloom lift is
 * not arbitrary: it comes from the real per-frame speed trace and the cut
 * boundaries of the actual edit.
 */

import { useMemo } from "react";
import { AbsoluteFill, Video, useCurrentFrame, useVideoConfig } from "remotion";

import { CLIPS, sampleAtFrame, speedTrace, TELEMETRY } from "../data/clips.js";
import {
  brakeIntensity,
  chromaBucket,
  clamp,
  cutImpact,
  filterChain,
  lookFor,
  speedIntensity
} from "./grade.js";
import {
  BloomLayer,
  ChromaDefs,
  CutFlashLayer,
  GrainLayer,
  LetterboxLayer,
  RainSheenLayer,
  SpeedStreakLayer,
  SplitToneLayer,
  VignetteLayer
} from "./CinemaLayers.jsx";
import { Hud, TitleCard } from "./Hud.jsx";

/** Title cards per clip, in frames at 24 fps. */
export const TITLE_CARDS = {
  onboard: [],
  pov: [
    {
      from: 6,
      duration: 62,
      kicker: "Driver's eye",
      title: "Riding it out",
      subtitle:
        "Chase and onboard alternating through one chronology, as the weather turns."
    },
    {
      from: 300,
      duration: 46,
      kicker: "Act 3",
      title: "Monsoon",
      subtitle: "Past the aquaplaning threshold, with a red flag in play."
    }
  ],
  highlight: [
    {
      from: 6,
      duration: 66,
      kicker: "Sepang · 5.543 km · 15 turns",
      title: "Three acts",
      subtitle:
        "Twenty-four shots rendered from the simulation's own car positions."
    },
    {
      from: 460,
      duration: 50,
      kicker: "Act 2",
      title: "The sky breaks",
      subtitle: "Sector 2 goes wet first. It always does."
    },
    {
      from: 916,
      duration: 50,
      kicker: "Act 3",
      title: "Monsoon",
      subtitle: "5.2 mm and race control stops the race."
    }
  ]
};

export function SepangComposition({
  clipKey = "onboard",
  variant = "full",
  showHud = true,
  showTitles = true,
  letterbox = true,
  uid = "cine"
}) {
  const frame = useCurrentFrame();
  const { fps, width, height, durationInFrames } = useVideoConfig();
  const clip = CLIPS[clipKey];

  const trace = useMemo(() => speedTrace(clip.edit), [clip.edit]);
  const cuts = TELEMETRY.edits[clip.edit].cuts;

  const sample = sampleAtFrame(clip.edit, frame);
  const look = lookFor(sample.condition);

  /* --- envelopes, all derived from the real edit and telemetry ---------- */
  const impact = cutImpact(sample.localFrame, 7);
  const brake = brakeIntensity(sample.accelMs2);
  const speed = speedIntensity(sample.speedKph);

  const chromaIdx = chromaBucket(impact * 0.95 + brake * 0.75);
  const chromaId = chromaIdx > 0 ? `${uid}-chroma-${chromaIdx}` : null;

  const extraContrast = impact * 0.18 + brake * 0.1;
  const bloom = clamp(look.bloom + speed * 0.18 + impact * 0.14);
  const grain = look.grain + impact * 0.05;

  /* --- camera: a slow push across every cut, plus a kick on the cut ----- */
  const cutLen = Math.max(1, sample.cut.frames);
  const through = clamp(sample.localFrame / cutLen);
  const push = 1.035 + through * 0.028 + impact * 0.02;
  const drift = -through * 9 - impact * 5;

  /* --- opening entry so the HUD keys in rather than popping ------------- */
  const entry = clamp(frame / (fps * 0.7));

  const cards = showTitles ? (TITLE_CARDS[clipKey] ?? []) : [];

  return (
    <AbsoluteFill style={{ background: "#03060a", overflow: "hidden" }}>
      <ChromaDefs uid={uid} />

      {/* the plate */}
      <AbsoluteFill
        style={{
          transform: `scale(${push.toFixed(4)}) translateY(${drift.toFixed(2)}px)`,
          transformOrigin: "50% 52%",
          willChange: "transform"
        }}
      >
        <Video
          src={clip.src}
          startFrom={0}
          muted={false}
          style={{
            width: "100%",
            height: "100%",
            objectFit: "cover",
            filter: filterChain(look, chromaId, extraContrast)
          }}
        />
      </AbsoluteFill>

      <BloomLayer amount={bloom} />
      <SplitToneLayer look={look} />
      <RainSheenLayer storm={sample.storm} frame={frame} />
      <SpeedStreakLayer intensity={speed * 0.85} frame={frame} />
      <GrainLayer amount={grain} frame={frame} />
      <VignetteLayer amount={look.vignette} />

      {/* a scrim along the bottom so the HUD always has something to sit on */}
      <AbsoluteFill
        style={{
          pointerEvents: "none",
          background:
            "linear-gradient(to top, rgba(3,6,10,0.86) 0%, rgba(3,6,10,0.42) 16%, transparent 34%)"
        }}
      />

      <CutFlashLayer amount={impact * (brake > 0.4 ? 1 : 0.55)} />

      {letterbox ? (
        <LetterboxLayer ratio={2.39} width={width} height={height} />
      ) : null}

      {showHud ? (
        <Hud
          sample={sample}
          frame={frame}
          totalFrames={durationInFrames}
          fps={fps}
          trace={trace}
          cuts={cuts}
          entry={entry}
          variant={variant}
        />
      ) : null}

      {cards.map((c) => (
        <TitleCard key={c.from} {...c} fps={fps} />
      ))}
    </AbsoluteFill>
  );
}

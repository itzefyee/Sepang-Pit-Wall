/**
 * The layer stack that sits over the plate, bottom to top:
 *
 *   1. bloom / halation   — a blurred, screen-blended sample of the video itself
 *   2. shadow + highlight split tint
 *   3. speed streaks       — radial, keyed to the real speed trace
 *   4. grain plate
 *   5. vignette
 *   6. letterbox to 2.39:1
 *
 * The bloom uses backdrop-filter so it samples the actual video underneath. That
 * keeps the whole composition down to a single <video> element — two copies of
 * the same file drift out of sync and double the decode cost for no visual gain.
 */

import { AbsoluteFill } from "remotion";
import { CHROMA_STEPS, grainOffset, grainTexture } from "./grade.js";

/**
 * The preset chromatic-aberration filters. Rendered once per composition,
 * selected by index at runtime. `uid` keeps ids unique when several
 * compositions are mounted on the same page.
 */
export function ChromaDefs({ uid }) {
  return (
    <svg
      aria-hidden="true"
      width="0"
      height="0"
      style={{ position: "absolute", width: 0, height: 0 }}
    >
      <defs>
        {CHROMA_STEPS.map((px, i) => (
          <filter
            key={i}
            id={`${uid}-chroma-${i}`}
            x="-2%"
            y="-2%"
            width="104%"
            height="104%"
            colorInterpolationFilters="sRGB"
          >
            {/* red channel, pushed left */}
            <feOffset in="SourceGraphic" dx={-px} dy={0} result="rOff" />
            <feColorMatrix
              in="rOff"
              type="matrix"
              values="1 0 0 0 0  0 0 0 0 0  0 0 0 0 0  0 0 0 1 0"
              result="r"
            />
            {/* green channel, centred */}
            <feColorMatrix
              in="SourceGraphic"
              type="matrix"
              values="0 0 0 0 0  0 1 0 0 0  0 0 0 0 0  0 0 0 1 0"
              result="g"
            />
            {/* blue channel, pushed right */}
            <feOffset in="SourceGraphic" dx={px} dy={0} result="bOff" />
            <feColorMatrix
              in="bOff"
              type="matrix"
              values="0 0 0 0 0  0 0 0 0 0  0 0 1 0 0  0 0 0 1 0"
              result="b"
            />
            <feBlend in="r" in2="g" mode="screen" result="rg" />
            <feBlend in="rg" in2="b" mode="screen" />
          </filter>
        ))}
      </defs>
    </svg>
  );
}

/** Halation: sample the plate, blur it, screen it back on top. */
export function BloomLayer({ amount }) {
  if (amount <= 0.001) return null;
  return (
    <AbsoluteFill
      className="stage__layer-bloom"
      style={{
        backdropFilter: `blur(26px) brightness(1.5) saturate(1.3)`,
        WebkitBackdropFilter: `blur(26px) brightness(1.5) saturate(1.3)`,
        mixBlendMode: "screen",
        opacity: amount,
        pointerEvents: "none"
      }}
    />
  );
}

/** Cool the shadows, warm the highlights. */
export function SplitToneLayer({ look }) {
  return (
    <>
      <AbsoluteFill
        style={{
          background: look.shadowTint,
          mixBlendMode: "color-burn",
          pointerEvents: "none"
        }}
      />
      <AbsoluteFill
        style={{
          background: `radial-gradient(120% 80% at 50% 34%, ${look.highlightTint}, transparent 68%)`,
          mixBlendMode: "screen",
          pointerEvents: "none"
        }}
      />
    </>
  );
}

/** Radial speed streaks, keyed to the real speed trace. */
export function SpeedStreakLayer({ intensity, frame }) {
  if (intensity <= 0.02) return null;
  const spin = (frame * 0.9) % 360;
  return (
    <AbsoluteFill
      style={{
        pointerEvents: "none",
        mixBlendMode: "screen",
        opacity: intensity * 0.5,
        background: `repeating-conic-gradient(from ${spin}deg at 50% 52%, rgba(233,239,245,0.16) 0deg 0.35deg, transparent 0.35deg 3.6deg)`,
        maskImage:
          "radial-gradient(circle at 50% 52%, transparent 26%, #000 78%)",
        WebkitMaskImage:
          "radial-gradient(circle at 50% 52%, transparent 26%, #000 78%)",
        transform: `scale(${1 + intensity * 0.18})`
      }}
    />
  );
}

export function GrainLayer({ amount, frame }) {
  const texture = grainTexture();
  if (!texture || amount <= 0.001) return null;
  return (
    <AbsoluteFill
      style={{
        pointerEvents: "none",
        mixBlendMode: "overlay",
        opacity: amount,
        backgroundImage: `url(${texture})`,
        backgroundSize: "128px 128px",
        backgroundPosition: grainOffset(frame)
      }}
    />
  );
}

export function VignetteLayer({ amount }) {
  return (
    <AbsoluteFill
      style={{
        pointerEvents: "none",
        background: `radial-gradient(122% 96% at 50% 48%, transparent 34%, rgba(3,6,10,${(
          amount * 0.55
        ).toFixed(3)}) 74%, rgba(2,4,7,${(amount * 0.94).toFixed(3)}) 100%)`
      }}
    />
  );
}

/**
 * Letterbox to 2.39:1 over a 16:9 plate. Bars are drawn rather than the frame
 * cropped, so the plate keeps its full resolution behind them.
 */
export function LetterboxLayer({ ratio = 2.39, width = 1920, height = 1080 }) {
  const targetHeight = width / ratio;
  const bar = Math.max(0, (height - targetHeight) / 2);
  if (bar < 1) return null;
  return (
    <>
      <div
        style={{
          position: "absolute",
          left: 0,
          right: 0,
          top: 0,
          height: bar,
          background: "#000",
          pointerEvents: "none",
          zIndex: 40
        }}
      />
      <div
        style={{
          position: "absolute",
          left: 0,
          right: 0,
          bottom: 0,
          height: bar,
          background: "#000",
          pointerEvents: "none",
          zIndex: 40
        }}
      />
    </>
  );
}

/** A single white frame on the hardest cuts. */
export function CutFlashLayer({ amount }) {
  if (amount <= 0.01) return null;
  return (
    <AbsoluteFill
      style={{
        pointerEvents: "none",
        background: "#dfe8f2",
        mixBlendMode: "screen",
        opacity: amount * 0.34
      }}
    />
  );
}

/** Rain sheen: faint diagonal streaks that only appear once it is wet. */
export function RainSheenLayer({ storm, frame }) {
  if (storm <= 0.05) return null;
  const drift = (frame * 6) % 220;
  return (
    <AbsoluteFill
      style={{
        pointerEvents: "none",
        mixBlendMode: "screen",
        opacity: 0.1 + storm * 0.16,
        backgroundImage:
          "repeating-linear-gradient(101deg, rgba(233,239,245,0.5) 0px, rgba(233,239,245,0) 1.4px, rgba(233,239,245,0) 9px)",
        backgroundSize: "auto 220px",
        backgroundPosition: `0px ${drift}px`
      }}
    />
  );
}

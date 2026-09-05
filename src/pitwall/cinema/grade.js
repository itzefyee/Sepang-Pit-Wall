/**
 * The colour grade.
 *
 * The source plates are bright, low-contrast overcast daylight — see the
 * measured palette in docs/design-dna-sepang.json, where the dominant cluster
 * is the sky at #adbdcb. There are no crushed blacks in the footage, so the
 * grade has to synthesise them.
 *
 * Everything here is a pure function of the frame, so the browser player and a
 * headless Remotion render produce identical pixels.
 */

/** Cheap smooth ramp, 0..1. */
export const smooth = (t) => t * t * (3 - 2 * t);

export const clamp = (v, lo = 0, hi = 1) => Math.min(hi, Math.max(lo, v));

/**
 * Three looks, one per act. Act 2 and 3 get progressively cooler and heavier
 * because the plate itself is losing light as the storm arrives.
 */
export const LOOKS = {
  DRY: {
    contrast: 1.2,
    saturate: 1.14,
    brightness: 0.94,
    hueRotate: -5,
    sepia: 0.06,
    vignette: 0.62,
    bloom: 0.26,
    grain: 0.09,
    shadowTint: "rgba(20, 42, 66, 0.34)",
    highlightTint: "rgba(255, 196, 150, 0.14)"
  },
  RAIN: {
    contrast: 1.28,
    saturate: 1.04,
    brightness: 0.86,
    hueRotate: -12,
    sepia: 0.03,
    vignette: 0.74,
    bloom: 0.34,
    grain: 0.13,
    shadowTint: "rgba(14, 36, 62, 0.46)",
    highlightTint: "rgba(190, 214, 255, 0.12)"
  },
  MONSOON: {
    contrast: 1.36,
    saturate: 0.94,
    brightness: 0.78,
    hueRotate: -18,
    sepia: 0.0,
    vignette: 0.86,
    bloom: 0.42,
    grain: 0.17,
    shadowTint: "rgba(8, 26, 48, 0.56)",
    highlightTint: "rgba(168, 200, 255, 0.1)"
  }
};

export function lookFor(condition) {
  return LOOKS[condition] ?? LOOKS.DRY;
}

/**
 * Chromatic aberration presets.
 *
 * These are declared once as static SVG filters and selected by index, rather
 * than rebuilt every frame. Re-creating an SVG filter graph over a 1080p video
 * 24 times a second is the one thing that reliably tanks frame rate, so the
 * intensity is quantised into four buckets instead.
 */
export const CHROMA_STEPS = [0, 0.9, 1.9, 3.2];

export function chromaBucket(intensity) {
  const i = clamp(intensity);
  if (i < 0.22) return 0;
  if (i < 0.5) return 1;
  if (i < 0.78) return 2;
  return 3;
}

/**
 * The CSS filter chain applied to the video element.
 * `chromaId` is the id of one of the preset SVG filters, or null for none.
 */
export function filterChain(look, chromaId, extraContrast = 0) {
  const parts = [
    `contrast(${(look.contrast + extraContrast).toFixed(3)})`,
    `saturate(${look.saturate.toFixed(3)})`,
    `brightness(${look.brightness.toFixed(3)})`,
    `hue-rotate(${look.hueRotate.toFixed(1)}deg)`
  ];
  if (look.sepia > 0.001) parts.push(`sepia(${look.sepia.toFixed(3)})`);
  if (chromaId) parts.push(`url(#${chromaId})`);
  return parts.join(" ");
}

/**
 * Impact envelope: a short spike at the start of every cut, so each edit lands
 * with a flash of contrast and RGB split the way a broadcast cut does.
 */
export function cutImpact(localFrame, lengthFrames = 7) {
  if (localFrame >= lengthFrames) return 0;
  return smooth(1 - localFrame / lengthFrames);
}

/**
 * Braking envelope, derived from the real speed trace. Hard deceleration is
 * where the picture should feel like it is being torn at the edges.
 */
export function brakeIntensity(accelMs2) {
  return clamp(-accelMs2 / 26);
}

/** Speed envelope, for the streak overlay and the bloom lift. */
export function speedIntensity(speedKph) {
  return clamp((speedKph - 120) / 220);
}

/**
 * A 128px tiling noise plate, generated once per document and reused by every
 * grain layer. Animating background-position on a static tile is close to free;
 * animating an feTurbulence seed is not.
 */
let grainUrl = null;

export function grainTexture() {
  if (grainUrl) return grainUrl;
  if (typeof document === "undefined") return null;
  const size = 128;
  const canvas = document.createElement("canvas");
  canvas.width = size;
  canvas.height = size;
  const ctx = canvas.getContext("2d");
  if (!ctx) return null;
  const img = ctx.createImageData(size, size);
  // deterministic PRNG so the plate is identical on every load
  let seed = 0x2f6e2b1;
  const rand = () => {
    seed ^= seed << 13;
    seed ^= seed >>> 17;
    seed ^= seed << 5;
    return ((seed >>> 0) % 1000) / 1000;
  };
  for (let i = 0; i < img.data.length; i += 4) {
    const v = 110 + rand() * 90;
    img.data[i] = v;
    img.data[i + 1] = v;
    img.data[i + 2] = v;
    img.data[i + 3] = 255;
  }
  ctx.putImageData(img, 0, 0);
  grainUrl = canvas.toDataURL("image/png");
  return grainUrl;
}

/** Deterministic per-frame jitter for the grain plate. */
export function grainOffset(frame) {
  const a = (frame * 71) % 128;
  const b = (frame * 137) % 128;
  return `${a}px ${b}px`;
}

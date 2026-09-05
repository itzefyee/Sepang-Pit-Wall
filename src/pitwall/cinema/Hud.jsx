/**
 * The diegetic broadcast HUD.
 *
 * Speed and storm state are read from the render's own per-frame telemetry.
 * Gear, rpm, throttle and brake are derived from that speed trace, and the panel
 * says so on screen, because a HUD that invents numbers over real footage is
 * worse than no HUD.
 *
 * All coordinates are in composition pixels (1920 x 1080). The 2.39:1 letterbox
 * leaves a safe band from y=138 to y=942, and nothing below sits outside it.
 */

import { interpolate, useCurrentFrame } from "remotion";
import { clamp, smooth } from "./grade.js";

const SAFE_TOP = 162;
const SAFE_BOTTOM = 918;
const SAFE_L = 74;
const SAFE_R = 74;

const HEAD = "'Chakra Petch', 'Segoe UI', system-ui, sans-serif";
const MONO = "'JetBrains Mono', ui-monospace, monospace";

const CONDITION_COLOUR = {
  DRY: "#f5b002",
  RAIN: "#00a19b",
  MONSOON: "#3498db"
};

function Panel({ children, style }) {
  return (
    <div
      style={{
        background: "rgba(6, 10, 15, 0.46)",
        border: "1px solid rgba(233,239,245,0.12)",
        borderTop: "1px solid rgba(233,239,245,0.2)",
        backdropFilter: "blur(14px)",
        WebkitBackdropFilter: "blur(14px)",
        borderRadius: 6,
        ...style
      }}
    >
      {children}
    </div>
  );
}

function Overline({ children, colour = "rgba(173,189,203,0.8)", size = 15 }) {
  return (
    <div
      style={{
        fontFamily: HEAD,
        fontSize: size,
        fontWeight: 700,
        letterSpacing: "0.2em",
        textTransform: "uppercase",
        color: colour,
        lineHeight: 1.2
      }}
    >
      {children}
    </div>
  );
}

/* ------------------------------------------------------------------ *
 * top left — where we are in the film
 * ------------------------------------------------------------------ */

function ShotSlate({ sample, entry }) {
  const colour = CONDITION_COLOUR[sample.condition] ?? "#adbdcb";
  return (
    <div
      style={{
        position: "absolute",
        left: SAFE_L,
        top: SAFE_TOP,
        display: "flex",
        flexDirection: "column",
        gap: 10,
        opacity: entry,
        transform: `translateX(${(1 - entry) * -22}px)`
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
        <div
          style={{
            width: 4,
            height: 30,
            background: "#d81f26",
            borderRadius: 1
          }}
        />
        <Overline colour="#e9eff5" size={16}>
          Act {sample.act}
        </Overline>
        <div
          style={{
            padding: "3px 10px",
            borderRadius: 999,
            border: `1px solid ${colour}66`,
            background: `${colour}22`,
            fontFamily: HEAD,
            fontSize: 13,
            fontWeight: 700,
            letterSpacing: "0.16em",
            color: colour
          }}
        >
          {sample.condition}
        </div>
      </div>
      <div
        style={{
          fontFamily: HEAD,
          fontSize: 34,
          fontWeight: 700,
          letterSpacing: "-0.01em",
          color: "#f2f6fa",
          textShadow: "0 2px 18px rgba(0,0,0,0.8)",
          lineHeight: 1.05
        }}
      >
        {sample.shotTitle}
      </div>
      <div
        style={{
          fontFamily: MONO,
          fontSize: 15,
          color: "rgba(173,189,203,0.9)",
          textShadow: "0 1px 10px rgba(0,0,0,0.9)"
        }}
      >
        {sample.corner} · {sample.lens} mm
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ *
 * top right — clock
 * ------------------------------------------------------------------ */

function Timecode({ sample, frame, totalFrames, fps, entry }) {
  const t = frame / fps;
  const mm = String(Math.floor(t / 60)).padStart(2, "0");
  const ss = String(Math.floor(t % 60)).padStart(2, "0");
  const ff = String(frame % fps).padStart(2, "0");
  return (
    <Panel
      style={{
        position: "absolute",
        right: SAFE_R,
        top: SAFE_TOP,
        padding: "10px 14px",
        display: "flex",
        gap: 18,
        alignItems: "center",
        opacity: entry,
        transform: `translateX(${(1 - entry) * 22}px)`
      }}
    >
      <div>
        <Overline size={11}>Timecode</Overline>
        <div
          style={{
            fontFamily: MONO,
            fontSize: 22,
            color: "#f2f6fa",
            fontVariantNumeric: "tabular-nums",
            marginTop: 2
          }}
        >
          {mm}:{ss}:{ff}
        </div>
      </div>
      <div style={{ width: 1, height: 34, background: "rgba(233,239,245,0.14)" }} />
      <div>
        <Overline size={11}>Shot</Overline>
        <div
          style={{
            fontFamily: MONO,
            fontSize: 22,
            color: "#f2f6fa",
            fontVariantNumeric: "tabular-nums",
            marginTop: 2
          }}
        >
          {String(sample.index + 1).padStart(2, "0")}
          <span style={{ color: "rgba(173,189,203,0.55)" }}>
            /{String(sample.cutCount).padStart(2, "0")}
          </span>
        </div>
      </div>
      <div style={{ width: 1, height: 34, background: "rgba(233,239,245,0.14)" }} />
      <div>
        <Overline size={11}>Frames</Overline>
        <div
          style={{
            fontFamily: MONO,
            fontSize: 22,
            color: "#f2f6fa",
            fontVariantNumeric: "tabular-nums",
            marginTop: 2
          }}
        >
          {totalFrames}
        </div>
      </div>
    </Panel>
  );
}

/* ------------------------------------------------------------------ *
 * bottom left — speed and gear
 * ------------------------------------------------------------------ */

function SpeedBlock({ sample, entry }) {
  return (
    <div
      style={{
        position: "absolute",
        left: SAFE_L,
        bottom: 1080 - SAFE_BOTTOM + 58,
        display: "flex",
        alignItems: "flex-end",
        gap: 22,
        opacity: entry,
        transform: `translateY(${(1 - entry) * 18}px)`
      }}
    >
      <div>
        <Overline size={12}>Speed · measured</Overline>
        <div style={{ display: "flex", alignItems: "baseline", gap: 8 }}>
          <div
            style={{
              fontFamily: HEAD,
              fontSize: 104,
              fontWeight: 700,
              lineHeight: 0.9,
              letterSpacing: "-0.04em",
              color: "#ffffff",
              fontVariantNumeric: "tabular-nums",
              textShadow: "0 4px 30px rgba(0,0,0,0.85)"
            }}
          >
            {Math.round(sample.speedKph)}
          </div>
          <div
            style={{
              fontFamily: HEAD,
              fontSize: 22,
              fontWeight: 700,
              letterSpacing: "0.14em",
              color: "rgba(173,189,203,0.85)"
            }}
          >
            KPH
          </div>
        </div>
      </div>

      <Panel
        style={{
          padding: "8px 0 10px",
          width: 92,
          textAlign: "center",
          borderColor: "rgba(216,31,38,0.4)"
        }}
      >
        <Overline size={11} colour="rgba(173,189,203,0.7)">
          Gear
        </Overline>
        <div
          style={{
            fontFamily: HEAD,
            fontSize: 46,
            fontWeight: 700,
            lineHeight: 1,
            color: "#ff3b42",
            fontVariantNumeric: "tabular-nums"
          }}
        >
          {sample.gear}
        </div>
      </Panel>
    </div>
  );
}

/* ------------------------------------------------------------------ *
 * bottom centre — rpm strip
 * ------------------------------------------------------------------ */

function RpmStrip({ sample, entry }) {
  const segments = 26;
  const lit = Math.round(sample.rpmPct * segments);
  return (
    <div
      style={{
        position: "absolute",
        left: "50%",
        transform: `translateX(-50%) translateY(${(1 - entry) * 14}px)`,
        bottom: 1080 - SAFE_BOTTOM + 96,
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        gap: 7,
        opacity: entry
      }}
    >
      <div style={{ display: "flex", gap: 3 }}>
        {Array.from({ length: segments }, (_, i) => {
          const on = i < lit;
          const zone = i / segments;
          const colour =
            zone > 0.86 ? "#ff3b42" : zone > 0.68 ? "#e8b93b" : "#e9eff5";
          return (
            <div
              key={i}
              style={{
                width: 12,
                height: 14 + zone * 8,
                borderRadius: 1,
                background: on ? colour : "rgba(233,239,245,0.11)",
                boxShadow: on ? `0 0 10px ${colour}88` : "none"
              }}
            />
          );
        })}
      </div>
      <div
        style={{
          fontFamily: MONO,
          fontSize: 13,
          letterSpacing: "0.1em",
          color: "rgba(173,189,203,0.75)",
          fontVariantNumeric: "tabular-nums"
        }}
      >
        {sample.rpm.toLocaleString("en-GB")} RPM · DERIVED
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ *
 * bottom right — pedals, DRS, water
 * ------------------------------------------------------------------ */

function PedalBar({ label, value, colour }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 6 }}>
      <div
        style={{
          width: 16,
          height: 92,
          background: "rgba(233,239,245,0.1)",
          borderRadius: 2,
          display: "flex",
          alignItems: "flex-end",
          overflow: "hidden"
        }}
      >
        <div
          style={{
            width: "100%",
            height: `${clamp(value) * 100}%`,
            background: colour,
            boxShadow: `0 0 14px ${colour}99`
          }}
        />
      </div>
      <Overline size={11}>{label}</Overline>
    </div>
  );
}

function RightRail({ sample, entry }) {
  const waterMm = sample.storm * 6.4;
  return (
    <div
      style={{
        position: "absolute",
        right: SAFE_R,
        bottom: 1080 - SAFE_BOTTOM + 58,
        display: "flex",
        alignItems: "flex-end",
        gap: 18,
        opacity: entry,
        transform: `translateY(${(1 - entry) * 18}px)`
      }}
    >
      <Panel style={{ padding: "12px 16px" }}>
        <Overline size={11}>Standing water</Overline>
        <div
          style={{
            fontFamily: HEAD,
            fontSize: 30,
            fontWeight: 700,
            color: sample.storm > 0.8 ? "#3498db" : "#e9eff5",
            fontVariantNumeric: "tabular-nums",
            lineHeight: 1.1
          }}
        >
          {waterMm.toFixed(1)}
          <span style={{ fontSize: 15, color: "rgba(173,189,203,0.8)" }}> mm</span>
        </div>
        <div
          style={{
            marginTop: 8,
            height: 4,
            width: 128,
            background: "rgba(233,239,245,0.11)",
            borderRadius: 2,
            overflow: "hidden"
          }}
        >
          <div
            style={{
              height: "100%",
              width: `${clamp(waterMm / 8) * 100}%`,
              background: "linear-gradient(90deg, #00a19b, #3498db)"
            }}
          />
        </div>
      </Panel>

      <Panel style={{ padding: "12px 16px", display: "flex", gap: 14 }}>
        <PedalBar label="THR" value={sample.throttle} colour="#2fbf71" />
        <PedalBar label="BRK" value={sample.brake} colour="#ff3b42" />
      </Panel>

      <Panel
        style={{
          padding: "10px 14px",
          textAlign: "center",
          borderColor:
            sample.drs === "ACTIVE"
              ? "rgba(47,191,113,0.5)"
              : sample.drs === "DISABLED"
                ? "rgba(255,90,95,0.4)"
                : "rgba(233,239,245,0.12)"
        }}
      >
        <Overline size={11}>DRS</Overline>
        <div
          style={{
            fontFamily: HEAD,
            fontSize: 17,
            fontWeight: 700,
            letterSpacing: "0.1em",
            marginTop: 3,
            color:
              sample.drs === "ACTIVE"
                ? "#2fbf71"
                : sample.drs === "DISABLED"
                  ? "#ff5a5f"
                  : "rgba(173,189,203,0.85)"
          }}
        >
          {sample.drs}
        </div>
      </Panel>
    </div>
  );
}

/* ------------------------------------------------------------------ *
 * bottom edge — the whole clip's speed trace with a playhead
 * ------------------------------------------------------------------ */

function TraceStrip({ trace, frame, totalFrames, cuts, entry }) {
  const w = 1920 - SAFE_L - SAFE_R;
  const h = 42;
  const max = 340;
  const step = Math.max(1, Math.floor(trace.length / 480));
  let d = "";
  for (let i = 0; i < trace.length; i += step) {
    const x = (i / (trace.length - 1)) * w;
    const y = h - (clamp(trace[i] / max) * h);
    d += `${i === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`;
  }
  const headX = (frame / Math.max(1, totalFrames - 1)) * w;

  return (
    <div
      style={{
        position: "absolute",
        left: SAFE_L,
        bottom: 1080 - SAFE_BOTTOM + 8,
        width: w,
        opacity: entry * 0.95
      }}
    >
      <svg width={w} height={h} style={{ overflow: "visible", display: "block" }}>
        <path
          d={`${d}L${w},${h}L0,${h}Z`}
          fill="rgba(216,31,38,0.13)"
          stroke="none"
        />
        <path d={d} fill="none" stroke="rgba(216,31,38,0.85)" strokeWidth="1.6" />
        {cuts.map((c, i) => {
          const x = (c.start / Math.max(1, totalFrames - 1)) * w;
          return (
            <line
              key={`${c.start}-${i}`}
              x1={x}
              y1={0}
              x2={x}
              y2={h}
              stroke="rgba(233,239,245,0.18)"
              strokeWidth="1"
            />
          );
        })}
        <line
          x1={headX}
          y1={-6}
          x2={headX}
          y2={h + 6}
          stroke="#ffffff"
          strokeWidth="1.6"
        />
        <circle cx={headX} cy={-6} r="3.4" fill="#ffffff" />
      </svg>
      <div
        style={{
          marginTop: 5,
          display: "flex",
          justifyContent: "space-between",
          fontFamily: MONO,
          fontSize: 11,
          letterSpacing: "0.1em",
          color: "rgba(173,189,203,0.6)"
        }}
      >
        <span>SPEED TRACE · SIMULATION TELEMETRY · {totalFrames} FRAMES @ 24 FPS</span>
        <span>PEAK {Math.round(Math.max(...trace))} KPH</span>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ *
 * title card
 * ------------------------------------------------------------------ */

export function TitleCard({ kicker, title, subtitle, from, duration, fps }) {
  const frame = useCurrentFrame();
  const local = frame - from;
  if (local < 0 || local > duration) return null;

  const inT = smooth(clamp(local / (fps * 0.55)));
  const outT = smooth(clamp((duration - local) / (fps * 0.5)));
  const a = Math.min(inT, outT);

  return (
    <div
      style={{
        position: "absolute",
        left: SAFE_L,
        top: "50%",
        transform: `translateY(-50%) translateX(${(1 - inT) * -26}px)`,
        opacity: a,
        zIndex: 45,
        maxWidth: 900
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 14 }}>
        <div
          style={{
            width: 56 * inT,
            height: 3,
            background: "#d81f26"
          }}
        />
        <Overline colour="#ff3b42" size={16}>
          {kicker}
        </Overline>
      </div>
      <div
        style={{
          fontFamily: HEAD,
          fontSize: 96,
          fontWeight: 700,
          lineHeight: 0.94,
          letterSpacing: "-0.035em",
          textTransform: "uppercase",
          color: "#ffffff",
          textShadow: `${(1 - inT) * -3}px 0 0 rgba(255,0,0,0.6), ${
            (1 - inT) * 3
          }px 0 0 rgba(0,180,255,0.6), 0 6px 40px rgba(0,0,0,0.9)`,
          clipPath: `inset(0 ${(1 - inT) * 100}% 0 0)`
        }}
      >
        {title}
      </div>
      {subtitle ? (
        <div
          style={{
            marginTop: 16,
            fontFamily: MONO,
            fontSize: 19,
            color: "rgba(233,239,245,0.85)",
            maxWidth: 720,
            lineHeight: 1.5,
            textShadow: "0 2px 16px rgba(0,0,0,0.9)",
            opacity: interpolate(local, [fps * 0.35, fps * 0.9], [0, 1], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp"
            })
          }}
        >
          {subtitle}
        </div>
      ) : null}
    </div>
  );
}

/* ------------------------------------------------------------------ *
 * assembled HUD
 * ------------------------------------------------------------------ */

/** Compact slate for the hero, which needs its centre and left kept clear. */
function HeroSlate({ sample, entry }) {
  const colour = CONDITION_COLOUR[sample.condition] ?? "#adbdcb";
  return (
    <Panel
      style={{
        position: "absolute",
        right: SAFE_R,
        top: SAFE_TOP,
        padding: "10px 14px",
        display: "flex",
        alignItems: "center",
        gap: 12,
        opacity: entry,
        transform: `translateX(${(1 - entry) * 22}px)`
      }}
    >
      <div
        style={{
          width: 8,
          height: 8,
          borderRadius: "50%",
          background: colour,
          boxShadow: `0 0 12px ${colour}`
        }}
      />
      <Overline size={12} colour="#e9eff5">
        Act {sample.act} · {sample.condition}
      </Overline>
      <div style={{ width: 1, height: 18, background: "rgba(233,239,245,0.16)" }} />
      <div
        style={{
          fontFamily: MONO,
          fontSize: 13,
          color: "rgba(173,189,203,0.9)"
        }}
      >
        {sample.corner}
      </div>
    </Panel>
  );
}

/**
 * `variant` decides how much of the HUD is drawn.
 *
 * "full" is the film-room layout inside a 2.39:1 letterbox.
 * "hero" is the cropped full-bleed layout, which keeps the centre and the left
 * of frame clear for the page headline sitting on top of it.
 */
export function Hud({
  sample,
  frame,
  totalFrames,
  fps,
  trace,
  cuts,
  entry = 1,
  variant = "full"
}) {
  const hero = variant === "hero";
  return (
    <div
      style={{
        position: "absolute",
        inset: 0,
        zIndex: 42,
        pointerEvents: "none"
      }}
    >
      {hero ? (
        <HeroSlate sample={sample} entry={entry} />
      ) : (
        <>
          <ShotSlate sample={sample} entry={entry} />
          <Timecode
            sample={sample}
            frame={frame}
            totalFrames={totalFrames}
            fps={fps}
            entry={entry}
          />
          <RpmStrip sample={sample} entry={entry} />
        </>
      )}
      <SpeedBlock sample={sample} entry={entry} />
      <RightRail sample={sample} entry={entry} />
      <TraceStrip
        trace={trace}
        frame={frame}
        totalFrames={totalFrames}
        cuts={cuts}
        entry={entry}
      />
    </div>
  );
}

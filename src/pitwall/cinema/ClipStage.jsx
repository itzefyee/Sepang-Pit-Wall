/**
 * The browser-side cinema surface: a Remotion <Player> running our composition,
 * wrapped in a broadcast-styled transport.
 *
 * Two behaviours worth knowing about:
 *
 *  - Players pause themselves when scrolled out of view. Three 1080p decoders
 *    running at once on a laptop is the difference between a smooth page and a
 *    stuttering one.
 *  - Autoplay is always muted, because every browser blocks unmuted autoplay.
 *    The transport exposes an explicit sound control instead of pretending.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Player } from "@remotion/player";

import { CLIPS, FPS, TELEMETRY, cutAtFrame } from "../data/clips.js";
import { SepangComposition } from "./SepangComposition.jsx";

let uidSeq = 0;

function usePrefersReducedMotion() {
  const [reduced, setReduced] = useState(false);
  useEffect(() => {
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    setReduced(mq.matches);
    const onChange = (e) => setReduced(e.matches);
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, []);
  return reduced;
}

function Icon({ name }) {
  const common = {
    width: 16,
    height: 16,
    viewBox: "0 0 16 16",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: 1.6,
    strokeLinecap: "round",
    strokeLinejoin: "round",
    "aria-hidden": true
  };
  if (name === "play")
    return (
      <svg {...common}>
        <path d="M4 2.6l9 5.4-9 5.4z" fill="currentColor" stroke="none" />
      </svg>
    );
  if (name === "pause")
    return (
      <svg {...common}>
        <path d="M5 3v10M11 3v10" />
      </svg>
    );
  if (name === "restart")
    return (
      <svg {...common}>
        <path d="M13.5 8a5.5 5.5 0 1 1-1.9-4.2" />
        <path d="M13.6 1.6v2.6h-2.6" />
      </svg>
    );
  if (name === "sound")
    return (
      <svg {...common}>
        <path d="M3 6h2l3-2.4v8.8L5 10H3z" />
        <path d="M10.6 5.6a3 3 0 0 1 0 4.8" />
      </svg>
    );
  if (name === "muted")
    return (
      <svg {...common}>
        <path d="M3 6h2l3-2.4v8.8L5 10H3z" />
        <path d="M10.8 6.2l3 3.6M13.8 6.2l-3 3.6" />
      </svg>
    );
  if (name === "expand")
    return (
      <svg {...common}>
        <path d="M6 2H2v4M10 14h4v-4M14 6V2h-4M2 10v4h4" />
      </svg>
    );
  return null;
}

export function ClipStage({
  clipKey,
  variant = "full",
  letterbox = true,
  showHud = true,
  showTitles = true,
  transport = true,
  autoPlay = true,
  loop = true,
  className = "",
  fill = false,
  soundControl = false,
  soundLabel = "Sound"
}) {
  const clip = CLIPS[clipKey];
  const uid = useMemo(() => `cine${(uidSeq += 1)}`, []);
  const playerRef = useRef(null);
  const hostRef = useRef(null);
  const reduced = usePrefersReducedMotion();

  const [frame, setFrame] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [muted, setMuted] = useState(true);
  const [failed, setFailed] = useState(false);
  const [inView, setInView] = useState(false);

  const cuts = TELEMETRY.edits[clip.edit].cuts;
  const total = clip.durationInFrames;

  const inputProps = useMemo(
    () => ({
      clipKey,
      variant,
      showHud,
      showTitles,
      letterbox,
      uid
    }),
    [clipKey, variant, showHud, showTitles, letterbox, uid]
  );

  /* --- frame + transport state --------------------------------------- */
  useEffect(() => {
    const p = playerRef.current;
    if (!p) return;
    const onFrame = (e) => {
      // 24 state updates a second is wasteful for a scrub bar; every third is plenty
      const f = e.detail.frame;
      setFrame((prev) => (Math.abs(f - prev) >= 3 || f === 0 ? f : prev));
    };
    const onPlay = () => setPlaying(true);
    const onPause = () => setPlaying(false);
    const onError = () => setFailed(true);
    p.addEventListener("frameupdate", onFrame);
    p.addEventListener("play", onPlay);
    p.addEventListener("pause", onPause);
    p.addEventListener("error", onError);
    return () => {
      p.removeEventListener("frameupdate", onFrame);
      p.removeEventListener("play", onPlay);
      p.removeEventListener("pause", onPause);
      p.removeEventListener("error", onError);
    };
  }, []);

  /* --- pause when off screen ----------------------------------------- */
  useEffect(() => {
    const host = hostRef.current;
    if (!host) return;
    const io = new IntersectionObserver(
      ([entry]) => setInView(entry.isIntersecting && entry.intersectionRatio > 0.15),
      { threshold: [0, 0.15, 0.5] }
    );
    io.observe(host);
    return () => io.disconnect();
  }, []);

  useEffect(() => {
    const p = playerRef.current;
    if (!p) return;
    if (!autoPlay || reduced) return;
    if (inView) {
      // play() can reject if the browser is still deciding about autoplay
      Promise.resolve(p.play()).catch(() => {});
    } else {
      p.pause();
    }
  }, [inView, autoPlay, reduced]);

  const toggle = useCallback(() => {
    const p = playerRef.current;
    if (!p) return;
    if (p.isPlaying()) p.pause();
    else Promise.resolve(p.play()).catch(() => {});
  }, []);

  const restart = useCallback(() => {
    const p = playerRef.current;
    if (!p) return;
    p.seekTo(0);
    Promise.resolve(p.play()).catch(() => {});
  }, []);

  const toggleSound = useCallback(() => {
    const p = playerRef.current;
    if (!p) return;
    if (p.isMuted()) {
      p.unmute();
      setMuted(false);
    } else {
      p.mute();
      setMuted(true);
    }
  }, []);

  const expand = useCallback(() => {
    const p = playerRef.current;
    if (!p) return;
    try {
      p.requestFullscreen();
    } catch {
      /* fullscreen refused, nothing to do */
    }
  }, []);

  const onScrub = useCallback((e) => {
    const p = playerRef.current;
    if (!p) return;
    const next = Number(e.target.value);
    p.seekTo(next);
    setFrame(next);
  }, []);

  const jumpToCut = useCallback((start) => {
    const p = playerRef.current;
    if (!p) return;
    p.seekTo(start);
    setFrame(start);
    Promise.resolve(p.play()).catch(() => {});
  }, []);

  const current = cutAtFrame(clip.edit, frame);
  const seconds = frame / FPS;
  const totalSeconds = total / FPS;

  const fmt = (s) =>
    `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, "0")}`;

  return (
    <div
      ref={hostRef}
      className={`stage ${fill ? "stage--fill" : ""} ${className}`}
      data-clip={clipKey}
    >
      <div className="stage__screen">
        {failed ? (
          <div className="stage__fail">
            <p className="t-overline hot">Plate unavailable</p>
            <p className="t-small dim">
              {clip.src} did not load. The dev server serves the renders from the
              project root — check the file is still there.
            </p>
          </div>
        ) : (
          <Player
            ref={playerRef}
            component={SepangComposition}
            inputProps={inputProps}
            durationInFrames={total}
            fps={FPS}
            compositionWidth={clip.width}
            compositionHeight={clip.height}
            style={{ width: "100%", height: "100%" }}
            controls={false}
            loop={loop}
            autoPlay={false}
            initiallyMuted
            clickToPlay={false}
            doubleClickToFullscreen={false}
            spaceKeyToPlayOrPause={false}
            overflowVisible={false}
            renderLoading={() => (
              <div className="stage__loading">
                <span className="t-overline dim">Loading plate…</span>
              </div>
            )}
            errorFallback={() => (
              <div className="stage__fail">
                <p className="t-overline hot">Composition error</p>
              </div>
            )}
          />
        )}
      </div>

      {soundControl ? (
        <button
          className="stage__sound-control"
          onClick={toggleSound}
          aria-label={muted ? `Turn ${soundLabel.toLowerCase()} on` : `Mute ${soundLabel.toLowerCase()}`}
          aria-pressed={!muted}
          type="button"
        >
          <Icon name={muted ? "muted" : "sound"} />
          <span>{soundLabel} {muted ? "off" : "on"}</span>
        </button>
      ) : null}

      {transport ? (
        <div className="stage__transport">
          <div className="stage__row">
            <button
              className="tbtn tbtn--primary"
              onClick={toggle}
              aria-label={playing ? "Pause" : "Play"}
              type="button"
            >
              <Icon name={playing ? "pause" : "play"} />
            </button>
            <button
              className="tbtn"
              onClick={restart}
              aria-label="Restart from the first frame"
              type="button"
            >
              <Icon name="restart" />
            </button>
            <button
              className="tbtn"
              onClick={toggleSound}
              aria-label={muted ? "Turn the engine mix on" : "Mute"}
              type="button"
              data-on={!muted}
            >
              <Icon name={muted ? "muted" : "sound"} />
            </button>

            <div className="stage__scrubwrap">
              <input
                type="range"
                min={0}
                max={total - 1}
                step={1}
                value={Math.min(frame, total - 1)}
                onChange={onScrub}
                aria-label="Scrub the clip"
                className="stage__scrub"
                style={{ "--fill": `${(frame / (total - 1)) * 100}%` }}
              />
              <div className="stage__ticks" aria-hidden="true">
                {cuts.map((c) => (
                  <span
                    key={c.start}
                    className="stage__tick"
                    data-active={c.shot === current.cut.shot}
                    style={{ left: `${(c.start / (total - 1)) * 100}%` }}
                  />
                ))}
              </div>
            </div>

            <span className="stage__clock mono">
              {fmt(seconds)} / {fmt(totalSeconds)}
            </span>

            <button
              className="tbtn"
              onClick={expand}
              aria-label="Full screen"
              type="button"
            >
              <Icon name="expand" />
            </button>
          </div>

          <div className="stage__cuts" role="tablist" aria-label="Shots in this clip">
            {cuts.map((c, i) => {
              const shot = TELEMETRY.shots[String(c.shot)];
              const active = i === current.index;
              return (
                <button
                  key={`${c.shot}-${c.start}`}
                  type="button"
                  role="tab"
                  aria-selected={active}
                  className="stage__cut"
                  onClick={() => jumpToCut(c.start)}
                  title={`${shot.title} — ${shot.corner}`}
                >
                  <span className="stage__cutno mono">
                    {String(i + 1).padStart(2, "0")}
                  </span>
                  <span className="stage__cutname">{shot.title}</span>
                </button>
              );
            })}
          </div>
        </div>
      ) : null}
    </div>
  );
}

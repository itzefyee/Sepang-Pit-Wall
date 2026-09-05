/**
 * The browser-side cinema surface: a Remotion <Player> running our composition,
 * wrapped in a broadcast-styled transport.
 *
 * Fullscreen controls and keyboard shortcuts:
 *  - Space / K : Play / Pause
 *  - F         : Toggle Fullscreen
 *  - M         : Mute / Unmute
 *  - Up / Down : Adjust Volume (±10%)
 *  - Left / Right (or J / L) : Seek 2s
 *  - [ / ]     : Previous / Next Shot
 *  - R / 0     : Restart from beginning
 *  - ? / H     : Shortcuts Guide
 *  - Esc       : Exit Fullscreen / Close dialog
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
        <path d="M12.8 4a5.2 5.2 0 0 1 0 8" />
      </svg>
    );
  if (name === "soundLow" || name === "sound-low")
    return (
      <svg {...common}>
        <path d="M3 6h2l3-2.4v8.8L5 10H3z" />
        <path d="M10.6 6.2a2.4 2.4 0 0 1 0 3.6" />
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
  if (name === "compress")
    return (
      <svg {...common}>
        <path d="M2 6h4V2M14 10h-4v4M10 2v4h4M6 14v-4H2" />
      </svg>
    );
  if (name === "prev")
    return (
      <svg {...common}>
        <path d="M3.5 3v10M12.5 3.5L5.5 8l7 4.5V3.5z" fill="currentColor" />
      </svg>
    );
  if (name === "next")
    return (
      <svg {...common}>
        <path d="M12.5 3v10M3.5 3.5L10.5 8l-7 4.5V3.5z" fill="currentColor" />
      </svg>
    );
  if (name === "keyboard")
    return (
      <svg {...common}>
        <rect x="2" y="3.5" width="12" height="9" rx="1.5" />
        <path d="M4.5 6.5h1M7.5 6.5h1M10.5 6.5h1M4.5 9.5h7" />
      </svg>
    );
  if (name === "close")
    return (
      <svg {...common}>
        <path d="M3.5 3.5l9 9M12.5 3.5l-9 9" />
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
  soundLabel = "Sound",
  eager = false,
  lightweight = false
}) {
  const clip = CLIPS[clipKey];
  const uid = useMemo(() => `cine${(uidSeq += 1)}`, []);
  const playerRef = useRef(null);
  const hostRef = useRef(null);
  const reduced = usePrefersReducedMotion();

  const [hasActivated, setHasActivated] = useState(eager);
  const [frame, setFrame] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [muted, setMuted] = useState(true);
  const [volume, setVolumeState] = useState(0.8);
  const prevVolumeRef = useRef(0.8);
  const [failed, setFailed] = useState(false);
  const [inView, setInView] = useState(false);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [controlsVisible, setControlsVisible] = useState(true);
  const [showShortcuts, setShowShortcuts] = useState(false);
  const [toast, setToast] = useState(null);

  const cuts = TELEMETRY.edits[clip.edit].cuts;
  const total = clip.durationInFrames;

  const toastTimerRef = useRef(null);
  const hideControlsTimerRef = useRef(null);

  const showToast = useCallback((msg) => {
    if (toastTimerRef.current) clearTimeout(toastTimerRef.current);
    setToast(msg);
    toastTimerRef.current = setTimeout(() => setToast(null), 1200);
  }, []);

  // Remove black bars when not full screen: letterbox is only active if isFullscreen is true
  const inputProps = useMemo(
    () => ({
      clipKey,
      variant,
      showHud,
      showTitles,
      letterbox: isFullscreen ? letterbox : false,
      uid,
      lightweight
    }),
    [clipKey, variant, showHud, showTitles, letterbox, isFullscreen, uid, lightweight]
  );

  /* --- lazy mounting: activate player when within 350px of viewport or clicked --- */
  /* On mobile (lightweight), skip IO auto-activation — require explicit tap. */
  useEffect(() => {
    if (eager || hasActivated || lightweight) return;
    const host = hostRef.current;
    if (!host) return;
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setHasActivated(true);
          observer.disconnect();
        }
      },
      { rootMargin: "350px 0px 350px 0px" }
    );
    observer.observe(host);
    return () => observer.disconnect();
  }, [eager, hasActivated, lightweight]);

  /* --- mobile one-at-a-time: when a lightweight clip activates, unmount others --- */
  useEffect(() => {
    if (!lightweight) return;
    const onDemand = (e) => {
      if (e.detail?.uid !== uid && hasActivated) {
        setHasActivated(false);
        setPlaying(false);
        setFrame(0);
      }
    };
    window.addEventListener("pitwall:videodemand", onDemand);
    return () => window.removeEventListener("pitwall:videodemand", onDemand);
  }, [lightweight, uid, hasActivated]);

  /* Broadcast demand when this lightweight clip activates */
  useEffect(() => {
    if (lightweight && hasActivated) {
      window.dispatchEvent(new CustomEvent("pitwall:videodemand", { detail: { uid } }));
    }
  }, [lightweight, hasActivated, uid]);

  /* --- global playback coordinator: only 1 video decodes/plays at a time on mobile --- */
  useEffect(() => {
    const onOtherPlay = (e) => {
      if (e.detail?.uid !== uid) {
        const p = playerRef.current;
        if (p && p.isPlaying()) {
          p.pause();
        }
      }
    };
    window.addEventListener("pitwall:videoplay", onOtherPlay);
    return () => window.removeEventListener("pitwall:videoplay", onOtherPlay);
  }, [uid]);

  /* --- frame + transport state --------------------------------------- */
  useEffect(() => {
    if (!hasActivated) return;
    const p = playerRef.current;
    if (!p) return;
    const onFrame = (e) => {
      const f = e.detail.frame;
      setFrame((prev) => (Math.abs(f - prev) >= 3 || f === 0 ? f : prev));
    };
    const onPlay = () => {
      setPlaying(true);
      window.dispatchEvent(new CustomEvent("pitwall:videoplay", { detail: { uid } }));
    };
    const onPause = () => setPlaying(false);
    const onError = () => setFailed(true);
    const onMuteChange = (e) => {
      if (typeof e.detail?.isMuted === "boolean") {
        setMuted(e.detail.isMuted);
      }
    };
    const onVolumeChange = (e) => {
      if (typeof e.detail?.volume === "number") {
        setVolumeState(e.detail.volume);
      }
    };

    p.addEventListener("frameupdate", onFrame);
    p.addEventListener("play", onPlay);
    p.addEventListener("pause", onPause);
    p.addEventListener("error", onError);
    p.addEventListener("mutechange", onMuteChange);
    p.addEventListener("volumechange", onVolumeChange);

    return () => {
      p.removeEventListener("frameupdate", onFrame);
      p.removeEventListener("play", onPlay);
      p.removeEventListener("pause", onPause);
      p.removeEventListener("error", onError);
      p.removeEventListener("mutechange", onMuteChange);
      p.removeEventListener("volumechange", onVolumeChange);
    };
  }, [hasActivated, uid]);

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
    if (!hasActivated) return;
    const p = playerRef.current;
    if (!p) return;
    if (!autoPlay || reduced) return;
    if (inView) {
      Promise.resolve(p.play()).catch(() => {});
    } else {
      p.pause();
    }
  }, [hasActivated, inView, autoPlay, reduced]);

  /* --- fullscreen detection ------------------------------------------ */
  useEffect(() => {
    const onFsChange = () => {
      const host = hostRef.current;
      const isFs = !!(
        document.fullscreenElement === host ||
        document.webkitFullscreenElement === host
      );
      setIsFullscreen(isFs);
      if (isFs) {
        setControlsVisible(true);
      } else {
        setShowShortcuts(false);
        setControlsVisible(true);
      }
    };
    document.addEventListener("fullscreenchange", onFsChange);
    document.addEventListener("webkitfullscreenchange", onFsChange);
    return () => {
      document.removeEventListener("fullscreenchange", onFsChange);
      document.removeEventListener("webkitfullscreenchange", onFsChange);
    };
  }, []);

  /* --- auto-hide controls in fullscreen ------------------------------- */
  const resetControlsTimer = useCallback(() => {
    setControlsVisible(true);
    if (hideControlsTimerRef.current) clearTimeout(hideControlsTimerRef.current);
    if (isFullscreen && playing && !showShortcuts) {
      hideControlsTimerRef.current = setTimeout(() => {
        setControlsVisible(false);
      }, 2600);
    }
  }, [isFullscreen, playing, showShortcuts]);

  useEffect(() => {
    if (!playing) {
      setControlsVisible(true);
      if (hideControlsTimerRef.current) clearTimeout(hideControlsTimerRef.current);
    } else if (isFullscreen) {
      resetControlsTimer();
    }
  }, [playing, isFullscreen, resetControlsTimer]);

  /* --- player actions ------------------------------------------------ */
  const toggle = useCallback(() => {
    const p = playerRef.current;
    if (!p) return;
    if (p.isPlaying()) {
      p.pause();
      showToast("⏸ Paused");
    } else {
      Promise.resolve(p.play()).catch(() => {});
      showToast("▶ Playing");
    }
  }, [showToast]);

  const restart = useCallback(() => {
    const p = playerRef.current;
    if (!p) return;
    p.seekTo(0);
    setFrame(0);
    Promise.resolve(p.play()).catch(() => {});
    showToast("↺ Restart");
  }, [showToast]);

  const applyVolume = useCallback((val, showToastMsg = true) => {
    const p = playerRef.current;
    const clamped = Math.max(0, Math.min(1, Math.round(val * 100) / 100));
    setVolumeState(clamped);
    if (clamped > 0) {
      prevVolumeRef.current = clamped;
    }
    if (p) {
      p.setVolume(clamped);
      if (clamped === 0) {
        p.mute();
        setMuted(true);
        if (showToastMsg) showToast("🔇 Audio Muted");
      } else {
        if (p.isMuted()) p.unmute();
        setMuted(false);
        if (showToastMsg) showToast(`🔊 Volume ${Math.round(clamped * 100)}%`);
      }
    }
  }, [showToast]);

  const onVolumeSliderChange = useCallback((e) => {
    const nextVal = parseFloat(e.target.value);
    applyVolume(nextVal, true);
  }, [applyVolume]);

  const toggleSound = useCallback(() => {
    const p = playerRef.current;
    if (!p) return;
    if (muted || volume === 0) {
      const restore = prevVolumeRef.current > 0 ? prevVolumeRef.current : 0.8;
      applyVolume(restore, true);
    } else {
      prevVolumeRef.current = volume;
      p.mute();
      setMuted(true);
      showToast("🔇 Audio Muted");
    }
  }, [muted, volume, applyVolume, showToast]);

  const adjustVolumeDelta = useCallback((delta) => {
    const currentVal = muted ? 0 : volume;
    const next = Math.max(0, Math.min(1, Math.round((currentVal + delta) * 10) / 10));
    applyVolume(next, true);
  }, [muted, volume, applyVolume]);

  const toggleFullscreen = useCallback(() => {
    const host = hostRef.current;
    if (!host) return;
    const isFs = !!(
      document.fullscreenElement === host ||
      document.webkitFullscreenElement === host
    );
    if (!isFs) {
      if (host.requestFullscreen) {
        host.requestFullscreen().catch(() => {});
      } else if (host.webkitRequestFullscreen) {
        host.webkitRequestFullscreen();
      }
      showToast("⛶ Fullscreen");
    } else {
      if (document.exitFullscreen) {
        document.exitFullscreen().catch(() => {});
      } else if (document.webkitExitFullscreen) {
        document.webkitExitFullscreen();
      }
      showToast("⛶ Windowed");
    }
  }, [showToast]);

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

  const jumpPrevCut = useCallback(() => {
    const p = playerRef.current;
    if (!p) return;
    const cur = cutAtFrame(clip.edit, frame);
    let targetIndex = cur.index;
    if (cur.localFrame > FPS * 0.8 && cur.index >= 0) {
      targetIndex = cur.index;
    } else {
      targetIndex = Math.max(0, cur.index - 1);
    }
    const targetStart = cuts[targetIndex].start;
    p.seekTo(targetStart);
    setFrame(targetStart);
    const shot = TELEMETRY.shots[String(cuts[targetIndex].shot)];
    showToast(`⏮ Shot ${String(targetIndex + 1).padStart(2, "0")}: ${shot.title}`);
  }, [clip.edit, frame, cuts, showToast]);

  const jumpNextCut = useCallback(() => {
    const p = playerRef.current;
    if (!p) return;
    const cur = cutAtFrame(clip.edit, frame);
    const targetIndex = Math.min(cuts.length - 1, cur.index + 1);
    const targetStart = cuts[targetIndex].start;
    p.seekTo(targetStart);
    setFrame(targetStart);
    const shot = TELEMETRY.shots[String(cuts[targetIndex].shot)];
    showToast(`⏭ Shot ${String(targetIndex + 1).padStart(2, "0")}: ${shot.title}`);
  }, [clip.edit, frame, cuts, showToast]);

  const seekDelta = useCallback((deltaFrames) => {
    const p = playerRef.current;
    if (!p) return;
    const next = Math.max(0, Math.min(total - 1, frame + deltaFrames));
    p.seekTo(next);
    setFrame(next);
    const s = Math.abs(deltaFrames) / FPS;
    const sign = deltaFrames > 0 ? "+" : "-";
    const icon = deltaFrames > 0 ? "⏩" : "⏪";
    showToast(`${icon} ${sign}${s.toFixed(0)}s (${fmt(next / FPS)})`);
  }, [frame, total, showToast]);

  /* --- keyboard shortcuts ------------------------------------------- */
  useEffect(() => {
    const onKeyDown = (e) => {
      const tag = e.target?.tagName?.toLowerCase();
      if (tag === "input" && e.target.type !== "range") return;
      if (tag === "textarea") return;

      const host = hostRef.current;
      const isFs = isFullscreen;
      const isHostActive = host && (host.contains(document.activeElement) || host.contains(e.target));

      if (!isFs && !isHostActive) return;

      switch (e.key) {
        case " ":
        case "k":
        case "K":
          e.preventDefault();
          toggle();
          resetControlsTimer();
          break;
        case "f":
        case "F":
          e.preventDefault();
          toggleFullscreen();
          break;
        case "m":
        case "M":
          e.preventDefault();
          toggleSound();
          resetControlsTimer();
          break;
        case "ArrowUp":
          e.preventDefault();
          adjustVolumeDelta(0.1);
          resetControlsTimer();
          break;
        case "ArrowDown":
          e.preventDefault();
          adjustVolumeDelta(-0.1);
          resetControlsTimer();
          break;
        case "ArrowLeft":
        case "j":
        case "J":
          e.preventDefault();
          seekDelta(-FPS * 2);
          resetControlsTimer();
          break;
        case "ArrowRight":
        case "l":
        case "L":
          e.preventDefault();
          seekDelta(FPS * 2);
          resetControlsTimer();
          break;
        case "[":
          e.preventDefault();
          jumpPrevCut();
          resetControlsTimer();
          break;
        case "]":
          e.preventDefault();
          jumpNextCut();
          resetControlsTimer();
          break;
        case "r":
        case "R":
        case "0":
        case "Home":
          e.preventDefault();
          restart();
          resetControlsTimer();
          break;
        case "?":
        case "h":
        case "H":
          e.preventDefault();
          setShowShortcuts((prev) => !prev);
          setControlsVisible(true);
          break;
        case "Escape":
          if (showShortcuts) {
            e.preventDefault();
            setShowShortcuts(false);
          }
          break;
        default:
          break;
      }
    };

    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [
    isFullscreen,
    toggle,
    toggleFullscreen,
    toggleSound,
    adjustVolumeDelta,
    seekDelta,
    jumpPrevCut,
    jumpNextCut,
    restart,
    showShortcuts,
    resetControlsTimer
  ]);

  const current = cutAtFrame(clip.edit, frame);
  const seconds = frame / FPS;
  const totalSeconds = total / FPS;

  const fmt = (s) =>
    `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, "0")}`;

  const handleScreenClick = useCallback(
    (e) => {
      if (
        e.target.closest("button") ||
        e.target.closest("input") ||
        e.target.closest(".stage__shortcuts-modal")
      )
        return;
      if (!hasActivated) {
        setHasActivated(true);
        return;
      }
      toggle();
      resetControlsTimer();
    },
    [hasActivated, toggle, resetControlsTimer]
  );

  const handleDoubleClick = useCallback((e) => {
    if (
      e.target.closest("button") ||
      e.target.closest("input") ||
      e.target.closest(".stage__shortcuts-modal")
    )
      return;
    toggleFullscreen();
  }, [toggleFullscreen]);

  const soundIconName = muted || volume === 0 ? "muted" : volume <= 0.4 ? "soundLow" : "sound";
  const soundPercent = muted || volume === 0 ? 0 : Math.round(volume * 100);

  return (
    <div
      ref={hostRef}
      className={`stage ${fill ? "stage--fill" : ""} ${isFullscreen ? "stage--fullscreen" : ""} ${isFullscreen && !controlsVisible ? "stage--cursor-hidden" : ""} ${className}`}
      data-clip={clipKey}
      onMouseMove={resetControlsTimer}
      onDoubleClick={handleDoubleClick}
      tabIndex={0}
      aria-label={`${clip.title} Player`}
    >
      {/* HUD Toast feedback */}
      {toast && (
        <div className="stage__toast" role="status" aria-live="polite">
          <span>{toast}</span>
        </div>
      )}

      {/* Fullscreen Top Header Overlay */}
      {isFullscreen && (
        <div
          className={`stage__fs-top ${!controlsVisible ? "stage__fs-top--hidden" : ""}`}
          onMouseEnter={() => setControlsVisible(true)}
        >
          <div className="stage__fs-titleblock">
            <span className="t-overline hot">{clip.kicker}</span>
            <span className="stage__fs-title">{clip.title}</span>
            <span className="stage__fs-curshot mono">
              Shot {String(current.index + 1).padStart(2, "0")} · {current.shot.title} ({current.shot.corner})
            </span>
          </div>

          <div className="stage__fs-actions">
            <button
              type="button"
              className="stage__fs-btn"
              onClick={() => setShowShortcuts((v) => !v)}
              aria-label="Keyboard shortcuts"
              title="Keyboard shortcuts (?)"
            >
              <Icon name="keyboard" />
              <span>Shortcuts [?]</span>
            </button>

            <button
              type="button"
              className="stage__fs-btn stage__fs-btn--close"
              onClick={toggleFullscreen}
              aria-label="Exit fullscreen (Esc)"
              title="Exit fullscreen (Esc)"
            >
              <Icon name="compress" />
              <span>Exit</span>
            </button>
          </div>
        </div>
      )}

      {/* Screen container */}
      <div className="stage__screen" onClick={handleScreenClick}>
        {!hasActivated ? (
          <div className="stage__poster-plate" role="button" aria-label={`Play ${clip.title}`}>
            <img
              src={clip.poster}
              alt={clip.title}
              className="stage__poster-img"
              loading="lazy"
              decoding="async"
            />
            <div className="stage__poster-overlay">
              <button
                type="button"
                className="stage__poster-playbtn"
                aria-label={`Play ${clip.title}`}
                onClick={(e) => {
                  e.stopPropagation();
                  setHasActivated(true);
                }}
              >
                <Icon name="play" />
              </button>
              <span className="stage__poster-badge mono t-overline">
                {clip.runtime} · {cuts.length} cuts
              </span>
            </div>
          </div>
        ) : failed ? (
          <div className="stage__fail">
            <p className="t-overline hot">Plate unavailable</p>
            <p className="t-small dim">
              {clip.src} did not load. Check that the source media file is present.
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
                <img
                  src={clip.poster}
                  alt=""
                  className="stage__poster-img stage__poster-img--blur"
                  aria-hidden="true"
                />
                <span className="t-overline dim" style={{ position: "relative", zIndex: 3 }}>
                  Loading plate…
                </span>
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

      {soundControl && !transport ? (
        <div className="stage__sound-control-wrap">
          <button
            className="stage__sound-control"
            onClick={toggleSound}
            aria-label={muted || volume === 0 ? `Turn ${soundLabel.toLowerCase()} on` : `Mute ${soundLabel.toLowerCase()} (${soundPercent}%)`}
            aria-pressed={!muted && volume > 0}
            type="button"
          >
            <Icon name={soundIconName} />
            <span>{soundLabel} {muted || volume === 0 ? "off" : `${soundPercent}%`}</span>
          </button>
          <div className="stage__sound-sliderwrap">
            <input
              type="range"
              min={0}
              max={1}
              step={0.05}
              value={muted ? 0 : volume}
              onChange={onVolumeSliderChange}
              aria-label="Adjust audio volume"
              className="stage__volume-slider"
              style={{ "--fill": `${soundPercent}%` }}
            />
          </div>
        </div>
      ) : null}

      {transport ? (
        <div
          className={`stage__transport ${isFullscreen ? "stage__transport--fullscreen" : ""} ${isFullscreen && !controlsVisible ? "stage__transport--hidden" : ""}`}
          onMouseEnter={() => setControlsVisible(true)}
        >
          <div className="stage__row">
            <button
              className="tbtn tbtn--primary"
              onClick={toggle}
              aria-label={playing ? "Pause (Space)" : "Play (Space)"}
              title={playing ? "Pause (Space)" : "Play (Space)"}
              type="button"
            >
              <Icon name={playing ? "pause" : "play"} />
            </button>

            <button
              className="tbtn"
              onClick={restart}
              aria-label="Restart (R)"
              title="Restart from beginning (R)"
              type="button"
            >
              <Icon name="restart" />
            </button>

            <button
              className="tbtn"
              onClick={jumpPrevCut}
              aria-label="Previous shot ([)"
              title="Previous shot ([)"
              type="button"
            >
              <Icon name="prev" />
            </button>

            <button
              className="tbtn"
              onClick={jumpNextCut}
              aria-label="Next shot (])"
              title="Next shot (])"
              type="button"
            >
              <Icon name="next" />
            </button>

            {/* Adjustable Volume Control Wrap */}
            <div className="stage__volume-wrap" onMouseEnter={resetControlsTimer}>
              <button
                className="tbtn stage__vol-btn"
                onClick={toggleSound}
                aria-label={muted || volume === 0 ? "Unmute audio (M)" : `Mute audio (${soundPercent}%) (M)`}
                title={muted || volume === 0 ? "Unmute audio (M)" : `Mute audio (${soundPercent}%) (M)`}
                type="button"
                data-on={!muted && volume > 0}
              >
                <Icon name={soundIconName} />
              </button>
              <div className="stage__volume-sliderwrap">
                <input
                  type="range"
                  min={0}
                  max={1}
                  step={0.05}
                  value={muted ? 0 : volume}
                  onChange={onVolumeSliderChange}
                  aria-label="Adjust audio volume (Up/Down arrow)"
                  className="stage__volume-slider"
                  style={{ "--fill": `${soundPercent}%` }}
                />
                <span className="stage__volume-val mono">{soundPercent}%</span>
              </div>
            </div>

            <div className="stage__scrubwrap">
              <input
                type="range"
                min={0}
                max={total - 1}
                step={1}
                value={Math.min(frame, total - 1)}
                onChange={onScrub}
                aria-label="Scrub clip timeline"
                className="stage__scrub"
                style={{ "--fill": `${(frame / (total - 1)) * 100}%` }}
              />
              <div className="stage__ticks" aria-hidden="true">
                {cuts.map((c, i) => (
                  <span
                    key={`${c.start}-${i}`}
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
              onClick={() => setShowShortcuts((v) => !v)}
              aria-label="Shortcuts guide (?)"
              title="Keyboard shortcuts (?)"
              type="button"
            >
              <Icon name="keyboard" />
            </button>

            <button
              className="tbtn"
              onClick={toggleFullscreen}
              aria-label={isFullscreen ? "Exit fullscreen (F / Esc)" : "Fullscreen (F)"}
              title={isFullscreen ? "Exit fullscreen (F / Esc)" : "Fullscreen (F)"}
              type="button"
            >
              <Icon name={isFullscreen ? "compress" : "expand"} />
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

      {/* Keyboard Shortcuts Modal */}
      {showShortcuts && (
        <div
          className="stage__shortcuts-modal"
          onClick={() => setShowShortcuts(false)}
          role="dialog"
          aria-label="Keyboard shortcuts"
        >
          <div
            className="stage__shortcuts-card"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="stage__shortcuts-header">
              <div className="stage__shortcuts-title-wrap">
                <span className="dot dot--live" style={{ color: "var(--red-bright)" }} />
                <h4 className="stage__shortcuts-title">Pit Wall Cinema Shortcuts</h4>
              </div>
              <button
                className="tbtn"
                type="button"
                onClick={() => setShowShortcuts(false)}
                aria-label="Close shortcuts guide"
              >
                <Icon name="close" />
              </button>
            </div>

            <div className="stage__shortcuts-grid">
              <div className="stage__shortcut-row">
                <span className="stage__shortcut-keys">
                  <kbd>Space</kbd> / <kbd>K</kbd>
                </span>
                <span className="stage__shortcut-desc">Play / Pause playback</span>
              </div>
              <div className="stage__shortcut-row">
                <span className="stage__shortcut-keys">
                  <kbd>F</kbd>
                </span>
                <span className="stage__shortcut-desc">Toggle Fullscreen mode</span>
              </div>
              <div className="stage__shortcut-row">
                <span className="stage__shortcut-keys">
                  <kbd>M</kbd>
                </span>
                <span className="stage__shortcut-desc">Mute / Unmute engine audio</span>
              </div>
              <div className="stage__shortcut-row">
                <span className="stage__shortcut-keys">
                  <kbd>↑</kbd> / <kbd>↓</kbd>
                </span>
                <span className="stage__shortcut-desc">Adjust volume by ±10%</span>
              </div>
              <div className="stage__shortcut-row">
                <span className="stage__shortcut-keys">
                  <kbd>←</kbd> / <kbd>→</kbd> or <kbd>J</kbd> / <kbd>L</kbd>
                </span>
                <span className="stage__shortcut-desc">Seek 2 seconds back / forward</span>
              </div>
              <div className="stage__shortcut-row">
                <span className="stage__shortcut-keys">
                  <kbd>[</kbd> / <kbd>]</kbd>
                </span>
                <span className="stage__shortcut-desc">Jump to Previous / Next Shot</span>
              </div>
              <div className="stage__shortcut-row">
                <span className="stage__shortcut-keys">
                  <kbd>R</kbd> or <kbd>0</kbd>
                </span>
                <span className="stage__shortcut-desc">Restart from Frame 0</span>
              </div>
              <div className="stage__shortcut-row">
                <span className="stage__shortcut-keys">
                  <kbd>?</kbd> / <kbd>H</kbd>
                </span>
                <span className="stage__shortcut-desc">Toggle this Shortcuts Guide</span>
              </div>
              <div className="stage__shortcut-row">
                <span className="stage__shortcut-keys">
                  <kbd>Esc</kbd>
                </span>
                <span className="stage__shortcut-desc">Exit Fullscreen / Close modal</span>
              </div>
            </div>

            <div className="stage__shortcuts-footer">
              <span className="t-caption dim-2">
                In full screen, controls auto-fade after 2.5s. Move mouse or tap any key to reveal.
              </span>
              <button
                type="button"
                className="btn btn--ghost"
                style={{ padding: "5px 14px", fontSize: "0.75rem" }}
                onClick={() => setShowShortcuts(false)}
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

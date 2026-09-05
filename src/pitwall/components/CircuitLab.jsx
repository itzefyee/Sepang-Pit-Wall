/**
 * Circuit intelligence: the surveyed map, the corner-by-corner briefing and the
 * elevation profile.
 *
 * The map is not an illustration. Every coordinate comes from the 1386-point
 * OpenStreetMap survey, scaled to the homologated 5543 m, and the corner markers
 * sit on the apex index the registration pipeline resolved.
 */

import { useEffect, useMemo, useRef, useState } from "react";

import { CIRCUIT, DRS_ZONES, GEO, LAP_PHYSICS, SECTORS, TURNS } from "../data/circuit.js";
import { useInView, usePrefersReducedMotion } from "../hooks.js";
import { ElevationChart } from "./charts.jsx";
import {
  MAP,
  SECTOR_COLOURS,
  cornerLabelAt,
  lapPath,
  pitLanePath,
  rangePath,
  startLine
} from "./circuitMap.js";
import { Panel, Pill, Reveal, Section, Segmented } from "./ui.jsx";

function Meter({ label, value, max = 5, colour = "var(--red)" }) {
  return (
    <div className="meter">
      <span className="meter__l t-overline">{label}</span>
      <span className="meter__pips" role="img" aria-label={`${value} out of ${max}`}>
        {Array.from({ length: max }, (_, i) => (
          <i key={i} data-on={i < value} style={{ background: i < value ? colour : undefined }} />
        ))}
      </span>
    </div>
  );
}

function TrackMap({ active, onPick, overlay }) {
  const [hostRef, seen] = useInView({ threshold: 0.15, rootMargin: "80px" });
  const lapRef = useRef(null);
  const reduced = usePrefersReducedMotion();

  const lap = useMemo(() => lapPath(2), []);
  const pit = useMemo(() => pitLanePath(), []);
  const sf = useMemo(() => startLine(), []);
  const sectorPaths = useMemo(
    () => SECTORS.map((s) => ({ id: s.id, d: rangePath(s.startIdx, s.endIdx, 2) })),
    []
  );
  const drsPaths = useMemo(
    () => DRS_ZONES.map((z) => ({ id: z.id, name: z.name, d: rangePath(z.start, z.end, 2) })),
    []
  );
  const markers = useMemo(
    () => TURNS.map((t) => ({ turn: t, ...cornerLabelAt(t.apex, 27) })),
    []
  );

  // draw the lap on first view
  useEffect(() => {
    const el = lapRef.current;
    if (!el || !seen) return;
    if (reduced) {
      el.style.strokeDasharray = "none";
      el.style.strokeDashoffset = "0";
      return;
    }
    const len = el.getTotalLength();
    el.style.strokeDasharray = `${len}`;
    el.style.strokeDashoffset = `${len}`;
    el.style.transition = "stroke-dashoffset 1700ms cubic-bezier(0.16,1,0.30,1)";
    // next frame, so the transition has a starting value to animate from
    const id = requestAnimationFrame(() => {
      el.style.strokeDashoffset = "0";
    });
    return () => cancelAnimationFrame(id);
  }, [seen, reduced]);

  return (
    <div className="map" ref={hostRef}>
      <svg
        viewBox={MAP.viewBox}
        className="map__svg"
        role="img"
        aria-label={`Map of ${CIRCUIT.name}, ${CIRCUIT.lengthKm} km, ${CIRCUIT.turns} turns`}
      >
        <defs>
          <filter id="markerGlow" x="-60%" y="-60%" width="220%" height="220%">
            <feGaussianBlur stdDeviation="3.4" result="b" />
            <feMerge>
              <feMergeNode in="b" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>

        {/* pit lane behind everything */}
        <path
          d={pit}
          fill="none"
          stroke="rgba(173,189,203,0.34)"
          strokeWidth="3"
          strokeDasharray="7 6"
          strokeLinecap="round"
        />

        {/* run-off and kerb casing */}
        <path d={lap} fill="none" stroke="rgba(47,191,113,0.1)" strokeWidth="30" strokeLinejoin="round" />
        <path d={lap} fill="none" stroke="#0b1016" strokeWidth="19" strokeLinejoin="round" />

        {/* sector tint */}
        {overlay === "sectors"
          ? sectorPaths.map((s) => (
              <path
                key={s.id}
                d={s.d}
                fill="none"
                stroke={SECTOR_COLOURS[s.id]}
                strokeWidth="13"
                strokeLinecap="butt"
                opacity="0.5"
              />
            ))
          : null}

        {/* DRS tint */}
        {overlay === "drs"
          ? drsPaths.map((z) => (
              <path
                key={z.id}
                d={z.d}
                fill="none"
                stroke="#2fbf71"
                strokeWidth="13"
                strokeLinecap="butt"
                opacity="0.55"
              />
            ))
          : null}

        {/* the surface, drawn on entry */}
        <path
          ref={lapRef}
          d={lap}
          fill="none"
          stroke="rgba(216,31,38,0.92)"
          strokeWidth="3.2"
          strokeLinejoin="round"
        />

        {/* start / finish */}
        <line
          x1={sf.x1}
          y1={sf.y1}
          x2={sf.x2}
          y2={sf.y2}
          stroke="#eef2f6"
          strokeWidth="4"
          strokeLinecap="butt"
        />

        {/* corner markers */}
        {markers.map(({ turn, apex, label }) => {
          const on = active === turn.id;
          return (
            <g
              key={turn.id}
              className="map__marker"
              data-on={on}
              onClick={() => onPick(turn.id)}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  onPick(turn.id);
                }
              }}
              tabIndex={0}
              role="button"
              aria-label={`${turn.name}, ${turn.kind}, ${turn.radiusM} metre radius`}
            >
              <line
                x1={apex[0]}
                y1={apex[1]}
                x2={label[0]}
                y2={label[1]}
                stroke={on ? "#ff3b42" : "rgba(173,189,203,0.4)"}
                strokeWidth="1.2"
              />
              <circle
                cx={label[0]}
                cy={label[1]}
                r="13"
                fill={on ? "#d81f26" : "#0d131b"}
                stroke={on ? "#ff9ba0" : "rgba(173,189,203,0.55)"}
                strokeWidth="1.6"
                filter={on ? "url(#markerGlow)" : undefined}
              />
              <text
                x={label[0]}
                y={label[1] + 4.5}
                textAnchor="middle"
                fontSize="13"
                fontWeight="700"
                fill={on ? "#fff" : "#adbdcb"}
                fontFamily="var(--font-head)"
              >
                {turn.id}
              </text>
              <circle cx={apex[0]} cy={apex[1]} r={on ? 5 : 3} fill={on ? "#ff3b42" : "#e9eff5"} />
            </g>
          );
        })}

        <text
          x={MAP.width - 14}
          y={MAP.height - 14}
          textAnchor="end"
          fontSize="12"
          fill="rgba(173,189,203,0.5)"
          fontFamily="var(--font-mono)"
        >
          1386 survey points · 4 m spacing · {CIRCUIT.lengthM} m
        </text>
      </svg>
    </div>
  );
}

function TurnDetail({ turn }) {
  return (
    <div className="turn">
      <div className="turn__head">
        <div>
          <span className="t-overline hot">
            {turn.label} · Sector {turn.sector} · {turn.sM} m
          </span>
          <h3 className="t-h2 turn__name">{turn.kind}</h3>
        </div>
        <Pill tone={turn.dir === "left" ? "teal" : "red"}>{turn.dir}</Pill>
      </div>

      <div className="turn__grid">
        <div>
          <span className="t-overline dim-2">Apex speed</span>
          <b className="mono">{turn.apexKph} kph</b>
        </div>
        <div>
          <span className="t-overline dim-2">Brake from</span>
          <b className="mono">{turn.brakeFromKph} kph</b>
        </div>
        <div>
          <span className="t-overline dim-2">Gear</span>
          <b className="mono">{turn.gear}</b>
        </div>
        <div>
          <span className="t-overline dim-2">Radius</span>
          <b className="mono">{turn.radiusM} m</b>
        </div>
        <div>
          <span className="t-overline dim-2">Heading change</span>
          <b className="mono">{turn.headingChangeDeg}°</b>
        </div>
        <div>
          <span className="t-overline dim-2">Corner length</span>
          <b className="mono">{turn.lengthM} m</b>
        </div>
      </div>

      <div className="turn__meters">
        <Meter label="Difficulty" value={turn.difficulty} />
        <Meter label="Overtaking" value={turn.overtaking} colour="var(--green)" />
        <Meter
          label="Tyre load"
          value={Math.round(turn.tyreLoad * 5)}
          colour="var(--amber)"
        />
      </div>

      <p className="turn__coach t-body">{turn.coach}</p>

      <div className="turn__foot">
        <p className="t-small">
          <span className="t-overline hot">Watch </span>
          <span className="dim">{turn.watch}</span>
        </p>
        <p className="t-caption dim-2">
          Survey note: {turn.note} · loads the {turn.tyre.toLowerCase()}
        </p>
      </div>
    </div>
  );
}

export function CircuitLab() {
  const [active, setActive] = useState(1);
  const [overlay, setOverlay] = useState("sectors");
  const [viewMode, setViewMode] = useState("map");
  const turn = TURNS.find((t) => t.id === active) ?? TURNS[0];

  return (
    <Section
      id="circuit"
      no="02 / Circuit intelligence"
      title="Fifteen corners, one of which decides everything"
      lede="Select a corner to inspect survey radii, braking points, apex speeds, and tyre load demands."
      aside={
        <div style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
          <Segmented
            label="View perspective"
            value={viewMode}
            onChange={setViewMode}
            options={[
              { value: "map", label: "2D Survey" },
              { value: "aerial", label: "3D Aerial" },
              { value: "pit", label: "3D Pits" }
            ]}
          />
          {viewMode === "map" ? (
            <Segmented
              label="Map overlay"
              value={overlay}
              onChange={setOverlay}
              options={[
                { value: "sectors", label: "Sectors" },
                { value: "drs", label: "DRS" },
                { value: "clean", label: "Clean" }
              ]}
            />
          ) : null}
        </div>
      }
    >
      <div className="circuit">
        <Reveal className="circuit__map">
          <Panel
            title={viewMode === "map" ? "Surveyed layout" : viewMode === "aerial" ? "3D Reconstructed Loop" : "3D Pit Straight & Gantry"}
            meta={`${CIRCUIT.lengthKm} km · ${CIRCUIT.direction}`}
            note={viewMode === "map"
              ? `GPS-surveyed loop scaled to homologated ${CIRCUIT.lengthM} m.`
              : "Physics-based 3D render from Blender camera rigs."}
          >
            {viewMode === "map" ? (
              <>
                <TrackMap active={active} onPick={setActive} overlay={overlay} />
                <div className="circuit__legend">
                  {overlay === "sectors"
                    ? SECTORS.map((s) => (
                        <span className="chart__key" key={s.id}>
                          <i style={{ background: SECTOR_COLOURS[s.id] }} />
                          {s.name} · {s.lengthM} m
                        </span>
                      ))
                    : null}
                  {overlay === "drs"
                    ? DRS_ZONES.map((z) => (
                        <span className="chart__key" key={z.id}>
                          <i style={{ background: "#2fbf71" }} />
                          {z.name} · {z.lengthM} m · worth {z.worthS.toFixed(2)} s
                        </span>
                      ))
                    : null}
                  <span className="chart__key">
                    <i style={{ background: "rgba(173,189,203,0.5)" }} />
                    Pit lane · {CIRCUIT.pitOffsetM} m offset
                  </span>
                </div>
              </>
            ) : viewMode === "aerial" ? (
              <div className="circuit__3dview">
                <img
                  src="/assets/img/sepang_shots/aerial.png"
                  alt="3D Reconstructed Circuit Aerial View"
                  className="circuit__3dimg"
                />
                <div className="circuit__3dcaption">
                  <span className="t-overline hot">Aerial Survey (Z: 850m)</span>
                  <p className="t-small dim" style={{ margin: "3px 0 0" }}>
                    Twin straights, Turn 1 hairpin, and Turn 15 hairpin. Homologated 5,543 m loop.
                  </p>
                </div>
              </div>
            ) : (
              <div className="circuit__3dview">
                <img
                  src="/assets/img/sepang_shots/pit_overview.png"
                  alt="3D Sepang Pit Complex and Grandstands"
                  className="circuit__3dimg"
                />
                <div className="circuit__3dcaption">
                  <span className="t-overline hot">Pit & Grandstand Complex</span>
                  <p className="t-small dim" style={{ margin: "3px 0 0" }}>
                    Twin grandstands, pit garages, start gantry, and DRS Zone 1.
                  </p>
                </div>
              </div>
            )}
          </Panel>
        </Reveal>

        <Reveal className="circuit__detail" delay={80}>
          <Panel title="Corner briefing" meta={`${turn.label} of ${CIRCUIT.turns}`}>
            <div className="circuit__picker" role="tablist" aria-label="Corners">
              {TURNS.map((t) => (
                <button
                  key={t.id}
                  type="button"
                  role="tab"
                  aria-selected={t.id === active}
                  className="circuit__pick"
                  onClick={() => setActive(t.id)}
                >
                  {t.id}
                </button>
              ))}
            </div>
            <TurnDetail turn={turn} />
          </Panel>
        </Reveal>
      </div>

      <div className="grid cols-3" style={{ marginTop: "var(--s6)" }}>
        {SECTORS.map((s, i) => (
          <Reveal key={s.id} delay={i * 70}>
            <Panel title={s.name} meta={`${s.lengthM} m · ${s.typicalTimeS} s`}>
              <p className="t-small" style={{ marginBottom: "var(--s3)" }}>
                {s.character}
              </p>
              <div className="sector__meta">
                <span className="t-caption dim-2">
                  {s.span} · turns {s.turns.join(", ")}
                </span>
                <Pill tone={s.drainage.startsWith("Poor") ? "fail" : s.drainage === "Good" ? "pass" : "warn"}>
                  Drainage {s.drainage.split(" ")[0]}
                </Pill>
              </div>
              <div
                className="sector__bar"
                style={{ background: SECTOR_COLOURS[s.id] }}
                aria-hidden="true"
              />
            </Panel>
          </Reveal>
        ))}
      </div>

      <Reveal delay={60} className="circuit__elev">
        <Panel
          title="Elevation along the lap"
          meta={`${CIRCUIT.elevationSpanM} m span · SRTM 30 m`}
          note="The climb into Turn 7 and 8 and the drop away from Turn 9 are the reason sector 2 punishes tyres and pools water. Contaminated by grandstand roofs near the pit straight, so the profile is smoothed over 100 m rather than trusted point by point."
        >
          <ElevationChart
            profile={GEO.elevationProfile}
            corners={TURNS}
            activeTurn={active}
            onPick={setActive}
          />
        </Panel>
      </Reveal>

      <Reveal delay={80} className="circuit__table">
        <Panel
          title="Every corner, measured"
          meta={`${CIRCUIT.turns} corners resolved automatically`}
          note="Turn numbering is not hand-entered: the reference circuit map is registered onto the centreline and its 15 circled labels are detected as ring-shaped blobs, then ordered along the lap. 95.8% of centreline samples land inside the reference track band."
        >
          <div className="tbl-scroll">
            <table className="tbl">
              <thead>
                <tr>
                  <th>Turn</th>
                  <th className="r">Distance</th>
                  <th className="r">Radius</th>
                  <th>Direction</th>
                  <th className="r">Heading</th>
                  <th className="r">Apex</th>
                  <th className="r">Gear</th>
                  <th>Character</th>
                </tr>
              </thead>
              <tbody>
                {TURNS.map((t) => (
                  <tr
                    key={t.id}
                    className={t.id === active ? "is-hero" : undefined}
                    onClick={() => setActive(t.id)}
                    style={{ cursor: "pointer" }}
                  >
                    <td className="pos">{t.label}</td>
                    <td className="r">{t.sM} m</td>
                    <td className="r">{t.radiusM} m</td>
                    <td className="dim">{t.dir}</td>
                    <td className="r">{t.headingChangeDeg}°</td>
                    <td className="r">{t.apexKph} kph</td>
                    <td className="r">{t.gear}</td>
                    <td className="dim">{t.kind}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Panel>
      </Reveal>

      <div className="grid cols-4" style={{ marginTop: "var(--s6)" }}>
        <Reveal>
          <Panel title="Qualifying lap" lit={false}>
            <p className="stat__v mono">1:30.076</p>
            <p className="t-caption dim">
              Calibration target was the 2017 pole, {LAP_PHYSICS.qualifyingTarget} s.
            </p>
          </Panel>
        </Reveal>
        <Reveal delay={60}>
          <Panel title="Top speed" lit={false}>
            <p className="stat__v mono">{LAP_PHYSICS.topSpeedKph} kph</p>
            <p className="t-caption dim">
              Back straight, {CIRCUIT.backStraightM} m, DRS open.
            </p>
          </Panel>
        </Reveal>
        <Reveal delay={120}>
          <Panel title="DRS worth" lit={false}>
            <p className="stat__v mono">{LAP_PHYSICS.drsWorthS} s</p>
            <p className="t-caption dim">
              Both zones over one lap. Zero once the track is wet.
            </p>
          </Panel>
        </Reveal>
        <Reveal delay={180}>
          <Panel title="Fuel effect" lit={false}>
            <p className="stat__v mono">{LAP_PHYSICS.fuelEffectSPerKg} s/kg</p>
            <p className="t-caption dim">
              One of only two calibrated parameters in the lap model.
            </p>
          </Panel>
        </Reveal>
      </div>
    </Section>
  );
}

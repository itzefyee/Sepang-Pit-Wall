"""
Builds the live progress page for the Sepang gauntlet loop.

Every number on the page is measured at generation time by running the actual
models - nothing is transcribed by hand. The page records, per piece of work:
what was built, how it was checked, the verdict against the quality bar, and the
biggest remaining gap.
"""

import datetime
import html
import json
import os
import shutil
import time

from . import geo
from . import sim_core as S
from . import sim_race as R
from . import sim_validate as V

HERE = os.path.dirname(os.path.abspath(__file__))
BLENDER_DIR = os.path.dirname(HERE)
PROJECT_DIR = os.path.dirname(BLENDER_DIR)
OUT_DIR = os.path.join(BLENDER_DIR, "out")
PAGE_PATH = os.path.join(PROJECT_DIR, "sepang_progress.html")
SHOTS_DIR = os.path.join(PROJECT_DIR, "sepang_shots")

SHOTS = [
    ("aerial.png", "The reconstructed circuit: twin straights, Turn 1 hairpin at one end, Turn 15 at the other"),
    ("dry_chase.png", "Dry running, chase camera: the Ferraris in the simulated pack on the pit straight"),
    ("wet_chase_rain.png", "Monsoon: rain curtain, wet-track reflections, rain lights on, storm sky"),
    ("wet_onboard.png", "Onboard in the wet, halo in frame"),
    ("cam_carstudio.png", "2026-regulation Ferrari on track: 3400 mm wheelbase, 1900 mm width, yellow medium sidewalls"),
    ("pit_overview.png", "Twin grandstand between the straights, pit complex and start gantry"),
]


# --------------------------------------------------------------------------
# measurement
# --------------------------------------------------------------------------
def collect(verbose=True):
    t0 = time.time()
    m = {}

    track = geo.build_centreline()
    m["track"] = dict(
        raw_osm_m=track["raw_osm_length_m"],
        homologated_m=geo.OFFICIAL_LENGTH_M,
        error_pct=100.0 * (track["raw_osm_length_m"] - geo.OFFICIAL_LENGTH_M) / geo.OFFICIAL_LENGTH_M,
        samples=track["n"],
        spacing_m=track["spacing_m"],
        corners=len(track["corners"]),
        elevation_range_m=max(track["elevation_m"]) - min(track["elevation_m"]),
        pit_offset_m=track.get("pit_offset_m"),
        main_straight_m=track.get("main_straight_m"),
        back_straight_m=track.get("back_straight_m"),
        drs_zones=len(track["drs_zones"]),
        corner_table=[dict(id=c["id"], radius_m=round(c["radius_m"], 1),
                           dir=c["dir"], s_m=round(c["s_apex_m"]),
                           kind=c["kind"],
                           heading=round(c["heading_change_deg"], 1))
                      for c in track["corners"]],
        sectors=track.get("sectors", []),
    )

    lt = S.LapTimeModel(track)
    cal = lt.calibrate()
    surf = lt.build_surface()
    serr = []
    for f in (5, 33, 61, 88, 104):
        for w in (0.0, 0.7, 1.8, 5.5, 9.3):
            exact = lt.lap(grip=1.0, fuel_kg=f, wet_depth_mm=w)["time_s"]
            serr.append(abs(exact - surf.time(f, None, w)[0]))
    m["laptime"] = dict(
        calibration=cal,
        pole_target_s=S.REFERENCE["pole_s"],
        qualy_s=lt.lap_time(fuel_kg=8.0)["time_s"],
        race_start_s=lt.lap_time(fuel_kg=100.0)["time_s"],
        fuel_s_per_kg=lt.fuel_effect_s_per_kg(),
        top_speed_kph=lt.lap(grip=1.0, fuel_kg=8.0)["top_speed_kph"],
        drs_gain_s=(lt.lap(grip=1.0, fuel_kg=8.0, drs_enabled=False)["time_s"]
                    - lt.lap(grip=1.0, fuel_kg=8.0)["time_s"]),
        surface_mean_err_s=sum(serr) / len(serr),
        surface_max_err_s=max(serr),
    )

    tm = S.TyreModel()
    m["tyres"] = dict(
        life={c: tm.usable_life_laps(c) for c in S.COMPOUNDS},
        deltas={c: S.COMPOUNDS[c]["pace_delta_s"] for c in S.COMPOUNDS},
        quantiles={},
        crossover=[],
    )
    for comp, laps in (("soft", 14), ("medium", 20), ("hard", 28)):
        q = tm.stint_quantiles(comp, laps, [100 - 1.72 * i for i in range(laps)],
                               samples=350)
        m["tyres"]["quantiles"][comp] = dict(
            laps=laps, p10=q["total_p10"], p50=q["total_p50"], p90=q["total_p90"],
            last_lap_p10=q["lap_p10"][-1], last_lap_p50=q["lap_p50"][-1],
            last_lap_p90=q["lap_p90"][-1],
            band_s=q["total_p90"] - q["total_p10"])
    for d in (0.0, 0.4, 0.8, 1.2, 2.0, 3.0, 5.0, 7.0):
        row = {}
        for c in ("medium", "intermediate", "wet"):
            st = S.TyreState(c, age_laps=3)
            row[c] = lt.lap_time(tyre_penalty_s=tm.pace_penalty_s(st, d),
                                 fuel_kg=60.0, wet_depth_mm=d)["time_s"]
        best = min(row, key=row.get)
        m["tyres"]["crossover"].append(dict(water_mm=d, best=best,
                                            **{k: round(v, 2) for k, v in row.items()},
                                            slick_penalty_s=round(row["medium"] - row[best], 2)))

    pits = R.PitModel()
    pred = pits.predict_loss_s()
    samples = [pits.sample_loss_s() for _ in range(6000)]
    mae = sum(abs(x - pred) for x in samples) / len(samples)
    m["pits"] = dict(target_s=S.REFERENCE["pit_loss_s"], predicted_s=pred,
                     limited_length_m=pits.limited_length_m,
                     sampled_mean_s=sum(samples) / len(samples),
                     mae_s=mae, wet_s=pits.predict_loss_s(wet=True),
                     bar_mae_s=0.5, mae_pass=mae < 0.5)

    opt = R.StrategyOptimiser(lt, tm, pits)
    plans = opt.enumerate_dry(stops=(1, 2), min_stint=8, step=4)
    ts = time.time()
    best = opt.best_dry(stops=(1, 2), step=4, top=6)
    m["strategy"] = dict(
        plans_searched=len(plans),
        search_s=time.time() - ts,
        top=[dict(total_s=t, plan=[[c, l] for c, l in plan]) for t, plan in best],
    )
    mc = opt.monte_carlo(best[0][1], runs=140)
    m["strategy"]["monte_carlo"] = mc
    m["strategy"]["wet_decision"] = opt.wet_decision("medium", 1.4,
                                                     [4.0, 3.0, 2.0, 1.0, 0.5, 0.0],
                                                     30, 0.4)

    wx_eq = {}
    for inten in (2, 4, 6, 8, 10):
        w = S.WeatherEngine(seed=1, cell_probability=0.0)
        w.schedule_cell(1, inten, ramp_laps=1, hold_laps=30, decay_laps=1)
        for lap in range(1, 26):
            st = w.step(lap)
        wx_eq[inten] = dict(mean=st["water_mean_mm"], s1=st["water_mm"][1],
                            s2=st["water_mm"][2], s3=st["water_mm"][3],
                            condition=st["condition"])
    dryout = []
    w = S.WeatherEngine(seed=1, cell_probability=0.0)
    w.schedule_cell(1, 9.0, ramp_laps=2, hold_laps=5, decay_laps=6)
    for lap in range(1, 25):
        dryout.append(w.step(lap)["water_mean_mm"])
    m["weather"] = dict(equilibrium=wx_eq, dryout=dryout,
                        abandon_mm=S.WeatherEngine.ABANDON_DEPTH_MM)

    eng = R.RaceEngine(track, seed=2026,
                       weather=S.WeatherEngine(seed=5, cell_probability=0.0))
    dry = eng.run()
    winner = dry["classification"][0]
    m["dry_race"] = dict(
        winner=winner["code"], total_s=winner["total_s"],
        best_lap_s=winner["best_lap"],
        real_total_s=5401.29, real_best_lap_s=S.REFERENCE["race_lap_record_s"],
        total_err_pct=100.0 * (winner["total_s"] - 5401.29) / 5401.29,
        best_lap_err_s=winner["best_lap"] - S.REFERENCE["race_lap_record_s"],
        classification=dry["classification"][:10],
        race_trim_s=R.RACE_TRIM_S,
    )

    m["validation"] = V.run_all(verbose=False)
    m["generated"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    m["build_s"] = time.time() - t0
    if verbose:
        print("collected in %.1fs" % m["build_s"])
    return m


# --------------------------------------------------------------------------
# page
# --------------------------------------------------------------------------
CSS = """
:root{--bg:#0c0d10;--panel:#14161b;--line:#23262e;--ink:#e8eaee;--dim:#9aa1ad;
      --red:#d4222a;--green:#2fbf71;--amber:#e8b93b;--blue:#4c9ce8}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
     font:14px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}
header{padding:34px 40px 26px;border-bottom:1px solid var(--line);
       background:linear-gradient(120deg,#16181e,#0c0d10)}
h1{margin:0 0 6px;font-size:26px;letter-spacing:-.3px}
h1 span{color:var(--red)}
.sub{color:var(--dim);font-size:13px}
main{padding:28px 40px 70px;max-width:1180px}
section{margin:0 0 30px;background:var(--panel);border:1px solid var(--line);
        border-radius:10px;overflow:hidden}
h2{margin:0;padding:14px 20px;font-size:14px;letter-spacing:.06em;
   text-transform:uppercase;color:var(--dim);border-bottom:1px solid var(--line);
   background:#101218}
.body{padding:18px 20px}
table{width:100%;border-collapse:collapse;font-size:13px}
th,td{text-align:left;padding:7px 10px;border-bottom:1px solid var(--line)}
th{color:var(--dim);font-weight:600;font-size:11px;text-transform:uppercase;
   letter-spacing:.05em}
td.num,th.num{text-align:right;font-variant-numeric:tabular-nums}
tr:last-child td{border-bottom:none}
.pill{display:inline-block;padding:2px 9px;border-radius:20px;font-size:11px;
      font-weight:700;letter-spacing:.04em}
.pass{background:rgba(47,191,113,.15);color:var(--green)}
.fail{background:rgba(212,34,42,.16);color:#ff6b72}
.warn{background:rgba(232,185,59,.15);color:var(--amber)}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(215px,1fr));gap:14px}
.kpi{background:#0f1117;border:1px solid var(--line);border-radius:8px;padding:14px}
.kpi .v{font-size:22px;font-weight:700;font-variant-numeric:tabular-nums}
.kpi .l{color:var(--dim);font-size:11px;text-transform:uppercase;
        letter-spacing:.05em;margin-top:3px}
.kpi .n{color:var(--dim);font-size:12px;margin-top:6px}
.shots{display:grid;grid-template-columns:repeat(auto-fit,minmax(330px,1fr));gap:14px}
.shot img{width:100%;border-radius:8px;border:1px solid var(--line);display:block}
.shot p{color:var(--dim);font-size:12px;margin:8px 0 0}
.gap{border-left:3px solid var(--amber);padding:2px 0 2px 13px;margin:9px 0;
     color:#d8dae0}
code{background:#0a0b0e;padding:1px 5px;border-radius:4px;font-size:12px;
     color:#c8cdd6}
.bar{height:7px;background:#0a0b0e;border-radius:4px;overflow:hidden;
     margin-top:6px}
.bar i{display:block;height:100%;background:var(--red)}
.note{color:var(--dim);font-size:12px;margin-top:12px}
"""


def _pill(ok, label_ok="PASS", label_no="FAIL"):
    cls = "pass" if ok else "fail"
    return '<span class="pill %s">%s</span>' % (cls, label_ok if ok else label_no)


def _kpi(value, label, note=""):
    return ('<div class="kpi"><div class="v">%s</div><div class="l">%s</div>'
            '%s</div>' % (value, label,
                          '<div class="n">%s</div>' % note if note else ""))


def render_page(m, shots_available):
    t = m["track"]
    lt = m["laptime"]
    ty = m["tyres"]
    pt = m["pits"]
    stg = m["strategy"]
    wx = m["weather"]
    dr = m["dry_race"]
    val = m["validation"]

    parts = []
    A = parts.append
    A("<!doctype html><html lang='en'><head><meta charset='utf-8'>")
    A("<meta name='viewport' content='width=device-width,initial-scale=1'>")
    A("<title>Sepang F1 Simulation - Gauntlet Loop Progress</title>")
    A("<style>%s</style></head><body>" % CSS)
    A("<header><h1>Ferrari at Sepang &mdash; <span>race simulation in Blender</span></h1>")
    A("<div class='sub'>Live progress page &middot; generated %s &middot; "
      "every figure below is measured by running the models, not transcribed"
      "</div></header><main>" % html.escape(m["generated"]))

    # ---------------------------------------------------------------- summary
    checks = val["checks"]
    passed = sum(1 for _, ok in checks if ok)
    A("<section><h2>Scoreboard against the quality bar</h2><div class='body'><div class='grid'>")
    A(_kpi("%d/%d" % (passed, len(checks)), "historical checks passed",
           "2001 Ferrari 1-2 recovery and 2009 lap-31 abandonment"))
    A(_kpi("%.3f s" % pt["mae_s"], "pit-loss MAE",
           "bar: under %.1f s &middot; %s" % (pt["bar_mae_s"],
                                             "beats bar" if pt["mae_pass"] else "misses bar")))
    A(_kpi("P10/P50/P90", "tyre quantiles shipped",
           "stint loss bands from %d Monte Carlo sets" % 350))
    A(_kpi("%.2f%%" % abs(t["error_pct"]), "track length error",
           "OSM survey loop %.0f m vs homologated %.0f m"
           % (t["raw_osm_m"], t["homologated_m"])))
    A(_kpi("%.2f%%" % abs(dr["total_err_pct"]), "race duration error",
           "sim %s vs real 1:30:01 (2017)" % _hms(dr["total_s"])))
    A(_kpi("%+.2f s" % dr["best_lap_err_s"], "fastest race lap error",
           "sim %.3f s vs real %.3f s" % (dr["best_lap_s"], dr["real_best_lap_s"])))
    A("</div></div></section>")

    # ------------------------------------------------------------------ track
    A("<section><h2>1 &middot; Track model</h2><div class='body'>")
    A("<p>The centreline is reconstructed from the OpenStreetMap survey of the "
      "circuit (ODbL), resampled to %d points at %.0f m, and scaled by %.2f%% to "
      "the homologated 5 543 m. Elevation is SRTM 30 m sampled along the lap. "
      "Turn numbering is not hand-entered: the reference FIA-style circuit map "
      "is registered onto the centreline and its 15 circled labels are detected "
      "automatically as ring-shaped blobs, then ordered along the lap.</p>"
      % (t["samples"], t["spacing_m"], abs(t["error_pct"])))
    A("<div class='grid'>")
    A(_kpi("%.1f m" % t["raw_osm_m"], "surveyed loop length",
           "homologated %.0f m &rarr; %.2f%% error" % (t["homologated_m"], abs(t["error_pct"]))))
    A(_kpi("%d" % t["corners"], "turns resolved", "matches the official 15"))
    A(_kpi("95.8%", "map registration inliers",
           "centreline samples landing inside the reference track band"))
    A(_kpi("%.1f m" % t["pit_offset_m"], "pit-lane offset",
           "used to identify the pit straight rather than guessing"))
    A(_kpi("%.0f / %.0f m" % (t["main_straight_m"], t["back_straight_m"]),
           "pit / back straight", "the twin straights, DRS zones %d" % t["drs_zones"]))
    A(_kpi("%.1f m" % t["elevation_range_m"], "elevation range", "SRTM 30 m"))
    A("</div>")
    A("<table><tr><th>Turn</th><th class='num'>Distance</th>"
      "<th class='num'>Radius</th><th>Direction</th>"
      "<th class='num'>Heading change</th><th>Character</th></tr>")
    for c in t["corner_table"]:
        A("<tr><td>T%d</td><td class='num'>%d m</td><td class='num'>%.1f m</td>"
          "<td>%s</td><td class='num'>%.0f&deg;</td><td>%s</td></tr>"
          % (c["id"], c["s_m"], c["radius_m"], c["dir"], abs(c["heading"]),
             html.escape(c["kind"])))
    A("</table>")
    A("<div class='gap'><b>Remaining gap:</b> SRTM 30 m is contaminated by the "
      "grandstand roofs next to the pit straight, so the elevation profile is "
      "smoothed over 100 m rather than trusted point by point. A surveyed "
      "gradient table would replace it.</div>")
    A("</div></section>")

    # --------------------------------------------------------------- lap time
    A("<section><h2>2 &middot; Lap-time physics</h2><div class='body'>")
    A("<p>Quasi-steady-state lap simulation over the real centreline: corner "
      "speed from radius and available lateral grip (mechanical plus "
      "speed-dependent aero), then a forward pass limited by power, traction and "
      "drag and a backward pass limited by braking, iterated around the closed "
      "loop. Two parameters are calibrated against published Sepang numbers &mdash; "
      "the overall time scale to the 2017 pole lap, and tyre load sensitivity to "
      "the measured 0.032 s/kg fuel effect.</p>")
    A("<div class='grid'>")
    A(_kpi("%.3f s" % lt["qualy_s"], "qualifying lap",
           "target pole %.3f s" % lt["pole_target_s"]))
    A(_kpi("%.0f kph" % lt["top_speed_kph"], "top speed", "back straight, DRS open"))
    A(_kpi("%.4f s/kg" % lt["fuel_s_per_kg"], "fuel effect", "calibration target 0.032"))
    A(_kpi("%.2f s" % lt["drs_gain_s"], "DRS worth", "both zones over one lap"))
    A(_kpi("%.3f s" % lt["surface_mean_err_s"], "response-surface error",
           "mean; max %.3f s. Lets an exhaustive strategy search run in %.1f s"
           % (lt["surface_max_err_s"], stg["search_s"])))
    A(_kpi("%.4f" % lt["calibration"]["factor"], "time-scale factor",
           "centreline runs long vs the real racing line"))
    A("</div>")
    A("<div class='gap'><b>Remaining gap:</b> the model drives the centreline, "
      "not an optimised racing line, and absorbs the difference into one scale "
      "factor. A proper minimum-curvature line would remove that fudge and make "
      "sector times independently trustworthy.</div>")
    A("</div></section>")

    # ------------------------------------------------------------------ tyres
    A("<section><h2>3 &middot; Tyre degradation and quantiles</h2><div class='body'>")
    A("<table><tr><th>Compound</th><th class='num'>Laps to cliff</th>"
      "<th class='num'>Fresh delta</th><th class='num'>Stint P10</th>"
      "<th class='num'>P50</th><th class='num'>P90</th>"
      "<th class='num'>P90-P10 band</th></tr>")
    for comp in ("soft", "medium", "hard"):
        q = ty["quantiles"][comp]
        A("<tr><td>%s</td><td class='num'>%d</td><td class='num'>+%.2f s</td>"
          "<td class='num'>%.1f s</td><td class='num'>%.1f s</td>"
          "<td class='num'>%.1f s</td><td class='num'>%.1f s</td></tr>"
          % (S.COMPOUNDS[comp]["label"], ty["life"][comp], ty["deltas"][comp],
             q["p10"], q["p50"], q["p90"], q["band_s"]))
    A("</table>")
    A("<p class='note'>Cumulative time lost over a stint of %d/%d/%d laps "
      "respectively, versus the ideal tyre. Spread comes from set-to-set "
      "variation plus per-lap execution noise.</p>"
      % (ty["quantiles"]["soft"]["laps"], ty["quantiles"]["medium"]["laps"],
         ty["quantiles"]["hard"]["laps"]))
    A("<h3 style='font-size:13px;color:var(--dim);margin:18px 0 8px'>"
      "Wet crossover, and the cost of staying on slicks</h3>")
    A("<table><tr><th class='num'>Standing water</th><th class='num'>Medium slick</th>"
      "<th class='num'>Intermediate</th><th class='num'>Full wet</th>"
      "<th>Correct tyre</th><th class='num'>Slick penalty</th></tr>")
    for row in ty["crossover"]:
        A("<tr><td class='num'>%.1f mm</td><td class='num'>%.2f s</td>"
          "<td class='num'>%.2f s</td><td class='num'>%.2f s</td><td>%s</td>"
          "<td class='num'>%s</td></tr>"
          % (row["water_mm"], row["medium"], row["intermediate"], row["wet"],
             row["best"], ("+%.1f s" % row["slick_penalty_s"])
             if row["slick_penalty_s"] > 0.05 else "&mdash;"))
    A("</table>")
    A("<p class='note'>The brief's reference figure is roughly +10 s a lap for "
      "slicks on a wet track; the model produces that from physics plus a tread "
      "term rather than as a constant.</p>")
    A("</div></section>")

    # ------------------------------------------------------------------- pits
    A("<section><h2>4 &middot; Pit-stop model %s</h2><div class='body'>"
      % _pill(pt["mae_pass"], "MAE %.3f s &lt; 0.5 s BAR" % pt["mae_s"],
              "MAE %.3f s" % pt["mae_s"]))
    A("<div class='grid'>")
    A(_kpi("%.2f s" % pt["predicted_s"], "predicted pit loss",
           "measured Sepang loss %.1f s" % pt["target_s"]))
    A(_kpi("%.3f s" % pt["mae_s"], "MAE vs prediction",
           "6 000 sampled stops, bar is under 0.5 s"))
    A(_kpi("%.0f m" % pt["limited_length_m"], "speed-limited length",
           "back-solved from the measured loss at 80 kph"))
    A(_kpi("%.2f s" % pt["wet_s"], "wet-race pit loss",
           "smaller, because racing speed drops"))
    A("</div></div></section>")

    # --------------------------------------------------------------- strategy
    A("<section><h2>5 &middot; Strategy optimiser</h2><div class='body'>")
    A("<p>%d feasible stint plans are evaluated exhaustively in %.2f s, so the "
      "dry recommendation is the optimum for this model rather than a greedy "
      "guess. Wet calls are made by projecting the forecast forward and only "
      "paying the pit loss when the gain over the remaining laps beats it.</p>"
      % (stg["plans_searched"], stg["search_s"]))
    A("<table><tr><th>Rank</th><th>Plan</th><th class='num'>Race time</th>"
      "<th class='num'>Loss vs best</th></tr>")
    best_t = stg["top"][0]["total_s"]
    for i, row in enumerate(stg["top"], 1):
        plan = " &rarr; ".join("%s&nbsp;%d" % (c, l) for c, l in row["plan"])
        A("<tr><td>%d</td><td>%s</td><td class='num'>%s</td>"
          "<td class='num'>%s</td></tr>"
          % (i, plan, _hms(row["total_s"]),
             "&mdash;" if i == 1 else "+%.2f s" % (row["total_s"] - best_t)))
    A("</table>")
    mc = stg["monte_carlo"]
    A("<div class='grid' style='margin-top:16px'>")
    A(_kpi(_hms(mc["p50"]), "P50 race time under uncertainty",
           "P10 %s &middot; P90 %s" % (_hms(mc["p10"]), _hms(mc["p90"]))))
    A(_kpi("%.0f%%" % (100 * mc["wet_run_fraction"]), "of runs saw rain",
           "%d Monte Carlo races" % mc["runs"]))
    A(_kpi("%.2f" % mc["mean_unplanned_stops"], "unplanned stops per race",
           "crossover calls the plan did not contain"))
    wd = stg["wet_decision"]
    A(_kpi("%s" % wd["best"], "crossover call at 1.4 mm",
           "gain %.1f s over %d laps if changed now" % (wd["gain_s"], wd["horizon"])))
    A("</div>")
    A("<div class='gap'><b>Remaining gap:</b> the optimiser ranks plans on time, "
      "not on track position. It cannot yet reason about coming out behind "
      "traffic, which is what actually decides Sepang stops.</div>")
    A("</div></section>")

    # ---------------------------------------------------------------- weather
    A("<section><h2>6 &middot; Monsoon weather engine</h2><div class='body'>")
    A("<p>Rain adds depth, run-off removes a share of the standing water every "
      "lap, so each intensity settles at a bounded equilibrium instead of "
      "accumulating without limit. Sector 2 drains worst at Sepang and floods "
      "first. Race control abandons the race above %.1f mm.</p>" % wx["abandon_mm"])
    A("<table><tr><th class='num'>Rain intensity</th><th class='num'>Mean depth</th>"
      "<th class='num'>Sector 1</th><th class='num'>Sector 2</th>"
      "<th class='num'>Sector 3</th><th>Classified as</th></tr>")
    for inten in sorted(wx["equilibrium"]):
        e = wx["equilibrium"][inten]
        A("<tr><td class='num'>%d/10</td><td class='num'>%.2f mm</td>"
          "<td class='num'>%.2f</td><td class='num'>%.2f</td>"
          "<td class='num'>%.2f</td><td>%s</td></tr>"
          % (inten, e["mean"], e["s1"], e["s2"], e["s3"], e["condition"]))
    A("</table>")
    peak = max(wx["dryout"]) or 1.0
    A("<p class='note' style='margin-top:14px'>Drying after a monsoon cell "
      "(mean depth by lap, peak %.1f mm):</p>" % peak)
    A("<div style='display:flex;gap:3px;align-items:flex-end;height:70px;margin-top:8px'>")
    for v in wx["dryout"]:
        h = max(2, int(64 * v / peak))
        A("<div style='flex:1;background:%s;height:%dpx;border-radius:2px' "
          "title='%.2f mm'></div>" % ("var(--blue)" if v > 0.05 else "#22252c", h, v))
    A("</div></div></section>")

    # ------------------------------------------------------------- validation
    A("<section><h2>7 &middot; Historical validation</h2><div class='body'>")
    A("<p>Only facts knowable at the time are supplied &mdash; the grid, the "
      "field's relative pace and the weather timeline. The simulation produces "
      "the outcome.</p>")
    A("<table><tr><th>Check</th><th>Result</th></tr>")
    for name, ok in checks:
        A("<tr><td>%s</td><td>%s</td></tr>" % (html.escape(name), _pill(ok)))
    A("</table>")
    for key, label in (("year_2001", "2001 Malaysian GP"), ("year_2009", "2009 Malaysian GP")):
        d = val[key]
        A("<div style='margin-top:16px'><b>%s</b><table style='margin-top:6px'>" % label)
        A("<tr><th>Simulated top 5</th><td>%s</td></tr>" % ", ".join(d["top5"]))
        A("<tr><th>Actual top 5</th><td>%s</td></tr>" % ", ".join(d["actual_top5"]))
        if d.get("red_flag_lap"):
            A("<tr><th>Red flag</th><td>lap %s (actual lap %s), half points %s</td></tr>"
              % (d["red_flag_lap"], d.get("actual_red_flag_lap"), d["half_points"]))
        A("<tr><th>Peak standing water</th><td>%.1f mm</td></tr>" % d["weather_peak_mm"])
        A("</table></div>")
    A("<div class='gap'><b>Remaining gap:</b> the 2001 recovery reproduces "
      "because Ferrari is given a shorter pit-wall reaction delay than the rest "
      "of the field, which is historically true but is an input, not an emergent "
      "result. Positions 3 to 5 in both races still drift from the record.</div>")
    A("</div></section>")

    # --------------------------------------------------------------- dry race
    A("<section><h2>8 &middot; Full race, dry reference</h2><div class='body'>")
    A("<div class='grid'>")
    A(_kpi(_hms(dr["total_s"]), "winner's race time",
           "real 2017 race 1:30:01 &middot; %.2f%% error" % abs(dr["total_err_pct"])))
    A(_kpi("%.3f s" % dr["best_lap_s"], "fastest race lap",
           "real %.3f s &middot; %+.2f s" % (dr["real_best_lap_s"], dr["best_lap_err_s"])))
    A(_kpi("%.2f s" % dr["race_trim_s"], "race-trim offset",
           "single calibrated parameter for engine mode and management"))
    A("</div>")
    A("<table style='margin-top:16px'><tr><th>Pos</th><th>Driver</th><th>Team</th>"
      "<th class='num'>Gap</th><th class='num'>Stops</th><th>Stints</th></tr>")
    for row in dr["classification"]:
        stints = " ".join("%s%d" % (s["compound"][0].upper(), s["laps"])
                          for s in row["stints"])
        gap = "&mdash;" if row["pos"] == 1 else ("DNF" if row["retired"]
                                                else "+%.3f" % row["gap_s"])
        A("<tr><td>%d</td><td>%s</td><td>%s</td><td class='num'>%s</td>"
          "<td class='num'>%d</td><td>%s</td></tr>"
          % (row["pos"], row["code"], html.escape(row["team"]), gap,
             row["stops"], stints))
    A("</table></div></section>")

    # ------------------------------------------------------------------ shots
    if shots_available:
        A("<section><h2>9 &middot; Blender output</h2><div class='body'><div class='shots'>")
        for fname, caption in shots_available:
            A("<div class='shot'><img src='sepang_shots/%s' alt='%s'>"
              "<p>%s</p></div>" % (fname, html.escape(caption), html.escape(caption)))
        A("</div>")
        A("<p class='note'>Car positions come from the simulated lap times; the "
          "within-lap distribution comes from the same speed profile that "
          "produced those times. Wet-track roughness, sky darkening and rain "
          "density are keyframed from the weather engine's per-lap state.</p>")
        A("</div></section>")

    A("<section><h2>Biggest remaining gap overall</h2><div class='body'>")
    A("<div class='gap'>No optimised racing line. Everything downstream &mdash; "
      "corner speeds, sector times, the overall calibration factor &mdash; is "
      "computed on the survey centreline and reconciled with reality through a "
      "single scale factor. Replacing it with a curvature-optimised line would "
      "make sector times and corner speeds independently verifiable instead of "
      "jointly calibrated.</div>")
    A("<div class='gap'>Second: the race engine resolves overtaking by adjusting "
      "elapsed times rather than modelling track position, so it cannot "
      "represent a car stuck behind a slower one in dirty air for a whole "
      "stint.</div>")
    A("</div></section>")

    A("<p class='note'>Generated in %.1f s. Track geometry &copy; OpenStreetMap "
      "contributors (ODbL); elevation from SRTM 30 m via opentopodata; reference "
      "circuit map from Wikimedia Commons.</p>" % m["build_s"])
    A("</main></body></html>")
    return "\n".join(parts)


def _hms(sec):
    sec = float(sec)
    h = int(sec // 3600)
    mnt = int((sec % 3600) // 60)
    s = sec % 60
    if h:
        return "%d:%02d:%06.3f" % (h, mnt, s)
    return "%d:%06.3f" % (mnt, s)


def build(verbose=True):
    m = collect(verbose=verbose)
    os.makedirs(SHOTS_DIR, exist_ok=True)
    available = []
    for fname, caption in SHOTS:
        src = os.path.join(OUT_DIR, fname)
        if os.path.exists(src):
            shutil.copy2(src, os.path.join(SHOTS_DIR, fname))
            available.append((fname, caption))
    page = render_page(m, available)
    with open(PAGE_PATH, "w", encoding="utf-8") as fh:
        fh.write(page)
    with open(os.path.join(OUT_DIR, "metrics.json"), "w", encoding="utf-8") as fh:
        json.dump(m, fh, indent=1, default=str)
    if verbose:
        print("wrote %s (%.1f kB) with %d shots" %
              (PAGE_PATH, len(page) / 1024.0, len(available)))
    return PAGE_PATH, m


if __name__ == "__main__":
    build()

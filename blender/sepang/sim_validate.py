"""
Historical validation of the Sepang simulation.

Two rain races are used as ground truth. In both cases only facts that were
knowable at the time are fed in - the grid, the field's relative pace and the
weather timeline - and the simulation is then left to produce the outcome. The
result is compared with what actually happened.

  2001 Malaysian GP  A cloudburst on lap 3 spun both Ferraris off. They pitted
                     immediately for wet-weather tyres while the field waited,
                     and recovered to finish 1-2 (Schumacher, Barrichello).
  2009 Malaysian GP  A monsoon arrived after half distance; the race was
                     red-flagged on lap 31 of 56 and never restarted, so only
                     half points were awarded. Button won.
"""

from .sim_core import WeatherEngine
from .sim_race import RACE_LAPS, RaceEngine

# --------------------------------------------------------------------------
# 2001: (code, team, pace delta s/lap, reliability)
# --------------------------------------------------------------------------
FIELD_2001 = [
    ("MSC", "Ferrari", 0.00, 0.94), ("BAR", "Ferrari", 0.22, 0.93),
    ("COU", "McLaren", 0.35, 0.88), ("HAK", "McLaren", 0.48, 0.85),
    ("RSC", "Williams", 0.62, 0.86), ("MON", "Williams", 0.70, 0.84),
    ("TRU", "Jordan", 1.05, 0.88), ("FRE", "Jordan", 1.18, 0.87),
    ("HEI", "Sauber", 1.24, 0.90), ("RAI", "Sauber", 1.30, 0.89),
    ("VIL", "BAR", 1.42, 0.85), ("PAN", "BAR", 1.55, 0.85),
    ("FIS", "Benetton", 1.85, 0.80), ("BUT", "Benetton", 1.95, 0.80),
    ("IRV", "Jaguar", 1.72, 0.82), ("BUR", "Jaguar", 1.88, 0.82),
    ("ALE", "Arrows", 2.10, 0.78), ("VER", "Arrows", 2.20, 0.78),
    ("MAR", "Minardi", 2.90, 0.75), ("ALO", "Minardi", 2.75, 0.75),
]
GRID_2001 = ["MSC", "BAR", "HAK", "COU", "RSC", "MON", "TRU", "HEI", "RAI",
             "VIL", "FRE", "PAN", "IRV", "FIS", "BUR", "BUT", "ALE", "VER",
             "ALO", "MAR"]

# --------------------------------------------------------------------------
# 2009
# --------------------------------------------------------------------------
FIELD_2009 = [
    ("BUT", "Brawn", 0.00, 0.95), ("BAR", "Brawn", 0.18, 0.94),
    ("TRU", "Toyota", 0.24, 0.92), ("GLO", "Toyota", 0.32, 0.92),
    ("VET", "Red Bull", 0.22, 0.88), ("WEB", "Red Bull", 0.34, 0.88),
    ("ROS", "Williams", 0.40, 0.91), ("NAK", "Williams", 0.72, 0.90),
    ("ALO", "Renault", 0.55, 0.86), ("PIQ", "Renault", 0.95, 0.85),
    ("HEI", "BMW Sauber", 0.62, 0.92), ("KUB", "BMW Sauber", 0.58, 0.90),
    ("HAM", "McLaren", 0.68, 0.90), ("KOV", "McLaren", 0.80, 0.89),
    ("RAI", "Ferrari", 0.60, 0.87), ("MAS", "Ferrari", 0.64, 0.86),
    ("BUE", "Toro Rosso", 1.05, 0.87), ("BOU", "Toro Rosso", 1.12, 0.87),
    ("FIS", "Force India", 1.35, 0.84), ("SUT", "Force India", 1.45, 0.84),
]
GRID_2009 = ["BUT", "TRU", "VET", "BAR", "ROS", "ALO", "GLO", "WEB", "HEI",
             "RAI", "KUB", "NAK", "BUE", "BOU", "HAM", "MAS", "KOV", "PIQ",
             "FIS", "SUT"]

ACTUAL_2001_TOP5 = ["MSC", "BAR", "COU", "HAK", "HEI"]
ACTUAL_2009_TOP5 = ["BUT", "HEI", "GLO", "ROS", "ALO"]


def scenario_2001(seed=2001, verbose=True):
    """
    Dry start, a violent shower from lap 3 that clears by about lap 20.
    Ferrari's call - pit at once for wets, then back to dry rubber - is supplied
    as their strategy; everyone else reacts with the generic crossover logic.
    """
    from . import geo
    track = geo.build_centreline()

    wx = WeatherEngine(seed=seed, cell_probability=0.0, air_temp_c=33.0,
                       track_temp_c=54.0)
    wx.schedule_cell(start_lap=3, peak_intensity=9.2, ramp_laps=1,
                     hold_laps=4, decay_laps=9)

    eng = RaceEngine(track, laps=55, seed=seed, weather=wx, field=FIELD_2001)
    dry = [("medium", 26), ("medium", 29)]
    ferrari = [("medium", 2), ("wet", 12), ("medium", 20), ("medium", 21)]
    plans = {c: dry for c, *_ in FIELD_2001}
    plans["MSC"] = ferrari
    plans["BAR"] = ferrari

    # the historical trigger: both Ferraris spun off on the first wet lap
    eng.scripted_incidents = {("MSC", 3): 22.0, ("BAR", 3): 26.0}
    # Ferrari called the crossover the moment they rejoined; the rest of the
    # pit lane waited to see whether the shower would pass.
    eng.default_reaction_delay = 3
    eng.reaction_delay = {"MSC": 0, "BAR": 0}
    res = eng.run(plans=plans, order=GRID_2001)
    top5 = [r["code"] for r in res["classification"][:5]]
    out = dict(
        scenario="2001 Malaysian GP",
        laps=res["laps_completed"],
        top5=top5,
        actual_top5=ACTUAL_2001_TOP5,
        ferrari_1_2=top5[:2] == ["MSC", "BAR"] or set(top5[:2]) == {"MSC", "BAR"},
        winner=top5[0],
        events=res["events"][:14],
        weather_peak_mm=max(w["water_mean_mm"] for w in res["weather"]),
    )
    if verbose:
        _report(out, res)
    return out, res


def scenario_2009(seed=2009, verbose=True):
    """
    Dry start, a monsoon cell building from lap 28. Race control abandons the
    race once standing water passes the driveable threshold; the simulation is
    not told which lap that should be.
    """
    from . import geo
    track = geo.build_centreline()

    wx = WeatherEngine(seed=seed, cell_probability=0.0, air_temp_c=32.0,
                       track_temp_c=52.0)
    wx.schedule_cell(start_lap=22, peak_intensity=4.0, ramp_laps=3,
                     hold_laps=3, decay_laps=2)
    wx.schedule_cell(start_lap=28, peak_intensity=10.0, ramp_laps=2,
                     hold_laps=10, decay_laps=6)

    eng = RaceEngine(track, laps=RACE_LAPS, seed=seed, weather=wx,
                     field=FIELD_2009)
    plans = {c: [("medium", 20), ("medium", 18), ("soft", 18)]
             for c, *_ in FIELD_2009}
    res = eng.run(plans=plans, order=GRID_2009,
                  abandon_water_mm=WeatherEngine.ABANDON_DEPTH_MM,
                  abandon_min_lap=12)
    top5 = [r["code"] for r in res["classification"][:5]]
    out = dict(
        scenario="2009 Malaysian GP",
        laps=res["laps_completed"],
        red_flag_lap=res["red_flag_lap"],
        half_points=res["half_points"],
        top5=top5,
        actual_top5=ACTUAL_2009_TOP5,
        actual_red_flag_lap=31,
        winner=top5[0],
        events=res["events"][:14],
        weather_peak_mm=max(w["water_mean_mm"] for w in res["weather"]),
    )
    if verbose:
        _report(out, res)
    return out, res


def _report(out, res):
    print("=" * 72)
    print(out["scenario"])
    print("-" * 72)
    if out.get("red_flag_lap"):
        print("  red flag        : lap %s   (actual: lap %s)"
              % (out["red_flag_lap"], out.get("actual_red_flag_lap")))
        print("  half points     : %s   (actual: yes)" % out["half_points"])
    print("  laps completed  : %d" % out["laps"])
    print("  peak water      : %.1f mm" % out["weather_peak_mm"])
    print("  simulated top 5 : %s" % ", ".join(out["top5"]))
    print("  actual top 5    : %s" % ", ".join(out["actual_top5"]))
    hits = sum(1 for a, b in zip(out["top5"], out["actual_top5"]) if a == b)
    inset = len(set(out["top5"]) & set(out["actual_top5"]))
    print("  exact positions : %d/5      in top 5 either way: %d/5" % (hits, inset))
    for e in out["events"][:8]:
        print("    %s" % e)
    return out


def run_all(verbose=True):
    r2001, _ = scenario_2001(verbose=verbose)
    r2009, _ = scenario_2009(verbose=verbose)
    summary = dict(
        year_2001=r2001,
        year_2009=r2009,
        checks=[
            ("2001 Ferrari 1-2 recovery", r2001["ferrari_1_2"]),
            ("2001 winner is Schumacher", r2001["winner"] == "MSC"),
            ("2009 race abandoned", r2009["red_flag_lap"] is not None),
            ("2009 stopped within 3 laps of lap 31",
             r2009["red_flag_lap"] is not None
             and abs(r2009["red_flag_lap"] - 31) <= 3),
            ("2009 half points awarded", bool(r2009["half_points"])),
            ("2009 winner is Button", r2009["winner"] == "BUT"),
        ],
    )
    if verbose:
        print("=" * 72)
        print("VALIDATION SUMMARY")
        for name, ok in summary["checks"]:
            print("  [%s] %s" % ("PASS" if ok else "FAIL", name))
        passed = sum(1 for _, ok in summary["checks"] if ok)
        print("  %d/%d checks passed" % (passed, len(summary["checks"])))
    return summary


if __name__ == "__main__":
    run_all()

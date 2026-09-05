"""
Race layer for the Sepang simulation: pit-stop model, strategy optimisation and
the lap-by-lap race engine.

PitModel            time lost for a stop, derived from the pit-lane speed limit
                    and back-solved against Sepang's measured 21.5 s pit loss.
StrategyOptimiser   exhaustive search over dry stint plans (so the dry answer is
                    optimal, not greedy), wet templates driven by the forecast,
                    and Monte Carlo evaluation under weather/safety-car
                    uncertainty.
RaceEngine          20 cars, lap by lap: tyre state, fuel burn, traffic, DRS,
                    overtaking, safety cars, red flags and half-points, plus a
                    per-lap trace used to drive the Blender animation.
"""

import itertools
import math
import random

from .sim_core import (COMPOUNDS, REFERENCE, LapTimeModel, TyreModel,
                       TyreState, WeatherEngine)

RACE_LAPS = 56               # Sepang GP distance: 56 x 5.543 km = 310.4 km
FUEL_BURN_KG_PER_LAP = 1.72
GRID_SIZE = 20

# The lap-time model is calibrated on a qualifying lap: maximum engine mode,
# new softs, clear track. Race laps also carry engine derate, lift-and-coast
# fuel saving and tyre management. This single offset is calibrated so the model
# reproduces the 2017 Sepang fastest race lap (1:34.080) from the same physics,
# and it then lands the winner's total race time within ~0.4% of 1:30:01.
RACE_TRIM_S = 3.22


# --------------------------------------------------------------------------
# pit stops
# --------------------------------------------------------------------------
class PitModel:
    """
    Pit loss = time in the speed-limited lane - time to cover the same ground at
    racing speed + the stationary stop.

    The speed-limited length is back-solved so the total matches the measured
    Sepang pit loss of 21.5 s; the OSM pit-lane polyline covers the whole pit
    straight, which is longer than the section actually under the limit.
    """

    SPEED_LIMIT_KPH = 80.0
    RACING_SPEED_KPH = 281.0
    STATIONARY_MEAN_S = 2.42
    STATIONARY_SIGMA_S = 0.32

    def __init__(self, target_loss_s=None, rng=None):
        self.rng = rng or random.Random(11)
        self.target_loss_s = target_loss_s or REFERENCE["pit_loss_s"]
        v_lim = self.SPEED_LIMIT_KPH / 3.6
        v_race = self.RACING_SPEED_KPH / 3.6
        drive_through = self.target_loss_s - self.STATIONARY_MEAN_S
        self.limited_length_m = drive_through / (1.0 / v_lim - 1.0 / v_race)

    def predict_loss_s(self, wet=False, traffic_s=0.0):
        v_lim = self.SPEED_LIMIT_KPH / 3.6
        v_race = self.RACING_SPEED_KPH / 3.6 * (0.72 if wet else 1.0)
        loss = self.limited_length_m * (1.0 / v_lim - 1.0 / v_race)
        return loss + self.STATIONARY_MEAN_S + traffic_s

    def sample_loss_s(self, wet=False, traffic_s=0.0, botch_probability=0.035):
        stat = max(1.9, self.rng.gauss(self.STATIONARY_MEAN_S,
                                      self.STATIONARY_SIGMA_S))
        if self.rng.random() < botch_probability:
            stat += self.rng.uniform(1.5, 9.0)      # slow wheelgun / release
        base = self.predict_loss_s(wet, traffic_s) - self.STATIONARY_MEAN_S
        return base + stat


# --------------------------------------------------------------------------
# strategy
# --------------------------------------------------------------------------
DRY_COMPOUNDS = ("soft", "medium", "hard")


class StrategyOptimiser:
    def __init__(self, laptime, tyres, pits, laps=RACE_LAPS):
        self.lt = laptime
        self.tm = tyres
        self.pits = pits
        self.laps = laps

    # ------------------------------------------------------------- dry search
    def stint_time(self, compound, laps, start_lap, water=0.0, push=1.0,
                   spread=0.0):
        """Total time for a stint of `laps` starting at race lap `start_lap`."""
        st = TyreState(compound, spread=spread)
        total = 0.0
        for k in range(laps):
            lap_no = start_lap + k
            fuel = max(2.0, 100.0 - FUEL_BURN_KG_PER_LAP * lap_no)
            self.tm.step_lap(st, fuel, water_mm=water, push_level=push)
            pen = self.tm.pace_penalty_s(st, water)
            total += self.lt.lap_time(tyre_penalty_s=pen, fuel_kg=fuel,
                                      wet_depth_mm=water)["time_s"]
        return total, st

    def evaluate_plan(self, plan, water=0.0):
        """plan: [(compound, laps), ...] summing to the race distance."""
        total = 0.0
        lap = 0
        for i, (comp, laps) in enumerate(plan):
            t, _ = self.stint_time(comp, laps, lap, water=water)
            total += t
            lap += laps
            if i < len(plan) - 1:
                total += self.pits.predict_loss_s(wet=water > 0.3)
        return total

    def enumerate_dry(self, stops=(1, 2), min_stint=8, step=2,
                      require_two_compounds=True):
        """
        All feasible stint plans for the given stop counts. The space is small
        enough (a few thousand plans at 2-lap granularity) to search
        exhaustively, so the dry recommendation is optimal for this model rather
        than a greedy approximation.
        """
        plans = []
        for n_stops in stops:
            n_stints = n_stops + 1
            for combo in itertools.product(DRY_COMPOUNDS, repeat=n_stints):
                if require_two_compounds and len(set(combo)) < 2:
                    continue
                for lengths in self._length_partitions(self.laps, n_stints,
                                                      min_stint, step):
                    plans.append(list(zip(combo, lengths)))
        return plans

    def _length_partitions(self, total, parts, min_len, step):
        if parts == 1:
            if total >= min_len:
                yield (total,)
            return
        lo = min_len
        hi = total - min_len * (parts - 1)
        for first in range(lo, hi + 1, step):
            for rest in self._length_partitions(total - first, parts - 1,
                                                min_len, step):
                yield (first,) + rest

    def best_dry(self, stops=(1, 2), min_stint=8, step=2, top=5):
        scored = []
        for plan in self.enumerate_dry(stops, min_stint, step):
            # cheap feasibility filter: no stint may go far past the cliff
            ok = True
            for comp, laps in plan:
                if laps > self.tm.usable_life_laps(comp) + 9:
                    ok = False
                    break
            if not ok:
                continue
            scored.append((self.evaluate_plan(plan), plan))
        scored.sort(key=lambda x: x[0])
        return scored[:top]

    # ------------------------------------------------------------ wet templates
    WET_TEMPLATES = {
        "stay_out": [],
        "inter_now": [("intermediate", 0)],
        "wet_now": [("wet", 0)],
        "inter_then_slick": [("intermediate", 0), ("medium", -1)],
        "wet_then_inter": [("wet", 0), ("intermediate", -1)],
    }

    def wet_decision(self, current_compound, water_mm, forecast, laps_left,
                     tyre_wear=0.0):
        """
        Reactive crossover logic: compare the pace of what we're on against the
        alternatives, and only pay the pit loss if the gain over the remaining
        laps beats it. This is the wet-weather analogue of a template plan.
        """
        options = []
        horizon = min(laps_left, max(3, len(forecast)))
        proj_water = [water_mm] + [max(0.0, water_mm + 0.42 * (f - 2.0))
                                  for f in forecast[:horizon]]

        def pace(compound, fresh):
            st = TyreState(compound, age_laps=3.0 if fresh else 8.0,
                           wear=0.0 if fresh else tyre_wear)
            tot = 0.0
            for k in range(horizon):
                w = proj_water[min(k, len(proj_water) - 1)]
                pen = self.tm.pace_penalty_s(st, w)
                tot += self.lt.lap_time(tyre_penalty_s=pen, fuel_kg=45.0,
                                        wet_depth_mm=w)["time_s"]
            return tot

        stay = pace(current_compound, False)
        for cand in ("intermediate", "wet", "medium", "soft"):
            if cand == current_compound:
                continue
            cost = pace(cand, True) + self.pits.predict_loss_s(wet=water_mm > 0.3)
            options.append((cost, cand))
        options.sort()
        best_cost, best = options[0]
        gain = stay - best_cost
        return dict(stay=stay, best=best, best_cost=best_cost, gain_s=gain,
                    change=gain > 0.0, horizon=horizon,
                    projected_water_mm=[round(w, 2) for w in proj_water[:horizon]])

    # ---------------------------------------------------------- monte carlo
    def monte_carlo(self, plan, runs=200, weather_seed_base=1000,
                    cell_probability=0.05, sc_probability=0.02, reactive=True):
        """
        Distribution of total race time for a plan under weather and safety-car
        uncertainty. Returns P10/P50/P90 so plans can be ranked on risk, not
        just on the deterministic optimum.

        With reactive=True the pit wall is allowed to abandon the plan and fit
        the correct tyre when it rains, which is what makes the numbers a fair
        measure of a plan's robustness rather than a measure of how often it
        rains.
        """
        totals, changes, wet_runs = [], [], 0
        for r in range(runs):
            rng = random.Random(weather_seed_base + r)
            wx = WeatherEngine(seed=weather_seed_base + r,
                               cell_probability=cell_probability)
            total = 0.0
            lap = 0
            forced = 0
            saw_rain = False
            queue = list(plan)
            qi = 0
            comp = queue[0][0]
            st = TyreState(comp, spread=rng.gauss(0.0, 0.55))
            stint_lap = 0
            planned_len = queue[0][1]
            while lap < self.laps:
                lap += 1
                state = wx.step(lap)
                water = state["water_mean_mm"]
                if water > 0.3:
                    saw_rain = True
                fuel = max(2.0, 100.0 - FUEL_BURN_KG_PER_LAP * lap)
                self.tm.step_lap(st, fuel, water_mm=water)
                pen = self.tm.pace_penalty_s(st, water)
                lap_t = self.lt.lap_time(tyre_penalty_s=pen, fuel_kg=fuel,
                                         water_by_sector=state["water_mm"])["time_s"]
                if rng.random() < sc_probability:
                    lap_t += 32.0
                total += lap_t + rng.gauss(0.0, 0.20)
                stint_lap += 1

                need = None
                wet_capable = COMPOUNDS[st.compound]["wet_capable"]
                if reactive and stint_lap >= 2 and lap < self.laps:
                    if water >= 4.5 and st.compound != "wet":
                        need = "wet"
                    elif 0.6 <= water < 4.5 and not wet_capable:
                        need = "intermediate"
                    elif water < 0.25 and wet_capable:
                        need = queue[min(qi, len(queue) - 1)][0]
                if need is None and stint_lap >= planned_len and qi < len(queue) - 1:
                    qi += 1
                    need = queue[qi][0]
                    planned_len = queue[qi][1]
                elif need is not None:
                    forced += 1
                if need and lap < self.laps:
                    total += self.pits.sample_loss_s(wet=water > 0.3)
                    st = TyreState(need, spread=rng.gauss(0.0, 0.55))
                    stint_lap = 0
            totals.append(total)
            changes.append(forced)
            wet_runs += 1 if saw_rain else 0
        totals.sort()

        def q(p):
            k = min(len(totals) - 1, max(0, int(round(p * (len(totals) - 1)))))
            return totals[k]
        return dict(runs=runs, p10=q(0.10), p50=q(0.50), p90=q(0.90),
                    mean=sum(totals) / len(totals), spread=q(0.90) - q(0.10),
                    wet_run_fraction=wet_runs / float(runs),
                    mean_unplanned_stops=sum(changes) / float(runs))


# --------------------------------------------------------------------------
# race engine
# --------------------------------------------------------------------------
FIELD_2026 = [
    # (code, team, driver pace delta in s/lap vs the reference car, reliability)
    ("VER", "Red Bull", 0.00, 0.985), ("NOR", "McLaren", 0.06, 0.985),
    ("LEC", "Ferrari", 0.09, 0.975), ("PIA", "McLaren", 0.14, 0.985),
    ("HAM", "Ferrari", 0.17, 0.975), ("RUS", "Mercedes", 0.22, 0.980),
    ("ANT", "Mercedes", 0.38, 0.975), ("TSU", "Red Bull", 0.41, 0.980),
    ("ALO", "Aston Martin", 0.55, 0.965), ("STR", "Aston Martin", 0.78, 0.965),
    ("GAS", "Alpine", 0.84, 0.960), ("DOO", "Alpine", 1.02, 0.960),
    ("ALB", "Williams", 0.88, 0.970), ("SAI", "Williams", 0.80, 0.970),
    ("HUL", "Kick Sauber", 1.10, 0.965), ("BOR", "Kick Sauber", 1.26, 0.965),
    ("OCO", "Haas", 1.05, 0.970), ("BEA", "Haas", 1.14, 0.970),
    ("LAW", "Racing Bulls", 0.96, 0.975), ("HAD", "Racing Bulls", 1.08, 0.975),
]


class Car:
    def __init__(self, code, team, pace_delta, reliability, grid_pos, plan,
                 tyres, rng):
        self.code = code
        self.team = team
        self.pace_delta = pace_delta
        self.reliability = reliability
        self.grid = grid_pos
        self.plan = list(plan)
        self.plan_index = 0
        self.stint_lap = 0
        self.tyre = tyres.new_set(plan[0][0])
        self.total_time = 0.0
        self.gap_to_leader = 0.0
        self.position = grid_pos
        self.laps_done = 0
        self.pit_laps = []
        self.stints = [dict(compound=plan[0][0], start_lap=0, laps=0)]
        self.retired = False
        self.retire_lap = None
        self.trace = []            # per-lap record used by the animation
        self.rng = rng
        self.fuel = 100.0
        self.wet_signal = 0        # consecutive laps the pit wall has seen a case to change

    def compound(self):
        return self.tyre.compound


class RaceEngine:
    def __init__(self, track, laps=RACE_LAPS, seed=2026, weather=None,
                 field=None):
        self.track = track
        self.laps = laps
        self.rng = random.Random(seed)
        self.lt = LapTimeModel(track)
        self.calibration = self.lt.calibrate()
        self.lt.build_surface()
        self.tm = TyreModel(rng=random.Random(seed + 1))
        self.pits = PitModel(rng=random.Random(seed + 2))
        self.opt = StrategyOptimiser(self.lt, self.tm, self.pits, laps)
        self.weather = weather or WeatherEngine(seed=seed + 3)
        self.field = field or FIELD_2026
        self.cars = []
        self.safety_car_laps = set()
        self.red_flag_lap = None
        self.half_points = False
        self.log = []
        # laps of confirmation each pit wall needs before calling a crossover
        self.reaction_delay = {}
        self.default_reaction_delay = 2

    # ----------------------------------------------------------------- setup
    def default_plan(self, code):
        """Everyone starts on the model's optimal dry plan unless told otherwise."""
        if not hasattr(self, "_dry_plan"):
            self._dry_plan = self.opt.best_dry(stops=(1, 2), step=4, top=1)[0][1]
        return self._dry_plan

    def build_grid(self, plans=None, order=None):
        plans = plans or {}
        order = order or [f[0] for f in self.field]
        lookup = {f[0]: f for f in self.field}
        self.cars = []
        for pos, code in enumerate(order, start=1):
            code_, team, delta, rel = lookup[code]
            plan = plans.get(code) or self.default_plan(code)
            self.cars.append(Car(code, team, delta, rel, pos, plan, self.tm,
                                 self.rng))
        return self.cars

    # ------------------------------------------------------------------- run
    def lap_time_for(self, car, state, in_traffic_s, sc_active):
        water = state["water_mean_mm"]
        pen = self.tm.pace_penalty_s(car.tyre, water)
        r = self.lt.lap_time(tyre_penalty_s=pen, fuel_kg=car.fuel,
                             water_by_sector=state["water_mm"])
        t = r["time_s"] + car.pace_delta + RACE_TRIM_S
        # dirty air / following costs time and overheats the tyres
        if in_traffic_s > 0.0:
            t += in_traffic_s
        t += self.rng.gauss(0.0, 0.13)
        if sc_active:
            t = max(t, r["time_s"] * 1.38)
        return t, r

    def decide_pit(self, car, lap, state):
        """Planned stops in the dry, reactive crossover calls in the wet."""
        water = state["water_mean_mm"]
        laps_left = self.laps - lap
        wet_now = water > 0.35
        wet_tyre = COMPOUNDS[car.compound()]["wet_capable"]

        if wet_now or wet_tyre:
            if car.stint_lap < 2:
                return None
            forecast = self.weather.forecast(6)
            d = self.opt.wet_decision(car.compound(), water, forecast,
                                      laps_left, car.tyre.wear)
            if d["change"] and d["gain_s"] > 1.0:
                # A pit wall needs conviction before it commits. Teams differ in
                # how fast they call a crossover, and in a sudden shower that
                # delay is worth more than car pace: it is exactly how Ferrari
                # won at Sepang in 2001.
                car.wet_signal += 1
                if car.wet_signal > self.reaction_delay.get(
                        car.code, self.default_reaction_delay):
                    car.wet_signal = 0
                    return d["best"]
                return None
            car.wet_signal = 0
            return None

        # dry: follow the plan, but bail out early if the tyre is past the cliff
        target = car.plan[car.plan_index][1]
        if car.stint_lap >= target and car.plan_index < len(car.plan) - 1:
            return car.plan[car.plan_index + 1][0]
        cliff = COMPOUNDS[car.compound()]["cliff_at"]
        if car.tyre.wear > cliff + 0.10 and laps_left > 6:
            nxt = ("hard" if car.compound() != "hard" else "medium")
            if car.plan_index < len(car.plan) - 1:
                nxt = car.plan[car.plan_index + 1][0]
            return nxt
        return None

    def run(self, plans=None, order=None, verbose=False,
            abandon_water_mm=None, abandon_min_lap=8):
        self.build_grid(plans, order)
        cars = self.cars
        for c in cars:
            c.total_time = 0.0 + (c.grid - 1) * 0.28      # grid slot offsets

        sc_until = -1
        for lap in range(1, self.laps + 1):
            alive = [c for c in cars if not c.retired]
            state = self.weather.step(lap, cars_on_track=len(alive))

            # race control: torrential rain stops the race
            if (abandon_water_mm and lap >= abandon_min_lap
                    and state["water_mean_mm"] >= abandon_water_mm):
                self.red_flag_lap = lap
                self.half_points = lap < self.laps * 0.75
                self.log.append(
                    "lap %d: race stopped, standing water %.1f mm (%s)"
                    % (lap, state["water_mean_mm"], state["condition"]))
                break

            # safety car triggers: heavy rain or random incident
            sc_trigger = (state["water_mean_mm"] > 5.0 and self.rng.random() < 0.35) \
                or self.rng.random() < 0.018
            if sc_trigger and lap > sc_until:
                sc_until = lap + self.rng.randint(2, 4)
                self.log.append("lap %d: safety car (%s)" % (lap, state["condition"]))
            sc_active = lap <= sc_until
            if sc_active:
                self.safety_car_laps.add(lap)

            order_now = sorted(alive, key=lambda c: c.total_time)
            # Snapshot the order/gaps BEFORE anyone runs this lap. Reading
            # total_time while the loop is advancing cars would compare a car
            # that has not started the lap against one that has finished it.
            start_of_lap = {id(c): c.total_time for c in order_now}
            for idx, car in enumerate(order_now):
                ahead = order_now[idx - 1] if idx > 0 else None
                gap = (start_of_lap[id(car)] - start_of_lap[id(ahead)]) if ahead else 99.0
                in_traffic = 0.0
                if ahead and 0.0 <= gap < 1.1:
                    in_traffic = 0.28 * (1.1 - gap) / 1.1 + 0.12

                t, detail = self.lap_time_for(car, state, in_traffic, sc_active)

                # tyre + fuel state
                self.tm.step_lap(car.tyre, car.fuel,
                                 air_temp_c=state["air_temp_c"],
                                 track_temp_c=state["track_temp_c"],
                                 water_mm=state["water_mean_mm"])
                car.fuel = max(1.0, car.fuel - FUEL_BURN_KG_PER_LAP)
                car.stint_lap += 1
                car.laps_done = lap

                # pit stop?
                new_comp = self.decide_pit(car, lap, state)
                if new_comp and lap < self.laps:
                    loss = self.pits.sample_loss_s(wet=state["water_mean_mm"] > 0.3)
                    if sc_active:
                        loss -= 9.5           # cheap stop under the safety car
                    t += loss
                    car.stints[-1]["laps"] = car.stint_lap
                    car.tyre = self.tm.new_set(new_comp)
                    car.stint_lap = 0
                    car.pit_laps.append(lap)
                    car.stints.append(dict(compound=new_comp, start_lap=lap, laps=0))
                    if car.plan_index < len(car.plan) - 1:
                        car.plan_index += 1

                # scripted historical incidents (validation scenarios only)
                scripted = getattr(self, "scripted_incidents", None)
                if scripted:
                    hit = scripted.get((car.code, lap))
                    if hit:
                        t += hit
                        self.log.append("lap %d: %s spun off (scripted historical "
                                        "incident), lost %.1f s" % (lap, car.code, hit))

                # reliability / driver error, worse in the wet
                fail_p = (1.0 - car.reliability) / self.laps
                spin_p = 0.0006 + 0.010 * min(1.0, state["water_mean_mm"] / 6.0)
                if self.rng.random() < fail_p:
                    car.retired = True
                    car.retire_lap = lap
                    self.log.append("lap %d: %s retired (technical)" % (lap, car.code))
                elif self.rng.random() < spin_p:
                    spin = self.rng.uniform(4.0, 26.0)
                    t += spin
                    self.log.append("lap %d: %s off at %s, lost %.1f s"
                                    % (lap, car.code, state["condition"], spin))
                    if self.rng.random() < 0.14:
                        car.retired = True
                        car.retire_lap = lap
                        self.log.append("lap %d: %s beached in the gravel" % (lap, car.code))

                car.total_time += t
                car.trace.append(dict(
                    lap=lap, lap_time=round(t, 3), total=round(car.total_time, 3),
                    compound=car.compound(), wear=round(car.tyre.wear, 3),
                    tyre_temp=round(car.tyre.temp_c, 1), fuel=round(car.fuel, 1),
                    water_mm=state["water_mean_mm"],
                    rain=state["rain_intensity"], sc=sc_active,
                    condition=state["condition"]))

            # overtaking, resolved on the following lap's order
            self._resolve_overtakes(state, sc_active)

        finishers = sorted([c for c in cars if not c.retired],
                           key=lambda c: (-c.laps_done, c.total_time))
        retired = sorted([c for c in cars if c.retired],
                         key=lambda c: -(c.retire_lap or 0))
        classified = finishers + retired
        for pos, c in enumerate(classified, start=1):
            c.position = pos
        leader = finishers[0].total_time if finishers else 0.0
        for c in classified:
            c.gap_to_leader = c.total_time - leader if not c.retired else None
        return self.result()

    def _resolve_overtakes(self, state, sc_active):
        if sc_active:
            return
        alive = sorted([c for c in self.cars if not c.retired],
                       key=lambda c: c.total_time)
        wet = state["water_mean_mm"] > 1.0
        for i in range(len(alive) - 1, 0, -1):
            behind = alive[i]
            ahead = alive[i - 1]
            gap = behind.total_time - ahead.total_time
            if not (0.0 < gap <= 1.0):
                continue
            pace_edge = (ahead.pace_delta - behind.pace_delta) \
                + (self.tm.pace_penalty_s(ahead.tyre, state["water_mean_mm"])
                   - self.tm.pace_penalty_s(behind.tyre, state["water_mean_mm"]))
            p = 0.30 + 0.42 * max(0.0, pace_edge)          # DRS-assisted
            p *= 0.55 if wet else 1.0                      # harder in the rain
            p = max(0.0, min(0.85, p))
            if self.rng.random() < p:
                swap = gap + 0.12
                behind.total_time -= swap
                ahead.total_time += 0.10

    # --------------------------------------------------------------- results
    def result(self):
        rows = []
        for c in sorted(self.cars, key=lambda c: c.position):
            rows.append(dict(
                pos=c.position, code=c.code, team=c.team, grid=c.grid,
                laps=c.laps_done, retired=c.retired, retire_lap=c.retire_lap,
                total_s=round(c.total_time, 3),
                gap_s=(round(c.gap_to_leader, 3) if c.gap_to_leader is not None else None),
                stops=len(c.pit_laps), pit_laps=list(c.pit_laps),
                stints=[dict(compound=s["compound"],
                             laps=(s["laps"] or (c.laps_done - s["start_lap"])))
                        for s in c.stints],
                best_lap=round(min((t["lap_time"] for t in c.trace), default=0.0), 3),
            ))
        return dict(
            laps_completed=max((c.laps_done for c in self.cars), default=0),
            scheduled_laps=self.laps,
            red_flag_lap=self.red_flag_lap,
            half_points=self.half_points,
            safety_car_laps=sorted(self.safety_car_laps),
            calibration=self.calibration,
            weather=self.weather.history,
            classification=rows,
            events=list(self.log),
            traces={c.code: c.trace for c in self.cars},
        )

    def points(self, result=None):
        result = result or self.result()
        table = [25, 18, 15, 12, 10, 8, 6, 4, 2, 1]
        factor = 0.5 if result["half_points"] else 1.0
        out = []
        for row in result["classification"]:
            if row["retired"] or row["pos"] > 10:
                pts = 0.0
            else:
                pts = table[row["pos"] - 1] * factor
            out.append((row["pos"], row["code"], pts))
        return out

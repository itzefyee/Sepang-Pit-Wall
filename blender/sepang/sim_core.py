"""
Physics and environment core for the Sepang race simulation. Pure Python: no
Blender dependency, so it can be run and checked on its own.

Contents
--------
LapTimeModel   quasi-steady-state lap simulation over the real centreline
               (corner-limited speed, power/drag-limited acceleration, braking),
               so lap time responds to grip, fuel mass, DRS and standing water
               instead of being a lookup table.
TyreModel      per-compound degradation with thermal state, a wear cliff and
               stochastic spread, exposing P10/P50/P90 stint quantiles.
WeatherEngine  tropical monsoon: convective cell arrival, rain intensity 0-10,
               per-sector water depth with Sepang's known drainage asymmetry,
               and track drying.
"""

import math
import random

G = 9.80665

# --------------------------------------------------------------------------
# car / physics constants (2026 regulations)
# --------------------------------------------------------------------------
CAR = dict(
    mass_dry_kg=768.0,          # 2026 minimum weight including driver
    fuel_start_kg=100.0,
    power_w=740000.0,           # ~992 hp combined ICE + ERS
    cda_closed=1.55,
    cda_drs=1.24,
    air_density=1.155,          # 32 C, sea level, high humidity
    mu_mech=1.58,               # mechanical grip coefficient, slicks on dry
    aero_grip_k=7.9e-4,         # added lateral g per (m/s)^2
    a_lat_cap_g=5.4,
    mu_brake=1.72,
    brake_aero_k=9.2e-4,
    a_brake_cap_g=5.6,
    a_traction_cap_g=1.55,
    v_max=101.0,                # 364 km/h aero/gearing ceiling
    # Tyre load sensitivity: grip rises slower than load, so a heavy car is
    # slower everywhere, not just under acceleration. Auto-calibrated by
    # LapTimeModel.calibrate() to the measured Sepang fuel effect.
    load_sensitivity=0.76,
    # Standing-water grip law, grip = 1 / (1 + a * depth_mm^b), fitted so that
    # wet-tyre lap times land on the 1:55-2:05 band seen in Sepang rain races.
    water_a=0.2422,
    water_b=0.75,
    water_grip_floor=0.34,
)

FUEL_EFFECT_S_PER_KG = 0.032    # measured Sepang fuel correction

# Sepang reference times used for calibration (2017 event, the last F1 running)
REFERENCE = dict(
    pole_s=90.076,              # Hamilton, 2017 qualifying
    race_lap_record_s=94.080,   # Ricciardo, 2017 race fastest lap
    laps=56,
    pit_loss_s=21.5,            # measured pit-lane delta at Sepang
)


class LapTimeModel:
    """
    Quasi-steady-state lap simulation.

    Speed at each centreline sample is capped by the corner radius and the
    available lateral grip, then a forward pass applies power/traction limits
    and a backward pass applies braking limits. Iterated around the closed loop
    until it converges, which is the standard approach for a track-accurate
    lap-time estimate without a full vehicle model.
    """

    def __init__(self, track, car=None):
        self.track = track
        self.car = dict(CAR)
        if car:
            self.car.update(car)
        self.sp = track["spacing_m"]
        self.n = track["n"]
        self.radius = []
        for k in track["curvature"]:
            self.radius.append(1e9 if abs(k) < 1e-9 else 1.0 / abs(k))
        self.grade = self._grades(track)
        self.drs_mask = self._drs_mask(track)
        self.sector_of = self._sector_of(track)
        self._calibration = 1.0

    def _grades(self, track):
        elev = track["elevation_m"]
        n = len(elev)
        sp = track["spacing_m"]
        return [(elev[(i + 1) % n] - elev[i]) / sp for i in range(n)]

    def _drs_mask(self, track):
        n = track["n"]
        mask = [False] * n
        for z in track["drs_zones"]:
            i, j = z["i_start"], z["i_end"]
            span = (j - i) % n
            for d in range(span + 1):
                mask[(i + d) % n] = True
        return mask

    def _sector_of(self, track):
        n = track["n"]
        sp = track["spacing_m"]
        out = [1] * n
        for s in track.get("sectors", []):
            i0 = int(s["start_m"] / sp)
            i1 = int(s["end_m"] / sp)
            for i in range(i0, min(i1, n)):
                out[i] = s["id"]
        return out

    # ---------------------------------------------------------------- limits
    def mass_grip_factor(self, mass):
        c = self.car
        return (c["mass_dry_kg"] / max(1.0, mass)) ** c["load_sensitivity"]

    def water_grip_factor(self, depth_mm):
        c = self.car
        if depth_mm <= 0.0:
            return 1.0
        g = 1.0 / (1.0 + c["water_a"] * depth_mm ** c["water_b"])
        return max(c["water_grip_floor"], g)

    def lateral_g(self, v, grip):
        c = self.car
        return min(c["a_lat_cap_g"], grip * (c["mu_mech"] + c["aero_grip_k"] * v * v))

    def brake_g(self, v, grip):
        c = self.car
        return min(c["a_brake_cap_g"], grip * (c["mu_brake"] + c["brake_aero_k"] * v * v))

    def drive_force(self, v, mass, drs):
        c = self.car
        v = max(v, 4.0)
        f_power = c["power_w"] / v
        f_trac = c["a_traction_cap_g"] * G * mass
        cda = c["cda_drs"] if drs else c["cda_closed"]
        f_drag = 0.5 * c["air_density"] * cda * v * v
        return min(f_power, f_trac) - f_drag

    def drag_decel(self, v, mass, drs):
        c = self.car
        cda = c["cda_drs"] if drs else c["cda_closed"]
        return 0.5 * c["air_density"] * cda * v * v / mass

    # ------------------------------------------------------------------- lap
    def lap(self, grip=1.0, fuel_kg=0.0, drs_enabled=True, wet_depth_mm=0.0,
            water_by_sector=None, detail=False):
        """
        Returns dict(time_s, sector_s, v_profile, top_speed_kph).
        `grip` is the multiplier from tyre state; water is handled separately so
        aquaplaning can be sector-local.
        """
        c = self.car
        n, sp = self.n, self.sp
        mass = c["mass_dry_kg"] + fuel_kg
        mass_f = self.mass_grip_factor(mass)

        def local_grip(i):
            depth = wet_depth_mm
            if water_by_sector:
                depth = water_by_sector.get(self.sector_of[i], wet_depth_mm)
            return grip * mass_f * self.water_grip_factor(depth)

        v = [0.0] * n
        for i in range(n):
            gi = local_grip(i)
            r = self.radius[i]
            # solve v^2 = a_lat(v) * R with the aero term included
            vv = min(c["v_max"], math.sqrt(max(1.0, self.lateral_g(0.0, gi) * G * r)))
            for _ in range(6):
                a = self.lateral_g(vv, gi) * G
                vv_new = math.sqrt(max(1.0, a * r))
                vv = min(c["v_max"], 0.5 * (vv + vv_new))
            v[i] = vv

        for _ in range(3):
            # forward: traction / power limited
            for i in range(n):
                j = (i + 1) % n
                gi = local_grip(i)
                f = self.drive_force(v[i], mass, drs_enabled and self.drs_mask[i])
                a = f / mass - G * self.grade[i]
                v_next = math.sqrt(max(1.0, v[i] * v[i] + 2.0 * a * sp))
                v[j] = min(v[j], v_next, c["v_max"])
            # backward: braking limited
            for i in range(n - 1, -1, -1):
                j = (i + 1) % n
                gi = local_grip(i)
                ab = self.brake_g(v[j], gi) * G + self.drag_decel(v[j], mass, False) \
                    + G * self.grade[i]
                v_prev = math.sqrt(max(1.0, v[j] * v[j] + 2.0 * ab * sp))
                v[i] = min(v[i], v_prev)

        t = 0.0
        sector_t = {1: 0.0, 2: 0.0, 3: 0.0}
        for i in range(n):
            j = (i + 1) % n
            vm = max(2.0, 0.5 * (v[i] + v[j]))
            dt = sp / vm
            t += dt
            sector_t[self.sector_of[i]] = sector_t.get(self.sector_of[i], 0.0) + dt
        t *= self._calibration
        for k in sector_t:
            sector_t[k] *= self._calibration
        out = dict(time_s=t, sector_s=sector_t,
                   top_speed_kph=max(v) * 3.6,
                   min_speed_kph=min(v) * 3.6)
        if detail:
            out["v_profile"] = v
        return out

    def fuel_effect_s_per_kg(self, fuel_hi=100.0):
        a = self.lap(grip=1.0, fuel_kg=0.0)["time_s"]
        b = self.lap(grip=1.0, fuel_kg=fuel_hi)["time_s"]
        return (b - a) / fuel_hi

    def build_surface(self, **kwargs):
        """Attach a precomputed physics response surface (see LapTimeSurface)."""
        self.surface = LapTimeSurface(self, **kwargs)
        return self.surface

    def lap_time(self, tyre_penalty_s=0.0, fuel_kg=0.0, water_by_sector=None,
                 wet_depth_mm=0.0, drs_enabled=True, extra_s=0.0):
        """
        Full lap time = physics (mass + standing water) + tyre pace penalty.

        Tyre effects are priced in seconds rather than folded into grip, so a
        published delta such as "+10 s for slicks in the wet" shows up as
        exactly that in the lap time.

        Uses the precomputed surface when one is attached, which is what makes
        an exhaustive strategy search and Monte Carlo runs affordable.
        """
        surf = getattr(self, "surface", None)
        if surf is not None and drs_enabled:
            phys, sectors = surf.time(fuel_kg, water_by_sector, wet_depth_mm)
            return dict(time_s=phys + tyre_penalty_s + extra_s,
                        physics_s=phys, sector_s=sectors,
                        tyre_penalty_s=tyre_penalty_s)
        r = self.lap(grip=1.0, fuel_kg=fuel_kg, drs_enabled=drs_enabled,
                     wet_depth_mm=wet_depth_mm, water_by_sector=water_by_sector)
        r["physics_s"] = r["time_s"]
        r["tyre_penalty_s"] = tyre_penalty_s
        r["time_s"] = r["time_s"] + tyre_penalty_s + extra_s
        return r

    def calibrate(self, target_s=None, grip=1.0, fuel_kg=8.0,
                  fuel_target=FUEL_EFFECT_S_PER_KG, iterations=3):
        """
        Two-parameter calibration against published Sepang numbers:
          * overall time scale  -> 2017 pole lap (centreline sim runs long,
            because the real racing line is shorter and straighter)
          * load sensitivity   -> measured 0.032 s/kg fuel effect
        """
        target_s = target_s or REFERENCE["pole_s"]
        raw0 = None
        lo, hi = 0.0, 3.0
        for _ in range(iterations):
            self._calibration = 1.0
            raw = self.lap(grip=grip, fuel_kg=fuel_kg)["time_s"]
            if raw0 is None:
                raw0 = raw
            self._calibration = target_s / raw
            lo, hi = 0.0, 3.0
            for _ in range(28):
                mid = 0.5 * (lo + hi)
                self.car["load_sensitivity"] = mid
                if self.fuel_effect_s_per_kg() < fuel_target:
                    lo = mid
                else:
                    hi = mid
            self.car["load_sensitivity"] = 0.5 * (lo + hi)
        return dict(raw_s=raw0, target_s=target_s, factor=self._calibration,
                    load_sensitivity=self.car["load_sensitivity"],
                    fuel_s_per_kg=self.fuel_effect_s_per_kg())


class LapTimeSurface:
    """
    Precomputed physics lap/sector times over a (fuel mass, water depth) grid.

    The quasi-steady-state solver is far too slow to call inside an exhaustive
    strategy search, but its output is smooth in both fuel and water, so a
    modest grid plus bilinear interpolation reproduces it closely. Sector times
    are stored separately, which lets a lap be assembled from three different
    water depths - exactly what Sepang's uneven drainage requires.
    """

    WATER_AXIS = [0.0, 0.25, 0.5, 1.0, 1.5, 2.0, 3.0, 4.0, 6.0, 8.0, 10.0,
                  12.0, 14.0]

    def __init__(self, model, fuel_max=110.0, n_fuel=12):
        self.model = model
        self.fuel_axis = [fuel_max * i / (n_fuel - 1) for i in range(n_fuel)]
        self.water_axis = list(self.WATER_AXIS)
        self.grid = []
        for f in self.fuel_axis:
            row = []
            for w in self.water_axis:
                r = model.lap(grip=1.0, fuel_kg=f, wet_depth_mm=w)
                row.append((r["time_s"], dict(r["sector_s"])))
            self.grid.append(row)

    def _bracket(self, axis, v):
        if v <= axis[0]:
            return 0, 0, 0.0
        if v >= axis[-1]:
            return len(axis) - 1, len(axis) - 1, 0.0
        for i in range(len(axis) - 1):
            if axis[i] <= v <= axis[i + 1]:
                span = axis[i + 1] - axis[i]
                return i, i + 1, (v - axis[i]) / span if span else 0.0
        return len(axis) - 1, len(axis) - 1, 0.0

    def sector_time(self, sector, fuel_kg, water_mm):
        i0, i1, ft = self._bracket(self.fuel_axis, fuel_kg)
        j0, j1, wt = self._bracket(self.water_axis, water_mm)
        a = self.grid[i0][j0][1][sector]
        b = self.grid[i0][j1][1][sector]
        c = self.grid[i1][j0][1][sector]
        d = self.grid[i1][j1][1][sector]
        top = a + (b - a) * wt
        bot = c + (d - c) * wt
        return top + (bot - top) * ft

    def time(self, fuel_kg, water_by_sector=None, water_mm=0.0):
        sectors = {}
        for s in (1, 2, 3):
            w = water_mm
            if water_by_sector:
                w = water_by_sector.get(s, water_mm)
            sectors[s] = self.sector_time(s, fuel_kg, w)
        return sum(sectors.values()), sectors


# --------------------------------------------------------------------------
# tyres
# --------------------------------------------------------------------------
COMPOUNDS = {
    # pace_delta_s : dry lap-time offset vs the soft on a fresh tyre
    # wear_per_lap : fraction of usable life consumed per lap at Sepang
    # cliff_at     : wear fraction where the compound falls off a cliff
    "soft": dict(label="C4 Soft", colour="red", pace_delta_s=0.00,
                 wear_per_lap=0.042, cliff_at=0.80, cliff_loss_s=2.6,
                 deg_s_per_wear=2.35, warmup_laps=1.0, temp_window=(88, 108),
                 wet_capable=False),
    "medium": dict(label="C3 Medium", colour="yellow", pace_delta_s=0.62,
                   wear_per_lap=0.030, cliff_at=0.86, cliff_loss_s=2.0,
                   deg_s_per_wear=1.85, warmup_laps=1.6, temp_window=(92, 112),
                   wet_capable=False),
    "hard": dict(label="C2 Hard", colour="white", pace_delta_s=1.28,
                 wear_per_lap=0.023, cliff_at=0.92, cliff_loss_s=1.5,
                 deg_s_per_wear=1.40, warmup_laps=2.4, temp_window=(96, 118),
                 wet_capable=False),
    "intermediate": dict(label="Intermediate", colour="green", pace_delta_s=6.10,
                         wear_per_lap=0.040, cliff_at=0.80, cliff_loss_s=3.0,
                         deg_s_per_wear=2.8, warmup_laps=1.0, temp_window=(50, 80),
                         wet_capable=True, best_depth_mm=(0.4, 3.0)),
    "wet": dict(label="Full Wet", colour="blue", pace_delta_s=10.80,
                wear_per_lap=0.036, cliff_at=0.78, cliff_loss_s=3.4,
                deg_s_per_wear=3.1, warmup_laps=1.0, temp_window=(40, 65),
                wet_capable=True, best_depth_mm=(2.5, 12.0)),
}

# Sepang is one of the most abrasive, hottest surfaces on the calendar.
TRACK_SEVERITY = 1.24
SLICK_IN_WET_PENALTY_S = 10.0     # doc bar: +10 s for slicks on a wet track


class TyreState:
    def __init__(self, compound, age_laps=0.0, wear=0.0, temp_c=95.0,
                 spread=0.0):
        self.compound = compound
        self.age_laps = age_laps
        self.wear = wear                 # 0 = new, 1 = fully used
        self.temp_c = temp_c
        self.spread = spread             # per-set luck, -1..+1

    def copy(self):
        return TyreState(self.compound, self.age_laps, self.wear, self.temp_c,
                         self.spread)


class TyreModel:
    """
    Wear-driven degradation with a cliff, thermal state and per-set spread.

    Wear rate scales with fuel load (mass), track severity, ambient temperature
    and how far the tyre is from its working window - and collapses on a wet
    track, where slicks stop wearing but stop working too.
    """

    def __init__(self, rng=None):
        self.rng = rng or random.Random(0xF1)

    def new_set(self, compound, spread_sigma=0.55):
        """
        spread_sigma is set-to-set manufacturing//conditioning luck; +-1 sigma
        moves the wear rate by roughly 9%, which is what drives the width of the
        P10/P90 stint band.
        """
        return TyreState(compound, spread=self.rng.gauss(0.0, spread_sigma))

    def wear_increment(self, state, fuel_kg, air_temp_c=32.0, water_mm=0.0,
                       push_level=1.0):
        c = COMPOUNDS[state.compound]
        base = c["wear_per_lap"] * TRACK_SEVERITY
        mass_factor = 1.0 + 0.0016 * fuel_kg
        temp_factor = 1.0 + 0.020 * (air_temp_c - 30.0)
        wet_factor = 1.0
        if water_mm > 0.2:
            # a wet track is cool and slippery: much less abrasion
            wet_factor = max(0.25, 1.0 - 0.18 * water_mm)
        spread = 1.0 + 0.16 * state.spread
        return base * mass_factor * temp_factor * wet_factor * spread * push_level

    def step_lap(self, state, fuel_kg, air_temp_c=32.0, track_temp_c=48.0,
                 water_mm=0.0, push_level=1.0):
        state.age_laps += 1.0
        state.wear = min(1.35, state.wear +
                         self.wear_increment(state, fuel_kg, air_temp_c,
                                             water_mm, push_level))
        lo, hi = COMPOUNDS[state.compound]["temp_window"]
        target = track_temp_c + 46.0 - 22.0 * min(1.0, water_mm / 3.0)
        state.temp_c += 0.55 * (target - state.temp_c)
        return state

    def pace_penalty_s(self, state, water_mm=0.0):
        """
        Lap-time penalty in seconds versus the ideal tyre for the conditions.

        The bulk grip loss from standing water is handled by the physics model
        (LapTimeModel.water_grip_factor) and deliberately NOT repeated here;
        this function only prices the *choice* of tyre, its wear, temperature
        and warm-up.
        """
        c = COMPOUNDS[state.compound]
        if c["wet_capable"]:
            # wet-pattern tyres are only slow when the track isn't wet enough
            lo_d = c["best_depth_mm"][0]
            dryness = max(0.0, min(1.0, (lo_d - water_mm) / max(0.3, lo_d)))
            pen = c["pace_delta_s"] * dryness
        else:
            pen = c["pace_delta_s"]

        # warm-up on the opening lap of a stint
        if state.age_laps < c["warmup_laps"]:
            pen += 0.55 * (c["warmup_laps"] - state.age_laps)

        # linear degradation up to the cliff, then a knee plus a steepening term
        cliff = c["cliff_at"]
        pen += c["deg_s_per_wear"] * min(state.wear, cliff)
        if state.wear > cliff:
            over = state.wear - cliff
            pen += c["cliff_loss_s"] * over / max(1e-6, 1.0 - cliff)
            pen += 6.0 * over * over

        # thermal window
        lo, hi = c["temp_window"]
        if state.temp_c < lo:
            pen += 0.045 * (lo - state.temp_c)
        elif state.temp_c > hi:
            pen += 0.055 * (state.temp_c - hi)

        # right tyre for the conditions?
        if not c["wet_capable"]:
            if water_mm > 0.2:
                # a slick cannot clear water at all: this is on top of the
                # physical grip loss everyone suffers
                pen += SLICK_IN_WET_PENALTY_S * min(1.0, water_mm / 2.0)
        else:
            lo_d, hi_d = c["best_depth_mm"]
            if water_mm > hi_d:
                pen += 1.9 * (water_mm - hi_d) / hi_d
        return pen

    def usable_life_laps(self, compound, fuel_kg=65.0, air_temp_c=32.0):
        """Laps until the compound reaches its cliff at Sepang."""
        st = TyreState(compound)
        laps = 0
        while st.wear < COMPOUNDS[compound]["cliff_at"] and laps < 120:
            st.wear += self.wear_increment(st, fuel_kg, air_temp_c)
            laps += 1
        return laps

    def stint_quantiles(self, compound, laps, fuel_curve, samples=400,
                        air_temp_c=32.0, water_mm=0.0):
        """
        P10/P50/P90 of cumulative stint time loss - the quantile output the
        quality bar asks for. Spread comes from set-to-set variation plus
        per-lap execution noise.
        """
        totals = []
        per_lap = [[] for _ in range(laps)]
        for _ in range(samples):
            st = self.new_set(compound)
            tot = 0.0
            for lap in range(laps):
                fuel = fuel_curve[min(lap, len(fuel_curve) - 1)]
                self.step_lap(st, fuel, air_temp_c=air_temp_c, water_mm=water_mm)
                loss = self.pace_penalty_s(st, water_mm) + self.rng.gauss(0.0, 0.12)
                per_lap[lap].append(loss)
                tot += loss
            totals.append(tot)
        totals.sort()

        def q(vals, p):
            vals = sorted(vals)
            k = min(len(vals) - 1, max(0, int(round(p * (len(vals) - 1)))))
            return vals[k]

        return dict(
            compound=compound, laps=laps, samples=samples,
            total_p10=q(totals, 0.10), total_p50=q(totals, 0.50),
            total_p90=q(totals, 0.90),
            lap_p10=[q(x, 0.10) for x in per_lap],
            lap_p50=[q(x, 0.50) for x in per_lap],
            lap_p90=[q(x, 0.90) for x in per_lap],
        )


# --------------------------------------------------------------------------
# weather
# --------------------------------------------------------------------------
class WeatherEngine:
    """
    Sepang sits 40 km from the equator: the afternoon convective cycle means a
    dry-to-torrential transition inside three or four laps is normal.

    State per lap:
        rain_intensity  0-10 (0 dry, 3 shower, 6 heavy, 9-10 monsoon cell)
        water_mm        standing water depth, per sector
        wetness         0-1 visual/grip wetness, per sector
    Sector 2 drains badly at Sepang and is modelled to pool faster and clear
    slower than sectors 1 and 3.
    """

    SECTOR_DRAINAGE = {1: 1.00, 2: 0.62, 3: 0.85}     # higher = drains faster

    # Water balance constants. Intensity 10 is a monsoon cell at roughly
    # 100 mm/h; a Sepang lap is about 95 s, so that is ~2.9 mm of rain per lap.
    RAIN_MM_PER_LAP_PER_UNIT = 0.29
    RUNOFF_FRACTION = 0.50        # share of standing water shed per lap
    DRY_EVAP_MM = 0.22            # hot-track evaporation once the rain stops
    DRY_SWEEP_MM = 0.30           # water thrown off the line by the field
    MAX_DEPTH_MM = 12.0

    # Equilibrium depths that follow from the constants above:
    #   intensity  4 -> ~2.3 mm mean, ~3.7 mm in sector 2  (heavy shower)
    #   intensity 10 -> ~5.8 mm mean, ~9.4 mm in sector 2  (monsoon, undriveable)
    ABANDON_DEPTH_MM = 5.2        # race-control threshold used by the engine

    def __init__(self, seed=7, air_temp_c=32.0, track_temp_c=52.0,
                 humidity=0.80, cell_probability=0.055, forecast_horizon=8):
        self.rng = random.Random(seed)
        self.air_temp_c = air_temp_c
        self.track_temp_c = track_temp_c
        self.humidity = humidity
        self.cell_probability = cell_probability
        self.forecast_horizon = forecast_horizon
        self.rain_intensity = 0.0
        self.water_mm = {1: 0.0, 2: 0.0, 3: 0.0}
        self.cell = None          # active convective cell
        self.history = []

    # -------------------------------------------------------------- scripting
    def schedule_cell(self, start_lap, peak_intensity, ramp_laps=3,
                      hold_laps=6, decay_laps=8):
        self.scheduled = getattr(self, "scheduled", [])
        self.scheduled.append(dict(start=start_lap, peak=peak_intensity,
                                   ramp=ramp_laps, hold=hold_laps,
                                   decay=decay_laps))
        return self

    def _scheduled_intensity(self, lap):
        best = 0.0
        for c in getattr(self, "scheduled", []):
            t = lap - c["start"]
            if t < 0:
                continue
            if t < c["ramp"]:
                v = c["peak"] * (t + 1) / c["ramp"]
            elif t < c["ramp"] + c["hold"]:
                v = c["peak"]
            elif t < c["ramp"] + c["hold"] + c["decay"]:
                f = (t - c["ramp"] - c["hold"]) / c["decay"]
                v = c["peak"] * (1.0 - f)
            else:
                v = 0.0
            best = max(best, v)
        return best

    # ------------------------------------------------------------------ step
    def step(self, lap, cars_on_track=20):
        sched = self._scheduled_intensity(lap)
        if sched > 0.0:
            self.rain_intensity = sched
        else:
            # stochastic cells
            if self.cell is None:
                if self.rng.random() < self.cell_probability:
                    self.cell = dict(peak=self.rng.uniform(3.0, 9.5),
                                     ramp=self.rng.randint(2, 4),
                                     hold=self.rng.randint(3, 9),
                                     decay=self.rng.randint(5, 12), t=0)
            if self.cell:
                c = self.cell
                t = c["t"]
                if t < c["ramp"]:
                    self.rain_intensity = c["peak"] * (t + 1) / c["ramp"]
                elif t < c["ramp"] + c["hold"]:
                    self.rain_intensity = c["peak"]
                else:
                    f = (t - c["ramp"] - c["hold"]) / max(1, c["decay"])
                    self.rain_intensity = max(0.0, c["peak"] * (1.0 - f))
                c["t"] += 1
                if f_done(c):
                    self.cell = None
            else:
                self.rain_intensity = max(0.0, self.rain_intensity - 1.2)

        # --- water balance per sector -------------------------------------
        # Rainfall adds depth; run-off removes a fraction of the standing water
        # every lap. Because run-off scales with depth, each rain intensity has
        # a bounded equilibrium depth instead of accumulating without limit.
        # Evaporation and 20 cars sweeping the line then clear the rest once the
        # rain stops, which is why tropical tracks dry so fast.
        for s in (1, 2, 3):
            quality = self.SECTOR_DRAINAGE[s]
            rainfall = self.RAIN_MM_PER_LAP_PER_UNIT * self.rain_intensity
            runoff = self.RUNOFF_FRACTION * quality * self.water_mm[s]
            depth = self.water_mm[s] + rainfall - runoff
            if self.rain_intensity < 1.0:
                dry = (self.DRY_EVAP_MM * max(0.0, self.track_temp_c - 28.0) / 20.0
                       + self.DRY_SWEEP_MM * cars_on_track / 20.0) * quality
                depth -= dry * (1.0 - self.rain_intensity)
            self.water_mm[s] = max(0.0, min(self.MAX_DEPTH_MM, depth))

        # temperatures respond to cloud and rain
        cloud = min(1.0, self.rain_intensity / 6.0)
        self.air_temp_c += 0.35 * ((32.0 - 6.5 * cloud) - self.air_temp_c)
        self.track_temp_c += 0.45 * ((52.0 - 22.0 * cloud) - self.track_temp_c)

        state = self.state(lap)
        self.history.append(state)
        return state

    def state(self, lap=None):
        mean_w = sum(self.water_mm.values()) / 3.0
        return dict(
            lap=lap,
            rain_intensity=round(self.rain_intensity, 2),
            water_mm={k: round(v, 3) for k, v in self.water_mm.items()},
            water_mean_mm=round(mean_w, 3),
            wetness={k: round(min(1.0, v / 4.0), 3) for k, v in self.water_mm.items()},
            wetness_mean=round(min(1.0, mean_w / 4.0), 3),
            air_temp_c=round(self.air_temp_c, 1),
            track_temp_c=round(self.track_temp_c, 1),
            condition=self.classify(),
        )

    def classify(self):
        mean_w = sum(self.water_mm.values()) / 3.0
        if self.rain_intensity >= 8.0 or mean_w > 7.0:
            return "monsoon"
        if self.rain_intensity >= 5.0 or mean_w > 3.5:
            return "heavy rain"
        if self.rain_intensity >= 2.0 or mean_w > 1.2:
            return "light rain"
        if mean_w > 0.25:
            return "damp / drying"
        return "dry"

    def forecast(self, laps=None):
        """Cheap deterministic look-ahead used by the strategy templates."""
        laps = laps or self.forecast_horizon
        out = []
        r = self.rain_intensity
        for k in range(laps):
            sched = self._scheduled_intensity((self.history[-1]["lap"] if self.history else 0) + k + 1)
            r = sched if sched > 0 else max(0.0, r - 0.9)
            out.append(round(r, 2))
        return out


def f_done(cell):
    return cell["t"] >= cell["ramp"] + cell["hold"] + cell["decay"]

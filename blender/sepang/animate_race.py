"""
Drives the Blender scene from race-simulation output.

Nothing here invents motion. Car positions come from the simulated lap times,
the within-lap speed distribution comes from the same quasi-steady-state solver
that produced those lap times, and the wet-track look, sky and rain density come
from the weather engine's per-lap state.
"""

import math

import bpy

from . import bmat, build_car, environment, geo
from .blender_util import get_collection, clear_collection, smooth_closed
from .build_track import ELEV_SIGMA_M, TRACK_HALF, frames

RAIN_COLLECTION = "Sepang_Rain"
RAIN_NODE = "RainIntensity"


def iter_fcurves(action):
    """
    F-curve access that works on both legacy actions and Blender 4.4+/5.x
    slotted actions, where curves live under layers -> strips -> channelbags.
    """
    if action is None:
        return
    legacy = getattr(action, "fcurves", None)
    if legacy is not None:
        for fc in legacy:
            yield fc
        return
    for layer in getattr(action, "layers", []):
        for strip in getattr(layer, "strips", []):
            for cb in getattr(strip, "channelbags", []):
                for fc in cb.fcurves:
                    yield fc


# --------------------------------------------------------------------------
# racing line and within-lap position
# --------------------------------------------------------------------------
def racing_line_offsets(track, max_offset=None, sigma_m=45.0):
    """
    Lateral offset from the centreline, in metres, positive to the left.
    Cars hug the inside of a corner and drift out on the straights; smoothing
    the result gives a continuous line rather than a series of steps.
    """
    n = track["n"]
    sp = track["spacing_m"]
    curv = track["curvature"]
    amp = max_offset if max_offset is not None else (TRACK_HALF - 2.4)
    raw = []
    for k in curv:
        strength = min(1.0, abs(k) * 140.0)
        raw.append((-1.0 if k < 0 else 1.0) * -amp * strength if k != 0 else 0.0)
    # apex-in means offset toward the inside: inside of a right-hander (k<0) is
    # the right-hand side, i.e. negative lateral offset
    fixed = []
    for i, k in enumerate(curv):
        strength = min(1.0, abs(k) * 140.0)
        side = -1.0 if k < 0 else 1.0        # +1 = left = inside of a left turn
        fixed.append(side * amp * strength)
    return smooth_closed(fixed, sigma_m / sp)


class LapProfile:
    """Time-to-distance map for one lap, built from the physics speed profile."""

    def __init__(self, model, water_mm=0.0, fuel_kg=60.0):
        r = model.lap(grip=1.0, fuel_kg=fuel_kg, wet_depth_mm=water_mm,
                      detail=True)
        self.v = r["v_profile"]
        self.sp = model.sp
        self.n = model.n
        self.cum_t = [0.0]
        for i in range(self.n):
            j = (i + 1) % self.n
            vm = max(2.0, 0.5 * (self.v[i] + self.v[j]))
            self.cum_t.append(self.cum_t[-1] + self.sp / vm)
        self.total_t = self.cum_t[-1]

    def distance_at(self, frac_of_lap_time):
        """frac in [0,1) of the lap's elapsed time -> distance along the lap."""
        target = max(0.0, min(0.999999, frac_of_lap_time)) * self.total_t
        lo, hi = 0, self.n
        while lo < hi - 1:
            mid = (lo + hi) // 2
            if self.cum_t[mid] <= target:
                lo = mid
            else:
                hi = mid
        span = self.cum_t[lo + 1] - self.cum_t[lo]
        f = 0.0 if span <= 0 else (target - self.cum_t[lo]) / span
        return (lo + f) * self.sp

    def speed_at_distance(self, s):
        i = int(s / self.sp) % self.n
        return self.v[i]


class TrackSpace:
    """Maps (lap distance, lateral offset) to a world transform on the track."""

    def __init__(self, track):
        self.track = track
        self.n = track["n"]
        self.sp = track["spacing_m"]
        self.pts = track["points"]
        self.elev = smooth_closed(track["elevation_m"], ELEV_SIGMA_M / self.sp)
        self.tan, self.nor = frames(self.pts)
        self.line = racing_line_offsets(track)
        self.length = track["length_m"]

    def sample(self, s, lateral_extra=0.0, ride_height=0.0):
        s = s % self.length
        f = s / self.sp
        i = int(f) % self.n
        j = (i + 1) % self.n
        t = f - int(f)
        px = self.pts[i][0] * (1 - t) + self.pts[j][0] * t
        py = self.pts[i][1] * (1 - t) + self.pts[j][1] * t
        z = self.elev[i] * (1 - t) + self.elev[j] * t
        nx = self.nor[i][0] * (1 - t) + self.nor[j][0] * t
        ny = self.nor[i][1] * (1 - t) + self.nor[j][1] * t
        nl = math.hypot(nx, ny) or 1.0
        nx, ny = nx / nl, ny / nl
        off = self.line[i] * (1 - t) + self.line[j] * t + lateral_extra
        tx = self.tan[i][0] * (1 - t) + self.tan[j][0] * t
        ty = self.tan[i][1] * (1 - t) + self.tan[j][1] * t
        heading = math.atan2(ty, tx)
        return ((px + nx * off, py + ny * off, z + ride_height), heading)


# --------------------------------------------------------------------------
# rain
# --------------------------------------------------------------------------
def build_rain_curtain(camera, layers=3):
    """
    Camera-locked rain: a few transparent planes in front of the lens carrying
    scrolling streaks.

    A particle emitter parented to a moving camera does not work here - at
    250 km/h the drops are left behind the moment they spawn - so the rain is
    rendered as a curtain that travels with the view instead. Density is driven
    by the same "RainIntensity" value node the weather engine keyframes.
    """
    clear_collection(RAIN_COLLECTION)
    col = get_collection(RAIN_COLLECTION)

    mat = bpy.data.materials.get("SEP_RainCurtain")
    if mat is None:
        mat = bpy.data.materials.new("SEP_RainCurtain")
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    out.location = (700, 0)
    emit = nt.nodes.new("ShaderNodeBsdfPrincipled")
    emit.location = (420, 0)
    emit.inputs["Base Color"].default_value = (0.78, 0.83, 0.90, 1.0)
    emit.inputs["Roughness"].default_value = 0.25
    nt.links.new(emit.outputs[0], out.inputs["Surface"])

    tc = nt.nodes.new("ShaderNodeTexCoord")
    tc.location = (-1200, 0)
    mapping = nt.nodes.new("ShaderNodeMapping")
    mapping.location = (-1000, 0)
    mapping.inputs["Scale"].default_value = (95.0, 2.2, 1.0)
    nt.links.new(tc.outputs["UV"], mapping.inputs["Vector"])

    streak = nt.nodes.new("ShaderNodeTexWave")
    streak.location = (-800, 120)
    streak.wave_type = 'BANDS'
    streak.bands_direction = 'X'
    streak.wave_profile = 'SIN'
    streak.inputs["Scale"].default_value = 1.0
    streak.inputs["Distortion"].default_value = 1.5
    streak.inputs["Detail"].default_value = 1.0
    nt.links.new(mapping.outputs["Vector"], streak.inputs["Vector"])

    breakup = nt.nodes.new("ShaderNodeTexNoise")
    breakup.location = (-800, -160)
    breakup.inputs["Scale"].default_value = 7.0
    breakup.inputs["Detail"].default_value = 2.0
    nt.links.new(mapping.outputs["Vector"], breakup.inputs["Vector"])

    mul = nt.nodes.new("ShaderNodeMath")
    mul.location = (-560, 0)
    mul.operation = 'MULTIPLY'
    nt.links.new(streak.outputs["Fac"], mul.inputs[0])
    nt.links.new(breakup.outputs["Fac"], mul.inputs[1])

    sharpen = nt.nodes.new("ShaderNodeMath")
    sharpen.location = (-380, 0)
    sharpen.operation = 'POWER'
    sharpen.inputs[1].default_value = 7.0
    nt.links.new(mul.outputs[0], sharpen.inputs[0])

    rain = nt.nodes.new("ShaderNodeValue")
    rain.name = rain.label = RAIN_NODE
    rain.location = (-380, -240)
    rain.outputs[0].default_value = 0.0

    gain = nt.nodes.new("ShaderNodeMath")
    gain.location = (-180, -120)
    gain.operation = 'MULTIPLY'
    nt.links.new(sharpen.outputs[0], gain.inputs[0])
    nt.links.new(rain.outputs[0], gain.inputs[1])

    boost = nt.nodes.new("ShaderNodeMath")
    boost.location = (40, -120)
    boost.operation = 'MULTIPLY'
    boost.inputs[1].default_value = 5.5
    nt.links.new(gain.outputs[0], boost.inputs[0])
    nt.links.new(boost.outputs[0], emit.inputs["Alpha"])
    bmat._make_transparent(mat, 1.0)

    # scroll the streaks downward over time
    drv = mapping.inputs["Location"].driver_add("default_value", 1)
    drv.driver.type = 'SCRIPTED'
    drv.driver.expression = "frame * -0.55"

    made = []
    for k in range(layers):
        dist = 5.0 + k * 7.5
        w, h = 3.2 * dist, 1.9 * dist
        me = bpy.data.meshes.new("SEP_RainLayer%d" % k)
        me.from_pydata([(-w / 2, -h / 2, 0), (w / 2, -h / 2, 0),
                        (w / 2, h / 2, 0), (-w / 2, h / 2, 0)], [],
                       [(0, 1, 2, 3)])
        uv = me.uv_layers.new(name="UVMap")
        for i, co in enumerate([(0, 0), (1, 0), (1, 1), (0, 1)]):
            uv.data[i].uv = co
        me.update()
        me.materials.append(mat)
        ob = bpy.data.objects.new("SEP_RainLayer%d" % k, me)
        col.objects.link(ob)
        ob.parent = camera
        ob.parent_type = 'OBJECT'
        ob.matrix_parent_inverse.identity()
        ob.location = (0.0, 0.0, -dist)     # camera looks down local -Z
        # a few degrees of tilt per layer reads as rain driven by the car's speed
        ob.rotation_euler = (0.0, 0.0, math.radians(4.0 + 3.0 * k))
        made.append(ob)
    return dict(layers=made, material=mat, value_node=rain)


def build_rain(camera, mats=None):
    """
    Particle rain parented to a camera: a wide emitter above the view with
    gravity-driven streaks. Kept for static cameras; moving shots should use
    build_rain_curtain instead.
    """
    clear_collection(RAIN_COLLECTION)
    col = get_collection(RAIN_COLLECTION)

    mat = bpy.data.materials.get("SEP_RainStreak")
    if mat is None:
        mat = bpy.data.materials.new("SEP_RainStreak")
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Base Color"].default_value = (0.72, 0.78, 0.85, 1.0)
    bsdf.inputs["Roughness"].default_value = 0.08
    if "Transmission Weight" in bsdf.inputs:
        bsdf.inputs["Transmission Weight"].default_value = 0.6
    rain = nt.nodes.new("ShaderNodeValue")
    rain.name = rain.label = RAIN_NODE
    rain.outputs[0].default_value = 0.0
    alpha = nt.nodes.new("ShaderNodeMapRange")
    alpha.inputs["To Min"].default_value = 0.0
    alpha.inputs["To Max"].default_value = 0.85
    nt.links.new(rain.outputs[0], alpha.inputs["Value"])
    nt.links.new(alpha.outputs["Result"], bsdf.inputs["Alpha"])
    nt.links.new(bsdf.outputs[0], out.inputs["Surface"])
    bmat._make_transparent(mat, 0.6)

    # streak instance
    me = bpy.data.meshes.new("SEP_RainDrop")
    verts = [(-0.006, 0, 0), (0.006, 0, 0), (0.006, 0, -0.42), (-0.006, 0, -0.42)]
    me.from_pydata(verts, [], [(0, 1, 2, 3)])
    me.update()
    me.materials.append(mat)
    drop = bpy.data.objects.new("SEP_RainDrop", me)
    col.objects.link(drop)
    drop.hide_render = True
    drop.hide_viewport = True

    emitter = bpy.data.objects.new("SEP_RainEmitter", bpy.data.meshes.new("SEP_RainEmitterMesh"))
    bm_verts = [(-70, -70, 0), (70, -70, 0), (70, 70, 0), (-70, 70, 0)]
    emitter.data.from_pydata(bm_verts, [], [(0, 1, 2, 3)])
    emitter.data.update()
    col.objects.link(emitter)
    emitter.location = (0, 0, 55)
    emitter.parent = camera
    emitter.parent_type = 'OBJECT'
    emitter.matrix_parent_inverse = camera.matrix_world.inverted()

    ps = emitter.modifiers.new("RainSystem", 'PARTICLE_SYSTEM')
    psys = emitter.particle_systems[-1]
    st = psys.settings
    st.count = 26000
    st.frame_start = 1
    st.frame_end = 4000
    st.lifetime = 90
    st.lifetime_random = 0.3
    st.emit_from = 'FACE'
    st.distribution = 'RAND'
    st.use_emit_random = True
    st.normal_factor = -22.0
    st.factor_random = 4.0
    st.physics_type = 'NEWTON'
    st.mass = 0.001
    st.particle_size = 1.0
    st.size_random = 0.4
    st.render_type = 'OBJECT'
    st.instance_object = drop
    st.use_rotation_instance = True
    st.effector_weights.gravity = 1.0
    return dict(emitter=emitter, drop=drop, material=mat,
                value_node=nt.nodes.get(RAIN_NODE))


def attach_car_cameras(car_root, tag="LEC"):
    """
    Broadcast cameras that ride with a car, so the action is always framed:
    a chase camera behind and above, and a cockpit/halo view.
    """
    col = get_collection(environment.CAM_COLLECTION)
    made = {}
    for name, loc, rot_x, lens in (
            ("CAM_Chase_%s" % tag, (-9.5, 0.0, 3.3), 82.0, 34.0),
            ("CAM_Onboard_%s" % tag, (0.20, 0.0, 1.02), 88.0, 26.0),
            ("CAM_Tyre_%s" % tag, (-0.6, 1.85, 0.85), 96.0, 30.0)):
        cam = bpy.data.cameras.get(name) or bpy.data.cameras.new(name)
        cam.lens = lens
        cam.clip_start = 0.05
        cam.clip_end = 12000.0
        ob = bpy.data.objects.get(name)
        if ob is None:
            ob = bpy.data.objects.new(name, cam)
            col.objects.link(ob)
        ob.parent = car_root
        ob.parent_type = 'OBJECT'
        ob.matrix_parent_inverse.identity()
        ob.location = loc
        # camera looks down -Z, so pitch it up to look along the car's +X
        ob.rotation_euler = (math.radians(rot_x), 0.0, math.radians(-90.0))
        if name.startswith("CAM_Tyre"):
            ob.rotation_euler = (math.radians(rot_x), 0.0, math.radians(-150.0))
        made[name] = ob
    return made


def rain_node():
    for name in ("SEP_RainCurtain", "SEP_RainStreak"):
        mat = bpy.data.materials.get(name)
        if mat and mat.use_nodes:
            nd = mat.node_tree.nodes.get(RAIN_NODE)
            if nd:
                return nd
    return None


# --------------------------------------------------------------------------
# weather keyframing
# --------------------------------------------------------------------------
def wetness_nodes():
    out = []
    for name in ("SEP_Asphalt", "SEP_Runoff", "SEP_Kerb", "SEP_Grass"):
        mat = bpy.data.materials.get(name)
        nd = bmat.get_wetness_node(mat)
        if nd:
            out.append(nd)
    return out


def key_weather(frame, water_mm, rain_intensity):
    wet = min(1.0, water_mm / 4.0)
    for nd in wetness_nodes():
        nd.outputs[0].default_value = wet
        nd.outputs[0].keyframe_insert("default_value", frame=frame)
    storm = environment.get_storm_node()
    if storm:
        storm.outputs[0].default_value = min(1.0, rain_intensity / 7.0)
        storm.outputs[0].keyframe_insert("default_value", frame=frame)
    rn = rain_node()
    if rn:
        rn.outputs[0].default_value = min(1.0, rain_intensity / 8.0)
        rn.outputs[0].keyframe_insert("default_value", frame=frame)
    sun = bpy.data.lights.get("SEP_Sun")
    if sun:
        # cloud cover kills the hard shadow but the overcast sky keeps lighting
        # the scene, so the sun never goes fully dark
        sun.energy = 4.0 * (1.0 - 0.82 * min(1.0, rain_intensity / 7.0))
        sun.keyframe_insert("energy", frame=frame)
        sun.angle = math.radians(1.5 + 22.0 * min(1.0, rain_intensity / 7.0))
        sun.keyframe_insert("angle", frame=frame)


# --------------------------------------------------------------------------
# main animation build
# --------------------------------------------------------------------------
def animate(result, track, cars, start_lap=1, n_laps=2, fps=24,
            key_every=2, codes=None, model=None, camera_name=None):
    """
    Keyframe the cars over a window of the race.

    result   : output of RaceEngine.run()
    cars     : {code: {"root": empty, ...}} from build_car.build()
    """
    from .sim_core import LapTimeModel

    scene = bpy.context.scene
    scene.render.fps = fps
    space = TrackSpace(track)
    model = model or LapTimeModel(track)
    if not hasattr(model, "_calibrated_once"):
        model.calibrate()
        model._calibrated_once = True

    codes = codes or [c for c in cars if c in result["traces"]]
    traces = {c: result["traces"][c] for c in codes if result["traces"].get(c)}
    if not traces:
        return dict(frames=0, cars=0)

    # per-lap water depth from the weather history
    water_by_lap = {w["lap"]: w["water_mean_mm"] for w in result["weather"]}
    rain_by_lap = {w["lap"]: w["rain_intensity"] for w in result["weather"]}

    # cache one time/distance profile per distinct water bucket
    profiles = {}

    def profile_for(water):
        key = round(min(8.0, water) * 2.0) / 2.0
        if key not in profiles:
            profiles[key] = LapProfile(model, water_mm=key)
        return profiles[key]

    # absolute race time at the start of each lap, per car
    lap_start = {}
    for code, tr in traces.items():
        acc = 0.0
        starts = {}
        for rec in tr:
            starts[rec["lap"]] = acc
            acc += rec["lap_time"]
        lap_start[code] = starts

    end_lap = min(start_lap + n_laps - 1,
                  max(r["lap"] for r in next(iter(traces.values()))))
    leader = min(traces, key=lambda c: lap_start[c].get(start_lap, 1e9))
    t0 = lap_start[leader].get(start_lap, 0.0)
    t1 = max(lap_start[c].get(end_lap, t0) + traces[c][-1]["lap_time"]
             for c in traces)
    duration = max(1.0, t1 - t0)
    total_frames = int(duration * fps)

    scene.frame_start = 1
    scene.frame_end = total_frames

    # clear old animation
    for code in traces:
        cars[code]["root"].animation_data_clear()
        for w in (cars[code].get("wheels") or []):
            w.animation_data_clear()

    lateral_jitter = {code: 0.9 * math.sin(i * 2.1)
                      for i, code in enumerate(sorted(traces))}

    wheel_angle = {code: 0.0 for code in traces}
    prev_s = {code: None for code in traces}

    for frame in range(1, total_frames + 1, key_every):
        race_t = t0 + (frame - 1) / float(fps)
        for code, tr in traces.items():
            starts = lap_start[code]
            # which lap is this car on?
            lap = None
            for rec in tr:
                if starts[rec["lap"]] <= race_t < starts[rec["lap"]] + rec["lap_time"]:
                    lap = rec
                    break
            if lap is None:
                if race_t < starts[tr[0]["lap"]]:
                    lap = tr[0]
                else:
                    lap = tr[-1]
            f_in_lap = 0.0
            span = lap["lap_time"]
            if span > 0:
                f_in_lap = min(0.9999, max(0.0, (race_t - starts[lap["lap"]]) / span))
            prof = profile_for(water_by_lap.get(lap["lap"], 0.0))
            s = prof.distance_at(f_in_lap)
            pos, heading = space.sample(s, lateral_extra=lateral_jitter[code],
                                        ride_height=0.0)
            ob = cars[code]["root"]
            ob.location = pos
            ob.rotation_euler = (0.0, 0.0, heading)
            ob.keyframe_insert("location", frame=frame)
            ob.keyframe_insert("rotation_euler", frame=frame)

            # spin each wheel about its own axle, from distance travelled
            ds = 0.0 if prev_s[code] is None else (s - prev_s[code]) % space.length
            if ds > space.length * 0.5:
                ds = 0.0                       # ignore the lap wrap
            wheel_angle[code] -= ds / 0.3575
            for w in (cars[code].get("wheels") or []):
                w.rotation_mode = 'XYZ'
                w.rotation_euler = (0.0, wheel_angle[code], 0.0)
                w.keyframe_insert("rotation_euler", frame=frame)
            prev_s[code] = s

        # weather at this instant
        lap_now = None
        for rec in traces[leader]:
            if lap_start[leader][rec["lap"]] <= race_t:
                lap_now = rec["lap"]
        if lap_now is not None:
            key_weather(frame, water_by_lap.get(lap_now, 0.0),
                        rain_by_lap.get(lap_now, 0.0))

    # linear interpolation reads better than Bezier for constant-speed motion
    for code in traces:
        for ob in [cars[code]["root"]] + list(cars[code].get("wheels") or []):
            if ob is None or ob.animation_data is None:
                continue
            for fc in iter_fcurves(ob.animation_data.action):
                for kp in fc.keyframe_points:
                    kp.interpolation = 'LINEAR'

    if camera_name:
        cam = bpy.data.objects.get(camera_name)
        if cam:
            scene.camera = cam
    return dict(frames=total_frames, cars=len(traces), duration_s=duration,
                laps=(start_lap, end_lap),
                water_range=(min(water_by_lap.values()) if water_by_lap else 0,
                             max(water_by_lap.values()) if water_by_lap else 0))

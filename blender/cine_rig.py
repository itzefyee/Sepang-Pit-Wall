"""Cinematic camera rig builder for the Sepang 1-minute highlight.

Why this exists
---------------
Earlier attempts placed cameras with hand-guessed WORLD-space coordinates.
That failed repeatedly: cameras ended up inside the pit wall, below the
terrain, or aimed at empty grass, because the correct offset depends on where
the car is on the circuit and which way it is heading.

This module instead places every camera in CAR-LOCAL space:

    cam_pos = car_pos + right*side + fwd*ahead + up*height

where `fwd` is derived from the car's actual velocity at that frame. A
"trackside left, low, telephoto" shot therefore composes correctly anywhere on
the lap. Every placement is then verified with a raycast to the car, and nudged
along a fallback ladder if a wall or grandstand blocks the sightline.

Two rig types:
  TRACK  - camera pinned in world space, pans to follow the car (broadcast feel)
  RIDER  - camera parented to the car, rides along (onboard / chase / tyre)

Run `build_all()` to construct the rig, then `probe_all()` to render checks.
"""

import bpy
import math
from mathutils import Vector, Matrix

FPS = 24
CINE_COLL = "CINE_RIG"


# ─────────────────────────────────────────────────────────────────────────────
# scene helpers
# ─────────────────────────────────────────────────────────────────────────────

def _coll():
    """Dedicated collection so the rig is easy to find and easy to wipe."""
    c = bpy.data.collections.get(CINE_COLL)
    if c is None:
        c = bpy.data.collections.new(CINE_COLL)
        bpy.context.scene.collection.children.link(c)
    return c


def _link(ob):
    for c in list(ob.users_collection):
        c.objects.unlink(ob)
    _coll().objects.link(ob)
    return ob


def _empty(name):
    ob = bpy.data.objects.get(name)
    if ob is None:
        ob = bpy.data.objects.new(name, None)
        ob.empty_display_size = 2.0
    return _link(ob)


def _camera(name):
    ob = bpy.data.objects.get(name)
    if ob is None:
        ob = bpy.data.objects.new(name, bpy.data.cameras.new(name))
        ob.data.clip_start = 0.05
        ob.data.clip_end = 12000.0
    return _link(ob)


def _clear_constraints(ob):
    for c in list(ob.constraints):
        ob.constraints.remove(c)


def car_state(car, frame):
    """World position and unit heading of `car` at `frame`.

    Heading comes from finite-difference velocity rather than the object's
    rotation, so it is independent of how the car model happens to be oriented.
    """
    sc = bpy.context.scene
    sc.frame_set(frame)
    bpy.context.view_layer.update()
    p0 = car.matrix_world.translation.copy()

    sc.frame_set(frame + 2)
    bpy.context.view_layer.update()
    p1 = car.matrix_world.translation.copy()

    sc.frame_set(frame)
    bpy.context.view_layer.update()

    fwd = (p1 - p0)
    fwd.z = 0.0
    fwd = fwd.normalized() if fwd.length > 1e-5 else Vector((1.0, 0.0, 0.0))
    return p0, fwd


def local_basis(fwd):
    """Right-handed basis from a horizontal heading: (fwd, right, up)."""
    up = Vector((0.0, 0.0, 1.0))
    right = fwd.cross(up).normalized()
    return fwd, right, up


# ─────────────────────────────────────────────────────────────────────────────
# sightline verification
# ─────────────────────────────────────────────────────────────────────────────

def _is_car_part(ob):
    return ob is not None and ob.name.startswith(("CAR_", "CINE_"))


# Objects a camera can legitimately shoot through. The rain layers are large
# semi-transparent volumes that envelop the circuit, so a naive raycast reports
# them as occluders for essentially every shot in the wet acts. Same story for
# the sky backdrop. These must be marched past, not treated as walls.
_SEE_THROUGH_EXACT = {"SEP_Backdrop"}
_SEE_THROUGH_SUBSTR = ("rainlayer", "rain_", "sky", "cloud", "fog", "mist",
                       "volume", "haze")


def _is_see_through(ob):
    if ob is None:
        return True
    if ob.name in _SEE_THROUGH_EXACT:
        return True
    low = ob.name.lower()
    return any(k in low for k in _SEE_THROUGH_SUBSTR)


def sightline_clear(origin, target, max_steps=12):
    """True if no *opaque* geometry sits between `origin` and `target`.

    Marches the ray forward past see-through hits (rain, sky, fog) instead of
    stopping at the first intersection, so atmosphere never counts as a wall.
    """
    sc = bpy.context.scene
    dg = bpy.context.evaluated_depsgraph_get()
    full = target - origin
    total = full.length
    if total < 1e-4:
        return False
    direction = full.normalized()

    travelled = 0.0
    for _ in range(max_steps):
        remaining = total * 0.985 - travelled
        if remaining <= 1e-3:
            return True
        start = origin + direction * travelled
        hit, loc, _n, _i, ob, _m = sc.ray_cast(dg, start, direction,
                                               distance=remaining)
        if not hit:
            return True
        if _is_car_part(ob):
            return True
        if not _is_see_through(ob):
            return False
        # Step just past this transparent surface and keep going.
        travelled = (loc - origin).length + 0.05
    return True


# Progressive rescue moves, applied in order until the car is visible.
# Each tuple scales the requested (side, ahead, height); `ahead` variation lets
# the camera slide along the track to dodge a single post or wall segment.
_FALLBACK = [
    (1.00,  1.00, 1.00),   # as requested
    (1.00,  1.00, 1.60),   # lift over a barrier
    (1.00,  1.00, 2.40),   # lift higher
    (0.55,  1.00, 1.00),   # duck inside the barrier line, same height
    (0.35,  1.00, 1.00),   # right up against the track edge
    (0.35,  1.00, 1.70),   # track edge, lifted
    (-1.00, 1.00, 1.00),   # swap to the far side of the track
    (-0.55, 1.00, 1.20),   # far side, close in
    (1.00, -1.00, 1.30),   # slide down-track to dodge one obstruction
    (1.00,  2.50, 1.30),   # slide up-track instead
    (1.45,  1.00, 1.80),   # stand further back, lifted
    (0.25,  1.00, 0.80),   # hugging the barrier, very low
    (1.00,  1.00, 3.60),   # crane well above everything
    (-0.70, 1.00, 3.20),
]


def solve_track_position(car, frame, side, ahead, height, aim_height):
    """Find a world position for a trackside camera with a clear view of the car.

    Returns (cam_pos, target_pos, attempt_index). attempt_index 0 means the
    requested framing was used unmodified; -1 means every fallback was occluded
    and the last candidate is returned as a best effort.
    """
    car_pos, fwd = car_state(car, frame)
    fwd, right, up = local_basis(fwd)
    target = car_pos + up * aim_height

    last = None
    for i, (s_mul, a_mul, h_mul) in enumerate(_FALLBACK):
        cand = (car_pos
                + right * (side * s_mul)
                + fwd * (ahead * a_mul)
                + up * (height * h_mul))
        last = cand
        if sightline_clear(cand, target):
            return cand, target, i
    return last, target, -1


# ─────────────────────────────────────────────────────────────────────────────
# rig construction
# ─────────────────────────────────────────────────────────────────────────────

def build_track_cam(shot, car):
    """Camera pinned in world space that pans to follow the car."""
    cam = _camera(shot["cam"])
    tgt = _empty("_aim_" + shot["cam"])

    mid = shot["start"] + shot["dur"] // 2
    pos, target, attempt = solve_track_position(
        car, mid,
        side=shot["side"], ahead=shot["ahead"],
        height=shot["height"], aim_height=shot.get("aim_height", 1.2),
    )

    # Aim empty rides with the car so the camera pans through the shot.
    # use_offset=True makes the constraint ADD the car's location to the
    # empty's own location, so the local (0,0,aim_height) survives as a
    # vertical offset. With use_offset=False the constraint would overwrite it.
    _clear_constraints(tgt)
    tgt.parent = None
    tgt.location = Vector((0.0, 0.0, shot.get("aim_height", 1.2)))
    cl = tgt.constraints.new("COPY_LOCATION")
    cl.target = car
    cl.use_offset = True

    cam.parent = None
    cam.location = pos
    _clear_constraints(cam)
    tt = cam.constraints.new("TRACK_TO")
    tt.target = tgt
    tt.track_axis = "TRACK_NEGATIVE_Z"
    tt.up_axis = "UP_Y"

    _apply_lens(cam, shot, tgt)
    return cam, attempt


def build_rider_cam(shot, car):
    """Camera parented to the car so it rides along (onboard / chase / tyre)."""
    cam = _camera(shot["cam"])
    tgt = _empty("_aim_" + shot["cam"])

    mid = shot["start"] + shot["dur"] // 2
    car_pos, fwd = car_state(car, mid)
    fwd, right, up = local_basis(fwd)

    cam_world = (car_pos
                 + right * shot["side"]
                 + fwd * shot["ahead"]
                 + up * shot["height"])
    aim_world = (car_pos
                 + fwd * shot.get("aim_ahead", 12.0)
                 + up * shot.get("aim_height", 1.0))

    # Parent with an inverse matrix captured at the shot's mid-frame, so the
    # rig keeps this exact framing for the whole shot as the car moves.
    inv = car.matrix_world.inverted()

    for ob, world in ((cam, cam_world), (tgt, aim_world)):
        _clear_constraints(ob)
        ob.parent = car
        ob.matrix_parent_inverse = inv
        ob.matrix_basis = Matrix.Translation(world)

    tt = cam.constraints.new("TRACK_TO")
    tt.target = tgt
    tt.track_axis = "TRACK_NEGATIVE_Z"
    tt.up_axis = "UP_Y"

    _apply_lens(cam, shot, tgt)
    return cam, 0


def _apply_lens(cam, shot, focus_target):
    d = cam.data
    d.lens = shot["lens"]
    fstop = shot.get("fstop")
    if fstop:
        d.dof.use_dof = True
        d.dof.focus_object = focus_target
        d.dof.aperture_fstop = fstop
        d.dof.aperture_blades = 7
    else:
        d.dof.use_dof = False


# ─────────────────────────────────────────────────────────────────────────────
# look development
# ─────────────────────────────────────────────────────────────────────────────

def setup_look(samples=32):
    """Motion blur, sampling and grade. Motion blur is the single biggest win
    for a racing clip and was switched off in the scene as found."""
    sc = bpy.context.scene
    r = sc.render

    r.fps = FPS
    r.resolution_x = 1920
    r.resolution_y = 1080
    r.image_settings.file_format = "PNG"
    r.image_settings.compression = 15

    r.use_motion_blur = True
    if hasattr(r, "motion_blur_shutter"):
        r.motion_blur_shutter = 0.55

    ee = sc.eevee
    ee.taa_render_samples = samples
    if hasattr(ee, "use_raytracing"):
        ee.use_raytracing = False          # keeps frame time near ~2s
    for attr, val in (("use_gtao", True), ("gtao_distance", 1.2),
                      ("use_bloom", True), ("bloom_intensity", 0.035),
                      ("use_motion_blur", True), ("motion_blur_shutter", 0.55)):
        if hasattr(ee, attr):
            setattr(ee, attr, val)

    # View transform and look are populated dynamically from the OCIO config,
    # so RNA introspection reports only 'NONE'. Assign directly and let the
    # unsupported names fail through.
    vs = sc.view_settings
    for cand in ("AgX", "Filmic", "Standard"):
        try:
            vs.view_transform = cand
            break
        except TypeError:
            continue
    for cand in ("AgX - Punchy", "Punchy", "AgX - Medium High Contrast",
                 "Medium High Contrast", "None"):
        try:
            vs.look = cand
            break
        except TypeError:
            continue
    vs.exposure = -0.75      # was -1.10; the monsoon act needs the headroom

    # A leftover 1000 W default point light was found in the scene; it flattens
    # the sun's shaping. Keep it out of renders.
    stray = bpy.data.objects.get("Light")
    if stray and stray.type == "LIGHT":
        stray.hide_render = True

    print("look: motion blur on, samples=%d, look=%s, exposure=%.2f"
          % (samples, vs.look, vs.exposure))


def _tune_glare(g):
    """Dial a Glare node toward a subtle fog-glow bloom.

    Blender 5.x moved every Glare setting off the node and onto input sockets,
    with the menus taking display strings ('Fog Glow') rather than enum
    identifiers ('FOG_GLOW'). Older versions keep them as node properties.
    Both are attempted, and anything unsupported is skipped rather than raising.
    """
    g.name = g.label = "CINE_Glare"

    def set_socket(name, value):
        s = g.inputs.get(name)
        if s is None or not hasattr(s, "default_value"):
            return False
        try:
            s.default_value = value
            return True
        except (TypeError, ValueError):
            return False

    # 5.x: settings live on sockets.
    if g.inputs.get("Type") is not None and hasattr(g.inputs["Type"], "default_value"):
        for cand in ("Fog Glow", "Bloom", "FOG_GLOW", "BLOOM"):
            if set_socket("Type", cand):
                break
        set_socket("Quality", "Medium")
        set_socket("Threshold", 0.90)   # only the brightest highlights bloom
        set_socket("Strength", 0.25)    # keep it a sheen, not a haze
        set_socket("Size", 0.60)
        return

    # 4.x and earlier: settings live on the node.
    if hasattr(g, "glare_type"):
        enum = {i.identifier
                for i in type(g).bl_rna.properties["glare_type"].enum_items}
        for cand in ("FOG_GLOW", "BLOOM"):
            if cand in enum:
                g.glare_type = cand
                break
    for attr, val in (("quality", "MEDIUM"), ("mix", -0.72),
                      ("threshold", 0.92), ("size", 8)):
        if hasattr(g, attr):
            try:
                setattr(g, attr, val)
            except (TypeError, ValueError):
                pass


def add_glare():
    """Subtle compositor glare — sells wet asphalt and backlit spray.

    Blender 5.x replaced `scene.node_tree` (Render Layers -> Composite) with
    `scene.compositing_node_group`, a plain node group wired Group Input ->
    Group Output. Both layouts are handled here.
    """
    sc = bpy.context.scene
    sc.use_nodes = True

    # ── Blender 5.x path ──────────────────────────────────────────────────
    # Critical: in 5.x the compositor executes whenever `compositing_node_group`
    # is assigned. `use_nodes = False` does NOT bypass it. A group that exists
    # but is unwired therefore renders every frame pure black, so this must
    # either end up fully wired or be cleared outright. It is rebuilt from
    # scratch each call rather than reused, so a half-built group from a failed
    # run can never persist.
    if hasattr(sc, "compositing_node_group"):
        old = sc.compositing_node_group
        sc.compositing_node_group = None
        if old is not None and old.name.startswith("CINE_Comp"):
            try:
                bpy.data.node_groups.remove(old)
            except (RuntimeError, ReferenceError):
                pass

        ng = bpy.data.node_groups.new("CINE_Comp", "CompositorNodeTree")
        try:
            ng.interface.new_socket(name="Image", in_out="INPUT",
                                    socket_type="NodeSocketColor")
            ng.interface.new_socket(name="Image", in_out="OUTPUT",
                                   socket_type="NodeSocketColor")

            gi = ng.nodes.new("NodeGroupInput")
            go = ng.nodes.new("NodeGroupOutput")
            g = ng.nodes.new("CompositorNodeGlare")
            _tune_glare(g)
            gi.location, g.location, go.location = (-320, 0), (0, 0), (320, 0)

            ng.links.new(gi.outputs[0], g.inputs["Image"])
            ng.links.new(g.outputs["Image"], go.inputs[0])

            # Verify a complete Group Input -> Glare -> Group Output path.
            # Compare by name, not identity: Blender's RNA hands back a fresh
            # Python wrapper on every attribute access, so `l.to_node is g` is
            # False even when the link is correct.
            gi_n, g_n, go_n = gi.name, g.name, go.name
            into_glare = any(l.from_node.name == gi_n and l.to_node.name == g_n
                             for l in ng.links)
            out_of_glare = any(l.from_node.name == g_n and l.to_node.name == go_n
                               for l in ng.links)
            if not (into_glare and out_of_glare):
                raise RuntimeError("glare group did not wire up")
        except Exception as exc:
            bpy.data.node_groups.remove(ng)
            sc.compositing_node_group = None
            print("compositor: glare skipped (%s); rendering straight through"
                  % exc)
            return

        sc.compositing_node_group = ng
        print("compositor: fog-glow glare added and verified (5.x node group)")
        return

    # ── legacy path (Blender 4.x and earlier) ─────────────────────────────
    nt = getattr(sc, "node_tree", None)
    if nt is None:
        print("compositor: no node tree available, skipping glare")
        return
    if nt.nodes.get("CINE_Glare"):
        return
    rl = next((n for n in nt.nodes if n.type == "R_LAYERS"), None)
    comp = next((n for n in nt.nodes if n.type == "COMPOSITE"), None)
    if not (rl and comp):
        print("compositor: expected nodes missing, skipping glare")
        return
    g = nt.nodes.new("CompositorNodeGlare")
    _tune_glare(g)
    g.location = (rl.location.x + 260, rl.location.y - 160)
    nt.links.new(rl.outputs["Image"], g.inputs["Image"])
    nt.links.new(g.outputs["Image"], comp.inputs["Image"])
    print("compositor: fog-glow glare added (legacy)")


def output_mean(camera_name, frame, res=(320, 180), samples=4):
    """Render a tiny frame and return its mean RGB level.

    Used as a tripwire: a fully black result means something in the output
    chain (most likely the compositor) is swallowing the image, and that is
    worth catching before committing to a 1440-frame render.
    """
    import os
    import tempfile
    sc = bpy.context.scene
    keep = (sc.render.resolution_x, sc.render.resolution_y,
            sc.eevee.taa_render_samples, sc.render.filepath,
            sc.camera, sc.frame_current)
    path = os.path.join(tempfile.gettempdir(), "cine_tripwire.png")
    try:
        sc.render.resolution_x, sc.render.resolution_y = res
        sc.eevee.taa_render_samples = samples
        sc.frame_set(frame)
        sc.camera = bpy.data.objects[camera_name]
        sc.render.filepath = path
        bpy.ops.render.render(write_still=True)
        img = bpy.data.images.load(path, check_existing=False)
        px = list(img.pixels)
        rgb = [px[i] for i in range(len(px)) if i % 4 != 3]
        mean = sum(rgb) / max(len(rgb), 1)
        bpy.data.images.remove(img)
        return mean
    finally:
        (sc.render.resolution_x, sc.render.resolution_y,
         sc.eevee.taa_render_samples, sc.render.filepath,
         sc.camera, _f) = keep
        sc.frame_set(keep[5])


def verify_output(camera_name, frame, threshold=0.01):
    """Confirm renders are not black; disable the compositor if they are."""
    sc = bpy.context.scene
    mean = output_mean(camera_name, frame)
    if mean >= threshold:
        print("output check: ok (mean=%.4f)" % mean)
        return True

    print("output check: BLACK (mean=%.5f) - clearing compositor" % mean)
    if hasattr(sc, "compositing_node_group"):
        ng = sc.compositing_node_group
        sc.compositing_node_group = None
        if ng is not None and ng.name.startswith("CINE_Comp"):
            try:
                bpy.data.node_groups.remove(ng)
            except (RuntimeError, ReferenceError):
                pass
    sc.use_nodes = False

    mean2 = output_mean(camera_name, frame)
    print("output check: after clearing compositor mean=%.4f" % mean2)
    return mean2 >= threshold

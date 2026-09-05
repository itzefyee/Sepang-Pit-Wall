"""
Scene environment for Sepang: tropical sky, sun, render settings and the camera
rig. The world exposes a "StormFactor" Value node (0 = clear equatorial
afternoon, 1 = black monsoon cell overhead) that the weather engine keyframes.
"""

import math

import bpy

from .blender_util import get_collection

STORM_NODE = "StormFactor"
CAM_COLLECTION = "Sepang_Cameras"

# Malaysian GP ran at 15:00 local; sun is high and slightly north at Sepang.
SUN_ELEVATION_DEG = 62.0
SUN_ROTATION_DEG = 205.0


def setup_render(res=(1920, 1080), samples=32):
    sc = bpy.context.scene
    sc.render.engine = 'BLENDER_EEVEE'
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.resolution_percentage = 100
    sc.render.film_transparent = False
    ee = sc.eevee
    for attr, val in (("taa_render_samples", samples), ("taa_samples", 16),
                      ("use_bloom", True), ("use_gtao", True),
                      ("use_ssr", True), ("use_ssr_refraction", True),
                      ("use_raytracing", True), ("use_shadows", True),
                      ("use_volumetric_lights", True)):
        try:
            setattr(ee, attr, val)
        except AttributeError:
            pass
    try:
        sc.view_settings.view_transform = 'AgX'
    except TypeError:
        sc.view_settings.view_transform = 'Filmic'
    sc.view_settings.look = 'None'
    return sc


def setup_world(storm=0.0):
    world = bpy.data.worlds.get("Sepang_Sky")
    if world is None:
        world = bpy.data.worlds.new("Sepang_Sky")
    bpy.context.scene.world = world
    world.use_nodes = True
    nt = world.node_tree
    nt.nodes.clear()

    out = nt.nodes.new("ShaderNodeOutputWorld")
    out.location = (600, 0)
    bg_clear = nt.nodes.new("ShaderNodeBackground")
    bg_clear.location = (200, 150)
    bg_storm = nt.nodes.new("ShaderNodeBackground")
    bg_storm.location = (200, -150)
    mix = nt.nodes.new("ShaderNodeMixShader")
    mix.location = (420, 0)

    sky = nt.nodes.new("ShaderNodeTexSky")
    sky.location = (-150, 200)
    try:
        sky.sky_type = 'NISHITA'
        sky.sun_elevation = math.radians(SUN_ELEVATION_DEG)
        sky.sun_rotation = math.radians(SUN_ROTATION_DEG)
        sky.altitude = 20.0
        sky.air_density = 1.3          # humid equatorial haze
        sky.dust_density = 2.2
        sky.sun_intensity = 1.0
        sky.sun_size = math.radians(0.6)
    except (AttributeError, TypeError):
        pass
    nt.links.new(sky.outputs[0], bg_clear.inputs["Color"])
    bg_clear.inputs["Strength"].default_value = 1.0

    # monsoon cell: near-black cloud base with a little scattered light
    grad = nt.nodes.new("ShaderNodeTexGradient")
    grad.location = (-400, -220)
    grad.gradient_type = 'SPHERICAL'
    storm_ramp = nt.nodes.new("ShaderNodeValToRGB")
    storm_ramp.location = (-200, -220)
    # A monsoon cell is dark but an overcast sky is still a large bright source:
    # too low here and the whole scene renders black instead of gloomy.
    storm_ramp.color_ramp.elements[0].position = 0.15
    storm_ramp.color_ramp.elements[0].color = (0.105, 0.115, 0.135, 1.0)
    storm_ramp.color_ramp.elements[1].position = 0.95
    storm_ramp.color_ramp.elements[1].color = (0.40, 0.425, 0.465, 1.0)
    tc = nt.nodes.new("ShaderNodeTexCoord")
    tc.location = (-600, -220)
    nt.links.new(tc.outputs["Generated"], grad.inputs["Vector"])
    nt.links.new(grad.outputs["Fac"], storm_ramp.inputs["Fac"])
    nt.links.new(storm_ramp.outputs["Color"], bg_storm.inputs["Color"])
    bg_storm.inputs["Strength"].default_value = 2.6

    sf = nt.nodes.new("ShaderNodeValue")
    sf.name = sf.label = STORM_NODE
    sf.location = (200, -350)
    sf.outputs[0].default_value = storm

    nt.links.new(bg_clear.outputs[0], mix.inputs[1])
    nt.links.new(bg_storm.outputs[0], mix.inputs[2])
    nt.links.new(sf.outputs[0], mix.inputs["Fac"])
    nt.links.new(mix.outputs[0], out.inputs["Surface"])
    return world


def get_storm_node():
    w = bpy.context.scene.world
    if w and w.use_nodes:
        return w.node_tree.nodes.get(STORM_NODE)
    return None


def setup_sun(name="SEP_Sun"):
    col = get_collection("Sepang_Lighting")
    lamp = bpy.data.lights.get(name)
    if lamp is None:
        lamp = bpy.data.lights.new(name, type='SUN')
    lamp.energy = 5.0
    lamp.angle = math.radians(1.5)
    lamp.color = (1.0, 0.97, 0.92)
    ob = bpy.data.objects.get(name)
    if ob is None:
        ob = bpy.data.objects.new(name, lamp)
        col.objects.link(ob)
    elif ob.name not in col.objects:
        pass
    el = math.radians(SUN_ELEVATION_DEG)
    az = math.radians(SUN_ROTATION_DEG)
    ob.rotation_euler = (math.pi / 2 - el, 0.0, az)
    ob.location = (0, 0, 400)
    return ob


def add_camera(name, location, look_at, lens=35.0, col=None):
    col = col or get_collection(CAM_COLLECTION)
    cam = bpy.data.cameras.get(name)
    if cam is None:
        cam = bpy.data.cameras.new(name)
    cam.lens = lens
    cam.clip_start = 0.1
    cam.clip_end = 12000.0
    ob = bpy.data.objects.get(name)
    if ob is None:
        ob = bpy.data.objects.new(name, cam)
        col.objects.link(ob)
    ob.location = location
    dx = look_at[0] - location[0]
    dy = look_at[1] - location[1]
    dz = look_at[2] - location[2]
    dist_xy = math.hypot(dx, dy)
    ob.rotation_euler = (math.atan2(dist_xy, -dz), 0.0, math.atan2(dy, dx) - math.pi / 2)
    return ob


def setup_cameras(data):
    pts = data["points"]
    elev = data["elevation_m"]
    n = data["n"]
    sp = data["spacing_m"]
    cx = sum(p[0] for p in pts) / n
    cy = sum(p[1] for p in pts) / n
    cz = sum(elev) / n

    def at(s):
        i = int(round(s / sp)) % n
        return (pts[i][0], pts[i][1], elev[i])

    cams = {}
    cams["CAM_Aerial"] = add_camera("CAM_Aerial", (cx + 900, cy - 1250, cz + 1150),
                                    (cx, cy, cz), lens=38.0)
    t1 = at(640)
    cams["CAM_Turn1"] = add_camera("CAM_Turn1", (t1[0] + 95, t1[1] - 105, t1[2] + 42),
                                   (t1[0], t1[1], t1[2] + 1.0), lens=50.0)
    sf = at(30)
    cams["CAM_StartFinish"] = add_camera("CAM_StartFinish",
                                         (sf[0] - 40, sf[1] - 60, sf[2] + 16),
                                         at(320)[0:2] + (sf[2] + 1.5,), lens=40.0)
    t15 = at(5164)
    cams["CAM_Turn15"] = add_camera("CAM_Turn15", (t15[0] - 70, t15[1] + 80, t15[2] + 30),
                                    (t15[0], t15[1], t15[2] + 1.0), lens=55.0)
    t9 = at(3172)
    cams["CAM_Turn9"] = add_camera("CAM_Turn9", (t9[0] + 60, t9[1] + 55, t9[2] + 25),
                                   (t9[0], t9[1], t9[2] + 1.0), lens=45.0)
    bpy.context.scene.camera = cams["CAM_Aerial"]
    return cams


def build(data):
    setup_render()
    setup_world()
    setup_sun()
    cams = setup_cameras(data)
    return cams

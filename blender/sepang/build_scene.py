"""
Top-level scene assembly. One call rebuilds the whole Sepang circuit in Blender:
materials, track surface, architecture, lighting, sky and the camera rig.
"""

import math
import time

import bpy

from . import bmat, build_structures, build_track, environment, geo
from .blender_util import smooth_closed
from .build_track import ELEV_SIGMA_M, TRACK_HALF, frames, pit_side


def track_frame(data, s, lateral=0.0, height=0.0):
    """World position `lateral` metres left of the centreline at lap distance s."""
    n = data["n"]
    sp = data["spacing_m"]
    pts = data["points"]
    elev = smooth_closed(data["elevation_m"], ELEV_SIGMA_M / sp)
    tan, nor = frames(pts)
    i = int(round(s / sp)) % n
    px, py = pts[i]
    nx, ny = nor[i]
    return (px + nx * lateral, py + ny * lateral, elev[i] + height), tan[i], nor[i]


def place_broadcast_cameras(data):
    ps = pit_side(data)
    stand = -ps                       # grandstand side of the pit straight
    cams = {}

    pos, _, _ = track_frame(data, -140.0, lateral=stand * 33.0, height=11.0)
    look, _, _ = track_frame(data, 280.0, lateral=0.0, height=1.2)
    cams["CAM_StartFinish"] = environment.add_camera("CAM_StartFinish", pos, look, lens=40.0)

    pos, _, _ = track_frame(data, 690.0, lateral=ps * 62.0, height=26.0)
    look, _, _ = track_frame(data, 640.0, lateral=0.0, height=1.0)
    cams["CAM_Turn1"] = environment.add_camera("CAM_Turn1", pos, look, lens=52.0)

    pos, _, _ = track_frame(data, 5210.0, lateral=-45.0, height=22.0)
    look, _, _ = track_frame(data, 5164.0, lateral=0.0, height=1.0)
    cams["CAM_Turn15"] = environment.add_camera("CAM_Turn15", pos, look, lens=48.0)

    pos, _, _ = track_frame(data, 3130.0, lateral=-52.0, height=20.0)
    look, _, _ = track_frame(data, 3172.0, lateral=0.0, height=1.0)
    cams["CAM_Turn9"] = environment.add_camera("CAM_Turn9", pos, look, lens=50.0)

    pos, _, _ = track_frame(data, 4700.0, lateral=40.0, height=15.0)
    look, _, _ = track_frame(data, 4950.0, lateral=0.0, height=1.0)
    cams["CAM_BackStraight"] = environment.add_camera("CAM_BackStraight", pos, look, lens=85.0)

    # circuit overview
    pts = data["points"]
    n = data["n"]
    elev = data["elevation_m"]
    cx = sum(p[0] for p in pts) / n
    cy = sum(p[1] for p in pts) / n
    cz = sum(elev) / n
    cams["CAM_Aerial"] = environment.add_camera(
        "CAM_Aerial", (cx + 640, cy - 940, cz + 820), (cx, cy, cz), lens=45.0)

    # pit straight from above, showing the twin grandstand
    sf, _, _ = track_frame(data, 300.0)
    cams["CAM_PitOverview"] = environment.add_camera(
        "CAM_PitOverview", (sf[0] + 250, sf[1] - 330, sf[2] + 240),
        (sf[0] - 250, sf[1], sf[2]), lens=42.0)
    return cams


def build(rebuild_geometry=True, verbose=True):
    t0 = time.time()
    log = []
    data = geo.build_centreline()
    mats = bmat.build_all()
    mats["seats"] = bmat.simple("SEP_Seats", (0.09, 0.12, 0.19), 0.7)

    if rebuild_geometry:
        _, rep = build_track.build(data, mats)
        log += rep
        _, rep = build_structures.build(data, mats)
        log += rep

    environment.setup_render()
    environment.setup_world()
    environment.setup_sun()
    cams = place_broadcast_cameras(data)
    sc = bpy.context.scene
    sc.view_settings.exposure = -1.1
    sc.camera = cams["CAM_StartFinish"]

    total_faces = sum(len(o.data.polygons) for o in bpy.data.objects
                      if o.type == 'MESH')
    log.append("scene: %d objects, %d faces, built in %.1fs"
               % (len(bpy.data.objects), total_faces, time.time() - t0))
    if verbose:
        print("\n".join(log))
    return data, mats, cams, log


def set_camera(name):
    ob = bpy.data.objects.get(name)
    if ob:
        bpy.context.scene.camera = ob
    for area in bpy.context.screen.areas:
        if area.type == 'VIEW_3D':
            sp = area.spaces.active
            sp.shading.type = 'RENDERED'
            sp.shading.use_scene_world = True
            sp.shading.use_scene_lights = True
            sp.region_3d.view_perspective = 'CAMERA'
            sp.overlay.show_overlays = False
            sp.clip_end = 14000.0
    return ob

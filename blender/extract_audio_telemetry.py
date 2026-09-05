"""Extract per-frame telemetry for audio synthesis.

Run headless:

    & "C:\\Program Files\\Blender Foundation\\Blender 5.2\\blender.exe" `
        -b "blender\\sepang_cine.blend" `
        --python "blender\\extract_audio_telemetry.py"

Writes blender/out/audio_telemetry.json describing, for every frame of every
shot: hero car speed, camera-to-car distance, radial velocity (for Doppler),
storm intensity, and the same distance/velocity data for the two nearest rival
cars so trackside shots can be given a crowded, layered engine mix.

The audio is synthesised from this rather than hand-timed, so engine pitch,
Doppler sweeps and level all stay locked to what is actually on screen.
"""

import json
import os
import sys

import bpy
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import cine_shots  # noqa: E402

CARS = ["CAR_LEC", "CAR_HAM", "CAR_VER", "CAR_NOR",
        "CAP_RUS", "CAR_RUS", "CAR_ALO", "CAR_PIA", "CAR_ANT"]
HERO = "CAR_LEC"
RIVAL_COUNT = 2


def main():
    sc = bpy.context.scene
    fps = sc.render.fps

    cars = [bpy.data.objects[n] for n in CARS if n in bpy.data.objects]
    hero = bpy.data.objects[HERO]
    storm_node = sc.world.node_tree.nodes.get("StormFactor")

    def sample(frame):
        sc.frame_set(frame)
        bpy.context.view_layer.update()
        return {c.name: c.matrix_world.translation.copy() for c in cars}

    out = {"fps": fps, "shots": []}

    for s in cine_shots.SHOTS:
        cam = bpy.data.objects[s["cam"]]
        start, dur = s["start"], s["dur"]

        # Pre-sample one frame beyond the shot so finite differences work at the
        # final frame without clamping.
        pos = {}
        for f in range(start, start + dur + 1):
            pos[f] = sample(f)

        rec = {
            "n": s["n"], "label": s["label"], "kind": s["kind"],
            "act": s["act"], "start": start, "dur": dur, "lens": s["lens"],
            "frames": [],
        }

        for i in range(dur):
            f = start + i
            sc.frame_set(f)
            bpy.context.view_layer.update()
            cam_pos = cam.matrix_world.translation.copy()
            storm = storm_node.outputs[0].default_value if storm_node else 0.0

            # Hero speed from finite difference.
            p0 = pos[f][HERO]
            p1 = pos[f + 1][HERO]
            speed = (p1 - p0).length * fps          # m/s

            entry = {"speed": round(speed, 3), "storm": round(storm, 4)}

            # Distance and radial velocity per car (Doppler + attenuation).
            per_car = []
            for c in cars:
                d0 = (pos[f][c.name] - cam_pos).length
                # Camera may also be moving; recompute its next-frame position.
                sc.frame_set(f + 1)
                bpy.context.view_layer.update()
                cam_next = cam.matrix_world.translation.copy()
                d1 = (pos[f + 1][c.name] - cam_next).length
                sc.frame_set(f)
                bpy.context.view_layer.update()

                v_rad = (d1 - d0) * fps             # +ve = receding
                sp = (pos[f + 1][c.name] - pos[f][c.name]).length * fps
                per_car.append((d0, v_rad, sp, c.name))

            per_car.sort(key=lambda x: x[0])
            hero_rec = next(x for x in per_car if x[3] == HERO)
            entry["dist"] = round(hero_rec[0], 3)
            entry["vrad"] = round(hero_rec[1], 3)

            rivals = [x for x in per_car if x[3] != HERO][:RIVAL_COUNT]
            entry["rivals"] = [
                {"dist": round(d, 3), "vrad": round(v, 3), "speed": round(sp, 3)}
                for d, v, sp, _n in rivals
            ]
            rec["frames"].append(entry)

        out["shots"].append(rec)
        print("  telemetry %02d %-20s %3d frames  speed %.0f-%.0f km/h  dist %.0f-%.0f m"
              % (s["n"], s["label"], dur,
                 min(e["speed"] for e in rec["frames"]) * 3.6,
                 max(e["speed"] for e in rec["frames"]) * 3.6,
                 min(e["dist"] for e in rec["frames"]),
                 max(e["dist"] for e in rec["frames"])), flush=True)

    dest = os.path.join(cine_shots.OUT, "audio_telemetry.json")
    with open(dest, "w") as fh:
        json.dump(out, fh)
    total = sum(len(r["frames"]) for r in out["shots"])
    print("\nwrote %s  (%d shots, %d frames)" % (dest, len(out["shots"]), total))


if __name__ == "__main__":
    main()

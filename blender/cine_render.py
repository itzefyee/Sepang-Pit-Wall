"""Headless render driver for the 1-minute Sepang highlight.

Usage (background render, no GUI):

    & "C:\\Program Files\\Blender Foundation\\Blender 5.2\\blender.exe" `
        -b "blender\\sepang_cine.blend" `
        --python "blender\\cine_render.py"

Writes 1440 PNG frames into blender/out/cine/<NN>_<shot>/f_####.png,
then stitch_cine.ps1 turns them into sepang_cine_highlight.mp4.

Progress is flushed per shot so the log can be tailed while it runs.
"""

import os
import sys
import time

import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import cine_rig      # noqa: E402
import cine_shots    # noqa: E402


def main():
    t_start = time.time()
    sc = bpy.context.scene

    # The rig is saved in the .blend, but rebuild anyway so a fresh checkout of
    # the scripts can render without a pre-built file, and so any shot-list edit
    # takes effect without re-saving the blend.
    cine_shots.build_all()

    sc.render.resolution_x = 1920
    sc.render.resolution_y = 1080
    sc.eevee.taa_render_samples = 16     # verified visually equal to 32 here
    sc.render.image_settings.file_format = "PNG"
    sc.render.image_settings.compression = 15

    total = sum(s["dur"] for s in cine_shots.SHOTS)
    done = 0
    root = os.path.join(cine_shots.OUT, "cine")
    os.makedirs(root, exist_ok=True)

    print("=" * 70, flush=True)
    print("RENDER START  %d shots  %d frames  %.1f s of footage"
          % (len(cine_shots.SHOTS), total, total / cine_shots.FPS), flush=True)
    print("=" * 70, flush=True)

    for s in cine_shots.SHOTS:
        folder = os.path.join(root, "%02d_%s" % (s["n"], s["label"]))
        os.makedirs(folder, exist_ok=True)

        sc.frame_start = s["start"]
        sc.frame_end = s["start"] + s["dur"] - 1
        sc.camera = bpy.data.objects[s["cam"]]
        sc.view_settings.exposure = s["exposure"]
        sc.render.filepath = os.path.join(folder, "f_####")

        t0 = time.time()
        bpy.ops.render.render(animation=True)
        el = time.time() - t0
        done += s["dur"]

        elapsed = time.time() - t_start
        eta = elapsed / done * (total - done)
        print("  [%2d/%2d] %-20s %3d fr  %5.1fs (%.2f s/fr)  "
              "%3d%% done  ETA %.0f min"
              % (s["n"], len(cine_shots.SHOTS), s["label"], s["dur"], el,
                 el / s["dur"], 100 * done // total, eta / 60), flush=True)

    print("=" * 70, flush=True)
    print("RENDER COMPLETE  %d frames in %.1f min"
          % (total, (time.time() - t_start) / 60), flush=True)
    print("Next: .\\stitch_cine.ps1", flush=True)


if __name__ == "__main__":
    main()

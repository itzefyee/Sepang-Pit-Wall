"""Run this from Blender's Scripting workspace to render all 6 highlight
segments. Open sepang_race.blend first, then open this file in the script
editor and press Run Script (Alt+P).

Expected time: ~24 minutes on an RTX 3060 Laptop.
Output: blender/out/highlight/seg_*/frame_####.png
"""
import bpy, os, time

sc = bpy.context.scene

# ── render settings ────────────────────────────────────────────────────────
sc.render.resolution_x = 1920
sc.render.resolution_y = 1080
sc.render.image_settings.file_format = "PNG"
sc.render.image_settings.compression = 15   # fast write
sc.eevee.taa_render_samples = 16
sc.eevee.use_raytracing = False              # disable to avoid 13-hr render

OUT_ROOT = r"c:\Users\spoop\OneDrive\Documents\Class\hackathon\F1\blender\out"

# ── highlight segments ─────────────────────────────────────────────────────
# (folder, start_frame, end_frame, camera)
segments = [
    ("seg_A_pit",      600,  719,  "CAM_StartFinish"),    # 5 s dry, pit straight blast
    ("seg_B_t1",       100,  219,  "CAM_Turn1"),          # 5 s T1 braking zone
    ("seg_C_t15",      900,  995,  "CAM_Turn15"),         # 4 s T15 hairpin
    ("seg_D_rain",    5400, 5543,  "CAM_Chase_LEC"),      # 6 s rain arriving
    ("seg_E_monsoon", 7300, 7491,  "CAM_Chase_LEC"),      # 8 s monsoon peak
    ("seg_F_onboard", 7650, 7793,  "CAM_Onboard_LEC"),   # 6 s wet onboard
]

total = sum(e - s + 1 for _, s, e, _ in segments)
print("Rendering %d frames = %.0f s  (~%.0f min at 1.75s/frame)"
      % (total, total / 24, total * 1.75 / 60))

wall = time.time()
for name, start, end, cam_name in segments:
    folder = os.path.join(OUT_ROOT, "highlight", name)
    os.makedirs(folder, exist_ok=True)
    sc.frame_start = start
    sc.frame_end = end
    sc.camera = bpy.data.objects[cam_name]
    sc.render.filepath = os.path.join(folder, "frame_####")
    print("  %s  [%d-%d, %s]..." % (name, start, end, cam_name), end=" ")
    t0 = time.time()
    bpy.ops.render.render(animation=True)
    print("done in %.0f s" % (time.time() - t0))

print("\nAll segments done in %.0f min." % ((time.time() - wall) / 60))
print("Next step: run stitch_highlight.ps1")

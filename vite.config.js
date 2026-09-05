import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { copyFileSync, existsSync, mkdirSync } from "node:fs";
import { dirname, resolve } from "node:path";

/**
 * The three final Blender renders live at the project root rather than in
 * public/, so they are not duplicated on disk. Vite's dev server already
 * serves project-root files (with Range support, which video seeking needs);
 * this plugin makes sure they also land in dist/ on a production build.
 */
const MEDIA = [
  "sepang_onboard_final.mp4",
  "sepang_pov_final.mp4",
  "sepang_highlight_final.mp4"
];

function copyRootMedia() {
  return {
    name: "copy-root-media",
    apply: "build",
    closeBundle() {
      for (const file of MEDIA) {
        const from = resolve(import.meta.dirname, file);
        if (!existsSync(from)) {
          this.warn(`media missing, not copied to dist: ${file}`);
          continue;
        }
        const to = resolve(import.meta.dirname, "dist", file);
        mkdirSync(dirname(to), { recursive: true });
        copyFileSync(from, to);
      }
    }
  };
}

export default defineConfig({
  plugins: [react(), copyRootMedia()],
  server: {
    port: 5173,
    open: false,
    host: true
  },
  build: {
    rollupOptions: {
      input: {
        pitwall: resolve(import.meta.dirname, "sepang_progress.html")
      }
    }
  }
});

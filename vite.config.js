import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { resolve } from "node:path";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    open: false,
    host: true
  },
  build: {
    rollupOptions: {
      input: {
        main: resolve(import.meta.dirname, "index.html"),
        pitwall: resolve(import.meta.dirname, "sepang_progress.html")
      },
      output: {
        manualChunks: (id) => {
          if (id.includes("@remotion") || id.includes("remotion")) {
            return "vendor-remotion";
          }
          if (id.includes("node_modules/motion") || id.includes("node_modules/lucide-react")) {
            return "vendor-motion";
          }
        }
      }
    }
  }
});

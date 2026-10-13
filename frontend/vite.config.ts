import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

/** Dev HMR (local default 5173). */
const devPort = Number(process.env.VITE_DEV_PORT || 5173);
/** Preview + Tailscale lab URL (default 4173; matches scripts/start-web-one-port.sh). */
const previewPort = Number(
  process.env.VITE_PREVIEW_PORT || process.env.AQREM_WEB_PORT || 4173,
);

export default defineConfig({
  plugins: [react()],
  server: {
    // Listen on all interfaces (required for Tailscale / LAN access).
    host: true,
    port: devPort,
    strictPort: true,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
      },
    },
  },
  preview: {
    host: true,
    port: previewPort,
    strictPort: true,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
      },
    },
  },
});

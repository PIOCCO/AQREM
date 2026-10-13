import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const devPort = Number(process.env.AQREM_WEB_PORT || process.env.VITE_DEV_PORT || 5173);

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
    port: devPort,
    strictPort: true,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
      },
    },
  },
});

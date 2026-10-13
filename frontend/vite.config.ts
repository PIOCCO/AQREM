import { execSync } from "node:child_process";
import { writeFileSync } from "node:fs";
import { defineConfig, type Plugin } from "vite";
import react from "@vitejs/plugin-react";

/** Dev HMR (local default 5173). */
const devPort = Number(process.env.VITE_DEV_PORT || 5173);
/** Preview + Tailscale lab URL (default 4173; matches scripts/start-web-one-port.sh). */
const previewPort = Number(
  process.env.VITE_PREVIEW_PORT || process.env.AQREM_WEB_PORT || 4173,
);

function resolveBuildId(): string {
  if (process.env.VITE_BUILD_ID) return process.env.VITE_BUILD_ID;
  try {
    return execSync("git rev-parse --short HEAD", { encoding: "utf8" }).trim();
  } catch {
    return "local";
  }
}

const buildId = resolveBuildId();
const buildTime = new Date().toISOString();

function buildInfoPlugin(): Plugin {
  return {
    name: "aqrem-build-info",
    closeBundle() {
      writeFileSync(
        "dist/build-info.json",
        JSON.stringify(
          {
            build_id: buildId,
            built_at: buildTime,
            auth_surface: "AuthPageShell",
            login_route: "/login",
          },
          null,
          2,
        ),
        "utf8",
      );
    },
  };
}

export default defineConfig({
  plugins: [react(), buildInfoPlugin()],
  define: {
    "import.meta.env.VITE_BUILD_ID": JSON.stringify(buildId),
    "import.meta.env.VITE_BUILD_TIME": JSON.stringify(buildTime),
  },
  server: {
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

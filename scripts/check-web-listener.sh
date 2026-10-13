#!/usr/bin/env bash
# Run ON the machine that should serve the app (e.g. your Tailscale node).
set -euo pipefail
PORT="${1:-4173}"
echo "=== AQREM web listener check (port ${PORT}) ==="
if command -v ss >/dev/null 2>&1; then
  echo "--- ss -tlnp | grep ${PORT} ---"
  if ! ss -tlnp | grep ":${PORT} "; then
    echo "(nothing listening on ${PORT})"
    echo ""
    echo "Start the lab server (UI + API on this port), from repo root:"
    echo "  ./scripts/start-web-one-port.sh"
    echo "Leave that terminal open, then re-run: ./scripts/check-web-listener.sh ${PORT}"
    exit 1
  fi
elif command -v lsof >/dev/null 2>&1; then
  lsof -iTCP:"${PORT}" -sTCP:LISTEN || true
else
  echo "Install ss or lsof for listener details."
fi
echo "--- curl GET http://127.0.0.1:${PORT}/ ---"
curl -sS -o /dev/null -w "HTTP %{http_code}\n" --connect-timeout 2 "http://127.0.0.1:${PORT}/" || echo "curl failed"
echo "--- curl GET http://127.0.0.1:${PORT}/platform-admin ---"
curl -sS -o /dev/null -w "HTTP %{http_code}\n" --connect-timeout 2 "http://127.0.0.1:${PORT}/platform-admin" || echo "curl failed"
if command -v tailscale >/dev/null 2>&1; then
  echo "--- tailscale ip -4 ---"
  tailscale ip -4 2>/dev/null || true
fi

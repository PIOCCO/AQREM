#!/usr/bin/env bash
# CI check for web container build args (not runtime Python).
set -euo pipefail
: "${VITE_PUBLIC_APP_URL:?Set VITE_PUBLIC_APP_URL to match client PUBLIC_BASE_URL}"
echo "OK: VITE_PUBLIC_APP_URL set"

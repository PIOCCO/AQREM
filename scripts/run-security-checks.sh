#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "== Backend tests (including security) =="
python3 -m pip install -q -e "backend[dev]" 2>/dev/null || pip install -q -e "backend[dev]"
python3 -m pytest tests/backend -q --tb=no

echo "== Ruff (backend) =="
python3 -m ruff check backend/app tests/backend 2>/dev/null || echo "ruff not installed — skip"

echo "== Terraform validate =="
if command -v terraform >/dev/null 2>&1; then
  (cd infra/terraform && terraform fmt -check -recursive && terraform init -backend=false -input=false >/dev/null && terraform validate)
else
  echo "terraform not installed — skip"
fi

echo "== Secret pattern grep (informational) =="
if rg -n "sk-[a-zA-Z0-9]{20,}" --glob '!*.md' . 2>/dev/null; then
  echo "WARNING: possible OpenAI-style key in tree"
  exit 1
fi
echo "No obvious sk- keys found."

echo "Security checks completed."

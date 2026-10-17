#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "== Backend tests (including security) =="
python3 -m pip install -q -e "backend[dev]" 2>/dev/null || pip install -q -e "backend[dev]"
python3 -m pytest tests/backend -q --tb=no

echo "== Ruff (backend) =="
python3 -m ruff check backend/app tests/backend 2>/dev/null || echo "ruff not installed — skip"

echo "== Terraform fmt + validate (all stacks, no backend, no Azure calls) =="
if command -v terraform >/dev/null 2>&1; then
  terraform fmt -check -recursive infra/terraform
  for d in infra/terraform infra/terraform/stacks/*/; do
    (cd "$d" && terraform init -backend=false -input=false >/dev/null && terraform validate -no-color >/dev/null) \
      && echo "valid: $d" || { echo "INVALID: $d"; exit 1; }
  done
else
  echo "terraform not installed — skip"
fi

echo "== Secret / state-file scan (tracked files + full git history; output masked) =="
python3 scripts/check_secrets.py
python3 scripts/check_secrets.py --history

echo "Security checks completed."

#!/usr/bin/env bash
# Install the local pre-commit hook: blocks commits that add Terraform state/plans, real tfvars,
# keys, .env files or credential-shaped values (scripts/check_secrets.py --staged).
# CI: run `python3 scripts/check_secrets.py && python3 scripts/check_secrets.py --history` as a job step
# (see docs/terraform-state-security.md; .github/workflows is not modified by this repo's tooling).
set -euo pipefail
ROOT="$(git rev-parse --show-toplevel)"
HOOK="$ROOT/.git/hooks/pre-commit"
cat > "$HOOK" <<'H'
#!/usr/bin/env bash
set -euo pipefail
ROOT="$(git rev-parse --show-toplevel)"
python3 "$ROOT/scripts/check_secrets.py" --staged || {
  echo "pre-commit: secret/state scan failed (values above are masked). Unstage the file or, for a" >&2
  echo "reviewed false positive, add 'secret-scan: allow' on that line." >&2
  exit 1
}
if git diff --cached --name-only | grep -qE '\.tf$'; then
  command -v terraform >/dev/null && (cd "$ROOT/infra/terraform" && terraform fmt -check -recursive >/dev/null) \
    || { echo "pre-commit: terraform fmt -check failed (run terraform fmt -recursive infra/terraform)" >&2; exit 1; }
fi
H
chmod +x "$HOOK"
echo "Installed $HOOK"

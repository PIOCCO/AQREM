#!/usr/bin/env python3
"""Repo secret / state-file scanner (no external dependencies).

    python3 scripts/check_secrets.py              # tracked files (working tree)
    python3 scripts/check_secrets.py --staged     # staged changes only (pre-commit hook)
    python3 scripts/check_secrets.py --history    # every commit reachable from any ref
    terraform state pull | python3 scripts/check_secrets.py --stdin   # audit a state without writing it to disk

Findings are printed MASKED (first 4 chars + length), never in full. Exit 1 on any HIGH finding.
HIGH  = forbidden file types (state, plans, real tfvars, keys, .env) or credential-shaped values.
INFO  = obvious local/dev placeholders (localhost URLs, *-for-tests tokens): listed as a count only.
Allow a single line with the marker `secret-scan: allow` (use sparingly, explain why next to it).
"""

from __future__ import annotations

import argparse
import fnmatch
import math
import re
import subprocess
import sys
from collections import Counter

FORBIDDEN_NAMES = [
    "*.tfstate", "*.tfstate.*", "*.tfplan", "tfplan", "tfplan.json", "*.tfplan.json", "crash.log",
    "terraform.tfvars", "*.auto.tfvars", "*.auto.tfvars.json", "backend.hcl", ".env", ".env.*",
    "*.pem", "*.key", "*.pfx", "*.p12", "*.jks", "id_rsa", "id_rsa.*", "id_ed25519", "id_ed25519.*",
    "*.license.json", "*license-private*", "credentials.json", "*.kubeconfig",
]
ALLOWED_NAMES = ["*.example", "*.sample.tfvars.json", ".env.example"]

RULES: list[tuple[str, re.Pattern[str]]] = [
    ("private-key", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA |ENCRYPTED )?PRIVATE KEY-----")),
    ("azure-storage-key", re.compile(r"AccountKey=([A-Za-z0-9+/]{40,}={0,2})")),
    ("azure-sas", re.compile(r"[?&]sig=([A-Za-z0-9%+/=]{20,})")),
    ("github-token", re.compile(r"\b(gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,})\b")),
    ("openai-key", re.compile(r"\b(sk-(?:proj-)?[A-Za-z0-9_-]{24,})\b")),
    ("aws-key", re.compile(r"\b(AKIA[0-9A-Z]{16})\b")),
    ("slack-token", re.compile(r"\b(xox[abprs]-[A-Za-z0-9-]{10,})\b")),
    ("jwt", re.compile(r"\b(eyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,})\b")),
    ("url-credentials", re.compile(r"\b[a-z][a-z0-9+.-]*://[^:/@\s'\"]+:([^@\s'\"/]{6,})@([^\s/'\":]+)")),
    ("tfstate-sensitive", re.compile(r"\"(?:administrator_password|primary_access_key|value)\"\s*:\s*\"([^\"]{12,})\"")),
    ("assigned-secret", re.compile(
        r"(?i)\b(?:password|passwd|secret|api[_-]?key|client_secret|token)\b[\"']?\s*[:=]\s*[\"']([A-Za-z0-9+/=_\-!@#$%^&*]{16,})[\"']")),
]

PLACEHOLDER = re.compile(
    r"(?i)(example|placeholder|changeme|change-me|dummy|fake|sample|for-tests|for_tests|test|local|dev|"
    r"xxxx|\.\.\.|<[^>]+>|\$\{|\$[A-Z_]|\*\*\*|redacted|not-a-real|0000000|aqrem)")
# Publicly documented, non-secret values (compared by SHA-256 so the scanner holds no key material).
KNOWN_PUBLIC_SHA256 = {
    "0011cc25eb4320717494d2703e8cba85743e71b500283c21c8b88147992f9059": "Azurite emulator well-known account key",
}
SOFT_RULES = {"assigned-secret", "tfstate-sensitive", "azure-sas", "jwt", "url-credentials", "openai-key"}
TEST_PATH = re.compile(r"(^|/)(tests?|__tests__|fixtures)/|\.test\.[jt]sx?$|(^|/)test_[^/]+\.py$")
DEV_HOSTS = re.compile(r"^(localhost|127\.0\.0\.1|postgres|db|redis|host|0\.0\.0\.0|\[::1\])$", re.I)


def _mask(v: str) -> str:
    return f"{v[:4]}…(len={len(v)})"


def _entropy(s: str) -> float:
    if not s:
        return 0.0
    c = Counter(s)
    return -sum(n / len(s) * math.log2(n / len(s)) for n in c.values())


def name_forbidden(path: str) -> bool:
    base = path.rsplit("/", 1)[-1]
    if any(fnmatch.fnmatch(base, a) for a in ALLOWED_NAMES):
        return False
    return any(fnmatch.fnmatch(base, f) for f in FORBIDDEN_NAMES)


def scan_line(line: str, path: str = "") -> list[tuple[str, str, str]]:
    """[(severity, rule, masked)]"""
    import hashlib

    if "secret-scan: allow" in line:
        return []
    in_tests = bool(TEST_PATH.search(path))
    out = []
    for rule, pat in RULES:
        for m in pat.finditer(line):
            value = m.group(1) if m.groups() else m.group(0)
            sev = "HIGH"
            if hashlib.sha256(value.encode()).hexdigest() in KNOWN_PUBLIC_SHA256:
                continue
            if in_tests and rule in SOFT_RULES:
                sev = "INFO"  # fixtures in test code; credential-shaped but not deployable secrets
            elif re.fullmatch(r"[a-z_]+", value):
                sev = "INFO"  # identifier / variable name (e.g. psql :'migrator_password')
            elif rule == "url-credentials":
                host = m.group(2)
                if DEV_HOSTS.match(host) or PLACEHOLDER.search(value) or PLACEHOLDER.search(host):
                    sev = "INFO"
            elif rule in {"assigned-secret", "tfstate-sensitive", "azure-sas", "jwt"}:
                if PLACEHOLDER.search(value) or _entropy(value) < 3.0:
                    sev = "INFO"
            out.append((sev, rule, _mask(value)))
    return out


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], check=True, capture_output=True, text=True, errors="replace").stdout


SKIP_CONTENT = ("scripts/check_secrets.py", "package-lock.json")


def scan_tracked(staged: bool) -> list[tuple]:
    findings = []
    files = (_git("diff", "--cached", "--name-only", "--diff-filter=ACMR") if staged else _git("ls-files")).splitlines()
    for f in files:
        if name_forbidden(f):
            findings.append(("HIGH", "forbidden-file", f, "-", "-"))
        if f.endswith(SKIP_CONTENT):
            continue
        try:
            text = _git("show", f":{f}") if staged else open(f, encoding="utf-8", errors="replace").read()
        except (OSError, subprocess.CalledProcessError):
            continue
        if "\0" in text[:2000]:
            continue
        for i, line in enumerate(text.splitlines(), 1):
            for sev, rule, masked in scan_line(line, f):
                findings.append((sev, rule, f, str(i), masked))
    return findings


def scan_history() -> list[tuple]:
    findings = []
    names = _git("log", "--all", "--diff-filter=A", "--name-only", "--format=@@%h")
    commit = "?"
    for line in names.splitlines():
        if line.startswith("@@"):
            commit = line[2:]
        elif line and name_forbidden(line):
            findings.append(("HIGH", "forbidden-file-in-history", line, commit, "-"))
    proc = subprocess.Popen(["git", "log", "--all", "-p", "--no-color", "-U0", "--format=@@%h"],
                            stdout=subprocess.PIPE, text=True, errors="replace")
    commit, path = "?", "?"
    assert proc.stdout
    for line in proc.stdout:
        if line.startswith("@@") and not line.startswith("@@ "):
            commit = line[2:].strip()
        elif line.startswith("+++ "):
            path = line[6:].strip() if line.startswith("+++ b/") else line[4:].strip()
        elif line.startswith("+") and not line.startswith("+++"):
            if path.endswith(SKIP_CONTENT):
                continue
            for sev, rule, masked in scan_line(line[1:], path):
                findings.append((sev, rule, path, commit, masked))
    proc.wait()
    return findings


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--staged", action="store_true")
    g.add_argument("--history", action="store_true")
    g.add_argument("--stdin", action="store_true", help="scan text on stdin (e.g. terraform state pull)")
    ap.add_argument("--show-info", action="store_true", help="also list INFO findings")
    a = ap.parse_args(argv)
    if a.stdin:
        findings = [(sev, rule, "<stdin>", str(i), m)
                    for i, line in enumerate(sys.stdin, 1) for sev, rule, m in scan_line(line, "<stdin>")]
    else:
        findings = scan_history() if a.history else scan_tracked(a.staged)
    high = [f for f in findings if f[0] == "HIGH"]
    info = [f for f in findings if f[0] == "INFO"]
    where = "commit" if a.history else "line"
    seen = set()
    for f in high + (info if a.show_info else []):
        key = f[1:4] if not a.history else (f[1], f[2], f[4])
        if key in seen:
            continue
        seen.add(key)
        print(f"{f[0]:4} {f[1]:26} {f[2]} {where}={f[3]} value={f[4]}")
    scope = "history" if a.history else ("stdin" if a.stdin else ("staged" if a.staged else "tracked files"))
    print(f"secret scan ({scope}): {len({(f[1], f[2], f[4]) for f in high})} HIGH, "
          f"{len({(f[1], f[2], f[4]) for f in info})} INFO (dev/test placeholders)", file=sys.stderr)
    return 1 if high else 0


if __name__ == "__main__":
    raise SystemExit(main())

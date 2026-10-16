"""Private-networking readiness: no hardcoded public endpoints outside config defaults."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
URL = re.compile(r"https?://(?!localhost|127\.0\.0\.1|0\.0\.0\.0)[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
# Files allowed to *declare* default endpoints (all overridable by env).
ALLOW = {
    "backend/app/core/config.py",
    "backend/app/services/email/brevo.py",       # default constant, overridden by BREVO_API_URL
    "backend/app/services/github/client.py",     # fallback when GITHUB_API_URL is blank
    "backend/app/services/llm/azure_openai.py",  # Entra scope default, AZURE_OPENAI_TOKEN_SCOPE
    "backend/app/services/llm/openai_provider.py",
}


def test_backend_has_no_unconfigurable_public_urls():
    offenders = []
    for path in (ROOT / "backend/app").rglob("*.py"):
        rel = str(path.relative_to(ROOT))
        if rel in ALLOW:
            continue
        for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            for m in URL.finditer(line):
                host = m.group(0)
                if any(s in host for s in ("example.", "aqrem.local", "schemas.", "w3.org")):
                    continue
                offenders.append(f"{rel}:{i}: {host}")
    assert not offenders, "Hardcoded outbound URLs:\n" + "\n".join(offenders)


def test_frontend_index_has_no_cdn():
    html = (ROOT / "frontend/index.html").read_text(encoding="utf-8")
    assert "fonts.googleapis.com" not in html and "cdn." not in html and "unpkg" not in html

"""Offline, signed license for dedicated environments.

License file = JSON {"payload": {...}, "signature": base64(Ed25519(canonical_json(payload))), "alg": "Ed25519"}.
Verified locally with the embedded public key (or LICENSE_PUBLIC_KEY override); no network call.
Sources (first found): LICENSE_KEY (file contents, e.g. from Key Vault) then LICENSE_FILE (path).

Shared mode does not use this module: it keeps the per-organization seat licensing in licensing.py.
"""

from __future__ import annotations

import base64
import json
import os
import threading
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from app.core.config import Settings, get_settings

# Production verification key. The matching private key is kept offline by the vendor
# (generated with scripts/aqrem_license.py keygen). Rotate by replacing this value.
EMBEDDED_PUBLIC_KEY_B64 = "pe8ErPz0vca5I+8nbSHB+lgNj8T4/aWbZIp2S/Dtx5E="

VALID = "valid"
MISSING = "missing"
INVALID = "invalid"
EXPIRED = "expired"


@dataclass
class LicenseResult:
    state: str
    message: str
    payload: dict = field(default_factory=dict)

    @property
    def seats(self) -> int:
        return int(self.payload.get("seats") or 0)

    @property
    def features(self) -> list[str]:
        return list(self.payload.get("features") or [])

    @property
    def expires_at(self) -> datetime | None:
        raw = self.payload.get("expires_at")
        if not raw:
            return None
        try:
            return datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        except ValueError:
            return None


def canonical(payload: dict) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def verify_license_text(text: str, *, public_key_b64: str | None = None, now: datetime | None = None) -> LicenseResult:
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

    try:
        doc = json.loads(text)
        payload = doc["payload"]
        sig = base64.b64decode(doc["signature"], validate=True)
        if not isinstance(payload, dict):
            raise ValueError
    except Exception:
        return LicenseResult(INVALID, "The license file is not valid JSON in the AQREM license format.")
    try:
        key = Ed25519PublicKey.from_public_bytes(base64.b64decode(public_key_b64 or EMBEDDED_PUBLIC_KEY_B64))
        key.verify(sig, canonical(payload))
    except InvalidSignature:
        return LicenseResult(INVALID, "The license signature is invalid (file modified or issued for another key).")
    except Exception:
        return LicenseResult(INVALID, "The license could not be verified (bad public key configuration).")
    res = LicenseResult(VALID, "", payload)
    exp = res.expires_at
    if exp is None:
        return LicenseResult(INVALID, "The license has no valid expiry date.", payload)
    now = now or datetime.now(UTC)
    if exp < now:
        return LicenseResult(EXPIRED, f"The license expired on {exp.date().isoformat()}. Contact your AQREM vendor to renew.", payload)
    if res.seats <= 0:
        return LicenseResult(INVALID, "The license grants no seats.", payload)
    res.message = (f"Licensed to {payload.get('organization')}: {res.seats} seats until {exp.date().isoformat()}.")
    return res


_cache: dict[str, tuple[object, LicenseResult]] = {}
_lock = threading.Lock()


def load_license(settings: Settings | None = None) -> LicenseResult:
    settings = settings or get_settings()
    inline = (os.environ.get("LICENSE_KEY") or "").strip()
    path = (settings.license_file or "").strip()
    if inline:
        text, cache_key = inline, ("env", hash(inline))
    elif path:
        p = Path(path)
        if not p.is_file():
            return LicenseResult(MISSING, f"No license file found at LICENSE_FILE={path}. Install the license file you received.")
        st = p.stat()
        cache_key = ("file", path, st.st_mtime_ns, st.st_size)
        with _lock:
            hit = _cache.get("lic")
            if hit and hit[0] == cache_key and hit[1].state == VALID and hit[1].expires_at and hit[1].expires_at > datetime.now(UTC):
                return hit[1]
        text = p.read_text(encoding="utf-8")
    else:
        return LicenseResult(MISSING, "No license is installed. Set LICENSE_FILE (path) or LICENSE_KEY (contents).")
    res = verify_license_text(text, public_key_b64=(settings.license_public_key or None))
    with _lock:
        _cache["lic"] = (cache_key, res)
    return res


def license_status_summary(settings: Settings | None = None) -> dict:
    res = load_license(settings)
    exp = res.expires_at
    return {
        "status": res.state,
        "message": res.message,
        "organization": res.payload.get("organization"),
        "seats": res.seats if res.payload else None,
        "expires_at": exp.isoformat() if exp else None,
        "features": res.features,
        "license_id": res.payload.get("license_id"),
    }


def has_feature(name: str, settings: Settings | None = None) -> bool:
    settings = settings or get_settings()
    if not settings.is_dedicated:
        return True
    res = load_license(settings)
    return res.state == VALID and (not res.features or name in res.features)

"""Offline, signed license for dedicated environments.

License file = JSON {"payload": {...}, "signature": base64(Ed25519(canonical_json(payload))), "alg": "Ed25519"}.
Verified locally against the public keys embedded in this image; no network call.
Sources (first found): LICENSE_KEY (file contents, e.g. from Key Vault) then LICENSE_FILE (path).

This module answers "is this license authentic and does it apply here, at time T". What the
application does about it (warning, grace period, read-only) is decided in license_enforcement.py,
which also supplies T (clock-rollback safe).

Messages produced here are shown to organization administrators. They say what is wrong and what
to do (contact the vendor); they deliberately never mention keys, file locations or settings.

Shared mode does not use this module: it keeps the per-organization seat licensing in licensing.py.
"""

from __future__ import annotations

import base64
import binascii
import json
import logging
import os
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from app.core.config import Settings, get_settings

logger = logging.getLogger("aqrem.license")

# Verification keys trusted by this image (key id -> base64 raw Ed25519 public key). A license is
# accepted if it verifies against any of them, so a key rotation ships the new key alongside the old
# one for one release. The matching private keys never enter the repository or the image.
# "dev-2026-10" is the DEVELOPMENT key; production builds must embed a production key generated
# offline (docs/licensing.md "Production signing key").
EMBEDDED_PUBLIC_KEYS: dict[str, str] = {
    "dev-2026-10": "pe8ErPz0vca5I+8nbSHB+lgNj8T4/aWbZIp2S/Dtx5E=",
}
DEVELOPMENT_KEY_IDS = frozenset({"dev-2026-10"})
# Back-compat alias (older imports / docs).
EMBEDDED_PUBLIC_KEY_B64 = EMBEDDED_PUBLIC_KEYS["dev-2026-10"]

# Environments in which LICENSE_PUBLIC_KEY (a test-only verification-key override) is honoured.
# Everything else (production, staging, typos) ignores it.
_KEY_OVERRIDE_ENVS = frozenset({"development", "test"})

LICENSE_FORMAT_VERSION = 2
REQUIRED_FIELDS = ("license_id", "organization", "organization_slug", "environment", "deployment_mode",
                   "seats", "issued_at", "expires_at")

VALID = "valid"
MISSING = "missing"
INVALID = "invalid"
EXPIRED = "expired"
NOT_YET_VALID = "not_yet_valid"
MISMATCH = "mismatch"

CONTACT = "Contact your AQREM vendor"

MSG_MISSING = f"No license is installed for this environment. {CONTACT} to obtain one."
MSG_INVALID = f"The installed license is not valid. {CONTACT} for a replacement license file."
MSG_MISMATCH = (f"The installed license was issued for a different organization or environment. "
                f"{CONTACT} for the license that belongs to this environment.")


@dataclass
class LicenseResult:
    state: str
    message: str
    payload: dict = field(default_factory=dict)
    # Operator-facing reason code for logs (never shown to end users, never contains secrets/paths).
    reason: str = ""

    @property
    def seats(self) -> int:
        try:
            return int(self.payload.get("seats") or 0)
        except (TypeError, ValueError):
            return 0

    @property
    def features(self) -> list[str]:
        return list(self.payload.get("features") or [])

    def _dt(self, key: str) -> datetime | None:
        return parse_time(self.payload.get(key))

    @property
    def expires_at(self) -> datetime | None:
        return self._dt("expires_at")

    @property
    def issued_at(self) -> datetime | None:
        return self._dt("issued_at")

    @property
    def not_before(self) -> datetime | None:
        return self._dt("not_before")

    @property
    def grace_days(self) -> int | None:
        raw = self.payload.get("grace_days")
        if raw is None:
            return None
        try:
            return max(0, min(90, int(raw)))
        except (TypeError, ValueError):
            return None


def parse_time(raw) -> datetime | None:
    if not raw or not isinstance(raw, str):
        return None
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo else None


def canonical(payload: dict) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def trusted_keys(settings: Settings | None = None) -> dict[str, str]:
    """Verification keys for this process. The override exists for automated tests only."""
    settings = settings or get_settings()
    override = (settings.license_public_key or "").strip()
    if override:
        if settings.app_env in _KEY_OVERRIDE_ENVS:
            return {"override": override}
        _warn_once("license_key_override_ignored",
                   "A license verification override is configured but ignored in app_env=%s.", settings.app_env)
    return dict(EMBEDDED_PUBLIC_KEYS)


_warned: set[str] = set()


def _warn_once(code: str, msg: str, *args) -> None:
    if code not in _warned:
        _warned.add(code)
        logger.warning(msg, *args)


def _verify_signature(payload: dict, sig: bytes, keys: dict[str, str]) -> str | None:
    """Return the id of the key that verifies, or None."""
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

    msg = canonical(payload)
    for kid, b64 in keys.items():
        try:
            Ed25519PublicKey.from_public_bytes(base64.b64decode(b64, validate=True)).verify(sig, msg)
            return kid
        except (InvalidSignature, ValueError, binascii.Error):
            continue
    return None


def verify_license_text(
    text: str,
    *,
    public_key_b64: str | None = None,
    keys: dict[str, str] | None = None,
    now: datetime | None = None,
    expected_org_slug: str | None = None,
    expected_environment: str | None = None,
    expected_mode: str | None = "dedicated",
) -> LicenseResult:
    """Authenticate the license and check it against this environment at time ``now``.

    Order: format -> signature (any change to the payload invalidates it) -> required fields ->
    binding (mode, environment, organization) -> not_before -> expiry.
    ``expected_*=None`` skips that binding (offline CLI verification of a file).
    """
    try:
        doc = json.loads(text)
        payload = doc["payload"]
        sig = base64.b64decode(doc["signature"], validate=True)
        if not isinstance(payload, dict) or doc.get("alg", "Ed25519") != "Ed25519" or len(sig) != 64:
            raise ValueError
    except Exception:
        return LicenseResult(INVALID, MSG_INVALID, reason="format_invalid")
    if keys is None:
        keys = {"explicit": public_key_b64} if public_key_b64 else trusted_keys()
    kid = _verify_signature(payload, sig, keys)
    if kid is None:
        return LicenseResult(INVALID, MSG_INVALID, reason="signature_invalid")
    res = LicenseResult(VALID, "", payload, reason=f"key={kid}")
    missing = [f for f in REQUIRED_FIELDS if payload.get(f) in (None, "")]
    if missing or res.expires_at is None or res.issued_at is None or res.seats <= 0 \
            or ("not_before" in payload and res.not_before is None):
        return LicenseResult(INVALID, MSG_INVALID, payload, reason="fields_invalid")
    if expected_mode is not None and payload.get("deployment_mode") != expected_mode:
        return LicenseResult(MISMATCH, MSG_MISMATCH, payload, reason="mode_mismatch")
    if expected_environment is not None and str(payload.get("environment")) != expected_environment:
        return LicenseResult(MISMATCH, MSG_MISMATCH, payload, reason="environment_mismatch")
    if expected_org_slug is not None and str(payload.get("organization_slug")) != expected_org_slug:
        return LicenseResult(MISMATCH, MSG_MISMATCH, payload, reason="organization_mismatch")
    now = now or datetime.now(UTC)
    nb = res.not_before
    if nb is not None and now < nb:
        return LicenseResult(
            NOT_YET_VALID,
            f"The installed license is valid from {nb.date().isoformat()} only. "
            f"{CONTACT} if you need it to start earlier.",
            payload, reason="not_yet_valid")
    exp = res.expires_at
    if exp <= now:
        return LicenseResult(EXPIRED, f"The license expired on {exp.date().isoformat()}. {CONTACT} to renew.",
                             payload, reason="expired")
    res.message = f"Licensed to {payload.get('organization')}: {res.seats} seats until {exp.date().isoformat()}."
    return res


def read_license_text(settings: Settings | None = None) -> str | None:
    """Raw license text from LICENSE_KEY or LICENSE_FILE, or None when no license is installed."""
    settings = settings or get_settings()
    inline = (os.environ.get("LICENSE_KEY") or "").strip()
    if inline:
        return inline
    path = (settings.license_file or "").strip()
    if not path:
        return None
    p = Path(path)
    try:
        if not p.is_file():
            return None
        # Equal-size replacements can retain the same timestamp. Read the small
        # signed document each time so an old valid signature cannot stay cached.
        text = p.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""  # unreadable -> treated as invalid, not as "missing"
    return text


def load_license(
    settings: Settings | None = None,
    *,
    now: datetime | None = None,
    expected_org_slug: str | None = None,
    expected_environment: str | None = None,
) -> LicenseResult:
    settings = settings or get_settings()
    text = read_license_text(settings)
    if text is None:
        return LicenseResult(MISSING, MSG_MISSING, reason="missing")
    return verify_license_text(
        text, keys=trusted_keys(settings), now=now,
        expected_org_slug=expected_org_slug, expected_environment=expected_environment,
        expected_mode="dedicated",
    )


def license_status_summary(settings: Settings | None = None) -> dict:
    """Health/diagnostics view (no signature, no key material)."""
    res = load_license(settings, expected_environment=(settings or get_settings()).environment_name or None)
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

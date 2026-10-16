"""Hardening for the dedicated first-run setup (/setup + /api/v1/setup/*).

* One-time token: only sha256(token) + issued_at/consumed_at/revoked_at are stored (``setup_tokens``).
  A bootstrap row is created from SETUP_TOKEN once (first app start of an environment without an
  admin). After that the env var is ignored: changing SETUP_TOKEN never re-opens setup. Only the
  operator CLI (``python -m app.setup reset --confirm``) can issue a new token.
* Lifetime: SETUP_TOKEN_TTL_MINUTES from issued_at.
* Closed => 404, identical to an unknown route. Open requires a live token AND (no admin yet OR an
  operator reset).
* Network: client IP must be inside SETUP_ALLOWED_CIDRS (default loopback/private), else 404.
* Rate limit: failed attempts per IP and globally within SETUP_LOCKOUT_MINUTES (DB-backed, so it
  survives restarts and works across replicas).
"""

from __future__ import annotations

import hashlib
import hmac
import ipaddress
import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.logging_setup import register_secret
from app.models.setup_token import SetupAttempt, SetupToken

logger = logging.getLogger("aqrem.setup")

BOOTSTRAP = "bootstrap"
OPERATOR_RESET = "operator_reset"

OPEN = "open"
CLOSED = "closed"        # -> 404
EXPIRED = "expired"      # -> 410 (no admin yet, but the token expired/was used; operator must reset)
UNCONFIGURED = "unconfigured"  # -> no SETUP_TOKEN and no token rows yet


def hash_token(token: str) -> str:
    return hashlib.sha256((token or "").strip().encode("utf-8")).hexdigest()


def _now() -> datetime:
    return datetime.now(UTC)


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def token_expires_at(row: SetupToken, settings: Settings) -> datetime:
    return _aware(row.issued_at) + timedelta(minutes=settings.setup_token_ttl_minutes)


def ensure_bootstrap_token(db: Session, settings: Settings) -> None:
    """First start of a dedicated env with no admin: record hash(SETUP_TOKEN). Idempotent; never re-issues."""
    if not settings.is_dedicated:
        return
    raw = (settings.setup_token or "").strip()
    register_secret(raw)
    if db.query(SetupToken.id).first() is not None:
        return
    from app.core.deployment import dedicated_setup_required

    if not raw or not dedicated_setup_required(db):
        return
    db.add(SetupToken(token_hash=hash_token(raw), source=BOOTSTRAP, issued_at=_now()))
    db.flush()
    logger.warning("Setup token issued (expires in %s minutes)", settings.setup_token_ttl_minutes)


def _latest_unrevoked(db: Session) -> SetupToken | None:
    return (
        db.query(SetupToken)
        .filter(SetupToken.revoked_at.is_(None))
        .order_by(SetupToken.issued_at.desc())
        .first()
    )


@dataclass
class SetupState:
    state: str
    token: SetupToken | None = None
    expires_at: datetime | None = None


def setup_state(db: Session, settings: Settings) -> SetupState:
    if not settings.is_dedicated:
        return SetupState(CLOSED)
    from app.core.deployment import dedicated_setup_required

    ensure_bootstrap_token(db, settings)
    admin_missing = dedicated_setup_required(db)
    row = _latest_unrevoked(db)
    if row is None:
        has_any = db.query(SetupToken.id).first() is not None
        if admin_missing and not has_any:
            return SetupState(UNCONFIGURED)
        return SetupState(EXPIRED if admin_missing else CLOSED)
    if row.source == BOOTSTRAP and not admin_missing:
        return SetupState(CLOSED)
    live = row.consumed_at is None and token_expires_at(row, settings) > _now()
    if live:
        return SetupState(OPEN, row, token_expires_at(row, settings))
    return SetupState(EXPIRED if admin_missing else CLOSED)


def verify_token(row: SetupToken, presented: str) -> bool:
    return hmac.compare_digest(hash_token(presented).encode(), row.token_hash.encode())


# ------------------------------------------------------------------ network gate


def client_ip(peer: str | None, forwarded_for: str | None, settings: Settings) -> str | None:
    """Client address after stripping exactly SETUP_TRUSTED_PROXY_HOPS trusted proxies. None = untrusted."""
    hops = settings.setup_trusted_proxy_hops
    xff = [p.strip() for p in (forwarded_for or "").split(",") if p.strip()]
    if hops == 0:
        if xff:
            # A proxy is in front but not declared: the peer would be the proxy's private address.
            return None
        chain = [peer or ""]
    else:
        chain = xff + [peer or ""]
        if len(chain) < hops + 1:
            return None
    candidate = chain[-(hops + 1)]
    try:
        return str(ipaddress.ip_address(candidate))
    except ValueError:
        return None


def ip_allowed(ip: str | None, settings: Settings) -> bool:
    if ip is None:
        return False
    addr = ipaddress.ip_address(ip)
    for part in (settings.setup_allowed_cidrs or "").split(","):
        part = part.strip()
        if not part:
            continue
        try:
            if addr in ipaddress.ip_network(part, strict=False):
                return True
        except ValueError:
            logger.error("Ignoring invalid SETUP_ALLOWED_CIDRS entry")
    return False


# ------------------------------------------------------------------ rate limit


def lockout_seconds(db: Session, ip: str, settings: Settings) -> int:
    """>0 when the IP (or the whole endpoint) is locked out; value = seconds until it unlocks."""
    window = timedelta(minutes=settings.setup_lockout_minutes)
    since = _now() - window
    base = db.query(SetupAttempt).filter(SetupAttempt.success.is_(False), SetupAttempt.attempted_at > since)
    worst = 0
    for q, limit in ((base.filter(SetupAttempt.client_ip == ip), settings.setup_max_attempts_per_ip),
                     (base, settings.setup_max_attempts_global)):
        rows = q.order_by(SetupAttempt.attempted_at.desc()).limit(limit).all()
        if len(rows) >= limit:
            # unlock when the oldest of the last `limit` failures leaves the window
            oldest = _aware(rows[-1].attempted_at)
            worst = max(worst, int((oldest + window - _now()).total_seconds()) + 1)
    return worst


def record_attempt(db: Session, ip: str, *, success: bool) -> None:
    db.add(SetupAttempt(client_ip=ip, success=success, attempted_at=_now()))
    db.flush()


# ------------------------------------------------------------------ operator reset


def operator_reset(db: Session, settings: Settings, new_token: str) -> SetupToken:
    """Revoke every unconsumed token and issue a new one (source=operator_reset). Token must be new."""
    new_token = (new_token or "").strip()
    if len(new_token) < 24:
        raise ValueError("New setup token must be at least 24 characters.")
    h = hash_token(new_token)
    if db.query(SetupToken.id).filter(SetupToken.token_hash == h).first() is not None:
        raise ValueError("This token was used before; issue a new one.")
    now = _now()
    db.query(SetupToken).filter(SetupToken.consumed_at.is_(None), SetupToken.revoked_at.is_(None)).update(
        {SetupToken.revoked_at: now}, synchronize_session=False
    )
    row = SetupToken(token_hash=h, source=OPERATOR_RESET, issued_at=now)
    db.add(row)
    db.flush()
    register_secret(new_token)
    return row

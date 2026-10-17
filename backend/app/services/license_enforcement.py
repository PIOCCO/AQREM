"""Dedicated tier: what the application does about the offline license.

Levels (never deletes or alters customer data in any level):
  ok         licensed, within seats.
  warning    licensed, but expiring within WARNING_DAYS, or the server clock went backwards.
  grace      a problem exists but full service continues until ``grace_until``:
               - license expired (grace counted from the expiry date),
               - more users than licensed seats (counted from first detection),
               - license missing/invalid/mismatched/not yet valid on an environment that was licensed
                 before (counted from first detection).
  read_only  after the grace period, or when no valid license was ever installed: sign-in, reading,
             searching, exports and administration keep working; creating content (uploads, chats,
             questionnaires, projects, sources) and adding users is refused with 403 LICENSE_READ_ONLY.

Time used for all license decisions = max(system clock, highest time ever observed by this
environment, license issue time). A clock set backwards therefore never extends a license; it is
flagged (warning + log) when it is more than CLOCK_ROLLBACK_TOLERANCE behind.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.services import offline_license as ol

logger = logging.getLogger("aqrem.license")

OK = "ok"
WARNING = "warning"
GRACE = "grace"
READ_ONLY = "read_only"

WARNING_DAYS = 30
DEFAULT_GRACE_DAYS = 14
CLOCK_ROLLBACK_TOLERANCE = timedelta(hours=2)
CACHE_SECONDS = 30.0

MSG_READ_ONLY_TAIL = ("AQREM is in read-only mode: existing content, search, exports and administration remain "
                      "available; new uploads, chats and users are blocked. No data is deleted.")
MSG_USER_READ_ONLY = ("AQREM is currently in read-only mode for this organization. Existing content remains "
                      "available. Please contact your administrator.")
MSG_CLOCK = ("The server clock is behind the last time recorded by this environment. License dates are "
             "evaluated against the recorded time. Ask your IT team to check the server's time synchronisation.")


@dataclass
class Enforcement:
    level: str
    mode: str = "dedicated"
    code: str = ""                     # license state or "seats_exceeded"
    message: str = ""                  # for organization administrators
    grace_until: datetime | None = None
    expires_at: datetime | None = None
    seats: int | None = None
    seats_used: int | None = None
    clock_rollback: bool = False
    effective_now: datetime | None = None
    notes: list[str] = field(default_factory=list)

    @property
    def read_only(self) -> bool:
        return self.level == READ_ONLY

    @property
    def can_add_users(self) -> bool:
        # Adding users needs a trustworthy seat count: a valid (or recently expired) license.
        return self.level != READ_ONLY and self.code in {ol.VALID, ol.EXPIRED} and \
            self.seats is not None and (self.seats_used or 0) < self.seats

    def public_dict(self, *, admin: bool) -> dict:
        d = {"mode": self.mode, "level": self.level, "read_only": self.read_only}
        if self.mode != "dedicated":
            return d
        if admin:
            d.update({
                "code": self.code,
                "message": self.message,
                "grace_until": self.grace_until.isoformat() if self.grace_until else None,
                "expires_at": self.expires_at.isoformat() if self.expires_at else None,
                "seats": self.seats,
                "seats_used": self.seats_used,
                "clock_warning": self.clock_rollback,
            })
        else:
            d["message"] = MSG_USER_READ_ONLY if self.read_only else ""
        return d


_cache: dict[str, tuple[float, Enforcement]] = {}
_cache_lock = threading.Lock()


def clear_cache() -> None:
    with _cache_lock:
        _cache.clear()


def _date(dt: datetime | None) -> str:
    return dt.date().isoformat() if dt else "?"


def _read_state(db: Session) -> dict:
    row = db.execute(text(
        "SELECT highest_seen_at, last_valid_at, problem_code, problem_since, clock_rollback_at "
        "FROM license_runtime_state WHERE id = 1"
    )).mappings().first()
    return dict(row) if row else {}


def _write_state(db: Session, *, real_now: datetime, effective_now: datetime, valid_license_id: str | None,
                 problem: str | None, clear_problem: bool, rollback: bool) -> None:
    """Monotonic upsert: highest_seen never decreases; first detection times are never moved later."""
    db.execute(text("INSERT INTO license_runtime_state (id, highest_seen_at, updated_at) VALUES (1, :n, :n) "
                    "ON CONFLICT (id) DO NOTHING"), {"n": real_now})
    db.execute(text("""
UPDATE license_runtime_state SET
  highest_seen_at = GREATEST(COALESCE(highest_seen_at, :real_now), :real_now),
  last_valid_at = CASE WHEN CAST(:valid_id AS text) IS NOT NULL THEN :eff ELSE last_valid_at END,
  last_license_id = COALESCE(CAST(:valid_id AS text), last_license_id),
  problem_code = CASE WHEN :clear THEN NULL WHEN CAST(:problem AS text) IS NOT NULL THEN :problem
                      ELSE problem_code END,
  problem_since = CASE WHEN :clear THEN NULL
                       WHEN CAST(:problem AS text) IS NOT NULL THEN COALESCE(problem_since, :eff)
                       ELSE problem_since END,
  clock_rollback_at = CASE WHEN :rollback THEN COALESCE(clock_rollback_at, :real_now) ELSE NULL END,
  updated_at = :real_now
WHERE id = 1
"""), {"real_now": real_now, "eff": effective_now, "valid_id": valid_license_id, "problem": problem,
       "clear": clear_problem, "rollback": rollback})


def evaluate(db: Session, settings: Settings | None = None, *, now: datetime | None = None,
             use_cache: bool = True, persist: bool = True) -> Enforcement:
    settings = settings or get_settings()
    if not settings.is_dedicated:
        return Enforcement(level=OK, mode="shared")
    if use_cache and now is None:
        with _cache_lock:
            hit = _cache.get("e")
            if hit and time.monotonic() - hit[0] < CACHE_SECONDS:
                return hit[1]
    result = _evaluate(db, settings, now=now, persist=persist)
    if now is None:
        with _cache_lock:
            _cache["e"] = (time.monotonic(), result)
    return result


def _evaluate(db: Session, settings: Settings, *, now: datetime | None, persist: bool) -> Enforcement:
    from app.core.deployment import get_dedicated_org
    from app.services.seat_usage import get_seat_usage

    real_now = now or datetime.now(UTC)
    try:
        state = _read_state(db)
    except Exception:  # table missing (pre-m7 schema) or no privilege: evaluate without history
        db.rollback()
        logger.error("license runtime state unavailable; evaluating without clock/grace history")
        state, persist = {}, False
    highest = state.get("highest_seen_at")
    rollback = bool(highest and real_now < highest - CLOCK_ROLLBACK_TOLERANCE)
    effective = max(real_now, highest) if highest else real_now

    org = get_dedicated_org(db)
    binding = {"expected_org_slug": org.slug if org is not None else "",
               "expected_environment": (settings.environment_name or "").strip()}
    lic = ol.load_license(settings, now=effective, **binding)
    issued = lic.issued_at if lic.payload else None
    if issued and issued > effective:
        if issued - real_now > CLOCK_ROLLBACK_TOLERANCE:
            rollback = True
        effective = issued
        lic = ol.load_license(settings, now=effective, **binding)

    grace_days = lic.grace_days if lic.grace_days is not None and lic.state in {ol.VALID, ol.EXPIRED} \
        else DEFAULT_GRACE_DAYS
    seats_used = get_seat_usage(db, org).seats_used if org is not None else 0
    enf = Enforcement(level=OK, code=lic.state, expires_at=lic.expires_at,
                      seats=lic.seats if lic.state in {ol.VALID, ol.EXPIRED} else None,
                      seats_used=seats_used, clock_rollback=rollback, effective_now=effective)

    problem: str | None = None
    if lic.state == ol.VALID and seats_used > lic.seats:
        problem = "seats_exceeded"
    elif lic.state not in {ol.VALID, ol.EXPIRED}:
        problem = lic.state
    clear_problem = lic.state == ol.VALID and problem is None
    since = state.get("problem_since")
    if problem and since is None:
        since = effective

    if lic.state == ol.VALID and problem is None:
        days_left = (lic.expires_at - effective).days
        if days_left < WARNING_DAYS:
            enf.level = WARNING
            enf.message = (f"The license expires on {_date(lic.expires_at)} ({max(days_left, 0)} days left). "
                           f"{ol.CONTACT} to renew; without renewal AQREM switches to read-only mode "
                           f"{grace_days} days after expiry.")
        else:
            enf.message = lic.message
    elif lic.state == ol.EXPIRED:
        enf.grace_until = lic.expires_at + timedelta(days=grace_days)
        if effective < enf.grace_until:
            enf.level = GRACE
            enf.message = (f"The license expired on {_date(lic.expires_at)}. All features remain available until "
                           f"{_date(enf.grace_until)}; after that AQREM switches to read-only mode. "
                           f"{ol.CONTACT} to renew.")
        else:
            enf.level = READ_ONLY
            enf.message = f"The license expired on {_date(lic.expires_at)}. {MSG_READ_ONLY_TAIL} {ol.CONTACT} to renew."
    elif problem == "seats_exceeded":
        enf.code = problem
        enf.grace_until = since + timedelta(days=grace_days)
        head = (f"{seats_used} users are registered but the license allows {lic.seats}. Adding users is blocked. "
                f"Deactivate users (or revoke pending invitations), or {ol.CONTACT.lower()} for more seats.")
        if effective < enf.grace_until:
            enf.level = GRACE
            enf.message = f"{head} Otherwise AQREM switches to read-only mode on {_date(enf.grace_until)}."
        else:
            enf.level = READ_ONLY
            enf.message = f"{head} {MSG_READ_ONLY_TAIL}"
    else:  # missing / invalid / mismatch / not yet valid
        if state.get("last_valid_at") is not None:
            enf.grace_until = since + timedelta(days=DEFAULT_GRACE_DAYS)
        if enf.grace_until is not None and effective < enf.grace_until:
            enf.level = GRACE
            enf.message = (f"{lic.message} All features remain available until {_date(enf.grace_until)}; "
                           "after that AQREM switches to read-only mode.")
        else:
            enf.level = READ_ONLY
            enf.message = f"{lic.message} {MSG_READ_ONLY_TAIL}"

    if rollback:
        enf.notes.append(MSG_CLOCK)
        if enf.level == OK:
            enf.level = WARNING
            enf.message = MSG_CLOCK
        else:
            enf.message = f"{enf.message} {MSG_CLOCK}"

    # Only persist on a clean session: never commit someone else's half-done unit of work.
    if persist and not (db.new or db.dirty or db.deleted):
        try:
            _write_state(db, real_now=real_now, effective_now=effective,
                         valid_license_id=str(lic.payload.get("license_id")) if lic.state == ol.VALID else None,
                         problem=problem, clear_problem=clear_problem, rollback=rollback)
            db.commit()
        except Exception:
            db.rollback()
            logger.error("could not persist license runtime state")
    _log_transition(enf, lic.reason)
    return enf


_last_logged: dict[str, str] = {}


def _log_transition(enf: Enforcement, reason: str) -> None:
    key = f"{enf.level}:{enf.code}:{enf.clock_rollback}"
    if _last_logged.get("k") == key:
        return
    _last_logged["k"] = key
    lvl = logging.INFO if enf.level == OK else logging.WARNING
    # Reason codes only (e.g. signature_invalid, environment_mismatch); no paths, keys or license contents.
    logger.log(lvl, "license enforcement: level=%s code=%s reason=%s clock_rollback=%s grace_until=%s",
               enf.level, enf.code, reason, enf.clock_rollback,
               enf.grace_until.isoformat() if enf.grace_until else "-")


# ----------------------------------------------------------------------------- write gate

# Writes still allowed in read_only (method, path prefix or exact path). Everything else that is not
# GET/HEAD/OPTIONS under /api/v1 is refused. Deny-by-default so new write endpoints are covered.
_READ_ONLY_ALLOWED: tuple[tuple[str, str], ...] = (
    ("POST", "/api/v1/auth/login"),
    ("POST", "/api/v1/auth/change-password"),
    ("POST", "/api/v1/auth/forgot-password"),
    ("POST", "/api/v1/auth/reset-password"),
    ("POST", "/api/v1/auth/accept-invitation/preview"),
    ("POST", "/api/v1/setup/first-admin"),
    # read-like POSTs
    ("POST", "/api/v1/answer-library/search"),
    ("POST", "/api/v1/retrieval/preview"),
    ("POST", "/api/v1/org-admin/access/preview-as"),
    ("POST", "/api/v1/org-admin/ai/test-connection"),
    ("POST", "/api/v1/org-admin/model-token/test"),
    ("POST", "/api/v1/org-admin/data-storage/preflight"),
    ("POST", "/api/v1/org-admin/data-storage/refresh-health"),
    # administration that reduces usage or changes settings (never adds users/content)
    ("POST", "/api/v1/org-admin/members/*/deactivate"),
    ("POST", "/api/v1/org-admin/members/*/password-reset"),
    ("POST", "/api/v1/org-admin/employee-join/pending/*/reject"),
    ("POST", "/api/v1/org-admin/employee-link/copied"),
    ("DELETE", "/api/v1/org-admin/access/groups/*/members/*"),
    ("POST", "/api/v1/org-admin/access/groups"),
    ("POST", "/api/v1/org-admin/access/groups/*/members"),
    ("POST", "/api/v1/org-admin/access/documents/visibility/bulk"),
    ("PATCH", "/api/v1/org-admin/access/documents/*/visibility"),
    ("PUT", "/api/v1/org-admin/chat-guardrails"),
    ("PUT", "/api/v1/org-admin/chat-sharing"),
    ("PUT", "/api/v1/org-admin/data-storage"),
    ("PUT", "/api/v1/org-admin/model-token"),
    ("POST", "/api/v1/org-admin/model-token/rotate"),
    ("DELETE", "/api/v1/org-admin/documents/*"),
    ("DELETE", "/api/v1/org-admin/audit-logs"),
    ("DELETE", "/api/v1/chat/shares/*"),
)


def _match(pattern: str, path: str) -> bool:
    pp, ps = pattern.strip("/").split("/"), path.rstrip("/").strip("/").split("/")
    return len(pp) == len(ps) and all(a == "*" or a == b for a, b in zip(pp, ps))


def write_allowed_in_read_only(method: str, path: str) -> bool:
    method = method.upper()
    if method in {"GET", "HEAD", "OPTIONS"}:
        return True
    return any(m == method and _match(p, path) for m, p in _READ_ONLY_ALLOWED)


READ_ONLY_CODE = "LICENSE_READ_ONLY"

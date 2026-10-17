"""CHECK 6: offline signed license (dedicated tier) - verification edge cases + enforcement.

Covers: edited file (every field), other signing key, malformed input, missing file, not_before,
expiry + grace, wrong organization / environment / mode, clock rollback, seat limit + seat counting,
read-only write gate (reads/admin keep working, nothing deleted), dev/test overrides in production,
and that messages never hint at a bypass.
"""

from __future__ import annotations

import base64
import json
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi.testclient import TestClient

from app.core.config import Settings, get_settings
from app.core.jwt_audiences import AUD_EMPLOYEE, AUD_ORG_ADMIN
from app.core.roles import Role
from app.core.security import create_access_token
from app.models.organization import Organization, OrganizationMembership, User
from app.services import license_enforcement as le
from app.services import offline_license as ol
from app.services.licensing import LicenseDenied, assert_can_add_seat, org_allows_sign_in

ROOT = Path(__file__).resolve().parents[2]
ENV = "contoso"
SLUG = "contoso"
FMT = "%Y-%m-%dT%H:%M:%SZ"
NOW = datetime.now(UTC).replace(microsecond=0)


def _pub(priv) -> str:
    return base64.b64encode(priv.public_key().public_bytes(serialization.Encoding.Raw,
                                                           serialization.PublicFormat.Raw)).decode()


@pytest.fixture()
def keypair():
    priv = Ed25519PrivateKey.generate()
    return priv, _pub(priv)


def _payload(**over):
    p = {"license_id": "lic-1", "organization": "Contoso", "organization_slug": SLUG, "environment": ENV,
         "deployment_mode": "dedicated", "seats": 5, "features": ["chat"], "version": 2,
         "issued_at": (NOW - timedelta(days=1)).strftime(FMT),
         "expires_at": (NOW + timedelta(days=365)).strftime(FMT)}
    for k, v in over.items():
        if v is None:
            p.pop(k, None)
        else:
            p[k] = v
    return p


def _sign(priv, payload) -> str:
    return json.dumps({"payload": payload, "alg": "Ed25519",
                       "signature": base64.b64encode(priv.sign(ol.canonical(payload))).decode()})


def _verify(text, pub, **kw):
    kw.setdefault("expected_org_slug", SLUG)
    kw.setdefault("expected_environment", ENV)
    return ol.verify_license_text(text, keys={"t": pub}, **kw)


FORBIDDEN_HINTS = ("key", "LICENSE_", "public", "signature", "path", "/", ".json", "variable", "disable",
                   "bypass", "override", "env var", "setting", "flag", "aqrem_license")


def _assert_no_hints(msg: str):
    low = msg.lower()
    for word in FORBIDDEN_HINTS:
        assert word.lower() not in low, f"message hints at {word!r}: {msg}"


# ------------------------------------------------------------------ (a) edited file, (b) other key

def test_valid_license(keypair):
    priv, pub = keypair
    r = _verify(_sign(priv, _payload()), pub)
    assert r.state == ol.VALID and r.seats == 5 and r.features == ["chat"]


@pytest.mark.parametrize("field,value", [
    ("seats", 500), ("expires_at", "2099-12-31T23:59:59Z"), ("organization_slug", "fabrikam"),
    ("environment", "prod2"), ("deployment_mode", "shared"), ("features", ["chat", "all"]),
    ("license_id", "lic-2"), ("issued_at", "2020-01-01T00:00:00Z"), ("organization", "Contoso Ltd"),
    ("grace_days", 90), ("not_before", "2020-01-01T00:00:00Z"), ("version", 3),
])
def test_any_field_change_invalidates_signature(keypair, field, value):
    priv, pub = keypair
    doc = json.loads(_sign(priv, _payload()))
    doc["payload"][field] = value
    r = _verify(json.dumps(doc), pub)
    assert r.state == ol.INVALID and r.reason == "signature_invalid"
    _assert_no_hints(r.message)


def test_removed_field_or_reformatting_semantics(keypair):
    priv, pub = keypair
    doc = json.loads(_sign(priv, _payload()))
    del doc["payload"]["features"]
    assert _verify(json.dumps(doc), pub).state == ol.INVALID
    # Whitespace / key order of the file do not matter (canonical form is signed)...
    doc = json.loads(_sign(priv, _payload()))
    pretty = json.dumps({"signature": doc["signature"], "payload": dict(reversed(list(doc["payload"].items())))},
                        indent=4)
    assert _verify(pretty, pub).state == ol.VALID
    # ...but a changed value type does ("5" vs 5).
    doc["payload"]["seats"] = "5"
    assert _verify(json.dumps(doc), pub).state == ol.INVALID


def test_edited_signature_rejected(keypair):
    priv, pub = keypair
    doc = json.loads(_sign(priv, _payload()))
    sig = bytearray(base64.b64decode(doc["signature"]))
    sig[0] ^= 1
    doc["signature"] = base64.b64encode(bytes(sig)).decode()
    assert _verify(json.dumps(doc), pub).reason == "signature_invalid"
    doc["signature"] = base64.b64encode(bytes(sig[:32])).decode()
    assert _verify(json.dumps(doc), pub).state == ol.INVALID


def test_license_signed_by_other_key(keypair):
    priv, pub = keypair
    other = Ed25519PrivateKey.generate()
    r = _verify(_sign(other, _payload()), pub)
    assert r.state == ol.INVALID and r.reason == "signature_invalid"
    # and against the keys embedded in the image
    r = ol.verify_license_text(_sign(other, _payload()), keys=dict(ol.EMBEDDED_PUBLIC_KEYS))
    assert r.state == ol.INVALID


def test_key_rotation_accepts_any_trusted_key(keypair):
    priv, pub = keypair
    new = Ed25519PrivateKey.generate()
    keys = {"old": pub, "new": _pub(new)}
    assert ol.verify_license_text(_sign(priv, _payload()), keys=keys).state == ol.VALID
    assert ol.verify_license_text(_sign(new, _payload()), keys=keys).reason == "key=new"


# ------------------------------------------------------------------ malformed / missing / required fields

@pytest.mark.parametrize("text", [
    "", "nope", "{}", "[]", '{"payload": [], "signature": "AA=="}', '{"payload": {}, "signature": "***"}',
    '{"payload": {"seats": 1}}', '{"payload": {"seats": 1}, "signature": "' + "A" * 88 + '", "alg": "RS256"}',
    "\x00\x01binary", '{"payload": {"seats": 1}, "signature": "QUFB"}',
])
def test_malformed_license(text, keypair):
    _, pub = keypair
    r = _verify(text, pub)
    assert r.state == ol.INVALID and r.reason in {"format_invalid", "signature_invalid"}
    _assert_no_hints(r.message)


@pytest.mark.parametrize("missing", list(ol.REQUIRED_FIELDS))
def test_required_fields(keypair, missing):
    priv, pub = keypair
    r = _verify(_sign(priv, _payload(**{missing: None})), pub)
    assert r.state == ol.INVALID and r.reason == "fields_invalid"


@pytest.mark.parametrize("bad", [{"seats": 0}, {"seats": -3}, {"expires_at": "tomorrow"},
                                 {"expires_at": "2027-01-01T00:00:00"}, {"not_before": "soon"}])
def test_bad_field_values(keypair, bad):
    priv, pub = keypair
    assert _verify(_sign(priv, _payload(**bad)), pub).state == ol.INVALID


def test_missing_and_unreadable_file(monkeypatch, tmp_path):
    monkeypatch.delenv("LICENSE_KEY", raising=False)
    assert ol.load_license(Settings()).state == ol.MISSING
    r = ol.load_license(Settings(license_file=str(tmp_path / "none.json")))
    assert r.state == ol.MISSING and str(tmp_path) not in r.message
    _assert_no_hints(r.message)
    assert ol.load_license(Settings(license_file=str(tmp_path))).state == ol.MISSING  # a directory
    bad = tmp_path / "bad.json"
    bad.write_bytes(b"\xff\xfe\x00garbage")
    assert ol.load_license(Settings(license_file=str(bad))).state == ol.INVALID


# ------------------------------------------------------------------ (d) expiry, not_before, (e) binding

def test_expired_and_not_yet_valid(keypair):
    priv, pub = keypair
    r = _verify(_sign(priv, _payload(expires_at=(NOW - timedelta(days=1)).strftime(FMT))), pub)
    assert r.state == ol.EXPIRED and "expired on" in r.message
    nb = (NOW + timedelta(days=10)).strftime(FMT)
    r = _verify(_sign(priv, _payload(not_before=nb)), pub)
    assert r.state == ol.NOT_YET_VALID and "valid from" in r.message
    assert _verify(_sign(priv, _payload(not_before=nb)), pub, now=NOW + timedelta(days=11)).state == ol.VALID


@pytest.mark.parametrize("over,reason", [
    ({"environment": "fabrikam"}, "environment_mismatch"),
    ({"organization_slug": "fabrikam"}, "organization_mismatch"),
    ({"deployment_mode": "shared"}, "mode_mismatch"),
])
def test_wrong_org_environment_or_mode(keypair, over, reason):
    priv, pub = keypair
    r = _verify(_sign(priv, _payload(**over)), pub)
    assert r.state == ol.MISMATCH and r.reason == reason
    _assert_no_hints(r.message)


# ------------------------------------------------------------------ dev/test overrides in production

@pytest.mark.parametrize("app_env", ["production", "staging", "prod", "Production"])
def test_key_override_ignored_outside_dev(keypair, app_env):
    _, pub = keypair
    s = Settings.model_construct(app_env=app_env, license_public_key=pub, deployment_mode="dedicated")
    assert ol.trusted_keys(s) == ol.EMBEDDED_PUBLIC_KEYS


def test_key_override_only_in_dev_and_test(keypair):
    _, pub = keypair
    for env in ("development", "test"):
        assert ol.trusted_keys(Settings.model_construct(app_env=env, license_public_key=pub)) == {"override": pub}


def test_production_forces_licensing_test_mode_off():
    from app.services.licensing import licensing_test_mode_effective

    assert licensing_test_mode_effective(Settings.model_construct(app_env="production", licensing_test_mode=True)) \
        is False


def test_no_grace_or_key_setting_exists():
    """Grace/warning windows are code constants or signed license fields, never environment settings."""
    names = {n.lower() for n in Settings.model_fields}
    for f in Settings.model_fields.values():
        names |= {str(a).lower() for a in getattr(f.validation_alias, "choices", []) or []}
    assert not [n for n in names if "grace" in n or "license_bypass" in n or "skip_license" in n]


# ------------------------------------------------------------------ enforcement (DB)

@pytest.fixture()
def ded(monkeypatch, tmp_path, keypair, db_session):
    priv, pub = keypair
    lic = tmp_path / "aqrem.license.json"
    monkeypatch.delenv("LICENSE_KEY", raising=False)
    monkeypatch.setenv("DEPLOYMENT_MODE", "dedicated")
    monkeypatch.setenv("ENVIRONMENT_NAME", ENV)
    monkeypatch.setenv("DEDICATED_ORG_SLUG", SLUG)
    monkeypatch.setenv("DEDICATED_ORG_NAME", "Contoso")
    monkeypatch.setenv("LICENSE_FILE", str(lic))
    monkeypatch.setenv("LICENSE_PUBLIC_KEY", pub)
    get_settings.cache_clear()
    le.clear_cache()
    from app.core.deployment import ensure_dedicated_organization

    org = ensure_dedicated_organization(db_session, get_settings())
    db_session.flush()

    class D:
        pass

    d = D()
    d.priv, d.pub, d.file, d.org, d.db = priv, pub, lic, org, db_session
    d.write = lambda **over: lic.write_text(_sign(priv, _payload(**over)))
    d.eval = lambda now=None: le.evaluate(db_session, get_settings(), now=now, use_cache=False)
    yield d
    get_settings.cache_clear()
    le.clear_cache()


def _add_members(db, org, n, *, prefix="m"):
    users = []
    for i in range(n):
        u = User(email=f"{prefix}{i}@contoso.example.com", full_name=f"M{i}", hashed_password="x")
        db.add(u)
        db.flush()
        db.add(OrganizationMembership(organization_id=org.id, user_id=u.id, role=Role.EDITOR.value))
        users.append(u)
    db.flush()
    return users


def _iso(days):
    return (NOW + timedelta(days=days)).strftime(FMT)


def test_enforcement_ok_and_state_persisted(ded):
    ded.write()
    e = ded.eval()
    assert e.level == le.OK and e.code == ol.VALID and not e.read_only
    from app.models.license_state import LicenseRuntimeState
    st = ded.db.get(LicenseRuntimeState, 1)
    assert st.highest_seen_at is not None and st.last_valid_at is not None and st.last_license_id == "lic-1"


def test_expiring_soon_warning(ded):
    ded.write(expires_at=_iso(10))
    e = ded.eval()
    assert e.level == le.WARNING and "expires on" in e.message and not e.read_only


def test_expiry_grace_then_read_only(ded):
    ded.write(expires_at=_iso(-3))
    e = ded.eval()
    assert e.level == le.GRACE and not e.read_only and e.grace_until.date() == (NOW + timedelta(days=11)).date()
    le.clear_cache()
    ded.write(expires_at=_iso(-20))
    e = ded.eval()
    assert e.level == le.READ_ONLY and e.read_only and "read-only" in e.message


def test_signed_grace_days(ded):
    ded.write(expires_at=_iso(-1), grace_days=0)
    assert ded.eval().level == le.READ_ONLY
    ded.write(expires_at=_iso(-20), grace_days=30)
    assert ded.eval().level == le.GRACE


@pytest.mark.parametrize("breaker", ["missing", "tampered", "malformed", "other_key", "wrong_env",
                                     "wrong_org", "shared_license", "not_yet_valid"])
def test_problem_without_prior_valid_license_is_read_only(ded, breaker):
    _break(ded, breaker)
    e = ded.eval()
    assert e.level == le.READ_ONLY, (breaker, e)
    _assert_no_hints(e.message)
    assert "read-only" in e.message


def _break(ded, breaker):
    if breaker == "missing":
        ded.file.unlink(missing_ok=True)
    elif breaker == "tampered":
        doc = json.loads(_sign(ded.priv, _payload()))
        doc["payload"]["seats"] = 9999
        ded.file.write_text(json.dumps(doc))
    elif breaker == "malformed":
        ded.file.write_text("{not json")
    elif breaker == "other_key":
        ded.file.write_text(_sign(Ed25519PrivateKey.generate(), _payload()))
    elif breaker == "wrong_env":
        ded.write(environment="fabrikam")
    elif breaker == "wrong_org":
        ded.write(organization_slug="fabrikam")
    elif breaker == "shared_license":
        ded.write(deployment_mode="shared")
    elif breaker == "not_yet_valid":
        ded.write(not_before=_iso(5))


@pytest.mark.parametrize("breaker", ["missing", "tampered", "other_key", "wrong_env"])
def test_problem_after_valid_license_gets_grace_then_read_only(ded, breaker):
    ded.write()
    assert ded.eval(NOW).level == le.OK
    _break(ded, breaker)
    e = ded.eval(NOW + timedelta(hours=1))
    assert e.level == le.GRACE and not e.read_only
    assert ded.eval(NOW + timedelta(days=13)).level == le.GRACE
    assert ded.eval(NOW + timedelta(days=15)).level == le.READ_ONLY


def test_switching_problems_does_not_restart_grace(ded):
    ded.write()
    ded.eval(NOW)
    _break(ded, "missing")
    ded.eval(NOW + timedelta(days=1))
    _break(ded, "tampered")
    assert ded.eval(NOW + timedelta(days=10)).level == le.GRACE
    _break(ded, "wrong_env")
    assert ded.eval(NOW + timedelta(days=16)).level == le.READ_ONLY


def test_valid_license_restores_full_service(ded):
    ded.write(expires_at=_iso(-30))
    assert ded.eval().level == le.READ_ONLY
    ded.write(expires_at=_iso(400), license_id="lic-renewed")
    e = ded.eval()
    assert e.level == le.OK and not e.read_only


# ------------------------------------------------------------------ (c) clock rollback

def test_clock_rollback_flagged_and_does_not_extend_license(ded):
    ded.write(expires_at=_iso(1))
    assert ded.eval(NOW).level == le.WARNING                       # expiring soon
    assert ded.eval(NOW + timedelta(days=2)).code == ol.EXPIRED      # clock moved past expiry
    e = ded.eval(NOW - timedelta(days=5))                           # clock set back
    assert e.clock_rollback and e.code == ol.EXPIRED and e.level == le.GRACE
    assert e.effective_now >= NOW + timedelta(days=2)
    assert "clock" in e.message.lower()
    _assert_no_hints(e.message)
    from app.models.license_state import LicenseRuntimeState
    ded.db.expire_all()
    st = ded.db.get(LicenseRuntimeState, 1)
    assert st.clock_rollback_at is not None
    assert st.highest_seen_at >= NOW + timedelta(days=2)             # never lowered


def test_rollback_grace_cannot_be_extended(ded):
    ded.write(expires_at=_iso(-1))
    assert ded.eval(NOW + timedelta(days=20)).level == le.READ_ONLY
    assert ded.eval(NOW).level == le.READ_ONLY                      # clock back into the "grace" window


def test_small_skew_not_flagged(ded):
    ded.write()
    ded.eval(NOW)
    e = ded.eval(NOW - timedelta(minutes=30))
    assert not e.clock_rollback and e.level == le.OK


def test_clock_before_license_issue_time_flagged(ded):
    ded.write(issued_at=_iso(3), expires_at=_iso(400))
    e = ded.eval(NOW)
    assert e.clock_rollback and e.level == le.WARNING and e.effective_now >= NOW + timedelta(days=3)


def test_rollback_flag_clears_when_clock_recovers(ded):
    ded.write()
    ded.eval(NOW + timedelta(days=1))
    assert ded.eval(NOW).clock_rollback
    assert not ded.eval(NOW + timedelta(days=1, minutes=5)).clock_rollback


# ------------------------------------------------------------------ (f) seats

def test_seat_counting_excludes_deactivated(ded):
    from app.services.seat_usage import get_seat_usage

    users = _add_members(ded.db, ded.org, 3)
    assert get_seat_usage(ded.db, ded.org).seats_used == 3
    m = ded.db.query(OrganizationMembership).filter_by(user_id=users[0].id).one()
    m.is_active = False                         # deactivated membership
    users[1].is_active = False                  # deactivated user account
    ded.db.flush()
    assert get_seat_usage(ded.db, ded.org).active_members == 1


def test_seat_limit_reached_blocks_new_users_only(ded):
    ded.write(seats=2)
    _add_members(ded.db, ded.org, 2)
    e = ded.eval()
    assert e.level == le.OK and not e.can_add_users
    with pytest.raises(LicenseDenied, match="Seat limit reached"):
        assert_can_add_seat(ded.db, ded.org, get_settings())


def test_seats_exceeded_grace_then_read_only(ded):
    ded.write(seats=2)
    users = _add_members(ded.db, ded.org, 3)
    e = ded.eval(NOW)
    assert e.code == "seats_exceeded" and e.level == le.GRACE and "3 users" in e.message
    assert ded.eval(NOW + timedelta(days=15)).level == le.READ_ONLY
    # deactivating a user fixes it (allowed in read-only) and restores service
    ded.db.query(OrganizationMembership).filter_by(user_id=users[0].id).one().is_active = False
    ded.db.flush()
    ded.db.commit()
    assert ded.eval(NOW + timedelta(days=15, hours=1)).level == le.OK


def test_cannot_add_users_without_valid_license(ded):
    with pytest.raises(LicenseDenied):
        assert_can_add_seat(ded.db, ded.org, get_settings())


# ------------------------------------------------------------------ sign-in, shared mode

def test_dedicated_sign_in_never_depends_on_license(ded):
    ok, _ = org_allows_sign_in(ded.org, get_settings())  # no license installed
    assert ok


def test_shared_mode_ignores_offline_license(db_session, monkeypatch, keypair, tmp_path):
    priv, pub = keypair
    lic = tmp_path / "l.json"
    lic.write_text(_sign(priv, _payload(seats=999)))
    monkeypatch.setenv("LICENSE_FILE", str(lic))
    monkeypatch.setenv("LICENSE_PUBLIC_KEY", pub)
    get_settings.cache_clear()
    try:
        s = get_settings()
        assert not s.is_dedicated
        assert le.evaluate(db_session, s, use_cache=False).mode == "shared"
        org = Organization(name="S", slug="s-lic", license_limit=0, is_active=True, license_status="active")
        ok, msg = org_allows_sign_in(org, s)
        assert not ok and "No licensed seats" in msg   # per-org seats, not the file
    finally:
        get_settings.cache_clear()


# ------------------------------------------------------------------ write gate (HTTP)

def _token(user, org, role, aud):
    return create_access_token(str(user.id), {"organization_id": str(org.id), "role": role, "auth_version": 1},
                               audience=aud)


@pytest.fixture()
def api(ded):
    from app.db.session import get_db
    from app.main import create_app
    from app.tenant_store.deps import get_tenant_db

    app = create_app()
    app.dependency_overrides[get_db] = lambda: ded.db
    app.dependency_overrides[get_tenant_db] = lambda: ded.db
    admin = User(email="admin@contoso.example.com", full_name="Admin", hashed_password="x")
    member = User(email="user@contoso.example.com", full_name="User", hashed_password="x")
    ded.db.add_all([admin, member])
    ded.db.flush()
    ded.db.add(OrganizationMembership(organization_id=ded.org.id, user_id=admin.id, role=Role.ORG_ADMIN.value))
    ded.db.add(OrganizationMembership(organization_id=ded.org.id, user_id=member.id, role=Role.EDITOR.value))
    ded.db.commit()
    c = TestClient(app)  # no lifespan: the test session is the database
    oid = str(ded.org.id)
    ded.h_admin = {"Authorization": f"Bearer {_token(admin, ded.org, 'ORG_ADMIN', AUD_ORG_ADMIN)}",
                   "X-Organization-Id": oid}
    ded.h_admin_emp = {"Authorization": f"Bearer {_token(admin, ded.org, 'ORG_ADMIN', AUD_EMPLOYEE)}",
                       "X-Organization-Id": oid}
    ded.h_user = {"Authorization": f"Bearer {_token(member, ded.org, 'EDITOR', AUD_EMPLOYEE)}",
                  "X-Organization-Id": oid}
    ded.member = member
    yield c
    app.dependency_overrides.clear()


def _counts(db):
    from sqlalchemy import text
    tables = ["organizations", "users", "organization_memberships", "projects", "client_documents",
              "audit_events"]
    return {t: db.execute(text(f"SELECT count(*) FROM {t}")).scalar() for t in tables}


def test_read_only_blocks_writes_keeps_reads_and_admin(api, ded):
    ded.write(expires_at=_iso(-30))
    le.clear_cache()
    before = _counts(ded.db)
    r = api.get("/api/v1/projects", headers=ded.h_user)
    assert r.status_code == 200, r.text
    r = api.post("/api/v1/projects", headers=ded.h_user, json={"name": "New", "description": ""})
    assert r.status_code == 403 and r.json()["detail"]["code"] == le.READ_ONLY_CODE
    _assert_no_hints(r.json()["message"])
    def _ro(resp):
        return resp.status_code == 403 and resp.json()["detail"]["code"] == le.READ_ONLY_CODE

    assert _ro(api.post("/api/v1/chat/ask", headers=ded.h_user, json={"question": "hi"}))
    assert _ro(api.post("/api/v1/org-admin/documents/upload", headers=ded.h_admin,
                        files={"file": ("a.txt", b"hello", "text/plain")}))
    assert _ro(api.post("/api/v1/org-admin/members/invite", headers=ded.h_admin,
                        json={"email": "new@contoso.example.com", "role": "EDITOR"}))
    assert _ro(api.post("/api/v1/public/join/start", json={"email": "x@contoso.example.com"}))
    assert api.get("/api/v1/license/status", headers=ded.h_admin_emp).status_code == 200
    # read-only evaluation + refused writes changed nothing (no data deleted or created)
    assert _counts(ded.db) == before
    # admin: usage-reducing actions still work in read-only
    m = ded.db.query(OrganizationMembership).filter_by(user_id=ded.member.id).one()
    r = api.post(f"/api/v1/org-admin/members/{m.id}/deactivate", headers=ded.h_admin)
    assert r.status_code in (200, 204), r.text


def test_full_service_allows_writes(api, ded):
    ded.write()
    le.clear_cache()
    r = api.post("/api/v1/projects", headers=ded.h_user, json={"name": "New", "description": ""})
    assert r.status_code in (200, 201), r.text


def test_status_endpoint_admin_vs_user(api, ded):
    ded.write(expires_at=_iso(-30))
    le.clear_cache()
    a = api.get("/api/v1/license/status", headers=ded.h_admin_emp).json()
    u = api.get("/api/v1/license/status", headers=ded.h_user).json()
    assert a["read_only"] and u["read_only"] and a["level"] == "read_only"
    assert "expired on" in a["message"] and a["expires_at"]
    assert "expired" not in u["message"] and "seats" not in u and "code" not in u
    for m in (a["message"], u["message"]):
        _assert_no_hints(m)


def test_status_endpoint_shared_mode(client, db_session):
    org = Organization(name="Shared", slug="shared-lic", license_limit=5)
    u = User(email="s@shared.example.com", full_name="S", hashed_password="x")
    db_session.add_all([org, u])
    db_session.flush()
    db_session.add(OrganizationMembership(organization_id=org.id, user_id=u.id, role=Role.EDITOR.value))
    db_session.commit()
    h = {"Authorization": f"Bearer {_token(u, org, 'EDITOR', AUD_EMPLOYEE)}", "X-Organization-Id": str(org.id)}
    assert client.get("/api/v1/license/status", headers=h).json() == {"mode": "shared", "level": "ok",
                                                                       "read_only": False}


def test_write_gate_allowlist_is_minimal_and_current():
    from fastapi.routing import APIRoute
    from app.main import create_app

    def walk(routes):
        for r in routes:
            if isinstance(r, APIRoute):
                yield r.path, r.methods
            elif type(r).__name__ == "_IncludedRouter":
                ctx = r.effective_route_contexts
                for x in (ctx() if callable(ctx) else ctx):
                    if type(x).__name__ == "_IncludedRouter":
                        yield from walk([x])
                    else:
                        yield x.path, getattr(x, "methods", None) or set()

    writes = {(m, p) for p, ms in walk(create_app().routes) for m in ms if m not in {"GET", "HEAD", "OPTIONS"}}
    assert len(writes) > 50
    for method, pattern in le._READ_ONLY_ALLOWED:   # every allowlist entry matches a real route
        assert any(m == method and le._match(pattern, p.replace("{", "").replace("}", "")) or
                   (m == method and len(p.split("/")) == len(pattern.split("/")) and
                    all(a == "*" or a == b for a, b in zip(pattern.split("/"), p.split("/"))))
                   for m, p in writes), (method, pattern)
    must_block = [("POST", "/api/v1/org-admin/documents/upload"), ("POST", "/api/v1/chat/ask"),
                  ("POST", "/api/v1/chat/ask/stream"), ("POST", "/api/v1/projects"),
                  ("POST", "/api/v1/questionnaires"), ("POST", "/api/v1/sources"),
                  ("POST", "/api/v1/org-admin/members/invite"), ("POST", "/api/v1/auth/accept-invitation"),
                  ("POST", "/api/v1/public/join/start"), ("POST", "/api/v1/public/join/complete"),
                  ("POST", "/api/v1/org-admin/employee-join/pending/x/approve"),
                  ("POST", "/api/v1/questionnaires/q1/upload"), ("POST", "/api/v1/chat/shares"),
                  ("POST", "/api/v1/sources/s1/files"), ("POST", "/api/v1/org-admin/documents/reindex-all")]
    for m, p in must_block:
        assert not le.write_allowed_in_read_only(m, p), (m, p)
    for m, p in [("POST", "/api/v1/auth/login"), ("GET", "/api/v1/anything"),
                 ("POST", "/api/v1/org-admin/members/123/deactivate")]:
        assert le.write_allowed_in_read_only(m, p)


# ------------------------------------------------------------------ CLI

def test_cli_sign_and_verify(tmp_path):
    keys = tmp_path / "k"
    cli = [sys.executable, str(ROOT / "scripts/aqrem_license.py")]
    out = subprocess.run(cli + ["keygen", "--out-dir", str(keys)], capture_output=True, text=True, check=True).stdout
    pub = (keys / "aqrem-license-public.b64").read_text().strip()
    assert pub in out and "PRIVATE KEY" not in out
    assert (keys / "aqrem-license-private.pem").stat().st_mode & 0o077 == 0
    lic = tmp_path / "c.license.json"
    subprocess.run(cli + ["sign", "--key", str(keys / "aqrem-license-private.pem"), "--org", "Contoso",
                          "--slug", SLUG, "--environment", ENV, "--seats", "10", "--expires", "2099-12-31",
                          "--grace-days", "7", "--features", "chat,questionnaires", "--out", str(lic)], check=True)
    payload = json.loads(lic.read_text())["payload"]
    assert payload["environment"] == ENV and payload["organization_slug"] == SLUG and payload["version"] == 2
    r = subprocess.run(cli + ["verify", "--license", str(lic), "--public-key", pub, "--slug", SLUG,
                              "--environment", ENV], capture_output=True, text=True, cwd=str(ROOT / "backend"))
    assert r.returncode == 0 and '"state": "valid"' in r.stdout, r.stdout + r.stderr
    r = subprocess.run(cli + ["verify", "--license", str(lic), "--public-key", pub, "--environment", "other"],
                       capture_output=True, text=True, cwd=str(ROOT / "backend"))
    assert r.returncode == 1 and "mismatch" in r.stdout
    # refuses to sign without binding or with past expiry
    bad = subprocess.run(cli + ["sign", "--key", str(keys / "aqrem-license-private.pem"), "--org", "C",
                                "--slug", SLUG, "--environment", ENV, "--seats", "1", "--expires", "2001-01-01"],
                         capture_output=True, text=True)
    assert bad.returncode != 0

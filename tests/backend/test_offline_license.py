"""Offline Ed25519 license (dedicated tier)."""

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

from app.core.config import Settings, get_settings
from app.models.organization import Organization
from app.services import offline_license as ol
from app.services.licensing import LicenseDenied, assert_can_add_seat, org_allows_sign_in

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture()
def keypair():
    priv = Ed25519PrivateKey.generate()
    pub = base64.b64encode(priv.public_key().public_bytes(serialization.Encoding.Raw,
                                                          serialization.PublicFormat.Raw)).decode()
    return priv, pub


def _make(priv, *, seats=5, days=30, features=("chat",)):
    payload = {"license_id": "t", "organization": "Contoso", "seats": seats, "features": list(features),
               "issued_at": "2026-01-01T00:00:00Z",
               "expires_at": (datetime.now(UTC) + timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")}
    return json.dumps({"payload": payload, "signature": base64.b64encode(priv.sign(ol.canonical(payload))).decode()})


def test_valid_license(keypair):
    priv, pub = keypair
    r = ol.verify_license_text(_make(priv), public_key_b64=pub)
    assert r.state == ol.VALID and r.seats == 5 and r.features == ["chat"]


def test_tampered_license_rejected(keypair):
    priv, pub = keypair
    doc = json.loads(_make(priv))
    doc["payload"]["seats"] = 500
    r = ol.verify_license_text(json.dumps(doc), public_key_b64=pub)
    assert r.state == ol.INVALID and "signature" in r.message


def test_other_key_rejected(keypair):
    priv, _ = keypair
    r = ol.verify_license_text(_make(priv))  # embedded production key
    assert r.state == ol.INVALID


def test_expired_license_message(keypair):
    priv, pub = keypair
    r = ol.verify_license_text(_make(priv, days=-1), public_key_b64=pub)
    assert r.state == ol.EXPIRED and "expired on" in r.message


def test_garbage_and_missing(monkeypatch, tmp_path):
    assert ol.verify_license_text("nope").state == ol.INVALID
    monkeypatch.delenv("LICENSE_KEY", raising=False)
    assert ol.load_license(Settings()).state == ol.MISSING
    r = ol.load_license(Settings(license_file=str(tmp_path / "none.json")))
    assert r.state == ol.MISSING and "LICENSE_FILE" in r.message


def test_dedicated_sign_in_and_seats(db_session, keypair, tmp_path, monkeypatch):
    priv, pub = keypair
    monkeypatch.delenv("LICENSE_KEY", raising=False)
    org = Organization(name="Contoso", slug="contoso-lic", license_limit=0)
    db_session.add(org)
    db_session.flush()
    lic = tmp_path / "aqrem.license.json"
    s = Settings(deployment_mode="dedicated", license_file=str(lic), license_public_key=pub)
    ok, msg = org_allows_sign_in(org, s)
    assert not ok and "No license file" in msg
    lic.write_text(_make(priv, days=-3))
    ok, msg = org_allows_sign_in(org, s)
    assert not ok and "expired" in msg
    lic.write_text(_make(priv, seats=1))
    ok, msg = org_allows_sign_in(org, s)
    assert ok, msg
    from app.core.roles import Role
    from app.models.organization import OrganizationMembership, User

    u = User(email="one@contoso.example.com", full_name="One", hashed_password="x")
    db_session.add(u)
    db_session.flush()
    db_session.add(OrganizationMembership(organization_id=org.id, user_id=u.id, role=Role.ORG_ADMIN.value))
    db_session.flush()
    with pytest.raises(LicenseDenied, match="Seat limit reached"):
        assert_can_add_seat(db_session, org, s)


def test_shared_mode_keeps_existing_logic(db_session):
    org = Organization(name="S", slug="s-lic", license_limit=0, is_active=True, license_status="active")
    ok, msg = org_allows_sign_in(org, Settings())
    assert not ok and "No licensed seats" in msg


def test_cli_sign_and_verify(tmp_path):
    keys = tmp_path / "k"
    out = subprocess.run([sys.executable, str(ROOT / "scripts/aqrem_license.py"), "keygen", "--out-dir", str(keys)],
                         capture_output=True, text=True, check=True).stdout
    pub = (keys / "aqrem-license-public.b64").read_text().strip()
    assert pub in out
    assert (keys / "aqrem-license-private.pem").stat().st_mode & 0o077 == 0
    lic = tmp_path / "c.license.json"
    subprocess.run([sys.executable, str(ROOT / "scripts/aqrem_license.py"), "sign", "--key",
                    str(keys / "aqrem-license-private.pem"), "--org", "Contoso", "--seats", "10",
                    "--expires", "2099-12-31", "--features", "chat,questionnaires", "--out", str(lic)], check=True)
    r = subprocess.run([sys.executable, str(ROOT / "scripts/aqrem_license.py"), "verify", "--license", str(lic),
                        "--public-key", pub], capture_output=True, text=True, cwd=str(ROOT / "backend"))
    assert r.returncode == 0, r.stdout + r.stderr
    assert '"state": "valid"' in r.stdout

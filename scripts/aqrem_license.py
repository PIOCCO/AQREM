#!/usr/bin/env python3
"""AQREM offline license tool (operator side). Requires: pip install cryptography

  keygen  --out-dir DIR            create Ed25519 keypair (private key 0600; NEVER commit it)
  sign    --key PRIV --org NAME --seats N --expires YYYY-MM-DD [--features a,b] [--slug s] [--out F]
  verify  --license F [--public-key B64]

Paste the printed public key into backend/app/services/offline_license.py (EMBEDDED_PUBLIC_KEY_B64)
or set LICENSE_PUBLIC_KEY on the environment. Install a license with LICENSE_FILE=/path or
LICENSE_KEY=<file contents> (e.g. Key Vault secret 'license-key').
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))


def _canonical(payload: dict) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def keygen(out_dir: str) -> None:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    d = Path(out_dir).expanduser()
    d.mkdir(parents=True, exist_ok=True)
    os.chmod(d, 0o700)
    priv = Ed25519PrivateKey.generate()
    priv_path = d / "aqrem-license-private.pem"
    if priv_path.exists():
        sys.exit(f"{priv_path} exists; refusing to overwrite")
    fd = os.open(priv_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as f:
        f.write(priv.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                   serialization.NoEncryption()))
    pub = priv.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    pub_b64 = base64.b64encode(pub).decode()
    (d / "aqrem-license-public.b64").write_text(pub_b64 + "\n")
    print(f"private key: {priv_path} (keep offline / in a vault; never commit)")
    print(f"public key (base64): {pub_b64}")


def sign(args) -> None:
    from cryptography.hazmat.primitives import serialization

    priv = serialization.load_pem_private_key(Path(args.key).expanduser().read_bytes(), password=None)
    expires = datetime.strptime(args.expires, "%Y-%m-%d").replace(hour=23, minute=59, second=59, tzinfo=UTC)
    payload = {
        "license_id": str(uuid.uuid4()),
        "organization": args.org,
        "organization_slug": args.slug or "",
        "seats": int(args.seats),
        "features": [f.strip() for f in (args.features or "").split(",") if f.strip()],
        "issued_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "expires_at": expires.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "deployment_mode": "dedicated",
        "version": 1,
    }
    sig = priv.sign(_canonical(payload))
    doc = {"payload": payload, "signature": base64.b64encode(sig).decode(), "alg": "Ed25519"}
    text = json.dumps(doc, indent=2) + "\n"
    if args.out:
        Path(args.out).write_text(text)
        print(f"wrote {args.out}")
    else:
        sys.stdout.write(text)


def verify(args) -> None:
    from app.services.offline_license import verify_license_text

    res = verify_license_text(Path(args.license).read_text(), public_key_b64=args.public_key)
    print(json.dumps({"state": res.state, "message": res.message, "payload": res.payload}, indent=2))
    sys.exit(0 if res.state == "valid" else 1)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    k = sub.add_parser("keygen")
    k.add_argument("--out-dir", required=True)
    s = sub.add_parser("sign")
    s.add_argument("--key", required=True)
    s.add_argument("--org", required=True)
    s.add_argument("--slug")
    s.add_argument("--seats", required=True, type=int)
    s.add_argument("--expires", required=True)
    s.add_argument("--features")
    s.add_argument("--out")
    v = sub.add_parser("verify")
    v.add_argument("--license", required=True)
    v.add_argument("--public-key")
    a = p.parse_args()
    if a.cmd == "keygen":
        keygen(a.out_dir)
    elif a.cmd == "sign":
        sign(a)
    else:
        verify(a)


if __name__ == "__main__":
    main()

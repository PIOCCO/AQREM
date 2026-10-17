"""Operator-only control of the dedicated setup screen. Run inside the api container / with its env.

    python -m app.setup status
    python -m app.setup reset --confirm                 # generate a new token, print it ONCE
    python -m app.setup reset --confirm --token-stdin   # read the new token from stdin (not echoed)
    python -m app.setup clear-lockout [--ip 10.1.2.3]   # forget failed attempts (all, or one address)

Setup is single-use: ``reset`` only works while no administrator exists (expired or lost token before
the first admin was created). To recover access afterwards use ``python -m app.ops recover-admin``.
There is no API route or environment toggle for any of this.
"""

from __future__ import annotations

import argparse
import secrets
import sys


def _audit(db, action: str, metadata: dict) -> None:
    from app.audit.service import record_audit
    from app.core.deployment import get_dedicated_org

    org = get_dedicated_org(db)
    if org is not None:
        record_audit(db, organization_id=org.id, user_id=None, action=action,
                     resource_type="organization", resource_id=str(org.id), metadata=metadata)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.setup")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status", help="show setup state (never prints the token)")
    reset = sub.add_parser("reset", help="issue a NEW one-time token (only while no admin exists)")
    reset.add_argument("--confirm", action="store_true", help="required")
    reset.add_argument("--token-stdin", action="store_true", help="read the new token from stdin")
    clear = sub.add_parser("clear-lockout", help="forget failed setup attempts")
    clear.add_argument("--ip", default=None, help="only this client address (default: all)")
    args = parser.parse_args(argv)

    from app.core.config import get_settings
    from app.core.deployment import dedicated_setup_required
    from app.db.session import SessionLocal
    from app.services import setup_guard

    settings = get_settings()
    if not settings.is_dedicated:
        print("DEPLOYMENT_MODE is not 'dedicated'; setup does not exist here.", file=sys.stderr)
        return 2

    with SessionLocal() as db:
        if args.cmd == "status":
            st = setup_guard.setup_state(db, settings)
            db.commit()
            line = f"state={st.state}"
            if st.expires_at:
                line += f" expires_at={st.expires_at.isoformat()} source={st.token.source if st.token else '-'}"
            print(line)
            return 0

        if args.cmd == "clear-lockout":
            try:
                n = setup_guard.clear_lockout(db, args.ip)
            except ValueError:
                print("Refusing: --ip is not a valid IP address.", file=sys.stderr)
                return 2
            _audit(db, "setup_lockout_cleared_by_operator", {"ip": args.ip or "*", "removed": n})
            db.commit()
            print(f"Cleared {n} failed setup attempt(s){' for ' + args.ip if args.ip else ''}.")
            return 0

        if not args.confirm:
            print("Refusing: add --confirm to re-issue the setup token.", file=sys.stderr)
            return 2
        if not dedicated_setup_required(db):
            print("Refusing: an administrator already exists; setup is single-use. "
                  "Use: python -m app.ops recover-admin --org <slug> --email <email> [--reset-password]",
                  file=sys.stderr)
            return 3
        token = sys.stdin.readline().strip() if args.token_stdin else secrets.token_urlsafe(32)
        try:
            row = setup_guard.operator_reset(db, settings, token)
        except ValueError as exc:
            print(f"Refusing: {exc}", file=sys.stderr)
            return 2
        _audit(db, "setup_reopened_by_operator", {})
        db.commit()
        expires = setup_guard.token_expires_at(row, settings).isoformat()
        print(f"Setup re-opened until {expires}.", file=sys.stderr)
        if not args.token_stdin:
            # Shown once on the operator's terminal; only its hash is stored.
            print(token)
        return 0


if __name__ == "__main__":
    raise SystemExit(main())

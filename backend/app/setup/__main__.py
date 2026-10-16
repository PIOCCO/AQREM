"""Operator-only control of the dedicated setup screen. Run inside the api container / with its env.

    python -m app.setup status
    python -m app.setup reset --confirm                 # generate a new token, print it ONCE
    python -m app.setup reset --confirm --token-stdin   # read the new token from stdin (not echoed)

Reset revokes any unconsumed token and issues a new one valid for SETUP_TOKEN_TTL_MINUTES. Setup then
opens even if an administrator exists (recovery: creates an additional org admin). There is no API or
environment toggle that does this.
"""

from __future__ import annotations

import argparse
import secrets
import sys


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.setup")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status", help="show setup state (never prints the token)")
    reset = sub.add_parser("reset", help="re-open setup with a NEW one-time token")
    reset.add_argument("--confirm", action="store_true", help="required")
    reset.add_argument("--token-stdin", action="store_true", help="read the new token from stdin")
    args = parser.parse_args(argv)

    from app.core.config import get_settings
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

        if not args.confirm:
            print("Refusing: add --confirm to re-open setup.", file=sys.stderr)
            return 2
        token = sys.stdin.readline().strip() if args.token_stdin else secrets.token_urlsafe(32)
        try:
            row = setup_guard.operator_reset(db, settings, token)
        except ValueError as exc:
            print(f"Refusing: {exc}", file=sys.stderr)
            return 2
        from app.audit.service import record_audit
        from app.core.deployment import get_dedicated_org

        org = get_dedicated_org(db)
        if org is not None:
            record_audit(db, organization_id=org.id, user_id=None, action="setup_reopened_by_operator",
                         resource_type="organization", resource_id=str(org.id), metadata={})
        db.commit()
        expires = setup_guard.token_expires_at(row, settings).isoformat()
        print(f"Setup re-opened until {expires}.", file=sys.stderr)
        if not args.token_stdin:
            # Shown once on the operator's terminal; only its hash is stored.
            print(token)
        return 0


if __name__ == "__main__":
    raise SystemExit(main())

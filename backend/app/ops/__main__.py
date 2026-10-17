"""Operator-only account recovery. Server-side CLI; there is deliberately no web route for this.

    python -m app.ops recover-admin --org <slug> --email <email> [--reset-password]

* Grants ORG_ADMIN in the organization to the user with that email (creating the user if needed).
* --reset-password (implied for a new user): sets a random temporary password, prints it ONCE to this
  terminal (stdout) and forces a change at next sign-in. Nothing is emailed; only the hash is stored.
* Audit-logged in the organization as ``admin_recovered_by_operator``.
"""

from __future__ import annotations

import argparse
import secrets
import sys


def recover_admin(db, *, org_slug: str, email: str, reset_password: bool) -> tuple[str | None, dict]:
    """Returns (temporary password or None, audit metadata). Raises LookupError for an unknown org."""
    from app.audit.service import record_audit
    from app.core.roles import Role
    from app.core.security import hash_password
    from app.models.organization import Organization, OrganizationMembership, User

    org = (db.query(Organization)
           .filter(Organization.slug == org_slug.strip().lower(), Organization.deleted_at.is_(None))
           .one_or_none())
    if org is None:
        raise LookupError("organization not found")
    email = email.strip().lower()
    user = db.query(User).filter(User.email == email).one_or_none()
    created = user is None
    temp = None
    if created:
        temp = secrets.token_urlsafe(18)
        user = User(email=email, full_name=email.split("@")[0], hashed_password=hash_password(temp),
                    is_active=True, must_change_password=True)
        db.add(user)
        db.flush()
    elif reset_password:
        temp = secrets.token_urlsafe(18)
        user.hashed_password = hash_password(temp)
        user.must_change_password = True
        user.is_active = True
    m = db.query(OrganizationMembership).filter_by(organization_id=org.id, user_id=user.id).one_or_none()
    previous_role = m.role if m else None
    if m is None:
        db.add(OrganizationMembership(organization_id=org.id, user_id=user.id, role=Role.ORG_ADMIN.value))
    else:
        m.role = Role.ORG_ADMIN.value
        if hasattr(m, "is_active"):
            m.is_active = True
    meta = {"created_user": created, "password_reset": temp is not None, "previous_role": previous_role,
            "channel": "operator_cli"}
    record_audit(db, organization_id=org.id, user_id=user.id, action="admin_recovered_by_operator",
                 resource_type="user", resource_id=str(user.id), metadata=meta)
    db.flush()
    return temp, meta


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.ops")
    sub = parser.add_subparsers(dest="cmd", required=True)
    rec = sub.add_parser("recover-admin", help="grant ORG_ADMIN to a user (operator recovery)")
    rec.add_argument("--org", required=True, help="organization slug")
    rec.add_argument("--email", required=True)
    rec.add_argument("--reset-password", action="store_true", help="issue a one-time temporary password")
    args = parser.parse_args(argv)

    from app.db.session import SessionLocal

    with SessionLocal() as db:
        try:
            temp, meta = recover_admin(db, org_slug=args.org, email=args.email, reset_password=args.reset_password)
        except LookupError:
            print(f"Refusing: no organization with slug {args.org!r}.", file=sys.stderr)
            return 2
        db.commit()
    print(f"ORG_ADMIN granted ({'new user' if meta['created_user'] else 'existing user'}).", file=sys.stderr)
    if temp:
        print("Temporary password (shown once; must be changed at first sign-in):", file=sys.stderr)
        print(temp)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Send a test email through the configured EMAIL_PROVIDER."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.db.session import SessionLocal
from app.services.email.service import queue_email, validate_email_config_at_startup
from app.services.email.types import OutboundEmail
from app.core.config import get_settings


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("recipient", help="Destination email address")
    args = parser.parse_args()
    settings = get_settings()
    validate_email_config_at_startup(settings)
    db = SessionLocal()
    try:
        queue_email(
            db,
            OutboundEmail(
                to_email=args.recipient,
                to_name=args.recipient,
                subject="AQREM test email",
                html="<p>AQREM transactional email test.</p>",
                text="AQREM transactional email test.",
                email_type="test",
                tags=["test"],
            ),
        )
        db.commit()
    finally:
        db.close()
    print("Queued test email to", args.recipient)
    print("Check logs (console) or Brevo dashboard (brevo).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

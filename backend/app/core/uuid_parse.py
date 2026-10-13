from uuid import UUID

from fastapi import HTTPException, status


def parse_optional_uuid(value: str | None) -> UUID | None:
    """Return a UUID when *value* is a valid string; otherwise None (no exception)."""
    if value is None:
        return None
    stripped = value.strip()
    if not stripped or stripped.lower() in ("null", "undefined"):
        return None
    try:
        return UUID(stripped)
    except ValueError:
        return None


def parse_required_uuid(value: str, *, detail: str = "Invalid UUID") -> UUID:
    try:
        return UUID(value.strip())
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail) from exc

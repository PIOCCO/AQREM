from datetime import UTC, datetime, timedelta
from typing import Any, Collection

from jose import JWTError, jwt
import bcrypt

from app.core.config import get_settings
from app.core.jwt_audiences import AUD_EMPLOYEE, AUD_ORG_ADMIN, AUD_PLATFORM

ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


def create_access_token(subject: str, claims: dict[str, Any] | None = None, *, audience: str | None = None) -> str:
    settings = get_settings()
    expire = datetime.now(UTC) + timedelta(minutes=settings.access_token_expire_minutes)
    extra = dict(claims or {})
    resolved_audience = audience or extra.pop("aud", None)
    if not resolved_audience:
        if extra.get("platform_role"):
            resolved_audience = AUD_PLATFORM
        elif extra.get("role") in {"ORG_ADMIN", "org_admin"}:
            resolved_audience = AUD_ORG_ADMIN
        else:
            resolved_audience = AUD_EMPLOYEE
    extra.pop("iss", None)
    extra.pop("sub", None)
    extra.pop("exp", None)
    extra.pop("aud", None)
    payload = {
        "sub": subject,
        "exp": expire,
        "iss": settings.jwt_issuer,
        "aud": resolved_audience,
        **extra,
    }
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def decode_access_token(token: str, *, audiences: str | Collection[str]) -> dict[str, Any]:
    settings = get_settings()
    aud_list = [audiences] if isinstance(audiences, str) else list(audiences)
    last_exc: JWTError | None = None
    for aud in aud_list:
        try:
            return jwt.decode(
                token,
                settings.secret_key,
                algorithms=[ALGORITHM],
                issuer=settings.jwt_issuer,
                audience=aud,
                options={"verify_aud": True, "verify_iss": True, "verify_exp": True},
            )
        except JWTError as exc:
            last_exc = exc
    raise ValueError("Invalid token") from last_exc

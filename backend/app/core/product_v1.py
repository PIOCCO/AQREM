from fastapi import HTTPException, status

from app.core.config import get_settings


def assert_chat_sharing_enabled() -> None:
    if get_settings().product_v1:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Conversation sharing is not available in this product version.",
        )

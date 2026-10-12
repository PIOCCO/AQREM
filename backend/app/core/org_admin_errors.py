from fastapi import HTTPException


def org_admin_error(
    *,
    code: str,
    message: str,
    field: str | None = None,
    status_code: int = 400,
) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={"code": code, "message": message, "field": field},
    )

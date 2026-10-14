import json
from pathlib import Path

from fastapi import APIRouter
from pydantic import BaseModel

from app.core.config import get_settings

router = APIRouter()

# Bump when platform delete routes or behavior change (for dev verification).
API_CAPABILITIES_REVISION = "2026-03-org-soft-delete-v1"


class ApiCapabilities(BaseModel):
    revision: str
    organization_soft_delete: bool = True
    organization_delete_routes: list[str] = [
        "POST /api/v1/admin/organizations/{organization_id}/delete",
        "POST /api/v1/admin/organizations/{organization_id}/schedule-deletion",
        "PATCH /api/v1/admin/organizations/{organization_id} (body: confirmName)",
        "DELETE /api/v1/admin/organizations/{organization_id} (body: confirmName)",
    ]


@router.get("/api-capabilities", response_model=ApiCapabilities)
def api_capabilities() -> ApiCapabilities:
    """Unauthenticated feature probe — use to confirm :8000 runs a build with org soft-delete."""
    return ApiCapabilities(revision=API_CAPABILITIES_REVISION)


class FrontendBuildInfo(BaseModel):
    build_id: str
    built_at: str
    auth_surface: str = "AuthPageShell"


def _dist_dir() -> Path:
    settings = get_settings()
    if settings.frontend_dist_path:
        return Path(settings.frontend_dist_path).expanduser().resolve()
    return Path(__file__).resolve().parents[4] / "frontend" / "dist"


@router.get("/frontend-build", response_model=FrontendBuildInfo)
def frontend_build() -> FrontendBuildInfo:
    info_path = _dist_dir() / "build-info.json"
    if info_path.is_file():
        data = json.loads(info_path.read_text(encoding="utf-8"))
        return FrontendBuildInfo(
            build_id=str(data.get("build_id", "unknown")),
            built_at=str(data.get("built_at", "")),
            auth_surface=str(data.get("auth_surface", "AuthPageShell")),
        )
    return FrontendBuildInfo(build_id="missing", built_at="", auth_surface="AuthPageShell")

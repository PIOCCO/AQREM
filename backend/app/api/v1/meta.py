import json
from pathlib import Path

from fastapi import APIRouter
from pydantic import BaseModel

from app.core.config import get_settings

router = APIRouter()


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

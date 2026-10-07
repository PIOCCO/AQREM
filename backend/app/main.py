import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from sqlalchemy import text

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.rate_limit import limiter
from app.core.security_middleware import SecurityHeadersMiddleware
from app.db.base import Base
from app.db.schema_patches import apply_schema_patches
from app.db.session import engine
import app.models  # noqa: F401


@asynccontextmanager
async def lifespan(_: FastAPI):
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        Base.metadata.create_all(bind=conn)
        apply_schema_patches(conn)
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="AQREM API", version="0.1.0", lifespan=lifespan)
    app.state.limiter = limiter
    if settings.rate_limit_enabled:
        app.add_middleware(SlowAPIMiddleware)

    @app.exception_handler(RateLimitExceeded)
    async def rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
        return JSONResponse(status_code=429, content={"message": "Too many requests. Please retry later."})

    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Organization-Id"],
    )
    app.include_router(api_router)

    @app.exception_handler(HTTPException)
    async def http_exception_handler(_: Request, exc: HTTPException) -> JSONResponse:
        detail = exc.detail
        if isinstance(detail, str):
            message = detail
        elif isinstance(detail, dict):
            message = detail.get("message", "Request could not be completed.")
        else:
            message = "Request could not be completed."
        return JSONResponse(
            status_code=exc.status_code,
            content={"message": message, "detail": detail},
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(_: Request, exc: Exception) -> JSONResponse:
        if settings.app_env == "development":
            message = str(exc)
        else:
            message = "Something went wrong. Please try again."
        return JSONResponse(status_code=500, content={"message": message})

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    if settings.serve_frontend or os.environ.get("SERVE_FRONTEND", "").strip() in {
        "1",
        "true",
        "yes",
    }:
        _mount_frontend_app(app, settings)

    return app


def _resolve_frontend_dist(settings) -> Path:
    if settings.frontend_dist_path:
        return Path(settings.frontend_dist_path).expanduser().resolve()
    # backend/app/main.py -> repo root -> frontend/dist
    return Path(__file__).resolve().parents[2] / "frontend" / "dist"


def _mount_frontend_app(app: FastAPI, settings) -> None:
    dist = _resolve_frontend_dist(settings)
    index_html = dist / "index.html"
    assets_dir = dist / "assets"
    if not index_html.is_file():
        raise RuntimeError(
            f"SERVE_FRONTEND is enabled but {index_html} is missing. "
            "Run: cd frontend && npm install && npm run build"
        )
    if assets_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="frontend-assets")

    @app.get("/")
    def frontend_index() -> FileResponse:
        return FileResponse(index_html)

    @app.get("/{full_path:path}")
    def frontend_spa(full_path: str) -> FileResponse:
        if full_path.startswith("api/") or full_path in {"docs", "openapi.json", "redoc"}:
            raise HTTPException(status_code=404, detail="Not found")
        candidate = dist / full_path
        if candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(index_html)


app = create_app()

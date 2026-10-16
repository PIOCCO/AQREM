import asyncio
import contextlib
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from sqlalchemy import text

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.container_config import validate_container_startup
from app.core.gateway_config import inspect_gateway
from app.core.llm_config import inspect_azure_openai, llm_provider_summary
from app.services.llm.errors import ModelServiceError
from app.core.rate_limit import limiter
from app.core.security_middleware import SecurityHeadersMiddleware
from app.db.control_base import ControlBase
from app.db.schema_patches import apply_schema_patches
from app.db.session import engine
from app.db.tenant_base import TenantBase
import app.models  # noqa: F401


logger = logging.getLogger("aqrem")


def _attach_info_logger(name: str) -> None:
    """Show provider and retrieval lines in the API process logs (redacted; JSON when LOG_FORMAT=json)."""
    from app.core.logging_setup import RedactionFilter, configure_logging

    configure_logging(get_settings().log_format)
    log = logging.getLogger(name)
    log.setLevel(logging.INFO)
    if get_settings().log_format.lower() == "json":
        return  # root JSON handler receives propagated records
    if not any(isinstance(handler, logging.StreamHandler) for handler in log.handlers):
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(levelname)s %(name)s %(message)s"))
        handler.addFilter(RedactionFilter())
        log.addHandler(handler)


@asynccontextmanager
async def lifespan(_: FastAPI):
    for name in ("aqrem", "aqrem.providers", "aqrem.rag"):
        _attach_info_logger(name)
    settings = get_settings()
    validate_container_startup(os.environ.get("CONTAINER_ROLE", ""), settings)
    from app.core.llm_config import log_active_providers, validate_llm_startup

    # Fail fast (names the missing variable, never a secret value).
    validate_llm_startup(settings)

    summary = llm_provider_summary(settings)
    log_active_providers(os.environ.get("CONTAINER_ROLE") or "api")
    logger.info(
        "LLM provider=%s configured=%s auth=%s chat_model=%s embedding_model=%s",
        summary.get("provider"),
        summary.get("configured"),
        summary.get("auth_mode"),
        summary.get("chat_model"),
        summary.get("embedding_model"),
    )
    if settings.llm_provider.lower().strip() == "azure":
        az = inspect_azure_openai(settings)
        if not az.configured:
            logger.error(
                "Azure OpenAI incomplete configuration; missing: %s",
                ", ".join(az.missing),
            )
    if settings.llm_provider.lower().strip() == "gateway":
        gw = inspect_gateway(settings)
        if not gw.configured:
            logger.error(
                "Model gateway incomplete configuration; missing: %s",
                ", ".join(gw.missing),
            )
    role = (os.environ.get("CONTAINER_ROLE") or "").strip().lower()
    if settings.app_env == "production" and role in {"api", "worker"}:
        from app.core.broker_health import assert_broker_available

        assert_broker_available()
    from app.db.migrate import LATEST_VERSION, migration_engine, pending, run_migrations

    if settings.run_migrations_on_startup:
        mig_engine = migration_engine() if (settings.migration_database_url or "").strip() else engine
        run_migrations(mig_engine, app_version=settings.app_version)
        if mig_engine is not engine:
            mig_engine.dispose()
    else:
        todo = pending(engine)
        if todo:
            raise RuntimeError(
                f"Database schema is behind (pending migrations {[m.version for m in todo]}, latest {LATEST_VERSION}). "
                "Run the migration job: python -m app.db.migrate"
            )
    from app.services.system.startup_report import log_startup_report

    log_startup_report(settings)
    from app.services.ingestion.vector_schema import check_vector_column_dimensions

    check_vector_column_dimensions(engine, settings)
    from app.db.session import SessionLocal
    from app.services.bootstrap import ensure_platform_admin

    with SessionLocal() as session:
        ensure_platform_admin(session)
        if settings.is_dedicated:
            from app.core.deployment import dedicated_setup_required, ensure_dedicated_organization

            from app.core.deployment import sync_license_to_org

            ensure_dedicated_organization(session, settings)
            session.flush()
            sync_license_to_org(session, settings)
            if dedicated_setup_required(session):
                logger.warning("Dedicated environment: first admin not created yet; open /setup (SETUP_TOKEN required)")
        from app.services.setup_checklist import backfill_local_prod_managed_storage_validation

        if backfill_local_prod_managed_storage_validation(session):
            logger.info("Backfilled setup_validated_at for local-prod managed tenant storage configs")
        session.commit()

    from app.api.v1.meta import API_CAPABILITIES_REVISION
    from app.services.email.service import validate_email_config_at_startup

    logger.info(
        "API capabilities revision=%s (org soft-delete via POST /api/v1/admin/organizations/{id}/delete)",
        API_CAPABILITIES_REVISION,
    )
    validate_email_config_at_startup(settings)

    async def _org_purge_worker() -> None:
        while True:
            await asyncio.sleep(3600)
            try:
                with SessionLocal() as session:
                    from app.services.org_lifecycle import run_scheduled_org_purges

                    run_scheduled_org_purges(session)
                    session.commit()
            except Exception:
                logger.exception("Scheduled organization purge failed")

    async def _audit_retention_worker() -> None:
        while True:
            await asyncio.sleep(3600)
            if settings.audit_retention_days <= 0:
                continue
            try:
                from app.services.audit.org_cleanup import run_audit_retention_all_orgs

                run_audit_retention_all_orgs(settings.audit_retention_days)
            except Exception:
                logger.exception("Scheduled audit retention failed")

    purge_task = asyncio.create_task(_org_purge_worker())
    audit_retention_task = asyncio.create_task(_audit_retention_worker())
    try:
        yield
    finally:
        purge_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await purge_task


def create_app() -> FastAPI:
    settings = get_settings()
    docs_url = None if settings.app_env == "production" else "/docs"
    redoc_url = None if settings.app_env == "production" else "/redoc"
    openapi_url = None if settings.app_env == "production" else "/openapi.json"
    app = FastAPI(
        title="AQREM API",
        version="0.1.0",
        lifespan=lifespan,
        docs_url=docs_url,
        redoc_url=redoc_url,
        openapi_url=openapi_url,
    )
    app.state.limiter = limiter
    if settings.rate_limit_enabled:
        app.add_middleware(SlowAPIMiddleware)

    @app.exception_handler(RateLimitExceeded)
    async def rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
        return JSONResponse(status_code=429, content={"message": "Too many requests. Please retry later."})

    app.add_middleware(SecurityHeadersMiddleware)
    cors_origins = settings.cors_origins_list
    if settings.app_env == "production" and not cors_origins:
        logger.warning(
            "CORS is not configured (set CORS_ALLOWED_ORIGINS and/or PUBLIC_BASE_URL). "
            "Browser clients on a different host/port will fail preflight with 400 and show a CORS error."
        )
    else:
        logger.info("CORS allow_origins=%s app_env=%s", cors_origins, settings.app_env)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=[
            "Authorization",
            "Content-Type",
            "X-Organization-Id",
            "X-Requested-With",
        ],
    )
    app.include_router(api_router)

    @app.middleware("http")
    async def dedicated_platform_gate(request: Request, call_next):
        from app.core.deployment import platform_route_allowed

        if not platform_route_allowed(request.url.path, request.method, settings):
            return JSONResponse(
                status_code=404,
                content={"message": "Not available in a dedicated environment.", "code": "DEDICATED_MODE"},
            )
        return await call_next(request)

    @app.middleware("http")
    async def admin_api_no_store(request: Request, call_next):
        response = await call_next(request)
        if request.url.path.startswith("/api/v1/admin"):
            response.headers["Cache-Control"] = "no-store"
            response.headers["Pragma"] = "no-cache"
        return response

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
        parts: list[str] = []
        for err in exc.errors()[:5]:
            loc = ".".join(str(x) for x in err.get("loc", []) if x != "body")
            msg = err.get("msg", "Invalid value")
            parts.append(f"{loc}: {msg}" if loc else str(msg))
        message = "; ".join(parts) if parts else "Request validation failed"
        return JSONResponse(status_code=422, content={"message": message, "detail": exc.errors()})

    @app.exception_handler(ModelServiceError)
    async def model_service_error_handler(_: Request, exc: ModelServiceError) -> JSONResponse:
        status_code = exc.status_code or 503
        return JSONResponse(
            status_code=status_code,
            content={
                "message": exc.user_message,
                "code": exc.code,
                "retryable": exc.retryable,
            },
        )

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
    def health() -> dict[str, object]:
        """Always 200 while the process serves requests; body reports each dependency."""
        from app.services.system.health import dependency_report

        try:
            return dependency_report(settings)
        except Exception as exc:  # never fail the liveness probe because a check crashed
            return {"status": "degraded", "error": type(exc).__name__}

    @app.get("/health/live")
    def health_live() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/health/ready")
    def health_ready() -> dict[str, object]:
        db_ok = False
        db_error: str | None = None
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            db_ok = True
        except Exception as exc:
            db_error = type(exc).__name__

        llm = llm_provider_summary(settings)
        provider = str(llm.get("provider") or "")
        llm_ready = provider not in {"azure", "gateway"} or bool(llm.get("configured"))

        status = "ok" if db_ok and llm_ready else "degraded"
        payload: dict[str, object] = {
            "status": status,
            "database": {"ready": db_ok, "error": db_error},
            "llm": llm,
        }
        if status != "ok":
            return JSONResponse(status_code=503, content=payload)
        return payload

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

    def _spa_index_response() -> FileResponse:
        return FileResponse(
            index_html,
            headers={
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
            },
        )

    @app.get("/")
    def frontend_index() -> FileResponse:
        return _spa_index_response()

    @app.get("/{full_path:path}")
    def frontend_spa(full_path: str) -> FileResponse:
        if full_path.startswith("api/") or full_path in {"docs", "openapi.json", "redoc"}:
            raise HTTPException(status_code=404, detail="Not found")
        candidate = dist / full_path
        if candidate.is_file():
            headers = None
            if full_path == "index.html" or not full_path.startswith("assets/"):
                headers = {"Cache-Control": "no-cache, no-store, must-revalidate", "Pragma": "no-cache"}
            return FileResponse(candidate, headers=headers)
        return _spa_index_response()


app = create_app()

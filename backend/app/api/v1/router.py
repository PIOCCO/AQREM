from fastapi import APIRouter

from app.api.v1 import auth, dashboard, evidence, organizations, projects, retrieval, sources

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(organizations.router, prefix="/organizations", tags=["organizations"])
api_router.include_router(projects.router, prefix="/projects", tags=["projects"])
api_router.include_router(sources.router, prefix="/sources", tags=["sources"])
api_router.include_router(evidence.router, prefix="/evidence", tags=["evidence"])
api_router.include_router(retrieval.router, prefix="/retrieval", tags=["retrieval"])
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["dashboard"])

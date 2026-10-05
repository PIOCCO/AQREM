from fastapi import APIRouter

from app.api.v1 import (
    answer_library,
    audit,
    auth,
    stale_answers,
    dashboard,
    evidence,
    organizations,
    projects,
    questionnaires,
    retrieval,
    review_queue,
    sources,
)

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(organizations.router, prefix="/organizations", tags=["organizations"])
api_router.include_router(projects.router, prefix="/projects", tags=["projects"])
api_router.include_router(sources.router, prefix="/sources", tags=["sources"])
api_router.include_router(evidence.router, prefix="/evidence", tags=["evidence"])
api_router.include_router(retrieval.router, prefix="/retrieval", tags=["retrieval"])
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["dashboard"])
api_router.include_router(questionnaires.router, prefix="/questionnaires", tags=["questionnaires"])
api_router.include_router(answer_library.router, prefix="/answer-library", tags=["answer-library"])
api_router.include_router(stale_answers.router, prefix="/stale-answers", tags=["stale-answers"])
api_router.include_router(review_queue.router, prefix="/review-queue", tags=["review-queue"])
api_router.include_router(audit.router, prefix="/audit", tags=["audit"])

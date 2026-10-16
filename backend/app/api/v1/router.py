from fastapi import APIRouter

from app.api.v1 import (
    admin,
    public_join,
    master,
    org_access,
    org_admin,
    public_chat,
    answer_library,
    audit,
    auth,
    chat,
    stale_answers,
    dashboard,
    evidence,
    organizations,
    projects,
    questionnaires,
    retrieval,
    review_queue,
    sources,
    meta,
)

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(public_join.router, prefix="/public/join", tags=["public-join"])
from app.api.v1 import setup as setup_api  # noqa: E402
from app.api.v1 import system as system_api  # noqa: E402

api_router.include_router(setup_api.router, prefix="/setup", tags=["setup"])
api_router.include_router(system_api.router, tags=["system"])
api_router.include_router(system_api.platform_router, prefix="/admin/system", tags=["system"])
api_router.include_router(meta.router, prefix="/meta", tags=["meta"])
api_router.include_router(admin.router, prefix="/admin", tags=["admin"])
api_router.include_router(master.router, prefix="/master", tags=["master"])
api_router.include_router(org_admin.router, prefix="/org-admin", tags=["org-admin"])
api_router.include_router(org_access.router, prefix="/org-admin/access", tags=["org-access"])
api_router.include_router(organizations.router, prefix="/organizations", tags=["organizations"])
api_router.include_router(projects.router, prefix="/projects", tags=["projects"])
api_router.include_router(sources.router, prefix="/sources", tags=["sources"])
api_router.include_router(evidence.router, prefix="/evidence", tags=["evidence"])
api_router.include_router(retrieval.router, prefix="/retrieval", tags=["retrieval"])
api_router.include_router(chat.router, prefix="/chat", tags=["chat"])
api_router.include_router(public_chat.router, prefix="/public/chat", tags=["public-chat"])
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["dashboard"])
api_router.include_router(questionnaires.router, prefix="/questionnaires", tags=["questionnaires"])
api_router.include_router(answer_library.router, prefix="/answer-library", tags=["answer-library"])
api_router.include_router(stale_answers.router, prefix="/stale-answers", tags=["stale-answers"])
api_router.include_router(review_queue.router, prefix="/review-queue", tags=["review-queue"])
api_router.include_router(audit.router, prefix="/audit", tags=["audit"])

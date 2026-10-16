"""CHECK 2 - systematic per-endpoint isolation audit.

Every route of the FastAPI app must have an entry in ROUTE_POLICY (test fails for new routes).
For each tenant/platform route, with two seeded organizations, the route is called as:
  * unauthenticated,
  * org A employee and org A org-admin,
  * org A tokens with a spoofed X-Organization-Id of org B,
passing (a) identifiers that belong to org B and (b) random identifiers. Assertions:
  * never 2xx for org-B identifiers / spoofed org; never org-B data in any response,
  * no existence oracle: status + normalized body for "exists in other org" == "does not exist".
"""

from __future__ import annotations

import asyncio
import json
import re
import secrets
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.routing import APIRoute

from app.core.jwt_audiences import AUD_EMPLOYEE, AUD_ORG_ADMIN
from app.core.roles import Role
from app.core.security import create_access_token, hash_password
from app.models.access_group import AccessGroup, AccessGroupMembership
from app.models.answer_library import AnswerLibraryEntry
from app.models.chat_share import ChatConversationShare
from app.models.chat_share_index import ChatShareTokenIndex
from app.models.client_admin import ClientDocument
from app.models.employee_join import EmployeeJoinLink, EmployeeJoinPending
from app.models.enums import EvidenceScope, SourceType, SyncJobStatus
from app.models.evidence import EvidenceItem
from app.models.invitation import UserInvitation
from app.models.organization import Organization, OrganizationMembership, User
from app.models.project import Project
from app.models.questionnaire import Answer, Question, Questionnaire
from app.models.source import Source, SourceSyncJob
from app.models.staleness import AnswerStalenessEvent
from app.services.ingestion.indexer import FilePayload, index_files
from app.services.storage.path_utils import org_blob_path
from tests.backend.helpers_acl import mark_source_visible_to_all_staff

MARK_B = "BRAVOISOLATIONMARK"

PUBLIC = "public"
PLATFORM = "platform"
TENANT = "tenant"

# placeholder -> seeded object key
PARAM_KIND = {
    "organization_id": "org", "document_id": "doc", "source_id": "source", "job_id": "job",
    "project_id": "project", "questionnaire_id": "questionnaire", "question_id": "question",
    "answer_id": "answer", "entry_id": "library", "evidence_id": "evidence", "group_id": "group",
    "user_id": "emp_user", "membership_id": "emp_membership", "pending_id": "pending", "link_id": "link",
    "invitation_id": "invitation", "record_id": "invitation", "token": "share_token",
}

_J = "{}"
# Route policy: "METHOD path" -> (kind, justification | JSON body | GET query params | "MULTIPART:<field>")
ROUTE_POLICY: dict[str, tuple[str, object]] = {
    # ---- public / global (allowlisted with justification) ----
    "GET /health": (PUBLIC, "liveness + dependency status; no tenant data"),
    "GET /health/live": (PUBLIC, "liveness probe"),
    "GET /health/ready": (PUBLIC, "readiness probe"),
    "GET /api/v1/version": (PUBLIC, "build version for fleet view; no tenant data"),
    "GET /api/v1/meta/version": (PUBLIC, "build/runtime metadata; no tenant data"),
    "GET /api/v1/meta/api-capabilities": (PUBLIC, "static capability flags"),
    "GET /api/v1/meta/frontend-build": (PUBLIC, "frontend build id"),
    "GET /api/v1/setup/status": (PUBLIC, "dedicated first-run only; 404 in shared mode, after setup, or outside SETUP_ALLOWED_CIDRS"),
    "POST /api/v1/setup/first-admin": (PUBLIC, "dedicated only, one-time expiring token, rate-limited; 404 in shared/after setup/outside CIDRs"),
    "POST /api/v1/auth/login": (PUBLIC, "credential check; identical 401 for unknown email / wrong password"),
    "POST /api/v1/auth/forgot-password": (PUBLIC, "always 200 regardless of email existence"),
    "POST /api/v1/auth/reset-password": (PUBLIC, "secret reset token is the authorization"),
    "POST /api/v1/auth/accept-invitation": (PUBLIC, "secret invitation token is the authorization"),
    "POST /api/v1/auth/accept-invitation/preview": (PUBLIC, "secret invitation token is the authorization"),
    "POST /api/v1/auth/accept-invitation/send-verification": (PUBLIC, "secret invitation token"),
    "POST /api/v1/public/join/preview": (PUBLIC, "secret employee-join token is the authorization"),
    "POST /api/v1/public/join/start": (PUBLIC, "secret employee-join token"),
    "POST /api/v1/public/join/verify-email": (PUBLIC, "secret employee-join token + emailed code"),
    "POST /api/v1/public/join/complete": (PUBLIC, "secret employee-join token + emailed code"),
    "GET /api/v1/public/chat/shares/{token}": (PUBLIC, "unguessable share token (256-bit) is the capability"),
    "POST /api/v1/master/telemetry": (PUBLIC, "machine-to-machine, telemetry key auth; no tenant read"),
    # ---- authenticated routes: TENANT (org-scoped) or PLATFORM (super-admin console). Payload strings
    # '@kind' are filled with org-B values (and random values for the existence comparison) ----
    "GET /api/v1/admin/context": (PLATFORM, None),
    "GET /api/v1/admin/organizations": (PLATFORM, None),
    "POST /api/v1/admin/organizations": (PLATFORM, None),
    "DELETE /api/v1/admin/organizations/{organization_id}": (PLATFORM, None),
    "GET /api/v1/admin/organizations/{organization_id}": (PLATFORM, None),
    "PATCH /api/v1/admin/organizations/{organization_id}": (PLATFORM, None),
    "GET /api/v1/admin/organizations/{organization_id}/audit": (PLATFORM, None),
    "POST /api/v1/admin/organizations/{organization_id}/delete": (PLATFORM, None),
    "GET /api/v1/admin/organizations/{organization_id}/directory": (PLATFORM, None),
    "GET /api/v1/admin/organizations/{organization_id}/employee-link": (PLATFORM, None),
    "POST /api/v1/admin/organizations/{organization_id}/employee-link": (PLATFORM, None),
    "DELETE /api/v1/admin/organizations/{organization_id}/employee-link/{link_id}": (PLATFORM, None),
    "POST /api/v1/admin/organizations/{organization_id}/employee-link/{link_id}/delete": (PLATFORM, None),
    "POST /api/v1/admin/organizations/{organization_id}/employee-link/{link_id}/disable": (PLATFORM, None),
    "GET /api/v1/admin/organizations/{organization_id}/employee-link/{link_id}/link": (PLATFORM, None),
    "POST /api/v1/admin/organizations/{organization_id}/employee-link/{link_id}/pause": (PLATFORM, None),
    "POST /api/v1/admin/organizations/{organization_id}/employee-link/{link_id}/resume": (PLATFORM, None),
    "POST /api/v1/admin/organizations/{organization_id}/employee-link/{link_id}/rotate": (PLATFORM, None),
    "POST /api/v1/admin/organizations/{organization_id}/invitation-history/{record_id}/delete": (PLATFORM, None),
    "GET /api/v1/admin/organizations/{organization_id}/invitations": (PLATFORM, None),
    "POST /api/v1/admin/organizations/{organization_id}/invitations/admin": (PLATFORM, None),
    "DELETE /api/v1/admin/organizations/{organization_id}/invitations/admin/{invitation_id}": (PLATFORM, None),
    "POST /api/v1/admin/organizations/{organization_id}/invitations/admin/{invitation_id}/delete": (PLATFORM, None),
    "GET /api/v1/admin/organizations/{organization_id}/invitations/admin/{invitation_id}/link": (PLATFORM, None),
    "POST /api/v1/admin/organizations/{organization_id}/invitations/admin/{invitation_id}/send-email": (PLATFORM, None),
    "GET /api/v1/admin/organizations/{organization_id}/invitations/history": (PLATFORM, None),
    "GET /api/v1/admin/organizations/{organization_id}/invitations/setup": (PLATFORM, None),
    "POST /api/v1/admin/organizations/{organization_id}/invitations/{invitation_id}/resend": (PLATFORM, None),
    "POST /api/v1/admin/organizations/{organization_id}/invitations/{invitation_id}/revoke": (PLATFORM, None),
    "GET /api/v1/admin/organizations/{organization_id}/members": (PLATFORM, None),
    "PATCH /api/v1/admin/organizations/{organization_id}/members/{membership_id}": (PLATFORM, None),
    "POST /api/v1/admin/organizations/{organization_id}/members/{membership_id}/deactivate": (PLATFORM, None),
    "GET /api/v1/admin/organizations/{organization_id}/model-token": (PLATFORM, None),
    "PUT /api/v1/admin/organizations/{organization_id}/model-token": (PLATFORM, None),
    "POST /api/v1/admin/organizations/{organization_id}/model-token/test": (PLATFORM, None),
    "POST /api/v1/admin/organizations/{organization_id}/purge-now": (PLATFORM, None),
    "POST /api/v1/admin/organizations/{organization_id}/replace-org-admin": (PLATFORM, None),
    "POST /api/v1/admin/organizations/{organization_id}/restore": (PLATFORM, None),
    "POST /api/v1/admin/organizations/{organization_id}/schedule-deletion": (PLATFORM, None),
    "POST /api/v1/admin/organizations/{organization_id}/users": (PLATFORM, None),
    "GET /api/v1/admin/permissions/matrix": (PLATFORM, None),
    "GET /api/v1/admin/platform-staff": (PLATFORM, None),
    "POST /api/v1/admin/platform-staff/invite": (PLATFORM, None),
    "DELETE /api/v1/admin/platform-staff/{user_id}": (PLATFORM, None),
    "PATCH /api/v1/admin/platform-staff/{user_id}": (PLATFORM, None),
    "GET /api/v1/admin/roles/audit": (PLATFORM, None),
    "GET /api/v1/admin/system/database-check": (PLATFORM, None),
    "GET /api/v1/admin/system/diagnostics": (PLATFORM, None),
    "GET /api/v1/admin/system/fleet": (PLATFORM, None),
    "GET /api/v1/admin/system/health": (PLATFORM, None),
    "GET /api/v1/answer-library": (TENANT, {"project_id": "@project"}),
    "POST /api/v1/answer-library/search": (TENANT, None),
    "GET /api/v1/answer-library/{entry_id}": (TENANT, None),
    "GET /api/v1/answer-library/{entry_id}/validation": (TENANT, None),
    "GET /api/v1/audit": (TENANT, {"actor_user_id": "@emp_user"}),
    "GET /api/v1/audit/actors": (TENANT, None),
    "GET /api/v1/audit/export": (TENANT, {"actor_user_id": "@emp_user"}),
    "POST /api/v1/auth/change-password": (TENANT, {"current_password": "x", "new_password": "yyyyyyyyyyyy"}),
    "GET /api/v1/auth/me": (TENANT, None),
    "GET /api/v1/auth/me/tenant": (TENANT, None),
    "POST /api/v1/chat/ask": (TENANT, {"query": "retention policy", "project_id": "@project"}),
    "POST /api/v1/chat/ask/stream": (TENANT, {"query": "retention policy", "project_id": "@project"}),
    "POST /api/v1/chat/shares": (TENANT, {"client_conversation_id": "conv-1", "title": "t", "messages": []}),
    "DELETE /api/v1/chat/shares/{token}": (TENANT, None),
    "GET /api/v1/chat/shares/{token}": (TENANT, None),
    "GET /api/v1/dashboard/metrics": (TENANT, {"project_id": "@project"}),
    "GET /api/v1/dashboard/overview": (TENANT, {"project_id": "@project"}),
    "GET /api/v1/evidence": (TENANT, {"project_id": "@project", "source_id": "@source"}),
    "GET /api/v1/evidence/{evidence_id}": (TENANT, None),
    "GET /api/v1/master/environments": (PLATFORM, None),
    "GET /api/v1/master/organizations/{organization_id}/environment": (PLATFORM, None),
    "POST /api/v1/master/organizations/{organization_id}/provision": (PLATFORM, None),
    "POST /api/v1/master/provisioning-jobs/{job_id}/retry": (PLATFORM, None),
    "GET /api/v1/org-admin/access/documents/needs-review/count": (TENANT, None),
    "POST /api/v1/org-admin/access/documents/visibility/bulk": (TENANT, {"visibility_mode": "all_staff", "document_ids": ["@doc"]}),
    "PATCH /api/v1/org-admin/access/documents/{document_id}/visibility": (TENANT, {"visibility_mode": "all_staff"}),
    "GET /api/v1/org-admin/access/groups": (TENANT, None),
    "POST /api/v1/org-admin/access/groups": (TENANT, {"name": "grp"}),
    "POST /api/v1/org-admin/access/groups/{group_id}/members": (TENANT, {"user_ids": ["@emp_user"]}),
    "DELETE /api/v1/org-admin/access/groups/{group_id}/members/{user_id}": (TENANT, None),
    "POST /api/v1/org-admin/access/preview-as": (TENANT, {"user_id": "@emp_user", "query": "retention policy"}),
    "GET /api/v1/org-admin/ai/status": (TENANT, None),
    "POST /api/v1/org-admin/ai/test-connection": (TENANT, None),
    "GET /api/v1/org-admin/audit": (TENANT, None),
    "DELETE /api/v1/org-admin/audit-logs": (TENANT, None),
    "GET /api/v1/org-admin/audit/export": (TENANT, None),
    "GET /api/v1/org-admin/chat-sharing": (TENANT, None),
    "PUT /api/v1/org-admin/chat-sharing": (TENANT, None),
    "GET /api/v1/org-admin/chat-guardrails": (TENANT, None),
    "PUT /api/v1/org-admin/chat-guardrails": (TENANT, {"strictness": "strict"}),
    "GET /api/v1/org-admin/console-enter": (TENANT, None),
    "GET /api/v1/org-admin/data-storage": (TENANT, None),
    "PUT /api/v1/org-admin/data-storage": (TENANT, None),
    "POST /api/v1/org-admin/data-storage/preflight": (TENANT, None),
    "POST /api/v1/org-admin/data-storage/refresh-health": (TENANT, None),
    "GET /api/v1/org-admin/documents": (TENANT, None),
    "POST /api/v1/org-admin/documents/reindex-all": (TENANT, None),
    "POST /api/v1/org-admin/documents/upload": (TENANT, "MULTIPART:files"),
    "DELETE /api/v1/org-admin/documents/{document_id}": (TENANT, None),
    "POST /api/v1/org-admin/documents/{document_id}/retry": (TENANT, None),
    "GET /api/v1/org-admin/employee-join/pending": (TENANT, None),
    "POST /api/v1/org-admin/employee-join/pending/{pending_id}/approve": (TENANT, None),
    "POST /api/v1/org-admin/employee-join/pending/{pending_id}/reject": (TENANT, None),
    "POST /api/v1/org-admin/employee-link/copied": (TENANT, None),
    "GET /api/v1/org-admin/members": (TENANT, None),
    "POST /api/v1/org-admin/members/invite": (TENANT, {"email": "@emp_email", "full_name": "X", "role": "EDITOR"}),
    "POST /api/v1/org-admin/members/{membership_id}/deactivate": (TENANT, None),
    "POST /api/v1/org-admin/members/{membership_id}/password-reset": (TENANT, None),
    "GET /api/v1/org-admin/model-token": (TENANT, None),
    "PUT /api/v1/org-admin/model-token": (TENANT, None),
    "POST /api/v1/org-admin/model-token/rotate": (TENANT, None),
    "POST /api/v1/org-admin/model-token/test": (TENANT, None),
    "GET /api/v1/org-admin/overview": (TENANT, None),
    "GET /api/v1/org-admin/setup": (TENANT, None),
    "GET /api/v1/org-admin/system/database-check": (TENANT, None),
    "GET /api/v1/org-admin/system/diagnostics": (TENANT, None),
    "GET /api/v1/org-admin/system/health": (TENANT, None),
    "GET /api/v1/org-admin/telemetry-schema": (TENANT, None),
    "GET /api/v1/org-admin/usage": (TENANT, None),
    "GET /api/v1/organizations": (TENANT, None),
    "GET /api/v1/projects": (TENANT, None),
    "POST /api/v1/projects": (TENANT, {"name": "New P"}),
    "GET /api/v1/projects/summaries": (TENANT, None),
    "GET /api/v1/projects/{project_id}": (TENANT, None),
    "GET /api/v1/questionnaires": (TENANT, {"project_id": "@project"}),
    "POST /api/v1/questionnaires": (TENANT, {"name": "New Q", "project_id": "@project"}),
    "POST /api/v1/questionnaires/answers/{answer_id}/approve": (TENANT, None),
    "POST /api/v1/questionnaires/answers/{answer_id}/edit": (TENANT, {"text": "edited"}),
    "POST /api/v1/questionnaires/answers/{answer_id}/reject": (TENANT, None),
    "GET /api/v1/questionnaires/questions/{question_id}": (TENANT, None),
    "POST /api/v1/questionnaires/questions/{question_id}/generate": (TENANT, None),
    "POST /api/v1/questionnaires/questions/{question_id}/regenerate": (TENANT, None),
    "GET /api/v1/questionnaires/{questionnaire_id}": (TENANT, None),
    "GET /api/v1/questionnaires/{questionnaire_id}/export/csv": (TENANT, None),
    "GET /api/v1/questionnaires/{questionnaire_id}/export/xlsx": (TENANT, None),
    "POST /api/v1/questionnaires/{questionnaire_id}/generate": (TENANT, None),
    "GET /api/v1/questionnaires/{questionnaire_id}/questions": (TENANT, None),
    "POST /api/v1/questionnaires/{questionnaire_id}/upload": (TENANT, "MULTIPART:file"),
    "POST /api/v1/retrieval/preview": (TENANT, {"query": "retention policy", "project_id": "@project", "source_id": "@source"}),
    "GET /api/v1/review-queue": (TENANT, {"project_id": "@project"}),
    "GET /api/v1/sources": (TENANT, {"project_id": "@project"}),
    "POST /api/v1/sources": (TENANT, {"name": "New S", "source_type": "file_upload", "project_id": "@project", "scope": "project"}),
    "POST /api/v1/sources/github/connect-repo": (TENANT, {"source_id": "@source", "repository_full_name": "o/r"}),
    "GET /api/v1/sources/jobs/{job_id}": (TENANT, None),
    "POST /api/v1/sources/{source_id}/files": (TENANT, "MULTIPART:files"),
    "GET /api/v1/sources/{source_id}/jobs": (TENANT, None),
    "POST /api/v1/sources/{source_id}/sync": (TENANT, None),
    "GET /api/v1/stale-answers": (TENANT, {"project_id": "@project"}),
    "GET /api/v1/stale-answers/{answer_id}": (TENANT, None),
    "POST /api/v1/stale-answers/{answer_id}/regenerate": (TENANT, None),
    "POST /api/v1/stale-answers/{answer_id}/revalidate": (TENANT, None),
}

_PLATFORM_PREFIXES = ("/api/v1/admin/", "/api/v1/master/")


def _route_key(method: str, path: str) -> str:
    return f"{method} {path}"


def _all_routes(app) -> list[tuple[str, str]]:
    out: set[tuple[str, str]] = set()

    def walk(routes):
        for r in routes:
            if isinstance(r, APIRoute):
                for m in r.methods:
                    out.add((m, r.path))
            elif type(r).__name__ == "_IncludedRouter":
                ctx = r.effective_route_contexts
                for x in (ctx() if callable(ctx) else ctx):
                    if type(x).__name__ == "_IncludedRouter":
                        walk([x])
                    else:
                        for m in x.methods or ():
                            out.add((m, x.path))
    walk(app.routes)
    return sorted((m, p) for m, p in out if m not in {"HEAD", "OPTIONS"})


def policy_for(method: str, path: str) -> tuple[str, object]:
    """Explicit entries only: a new route without an entry fails test_every_route_has_isolation_policy."""
    return ROUTE_POLICY[_route_key(method, path)]


def test_every_route_has_isolation_policy():
    from app.main import create_app

    routes = _all_routes(create_app())
    assert len(routes) >= 160
    missing = []
    for m, p in routes:
        try:
            kind, _ = policy_for(m, p)
        except KeyError:
            missing.append(f"{m} {p}")
            continue
        if kind == PLATFORM and not p.startswith(_PLATFORM_PREFIXES):
            missing.append(f"{m} {p} (platform policy outside platform prefixes)")
        for ph in re.findall(r"{(\w+)}", p):
            if kind != PUBLIC and ph not in PARAM_KIND:
                missing.append(f"{m} {p} (unknown path param {ph})")
    assert not missing, "Routes without an isolation-check entry:\n" + "\n".join(missing)
    stale = [k for k in ROUTE_POLICY if tuple(k.split(" ", 1)) not in set(routes)]
    assert not stale, f"ROUTE_POLICY entries for routes that no longer exist: {stale}"


# ---------------------------------------------------------------- seeding
async def _seed(db, name: str, marker: str) -> dict:
    org = Organization(name=f"{name} {marker}", slug=f"{name.lower()}-{uuid.uuid4().hex[:6]}", license_limit=20,
                       chat_shares_enabled=True)
    db.add(org)
    db.flush()
    mk = lambda r: User(email=f"{r}-{uuid.uuid4().hex[:6]}@{name.lower()}.example.com",  # noqa: E731
                        full_name=f"{name} {r} {marker}", hashed_password=hash_password("x"), is_active=True)
    admin, emp = mk("admin"), mk("emp")
    db.add_all([admin, emp])
    db.flush()
    m_admin = OrganizationMembership(organization_id=org.id, user_id=admin.id, role=Role.ORG_ADMIN.value)
    m_emp = OrganizationMembership(organization_id=org.id, user_id=emp.id, role=Role.EDITOR.value)
    db.add_all([m_admin, m_emp])
    project = Project(organization_id=org.id, name=f"{name} Project {marker}")
    db.add(project)
    db.flush()
    source = Source(organization_id=org.id, project_id=project.id, name=f"{name} docs {marker}",
                    source_type=SourceType.FILE_UPLOAD.value, scope=EvidenceScope.ORGANIZATION.value)
    mark_source_visible_to_all_staff(source)
    db.add(source)
    db.flush()
    job = SourceSyncJob(organization_id=org.id, source_id=source.id, status=SyncJobStatus.COMPLETED.value)
    db.add(job)
    db.flush()
    await index_files(db, source=source, job=job,
                      files=[FilePayload(relative_path="policy.txt", data=f"{marker} retention policy text".encode())])
    evidence = db.query(EvidenceItem).filter(EvidenceItem.organization_id == org.id).first()
    doc = ClientDocument(organization_id=org.id, source_id=source.id, file_name=f"{name}-{marker}.txt",
                         blob_path=org_blob_path(org.id, str(source.id), "policy.txt"), status="indexed",
                         visibility_mode="all_staff")
    group = AccessGroup(organization_id=org.id, name=f"{name} group {marker}", slug=f"g-{uuid.uuid4().hex[:6]}")
    qn = Questionnaire(organization_id=org.id, name=f"{name} questionnaire {marker}", project_id=project.id)
    db.add_all([doc, group, qn])
    db.flush()
    db.add(AccessGroupMembership(organization_id=org.id, group_id=group.id, user_id=emp.id))
    q = Question(organization_id=org.id, questionnaire_id=qn.id, external_id="Q1", text=f"{marker} question?",
                 normalized_text=f"{marker.lower()} question")
    db.add(q)
    db.flush()
    ans = Answer(organization_id=org.id, question_id=q.id, draft_text=f"{marker} answer", approved_text=f"{marker} answer", status="approved")
    db.add(ans)
    db.flush()
    lib = AnswerLibraryEntry(organization_id=org.id, source_answer_id=ans.id, question_text=f"{marker} q",
                             normalized_question=f"{marker.lower()} q", answer_text=f"{marker} lib answer")
    stale = AnswerStalenessEvent(organization_id=org.id, answer_id=ans.id, file_path="policy.txt",
                                 snapshot_content_hash="a", current_content_hash="b", reason="changed")
    link = EmployeeJoinLink(organization_id=org.id, token_hash=secrets.token_hex(32))
    db.add_all([lib, stale, link])
    db.flush()
    pending = EmployeeJoinPending(organization_id=org.id, link_id=link.id, email=f"p-{uuid.uuid4().hex[:6]}@x.example.com",
                                  full_name=f"Pending {marker}")
    inv = UserInvitation(organization_id=org.id, email=f"inv-{uuid.uuid4().hex[:6]}@x.example.com",
                         role=Role.EDITOR.value, token_hash=secrets.token_hex(32),
                         expires_at=datetime.now(UTC) + timedelta(days=3))
    tok = secrets.token_urlsafe(32)
    share = ChatConversationShare(share_token=tok, organization_id=org.id, created_by_user_id=emp.id,
                                  client_conversation_id="conv-1", title=f"{marker} chat",
                                  messages=[{"role": "user", "content": marker}],
                                  expires_at=datetime.now(UTC) + timedelta(days=3))
    db.add_all([pending, inv, share, ChatShareTokenIndex(share_token=tok, organization_id=org.id,
                                                        expires_at=datetime.now(UTC) + timedelta(days=3))])
    db.commit()
    return {
        "org": org.id, "doc": doc.id, "source": source.id, "job": job.id, "project": project.id,
        "questionnaire": qn.id, "question": q.id, "answer": ans.id, "library": lib.id, "evidence": evidence.id,
        "group": group.id, "emp_user": emp.id, "emp_membership": m_emp.id, "pending": pending.id,
        "link": link.id, "invitation": inv.id, "share_token": tok,
        "admin_tok": create_access_token(str(admin.id), {"organization_id": str(org.id), "role": Role.ORG_ADMIN.value,
                                                         "auth_version": 1}, audience=AUD_ORG_ADMIN),
        "emp_tok": create_access_token(str(emp.id), {"organization_id": str(org.id), "role": Role.EDITOR.value,
                                                     "auth_version": 1}, audience=AUD_EMPLOYEE),
        "emails": [admin.email, emp.email, pending.email, inv.email],
    }


@pytest.fixture()
def orgs(db_session, monkeypatch):
    from app.core.rate_limit import limiter

    monkeypatch.setattr(limiter, "enabled", False)
    loop = asyncio.new_event_loop()
    try:
        a = loop.run_until_complete(_seed(db_session, "Alpha", "ALPHAISOLATIONMARK"))
        b = loop.run_until_complete(_seed(db_session, "Bravo", MARK_B))
    finally:
        loop.close()
    return a, b


# ---------------------------------------------------------------- helpers
_UUID = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")


def _normalize(text: str, ids: list[str]) -> str:
    for i in ids:
        text = text.replace(i, "<ID>")
    text = _UUID.sub("<UUID>", text)
    text = re.sub(r'"(request_id|timestamp|trace_id)"\s*:\s*"[^"]*"', r'"\1":"<x>"', text)
    text = re.sub(r'"(\w*_ms|\w*latency\w*|\w*duration\w*)"\s*:\s*[\d.]+', r'"\1":0', text)
    text = re.sub(r"\d{4}-\d{2}-\d{2}T[\d:.]+(\+00:00|Z)?", "<TS>", text)
    text = re.sub(r"[A-Za-z0-9_-]{40,}", "<TOKEN>", text)
    return text


def _fill(path: str, objs: dict) -> tuple[str, list[str]]:
    used = []

    def rep(m):
        v = str(objs[PARAM_KIND[m.group(1)]])
        used.append(v)
        return v
    return re.sub(r"{(\w+)}", rep, path), used


def _random_objs(b: dict) -> dict:
    r = {k: (uuid.uuid4() if isinstance(v, uuid.UUID) else v) for k, v in b.items()}
    r["share_token"] = secrets.token_urlsafe(32)
    r["emails"] = [f"nobody-{uuid.uuid4().hex[:6]}@nowhere.example.com" for _ in b["emails"]]
    return r


def _fill_payload(payload, objs: dict, used: list[str]):
    if isinstance(payload, dict):
        return {k: _fill_payload(v, objs, used) for k, v in payload.items()}
    if isinstance(payload, list):
        return [_fill_payload(v, objs, used) for v in payload]
    if isinstance(payload, str) and payload.startswith("@"):
        v = objs["emails"][1] if payload == "@emp_email" else str(objs[payload[1:]])
        used.append(v)
        return v
    return payload


def _call(client, method, url, headers, payload):
    kw = {"headers": headers}
    if method == "GET":  # GET payload = query parameters (org-B ids vs random ids)
        return client.request(method, url, headers=headers, params=payload or None)
    if isinstance(payload, str) and payload.startswith("MULTIPART:"):
        field = payload.split(":", 1)[1]
        return client.request(method, url, headers=headers, data={"visibility_mode": "all_staff"},
                              files=[(field, ("probe.txt", b"probe content", "text/plain"))])
    if method in {"POST", "PUT", "PATCH", "DELETE"}:
        kw["content"] = json.dumps(payload if payload is not None else {})
        kw["headers"] = {**headers, "Content-Type": "application/json"}
    return client.request(method, url, **kw)


def _b_markers(b: dict) -> list[str]:
    vals = [MARK_B, str(b["org"]), b["share_token"], *b["emails"]]
    return [v for v in vals if v]


def _assert_no_b_data(resp, b, path_ids, ctx):
    body = resp.text
    for v in _b_markers(b):
        if v in path_ids:
            continue
        assert v not in body, f"{ctx}: org B value leaked ({v[:24]}...) status={resp.status_code} body={body[:300]}"


def _dump(ctx, resp):
    import os

    if os.environ.get("ISO_DUMP"):
        with open(os.environ["ISO_DUMP"], "a") as fh:
            fh.write(f"{resp.status_code}\t{ctx}\t{resp.text[:120]}\n")


ALL_ROUTES: list[tuple[str, str]] = []


def _collect():
    global ALL_ROUTES
    if not ALL_ROUTES:
        from app.main import create_app

        ALL_ROUTES = _all_routes(create_app())
    return ALL_ROUTES


def _non_public():
    return [(m, p) for m, p in _collect() if policy_for(m, p)[0] != PUBLIC]


@pytest.mark.parametrize("method,path", _non_public(), ids=lambda x: x)
def test_route_isolation(client, orgs, method, path):
    a, b = orgs
    kind, payload = policy_for(method, path)
    rand = _random_objs(b)
    url_b, ids_b = _fill(path, b)
    url_r, ids_r = _fill(path, rand)
    has_ids = bool(ids_b)  # path identifiers of org B -> must be refused
    body_ids_b: list[str] = []
    body_ids_r: list[str] = []
    payload_b = _fill_payload(payload, b, body_ids_b)
    payload_r = _fill_payload(payload, rand, body_ids_r)
    ids_b, ids_r = ids_b + body_ids_b, ids_r + body_ids_r

    # 1) unauthenticated: refused, identical for B-id vs random id
    rb = _call(client, method, url_b, {}, payload_b)
    rr = _call(client, method, url_r, {}, payload_r)
    assert rb.status_code in (401, 403), f"unauth {method} {path} -> {rb.status_code} {rb.text[:200]}"
    assert (rb.status_code, _normalize(rb.text, ids_b)) == (rr.status_code, _normalize(rr.text, ids_r))
    _assert_no_b_data(rb, b, ids_b, f"unauth {method} {path}")

    for who in ("emp_tok", "admin_tok"):
        H = {"Authorization": f"Bearer {a[who]}", "X-Organization-Id": str(a["org"])}
        ctx = f"{who} {method} {path}"
        # 2) org-A caller with org-B identifiers vs random identifiers
        rb = _call(client, method, url_b, H, payload_b)
        _dump(ctx, rb)
        _assert_no_b_data(rb, b, ids_b, ctx)
        if has_ids or body_ids_b:
            rr = _call(client, method, url_r, H, payload_r)
            if has_ids:
                assert not (200 <= rb.status_code < 300), f"{ctx}: org-B id accepted -> {rb.status_code} {rb.text[:300]}"
            assert rb.status_code == rr.status_code, f"{ctx}: existence oracle {rb.status_code} vs {rr.status_code}"
            assert _normalize(rb.text, ids_b) == _normalize(rr.text, ids_r), (
                f"{ctx}: existence oracle body\n B: {rb.text[:300]}\n R: {rr.text[:300]}")
        # 3) spoofed organization header -> refused, no B data
        HS = {"Authorization": f"Bearer {a[who]}", "X-Organization-Id": str(b["org"])}
        rs = _call(client, method, url_b, HS, payload_b)
        _assert_no_b_data(rs, b, ids_b, f"spoof {ctx}")
        if kind == TENANT and path not in ("/api/v1/auth/me", "/api/v1/organizations"):
            assert rs.status_code in (400, 401, 403, 404), f"spoof {ctx} -> {rs.status_code} {rs.text[:200]}"
        if kind == PLATFORM:
            assert rb.status_code in (401, 403), f"{ctx}: tenant token reached platform route -> {rb.status_code}"

"""Human-readable activity rows from audit events."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.audit import AuditEvent
from app.models.organization import User

SECURITY_ACTIONS = frozenset(
    {
        "model_token_configured",
        "model_token_tested",
        "member_role_changed",
        "membership_deactivated",
        "user_deactivated",
        "invitation_revoked",
    }
)

FAILURE_METADATA_KEYS = ("result", "status", "last_test_status")


def _user_label(user: User | None, user_id: UUID | None) -> tuple[str, str | None, str | None]:
    if user:
        name = (user.full_name or "").strip() or user.email.split("@")[0]
        return name, user.email, None
    if user_id:
        return "Deleted user", None, str(user_id)
    return "System", None, None


def _category_for(action: str, resource_type: str) -> str:
    if "invitation" in action or action in {"user_invited", "member_invited"}:
        return "Invitations"
    if action.startswith("organization") or resource_type == "organization":
        return "Organization"
    if "member" in action or "user" in action or resource_type == "user":
        return "Users"
    if "source" in action or resource_type == "source":
        return "Sources"
    if "document" in action or "credential" in action or "token" in action:
        return "Settings"
    if "questionnaire" in action or "answer" in action or resource_type in {"questionnaire", "answer"}:
        return "Security"
    return "Security" if action in SECURITY_ACTIONS else "Organization"


def _action_group(action: str) -> str:
    cat = _category_for(action, "")
    if cat in {"Invitations", "Users"}:
        return "Users" if "member" not in action and action != "user_invited" else cat
    return cat


def _is_failure(metadata: dict) -> bool:
    for key in FAILURE_METADATA_KEYS:
        val = metadata.get(key)
        if isinstance(val, str) and val.lower() in {"failed", "error", "failure"}:
            return True
    return metadata.get("success") is False


def _target_label(action: str, metadata: dict, resource_type: str, resource_id: str | None) -> str | None:
    if metadata.get("email"):
        return str(metadata["email"])
    if metadata.get("role"):
        return str(metadata["role"])
    if resource_type and resource_id and resource_type not in {"organization"}:
        return f"{resource_type}"
    return None


def build_sentence(action: str, actor_name: str, metadata: dict, resource_type: str) -> str:
    email = metadata.get("email")
    role = metadata.get("role")
    role_label = f" as {role}" if role else ""

    templates: dict[str, str] = {
        "organization_created": f"{actor_name} created the organization",
        "user_invited": f"{actor_name} invited {email or 'a user'}{role_label}",
        "member_invited": f"{actor_name} invited {email or 'a member'}{role_label}",
        "invitation_accepted": f"{actor_name} accepted the invitation",
        "invitation_revoked": f"{actor_name} revoked an invitation",
        "invitation_resent": f"{actor_name} resent an invitation",
        "member_role_changed": f"{actor_name} changed a member role",
        "membership_deactivated": f"{actor_name} deactivated a member",
        "user_deactivated": f"{actor_name} deactivated a user",
        "organization_license_updated": (
            f"Platform: license {metadata.get('license_status', 'updated')}"
            if metadata.get("source") == "platform_control_plane"
            else f"{actor_name} updated organization licensing"
        ),
        "source_connected": f"{actor_name} connected a source",
        "questionnaire_created": f"{actor_name} created a questionnaire",
        "questionnaire_uploaded": f"{actor_name} uploaded a questionnaire",
        "questionnaire_exported": f"{actor_name} exported a questionnaire",
        "answer_approved": f"{actor_name} approved an answer",
        "answer_edited": f"{actor_name} edited an answer",
        "client_document_uploaded": f"{actor_name} uploaded a document",
        "client_document_removed": f"{actor_name} removed a document",
        "model_token_configured": f"{actor_name} updated the model token",
        "model_token_tested": f"{actor_name} tested the model token connection",
        "employee_link_copied": f"{actor_name} copied the employee sign-in link",
    }
    if action in templates:
        return templates[action]
    readable = action.replace("_", " ")
    return f"{actor_name} {readable}"


def enrich_event(event: AuditEvent, users_by_id: dict[UUID, User]) -> dict:
    meta = event.event_metadata or {}
    user = users_by_id.get(event.user_id) if event.user_id else None
    actor_name, actor_email, actor_id_fallback = _user_label(user, event.user_id)
    category = _category_for(event.action, event.resource_type)
    sentence = build_sentence(event.action, actor_name, meta, event.resource_type)
    secondary_parts = [category]
    if meta.get("role"):
        secondary_parts.append(f"{meta.get('role')} role")
    elif event.resource_type:
        secondary_parts.append(event.resource_type.replace("_", " "))
    secondary = " · ".join(secondary_parts)

    changes: dict | None = None
    if "from" in meta and "to" in meta:
        changes = {"before": meta.get("from"), "after": meta.get("to")}
    elif "license_limit" in meta:
        changes = {"after": {k: meta[k] for k in ("license_limit", "license_status", "is_active") if k in meta}}

    result = "Failed" if _is_failure(meta) else "Success"
    if event.action.endswith("_tested") and meta.get("result"):
        result = str(meta["result"]).title()

    return {
        "id": event.id,
        "action": event.action,
        "resource_type": event.resource_type,
        "resource_id": event.resource_id,
        "created_at": event.created_at,
        "actor_user_id": event.user_id,
        "actor_name": actor_name,
        "actor_email": actor_email,
        "actor_deleted_id": actor_id_fallback,
        "target_label": _target_label(event.action, meta, event.resource_type, event.resource_id),
        "summary": sentence,
        "category": category,
        "secondary": secondary,
        "action_group": _action_group(event.action),
        "is_security": event.action in SECURITY_ACTIONS,
        "is_failure": result == "Failed",
        "result": result,
        "ip_address": meta.get("ip_address") or meta.get("ip"),
        "user_agent": meta.get("user_agent") or meta.get("device"),
        "request_id": meta.get("request_id"),
        "changes": changes,
        "metadata_safe": {k: v for k, v in meta.items() if k not in {"password", "token", "secret"}},
    }


def load_users_for_events(db: Session, events: list[AuditEvent]) -> dict[UUID, User]:
    ids = {e.user_id for e in events if e.user_id}
    if not ids:
        return {}
    rows = db.scalars(select(User).where(User.id.in_(ids))).all()
    return {u.id: u for u in rows}

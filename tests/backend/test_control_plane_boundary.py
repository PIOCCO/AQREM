"""Master console must not expose customer content APIs."""

from app.api.v1 import master


def test_master_router_has_no_evidence_or_chat_routes():
    paths = [getattr(r, "path", "") for r in master.router.routes]
    joined = " ".join(paths)
    assert "evidence" not in joined.lower()
    assert "chat" not in joined.lower()
    assert "questionnaire" not in joined.lower()

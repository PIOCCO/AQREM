"""Public invitation URL builder (PUBLIC_APP_URL)."""

from urllib.parse import unquote

import pytest

from app.services.invitations.invite_urls import (
    absolute_from_invite_path,
    build_invite_url,
    invite_path,
    public_app_base_url,
)


@pytest.fixture()
def public_url(monkeypatch):
    monkeypatch.setenv("PUBLIC_APP_URL", "http://100.80.43.124:5173/")
    from app.core.config import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_build_admin_and_employee_urls(public_url):
    admin = build_invite_url("admin", "tok@@en")
    assert admin == "http://100.80.43.124:5173/invite/admin/tok%40%40en"
    employee = build_invite_url("employee", "join-tok")
    assert employee == "http://100.80.43.124:5173/join/join-tok"


def test_trailing_slash_stripped(public_url):
    assert public_app_base_url() == "http://100.80.43.124:5173"
    path = invite_path("admin", "abc")
    assert absolute_from_invite_path(path) == "http://100.80.43.124:5173/invite/admin/abc"


def test_token_roundtrip_in_path():
    raw = "73ec282b-f4e1-46ab-bfeb-49ef60265409"
    path = invite_path("admin", raw)
    assert unquote(path.split("/invite/admin/", 1)[1]) == raw

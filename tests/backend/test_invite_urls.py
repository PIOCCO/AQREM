"""Public invitation URL builder (PUBLIC_BASE_URL / PUBLIC_APP_URL)."""

from urllib.parse import unquote

import pytest
from starlette.requests import Request

from app.services.invitations.invite_urls import (
    absolute_from_invite_path,
    base_url_from_request,
    build_invite_url,
    invite_path,
    public_app_base_url,
    resolve_public_base_url,
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


def test_request_fallback_when_env_unset(monkeypatch):
    monkeypatch.delenv("PUBLIC_APP_URL", raising=False)
    monkeypatch.delenv("PUBLIC_BASE_URL", raising=False)
    monkeypatch.delenv("APP_PUBLIC_BASE_URL", raising=False)
    from app.core.config import get_settings

    get_settings.cache_clear()
    assert public_app_base_url() == ""

    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": [(b"host", b"dev.example.com:5173"), (b"x-forwarded-proto", b"https")],
        "query_string": b"",
        "client": ("127.0.0.1", 12345),
        "server": ("dev.example.com", 5173),
        "scheme": "http",
    }
    request = Request(scope)
    assert base_url_from_request(request) == "https://dev.example.com:5173"
    assert resolve_public_base_url(request=request) == "https://dev.example.com:5173"
    url = build_invite_url("member", "abc", request=request)
    assert url == "https://dev.example.com:5173/invite/member/abc"
    get_settings.cache_clear()

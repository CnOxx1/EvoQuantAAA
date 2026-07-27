from __future__ import annotations

from api_gateway.auth import check_bearer
from api_gateway.models import fail, ok


def test_envelope():
    assert ok([1, 2])["data"] == [1, 2]
    err = fail("E", "bad", status=422)
    assert err["ok"] is False and err["error"]["status"] == 422


def test_auth_open_when_no_token(monkeypatch):
    monkeypatch.delenv("ASHARE_API_TOKEN", raising=False)
    monkeypatch.delenv("ASHARE_API_REQUIRE_TOKEN", raising=False)
    assert check_bearer(None) == (True, "anonymous")


def test_auth_require_token_when_unset(monkeypatch):
    monkeypatch.delenv("ASHARE_API_TOKEN", raising=False)
    monkeypatch.setenv("ASHARE_API_REQUIRE_TOKEN", "1")
    ok, msg = check_bearer(None)
    assert ok is False and "ASHARE_API_TOKEN required" in (msg or "")


def test_auth_requires_bearer(monkeypatch):
    monkeypatch.delenv("ASHARE_API_REQUIRE_TOKEN", raising=False)
    monkeypatch.setenv("ASHARE_API_TOKEN", "tok")
    assert check_bearer(None)[0] is False
    assert check_bearer("Bearer tok") == (True, "token")
    assert check_bearer("Bearer no")[0] is False


def test_app_health():
    pytest = __import__("pytest")
    try:
        from fastapi.testclient import TestClient
        from api_gateway.app import create_app
    except ImportError:
        pytest.skip("fastapi not installed")
    client = TestClient(create_app())
    r = client.get("/health")
    assert r.status_code == 200 and r.json()["ok"] is True
    r2 = client.get("/v1/strategies")
    assert r2.status_code == 200 and r2.json()["ok"] is True

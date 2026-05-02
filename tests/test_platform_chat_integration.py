"""Integration tests: ``nom.platform`` seams wired into ``nom.chat.server``.

Proves the refactor preserves the original auth contract while
running through the new ``Authenticator`` Protocol — and that
``current_user`` is correctly set inside request handlers.
"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from nom.chat.server import build_app
from nom.chat.store import MemoryStore
from nom.platform import current_user
from tests._fakes import FakeEmbedder as _FakeEmbedder
from tests._fakes import FakeLLM as _FakeLLM


def _make_app() -> Any:
    return build_app(store=MemoryStore(embedder=_FakeEmbedder(), llm=_FakeLLM()))


def test_no_auth_env_means_open_api(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("NOM_AUTH_TOKEN", raising=False)
    monkeypatch.delenv("NOM_AUTH_PLUGIN", raising=False)
    c = TestClient(_make_app())
    assert c.get("/api/health").json()["auth_required"] is False
    # No 401 — we expect 200 since no auth is configured.
    assert c.get("/api/spaces").status_code == 200


def test_bearer_token_route_via_platform(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NOM_AUTH_TOKEN", "topsecret")
    monkeypatch.delenv("NOM_AUTH_PLUGIN", raising=False)
    c = TestClient(_make_app())
    assert c.get("/api/health").json()["auth_required"] is True
    assert c.get("/api/spaces").status_code == 401
    ok = c.get("/api/spaces", headers={"Authorization": "Bearer topsecret"})
    assert ok.status_code == 200


def test_current_user_is_set_during_request(monkeypatch: pytest.MonkeyPatch) -> None:
    """Hooking a tool route, we should observe ``current_user`` inside
    the handler when the request authenticated successfully."""
    monkeypatch.setenv("NOM_AUTH_TOKEN", "abc")
    monkeypatch.delenv("NOM_AUTH_PLUGIN", raising=False)
    app = _make_app()
    captured: dict[str, str | None] = {}

    @app.get("/api/_probe_user")
    def probe() -> dict[str, str | None]:
        u = current_user.get()
        captured["id"] = u.id if u else None
        captured["tenant"] = u.tenant_id if u else None
        return captured

    c = TestClient(app)
    r = c.get("/api/_probe_user", headers={"Authorization": "Bearer abc"})
    assert r.status_code == 200
    assert captured["id"] == "anonymous"
    assert captured["tenant"] == "default"


def test_current_user_reset_after_request(monkeypatch: pytest.MonkeyPatch) -> None:
    """The middleware must reset the ContextVar at request exit so
    one request never leaks identity into another."""
    monkeypatch.setenv("NOM_AUTH_TOKEN", "abc")
    monkeypatch.delenv("NOM_AUTH_PLUGIN", raising=False)
    c = TestClient(_make_app())
    c.get("/api/spaces", headers={"Authorization": "Bearer abc"})
    # In the test thread, current_user should be back to its default
    # because ContextVar.reset ran in the middleware's finally block.
    assert current_user.get() is None


def test_plugin_env_takes_priority_over_bearer(monkeypatch: pytest.MonkeyPatch) -> None:
    """When both env vars are set, NOM_AUTH_PLUGIN wins.

    We register a fake plugin via monkeypatching the plugin loader so
    the test stays self-contained.
    """
    from nom.platform import plugins as plugins_mod

    class _StubPlugin:
        name = "stub"

        def authenticate(self, *, credentials: Any) -> Any:
            from nom.platform import AuthDeniedError

            raise AuthDeniedError("stub denies all")

    def fake_load(category: str, name: str | None = None) -> Any:
        assert category == "auth"
        assert name == "stub"
        return _StubPlugin

    monkeypatch.setattr(plugins_mod, "load_plugin", fake_load)
    # Re-export the patched name into the chat.server module's namespace
    # since server.py does `from nom.platform import load_plugin` lazily.
    import nom.platform

    monkeypatch.setattr(nom.platform, "load_plugin", fake_load)

    monkeypatch.setenv("NOM_AUTH_TOKEN", "would-have-worked")
    monkeypatch.setenv("NOM_AUTH_PLUGIN", "stub")
    c = TestClient(_make_app())
    # Bearer that *would* have passed under NOM_AUTH_TOKEN now fails
    # because NOM_AUTH_PLUGIN took precedence and the stub denies.
    r = c.get("/api/spaces", headers={"Authorization": "Bearer would-have-worked"})
    assert r.status_code == 401
    assert "stub denies all" in r.json()["detail"]

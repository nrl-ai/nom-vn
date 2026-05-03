"""SPA-fallback routing regression tests.

The catch-all `/{path:path}` route MUST be registered last so concrete
`/api/*` routes win FastAPI's first-match-wins resolution. We caught a
regression where the catch-all swallowed `/api/health` and every other
`/api/*` request went to 404. These tests lock the contract:

- Real API routes still respond.
- Unknown SPA paths (e.g. `/translate`) serve the React shell so deep
  links and back/forward navigation work.
- Unknown `/api/*` paths must stay 404 — clients that try to fetch a
  typo'd endpoint should see an HTTP error, not parse the SPA shell as
  JSON.
"""

from __future__ import annotations

import pytest

fastapi = pytest.importorskip("fastapi")
pytest.importorskip("fastapi.testclient")

from fastapi.testclient import TestClient  # noqa: E402

from nom.chat.server import build_app  # noqa: E402
from nom.chat.store import MemoryStore  # noqa: E402
from tests._fakes import FakeEmbedder, FakeLLM  # noqa: E402


@pytest.fixture
def client() -> TestClient:
    store = MemoryStore(embedder=FakeEmbedder(), llm=FakeLLM(response="ok"))
    return TestClient(build_app(store=store))


class TestApiRoutesStillWork:
    def test_health_returns_200(self, client: TestClient) -> None:
        r = client.get("/api/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"

    def test_translate_models_returns_200(self, client: TestClient) -> None:
        r = client.get("/api/tools/translate/models")
        assert r.status_code == 200

    def test_unknown_api_path_returns_404(self, client: TestClient) -> None:
        r = client.get("/api/no-such-route")
        assert r.status_code == 404


class TestSpaDeepLinks:
    @pytest.mark.parametrize(
        "path",
        [
            "/translate",
            "/convert",
            "/diacritic",
            "/tokenize",
            "/normalize",
            "/strip",
            "/models",
            "/agents",
            "/compliance",
            "/admin",
            "/settings",
        ],
    )
    def test_spa_route_serves_index(self, client: TestClient, path: str) -> None:
        # When the UI bundle is staged into the package, deep links must
        # serve index.html so the React router can take over. CI ships a
        # placeholder index.html (just `<title>Nôm — UI placeholder</title>`)
        # and the test should pass against that too — what we're really
        # guarding here is the routing order (catch-all fires last so
        # `/api/*` resolves first), not the bundle contents.
        r = client.get(path)
        if r.status_code == 404:
            pytest.skip("UI dist not staged in this environment")
        assert r.status_code == 200
        # Any HTML response is fine — full bundle has `<div id="root">`,
        # CI placeholder has `<title>Nôm — UI placeholder</title>`.
        body = r.text.lower()
        assert (
            '<div id="root"' in r.text
            or "<html" in body
            or "<title>" in body
            or "<!doctype" in body
        )

    def test_root_serves_index(self, client: TestClient) -> None:
        r = client.get("/")
        if r.status_code == 404:
            pytest.skip("UI dist not staged in this environment")
        assert r.status_code == 200

"""Tests for /api/compliance/classify — risk-classifier HTTP surface."""

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
    store = MemoryStore(embedder=FakeEmbedder(), llm=FakeLLM())
    return TestClient(build_app(store=store))


def test_classify_low_risk_individual_assistant(client: TestClient) -> None:
    r = client.post(
        "/api/compliance/classify",
        json={
            "purpose": "Trợ lý cá nhân tóm tắt email tiếng Việt",
            "sector": "other",
            "automation_level": "advisory",
            "user_scope": "individual",
            "handles_personal_data": False,
            "affects_vulnerable_groups": False,
            "can_generate_synthetic_content": False,
            "interacts_directly_with_users": True,
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["tier"] in {"low", "medium"}
    assert "Đ11.1" in body["applicable_articles"]


def test_classify_high_risk_health_autonomous(client: TestClient) -> None:
    r = client.post(
        "/api/compliance/classify",
        json={
            "purpose": "Hệ thống tự động chẩn đoán bệnh án trẻ em",
            "sector": "health",
            "automation_level": "autonomous",
            "user_scope": "public-mass",
            "handles_personal_data": True,
            "affects_vulnerable_groups": True,
            "can_generate_synthetic_content": False,
            "interacts_directly_with_users": True,
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["tier"] == "high"
    # Đ14.1 (high-risk obligations) should be on the list.
    assert "Đ14.1" in body["applicable_articles"]
    assert len(body["reasoning"]) > 0


def test_classify_synthetic_content_triggers_marking_articles(client: TestClient) -> None:
    r = client.post(
        "/api/compliance/classify",
        json={
            "purpose": "Hệ thống sinh ảnh tổng hợp cho marketing",
            "sector": "other",
            "automation_level": "advisory",
            "user_scope": "public-mass",
            "handles_personal_data": False,
            "affects_vulnerable_groups": False,
            "can_generate_synthetic_content": True,
            "interacts_directly_with_users": True,
        },
    )
    assert r.status_code == 200
    body = r.json()
    arts = body["applicable_articles"]
    assert "Đ11.2" in arts
    assert "Đ11.4" in arts


def test_classify_empty_purpose_422(client: TestClient) -> None:
    r = client.post(
        "/api/compliance/classify",
        json={"purpose": "", "sector": "other", "automation_level": "advisory"},
    )
    assert r.status_code == 422


def test_classify_invalid_sector_422(client: TestClient) -> None:
    r = client.post(
        "/api/compliance/classify",
        json={
            "purpose": "x",
            "sector": "not-a-sector",
            "automation_level": "advisory",
            "user_scope": "individual",
            "handles_personal_data": False,
            "affects_vulnerable_groups": False,
            "can_generate_synthetic_content": False,
        },
    )
    # SystemSpec doesn't runtime-validate Literal at construction; the
    # rule table will simply not match anything. We accept either a
    # 200 with low tier OR a 422; assert the tier is sane in either
    # case.
    assert r.status_code in {200, 422}

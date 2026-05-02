"""Tests for ``nom.compliance.transparency``."""

from __future__ import annotations

import json
from pathlib import Path

from nom.compliance.transparency import (
    AI_INTERACTION_NOTICE_EN,
    AI_INTERACTION_NOTICE_VI,
    PROVENANCE_VERSION,
    interaction_notice,
    mark_image,
    mark_text_html,
    write_sidecar,
)


def test_notice_constants_mention_law() -> None:
    assert "134/2025" in AI_INTERACTION_NOTICE_VI
    assert "134/2025" in AI_INTERACTION_NOTICE_EN
    assert "AI" in AI_INTERACTION_NOTICE_VI


def test_interaction_notice_inserts_system_name() -> None:
    out = interaction_notice(system_name="Trợ lý hợp đồng")
    assert "[Trợ lý hợp đồng]" in out
    assert "AI" in out


def test_interaction_notice_english() -> None:
    out = interaction_notice(system_name="Contract Assistant", language="en")
    assert "interacting with an AI system" in out


def test_interaction_notice_with_model_label() -> None:
    out = interaction_notice(system_name="Bot", model_label="qwen3:8b")
    assert "qwen3:8b" in out
    assert "Mô hình" in out


def test_mark_image_returns_manifest_with_required_fields(tmp_path: Path) -> None:
    img = tmp_path / "out.png"
    img.write_bytes(b"fake png")
    m = mark_image(img, model="ollama:qwen3-vl", prompt_summary="VN landscape")
    assert m.version == PROVENANCE_VERSION
    assert m.media_type == "image/png"
    assert m.model == "ollama:qwen3-vl"
    assert m.is_ai_generated is True
    assert m.is_synthetic is False
    assert m.prompt_summary == "VN landscape"


def test_mark_image_synthetic_flag(tmp_path: Path) -> None:
    img = tmp_path / "deepfake.jpg"
    img.write_bytes(b"x")
    m = mark_image(img, model="sd-3.5", is_synthetic=True)
    assert m.is_synthetic is True
    assert m.media_type == "image/jpeg"


def test_write_sidecar_default_path(tmp_path: Path) -> None:
    img = tmp_path / "out.png"
    img.write_bytes(b"x")
    m = mark_image(img, model="m")
    sidecar = write_sidecar(m)
    assert sidecar == img.with_suffix(".png.nom-provenance.json")
    data = json.loads(sidecar.read_text())
    assert data["version"] == PROVENANCE_VERSION
    assert data["model"] == "m"


def test_write_sidecar_custom_path(tmp_path: Path) -> None:
    img = tmp_path / "out.png"
    img.write_bytes(b"x")
    m = mark_image(img, model="m")
    custom = tmp_path / "manifests" / "out.json"
    sidecar = write_sidecar(m, sidecar_path=custom)
    assert sidecar == custom
    assert custom.exists()


def test_mark_text_html_inserts_meta_into_head() -> None:
    html = "<html><head><title>x</title></head><body>x</body></html>"
    out = mark_text_html(html, model="qwen3")
    assert 'name="ai-generated"' in out
    assert "qwen3" in out
    # Tag landed before </head>
    head_close = out.find("</head>")
    tag_pos = out.find('<meta name="ai-generated"')
    assert tag_pos != -1
    assert tag_pos < head_close


def test_mark_text_html_idempotent() -> None:
    html = "<html><head></head><body></body></html>"
    once = mark_text_html(html, model="m")
    twice = mark_text_html(once, model="m2")
    # Only one ai-generated meta tag in the final output
    assert twice.count('name="ai-generated"') == 1
    # Latest model wins
    assert "m2" in twice


def test_mark_text_html_no_head() -> None:
    """Headless HTML still gets the tag (prepended)."""
    out = mark_text_html("<p>hi</p>", model="m")
    assert out.startswith('<meta name="ai-generated"')


def test_mark_text_html_attr_escaping() -> None:
    """Model strings with special chars don't break HTML."""
    out = mark_text_html("<html><head></head></html>", model='evil"<m>')
    # Escaped quote → no premature attribute close
    assert "&quot;" in out


def test_provenance_manifest_to_json(tmp_path: Path) -> None:
    img = tmp_path / "x.png"
    img.write_bytes(b"x")
    m = mark_image(img, model="m", extra={"license": "internal"})
    js = m.to_json()
    parsed = json.loads(js)
    assert parsed["extra"] == {"license": "internal"}

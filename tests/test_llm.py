"""Tests for nom.llm — Ollama adapter and stub providers.

The Ollama adapter is tested with a mocked httpx response — we don't
spin up a real Ollama server in the test suite. The integration test in
``benchmarks/`` (manual, gated) exercises the real network path.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from nom.llm import Anthropic, Ollama, OpenAI


class TestOllamaAdapter:
    def _patch_httpx(self, monkeypatch: pytest.MonkeyPatch, response_content: str) -> MagicMock:
        """Patch httpx.post on the adapter instance to return a canned response."""
        # Create a fake httpx module exposing a .post that returns a fake response.
        fake_response = MagicMock()
        fake_response.json.return_value = {
            "message": {"role": "assistant", "content": response_content}
        }
        fake_response.raise_for_status.return_value = None

        fake_httpx = MagicMock()
        fake_httpx.post.return_value = fake_response
        return fake_httpx

    def test_construct_default_model(self) -> None:
        llm = Ollama()
        assert llm.model == "qwen3:8b"
        assert llm.base_url == "http://localhost:11434"

    def test_construct_custom_model(self) -> None:
        llm = Ollama(model="llama3.1:8b", base_url="http://gpu-box:11434/")
        assert llm.model == "llama3.1:8b"
        assert llm.base_url == "http://gpu-box:11434"  # trailing slash stripped

    def test_complete_returns_message_content(self) -> None:
        llm = Ollama()
        llm._httpx = self._patch_httpx(None, "Hợp đồng số 02")  # type: ignore[arg-type,assignment]
        result = llm.complete("Tóm tắt văn bản:")
        assert result == "Hợp đồng số 02"

    def test_complete_with_schema_passes_format(self) -> None:
        llm = Ollama()
        fake = self._patch_httpx(None, '{"so": "HD-001"}')  # type: ignore[arg-type]
        llm._httpx = fake  # type: ignore[assignment]

        schema = {"type": "object", "properties": {"so": {"type": "string"}}}
        llm.complete("Extract:", schema=schema)

        # Verify the request body included the schema in 'format'
        call_kwargs = fake.post.call_args.kwargs
        body = call_kwargs["json"]
        assert body["format"] == schema
        assert body["model"] == "qwen3:8b"
        assert body["stream"] is False

    def test_complete_without_schema_omits_format(self) -> None:
        llm = Ollama()
        fake = self._patch_httpx(None, "result")  # type: ignore[arg-type]
        llm._httpx = fake  # type: ignore[assignment]

        llm.complete("Hello")

        body = fake.post.call_args.kwargs["json"]
        assert "format" not in body

    def test_temperature_in_options(self) -> None:
        llm = Ollama(temperature=0.7)
        fake = self._patch_httpx(None, "x")  # type: ignore[arg-type]
        llm._httpx = fake  # type: ignore[assignment]

        llm.complete("Hi")

        body = fake.post.call_args.kwargs["json"]
        assert body["options"]["temperature"] == 0.7

    def test_unexpected_response_shape_raises(self) -> None:
        llm = Ollama()
        fake_response = MagicMock()
        fake_response.json.return_value = {"unexpected": "shape"}
        fake_response.raise_for_status.return_value = None
        fake_httpx = MagicMock()
        fake_httpx.post.return_value = fake_response
        llm._httpx = fake_httpx  # type: ignore[assignment]

        with pytest.raises(RuntimeError, match=r"Unexpected"):
            llm.complete("Hi")

    def test_repr(self) -> None:
        llm = Ollama(model="llama3.1:8b")
        assert "llama3.1:8b" in repr(llm)


class TestStubProviders:
    """OpenAI and Anthropic still raise NotImplementedError until v0.1.1."""

    def test_openai_stub_raises(self) -> None:
        llm = OpenAI(model="gpt-4o")
        with pytest.raises(NotImplementedError, match=r"v0\.1\.1"):
            llm.complete("Hi")

    def test_anthropic_stub_raises(self) -> None:
        llm = Anthropic(model="claude-sonnet")
        with pytest.raises(NotImplementedError, match=r"v0\.1\.1"):
            llm.complete("Hi")

    def test_stubs_have_names(self) -> None:
        assert OpenAI().name == "openai"
        assert Anthropic().name == "anthropic"


class _FakeLLM:
    """Test double for the LLM Protocol used by Extract tests."""

    name = "fake"

    def __init__(self, responses: list[str]) -> None:
        self.responses = list(responses)
        self.calls: list[dict[str, Any]] = []

    def complete(
        self,
        prompt: str,
        *,
        schema: dict[str, Any] | None = None,
        max_tokens: int = 2048,
    ) -> str:
        self.calls.append({"prompt": prompt, "schema": schema, "max_tokens": max_tokens})
        if not self.responses:
            raise RuntimeError("FakeLLM ran out of canned responses")
        return self.responses.pop(0)


@pytest.fixture
def fake_llm_factory():  # type: ignore[no-untyped-def]
    """Factory for building a FakeLLM with a list of responses."""

    def make(*responses: str) -> _FakeLLM:
        return _FakeLLM(list(responses))

    return make


class TestExtractStage:
    """Real Extract stage — schema-driven LLM extraction with retries."""

    def _make_ctx(self):  # type: ignore[no-untyped-def]
        from nom.doc.pipeline import Context

        return Context(
            source="x.pdf",
            text="Hợp đồng số HD-001 ngày 14/3/2025",
            schema={"so": str, "ngay": "date"},
        )

    def test_happy_path_one_call(self, fake_llm_factory):  # type: ignore[no-untyped-def]
        from nom.doc import Extract

        llm = fake_llm_factory('{"so": "HD-001", "ngay": "14/3/2025"}')
        ctx = self._make_ctx()
        Extract(llm).run(ctx)

        assert ctx.output == {"so": "HD-001", "ngay": "14/3/2025"}
        assert len(llm.calls) == 1
        assert ctx.metadata["extract_attempts"] == 1

    def test_strips_markdown_fence(self, fake_llm_factory):  # type: ignore[no-untyped-def]
        from nom.doc import Extract

        # Model wrapped its JSON in ```json ... ```
        llm = fake_llm_factory('```json\n{"so": "X", "ngay": "1/1/2025"}\n```')
        ctx = self._make_ctx()
        Extract(llm).run(ctx)

        assert ctx.output == {"so": "X", "ngay": "1/1/2025"}

    def test_retries_on_invalid_json(self, fake_llm_factory):  # type: ignore[no-untyped-def]
        from nom.doc import Extract

        llm = fake_llm_factory(
            "this is not json",  # attempt 1: garbage
            '{"so": "OK", "ngay": "1/1/2025"}',  # attempt 2: valid
        )
        ctx = self._make_ctx()
        Extract(llm).run(ctx)

        assert ctx.output["so"] == "OK"
        assert ctx.metadata["extract_attempts"] == 2
        # Second prompt should include the failure feedback.
        assert "invalid output" in llm.calls[1]["prompt"]

    def test_gives_up_after_max_retries(self, fake_llm_factory):  # type: ignore[no-untyped-def]
        from nom.doc import Extract

        llm = fake_llm_factory("garbage", "still garbage", "still garbage")
        ctx = self._make_ctx()
        with pytest.raises(RuntimeError, match=r"Extract failed after 3"):
            Extract(llm, max_retries=3).run(ctx)
        assert len(llm.calls) == 3

    def test_rejects_none_llm(self) -> None:
        from nom.doc import Extract

        with pytest.raises(ValueError, match=r"requires an LLM"):
            Extract(llm=None)

    def test_rejects_zero_retries(self, fake_llm_factory):  # type: ignore[no-untyped-def]
        from nom.doc import Extract

        with pytest.raises(ValueError, match=r"max_retries"):
            Extract(fake_llm_factory(), max_retries=0)

    def test_no_schema_raises(self, fake_llm_factory):  # type: ignore[no-untyped-def]
        from nom.doc import Extract
        from nom.doc.pipeline import Context

        ctx = Context(source="x.pdf", text="hello")  # no schema
        with pytest.raises(RuntimeError, match=r"schema"):
            Extract(fake_llm_factory("{}")).run(ctx)

    def test_no_text_raises(self, fake_llm_factory):  # type: ignore[no-untyped-def]
        from nom.doc import Extract
        from nom.doc.pipeline import Context

        ctx = Context(source="x.pdf", schema={"so": str})  # no text
        with pytest.raises(RuntimeError, match=r"text"):
            Extract(fake_llm_factory("{}")).run(ctx)

    def test_response_is_array_not_object_retries(self, fake_llm_factory):  # type: ignore[no-untyped-def]
        from nom.doc import Extract

        # First response is a JSON array, not an object — retry should succeed.
        llm = fake_llm_factory(
            "[1, 2, 3]",
            '{"so": "X", "ngay": "1/1/2025"}',
        )
        ctx = self._make_ctx()
        Extract(llm).run(ctx)
        assert ctx.output["so"] == "X"
        assert ctx.metadata["extract_attempts"] == 2

    def test_passes_schema_to_llm(self, fake_llm_factory):  # type: ignore[no-untyped-def]
        from nom.doc import Extract

        llm = fake_llm_factory('{"so": "X", "ngay": "1/1/2025"}')
        ctx = self._make_ctx()
        Extract(llm).run(ctx)

        # The LLM should have been called with a JSON schema (Pydantic-generated).
        call_schema = llm.calls[0]["schema"]
        assert call_schema is not None
        assert "properties" in call_schema
        assert "so" in call_schema["properties"]


class TestEndToEndPipeline:
    """Run a complete pipeline (text input → extracted dict) without OCR.

    Uses a fake LLM so no Ollama server is required. Demonstrates that
    Load → Parse → Normalize → Extract → Validate compose end-to-end.
    """

    def test_full_pipeline_text_input(self, fake_llm_factory):  # type: ignore[no-untyped-def]
        from nom.doc import Extract, Load, Normalize, Parse, Pipeline, Validate

        text = "Hợp đồng số HD-001 ngày 14/3/2025, tổng giá trị 1.500.000.000 đồng"
        llm = fake_llm_factory('{"so": "HD-001", "ngay": "14/3/2025", "gia": "1.500.000.000"}')

        # Note: we skip OCR (it's a placeholder for image inputs only).
        pipe = Pipeline(
            [
                Load(),
                Parse(),
                Normalize(),
                Extract(llm),
                Validate(),
            ]
        )
        result = pipe.run(
            text.encode("utf-8"),
            schema={"so": str, "ngay": "date", "gia": "amount_vnd"},
        )

        from datetime import date

        assert result["so"] == "HD-001"
        assert result["ngay"] == date(2025, 3, 14)
        assert result["gia"] == 1_500_000_000

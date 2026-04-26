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

    def test_think_false_by_default(self) -> None:
        # Qwen3 / DeepSeek-R1 burn token budget on hidden CoT when think mode is
        # on, leaving the content field empty for terse extraction tasks. We
        # default the adapter to think=False so the model emits the answer
        # straight into content; Ollama silently ignores think on non-thinking
        # models.
        llm = Ollama()
        fake = self._patch_httpx(None, "ok")  # type: ignore[arg-type]
        llm._httpx = fake  # type: ignore[assignment]
        llm.complete("Hi")
        body = fake.post.call_args.kwargs["json"]
        assert body["think"] is False

    def test_think_true_when_opted_in(self) -> None:
        llm = Ollama(think=True)
        fake = self._patch_httpx(None, "ok")  # type: ignore[arg-type]
        llm._httpx = fake  # type: ignore[assignment]
        llm.complete("Hi")
        body = fake.post.call_args.kwargs["json"]
        assert body["think"] is True


class TestOpenAIAdapter:
    """OpenAI adapter — mocked HTTP, no live calls. Covers default OpenAI
    + OpenAI-compatible endpoints (Azure / DeepSeek / OpenRouter / etc.)
    via ``base_url``. Live integration is exercised manually in
    ``benchmarks/`` against actual OPENAI_API_KEY.
    """

    def _patch(self, content: str) -> MagicMock:
        """Build a fake httpx that returns one canned chat completion."""
        fake_response = MagicMock()
        fake_response.json.return_value = {
            "choices": [{"message": {"role": "assistant", "content": content}}]
        }
        fake_response.raise_for_status.return_value = None
        fake_httpx = MagicMock()
        fake_httpx.post.return_value = fake_response
        return fake_httpx

    def test_construct_default_model(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        llm = OpenAI()
        assert llm.model == "gpt-4o-mini"
        assert llm.base_url == "https://api.openai.com/v1"
        assert llm.name == "openai"

    def test_construct_requires_api_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        with pytest.raises(RuntimeError, match=r"no API key"):
            OpenAI()

    def test_construct_accepts_explicit_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        llm = OpenAI(api_key="sk-explicit")
        assert llm._api_key == "sk-explicit"

    def test_complete_returns_choice_content(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        llm = OpenAI()
        llm._httpx = self._patch("Hello")  # type: ignore[assignment]
        assert llm.complete("Hi") == "Hello"

    def test_authorization_header_set(self) -> None:
        llm = OpenAI(api_key="sk-abc")
        fake = self._patch("x")
        llm._httpx = fake  # type: ignore[assignment]
        llm.complete("Hi")
        headers = fake.post.call_args.kwargs["headers"]
        assert headers["Authorization"] == "Bearer sk-abc"
        assert headers["Content-Type"] == "application/json"

    def test_schema_uses_response_format_strict(self) -> None:
        llm = OpenAI(api_key="sk-abc")
        fake = self._patch('{"so": "HD-001"}')
        llm._httpx = fake  # type: ignore[assignment]
        schema = {"type": "object", "properties": {"so": {"type": "string"}}}
        llm.complete("Extract:", schema=schema)
        body = fake.post.call_args.kwargs["json"]
        assert body["response_format"]["type"] == "json_schema"
        assert body["response_format"]["json_schema"]["strict"] is True
        assert body["response_format"]["json_schema"]["schema"] == schema

    def test_compatible_endpoint_via_base_url(self) -> None:
        """Same adapter, different provider — DeepSeek via ``base_url=``."""
        llm = OpenAI(
            model="deepseek-chat",
            api_key="sk-deepseek",
            base_url="https://api.deepseek.com/v1",
        )
        fake = self._patch("vâng")
        llm._httpx = fake  # type: ignore[assignment]
        llm.complete("Xin chào")
        url = fake.post.call_args.args[0]
        assert url == "https://api.deepseek.com/v1/chat/completions"
        body = fake.post.call_args.kwargs["json"]
        assert body["model"] == "deepseek-chat"

    def test_organization_header(self) -> None:
        llm = OpenAI(api_key="sk-abc", organization="org-test")
        fake = self._patch("x")
        llm._httpx = fake  # type: ignore[assignment]
        llm.complete("Hi")
        assert fake.post.call_args.kwargs["headers"]["OpenAI-Organization"] == "org-test"

    def test_unexpected_response_shape_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        llm = OpenAI(api_key="sk-abc")
        fake_response = MagicMock()
        fake_response.json.return_value = {"choices": []}
        fake_response.raise_for_status.return_value = None
        fake_httpx = MagicMock()
        fake_httpx.post.return_value = fake_response
        llm._httpx = fake_httpx  # type: ignore[assignment]
        with pytest.raises(RuntimeError, match=r"Unexpected"):
            llm.complete("Hi")


class TestAnthropicAdapter:
    """Anthropic adapter — mocked HTTP, no live calls."""

    def _patch_text(self, text: str) -> MagicMock:
        fake_response = MagicMock()
        fake_response.json.return_value = {
            "content": [{"type": "text", "text": text}],
            "stop_reason": "end_turn",
        }
        fake_response.raise_for_status.return_value = None
        fake_httpx = MagicMock()
        fake_httpx.post.return_value = fake_response
        return fake_httpx

    def _patch_tool_use(self, tool_input: dict[str, Any]) -> MagicMock:
        fake_response = MagicMock()
        fake_response.json.return_value = {
            "content": [{"type": "tool_use", "name": "nom_extract", "input": tool_input}],
            "stop_reason": "tool_use",
        }
        fake_response.raise_for_status.return_value = None
        fake_httpx = MagicMock()
        fake_httpx.post.return_value = fake_response
        return fake_httpx

    def test_construct_default_model(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
        llm = Anthropic()
        assert llm.model.startswith("claude-haiku-4-5")
        assert llm.base_url == "https://api.anthropic.com"
        assert llm.name == "anthropic"

    def test_construct_requires_api_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        with pytest.raises(RuntimeError, match=r"no API key"):
            Anthropic()

    def test_complete_returns_text(self) -> None:
        llm = Anthropic(api_key="sk-ant-abc")
        llm._httpx = self._patch_text("Xin chào")  # type: ignore[assignment]
        assert llm.complete("Hi") == "Xin chào"

    def test_request_headers(self) -> None:
        llm = Anthropic(api_key="sk-ant-abc")
        fake = self._patch_text("x")
        llm._httpx = fake  # type: ignore[assignment]
        llm.complete("Hi")
        headers = fake.post.call_args.kwargs["headers"]
        assert headers["x-api-key"] == "sk-ant-abc"
        assert headers["anthropic-version"] == "2023-06-01"
        url = fake.post.call_args.args[0]
        assert url == "https://api.anthropic.com/v1/messages"

    def test_schema_uses_tool_use_pattern(self) -> None:
        llm = Anthropic(api_key="sk-ant-abc")
        fake = self._patch_tool_use({"so": "HD-001"})
        llm._httpx = fake  # type: ignore[assignment]
        schema = {"type": "object", "properties": {"so": {"type": "string"}}}
        result = llm.complete("Extract:", schema=schema)

        # Returned string is the tool input as JSON
        import json as _json

        assert _json.loads(result) == {"so": "HD-001"}

        # Request body has tools + forced tool_choice
        body = fake.post.call_args.kwargs["json"]
        assert body["tools"][0]["name"] == "nom_extract"
        assert body["tools"][0]["input_schema"] == schema
        assert body["tool_choice"] == {"type": "tool", "name": "nom_extract"}

    def test_text_concatenated_when_multiple_blocks(self) -> None:
        fake_response = MagicMock()
        fake_response.json.return_value = {
            "content": [
                {"type": "text", "text": "Xin "},
                {"type": "text", "text": "chào"},
            ],
            "stop_reason": "end_turn",
        }
        fake_response.raise_for_status.return_value = None
        fake_httpx = MagicMock()
        fake_httpx.post.return_value = fake_response
        llm = Anthropic(api_key="sk-ant-abc")
        llm._httpx = fake_httpx  # type: ignore[assignment]
        assert llm.complete("Hi") == "Xin chào"

    def test_no_text_block_raises(self) -> None:
        fake_response = MagicMock()
        fake_response.json.return_value = {
            "content": [],
            "stop_reason": "max_tokens",
        }
        fake_response.raise_for_status.return_value = None
        fake_httpx = MagicMock()
        fake_httpx.post.return_value = fake_response
        llm = Anthropic(api_key="sk-ant-abc")
        llm._httpx = fake_httpx  # type: ignore[assignment]
        with pytest.raises(RuntimeError, match=r"no text content"):
            llm.complete("Hi")


class TestProtocolConformance:
    """All three real adapters satisfy the LLM Protocol."""

    def test_all_adapters_implement_protocol(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from nom.llm import LLM

        monkeypatch.setenv("OPENAI_API_KEY", "x")
        monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
        for llm in (Ollama(), OpenAI(), Anthropic()):
            assert isinstance(llm, LLM)
            assert isinstance(llm.name, str)
            assert callable(llm.complete)


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

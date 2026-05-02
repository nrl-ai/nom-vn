"""Unit tests for nom.translate.llm.LLMTranslator."""

from __future__ import annotations

import json
import unicodedata
from typing import Any

import pytest

from nom.translate import LLMTranslator


class _FakeLLM:
    """In-memory LLM that returns canned JSON. Mirrors the nom.llm.LLM
    Protocol's complete() signature."""

    name = "fake"

    def __init__(self, response: str) -> None:
        self.response = response
        self.last_prompt: str | None = None
        self.last_schema: dict[str, Any] | None = None
        self.last_max_tokens: int | None = None

    def complete(
        self,
        prompt: str,
        *,
        schema: dict[str, Any] | None = None,
        max_tokens: int = 2048,
    ) -> str:
        self.last_prompt = prompt
        self.last_schema = schema
        self.last_max_tokens = max_tokens
        return self.response


def test_translates_via_json_response() -> None:
    llm = _FakeLLM(json.dumps({"translation": "Xin chào"}))
    tx = LLMTranslator(llm=llm, source_lang="en", target_lang="vi")
    assert tx.translate("Hello") == "Xin chào"


def test_falls_back_to_raw_when_json_invalid() -> None:
    llm = _FakeLLM("Xin chào, this is not JSON")
    tx = LLMTranslator(llm=llm, source_lang="en", target_lang="vi")
    assert tx.translate("Hello") == "Xin chào, this is not JSON"


def test_falls_back_to_raw_when_translation_field_missing() -> None:
    llm = _FakeLLM(json.dumps({"other_field": "value"}))
    tx = LLMTranslator(llm=llm, source_lang="en", target_lang="vi")
    assert tx.translate("Hello") == json.dumps({"other_field": "value"})


def test_normalizes_to_nfc() -> None:
    nfd_text = unicodedata.normalize("NFD", "Việt Nam")
    assert nfd_text != "Việt Nam"
    llm = _FakeLLM(json.dumps({"translation": nfd_text}))
    tx = LLMTranslator(llm=llm, source_lang="en", target_lang="vi")
    out = tx.translate("Vietnam")
    assert unicodedata.normalize("NFC", out) == out
    assert out == "Việt Nam"


def test_passes_schema_for_structured_output() -> None:
    llm = _FakeLLM(json.dumps({"translation": "Xin chào"}))
    tx = LLMTranslator(llm=llm, source_lang="en", target_lang="vi")
    tx.translate("Hello")
    assert llm.last_schema is not None
    assert llm.last_schema["type"] == "object"
    assert "translation" in llm.last_schema["required"]


def test_includes_source_language_name_in_prompt() -> None:
    llm = _FakeLLM(json.dumps({"translation": "Hello"}))
    tx = LLMTranslator(llm=llm, source_lang="vi", target_lang="en")
    tx.translate("Xin chào")
    assert llm.last_prompt is not None
    assert "Vietnamese" in llm.last_prompt
    assert "English" in llm.last_prompt


def test_includes_hint_block_when_provided() -> None:
    llm = _FakeLLM(json.dumps({"translation": "X"}))
    tx = LLMTranslator(llm=llm, source_lang="en", target_lang="vi")
    tx.translate("Hello", hint="legal contract preamble")
    assert llm.last_prompt is not None
    assert "legal contract preamble" in llm.last_prompt


def test_omits_hint_block_when_none() -> None:
    llm = _FakeLLM(json.dumps({"translation": "X"}))
    tx = LLMTranslator(llm=llm, source_lang="en", target_lang="vi")
    tx.translate("Hello")
    assert llm.last_prompt is not None
    assert "Context hint" not in llm.last_prompt


def test_empty_input_short_circuits() -> None:
    llm = _FakeLLM("never called")
    tx = LLMTranslator(llm=llm, source_lang="en", target_lang="vi")
    assert tx.translate("") == ""
    assert tx.translate("   \n  ") == "   \n  "
    assert llm.last_prompt is None


def test_rejects_unsupported_language_pair() -> None:
    llm = _FakeLLM("X")
    with pytest.raises(ValueError, match="unsupported language pair"):
        LLMTranslator(llm=llm, source_lang="ja", target_lang="vi")


def test_rejects_same_source_and_target() -> None:
    llm = _FakeLLM("X")
    with pytest.raises(ValueError, match="must differ"):
        LLMTranslator(llm=llm, source_lang="vi", target_lang="vi")


def test_runtime_checkable_protocol() -> None:
    """Translator is a runtime_checkable Protocol — useful for tests
    that need to assert backends conform without a hard isinstance
    against a concrete class."""
    from nom.translate import Translator

    llm = _FakeLLM(json.dumps({"translation": "X"}))
    tx = LLMTranslator(llm=llm, source_lang="en", target_lang="vi")
    assert isinstance(tx, Translator)

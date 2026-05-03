"""Unit tests for nom.stt.whisper.

Smoke tests on the wrapper contract: Protocol satisfaction, dataclass
shapes, the lazy-import error surface. Real audio inference is gated
behind transformers + torch + librosa + a 1.5 GB model download —
that's the integration tier and lives outside this file.
"""

from __future__ import annotations

import pytest

from nom.stt import (
    PhoWhisperSTT,
    SpeechToText,
    TranscriptionResult,
    TranscriptionSegment,
    WhisperSTT,
)


def test_protocol_satisfaction() -> None:
    assert isinstance(PhoWhisperSTT(), SpeechToText)
    assert isinstance(WhisperSTT(), SpeechToText)


def test_default_model_ids() -> None:
    """Default model IDs match the survey's top picks; flag drift if either
    of these change unexpectedly."""
    assert PhoWhisperSTT().model_id == "vinai/PhoWhisper-large"
    assert WhisperSTT().model_id == "openai/whisper-large-v3"


def test_phowhisper_name() -> None:
    assert PhoWhisperSTT().name == "phowhisper-large"


def test_whisper_name() -> None:
    assert WhisperSTT().name == "whisper-large-v3"


def test_transcription_segment_is_frozen() -> None:
    seg = TranscriptionSegment(start=0.0, end=1.5, text="xin chào")
    with pytest.raises((AttributeError, Exception)):
        seg.text = "mutated"  # type: ignore[misc]


def test_transcription_result_is_frozen() -> None:
    res = TranscriptionResult(text="abc", model="phowhisper", language="vi")
    with pytest.raises((AttributeError, Exception)):
        res.text = "mutated"  # type: ignore[misc]


def test_pipeline_lazy_load_raises_when_deps_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    """Force the lazy-import branch to fail and verify the wrapper raises
    a clear ImportError mentioning the install hint."""
    import builtins

    real_import = builtins.__import__

    def fake_import(name: str, *args: object, **kwargs: object) -> object:
        if name == "transformers":
            raise ImportError("synthetic — transformers not installed")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    clf = PhoWhisperSTT()
    with pytest.raises(ImportError, match="transformers"):
        clf.transcribe(b"\x00" * 100)

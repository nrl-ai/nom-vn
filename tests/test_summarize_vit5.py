"""Unit tests for nom.summarize.vit5 — wrapper contract only.

Real ViT5 forward needs transformers + torch + a 3.5 GB checkpoint
download. That belongs to the integration tier, not unit tests.
"""

from __future__ import annotations

import pytest

from nom.summarize import Summarizer, SummaryResult, ViT5Summarizer


def test_protocol_satisfaction() -> None:
    assert isinstance(ViT5Summarizer(), Summarizer)


def test_default_model_id_drift_check() -> None:
    """Default model id matches the survey's pick — flag drift if anyone
    reaches in to swap to a non-VN-tuned base."""
    assert ViT5Summarizer().model_id == "VietAI/vit5-large-vietnews-summarization"


def test_summary_result_is_frozen() -> None:
    r = SummaryResult(text="x", model="vit5", n_chars_in=10, n_chars_out=2)
    with pytest.raises((AttributeError, Exception)):
        r.text = "mutated"  # type: ignore[misc]


def test_lazy_import_raises_with_install_hint(monkeypatch: pytest.MonkeyPatch) -> None:
    import builtins

    real_import = builtins.__import__

    def fake_import(name: str, *args: object, **kwargs: object) -> object:
        if name == "transformers":
            raise ImportError("synthetic — not installed")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    s = ViT5Summarizer()
    with pytest.raises(ImportError, match="transformers"):
        s.summarize("Some Vietnamese text…")

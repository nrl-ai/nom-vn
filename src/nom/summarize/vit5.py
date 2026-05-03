"""ViT5 wrapper — public news-summarization SOTA on Vietnamese.

VietAI's ViT5-base / ViT5-large reach ROUGE-1 63.4 on vietnews — the
strongest published number for VN news summarization without an LLM.
Encoder-decoder, 1 024-token input cap (so legal contracts that exceed
this need truncation or the LLM fallback in Tier 3).

Lazy-loads transformers + torch on first ``summarize`` call. The model
is decoder-prompted (``vietnews:``) so the Apache pipeline's
``"summarization"`` task wires up correctly.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

__all__ = ["Summarizer", "SummaryResult", "ViT5Summarizer"]


@dataclass(frozen=True, slots=True)
class SummaryResult:
    """One summarization output. ``register`` records the prompt
    prefix that was applied (or ``None`` if none) — useful for
    distinguishing register-conditional outputs in audits."""

    text: str
    model: str
    n_chars_in: int
    n_chars_out: int
    register: str | None = None


@runtime_checkable
class Summarizer(Protocol):
    """Protocol seam for any VN summarization engine.

    ``register`` is one of ``"news"`` / ``"legal"`` / ``"dialogue"`` —
    impls that don't condition on register can ignore it; the OSS
    default treats it as a prompt-prefix hint.
    """

    name: str

    def summarize(
        self,
        text: str,
        *,
        register: str | None = None,
        max_length: int = 256,
        min_length: int = 32,
    ) -> SummaryResult: ...


# Register prefixes. ViT5-large fine-tuned on `vietnews` expects the
# decoder prompt ``vietnews:`` — extending the prefix scheme to other
# registers is the bridge before per-register LoRAs land.
_REGISTER_PREFIX: dict[str, str] = {
    "news": "vietnews:",
    "legal": "tóm tắt hợp đồng:",
    "dialogue": "tóm tắt hội thoại:",
}


@dataclass
class ViT5Summarizer:
    """ViT5-large default; override ``model_id`` for ``vit5-base``.

    ``register`` argument to :meth:`summarize` injects a decoder prompt
    prefix matching the register; without it the model gets a bare
    ``"vietnews:"`` (the prefix it was fine-tuned with), which is the
    safest default for general news prose.
    """

    model_id: str = "VietAI/vit5-large-vietnews-summarization"
    device: str | None = None
    name: str = "vit5-large"
    _pipeline: Any = field(default=None, init=False, repr=False)

    def _ensure_loaded(self) -> Any:
        if self._pipeline is not None:
            return self._pipeline
        try:
            from transformers import pipeline
        except ImportError as exc:
            raise ImportError(
                "ViT5Summarizer requires transformers + torch. "
                "Install with: pip install 'transformers>=4.45' 'torch>=2.0'"
            ) from exc

        device = self.device
        if device is None:
            try:
                import torch

                if torch.cuda.is_available():
                    device = "cuda"
                elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
                    device = "mps"
                else:
                    device = "cpu"
            except ImportError:
                device = "cpu"

        self._pipeline = pipeline("summarization", model=self.model_id, device=device)
        return self._pipeline

    def summarize(
        self,
        text: str,
        *,
        register: str | None = None,
        max_length: int = 256,
        min_length: int = 32,
    ) -> SummaryResult:
        from nom.text import normalize

        clean = normalize(text)
        prefix = _REGISTER_PREFIX.get(register or "news", "vietnews:")
        prompt = f"{prefix} {clean}"

        pipe = self._ensure_loaded()
        result = pipe(
            prompt,
            max_length=max_length,
            min_length=min_length,
            do_sample=False,
            truncation=True,
        )
        out_text = ""
        if result and isinstance(result, list):
            out_text = str(result[0].get("summary_text", "")).strip()
        return SummaryResult(
            text=normalize(out_text),
            model=self.model_id,
            n_chars_in=len(clean),
            n_chars_out=len(out_text),
            register=register,
        )

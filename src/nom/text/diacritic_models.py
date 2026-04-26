"""Off-the-shelf VN diacritic-restoration model adapters.

These adapters wrap public Hugging Face models behind a simple
``predict(text) -> str`` API. They're opt-in: lazy-import the heavy ML
deps so ``import nom.text`` stays cheap, and only construct on demand.

Reference (measured 2026-04-26 on the same 55-sentence corpus the rest of
this package benches against):

    Backend                                                   Word acc   p50 lat
    Rule (built-in, no deps)                                   41.06%   <1 ms
    Local LLM (gemma3:4b via Ollama)                           87.90%   1.10 s
    Local LLM (gemma4:e4b via Ollama)                          93.18%   1.33 s
    Cloud LLM (gpt-4o-mini via OpenAI)                         95.37%   1.27 s
    Toshiiiii1/Vietnamese_diacritics_restoration_5th (T5 200M) 97.81%   148  ms

The Toshiiiii1 T5 fine-tune wins on accuracy AND latency vs every other
option short of "no model at all". Apache 2.0, safetensors. We don't
bundle it — it's a 1 GB on-disk download — but the adapter makes
opting in a one-liner.

Caveat: the canonical T5 slow-tokenizer path is broken under
``transformers>=5.6`` (Unigram vocab regression). Install
``transformers<5`` until upstream ships a fix. The adapter raises
ImportError early with that hint.

Example::

    from nom.text import fix_diacritics
    from nom.text.diacritic_models import HFDiacriticModel

    restorer = HFDiacriticModel(
        "Toshiiiii1/Vietnamese_diacritics_restoration_5th"
    )
    out = fix_diacritics("Hop dong nay duoc lap ngay 14 thang 3", model=restorer)
"""

from __future__ import annotations

from typing import Any


class HFDiacriticModel:
    """Adapter for an HF seq2seq diacritic-restoration model.

    Args:
        model_id: HuggingFace repo id. Default: the 2026-04-26 winner,
            ``Toshiiiii1/Vietnamese_diacritics_restoration_5th`` (Apache 2.0,
            safetensors, 200 M T5).
        device: ``cpu``, ``cuda``, or ``auto`` (picks CUDA when available,
            else CPU). MPS not auto-selected because t5-v1_1's BFloat16
            kernel is patchy on MPS in current PyTorch builds.
        max_input_tokens: Truncate inputs to this length. Default 512
            matches the model's training cap.
        num_beams: Decoding beams. Default 1 (greedy) — measured fastest
            with no quality drop on the 55-sent corpus.

    Raises:
        ImportError: if ``transformers`` or ``torch`` aren't installed,
            or if the installed ``transformers`` is the broken 5.6+
            regression on slow T5 tokenizers. Both errors include
            install hints.
    """

    name = "hf-diacritic"

    def __init__(
        self,
        model_id: str = "Toshiiiii1/Vietnamese_diacritics_restoration_5th",
        *,
        device: str = "auto",
        max_input_tokens: int = 512,
        num_beams: int = 1,
    ) -> None:
        try:
            import torch
            import transformers
        except ImportError as exc:
            raise ImportError(
                "nom.text.diacritic_models requires torch + transformers. "
                'Install with: pip install "nom-vn[diacritic-hf]" '
                'OR: pip install "transformers<5" torch'
            ) from exc

        # transformers>=5.6 broke slow T5 tokenizer init for some unigram
        # vocabs (Toshiiiii1 included). Detect early so the user gets a
        # crisp install hint instead of a deep-stack TypeError.
        try:
            major = int(transformers.__version__.split(".", 1)[0])
        except (AttributeError, ValueError):
            major = 0
        if major >= 5:
            raise ImportError(
                "transformers>=5 has a regression that breaks slow T5 "
                "tokenizers used by current VN diacritic models. "
                'Install: pip install "transformers<5" '
                "(see docs/benchmark.md for details)."
            )

        self.model_id = model_id
        self.max_input_tokens = max_input_tokens
        self.num_beams = num_beams
        if device == "auto":
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
        else:
            self.device = device
        self._torch = torch
        self._tok: Any = None
        self._model: Any = None

    def _ensure_loaded(self) -> None:
        if self._model is not None:
            return
        from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

        self._tok = AutoTokenizer.from_pretrained(self.model_id)
        self._model = AutoModelForSeq2SeqLM.from_pretrained(self.model_id).to(self.device).eval()

    def predict(self, text: str) -> str:
        """Restore diacritics on ``text``. Pure transformation; no caching."""
        self._ensure_loaded()
        if not text.strip():
            return text
        inputs = self._tok(
            text,
            return_tensors="pt",
            max_length=self.max_input_tokens,
            truncation=True,
        ).to(self.device)
        with self._torch.no_grad():
            out = self._model.generate(
                **inputs,
                max_length=self.max_input_tokens,
                num_beams=self.num_beams,
            )
        return str(self._tok.decode(out[0], skip_special_tokens=True))

    # Aliasing for the LLM-style call site so users can drop this in
    # via ``fix_diacritics(text, model=HFDiacriticModel(...))``.
    def __call__(self, text: str) -> str:
        return self.predict(text)


__all__ = ["HFDiacriticModel"]

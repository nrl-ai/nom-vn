"""Off-the-shelf VN diacritic-restoration model adapters.

These adapters wrap public Hugging Face models behind a simple
``predict(text) -> str`` API. They're opt-in: lazy-import the heavy ML
deps so ``import nom.text`` stays cheap, and only construct on demand.

Default model: ``nrl-ai/vn-diacritic-vit5-base`` — our ViT5-base fine-tune,
Apache 2.0, safetensors, 220 M params. Wins on register-balanced eval
against the public landscape (Toshiiiii1, qthuan2604, gpt-4o-mini, ...);
the spell-correction sibling under the same `nrl-ai/*` org is a strict
superset that also fixes letter-level typos and OCR errors.

Reference numbers across 4 registers (measured 2026-04-29):

    Model                                              avg word acc   ms/sent
    nrl-ai/vn-diacritic-vit5-base (ViT5-base 220 M)         97.4 %   ~150 ms
    nrl-ai/vn-diacritic-small (BARTpho-syllable 115 M)      93.6 %   ~50  ms
    Toshiiiii1/Vietnamese_diacritics_restoration_5th        93.4 %   ~150 ms
    Local LLM (gemma3:4b via Ollama)                        87.90 %  ~1.1 s

For the fast tier, pass ``model_id="nrl-ai/vn-diacritic-small"`` —
~3x lower latency, ~3-4 pp word-acc trade-off.

Caveat: the canonical T5 slow-tokenizer path is broken under
``transformers>=5.6`` (Unigram vocab regression). Install
``transformers<5`` until upstream ships a fix. The adapter raises
ImportError early with that hint.

Example::

    from nom.text import fix_diacritics
    from nom.text.diacritic_models import HFDiacriticModel

    restorer = HFDiacriticModel()  # nrl-ai/vn-diacritic-base by default
    out = fix_diacritics("Hop dong nay duoc lap ngay 14 thang 3", model=restorer)

    # Or explicitly pick the spell-correction variant (broader: also fixes
    # letter-level typos / OCR errors / Telex slips):
    speller = HFDiacriticModel(model_id="nrl-ai/vn-spell-correction-base")
    speller("Toi yu Vit Nam, dat nuoc tuyet voi")
    # 'Tôi yêu Việt Nam, đất nước tuyệt vời'
"""

from __future__ import annotations

from typing import Any


class HFDiacriticModel:
    """Adapter for an HF seq2seq diacritic-restoration model.

    Args:
        model_id: HuggingFace repo id. Default:
            ``nrl-ai/vn-diacritic-vit5-base`` (Apache 2.0, safetensors,
            ViT5-base 220 M). Use ``nrl-ai/vn-diacritic-small`` for the
            lower-latency tier or ``nrl-ai/vn-spell-correction-base`` for
            the typo-tolerant superset.
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
        model_id: str = "nrl-ai/vn-diacritic-vit5-base",
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

        self._tok = AutoTokenizer.from_pretrained(self.model_id)  # type: ignore[no-untyped-call,unused-ignore]
        self._model = (
            AutoModelForSeq2SeqLM.from_pretrained(self.model_id).to(self.device).eval()  # type: ignore[no-untyped-call,unused-ignore]
        )

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

    def predict_batch(self, texts: list[str], *, batch_size: int = 16) -> list[str]:
        """Restore diacritics on a list of sentences using batched inference.

        Padding to the longest sequence per batch (not to ``max_input_tokens``)
        keeps each generate() call as small as the inputs allow. Empty / blank
        sentences are passed through unchanged without hitting the model.

        Args:
            texts: Sentences to restore. Order is preserved in the output.
            batch_size: Sentences per generate() call. Default 16 — fits in
                a 4 GB GPU footprint for typical (≤256-token) inputs. Bump to
                32+ on cards with ≥16 GB free, drop to 4-8 on smaller GPUs
                or for unusually long inputs.

        Returns:
            List of restored sentences, same length and order as ``texts``.

        Notes:
            On a single 3080 16 GB Mobile, batched inference gives ~5-8x
            throughput over calling ``predict`` in a loop on the 300-sentence
            Tatoeba corpus, since CUDA kernel launch overhead dominates the
            per-call cost on short sequences.
        """
        self._ensure_loaded()
        if not texts:
            return []
        out: list[str] = [""] * len(texts)
        # Indices of non-blank inputs we'll actually run through the model.
        live_idx: list[int] = []
        live_texts: list[str] = []
        for i, t in enumerate(texts):
            if not t.strip():
                out[i] = t
            else:
                live_idx.append(i)
                live_texts.append(t)

        for chunk_start in range(0, len(live_texts), batch_size):
            chunk = live_texts[chunk_start : chunk_start + batch_size]
            inputs = self._tok(
                chunk,
                return_tensors="pt",
                max_length=self.max_input_tokens,
                truncation=True,
                padding=True,
            ).to(self.device)
            with self._torch.no_grad():
                gen = self._model.generate(
                    **inputs,
                    max_length=self.max_input_tokens,
                    num_beams=self.num_beams,
                )
            decoded = self._tok.batch_decode(gen, skip_special_tokens=True)
            for j, pred in enumerate(decoded):
                out[live_idx[chunk_start + j]] = str(pred)
        return out

    # Aliasing for the LLM-style call site so users can drop this in
    # via ``fix_diacritics(text, model=HFDiacriticModel(...))``.
    def __call__(self, text: str) -> str:
        return self.predict(text)


__all__ = ["HFDiacriticModel"]

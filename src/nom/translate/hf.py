"""HuggingFace seq2seq translator — MADLAD-400, m2m100, generic enc-dec.

Lazy-imports torch + transformers on first :meth:`translate` call so
``import nom.translate`` stays cheap. Loaded models are cached
process-wide by ``model_id`` so repeated construction across walkers
or pipeline stages reuses the same weights.

Default model picks belong in the bench harness, not this class — the
caller passes ``model_id`` explicitly. Survey of candidates and license
audit lives in
``docs/research/2026-05-02-translation-models-survey.md``.
"""

from __future__ import annotations

import threading
import unicodedata
from typing import Any, cast

from nom.translate.base import Translator

__all__ = ["HFTranslator"]

_LANG_NAMES: dict[str, str] = {
    "en": "English",
    "vi": "Vietnamese",
}
_MODEL_CACHE: dict[str, tuple[Any, Any]] = {}
_CACHE_LOCK = threading.Lock()


class HFTranslator(Translator):
    """Translate via a HuggingFace seq2seq model.

    Auto-detects MADLAD's ``<2vi>`` / ``<2en>`` prefix convention and
    m2m100's ``forced_bos_token_id`` switch. Anything else falls back
    to a plain encode → generate → decode path; the caller is
    responsible for picking a model that translates without prefixes.
    """

    name = "hf"

    def __init__(
        self,
        *,
        model_id: str,
        source_lang: str,
        target_lang: str,
        max_new_tokens: int = 512,
    ) -> None:
        if source_lang not in _LANG_NAMES or target_lang not in _LANG_NAMES:
            raise ValueError(
                f"unsupported language pair: {source_lang}->{target_lang}; "
                f"v0.1 supports {sorted(_LANG_NAMES)}"
            )
        if source_lang == target_lang:
            raise ValueError("source_lang and target_lang must differ")
        self._model_id = model_id
        self.source_lang = source_lang
        self.target_lang = target_lang
        self._max_new_tokens = max_new_tokens
        self._kind = _detect_kind(model_id)

    def translate(self, text: str, *, hint: str | None = None) -> str:
        if not text or not text.strip():
            return text
        tokenizer, model = self._ensure_loaded()

        if self._kind == "madlad":
            prompt = f"<2{self.target_lang}> {text}"
            inputs = tokenizer(prompt, return_tensors="pt")
            output_ids = model.generate(**inputs, max_new_tokens=self._max_new_tokens)
        elif self._kind == "m2m100":
            tokenizer.src_lang = self.source_lang
            inputs = tokenizer(text, return_tensors="pt")
            output_ids = model.generate(
                **inputs,
                forced_bos_token_id=tokenizer.get_lang_id(self.target_lang),
                max_new_tokens=self._max_new_tokens,
            )
        else:
            inputs = tokenizer(text, return_tensors="pt")
            output_ids = model.generate(**inputs, max_new_tokens=self._max_new_tokens)

        decoded = tokenizer.batch_decode(output_ids, skip_special_tokens=True)[0].strip()
        return unicodedata.normalize("NFC", decoded)

    def _ensure_loaded(self) -> tuple[Any, Any]:
        with _CACHE_LOCK:
            cached = _MODEL_CACHE.get(self._model_id)
            if cached is not None:
                return cached
            try:
                from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
            except ImportError as exc:
                raise ImportError(
                    "HFTranslator requires transformers + torch. "
                    "Install with: pip install 'transformers>=4.45' 'torch>=2.0' sentencepiece"
                ) from exc
            tokenizer = cast(Any, AutoTokenizer.from_pretrained(self._model_id))
            model = cast(Any, AutoModelForSeq2SeqLM.from_pretrained(self._model_id))
            _MODEL_CACHE[self._model_id] = (tokenizer, model)
            return tokenizer, model


def _detect_kind(model_id: str) -> str:
    lowered = model_id.lower()
    if "madlad" in lowered:
        return "madlad"
    if "m2m100" in lowered:
        return "m2m100"
    return "generic"

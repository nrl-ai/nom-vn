"""Stateless playground endpoints for the React UI.

The chat app exposes RAG-over-spaces under ``/api/spaces/*``. The
``/api/tools/*`` surface here is independent: each route is a pure
function over text, with no notion of spaces or materials. The UI uses
these to power the multi-task Playground (diacritic restore, tokenize,
normalize, detect, strip, noise) without coupling stateless tools to
the document store.

Heavy backends (HF seq2seq for diacritic restore) are lazy and process-
cached: first call may take ~10-30 s while weights download, subsequent
calls reuse the in-memory model. The chat-LLM path reuses whatever LLM
was passed into ``build_app``.

Each handler returns NFC-normalized strings — see CLAUDE.md NFC rule.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from fastapi import FastAPI

    from nom.llm import LLM


__all__ = ["register_tool_routes"]


# Lazy singleton cache for the HF diacritic model. Keyed by model_id so
# users can A/B base vs small without paying the load cost twice. None
# of these are touched until the first call to /api/tools/diacritic with
# backend=hf.
_HF_CACHE: dict[str, Any] = {}


def _get_hf_model(model_id: str) -> Any:
    """Lazy + memoize a `HFDiacriticModel` per repo id."""
    cached = _HF_CACHE.get(model_id)
    if cached is not None:
        return cached
    from nom.text.diacritic_models import HFDiacriticModel

    model = HFDiacriticModel(model_id=model_id)
    _HF_CACHE[model_id] = model
    return model


def register_tool_routes(app: FastAPI, *, llm: LLM | None = None) -> None:
    """Mount /api/tools/* on ``app``. Idempotent against re-registration."""
    from fastapi import HTTPException

    @app.post("/api/tools/diacritic/restore")
    def restore_diacritics(payload: dict[str, Any]) -> dict[str, Any]:
        """Restore diacritics on Vietnamese text.

        Backends:
        - ``rule`` (default): zero-dep table lookup, ~5 ms.
        - ``hf``: HF seq2seq, optional ``model_id`` (default
          ``nrl-ai/vn-diacritic-vit5-base``). First call may take 10-30 s
          while weights load.
        - ``llm``: defers to the chat LLM (qwen3:8b et al.). Slower, but
          handles register shifts the rule table doesn't cover.
        """
        text = str(payload.get("text", ""))
        backend = str(payload.get("backend", "rule")).lower()
        if not text:
            raise HTTPException(status_code=422, detail="`text` is required")

        from nom.text.normalize import fix_diacritics

        if backend == "rule":
            restored = fix_diacritics(text)
            used = "rule"
            model_id: str | None = None
        elif backend == "hf":
            model_id = str(payload.get("model_id", "nrl-ai/vn-diacritic-vit5-base"))
            try:
                model = _get_hf_model(model_id)
                restored = fix_diacritics(text, model=model)
            except ImportError as exc:
                raise HTTPException(
                    status_code=503,
                    detail=f"HF backend unavailable: {exc}",
                ) from exc
            used = "hf"
        elif backend == "llm":
            if llm is None:
                raise HTTPException(
                    status_code=503,
                    detail="LLM backend unavailable (server started without an LLM)",
                )
            try:
                restored = fix_diacritics(text, llm=llm)
            except Exception as exc:
                cls = type(exc).__name__
                if "HTTPStatusError" in cls or "ConnectError" in cls or "Timeout" in cls:
                    from nom.chat.server import _llm_error_to_503

                    raise _llm_error_to_503(exc) from exc
                raise
            used = "llm"
            model_id = getattr(llm, "name", None)
        else:
            raise HTTPException(
                status_code=422,
                detail=f"unknown backend {backend!r}; expected rule|hf|llm",
            )

        return {
            "restored": restored,
            "input": text,
            "backend": used,
            "model_id": model_id,
        }

    @app.post("/api/tools/diacritic/strip")
    def strip(payload: dict[str, Any]) -> dict[str, Any]:
        """Drop all VN diacritics; returns ASCII approximation."""
        text = str(payload.get("text", ""))
        if not text:
            raise HTTPException(status_code=422, detail="`text` is required")
        from nom.text.normalize import strip_diacritics

        return {"input": text, "stripped": strip_diacritics(text)}

    @app.post("/api/tools/tokenize/word")
    def tokenize_word(payload: dict[str, Any]) -> dict[str, Any]:
        """Word-tokenize — greedy compound merge over the curated table.

        ``fmt=list`` returns ``["Hợp đồng", "số", ...]`` (compound joined
        by space inside one token). ``fmt=text`` returns underscore-joined
        compounds in a single string (for downstream whitespace tokenizers).
        """
        text = str(payload.get("text", ""))
        fmt = str(payload.get("fmt", "list")).lower()
        if not text:
            raise HTTPException(status_code=422, detail="`text` is required")
        if fmt not in ("list", "text"):
            raise HTTPException(status_code=422, detail="`fmt` must be 'list' or 'text'")
        from nom.text.segment import word_tokenize

        result = word_tokenize(text, fmt=fmt)
        if fmt == "list":
            assert isinstance(result, list)
            return {
                "input": text,
                "tokens": result,
                "n_tokens": len(result),
                "n_compounds": sum(1 for t in result if " " in t),
            }
        assert isinstance(result, str)
        return {"input": text, "text": result}

    @app.post("/api/tools/tokenize/sentence")
    def tokenize_sentence(payload: dict[str, Any]) -> dict[str, Any]:
        """Sentence-split on Vietnamese punctuation (., !, ?, …)."""
        text = str(payload.get("text", ""))
        if not text:
            raise HTTPException(status_code=422, detail="`text` is required")
        from nom.text.segment import sent_tokenize

        sents = sent_tokenize(text)
        return {
            "input": text,
            "sentences": sents,
            "n_sentences": len(sents),
        }

    @app.post("/api/tools/text/normalize")
    def normalize_text(payload: dict[str, Any]) -> dict[str, Any]:
        """NFC-normalize and report whether the input was already NFC.

        Returns the per-character codepoint diff for the first 200 chars
        so the UI can render which positions changed (combining-mark
        decomposition is invisible in plaintext but breaks tokenizers).
        """
        text = str(payload.get("text", ""))
        if not text:
            raise HTTPException(status_code=422, detail="`text` is required")
        import unicodedata

        from nom.text.segment import text_normalize as _full_normalize

        nfc = unicodedata.normalize("NFC", text)
        full = _full_normalize(text)
        return {
            "input": text,
            "nfc": nfc,
            "full_normalized": full,
            "is_nfc": text == nfc,
            "n_input_codepoints": len(text),
            "n_nfc_codepoints": len(nfc),
        }

    @app.post("/api/tools/text/detect")
    def detect(payload: dict[str, Any]) -> dict[str, Any]:
        """Heuristic VN detection + diacritic presence check."""
        text = str(payload.get("text", ""))
        if not text:
            raise HTTPException(status_code=422, detail="`text` is required")
        from nom.text.normalize import has_diacritics, is_vietnamese

        has = has_diacritics(text)
        vn = is_vietnamese(text)
        if has:
            reason = "Contains Vietnamese-unique diacritic characters"
        elif vn:
            reason = "Stripped form matches the common-VN-word table"
        else:
            reason = "No VN markers found (ASCII fallback failed)"
        return {
            "input": text,
            "is_vietnamese": vn,
            "has_diacritics": has,
            "reason": reason,
        }

    @app.post("/api/tools/noise/apply")
    def apply_noise(payload: dict[str, Any]) -> dict[str, Any]:
        """Apply a calibrated noise preset to clean Vietnamese text.

        Presets: ``light``, ``heavy``, ``telex_typo``, ``telex_grammar``,
        ``mobile``, ``ocr_realistic``, ``comprehensive``. Each is a pure
        function of (text, preset, seed) — same inputs, same output.
        """
        text = str(payload.get("text", ""))
        preset = str(payload.get("preset", "light")).lower()
        seed = int(payload.get("seed", 42))
        if not text:
            raise HTTPException(status_code=422, detail="`text` is required")
        from nom.text import noise as noise_mod

        presets: dict[str, Any] = {
            "light": noise_mod.light_noise,
            "heavy": noise_mod.heavy_noise,
            "telex_typo": noise_mod.telex_typo_noise,
            "telex_grammar": noise_mod.telex_grammar_noise,
            "mobile": noise_mod.mobile_noise,
            "ocr_realistic": noise_mod.ocr_realistic_noise,
            "comprehensive": noise_mod.comprehensive_noise,
        }
        if preset not in presets:
            raise HTTPException(
                status_code=422,
                detail=f"unknown preset {preset!r}; expected one of {sorted(presets)}",
            )
        gen = noise_mod.NoiseGenerator(presets[preset](), seed=seed)
        return {
            "input": text,
            "noisy": gen.noisify(text),
            "preset": preset,
            "seed": seed,
        }

    @app.get("/api/tools/diacritic/models")
    def list_diacritic_models() -> dict[str, Any]:
        """Curated list of HF diacritic-restoration models the UI offers."""
        return {
            "default": "nrl-ai/vn-diacritic-vit5-base",
            "models": [
                {
                    "id": "nrl-ai/vn-diacritic-vit5-base",
                    "label": "vn-diacritic-base (ViT5-base, 220 M)",
                    "tier": "accuracy",
                    "params_m": 220,
                    "license": "Apache 2.0",
                },
                {
                    "id": "nrl-ai/vn-diacritic-small",
                    "label": "vn-diacritic-small (BARTpho, 115 M)",
                    "tier": "fast",
                    "params_m": 115,
                    "license": "Apache 2.0",
                },
                {
                    "id": "nrl-ai/vn-spell-correction-base",
                    "label": "vn-spell-correction-base (ViT5, 220 M)",
                    "tier": "robust",
                    "params_m": 220,
                    "license": "Apache 2.0",
                },
                {
                    "id": "Toshiiiii1/Vietnamese_diacritics_restoration_5th",
                    "label": "Toshiiiii1 (T5, 200 M)",
                    "tier": "baseline",
                    "params_m": 200,
                    "license": "Apache 2.0",
                },
            ],
            "presets": ["rule", "hf", "llm"],
        }

    @app.get("/api/tools/noise/presets")
    def list_noise_presets() -> dict[str, Any]:
        """Names + one-line descriptions of every noise preset."""
        return {
            "presets": [
                {"id": "light", "label": "Light typing (~5% edit)"},
                {"id": "heavy", "label": "Heavy / mid-quality OCR (~15-20%)"},
                {"id": "telex_typo", "label": "Telex / VNI surface errors"},
                {"id": "telex_grammar", "label": "Telex keystroke errors"},
                {"id": "mobile", "label": "Mobile thumbs + slang"},
                {"id": "ocr_realistic", "label": "Scanned-document OCR"},
                {"id": "comprehensive", "label": "Mix of every dimension"},
            ],
        }

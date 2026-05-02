"""Stateless playground endpoints for the React UI.

The chat app exposes RAG-over-spaces under ``/api/spaces/*``. The
``/api/tools/*`` surface here is independent: each route is a pure
function over text, with no notion of spaces or materials. The UI uses
these to power the multi-task Playground (diacritic restore, tokenize,
normalize, detect, NER, sentiment, language detection) without
coupling stateless tools to the document store.

Heavy backends (HF seq2seq for diacritic restore) are lazy and process-
cached: first call may take ~10-30 s while weights download, subsequent
calls reuse the in-memory model. The chat-LLM path reuses whatever LLM
was passed into ``build_app``.

Each handler returns NFC-normalized strings (text routes); the file
upload route returns the translated ``.docx`` as raw bytes.
"""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING, Annotated, Any

# Module-level import: FastAPI needs runtime access to ``UploadFile``
# / ``File`` / ``Form`` to wire multipart dependency injection on the
# file-upload route. With ``from __future__ import annotations`` these
# would be unresolvable string forward refs unless they live in module
# globals.
with contextlib.suppress(ImportError):  # fastapi is a [chat] extra
    from fastapi import File, Form, UploadFile

if TYPE_CHECKING:
    from fastapi import FastAPI

    from nom.llm import LLM


__all__ = ["register_tool_routes"]


# Lazy singleton cache for the HF diacritic model. Keyed by model_id so
# users can A/B base vs small without paying the load cost twice. None
# of these are touched until the first call to /api/tools/diacritic with
# backend=hf.
_HF_CACHE: dict[str, Any] = {}


_OOXML_DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
_OOXML_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
_OOXML_PPTX = "application/vnd.openxmlformats-officedocument.presentationml.presentation"


def _media_type_for_suffix(suffix: str) -> str:
    """MIME type for the file-translation download response."""
    return {
        ".docx": _OOXML_DOCX,
        ".xlsx": _OOXML_XLSX,
        ".pptx": _OOXML_PPTX,
        ".txt": "text/plain; charset=utf-8",
        ".md": "text/markdown; charset=utf-8",
        ".markdown": "text/markdown; charset=utf-8",
        ".rst": "text/x-rst; charset=utf-8",
    }.get(suffix.lower(), "application/octet-stream")


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
    from fastapi.responses import Response

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

    # NLP analysis: NER + sentiment + language detection. These three
    # cover the canonical "what's in this text" primitives every UI
    # asks for. Power users compose them via nom.agents (one tool
    # per modality).
    @app.post("/api/tools/nlp/ner")
    def nlp_ner(payload: dict[str, Any]) -> dict[str, Any]:
        text = str(payload.get("text", ""))
        if not text:
            raise HTTPException(status_code=422, detail="`text` is required")
        from nom.nlp import RegexNERModel

        spans = RegexNERModel().tag(text)
        return {
            "input": text,
            "spans": [
                {
                    "start": s.start,
                    "end": s.end,
                    "label": s.label,
                    "text": s.text,
                    "confidence": s.confidence,
                }
                for s in spans
            ],
        }

    @app.post("/api/tools/nlp/sentiment")
    def nlp_sentiment(payload: dict[str, Any]) -> dict[str, Any]:
        text = str(payload.get("text", ""))
        if not text:
            raise HTTPException(status_code=422, detail="`text` is required")
        from nom.nlp import LexiconSentimentModel

        result = LexiconSentimentModel().predict(text)
        return {"input": text, "label": result.label.value, "score": result.score}

    @app.post("/api/tools/nlp/language")
    def nlp_language(payload: dict[str, Any]) -> dict[str, Any]:
        text = str(payload.get("text", ""))
        if not text:
            raise HTTPException(status_code=422, detail="`text` is required")
        from nom.nlp import detect_language

        d = detect_language(text)
        return {"input": text, "language": d.code, "confidence": d.confidence}

    @app.post("/api/tools/translate")
    def translate(payload: dict[str, Any]) -> dict[str, Any]:
        """Translate a single string between EN and VN.

        Backends:

        - ``llm`` (default): defers to the chat LLM via
          :class:`~nom.translate.LLMTranslator`. Already in the stack;
          no extra download. Quality scales with model size.
        - ``hf``: HF seq2seq via :class:`~nom.translate.hf.HFTranslator`.
          ``model_id`` defaults to ``google/madlad400-3b-mt`` (Apache,
          safetensors, MT specialist). First call may take 30-60 s
          while weights load.
        """
        text = str(payload.get("text", ""))
        source = str(payload.get("source", "vi")).lower()
        target = str(payload.get("target", "en")).lower()
        backend = str(payload.get("backend", "llm")).lower()
        if not text:
            raise HTTPException(status_code=422, detail="`text` is required")
        if source == target:
            raise HTTPException(
                status_code=422,
                detail="`source` and `target` must differ",
            )

        from nom.translate import LLMTranslator, Translator

        translator: Translator
        used_model: str | None
        if backend == "llm":
            if llm is None:
                raise HTTPException(
                    status_code=503,
                    detail="LLM backend unavailable (server started without an LLM)",
                )
            try:
                translator = LLMTranslator(
                    llm=llm,
                    source_lang=source,
                    target_lang=target,
                )
            except ValueError as exc:
                raise HTTPException(status_code=422, detail=str(exc)) from exc
            used_model = getattr(llm, "name", None)
        elif backend == "hf":
            from nom.translate.hf import HFTranslator

            model_id = str(payload.get("model_id", "google/madlad400-3b-mt"))
            try:
                translator = HFTranslator(
                    model_id=model_id,
                    source_lang=source,
                    target_lang=target,
                )
            except ImportError as exc:
                raise HTTPException(
                    status_code=503,
                    detail=f"HF backend unavailable: {exc}",
                ) from exc
            except ValueError as exc:
                raise HTTPException(status_code=422, detail=str(exc)) from exc
            used_model = model_id
        else:
            raise HTTPException(
                status_code=422,
                detail=f"unknown backend {backend!r}; expected llm|hf",
            )

        try:
            translated = translator.translate(text)
        except Exception as exc:
            cls = type(exc).__name__
            if "HTTPStatusError" in cls or "ConnectError" in cls or "Timeout" in cls:
                from nom.chat.server import _llm_error_to_503

                raise _llm_error_to_503(exc) from exc
            raise

        return {
            "input": text,
            "translation": translated,
            "source": source,
            "target": target,
            "backend": backend,
            "model_id": used_model,
        }

    @app.post("/api/tools/translate/file")
    async def translate_file_upload(
        file: Annotated[UploadFile, File()],
        source: Annotated[str, Form()] = "vi",
        target: Annotated[str, Form()] = "en",
        backend: Annotated[str, Form()] = "llm",
        model_id: Annotated[str | None, Form()] = None,
    ) -> Response:
        """Translate an uploaded document; respond with the translated
        file plus per-unit stats in the ``X-Translation-Stats`` header.

        Multipart form fields:

        - ``file`` — source document. Supported: ``.docx``, ``.xlsx``,
          ``.pptx``, ``.txt``, ``.md``, ``.markdown``, ``.rst``.
        - ``source`` / ``target`` — language codes ``en``|``vi``. Must differ.
        - ``backend`` — ``llm`` (default, uses the server's chat LLM) or
          ``hf`` (loads an HF seq2seq specialist).
        - ``model_id`` — optional HF model id when ``backend=hf``;
          defaults to ``google/madlad400-3b-mt``.
        """
        import json
        import tempfile
        from pathlib import Path

        from nom.translate.formats import SUPPORTED_FORMATS

        filename = file.filename or "uploaded.docx"
        suffix = Path(filename).suffix.lower()
        if suffix not in SUPPORTED_FORMATS:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"unsupported source format {suffix!r}; supported: {sorted(SUPPORTED_FORMATS)}"
                ),
            )
        source_lc = source.lower()
        target_lc = target.lower()
        if source_lc == target_lc:
            raise HTTPException(
                status_code=422,
                detail="`source` and `target` must differ",
            )

        from nom.translate import LLMTranslator, Translator

        translator: Translator
        used_model: str | None
        if backend == "llm":
            if llm is None:
                raise HTTPException(
                    status_code=503,
                    detail="LLM backend unavailable (server started without an LLM)",
                )
            try:
                translator = LLMTranslator(
                    llm=llm,
                    source_lang=source_lc,
                    target_lang=target_lc,
                )
            except ValueError as exc:
                raise HTTPException(status_code=422, detail=str(exc)) from exc
            used_model = getattr(llm, "name", None)
        elif backend == "hf":
            from nom.translate.hf import HFTranslator

            resolved_model = model_id or "google/madlad400-3b-mt"
            try:
                translator = HFTranslator(
                    model_id=resolved_model,
                    source_lang=source_lc,
                    target_lang=target_lc,
                )
            except ImportError as exc:
                raise HTTPException(
                    status_code=503,
                    detail=f"HF backend unavailable: {exc}",
                ) from exc
            except ValueError as exc:
                raise HTTPException(status_code=422, detail=str(exc)) from exc
            used_model = resolved_model
        else:
            raise HTTPException(
                status_code=422,
                detail=f"unknown backend {backend!r}; expected llm|hf",
            )

        contents = await file.read()
        with tempfile.TemporaryDirectory() as td:
            src_path = Path(td) / f"source{suffix}"
            dst_path = Path(td) / f"translated{suffix}"
            src_path.write_bytes(contents)

            from nom.translate.formats import translate_file as _translate_file

            try:
                stats = _translate_file(src_path, dst_path, translator)
            except Exception as exc:
                cls = type(exc).__name__
                if "HTTPStatusError" in cls or "ConnectError" in cls or "Timeout" in cls:
                    from nom.chat.server import _llm_error_to_503

                    raise _llm_error_to_503(exc) from exc
                raise HTTPException(status_code=500, detail=str(exc)) from exc

            output_bytes = dst_path.read_bytes()

        stem = filename.rsplit(".", 1)[0]
        out_filename = f"{stem}.{target_lc}{suffix}"

        # Stats fields differ by format (paragraphs_* for docx/pptx/text,
        # cells_* for xlsx). Normalize to "units_*" for the JSON header.
        units_translated = getattr(stats, "paragraphs_translated", None)
        if units_translated is None:
            units_translated = getattr(stats, "cells_translated", 0)
        units_skipped = getattr(stats, "paragraphs_skipped", None)
        if units_skipped is None:
            units_skipped = getattr(stats, "cells_skipped", 0)
        units_failed = getattr(stats, "paragraphs_failed", None)
        if units_failed is None:
            units_failed = getattr(stats, "cells_failed", 0)

        stats_json = json.dumps(
            {
                "units_translated": units_translated,
                "units_skipped": units_skipped,
                "units_failed": units_failed,
                "paragraphs_translated": units_translated,
                "paragraphs_skipped": units_skipped,
                "paragraphs_failed": units_failed,
                "chars_in": stats.chars_in,
                "chars_out": stats.chars_out,
                "source": source_lc,
                "target": target_lc,
                "backend": backend,
                "model_id": used_model,
                "format": suffix.lstrip("."),
            }
        )

        return Response(
            content=output_bytes,
            media_type=_media_type_for_suffix(suffix),
            headers={
                "Content-Disposition": f'attachment; filename="{out_filename}"',
                "X-Translation-Stats": stats_json,
            },
        )

    @app.post("/api/tools/convert/file")
    async def convert_file_upload(
        file: Annotated[UploadFile, File()],
        ocr_language: Annotated[str, Form()] = "vie+eng",
    ) -> Response:
        """Convert an uploaded PDF or image to ``.docx``; respond with the
        converted file plus per-page stats in ``X-Convert-Stats``.

        Supported inputs: ``.pdf``, ``.png``, ``.jpg``, ``.jpeg``, ``.tif``,
        ``.tiff``, ``.bmp``, ``.webp``. PDF pages with a usable text layer
        are extracted directly; pages without are rendered and OCR'd via
        Tesseract using ``ocr_language`` (default ``vie+eng``).
        """
        import json
        import tempfile
        from pathlib import Path

        from nom.convert import SUPPORTED_INPUTS, convert_to_docx

        filename = file.filename or "upload.pdf"
        suffix = Path(filename).suffix.lower()
        if suffix not in SUPPORTED_INPUTS:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"unsupported source format {suffix!r}; supported: {sorted(SUPPORTED_INPUTS)}"
                ),
            )

        contents = await file.read()
        with tempfile.TemporaryDirectory() as td:
            src_path = Path(td) / f"source{suffix}"
            dst_path = Path(td) / "converted.docx"
            src_path.write_bytes(contents)

            try:
                stats = convert_to_docx(src_path, dst_path, ocr_language=ocr_language)
            except ImportError as exc:
                raise HTTPException(
                    status_code=503,
                    detail=f"convert backend unavailable: {exc}",
                ) from exc
            except Exception as exc:
                raise HTTPException(status_code=500, detail=str(exc)) from exc

            output_bytes = dst_path.read_bytes()

        stem = Path(filename).stem
        out_filename = f"{stem}.docx"

        stats_json = json.dumps(
            {
                "n_pages": stats.n_pages,
                "pages_text_extracted": stats.pages_text_extracted,
                "pages_ocred": stats.pages_ocred,
                "chars_out": stats.chars_out,
                "ocr_language": stats.ocr_language,
            }
        )

        return Response(
            content=output_bytes,
            media_type=("application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
            headers={
                "Content-Disposition": f'attachment; filename="{out_filename}"',
                "X-Convert-Stats": stats_json,
            },
        )

    @app.get("/api/tools/translate/models")
    def list_translate_models() -> dict[str, Any]:
        """Curated translation backends + the HF specialist models the
        UI offers. ``llm`` is always available when the server has a
        chat LLM configured."""
        return {
            "default_backend": "llm",
            "directions": ["en2vi", "vi2en"],
            "backends": [
                {
                    "id": "llm",
                    "label": "Chat LLM (Qwen3 / Gemma / Claude / GPT-4)",
                    "tier": "general",
                    "license": "depends on backing model",
                    "notes": "Already loaded — no extra download.",
                },
                {
                    "id": "hf",
                    "label": "HF seq2seq specialist",
                    "tier": "specialist",
                    "license": "varies — see model_id",
                    "notes": "Lazy-downloads on first call. Default: MADLAD-3B (Apache).",
                },
            ],
            "hf_models": [
                {
                    "id": "google/madlad400-3b-mt",
                    "label": "MADLAD-400-3B (T5 enc-dec, 3 B)",
                    "tier": "accuracy",
                    "params_m": 3000,
                    "license": "Apache 2.0",
                },
                {
                    "id": "facebook/m2m100_418M",
                    "label": "m2m100-418M (small specialist)",
                    "tier": "fast",
                    "params_m": 418,
                    "license": "MIT",
                },
            ],
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

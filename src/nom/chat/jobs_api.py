"""``/api/jobs/*`` — background-job HTTP surface for long-running tools.

The synchronous ``/api/tools/...`` endpoints stay (clients that want a
blocking call keep working). These job endpoints add a non-blocking
flow for tasks that take seconds-to-minutes — model loads, audio
transcription, large-document operations.

Job kinds shipped today:

- ``translate-file``      — upload → translated DOCX/PDF/...
- ``convert-file``        — PDF / image → DOCX (Tesseract OCR)
- ``stt-transcribe``      — audio → transcript + optional segments
- ``ocr-handwriting``     — handwritten image → transcript
- ``summarize-text``      — VN text → register-aware summary

Endpoints:

- ``POST /api/jobs/<kind>`` — enqueue, returns ``{job_id, status, ...}``
  immediately (HTTP 202).
- ``GET  /api/jobs``        — list all jobs (newest first).
- ``GET  /api/jobs/{id}``   — single snapshot for the polling client.
- ``GET  /api/jobs/{id}/download`` — stream the result file.
- ``POST /api/jobs/{id}/cancel`` — cooperative cancel.
- ``DELETE /api/jobs/{id}`` — drop the snapshot + temp dir.

The work runs on the process-wide :class:`~nom.chat.bgjobs.BgJobRunner`.
"""

from __future__ import annotations

import contextlib
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Any

with contextlib.suppress(ImportError):  # fastapi is a [chat] extra
    from fastapi import File, Form, UploadFile

if TYPE_CHECKING:
    from fastapi import FastAPI

    from nom.llm import LLM


__all__ = ["register_jobs_routes"]


def _job_to_dict(job: Any) -> dict[str, Any]:
    """Stable JSON shape for the UI client."""
    return {
        "id": job.id,
        "kind": job.kind,
        "status": job.status,
        "progress": round(job.progress, 4),
        "message": job.message,
        "created_at": job.created_at,
        "updated_at": job.updated_at,
        "result_filename": job.result_filename,
        "result_meta": job.result_meta,
        "error": job.error,
        # Convenience: clients can compose the URL themselves but giving
        # it here means the polling component doesn't need to know the
        # route shape. Empty until completed.
        "download_url": (f"/api/jobs/{job.id}/download" if job.status == "completed" else None),
    }


def register_jobs_routes(app: FastAPI, *, llm: LLM | None = None) -> None:
    """Mount ``/api/jobs/*`` on ``app``."""
    from fastapi import HTTPException
    from fastapi.responses import FileResponse

    from nom.chat.bgjobs import get_runner

    runner = get_runner()

    @app.get("/api/jobs")
    def list_jobs() -> dict[str, Any]:
        return {"jobs": [_job_to_dict(j) for j in runner.store.list()]}

    @app.get("/api/jobs/{job_id}")
    def get_job(job_id: str) -> dict[str, Any]:
        snap = runner.store.get(job_id)
        if snap is None:
            raise HTTPException(status_code=404, detail="job not found")
        return _job_to_dict(snap)

    @app.post("/api/jobs/{job_id}/cancel")
    def cancel_job(job_id: str) -> dict[str, Any]:
        if not runner.cancel(job_id):
            raise HTTPException(status_code=404, detail="job not found")
        snap = runner.store.get(job_id)
        return _job_to_dict(snap) if snap is not None else {"id": job_id, "status": "cancelled"}

    @app.delete("/api/jobs/{job_id}", status_code=204)
    def delete_job(job_id: str) -> None:
        snap = runner.store.get(job_id)
        if snap is None:
            raise HTTPException(status_code=404, detail="job not found")
        runner.cleanup(job_id)
        runner.store.delete(job_id)

    @app.get("/api/jobs/{job_id}/download")
    def download_result(job_id: str) -> FileResponse:
        snap = runner.store.get(job_id)
        if snap is None:
            raise HTTPException(status_code=404, detail="job not found")
        if snap.status != "completed":
            raise HTTPException(status_code=409, detail=f"job not ready (status={snap.status})")
        if not snap.result_path or not Path(snap.result_path).exists():
            raise HTTPException(status_code=410, detail="result expired")
        return FileResponse(
            path=snap.result_path,
            filename=snap.result_filename or Path(snap.result_path).name,
            media_type=_media_type_for(snap.result_filename or ""),
        )

    @app.post("/api/jobs/translate-file", status_code=202)
    async def start_translate_job(
        file: Annotated[UploadFile, File()],
        source: Annotated[str, Form()] = "vi",
        target: Annotated[str, Form()] = "en",
        backend: Annotated[str, Form()] = "llm",
        model_id: Annotated[str | None, Form()] = None,
    ) -> dict[str, Any]:
        """Enqueue a format-preserving translation job."""
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
            raise HTTPException(status_code=422, detail="`source` and `target` must differ")

        contents = await file.read()
        captured_llm = llm  # capture in closure so the worker thread sees a fixed reference

        def fn(job_dir: Path, reporter: Any) -> tuple[Path, str, dict[str, Any]]:
            from nom.translate import LLMTranslator, Translator
            from nom.translate.formats import translate_file as _translate_file

            translator: Translator
            used_model: str | None
            if backend == "llm":
                if captured_llm is None:
                    raise RuntimeError("LLM backend unavailable — server has no LLM")
                translator = LLMTranslator(
                    llm=captured_llm, source_lang=source_lc, target_lang=target_lc
                )
                used_model = getattr(captured_llm, "name", None)
            elif backend == "hf":
                from nom.translate.hf import HFTranslator

                resolved_model = model_id or "google/madlad400-3b-mt"
                translator = HFTranslator(
                    model_id=resolved_model,
                    source_lang=source_lc,
                    target_lang=target_lc,
                )
                used_model = resolved_model
            else:
                raise ValueError(f"unknown backend {backend!r}; expected llm|hf")

            src_path = job_dir / f"source{suffix}"
            dst_path = job_dir / f"translated{suffix}"
            src_path.write_bytes(contents)

            def on_progress(frac: float) -> None:
                reporter.raise_if_cancelled()
                reporter.update(frac, message=f"{int(frac * 100)}%")

            stats = _translate_file(src_path, dst_path, translator, progress_cb=on_progress)

            stem = filename.rsplit(".", 1)[0]
            out_filename = f"{stem}.{target_lc}{suffix}"

            units_translated = getattr(stats, "paragraphs_translated", None)
            if units_translated is None:
                units_translated = getattr(stats, "cells_translated", 0)
            units_skipped = getattr(stats, "paragraphs_skipped", None)
            if units_skipped is None:
                units_skipped = getattr(stats, "cells_skipped", 0)
            units_failed = getattr(stats, "paragraphs_failed", None)
            if units_failed is None:
                units_failed = getattr(stats, "cells_failed", 0)

            meta = {
                "kind": "translate",
                "source": source_lc,
                "target": target_lc,
                "backend": backend,
                "model_id": used_model,
                "format": suffix.lstrip("."),
                "units_translated": units_translated,
                "units_skipped": units_skipped,
                "units_failed": units_failed,
                "chars_in": stats.chars_in,
                "chars_out": stats.chars_out,
                "input_filename": filename,
            }
            return dst_path, out_filename, meta

        job = runner.submit(
            "translate-file", fn, message=f"queued: {filename} ({source_lc}→{target_lc})"
        )
        return _job_to_dict(job)

    @app.post("/api/jobs/convert-file", status_code=202)
    async def start_convert_job(
        file: Annotated[UploadFile, File()],
        ocr_language: Annotated[str, Form()] = "vie+eng",
    ) -> dict[str, Any]:
        """Enqueue a PDF/image → DOCX conversion job."""
        from nom.convert import SUPPORTED_INPUTS

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

        def fn(job_dir: Path, reporter: Any) -> tuple[Path, str, dict[str, Any]]:
            from nom.convert import convert_to_docx

            src_path = job_dir / f"source{suffix}"
            dst_path = job_dir / "converted.docx"
            src_path.write_bytes(contents)

            # Convert pipeline doesn't expose a progress hook yet — emit
            # coarse 5/40/95 % so the bar at least moves through the
            # three perceived phases (loaded / processing / writing).
            reporter.update(0.05, message="loaded")
            reporter.raise_if_cancelled()

            try:
                stats = convert_to_docx(src_path, dst_path, ocr_language=ocr_language)
            except ImportError as exc:
                raise RuntimeError(f"convert backend unavailable: {exc}") from exc

            reporter.update(0.95, message="writing")

            stem = Path(filename).stem
            out_filename = f"{stem}.docx"
            meta = {
                "kind": "convert",
                "n_pages": stats.n_pages,
                "pages_text_extracted": stats.pages_text_extracted,
                "pages_ocred": stats.pages_ocred,
                "chars_out": stats.chars_out,
                "ocr_language": stats.ocr_language,
                "input_filename": filename,
            }
            return dst_path, out_filename, meta

        job = runner.submit("convert-file", fn, message=f"queued: {filename}")
        return _job_to_dict(job)

    # ------------------------------------------------------------------ #
    # New tool-style jobs — the synchronous /api/tools/<x> endpoints stay
    # for short / interactive calls; these queue equivalents handle the
    # cases where the model load alone is 10-60 s (Whisper, Vintern,
    # ViT5-large). Result is always written as a UTF-8 text file inside
    # the job's working dir so the existing /download path streams it
    # without per-kind plumbing. ``meta`` carries the structured fields
    # the UI used to read off the synchronous response (model id, n_chars,
    # segments, register).
    # ------------------------------------------------------------------ #

    @app.post("/api/jobs/stt-transcribe", status_code=202)
    async def start_stt_job(
        file: Annotated[UploadFile, File()],
        backend: Annotated[str, Form()] = "phowhisper",
        language: Annotated[str | None, Form()] = None,
        return_timestamps: Annotated[bool, Form()] = False,
    ) -> dict[str, Any]:
        """Enqueue an STT transcription. Returns the transcript as a
        ``.txt`` (and writes segment timestamps as JSON in ``meta``)."""
        filename = file.filename or "audio"
        suffix = Path(filename).suffix.lower()
        if suffix not in {".wav", ".mp3", ".flac", ".m4a", ".ogg", ".opus", ".webm"}:
            raise HTTPException(status_code=422, detail=f"unsupported audio format {suffix!r}")
        if backend not in ("phowhisper", "whisper-v3", "whisper"):
            raise HTTPException(
                status_code=422,
                detail=f"unsupported backend {backend!r}; expected 'phowhisper' or 'whisper-v3'",
            )

        contents = await file.read()

        def fn(job_dir: Path, reporter: Any) -> tuple[Path, str, dict[str, Any]]:
            from nom.stt import PhoWhisperSTT, WhisperSTT

            reporter.update(0.05, message="loading model")
            stt: Any = PhoWhisperSTT() if backend == "phowhisper" else WhisperSTT()
            reporter.raise_if_cancelled()
            reporter.update(0.25, message="transcribing")
            try:
                result = stt.transcribe(
                    contents, language=language, return_timestamps=return_timestamps
                )
            except ImportError as exc:
                raise RuntimeError(f"STT backend unavailable: {exc}") from exc
            reporter.update(0.95, message="writing")

            stem = Path(filename).stem or "transcript"
            out_filename = f"{stem}.txt"
            dst_path = job_dir / out_filename
            dst_path.write_text(result.text or "", encoding="utf-8")

            segments_meta: list[dict[str, Any]] | None = None
            if result.segments:
                segments_meta = [
                    {"start": s.start, "end": s.end, "text": s.text} for s in result.segments
                ]

            meta = {
                "kind": "stt",
                "backend": backend,
                "model": result.model,
                "language": result.language,
                "n_chars": len(result.text or ""),
                "segments": segments_meta,
                "input_filename": filename,
            }
            return dst_path, out_filename, meta

        job = runner.submit("stt-transcribe", fn, message=f"queued: {filename} ({backend})")
        return _job_to_dict(job)

    @app.post("/api/jobs/ocr-handwriting", status_code=202)
    async def start_ocr_handwriting_job(
        file: Annotated[UploadFile, File()],
        model_id: Annotated[str | None, Form()] = None,
    ) -> dict[str, Any]:
        """Enqueue a Vintern handwriting-OCR call. Returns the transcript
        as a ``.txt``; ``meta.confidence`` carries the engine's confidence
        when surfaced (Vintern doesn't, so it's null today)."""
        filename = file.filename or "page.png"
        suffix = Path(filename).suffix.lower()
        if suffix not in {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp"}:
            raise HTTPException(status_code=422, detail=f"unsupported image format {suffix!r}")

        contents = await file.read()

        def fn(job_dir: Path, reporter: Any) -> tuple[Path, str, dict[str, Any]]:
            from nom.ocr import VinternHandwritingOcr

            reporter.update(0.05, message="loading model")
            clf = VinternHandwritingOcr(model_id=model_id) if model_id else VinternHandwritingOcr()
            reporter.raise_if_cancelled()
            reporter.update(0.25, message="transcribing")
            try:
                result = clf.transcribe(contents)
            except ImportError as exc:
                raise RuntimeError(f"OCR backend unavailable: {exc}") from exc
            except ValueError as exc:
                # Line-crop guard fires *before* model load, but propagate
                # via the runtime-error path so the user sees the message.
                raise RuntimeError(str(exc)) from exc
            reporter.update(0.95, message="writing")

            stem = Path(filename).stem or "transcript"
            out_filename = f"{stem}.txt"
            dst_path = job_dir / out_filename
            dst_path.write_text(result.text or "", encoding="utf-8")

            meta = {
                "kind": "ocr-handwriting",
                "model": result.model,
                "n_chars": len(result.text or ""),
                "confidence": result.confidence,
                "input_filename": filename,
            }
            return dst_path, out_filename, meta

        job = runner.submit("ocr-handwriting", fn, message=f"queued: {filename}")
        return _job_to_dict(job)

    @app.post("/api/jobs/summarize-text", status_code=202)
    async def start_summarize_job(payload: dict[str, Any]) -> dict[str, Any]:
        """Enqueue a ViT5-large summarization. Body identical to the
        synchronous ``/api/tools/summarize`` endpoint."""
        text = str(payload.get("text", ""))
        register = payload.get("register")
        if register is not None and not isinstance(register, str):
            register = None
        try:
            max_length = int(payload.get("max_length", 256))
            min_length = int(payload.get("min_length", 32))
        except (TypeError, ValueError) as exc:
            raise HTTPException(
                status_code=422,
                detail="`max_length` and `min_length` must be integers",
            ) from exc
        if not text:
            raise HTTPException(status_code=422, detail="`text` is required")

        def fn(job_dir: Path, reporter: Any) -> tuple[Path, str, dict[str, Any]]:
            from nom.summarize import ViT5Summarizer

            reporter.update(0.05, message="loading model")
            summ = ViT5Summarizer()
            reporter.raise_if_cancelled()
            reporter.update(0.25, message="summarizing")
            try:
                result = summ.summarize(
                    text,
                    register=register,
                    max_length=max_length,
                    min_length=min_length,
                )
            except ImportError as exc:
                raise RuntimeError(f"summarize backend unavailable: {exc}") from exc
            reporter.update(0.95, message="writing")

            out_filename = "summary.txt"
            dst_path = job_dir / out_filename
            dst_path.write_text(result.text or "", encoding="utf-8")

            meta = {
                "kind": "summarize",
                "model": result.model,
                "register": result.register,
                "n_chars_in": result.n_chars_in,
                "n_chars_out": result.n_chars_out,
            }
            return dst_path, out_filename, meta

        job = runner.submit(
            "summarize-text",
            fn,
            message=f"queued: {len(text)} chars · register={register or 'news'}",
        )
        return _job_to_dict(job)


_OOXML_DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
_OOXML_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
_OOXML_PPTX = "application/vnd.openxmlformats-officedocument.presentationml.presentation"


def _media_type_for(filename: str) -> str:
    suffix = Path(filename).suffix.lower()
    return {
        ".docx": _OOXML_DOCX,
        ".xlsx": _OOXML_XLSX,
        ".pptx": _OOXML_PPTX,
        ".txt": "text/plain; charset=utf-8",
        ".md": "text/markdown; charset=utf-8",
        ".markdown": "text/markdown; charset=utf-8",
        ".rst": "text/x-rst; charset=utf-8",
    }.get(suffix, "application/octet-stream")

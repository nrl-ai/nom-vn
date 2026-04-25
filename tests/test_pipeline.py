"""Tests for nom.doc pipeline + stages.

v0.0.3: Load and Parse are real (pure-stdlib for Load, optional pdfplumber for
Parse). OCR / Extract / Validate remain placeholders for v0.1.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from nom.doc import (
    OCR,
    Context,
    Extract,
    Load,
    Normalize,
    Parse,
    Pipeline,
    Validate,
    default_pipeline,
)


class TestContext:
    def test_minimal_construction(self) -> None:
        ctx = Context(source="hello.pdf")
        assert ctx.source == "hello.pdf"
        assert ctx.fmt is None
        assert ctx.pages_text == []
        assert ctx.text == ""
        assert ctx.output == {}

    def test_can_be_mutated_in_place(self) -> None:
        ctx = Context(source="x.pdf")
        ctx.fmt = "pdf"
        ctx.pages_text.append("page 1")
        ctx.output["key"] = "value"
        assert ctx.fmt == "pdf"
        assert ctx.pages_text == ["page 1"]
        assert ctx.output == {"key": "value"}


class TestLoadStage:
    """Real Load stage — pure stdlib, no third-party deps."""

    def test_pdf_magic_from_bytes(self) -> None:
        ctx = Context(source=b"%PDF-1.7\n...rest of pdf...")
        Load().run(ctx)
        assert ctx.fmt == "pdf"
        assert ctx.metadata["bytes"].startswith(b"%PDF")

    def test_png_magic_from_bytes(self) -> None:
        ctx = Context(source=b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)
        Load().run(ctx)
        assert ctx.fmt == "image"

    def test_jpeg_magic_from_bytes(self) -> None:
        ctx = Context(source=b"\xff\xd8\xff\xe0" + b"\x00" * 100)
        Load().run(ctx)
        assert ctx.fmt == "image"

    def test_text_fallback(self) -> None:
        ctx = Context(source=b"plain ASCII text content here")
        Load().run(ctx)
        assert ctx.fmt == "text"

    def test_path_extension_pdf(self, tmp_path: Path) -> None:
        # Path that exists, with PDF magic
        p = tmp_path / "doc.pdf"
        p.write_bytes(b"%PDF-1.4\nfake pdf bytes")
        ctx = Context(source=p)
        Load().run(ctx)
        assert ctx.fmt == "pdf"
        assert ctx.metadata["path"] == p
        assert ctx.metadata["bytes"].startswith(b"%PDF")

    def test_path_extension_image(self, tmp_path: Path) -> None:
        p = tmp_path / "scan.png"
        p.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)
        ctx = Context(source=p)
        Load().run(ctx)
        assert ctx.fmt == "image"

    def test_path_extension_text_file(self, tmp_path: Path) -> None:
        p = tmp_path / "note.txt"
        p.write_text("hello world")
        ctx = Context(source=p)
        Load().run(ctx)
        assert ctx.fmt == "text"

    def test_nonexistent_path_uses_extension(self) -> None:
        # Path doesn't exist — falls back to extension lookup
        ctx = Context(source="missing.pdf")
        Load().run(ctx)
        assert ctx.fmt == "pdf"
        # Bytes NOT cached when path doesn't exist
        assert "bytes" not in ctx.metadata

    def test_unknown_extension_defaults_to_text(self) -> None:
        ctx = Context(source="weird.xyz")
        Load().run(ctx)
        assert ctx.fmt == "text"


class TestParseStage:
    """Parse stage. PDF requires the [doc] extra (pdfplumber); text path is dep-free."""

    def test_text_input_populates_pages(self) -> None:
        ctx = Context(source=b"Hop dong nay.")
        Load().run(ctx)
        Parse().run(ctx)
        assert ctx.pages_text == ["Hop dong nay."]
        assert ctx.text == "Hop dong nay."

    def test_image_input_flags_for_ocr(self) -> None:
        ctx = Context(source=b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)
        Load().run(ctx)
        Parse().run(ctx)
        assert ctx.pages_text == [""]
        assert ctx.needs_ocr == [0]

    def test_parse_without_load_raises(self) -> None:
        ctx = Context(source="x.pdf")  # fmt not set
        with pytest.raises(RuntimeError, match=r"fmt"):
            Parse().run(ctx)

    def test_invalid_backend_rejected(self) -> None:
        with pytest.raises(ValueError, match=r"backend"):
            Parse(backend="bogus")

    def test_pdf_without_pdfplumber_gives_install_hint(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # Simulate pdfplumber not being installed.
        import builtins

        original_import = builtins.__import__

        def fake_import(name: str, *args: object, **kwargs: object) -> object:
            if name == "pdfplumber":
                raise ImportError("simulated missing")
            return original_import(name, *args, **kwargs)  # type: ignore[arg-type]

        monkeypatch.setattr(builtins, "__import__", fake_import)

        ctx = Context(source=b"%PDF-1.4\nfake")
        Load().run(ctx)
        with pytest.raises(ImportError, match=r"nom-vn\[doc\]"):
            Parse().run(ctx)


class TestPlaceholderStages:
    """OCR / Extract / Validate / Normalize still raise NotImplementedError."""

    def test_each_stage_has_name(self) -> None:
        assert OCR().name == "OCR"
        assert Normalize().name == "Normalize"
        assert Extract(llm=None).name == "Extract"
        assert Validate().name == "Validate"

    def test_placeholders_raise_in_v0(self) -> None:
        for stage in [OCR(), Normalize(), Extract(llm=None), Validate()]:
            with pytest.raises(NotImplementedError, match=r"v0\.1"):
                stage.run(Context(source="x.pdf"))


class TestPipeline:
    def test_construct_with_stages(self) -> None:
        pipe = Pipeline([Load(), Parse()])
        assert len(pipe.stages) == 2
        assert "Load" in repr(pipe)
        assert "Parse" in repr(pipe)
        assert "→" in repr(pipe)

    def test_empty_pipeline_rejected(self) -> None:
        with pytest.raises(ValueError, match=r"at least one"):
            Pipeline([])

    def test_default_pipeline_has_six_stages(self) -> None:
        pipe = default_pipeline()
        names = [s.name for s in pipe.stages]
        assert names == ["Load", "Parse", "OCR", "Normalize", "Extract", "Validate"]

    def test_default_pipeline_runs_through_load_then_fails_at_ocr(self) -> None:
        # Load + Parse work; OCR is still a placeholder. Pass a text input so
        # Parse short-circuits and we hit OCR (which is a placeholder).
        pipe = default_pipeline()
        # Hmm — for text input, Parse doesn't trigger OCR (needs_ocr stays empty).
        # The default pipeline invokes OCR unconditionally though, so it raises.
        # That's fine — confirms placeholders still raise for now.
        with pytest.raises(NotImplementedError, match=r"v0\.1"):
            pipe.run(b"hello text")

    def test_load_and_parse_compose_for_text(self) -> None:
        # Build a partial pipeline with only the implemented stages.
        pipe = Pipeline([Load(), Parse()])
        # Pipeline.run calls each stage in turn — but it returns ctx.output,
        # which Parse doesn't populate. So we test the stages directly:
        ctx = Context(source=b"Hop dong nay.")
        for stage in pipe.stages:
            ctx = stage.run(ctx)
        assert ctx.fmt == "text"
        assert ctx.text == "Hop dong nay."

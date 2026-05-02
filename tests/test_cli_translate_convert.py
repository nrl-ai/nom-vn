"""End-to-end CLI smoke tests for ``nom translate`` and ``nom convert``.

Exercises the actual subcommand dispatch via ``nom.chat.cli.main``,
using fake translators / no-OCR paths so the tests run offline and
fast. Covers the wiring (subparser registration → handler invocation)
that unit tests of the underlying modules can't catch.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

pytest.importorskip("docx")

_TESSERACT_BIN = shutil.which("tesseract")


def test_translate_help_lists_all_supported_formats(capsys: pytest.CaptureFixture[str]) -> None:
    """`nom translate --help` should mention all v0.2 supported formats."""
    from nom.chat.cli import main

    with pytest.raises(SystemExit) as exc:
        main(["translate", "--help"])
    assert exc.value.code == 0

    out = capsys.readouterr().out.lower()
    assert ".docx" in out
    assert ".xlsx" in out
    assert ".pptx" in out
    assert ".txt" in out


def test_convert_help_mentions_supported_inputs(capsys: pytest.CaptureFixture[str]) -> None:
    from nom.chat.cli import main

    with pytest.raises(SystemExit) as exc:
        main(["convert", "--help"])
    assert exc.value.code == 0

    out = capsys.readouterr().out.lower()
    assert ".pdf" in out
    assert ".png" in out


def test_translate_rejects_missing_input(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from nom.chat.cli import main

    rc = main(["translate", str(tmp_path / "nope.docx")])
    assert rc == 2
    err = capsys.readouterr().err
    assert "input not found" in err


def test_translate_rejects_unsupported_format(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from nom.chat.cli import main

    src = tmp_path / "data.csv"
    src.write_text("a,b,c\n", encoding="utf-8")
    rc = main(["translate", str(src)])
    assert rc == 2
    err = capsys.readouterr().err
    assert "unsupported source format" in err


def test_convert_rejects_unsupported_format(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from nom.chat.cli import main

    src = tmp_path / "data.csv"
    src.write_text("a,b,c\n", encoding="utf-8")
    rc = main(["convert", str(src)])
    assert rc == 2
    err = capsys.readouterr().err
    assert "unsupported source format" in err


def test_convert_rejects_missing_input(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    from nom.chat.cli import main

    rc = main(["convert", str(tmp_path / "nope.pdf")])
    assert rc == 2


@pytest.mark.skipif(_TESSERACT_BIN is None, reason="tesseract not installed")
def test_convert_image_end_to_end(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Real Tesseract OCR via the CLI on a PIL-rendered image."""
    pytest.importorskip("PIL")
    from PIL import Image, ImageDraw, ImageFont

    from nom.chat.cli import main

    src = tmp_path / "scan.png"
    img = Image.new("L", (640, 200), 255)
    drawer = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("DejaVuSans.ttf", 36)
    except OSError:
        font = ImageFont.load_default()
    drawer.text((20, 60), "Hello world", fill=0, font=font)
    img.save(str(src))

    rc = main(["convert", str(src), "--ocr-language", "eng"])
    assert rc == 0
    expected_dst = tmp_path / "scan.docx"
    assert expected_dst.exists()


def test_translate_with_explicit_output_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Use --output to control the destination path."""
    pytest.importorskip("docx")

    from nom.chat.cli import main

    src = tmp_path / "source.txt"
    custom_dst = tmp_path / "deeply" / "nested" / "result.txt"
    src.write_text("Xin chào", encoding="utf-8")

    # Monkey-patch the LLMTranslator to a no-network identity to keep
    # the test fast and offline. The CLI builds its translator from
    # nom.translate.cli._build_translator — patch that.
    import nom.translate.cli as cli_mod

    class IdentityLLMTranslator:
        name = "id"
        source_lang = "vi"
        target_lang = "en"

        def translate(self, text: str, *, hint: str | None = None) -> str:
            return text

    monkeypatch.setattr(cli_mod, "_build_translator", lambda args: IdentityLLMTranslator())

    rc = main(["translate", str(src), "--output", str(custom_dst)])
    assert rc == 0
    assert custom_dst.exists()
    assert "Xin chào" in custom_dst.read_text(encoding="utf-8")


def test_translate_default_output_path_uses_target_language(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Without --output, the result lands at <stem>.<target><ext>."""
    from nom.chat.cli import main

    src = tmp_path / "report.txt"
    src.write_text("hello", encoding="utf-8")

    import nom.translate.cli as cli_mod

    class IdentityLLMTranslator:
        name = "id"
        source_lang = "en"
        target_lang = "vi"

        def translate(self, text: str, *, hint: str | None = None) -> str:
            return text

    monkeypatch.setattr(cli_mod, "_build_translator", lambda args: IdentityLLMTranslator())

    rc = main(["translate", str(src), "--src", "en", "--tgt", "vi"])
    assert rc == 0
    assert (tmp_path / "report.vi.txt").exists()

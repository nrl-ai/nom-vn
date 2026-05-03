"""Tests for nom.ocr.handwriting.

Lightweight unit tests on the wrapper contract — Protocol satisfaction,
the line-crop guard, and the lazy-import error path. The actual Vintern
forward pass needs ~2 GB weights + GPU, so it lives in the integration
tier (skipped cleanly when transformers / torch are missing).
"""

from __future__ import annotations

import pytest

from nom.ocr import HandwritingOcr, HandwritingResult, VinternHandwritingOcr


def test_protocol_satisfaction() -> None:
    clf = VinternHandwritingOcr()
    assert isinstance(clf, HandwritingOcr)
    assert clf.name == "vintern-1b-v3_5"


def test_line_crop_rejected() -> None:
    """The min_height guard fires before any model load — sub-60-px short
    edge raises ValueError naming the trap."""
    pil = pytest.importorskip("PIL.Image")
    img_bytes = _png_bytes(pil, width=200, height=20)  # tight line crop

    clf = VinternHandwritingOcr()
    with pytest.raises(ValueError, match="min_height"):
        clf.transcribe(img_bytes)


def test_full_page_passes_size_guard() -> None:
    """A 600x800 full page passes the guard — error from then on must
    come from missing model deps, not from the size check."""
    pil = pytest.importorskip("PIL.Image")
    img_bytes = _png_bytes(pil, width=600, height=800)

    clf = VinternHandwritingOcr()
    # We don't want to actually download Vintern in unit tests, so the
    # call may raise ImportError (deps missing) or another error from
    # downstream — but it must NOT be the size-guard ValueError.
    try:
        clf.transcribe(img_bytes)
    except ValueError as e:
        if "min_height" in str(e):
            raise AssertionError("full page should not trip the line-crop guard") from e
    except (ImportError, Exception):
        # Any other failure path is acceptable — model load / network /
        # API mismatch. We only assert the guard didn't fire spuriously.
        pass


def test_handwriting_result_is_frozen() -> None:
    """Result objects must be immutable so callers can hash / cache them."""
    res = HandwritingResult(text="abc", model="vintern", confidence=None)
    with pytest.raises((AttributeError, Exception)):
        res.text = "mutated"  # type: ignore[misc]


def _png_bytes(pil_module: object, *, width: int, height: int) -> bytes:
    """Make an in-memory PNG of the given size — minimal fixture."""
    from io import BytesIO

    img = pil_module.new("RGB", (width, height), color=(255, 255, 255))  # type: ignore[attr-defined]
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()

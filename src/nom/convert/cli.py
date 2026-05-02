"""``nom convert <file> --to docx`` — PDF / image → DOCX."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

__all__ = ["add_subparser", "run"]


def add_subparser(subparsers: argparse._SubParsersAction[Any]) -> None:
    """Register the ``convert`` subcommand on a top-level parser."""
    p = subparsers.add_parser(
        "convert",
        help="Convert PDF / image to DOCX (with OCR fallback for scanned PDFs)",
    )
    p.add_argument("input", help="Path to a .pdf, .png, .jpg, .tif, .bmp, or .webp file.")
    p.add_argument(
        "--to",
        default="docx",
        choices=["docx"],
        help="Output format. Currently only docx is supported.",
    )
    p.add_argument(
        "--output",
        "-o",
        default=None,
        help="Output path. Default: <input-stem>.docx next to source.",
    )
    p.add_argument(
        "--ocr-language",
        default="vie+eng",
        help="Tesseract language pack. Default: vie+eng.",
    )


def run(args: argparse.Namespace) -> int:
    """Execute a configured convert invocation. Returns a process exit code."""
    src_path = Path(args.input).expanduser()
    if not src_path.exists():
        print(f"input not found: {src_path}", file=sys.stderr)
        return 2

    dst_path = Path(args.output).expanduser() if args.output else src_path.with_suffix(".docx")

    from nom.convert import SUPPORTED_INPUTS, convert_to_docx

    if src_path.suffix.lower() not in SUPPORTED_INPUTS:
        print(
            f"unsupported source format {src_path.suffix!r}; supported: {sorted(SUPPORTED_INPUTS)}",
            file=sys.stderr,
        )
        return 2

    print(
        f"converting {src_path.name} → {dst_path.name} (OCR lang: {args.ocr_language}) ...",
        file=sys.stderr,
    )
    try:
        stats = convert_to_docx(src_path, dst_path, ocr_language=args.ocr_language)
    except ImportError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 3

    print(
        f"done: {stats.n_pages} page(s) — "
        f"{stats.pages_text_extracted} text-layer + {stats.pages_ocred} OCR — "
        f"{stats.chars_out:,} chars.",
        file=sys.stderr,
    )
    return 0

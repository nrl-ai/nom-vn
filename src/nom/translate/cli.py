"""``nom translate <file>`` — format-preserving file translation.

v0.1 supports ``.docx``. Other formats are scaffolded in
``nom.translate.formats`` but not wired into the CLI yet.

Wired into the top-level ``nom`` dispatcher via
:func:`add_subparser` and :func:`run`, called from
``nom.chat.cli.main``.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

from nom.translate.base import Translator

__all__ = ["add_subparser", "run"]


def add_subparser(subparsers: argparse._SubParsersAction[Any]) -> None:
    """Register the ``translate`` subcommand on a top-level parser."""
    p = subparsers.add_parser(
        "translate",
        help="Translate a .docx file preserving formatting (v0.1)",
    )
    p.add_argument("input", help="Path to a .docx file.")
    p.add_argument(
        "--source",
        "--src",
        dest="source",
        default="vi",
        choices=["en", "vi"],
        help="Source language. Default: vi.",
    )
    p.add_argument(
        "--target",
        "--tgt",
        dest="target",
        default="en",
        choices=["en", "vi"],
        help="Target language. Default: en.",
    )
    p.add_argument(
        "--output",
        "-o",
        default=None,
        help="Output .docx path. Default: <input-stem>.<tgt>.docx next to source.",
    )
    p.add_argument(
        "--backend",
        default="ollama",
        choices=["ollama", "hf"],
        help="Translator backend: prompted Ollama LLM (default) or HF seq2seq.",
    )
    p.add_argument(
        "--model",
        default=None,
        help=(
            "Model id. Backend-specific defaults: ollama → qwen3:8b, hf → google/madlad400-3b-mt."
        ),
    )
    p.add_argument(
        "--ollama-url",
        default="http://localhost:11434",
        help="Ollama server URL (only used when --backend=ollama).",
    )


def run(args: argparse.Namespace) -> int:
    """Execute a configured translate invocation. Returns a process exit code."""
    src_path = Path(args.input).expanduser()
    if not src_path.exists():
        print(f"input not found: {src_path}", file=sys.stderr)
        return 2

    suffix = src_path.suffix.lower()
    if suffix != ".docx":
        print(
            f"only .docx is supported in v0.1; got '{suffix}'. "
            f"Other formats land after the docx walker has user feedback.",
            file=sys.stderr,
        )
        return 2

    if args.output:
        dst_path = Path(args.output).expanduser()
    else:
        dst_path = src_path.with_name(f"{src_path.stem}.{args.target}{src_path.suffix}")

    translator = _build_translator(args)
    from nom.translate.formats.docx import translate_docx

    print(
        f"translating {src_path.name} ({args.source}→{args.target}) "
        f"via {args.backend}:{translator.name} → {dst_path.name} ...",
        file=sys.stderr,
    )
    stats = translate_docx(src_path, dst_path, translator)

    print(
        f"done: {stats.paragraphs_translated} translated, "
        f"{stats.paragraphs_skipped} skipped, "
        f"{stats.paragraphs_failed} failed "
        f"({stats.chars_in:,} → {stats.chars_out:,} chars).",
        file=sys.stderr,
    )
    return 0 if stats.paragraphs_failed == 0 else 1


def _build_translator(args: argparse.Namespace) -> Translator:
    if args.backend == "ollama":
        from nom.llm import Ollama
        from nom.translate.llm import LLMTranslator

        llm = Ollama(
            model=args.model or "qwen3:8b",
            base_url=args.ollama_url,
            think=False,
        )
        return LLMTranslator(
            llm=llm,
            source_lang=args.source,
            target_lang=args.target,
        )

    if args.backend == "hf":
        from nom.translate.hf import HFTranslator

        return HFTranslator(
            model_id=args.model or "google/madlad400-3b-mt",
            source_lang=args.source,
            target_lang=args.target,
        )

    raise ValueError(f"unknown backend: {args.backend}")

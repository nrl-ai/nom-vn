"""PDF text-extraction benchmark — pdfplumber vs pypdfium2.

Measures speed and extraction fidelity on the committed UDHR Vietnamese PDF
(``benchmarks/data/udhr_vi/udhr_vie.pdf``, public domain, ~111 KB / 4 pages).
The ground-truth plaintext (``udhr_vi.txt``) lets us measure character-level
extraction completeness.

Methodology:
  - Warmup: 3 throwaway extractions (CLAUDE.md §12).
  - Timed: best-of-5 elapsed for the full document.
  - Fidelity: char-overlap fraction between extracted text (after NFC
    normalize) and the ground-truth text. Both are normalised to a canonical
    form before comparison so whitespace differences don't dominate.

Why not PyMuPDF? AGPL — incompatible with our Apache-2.0 default. pypdfium2
ships PDFium (Apache-2.0) under a BSD-3 wrapper.

Run:
    python benchmarks/perf/bench_pdf_extract.py
    python benchmarks/perf/bench_pdf_extract.py --json results/pdf_extract.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import unicodedata
from dataclasses import asdict, dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
# Synthetic VN PDF with proper Unicode text layer. See
# benchmarks/data/synthetic_pdf_vi/_generate.py — built from real VN
# public-domain prose using fpdf2 + DejaVuSans. The committed UDHR PDF
# (udhr_vie.pdf) embeds a custom font without ToUnicode CMap, so any
# extractor returns CIDs / garbled bytes. Synthetic PDF gives a clean
# ground truth for fidelity comparison.
PDF_PATH = REPO_ROOT / "benchmarks" / "data" / "synthetic_pdf_vi" / "vn_legal.pdf"
GROUND_TRUTH = REPO_ROOT / "benchmarks" / "data" / "synthetic_pdf_vi" / "vn_legal.gt.txt"


def _extract_pdfplumber(pdf_path: Path) -> str:
    import pdfplumber

    with pdfplumber.open(pdf_path) as pdf:
        return "\n".join(page.extract_text() or "" for page in pdf.pages)


def _extract_pypdfium2(pdf_path: Path) -> str:
    import pypdfium2 as pdfium

    pdf = pdfium.PdfDocument(str(pdf_path))
    try:
        chunks: list[str] = []
        for page in pdf:
            tp = page.get_textpage()
            try:
                chunks.append(tp.get_text_range())
            finally:
                tp.close()
        return "\n".join(chunks)
    finally:
        pdf.close()


def _canonical(text: str) -> str:
    """Normalise to NFC; collapse whitespace runs to a single space.

    Without this step the comparison is dominated by trivial whitespace
    diffs (newlines vs spaces in different extraction paths).
    """
    text = unicodedata.normalize("NFC", text)
    return re.sub(r"\s+", " ", text).strip()


def _char_overlap(extracted: str, gold: str) -> float:
    """Fraction of gold characters present in extracted (canonical forms).

    Uses character-multiset intersection — not edit distance — because
    we want to penalise dropped characters and reward complete coverage,
    not order. Diacritics in pdfplumber's output sometimes appear before
    or after the base character; multiset overlap is robust to that.
    """
    if not gold:
        return 1.0
    e = _canonical(extracted)
    g = _canonical(gold)
    from collections import Counter

    ce = Counter(e)
    cg = Counter(g)
    total_gold = sum(cg.values())
    matched = sum((ce & cg).values())
    return matched / total_gold if total_gold else 0.0


@dataclass
class EngineResult:
    name: str
    extracted_chars: int
    canonical_chars: int
    overlap_with_ground_truth: float
    elapsed_best_of_5_seconds: float
    throughput_chars_per_sec: float
    pages: int


@dataclass
class BenchSummary:
    pdf: str
    pdf_bytes: int
    ground_truth_chars: int
    canonical_ground_truth_chars: int
    warmup_calls: int
    runs: int
    engines: list[EngineResult]


def _time_extractor(fn, pdf_path: Path, warmup: int, runs: int) -> tuple[float, str]:
    for _ in range(warmup):
        fn(pdf_path)
    best = float("inf")
    sample: str = ""
    for _ in range(runs):
        start = time.perf_counter()
        sample = fn(pdf_path)
        elapsed = time.perf_counter() - start
        if elapsed < best:
            best = elapsed
    return best, sample


def _page_count(pdf_path: Path) -> int:
    import pypdfium2 as pdfium

    pdf = pdfium.PdfDocument(str(pdf_path))
    try:
        return len(pdf)
    finally:
        pdf.close()


def run(warmup: int = 3, runs: int = 5) -> BenchSummary:
    if not PDF_PATH.exists():
        raise FileNotFoundError(f"PDF not at {PDF_PATH}")
    if not GROUND_TRUTH.exists():
        raise FileNotFoundError(f"Ground truth not at {GROUND_TRUTH}")

    gt_text = GROUND_TRUTH.read_text(encoding="utf-8")
    gt_canon = _canonical(gt_text)
    pages = _page_count(PDF_PATH)

    extractors = [
        ("pdfplumber", _extract_pdfplumber),
        ("pypdfium2", _extract_pypdfium2),
    ]

    engines: list[EngineResult] = []
    for name, fn in extractors:
        elapsed, sample = _time_extractor(fn, PDF_PATH, warmup=warmup, runs=runs)
        canon = _canonical(sample)
        overlap = _char_overlap(sample, gt_text)
        engines.append(
            EngineResult(
                name=name,
                extracted_chars=len(sample),
                canonical_chars=len(canon),
                overlap_with_ground_truth=round(overlap, 4),
                elapsed_best_of_5_seconds=round(elapsed, 4),
                throughput_chars_per_sec=round(len(canon) / elapsed, 0) if elapsed else 0.0,
                pages=pages,
            )
        )

    return BenchSummary(
        pdf=str(PDF_PATH.relative_to(REPO_ROOT)),
        pdf_bytes=PDF_PATH.stat().st_size,
        ground_truth_chars=len(gt_text),
        canonical_ground_truth_chars=len(gt_canon),
        warmup_calls=warmup,
        runs=runs,
        engines=engines,
    )


def _print_human(s: BenchSummary) -> None:
    print(f"PDF: {s.pdf}  ({s.pdf_bytes:,} bytes, {s.engines[0].pages} pages)")
    print(
        f"Ground truth: {s.ground_truth_chars:,} chars (canonical {s.canonical_ground_truth_chars:,})"
    )
    print(f"Methodology: warmup {s.warmup_calls} · best-of-{s.runs}")
    print()
    print(f"{'engine':>14}  {'best (s)':>10}  {'chars/s':>14}  {'extracted':>11}  {'overlap':>8}")
    print("-" * 64)
    for e in s.engines:
        print(
            f"{e.name:>14}  {e.elapsed_best_of_5_seconds:>10.4f}  "
            f"{e.throughput_chars_per_sec:>14,.0f}  {e.canonical_chars:>11,}  "
            f"{e.overlap_with_ground_truth:>8.2%}"
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", type=Path, default=None)
    parser.add_argument("--warmup", type=int, default=3)
    parser.add_argument("--runs", type=int, default=5)
    args = parser.parse_args(argv)

    summary = run(warmup=args.warmup, runs=args.runs)
    _print_human(summary)

    if args.json is not None:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        with args.json.open("w", encoding="utf-8") as f:
            json.dump(asdict(summary), f, ensure_ascii=False, indent=2)
        print(f"\nResults: {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""OCR accuracy benchmark — compares OCR engines on Vietnamese scans.

**Status: scaffold for v0.1.** Real engine integrations (VietOCR, PaddleOCR,
Tesseract) and a Vietnamese scan corpus arrive with v0.1.

Today this script:
  - Lists planned engines.
  - Validates the harness shape.
  - Documents what we'll measure (CER, WER, diacritic-aware WER, latency).

Run:
    python benchmarks/accuracy/bench_ocr.py            # smoke
    python benchmarks/accuracy/bench_ocr.py --engine vietocr   # v0.1+
"""

from __future__ import annotations

import argparse
import sys

# Engines we plan to compare in v0.1. See docs/PIPELINE.md for selection rationale.
PLANNED_ENGINES: list[dict[str, str]] = [
    {
        "name": "vietocr",
        "approach": "Transformer (VN-specialized)",
        "license": "Apache 2.0",
        "expected_cer": "low (best on diacritics)",
        "speed": "slower (Transformer)",
        "url": "https://github.com/pbcquoc/vietocr",
    },
    {
        "name": "paddleocr",
        "approach": "PP-OCRv5 (multilingual)",
        "license": "Apache 2.0",
        "expected_cer": "94.5% on OmniDocBench",
        "speed": "medium",
        "url": "https://github.com/PaddlePaddle/PaddleOCR",
    },
    {
        "name": "easyocr",
        "approach": "CNN+LSTM (multilingual)",
        "license": "Apache 2.0",
        "expected_cer": "~79% general",
        "speed": "fast (56 FPS)",
        "url": "https://github.com/JaidedAI/EasyOCR",
    },
    {
        "name": "tesseract",
        "approach": "LSTM with vie traineddata",
        "license": "Apache 2.0",
        "expected_cer": "70-97% (image-quality dependent)",
        "speed": "slow (9.8 FPS)",
        "url": "https://github.com/tesseract-ocr/tesseract",
    },
]


# Metrics we will report per (engine, document) pair.
PLANNED_METRICS: list[str] = [
    "char_error_rate",  # CER — Levenshtein / total chars
    "word_error_rate",  # WER — token-level mismatch
    "diacritic_aware_wer",  # WER weighted to penalize tone-mark errors
    "latency_per_page_ms",
    "throughput_pages_per_sec",
    "memory_peak_mb",
]


def smoke_test() -> int:
    print("nom-vn OCR accuracy benchmark · v0.0.1 scaffold")
    print(f"Planned engines:  {len(PLANNED_ENGINES)}")
    print(f"Planned metrics:  {len(PLANNED_METRICS)}")
    print()
    print(f"  {'engine':<12} {'license':<12} {'expected accuracy':<32} {'speed':<20}")
    print("  " + "-" * 80)
    for e in PLANNED_ENGINES:
        print(f"  {e['name']:<12} {e['license']:<12} {e['expected_cer']:<32} {e['speed']:<20}")
    print()
    print("Metrics we will report:")
    for m in PLANNED_METRICS:
        print(f"  - {m}")
    print()
    print("Why this is empty today:")
    print("  - The OCR scan corpus arrives with v0.1.")
    print("  - Engine integrations require optional deps (`pip install nom-vn[doc]`).")
    print("  - We do not publish synthetic OCR numbers.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--engine",
        choices=[e["name"] for e in PLANNED_ENGINES],
        help="Run only this engine. v0.1+.",
    )
    parser.add_argument("--json", type=str, default=None, help="Output JSON results. v0.1+.")
    args = parser.parse_args(argv)

    if args.engine or args.json:
        print(
            "ERROR: real OCR runs are part of v0.1, not v0.0.1.",
            file=sys.stderr,
        )
        return 1

    return smoke_test()


if __name__ == "__main__":
    sys.exit(main())

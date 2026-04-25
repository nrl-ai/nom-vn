"""End-to-end pipeline benchmark — measures composite extraction quality.

**Status: scaffold for v0.1.** Once ``nom.doc.Pipeline`` has real stages, this
harness runs full PDF/scan → JSON extractions and scores them on field-level
accuracy + latency + cost.

Today this script:
  - Enumerates the document categories the corpus will cover.
  - Documents what we'll score and how.
  - Validates the harness shape via a smoke run.

Run:
    python benchmarks/accuracy/bench_pipeline.py             # smoke
    python benchmarks/accuracy/bench_pipeline.py --llm ollama:qwen3:8b  # v0.1+
"""

from __future__ import annotations

import argparse
import sys

# Document categories we will cover in the v0.1 corpus.
PLANNED_CATEGORIES: list[dict[str, str]] = [
    {
        "name": "contract",
        "n_documents": "20 synthetic + 10 anonymized real",
        "fields": "so_hop_dong, ngay_ky, ben_a, ben_b, tong_gia_tri, dieu_khoan_phat",
        "input_form": "PDF (mostly native, some scan)",
    },
    {
        "name": "official_doc",
        "n_documents": "15 synthetic công văn",
        "fields": "so_van_ban, ngay_ban_hanh, don_vi_phat_hanh, noi_dung_chinh",
        "input_form": "PDF + scanned image",
    },
    {
        "name": "id_card",
        "n_documents": "synthetic CMND/CCCD only (privacy)",
        "fields": "so, ho_ten, ngay_sinh, gioi_tinh, dia_chi",
        "input_form": "scanned image",
    },
    {
        "name": "receipt",
        "n_documents": "30 receipts (mixed cuisine + retail)",
        "fields": "merchant, date, items, total_vnd, tax",
        "input_form": "phone-camera image",
    },
    {
        "name": "application",
        "n_documents": "10 đơn xin (admin / HR)",
        "fields": "ho_ten, lý_do, thoi_gian, người_ký",
        "input_form": "PDF or scan",
    },
]


# What we score per (pipeline_config, document) pair.
PLANNED_METRICS: list[str] = [
    "field_accuracy_strict",  # exact match on each schema field
    "field_accuracy_fuzzy",  # Levenshtein-tolerant on string fields
    "schema_validation_rate",  # how often output passes Pydantic validation first try
    "retries_required",  # avg LLM retries to get valid output (instructor metric)
    "latency_p50_ms",
    "latency_p95_ms",
    "input_tokens",
    "output_tokens",
    "cost_usd_per_doc",  # only for paid LLM tiers
]


# Pipeline configurations we will compare. Each is a different combo of
# (OCR engine, normalize backend, LLM, schema-extraction lib).
PLANNED_CONFIGS: list[str] = [
    "vietocr + nom.text(rules) + qwen3:8b + instructor",
    "vietocr + nom.text(model) + qwen3:8b + instructor",
    "tesseract + nom.text(model) + qwen3:8b + instructor",
    "paddleocr + nom.text(model) + llama3.1:8b + instructor",
    "vietocr + nom.text(model) + gpt-4o + instructor",  # cloud reference
    "vision-only (Qwen2.5-VL-72B)",  # OCR-skip, vision-LLM direct
]


def smoke_test() -> int:
    print("nom-vn end-to-end pipeline benchmark · v0.0.1 scaffold")
    print(f"Document categories:  {len(PLANNED_CATEGORIES)}")
    print(f"Pipeline configs:     {len(PLANNED_CONFIGS)}")
    print(f"Metrics per run:      {len(PLANNED_METRICS)}")
    print()
    print("Document categories planned for v0.1 corpus:")
    print(f"  {'category':<14} {'count':<32} {'input form':<28}")
    print("  " + "-" * 76)
    for c in PLANNED_CATEGORIES:
        print(f"  {c['name']:<14} {c['n_documents']:<32} {c['input_form']:<28}")
    print()
    print("Pipeline configurations to compare:")
    for i, cfg in enumerate(PLANNED_CONFIGS, 1):
        print(f"  {i}. {cfg}")
    print()
    print("Metrics:")
    for m in PLANNED_METRICS:
        print(f"  - {m}")
    print()
    print("Why this is empty today:")
    print("  - Real Pipeline stages ship in v0.1 (currently raise NotImplementedError).")
    print("  - The extraction corpus is being curated; no real numbers yet.")
    print("  - Synthetic / projected numbers are not published.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--llm", help="LLM backend spec (v0.1+)")
    parser.add_argument("--json", type=str, default=None, help="Output JSON. v0.1+.")
    args = parser.parse_args(argv)

    if args.llm or args.json:
        print(
            "ERROR: real pipeline runs are part of v0.1, not v0.0.1.",
            file=sys.stderr,
        )
        return 1

    return smoke_test()


if __name__ == "__main__":
    sys.exit(main())

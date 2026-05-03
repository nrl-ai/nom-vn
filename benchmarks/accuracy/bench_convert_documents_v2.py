"""Benchmark `nom.convert.convert_to_docx` on the v0.2 corpus —
9 real PD scans (chinhphu.vn + hanoi.gov.vn) + 3 synthetic receipts
with scan artifacts.

Reports CER (raw and whitespace-normalized) per config + per
document. v0.1 had only synthetic line-renders; v0.2 lets us track
the realistic-scan baseline.

Usage::

    python benchmarks/accuracy/bench_convert_documents_v2.py
    python benchmarks/accuracy/bench_convert_documents_v2.py \\
        --json benchmarks/results/baseline_convert_documents_v2.json
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import statistics
import sys
import tempfile
import time
import unicodedata
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

_WS = re.compile(r"\s+")


def _cer(hyp: str, ref: str, *, normalize_whitespace: bool) -> float:
    a = unicodedata.normalize("NFC", hyp)
    b = unicodedata.normalize("NFC", ref)
    if normalize_whitespace:
        a = _WS.sub(" ", a).strip()
        b = _WS.sub(" ", b).strip()
    if not b:
        return 0.0 if not a else 1.0
    m, n = len(a), len(b)
    if m == 0:
        return 1.0
    dp = list(range(n + 1))
    for i in range(1, m + 1):
        prev = dp[0]
        dp[0] = i
        for j in range(1, n + 1):
            cur = dp[j]
            dp[j] = prev if a[i - 1] == b[j - 1] else 1 + min(prev, dp[j], dp[j - 1])
            prev = cur
    return dp[n] / max(m, n)


def _read_docx_text(path: Path) -> str:
    from docx import Document

    return "\n".join(p.text for p in Document(path).paragraphs).strip()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=0, help="Cap docs (0 = full).")
    parser.add_argument("--ocr-language", default="vie+eng")
    parser.add_argument("--json", type=Path, default=None)
    args = parser.parse_args()

    if shutil.which("tesseract") is None:
        print("error: tesseract not installed", file=sys.stderr)
        return 1

    from nom.convert import convert_to_docx

    corpus = REPO / "benchmarks" / "data" / "vn_documents_ocr_v2"
    meta_path = corpus / "metadata.jsonl"
    if not meta_path.exists():
        print(f"error: corpus missing — run {corpus}/_generate.py first", file=sys.stderr)
        return 1

    docs = [json.loads(line) for line in meta_path.read_text(encoding="utf-8").splitlines()]
    if args.limit:
        docs = docs[: args.limit]

    print(f"\n{'config':>14} | {'doc_id':>32} | {'CER (raw)':>9} | {'CER (norm)':>10} | {'sec':>4}")
    print("-" * 85)

    per_doc: list[dict[str, Any]] = []
    by_config_norm: dict[str, list[float]] = {}

    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)
        for doc in docs:
            pdf_path = corpus / doc["pdf"]
            out_path = td_path / f"{doc['doc_id']}.docx"
            t0 = time.perf_counter()
            stats = convert_to_docx(pdf_path, out_path, ocr_language=args.ocr_language)
            elapsed = time.perf_counter() - t0
            hyp = _read_docx_text(out_path)
            cer_raw = _cer(hyp, doc["text"], normalize_whitespace=False)
            cer_norm = _cer(hyp, doc["text"], normalize_whitespace=True)

            per_doc.append(
                {
                    "doc_id": doc["doc_id"],
                    "config": doc["config"],
                    "category": doc["category"],
                    "title": doc["title"],
                    "issuer": doc["issuer"],
                    "n_pages": doc["n_pages"],
                    "cer_raw": round(cer_raw, 4),
                    "cer_normalized": round(cer_norm, 4),
                    "elapsed_seconds": round(elapsed, 2),
                    "pages_ocred": stats.pages_ocred,
                    "pages_text_extracted": stats.pages_text_extracted,
                }
            )
            by_config_norm.setdefault(doc["config"], []).append(cer_norm)

            print(
                f"{doc['config']:>14} | {doc['doc_id']:>32} | "
                f"{cer_raw * 100:>8.2f}% | {cer_norm * 100:>9.2f}% | {elapsed:>4.1f}"
            )

    print("\n--- BY CONFIG (whitespace-normalized) ---")
    for cfg, cers in sorted(by_config_norm.items()):
        print(
            f"  {cfg:<15s} mean {statistics.mean(cers) * 100:5.2f}% "
            f"median {statistics.median(cers) * 100:5.2f}%  n={len(cers)}"
        )

    overall_norm = statistics.mean([d["cer_normalized"] for d in per_doc])
    overall_raw = statistics.mean([d["cer_raw"] for d in per_doc])
    total_seconds = sum(d["elapsed_seconds"] for d in per_doc)
    docs_per_sec = len(per_doc) / total_seconds if total_seconds else 0.0

    print(
        f"\n  OVERALL    raw {overall_raw * 100:.2f}%  norm {overall_norm * 100:.2f}%  n={len(per_doc)}"
    )
    print(f"  Throughput {total_seconds:.1f}s total → {docs_per_sec:.2f} docs/sec")

    if args.json:
        result = {
            "config": {
                "ocr_language": args.ocr_language,
                "limit": args.limit,
                "tesseract": shutil.which("tesseract"),
                "corpus": "benchmarks/data/vn_documents_ocr_v2",
                "n_docs": len(per_doc),
            },
            "summary": {
                "overall_cer_raw": round(overall_raw, 4),
                "overall_cer_normalized": round(overall_norm, 4),
                "total_seconds": round(total_seconds, 2),
                "docs_per_second": round(docs_per_sec, 3),
            },
            "by_config": {
                cfg: {
                    "n": len(by_config_norm[cfg]),
                    "cer_normalized_mean": round(statistics.mean(by_config_norm[cfg]), 4),
                    "cer_normalized_median": round(statistics.median(by_config_norm[cfg]), 4),
                }
                for cfg in sorted(by_config_norm)
            },
            "per_doc": per_doc,
        }
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(result, ensure_ascii=False, indent=2))
        print(f"\nResults: {args.json}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

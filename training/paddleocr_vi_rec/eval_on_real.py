"""Eval a fine-tuned PaddleOCR rec checkpoint on the real-scan corpus.

Compares against the existing baselines:
  - Tesseract vie+eng:               12.62 % CER (config=real, n=9)
  - PaddleOCR PP-OCRv5 lang='vi':    20.74 % CER (config=real, n=9)

Usage::

    # After training finishes on the remote and you rsync'd the checkpoint
    # back to ./checkpoints/vi_rec_finetune/, run:
    python training/paddleocr_vi_rec/eval_on_real.py \\
        --checkpoint training/paddleocr_vi_rec/checkpoints/vi_rec_finetune/best_accuracy \\
        --json benchmarks/results/baseline_paddleocr_v5_vi_finetune.json

The eval uses the same PaddleOCR pipeline as the default lang='vi'
bench but swaps in our fine-tuned recognizer via the
`text_recognition_model_dir` parameter — so detection stays as
PP-OCRv5_server_det (good at finding text boxes in cluttered scans).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import statistics
import sys
import time
import unicodedata
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--checkpoint",
        type=Path,
        required=True,
        help="Path to the fine-tuned recognizer checkpoint dir (PaddleOCR inference format)",
    )
    parser.add_argument(
        "--json",
        type=Path,
        default=REPO / "benchmarks/results/baseline_paddleocr_v5_vi_finetune.json",
    )
    args = parser.parse_args()

    # Disable mkldnn — PIR + onednn instruction is broken in our paddle 3.3.x
    os.environ["FLAGS_use_mkldnn"] = "0"  # noqa: SIM112 (paddle-specific lowercase)
    import paddle

    paddle.set_flags({"FLAGS_use_mkldnn": 0})

    from paddleocr import PaddleOCR

    ocr = PaddleOCR(
        text_recognition_model_dir=str(args.checkpoint),
        text_recognition_model_name="PP-OCRv5_mobile_rec",  # match arch
        lang="vi",
        use_doc_orientation_classify=False,
        use_doc_unwarping=False,
        use_textline_orientation=False,
        enable_mkldnn=False,
    )

    meta_path = REPO / "benchmarks/data/vn_documents_ocr_v2/metadata.jsonl"
    docs = [json.loads(line) for line in meta_path.read_text(encoding="utf-8").splitlines()]
    real_docs = [d for d in docs if d["config"] == "real"]
    print(f"Eval on {len(real_docs)} real-scan documents\n")

    ws = re.compile(r"\s+")

    def cer(hyp: str, ref: str) -> float:
        a = ws.sub(" ", unicodedata.normalize("NFC", hyp)).strip()
        b = ws.sub(" ", unicodedata.normalize("NFC", ref)).strip()
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

    print(f"{'doc_id':>32} | {'CER':>6} | {'sec':>5}", flush=True)
    print("-" * 60)
    results = []
    for d in real_docs:
        img = REPO / "benchmarks/data/vn_documents_ocr_v2" / d["image"]
        t0 = time.perf_counter()
        res = ocr.predict(str(img))
        elapsed = time.perf_counter() - t0
        text = ""
        for r in res:
            if hasattr(r, "keys") and "rec_texts" in r:
                text = "\n".join(r["rec_texts"])
                break
        c = cer(text, d["text"])
        results.append({"doc_id": d["doc_id"], "cer": round(c, 4), "sec": round(elapsed, 1)})
        print(f"{d['doc_id']:>32} | {c * 100:5.2f}% | {elapsed:5.1f}", flush=True)

    cers = [r["cer"] for r in results]
    print(f"\nmean CER {statistics.mean(cers) * 100:.2f}%")
    print(f"median CER {statistics.median(cers) * 100:.2f}%")
    print(f"mean sec {statistics.mean([r['sec'] for r in results]):.1f}")

    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(
        json.dumps(
            {
                "engine": f"PaddleOCR PP-OCRv5_mobile_rec fine-tuned (Vietnamese), checkpoint={args.checkpoint}",
                "corpus": "vn-ocr-documents-eval v0.4 / config=real (n=9)",
                "mean_cer_normalized": round(statistics.mean(cers), 4),
                "median_cer_normalized": round(statistics.median(cers), 4),
                "mean_seconds": round(statistics.mean([r["sec"] for r in results]), 2),
                "tesseract_baseline": 0.1262,
                "paddle_default_baseline": 0.2074,
                "per_doc": results,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    print(f"\nSaved → {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

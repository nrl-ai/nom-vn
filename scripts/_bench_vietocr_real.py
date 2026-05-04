"""Bench VietOCR (pbcquoc/vietocr Transformer rec) on the 9 real-scan
corpus. VietOCR has a VN-tuned recognizer but doesn't ship a detector,
so we use Tesseract to detect line bboxes then VietOCR to recognize
each line crop — the same det+rec composition PaddleOCR uses.
"""

from __future__ import annotations

import json
import os
import re
import statistics
import sys
import time
import unicodedata
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
WS = re.compile(r"\s+")


def cer(hyp: str, ref: str) -> float:
    a = WS.sub(" ", unicodedata.normalize("NFC", hyp)).strip()
    b = WS.sub(" ", unicodedata.normalize("NFC", ref)).strip()
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


def main() -> int:
    # Tesseract for line detection (returns bboxes only, then VietOCR
    # recognizes each line)
    import pytesseract
    from PIL import Image
    from vietocr.tool.config import Cfg
    from vietocr.tool.predictor import Predictor

    print("init VietOCR…", flush=True)
    cfg = Cfg.load_config_from_name("vgg_seq2seq")
    cfg["device"] = "cuda" if os.getenv("CUDA_VISIBLE_DEVICES") != "-1" else "cpu"
    cfg["predictor"]["beamsearch"] = False
    detector = Predictor(cfg)
    print(f"  device: {cfg['device']}", flush=True)

    meta = (
        (REPO / "benchmarks/data/vn_documents_ocr_v2/metadata.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    )
    real_docs = [json.loads(line) for line in meta if json.loads(line)["config"] == "real"]
    print(f"\nbench on {len(real_docs)} real-scan documents", flush=True)
    print(f"\n{'doc_id':>32} | {'CER':>6} | {'sec':>5}", flush=True)
    print("-" * 60, flush=True)

    results = []
    for d in real_docs:
        img_path = REPO / "benchmarks/data/vn_documents_ocr_v2" / d["image"]
        img = Image.open(img_path).convert("RGB")

        t0 = time.perf_counter()
        # Use pytesseract to get word/line bboxes
        data = pytesseract.image_to_data(img, lang="vie+eng", output_type=pytesseract.Output.DICT)
        # Group bboxes by line_num within block_num
        from collections import defaultdict

        lines: dict[tuple[int, int, int], list[int]] = defaultdict(list)
        for i in range(len(data["text"])):
            if not data["text"][i].strip():
                continue
            key = (data["block_num"][i], data["par_num"][i], data["line_num"][i])
            lines[key].append(i)

        line_texts = []
        for key, idx_list in sorted(lines.items()):
            if not idx_list:
                continue
            xs = [data["left"][i] for i in idx_list]
            ys = [data["top"][i] for i in idx_list]
            ws = [data["left"][i] + data["width"][i] for i in idx_list]
            hs = [data["top"][i] + data["height"][i] for i in idx_list]
            x0, y0, x1, y1 = min(xs), min(ys), max(ws), max(hs)
            # Pad
            x0, y0 = max(0, x0 - 4), max(0, y0 - 4)
            x1, y1 = min(img.width, x1 + 4), min(img.height, y1 + 4)
            crop = img.crop((x0, y0, x1, y1))
            try:
                txt = detector.predict(crop)
            except Exception as exc:
                txt = ""
                print(f"  vietocr predict fail: {exc}", file=sys.stderr)
            line_texts.append(txt)

        elapsed = time.perf_counter() - t0
        full_text = "\n".join(line_texts)
        c = cer(full_text, d["text"])
        results.append({"doc_id": d["doc_id"], "cer": round(c, 4), "sec": round(elapsed, 1)})
        print(f"{d['doc_id']:>32} | {c * 100:5.2f}% | {elapsed:5.1f}", flush=True)

    cers = [r["cer"] for r in results]
    print(f"\nmean CER {statistics.mean(cers) * 100:.2f}%")
    print(f"median CER {statistics.median(cers) * 100:.2f}%")
    print(f"mean sec {statistics.mean([r['sec'] for r in results]):.1f}")

    out = REPO / "benchmarks/results/baseline_vietocr_real.json"
    out.write_text(
        json.dumps(
            {
                "engine": "VietOCR (pbcquoc/vietocr) vgg_seq2seq, with Tesseract for line detection",
                "corpus": "vn-ocr-documents-eval v0.4 / config=real (n=9)",
                "mean_cer_normalized": round(statistics.mean(cers), 4),
                "median_cer_normalized": round(statistics.median(cers), 4),
                "mean_seconds": round(statistics.mean([r["sec"] for r in results]), 2),
                "tesseract_baseline": 0.1262,
                "paddleocr_default_baseline": 0.2074,
                "paddleocr_finetune_baseline": 0.1508,
                "per_doc": results,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    print(f"\nSaved → {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

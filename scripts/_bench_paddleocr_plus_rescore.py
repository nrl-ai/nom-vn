"""Test if Tesseract+rescore lift (1.35 pp median) stacks on PaddleOCR
round-1 mobile fine-tune output."""

from __future__ import annotations

import json
import os
import re
import statistics
import sys
import unicodedata
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
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
    os.environ["FLAGS_use_mkldnn"] = "0"  # noqa: SIM112
    import paddle

    paddle.set_flags({"FLAGS_use_mkldnn": 0})

    from paddleocr import PaddleOCR

    from nom.text.diacritic_models import HFDiacriticModel

    print("init…", flush=True)
    rescorer = HFDiacriticModel(model_id="nrl-ai/vn-spell-correction-base")
    rescorer._ensure_loaded()
    ocr = PaddleOCR(
        text_recognition_model_dir=str(
            REPO / "training/paddleocr_vi_rec/checkpoints/vi_rec_finetune/inference"
        ),
        text_recognition_model_name="PP-OCRv5_mobile_rec",
        lang="vi",
        use_doc_orientation_classify=False,
        use_doc_unwarping=False,
        use_textline_orientation=False,
        enable_mkldnn=False,
    )

    meta = (
        (REPO / "benchmarks/data/vn_documents_ocr_v2/metadata.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    )
    real_docs = [json.loads(line) for line in meta if json.loads(line)["config"] == "real"]
    print(f"\n{'doc_id':>32} | {'paddle CER':>10} | {'+rescore':>9} | {'Δ pp':>6}")
    print("-" * 70)

    raw_cers, rescored_cers = [], []
    for d in real_docs:
        img = REPO / "benchmarks/data/vn_documents_ocr_v2" / d["image"]
        res = ocr.predict(str(img))
        text_raw = ""
        for r in res:
            if hasattr(r, "keys") and "rec_texts" in r:
                text_raw = "\n".join(r["rec_texts"])
                break
        # Rescore line-by-line
        lines = text_raw.split("\n")
        rescored = []
        for line in lines:
            if not line.strip():
                rescored.append(line)
            else:
                try:
                    rescored.append(rescorer.predict(line))
                except Exception:
                    rescored.append(line)
        text_rescored = "\n".join(rescored)

        c_raw = cer(text_raw, d["text"])
        c_rescored = cer(text_rescored, d["text"])
        raw_cers.append(c_raw)
        rescored_cers.append(c_rescored)
        print(
            f"{d['doc_id']:>32} | {c_raw * 100:9.2f}% | {c_rescored * 100:8.2f}% | {(c_raw - c_rescored) * 100:+5.2f}",
            flush=True,
        )

    mean_raw = statistics.mean(raw_cers)
    mean_rescored = statistics.mean(rescored_cers)
    med_raw = statistics.median(raw_cers)
    med_rescored = statistics.median(rescored_cers)
    print(f"\nPaddleOCR mobile r1 alone   mean {mean_raw * 100:.2f}%  median {med_raw * 100:.2f}%")
    print(
        f"+ rescore                   mean {mean_rescored * 100:.2f}%  median {med_rescored * 100:.2f}%"
    )
    print(
        f"Δ                           mean {(mean_raw - mean_rescored) * 100:+.2f} pp  median {(med_raw - med_rescored) * 100:+.2f} pp"
    )

    out = REPO / "benchmarks/results/baseline_paddleocr_mobile_post_rescore_real.json"
    out.write_text(
        json.dumps(
            {
                "engine": "PaddleOCR mobile fine-tune (r1) + nrl-ai/vn-spell-correction-base post-rescore",
                "corpus": "vn-ocr-documents-eval v0.4 / config=real (n=9)",
                "paddleocr_mobile_alone_mean": round(mean_raw, 4),
                "paddleocr_mobile_alone_median": round(med_raw, 4),
                "with_rescore_mean": round(mean_rescored, 4),
                "with_rescore_median": round(med_rescored, 4),
                "delta_mean_pp": round((mean_raw - mean_rescored) * 100, 2),
                "delta_median_pp": round((med_raw - med_rescored) * 100, 2),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    print(f"\nSaved → {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

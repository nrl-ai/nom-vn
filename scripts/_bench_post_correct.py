"""Bench Tesseract → spell-correction post-pipeline on real-scan corpus.

Per Do et al. (AAAI 2025, arXiv 2410.13305), LLM post-OCR rescoring is
the strongest cited technique for printed VN — they drop WER from 27%
to 18% by chaining Tesseract + GPT-4o-mini with content reference.

We don't have a content reference for chinhphu.vn scans, but our
nrl-ai/vn-spell-correction-base model is precisely a typo-tolerant VN
diacritic + spell corrector trained for this scenario. Test whether
chaining Tesseract → vn-spell-correction-base reduces CER on the same
n=9 real-scan corpus.

Hypothesis: the spell-correct model fixes a chunk of Tesseract's diacritic
+ rare-OCR-substitution errors. Expected lift: 1-3 pp CER.
"""

from __future__ import annotations

import json
import re
import statistics
import sys
import time
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
    from nom.convert import convert_to_docx
    from nom.text.diacritic_models import HFDiacriticModel
    from docx import Document
    import tempfile

    print("init spell-correction model…", flush=True)
    rescorer = HFDiacriticModel(model_id="nrl-ai/vn-spell-correction-base")
    rescorer._ensure_loaded()  # warm
    print(f"  device: {rescorer.device}", flush=True)

    meta = (REPO / "benchmarks/data/vn_documents_ocr_v2/metadata.jsonl").read_text(encoding="utf-8").splitlines()
    real_docs = [json.loads(line) for line in meta if json.loads(line)["config"] == "real"]
    print(f"\nbench on {len(real_docs)} real-scan documents", flush=True)
    print(f"\n{'doc_id':>32} | {'tess CER':>8} | {'+rescore':>8} | {'Δ pp':>6}")
    print("-" * 70)

    raw_cers, rescored_cers = [], []
    rescore_seconds = []

    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)
        for d in real_docs:
            pdf = REPO / "benchmarks/data/vn_documents_ocr_v2" / d["pdf"]
            out = td_path / f"{d['doc_id']}.docx"
            convert_to_docx(pdf, out, ocr_language="vie+eng")
            text_raw = "\n".join(p.text for p in Document(out).paragraphs).strip()

            # Apply spell-correction line by line
            t0 = time.perf_counter()
            lines = text_raw.split("\n")
            rescored = []
            for line in lines:
                if not line.strip():
                    rescored.append(line)
                else:
                    try:
                        rescored.append(rescorer.predict(line))
                    except Exception as exc:  # noqa: BLE001
                        print(f"  rescore failed: {exc}", file=sys.stderr)
                        rescored.append(line)
            rescore_t = time.perf_counter() - t0
            text_rescored = "\n".join(rescored)

            c_raw = cer(text_raw, d["text"])
            c_rescored = cer(text_rescored, d["text"])
            delta = (c_raw - c_rescored) * 100
            raw_cers.append(c_raw)
            rescored_cers.append(c_rescored)
            rescore_seconds.append(rescore_t)
            print(
                f"{d['doc_id']:>32} | {c_raw * 100:7.2f}% | {c_rescored * 100:7.2f}% | {delta:+5.2f}",
                flush=True,
            )

    print(f'\n  raw Tesseract        mean {statistics.mean(raw_cers) * 100:.2f}%  median {statistics.median(raw_cers) * 100:.2f}%')
    print(f'  + rescore            mean {statistics.mean(rescored_cers) * 100:.2f}%  median {statistics.median(rescored_cers) * 100:.2f}%')
    delta_mean = (statistics.mean(raw_cers) - statistics.mean(rescored_cers)) * 100
    delta_median = (statistics.median(raw_cers) - statistics.median(rescored_cers)) * 100
    print(f'  Δ (improvement)      mean {delta_mean:+.2f} pp  median {delta_median:+.2f} pp')
    print(f'  rescore latency      mean {statistics.mean(rescore_seconds):.1f} s/doc')

    out = REPO / "benchmarks/results/baseline_tesseract_post_rescore_real.json"
    out.write_text(
        json.dumps(
            {
                "engine": "Tesseract vie+eng + nrl-ai/vn-spell-correction-base post-rescore",
                "corpus": "vn-ocr-documents-eval v0.4 / config=real (n=9)",
                "tesseract_alone_mean": round(statistics.mean(raw_cers), 4),
                "tesseract_alone_median": round(statistics.median(raw_cers), 4),
                "with_rescore_mean": round(statistics.mean(rescored_cers), 4),
                "with_rescore_median": round(statistics.median(rescored_cers), 4),
                "delta_mean_pp": round(delta_mean, 2),
                "delta_median_pp": round(delta_median, 2),
                "rescore_seconds_mean": round(statistics.mean(rescore_seconds), 2),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    print(f'\nSaved → {out}')
    return 0


if __name__ == "__main__":
    sys.exit(main())

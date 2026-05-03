"""End-to-end feature-grid benchmark on `vn-ocr-documents-eval` v0.2.

Runs every applicable nom-vn feature on each document in the v0.2
corpus and reports a single grid of feature-by-doc results. Tests
that the full stack works on real Vietnamese government scans, not
just synthetic line crops.

Features exercised per document (downstream of the OCR'd text):

  1. nom.convert.convert_to_docx       — OCR (Tesseract via pdf_to_docx)
                                         → CER vs human-verified gold
  2. nom.text.normalize                — NFC; is_vietnamese; has_diacritics
  3. nom.text.segment.word_tokenize    — token count + n_compounds
  4. nom.text.segment.sent_tokenize    — sentence count
  5. nom.nlp.ner.RegexNERModel(legal)  — labelled spans (PER/ORG/LOC/
                                         DATE/MONEY/LAW_REF/ID_VN/PHONE_VN)
  6. nom.nlp.sentiment                 — coarse polarity
  7. nom.classify.register             — LexiconRegisterClassifier
                                         (top-1 register prediction)
  8. nom.text.normalize.fix_diacritics — round-trip fidelity
                                         (strip then restore via rule baseline)

Skipped here because they require heavy weights or external services:
  - nom.summarize.ViT5Summarizer       (866 M, would slow bench >10x)
  - nom.classify.PhoBertRegisterClassifier (540 MB)
  - nom.translate.LLMTranslator        (needs Ollama)
  - nom.ocr.handwriting                (this is OCR for handwriting, not
                                         relevant for printed gov docs)
  - nom.stt.whisper                    (audio, not text)

Run::

    python benchmarks/accuracy/bench_features_e2e.py
    python benchmarks/accuracy/bench_features_e2e.py \\
        --json benchmarks/results/baseline_features_e2e.json
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
from collections import Counter
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

_WS = re.compile(r"\s+")


def _cer(hyp: str, ref: str) -> float:
    a = _WS.sub(" ", unicodedata.normalize("NFC", hyp)).strip()
    b = _WS.sub(" ", unicodedata.normalize("NFC", ref)).strip()
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


def _read_docx(path: Path) -> str:
    from docx import Document

    return "\n".join(p.text for p in Document(path).paragraphs).strip()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--ocr-language", default="vie+eng")
    parser.add_argument("--json", type=Path, default=None)
    args = parser.parse_args()

    if shutil.which("tesseract") is None:
        print("error: tesseract not installed", file=sys.stderr)
        return 1

    from nom.classify.register import LexiconRegisterClassifier
    from nom.convert import convert_to_docx
    from nom.nlp.ner import RegexNERModel
    from nom.nlp.ner_legal import legal_ner_patterns
    from nom.nlp.sentiment import LexiconSentimentModel
    from nom.text import sent_tokenize, word_tokenize
    from nom.text.normalize import (
        fix_diacritics,
        has_diacritics,
        is_vietnamese,
        normalize,
        strip_diacritics,
    )

    corpus = REPO / "benchmarks" / "data" / "vn_documents_ocr_v2"
    meta_path = corpus / "metadata.jsonl"
    if not meta_path.exists():
        print(f"error: corpus missing — run {corpus}/_generate.py first", file=sys.stderr)
        return 1

    docs = [json.loads(line) for line in meta_path.read_text(encoding="utf-8").splitlines()]
    if args.limit:
        docs = docs[: args.limit]

    ner = RegexNERModel(extra_patterns=legal_ner_patterns())
    register_clf = LexiconRegisterClassifier()
    sentiment_clf = LexiconSentimentModel()

    per_doc: list[dict[str, Any]] = []
    feature_summary: dict[str, list[float]] = {
        "convert_cer": [],
        "convert_seconds": [],
        "ner_seconds": [],
        "register_seconds": [],
        "fix_diacritics_seconds": [],
    }
    label_counts: dict[str, Counter] = {
        "ner_label": Counter(),
        "register_label": Counter(),
        "sentiment_label": Counter(),
    }

    print(
        f"\n{'config':>14} | {'doc_id':>32} | {'CER':>5} | {'tok':>4} | {'sent':>4} | {'NER':>3} | {'register':>13} | {'sentmt':>8}"
    )
    print("-" * 105)

    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)
        for doc in docs:
            pdf_path = corpus / doc["pdf"]
            out_path = td_path / f"{doc['doc_id']}.docx"

            # 1. convert_to_docx
            t0 = time.perf_counter()
            stats = convert_to_docx(pdf_path, out_path, ocr_language=args.ocr_language)
            convert_t = time.perf_counter() - t0
            ocr_text = _read_docx(out_path)
            cer = _cer(ocr_text, doc["text"])

            # 2. text.normalize
            normed = normalize(ocr_text)
            is_vi = is_vietnamese(normed)
            has_d = has_diacritics(normed)

            # 3. tokenization (apply on the OCR output, not gold — measures
            #    what downstream tasks would actually see).
            tokens = word_tokenize(normed)
            sentences = sent_tokenize(normed)
            n_compounds = sum(1 for t in tokens if " " in t)

            # 5. NER (regex + legal preset)
            t0 = time.perf_counter()
            spans = ner.tag(normed)
            ner_t = time.perf_counter() - t0
            for s in spans:
                label_counts["ner_label"][s.label] += 1

            # 6. sentiment
            sent_res = sentiment_clf.predict(normed)
            label_counts["sentiment_label"][sent_res.label.value] += 1

            # 7. register
            t0 = time.perf_counter()
            reg_res = register_clf.predict(normed)
            register_t = time.perf_counter() - t0
            label_counts["register_label"][reg_res.label.value] += 1

            # 8. diacritic round-trip — strip dấu, restore via rule baseline,
            #    measure how close we get back to the original (informational
            #    only — known limitation: rule baseline ~50% on real text).
            t0 = time.perf_counter()
            stripped = strip_diacritics(normed[:500])
            restored = fix_diacritics(stripped)
            diacritic_t = time.perf_counter() - t0
            roundtrip_cer = _cer(restored, normed[:500])

            row = {
                "doc_id": doc["doc_id"],
                "config": doc["config"],
                "category": doc["category"],
                # convert
                "convert_cer": round(cer, 4),
                "convert_seconds": round(convert_t, 2),
                "convert_pages_ocred": stats.pages_ocred,
                # text.normalize / detect
                "is_vietnamese": is_vi,
                "has_diacritics": has_d,
                "ocr_chars": len(ocr_text),
                # tokenize
                "n_tokens": len(tokens),
                "n_compounds": n_compounds,
                "n_sentences": len(sentences),
                # ner
                "ner_n_spans": len(spans),
                "ner_labels": sorted({s.label for s in spans}),
                "ner_seconds": round(ner_t * 1000, 1),  # ms
                # sentiment
                "sentiment_label": sent_res.label.value,
                "sentiment_score": round(sent_res.score, 3),
                # register
                "register_label": reg_res.label.value,
                "register_score": round(reg_res.score, 3),
                "register_seconds": round(register_t * 1000, 1),
                # diacritic round-trip on first 500 chars
                "diacritic_roundtrip_cer": round(roundtrip_cer, 3),
                "fix_diacritics_seconds": round(diacritic_t, 2),
            }
            per_doc.append(row)
            feature_summary["convert_cer"].append(cer)
            feature_summary["convert_seconds"].append(convert_t)
            feature_summary["ner_seconds"].append(ner_t * 1000)
            feature_summary["register_seconds"].append(register_t * 1000)
            feature_summary["fix_diacritics_seconds"].append(diacritic_t)

            print(
                f"{doc['config']:>14} | {doc['doc_id']:>32} | "
                f"{cer * 100:4.1f}% | {len(tokens):>4} | {len(sentences):>4} | "
                f"{len(spans):>3} | {reg_res.label.value:>13} | {sent_res.label.value:>8}"
            )

    # ----- summary -----
    print("\n=== FEATURE-GRID SUMMARY ===")
    print(
        f"  convert_cer (whitespace-norm)  mean {statistics.mean(feature_summary['convert_cer']) * 100:5.2f}%  median {statistics.median(feature_summary['convert_cer']) * 100:5.2f}%"
    )
    print(
        f"  convert_seconds                mean {statistics.mean(feature_summary['convert_seconds']):5.2f}s  median {statistics.median(feature_summary['convert_seconds']):5.2f}s"
    )
    print(
        f"  ner_seconds                    mean {statistics.mean(feature_summary['ner_seconds']):5.1f}ms"
    )
    print(
        f"  register_seconds               mean {statistics.mean(feature_summary['register_seconds']):5.1f}ms"
    )
    print(
        f"  fix_diacritics_seconds (500c)  mean {statistics.mean(feature_summary['fix_diacritics_seconds']):5.2f}s"
    )

    print("\n  NER label distribution      :", dict(label_counts["ner_label"]))
    print("  Register label distribution :", dict(label_counts["register_label"]))
    print("  Sentiment label distribution:", dict(label_counts["sentiment_label"]))

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
                "convert_cer_mean": round(statistics.mean(feature_summary["convert_cer"]), 4),
                "convert_cer_median": round(statistics.median(feature_summary["convert_cer"]), 4),
                "convert_seconds_mean": round(
                    statistics.mean(feature_summary["convert_seconds"]), 2
                ),
                "ner_ms_mean": round(statistics.mean(feature_summary["ner_seconds"]), 1),
                "register_ms_mean": round(statistics.mean(feature_summary["register_seconds"]), 1),
                "fix_diacritics_seconds_mean": round(
                    statistics.mean(feature_summary["fix_diacritics_seconds"]), 2
                ),
                "ner_label_distribution": dict(label_counts["ner_label"]),
                "register_label_distribution": dict(label_counts["register_label"]),
                "sentiment_label_distribution": dict(label_counts["sentiment_label"]),
            },
            "per_doc": per_doc,
        }
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(result, ensure_ascii=False, indent=2))
        print(f"\nResults: {args.json}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

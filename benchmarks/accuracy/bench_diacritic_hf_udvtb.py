"""Bench Toshiiiii1 T5 diacritic restoration on UD_Vietnamese-VTB test (800 sents).

Larger corpus = more confident accuracy estimate vs the 55-sent v0 corpus.
The diacritic-survey agent flagged this on 2026-04-26.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import torch
from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

sys.path.insert(0, "src")
from nom.text import has_diacritics, strip_diacritics

REPO = Path(__file__).resolve().parent
CONLLU = Path("benchmarks/data/ud_vi_vtb/test.conllu")
OUT = Path("benchmarks/results/baseline_diacritic_toshiiiii_udvtb_test.json")


def load_sentences(path: Path) -> list[str]:
    """Extract # text= lines from a CoNLL-U file."""
    sents: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("# text"):
            _, _, val = line.partition("=")
            text = val.strip()
            if text:
                sents.append(text)
    return sents


def main() -> int:
    sents = load_sentences(CONLLU)
    print(f"corpus: {len(sents)} sentences from {CONLLU}")

    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"device: {device}")
    model_id = "Toshiiiii1/Vietnamese_diacritics_restoration_5th"
    print(f"loading {model_id}...")
    t0 = time.perf_counter()
    tok = AutoTokenizer.from_pretrained(model_id)
    model = AutoModelForSeq2SeqLM.from_pretrained(model_id).to(device).eval()
    print(f"  loaded in {time.perf_counter() - t0:.1f}s")

    # Warmup
    warm = strip_diacritics(sents[0])
    for _ in range(3):
        x = tok(warm, return_tensors="pt", max_length=512, truncation=True).to(device)
        with torch.no_grad():
            model.generate(**x, max_length=512, num_beams=1)

    n_words = n_correct = n_diac = n_diac_rec = 0
    n_sent = 0
    n_sent_exact = 0
    latencies: list[float] = []
    t_total0 = time.perf_counter()
    for i, orig in enumerate(sents):
        stripped = strip_diacritics(orig)
        t0 = time.perf_counter()
        x = tok(stripped, return_tensors="pt", max_length=512, truncation=True).to(device)
        with torch.no_grad():
            out = model.generate(**x, max_length=512, num_beams=1)
        pred = tok.decode(out[0], skip_special_tokens=True)
        latencies.append(time.perf_counter() - t0)

        n_sent += 1
        if pred.strip() == orig.strip():
            n_sent_exact += 1
        for o, p in zip(orig.split(), pred.split(), strict=False):
            n_words += 1
            if o == p:
                n_correct += 1
            if has_diacritics(o):
                n_diac += 1
                if o == p:
                    n_diac_rec += 1
        if (i + 1) % 100 == 0:
            print(f"  {i + 1}/{len(sents)} processed, running word_acc={n_correct / n_words:.4f}")
    elapsed = time.perf_counter() - t_total0

    word_acc = n_correct / n_words if n_words else 0
    diac_rec = n_diac_rec / n_diac if n_diac else 0
    sent_acc = n_sent_exact / n_sent if n_sent else 0
    latencies.sort()
    p50 = latencies[len(latencies) // 2]
    p95 = latencies[max(0, int(len(latencies) * 0.95) - 1)]
    mean = sum(latencies) / len(latencies)

    print()
    print("Final:")
    print(f"  Word accuracy:     {word_acc:.4f}  ({n_correct:,}/{n_words:,})")
    print(f"  Diacritic recall:  {diac_rec:.4f}  ({n_diac_rec:,}/{n_diac:,})")
    print(f"  Sentence exact:    {sent_acc:.4f}  ({n_sent_exact}/{n_sent})")
    print(f"  Mean latency:      {mean * 1000:.1f} ms")
    print(f"  p50 latency:       {p50 * 1000:.1f} ms")
    print(f"  p95 latency:       {p95 * 1000:.1f} ms")
    print(f"  Total elapsed:     {elapsed:.1f} s")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        json.dumps(
            {
                "model_id": model_id,
                "corpus": str(CONLLU),
                "device": device,
                "n_sentences": len(sents),
                "n_words": n_words,
                "n_words_with_diacritic": n_diac,
                "word_accuracy": round(word_acc, 4),
                "diacritic_recall": round(diac_rec, 4),
                "sentence_exact_match": round(sent_acc, 4),
                "elapsed_seconds": round(elapsed, 4),
                "latency_per_sentence_mean": round(mean, 4),
                "latency_per_sentence_p50": round(p50, 4),
                "latency_per_sentence_p95": round(p95, 4),
                "warmup_calls": 3,
                "num_beams": 1,
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    print(f"\nResults: {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

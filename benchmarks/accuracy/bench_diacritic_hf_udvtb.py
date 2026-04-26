"""Bench HF seq2seq diacritic models on UD_Vietnamese-VTB test (800 sents).

Larger / different-register corpus vs ``diacritic_eval_v0.txt``. UD-VTB
provides a literary-register signal that the small business-corpus eval
misses.

**Punctuation normalization is critical.** UD-VTB ships sentences in the
treebank's tokenized form — spaces around every punctuation mark
(``nhỉ ? " .`` not ``nhỉ?".``). Modern seq2seq models output the natural
form with attached punctuation. Comparing raw ``.split()`` lists between
the two produces 0 sentence-exact matches no matter how good the
model is, because the token alignment shifts at the first punctuation.

We normalize *both* sides to a canonical "no space before punctuation,
single space elsewhere" form before splitting. This isolates diacritic
quality from punctuation spacing convention.

This was an actual incident on 2026-04-26: the v0.2.17 commit reported
54.14 % word accuracy / 0.00 % sentence-exact on UD-VTB. The 0/800
sentence-exact was the giveaway — a tokenization artifact, not real
model failure. After normalization the diacritic-only metric sits much
higher; see the JSON output for both tracks.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import unicodedata
from pathlib import Path

import torch
from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

sys.path.insert(0, "src")
from nom.text import has_diacritics, strip_diacritics

# Punctuation that should attach to the preceding token (no space before).
# ASCII + common Vietnamese / typographical variants.
_ATTACH_TRAILING = re.compile(r"\s+([,.;:!?\)\]\}\"\'»…])")
# Punctuation that should attach to the following token (no space after).
_ATTACH_LEADING = re.compile(r"([\(\[\{\"\'«])\s+")


def normalize_punct(text: str) -> str:
    """Canonical form: NFC + no space before/after attaching punctuation.

    Comparison-time normalization only; do not mutate user data elsewhere.
    UD treebank tokenization is correct for treebank tasks (POS, parsing);
    it's just wrong for byte-equal sentence-match with naturally-formatted
    seq2seq output.
    """
    text = unicodedata.normalize("NFC", text)
    text = _ATTACH_TRAILING.sub(r"\1", text)
    text = _ATTACH_LEADING.sub(r"\1", text)
    return re.sub(r"\s+", " ", text).strip()


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
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--model-id",
        default="Toshiiiii1/Vietnamese_diacritics_restoration_5th",
    )
    p.add_argument(
        "--corpus",
        type=Path,
        default=Path("benchmarks/data/ud_vi_vtb/test.conllu"),
    )
    p.add_argument("--examples", type=int, default=3)
    p.add_argument(
        "--json",
        type=Path,
        default=Path("benchmarks/results/baseline_diacritic_toshiiiii_udvtb_test.json"),
    )
    args = p.parse_args()

    sents = load_sentences(args.corpus)
    print(f"corpus: {len(sents)} sentences from {args.corpus}")

    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"device: {device}")
    print(f"loading {args.model_id}...")
    t0 = time.perf_counter()
    tok = AutoTokenizer.from_pretrained(args.model_id)
    model = AutoModelForSeq2SeqLM.from_pretrained(args.model_id).to(device).eval()
    print(f"  loaded in {time.perf_counter() - t0:.1f}s")

    # Warmup
    warm = strip_diacritics(sents[0])
    for _ in range(3):
        x = tok(warm, return_tensors="pt", max_length=512, truncation=True).to(device)
        with torch.no_grad():
            model.generate(**x, max_length=512, num_beams=1)

    # Two metric tracks: normalized (apples-to-apples) and raw (kept for context).
    raw_n_words = raw_n_correct = raw_n_diac = raw_n_diac_rec = 0
    n_words = n_correct = n_diac = n_diac_rec = 0
    n_sent_exact_norm = 0
    n_sent_exact_raw = 0
    latencies: list[float] = []
    sample_outs: list[tuple[str, str, str]] = []
    t_total0 = time.perf_counter()

    for i, orig in enumerate(sents):
        stripped = strip_diacritics(orig)
        t0 = time.perf_counter()
        x = tok(stripped, return_tensors="pt", max_length=512, truncation=True).to(device)
        with torch.no_grad():
            out = model.generate(**x, max_length=512, num_beams=1)
        pred = tok.decode(out[0], skip_special_tokens=True)
        latencies.append(time.perf_counter() - t0)
        sample_outs.append((orig, stripped, pred))

        # Raw byte-level comparison (the old metric — alignment-broken on UD-VTB)
        if pred.strip() == orig.strip():
            n_sent_exact_raw += 1
        for o, prd in zip(orig.split(), pred.split(), strict=False):
            raw_n_words += 1
            if o == prd:
                raw_n_correct += 1
            if has_diacritics(o):
                raw_n_diac += 1
                if o == prd:
                    raw_n_diac_rec += 1

        # Punctuation-normalized comparison
        orig_norm = normalize_punct(orig)
        pred_norm = normalize_punct(pred)
        if pred_norm == orig_norm:
            n_sent_exact_norm += 1
        for o, prd in zip(orig_norm.split(), pred_norm.split(), strict=False):
            n_words += 1
            if o == prd:
                n_correct += 1
            if has_diacritics(o):
                n_diac += 1
                if o == prd:
                    n_diac_rec += 1

        if (i + 1) % 100 == 0:
            print(
                f"  {i + 1}/{len(sents)} processed: "
                f"normalized word_acc={n_correct / n_words:.4f}, "
                f"raw word_acc={raw_n_correct / raw_n_words:.4f}"
            )
    elapsed = time.perf_counter() - t_total0

    word_acc_norm = n_correct / n_words if n_words else 0
    diac_rec_norm = n_diac_rec / n_diac if n_diac else 0
    sent_acc_norm = n_sent_exact_norm / len(sents)

    word_acc_raw = raw_n_correct / raw_n_words if raw_n_words else 0
    diac_rec_raw = raw_n_diac_rec / raw_n_diac if raw_n_diac else 0
    sent_acc_raw = n_sent_exact_raw / len(sents)

    latencies.sort()
    p50 = latencies[len(latencies) // 2]
    p95 = latencies[max(0, int(len(latencies) * 0.95) - 1)]
    mean = sum(latencies) / len(latencies)

    print()
    print("=== Punctuation-normalized (apples-to-apples diacritic quality) ===")
    print(f"  Word accuracy:     {word_acc_norm:.4f}  ({n_correct:,}/{n_words:,})")
    print(f"  Diacritic recall:  {diac_rec_norm:.4f}  ({n_diac_rec:,}/{n_diac:,})")
    print(f"  Sentence exact:    {sent_acc_norm:.4f}  ({n_sent_exact_norm}/{len(sents)})")
    print()
    print("=== Raw .split() (kept for context — UD-VTB tokenization shifts alignment) ===")
    print(f"  Word accuracy:     {word_acc_raw:.4f}  ({raw_n_correct:,}/{raw_n_words:,})")
    print(f"  Diacritic recall:  {diac_rec_raw:.4f}  ({raw_n_diac_rec:,}/{raw_n_diac:,})")
    print(f"  Sentence exact:    {sent_acc_raw:.4f}  ({n_sent_exact_raw}/{len(sents)})")
    print()
    print(f"Mean latency:      {mean * 1000:.1f} ms")
    print(f"p50 latency:       {p50 * 1000:.1f} ms")
    print(f"p95 latency:       {p95 * 1000:.1f} ms")
    print(f"Total elapsed:     {elapsed:.1f} s")

    if args.examples > 0:
        print()
        print(f"=== Examples (first {args.examples}, normalized) ===")
        for orig, _stripped, pred in sample_outs[: args.examples]:
            on = normalize_punct(orig)
            pn = normalize_punct(pred)
            match = "MATCH" if on == pn else "DIFF "
            print(f"  [{match}] GT:  {on}")
            print(f"          OUT: {pn}")
            print()

    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(
        json.dumps(
            {
                "model_id": args.model_id,
                "corpus": str(args.corpus),
                "device": device,
                "n_sentences": len(sents),
                "normalized": {
                    "n_words": n_words,
                    "n_words_with_diacritic": n_diac,
                    "word_accuracy": round(word_acc_norm, 4),
                    "diacritic_recall": round(diac_rec_norm, 4),
                    "sentence_exact_match": round(sent_acc_norm, 4),
                },
                "raw_split": {
                    "n_words": raw_n_words,
                    "n_words_with_diacritic": raw_n_diac,
                    "word_accuracy": round(word_acc_raw, 4),
                    "diacritic_recall": round(diac_rec_raw, 4),
                    "sentence_exact_match": round(sent_acc_raw, 4),
                    "note": (
                        "Pre-tokenized UD-VTB style (spaces around punctuation) "
                        "shifts alignment vs natural seq2seq output. Use "
                        "'normalized' track for apples-to-apples model quality."
                    ),
                },
                "elapsed_seconds": round(elapsed, 4),
                "latency_per_sentence_mean": round(mean, 4),
                "latency_per_sentence_p50": round(p50, 4),
                "latency_per_sentence_p95": round(p95, 4),
                "warmup_calls": 3,
                "num_beams": 1,
                "comparison_normalization": (
                    "NFC + no space before/after attaching punctuation, "
                    "collapse whitespace runs to single space."
                ),
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    print(f"\nResults: {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

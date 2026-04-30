"""Bench an HF spell-correction model on the OOD real-world VN typo eval set.

Companion to ``bench_spell_correction_hf.py``. Same metrics, same model
loading, but reads from ``benchmarks/data/spell_correction_eval_real/``
where the noise patterns come from real Vietnamese error sources
(forum slang, mobile autocorrect, real Telex keystrokes, OCR engine
output) rather than from `nom.text.noise`.

Compare these numbers against the in-distribution synthetic numbers to
estimate the model's OOD robustness. A model that scores 98 % on
synthetic and 60 % on real has overfit to the noise generator; a model
that scores ~85 % on both has generalized well.

Usage::

    python benchmarks/accuracy/bench_spell_correction_real.py \\
        nrl-ai/vn-spell-correction-base \\
        --json benchmarks/results/real_spell_correction_base.json
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import unicodedata
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from training.diacritic.train import _word_accuracy, normalize_punct  # noqa: E402

# --- Statistical helpers --------------------------------------------------


def _bootstrap_ci_word_acc(
    preds: list[str],
    targets: list[str],
    *,
    n_resamples: int = 1000,
    seed: int = 42,
) -> tuple[float, float]:
    """Sentence-level bootstrap 95 % CI on word accuracy.

    Resamples the (pred, target) pairs N times with replacement and
    re-computes ``_word_accuracy`` each time. Returns the (low, high)
    percentile (2.5, 97.5) of the resampled distribution.
    """
    import random

    if not preds:
        return (0.0, 0.0)
    rng = random.Random(seed)
    n = len(preds)
    samples: list[float] = []
    for _ in range(n_resamples):
        idx = [rng.randrange(n) for _ in range(n)]
        rs_preds = [preds[i] for i in idx]
        rs_tgts = [targets[i] for i in idx]
        wa, _ = _word_accuracy(rs_preds, rs_tgts)
        samples.append(wa)
    samples.sort()
    lo = samples[int(0.025 * n_resamples)]
    hi = samples[int(0.975 * n_resamples)]
    return (lo, hi)


def _categorize_errors(preds: list[str], targets: list[str]) -> dict[str, int]:
    """Bucket per-token errors so we can see which failure modes dominate.

    Buckets (NFC-normalized, after `normalize_punct` on both sides):
      - missed_diacritic: gold has a diacritic; pred is the strip-diacritic
        equivalent. ("không" vs "khong")
      - wrong_tone: gold + pred both have diacritics but tone marks
        differ on the same base. ("không" vs "khống")
      - base_char: base letters differ (different word). ("không" vs "khá")
      - extra_word: pred has more tokens than gold (insertion)
      - missing_word: pred has fewer tokens than gold (deletion)
    """
    import unicodedata

    def base_letters(tok: str) -> str:
        nfd = unicodedata.normalize("NFD", tok)
        return "".join(c for c in nfd if unicodedata.category(c) != "Mn").lower()

    counts: dict[str, int] = {
        "missed_diacritic": 0,
        "wrong_tone": 0,
        "base_char": 0,
        "extra_word": 0,
        "missing_word": 0,
        "correct": 0,
    }
    for pred, gold in zip(preds, targets, strict=False):
        gold = normalize_punct(unicodedata.normalize("NFC", gold))
        pred = normalize_punct(unicodedata.normalize("NFC", pred))
        gold_toks = gold.split()
        pred_toks = pred.split()
        # Pad whichever is shorter so the zip covers everything.
        gn, pn = len(gold_toks), len(pred_toks)
        if gn > pn:
            counts["missing_word"] += gn - pn
            pred_toks = pred_toks + [""] * (gn - pn)
        elif pn > gn:
            counts["extra_word"] += pn - gn
            gold_toks = gold_toks + [""] * (pn - gn)
        for g, p in zip(gold_toks, pred_toks, strict=False):
            if not g and not p:
                continue
            if g == p:
                counts["correct"] += 1
                continue
            if not g or not p:
                # already accounted for in extra/missing buckets above
                continue
            gb = base_letters(g)
            pb = base_letters(p)
            if gb != pb:
                counts["base_char"] += 1
                continue
            # Same base letters → diacritic-level error.
            # If pred is a strict ASCII strip, call it missed_diacritic.
            pred_is_stripped = p == gb
            if pred_is_stripped and g != gb:
                counts["missed_diacritic"] += 1
            else:
                counts["wrong_tone"] += 1
    return counts


# Hand-curated OOD slices. See benchmarks/data/spell_correction_eval_real/README.md.
EVAL_SLICES = (
    "forum_25",
    "mobile_25",
    "telex_real_25",
    "ocr_25",
    "legal_real_25",
    "news_real_25",
)


def _load_jsonl(path: Path) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        rec = json.loads(line)
        inp = unicodedata.normalize("NFC", rec["input"])
        tgt = unicodedata.normalize("NFC", rec["target"])
        pairs.append((inp, tgt))
    return pairs


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("model_id")
    p.add_argument(
        "--eval-dir",
        type=Path,
        default=REPO / "benchmarks" / "data" / "spell_correction_eval_real",
    )
    p.add_argument("--max-input-length", type=int, default=256)
    p.add_argument("--max-target-length", type=int, default=256)
    p.add_argument("--num-beams", type=int, default=1)
    p.add_argument("--prefix", default="")
    p.add_argument("--warmup", type=int, default=3)
    p.add_argument("--json", type=Path, default=None)
    p.add_argument("--examples", type=int, default=3)
    p.add_argument("--use-slow-tokenizer", action="store_true")
    args = p.parse_args()

    import torch
    from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"device: {device}")
    print(f"loading {args.model_id}...")
    t0 = time.perf_counter()
    tok = AutoTokenizer.from_pretrained(args.model_id, use_fast=not args.use_slow_tokenizer)
    model = AutoModelForSeq2SeqLM.from_pretrained(args.model_id).to(device).eval()
    print(f"  loaded in {time.perf_counter() - t0:.1f}s")

    # Warmup
    if args.warmup > 0:
        any_jsonl = sorted(args.eval_dir.glob("*.jsonl"))[0]
        warm_pair = _load_jsonl(any_jsonl)[0]
        warm_in = args.prefix + warm_pair[0] if args.prefix else warm_pair[0]
        for _ in range(args.warmup):
            x = tok(
                warm_in,
                return_tensors="pt",
                max_length=args.max_input_length,
                truncation=True,
            ).to(device)
            with torch.no_grad():
                model.generate(**x, max_length=args.max_target_length, num_beams=args.num_beams)

    eval_summary: dict[str, dict[str, float]] = {}
    all_preds: list[str] = []
    all_targets: list[str] = []

    for name in EVAL_SLICES:
        path = args.eval_dir / f"{name}.jsonl"
        if not path.exists():
            print(f"skip {name}: no such file")
            continue
        pairs = _load_jsonl(path)
        print(f"\n--- {name} ({len(pairs)} sentences) ---")
        preds: list[str] = []
        targets: list[str] = []
        latencies: list[float] = []
        for noisy, target in pairs:
            inp = args.prefix + noisy if args.prefix else noisy
            t_one = time.perf_counter()
            x = tok(
                inp,
                return_tensors="pt",
                max_length=args.max_input_length,
                truncation=True,
            ).to(device)
            with torch.no_grad():
                out = model.generate(
                    **x, max_length=args.max_target_length, num_beams=args.num_beams
                )
            pred = tok.decode(out[0], skip_special_tokens=True)
            latencies.append(time.perf_counter() - t_one)
            preds.append(pred)
            targets.append(target)
        latencies.sort()
        wa, se = _word_accuracy(preds, targets)
        ci_lo, ci_hi = _bootstrap_ci_word_acc(preds, targets)
        err_counts = _categorize_errors(preds, targets)
        mean_ms = sum(latencies) / len(latencies) * 1000
        p50_ms = latencies[len(latencies) // 2] * 1000
        p95_ms = latencies[max(0, int(len(latencies) * 0.95) - 1)] * 1000
        eval_summary[name] = {
            "n_sentences": len(pairs),
            "word_accuracy": round(wa, 4),
            "word_accuracy_ci95": [round(ci_lo, 4), round(ci_hi, 4)],
            "sentence_exact": round(se, 4),
            "errors": err_counts,
            "mean_ms_per_sentence": round(mean_ms, 2),
            "p50_ms": round(p50_ms, 2),
            "p95_ms": round(p95_ms, 2),
        }
        print(f"  Word accuracy:   {wa:.4f} [95% CI {ci_lo:.4f}-{ci_hi:.4f}]")
        print(f"  Sentence exact:  {se:.4f}")
        print(f"  Latency:         mean {mean_ms:.1f} ms · p50 {p50_ms:.1f} · p95 {p95_ms:.1f}")
        total_errs = sum(v for k, v in err_counts.items() if k != "correct")
        if total_errs > 0:
            print(
                f"  Error breakdown: missed_diac={err_counts['missed_diacritic']} "
                f"wrong_tone={err_counts['wrong_tone']} "
                f"base_char={err_counts['base_char']} "
                f"extra={err_counts['extra_word']} "
                f"missing={err_counts['missing_word']} "
                f"(of {total_errs} errs / {err_counts['correct']} correct)"
            )
        if args.examples > 0:
            for (noisy, _target), pred in list(zip(pairs, preds, strict=False))[: args.examples]:
                gt = normalize_punct(_target)
                pr = normalize_punct(pred)
                tag = "MATCH" if gt == pr else "DIFF "
                print(f"    [{tag}] IN:  {noisy[:120]}")
                print(f"            GT:  {gt[:120]}")
                print(f"            OUT: {pr[:120]}")
        all_preds.extend(preds)
        all_targets.extend(targets)

    # Aggregate across all slices.
    if all_preds:
        wa_all, se_all = _word_accuracy(all_preds, all_targets)
        ci_lo, ci_hi = _bootstrap_ci_word_acc(all_preds, all_targets)
        err_counts = _categorize_errors(all_preds, all_targets)
        eval_summary["__all_real__"] = {
            "n_sentences": len(all_preds),
            "word_accuracy": round(wa_all, 4),
            "word_accuracy_ci95": [round(ci_lo, 4), round(ci_hi, 4)],
            "sentence_exact": round(se_all, 4),
            "errors": err_counts,
        }
        print()
        print(
            f"=== aggregate (n={len(all_preds)}): "
            f"word_acc={wa_all:.4f} [95% CI {ci_lo:.4f}-{ci_hi:.4f}] "
            f"sentence_exact={se_all:.4f} ==="
        )
        total_errs = sum(v for k, v in err_counts.items() if k != "correct")
        if total_errs > 0:
            print(
                f"  Error breakdown: missed_diac={err_counts['missed_diacritic']} "
                f"wrong_tone={err_counts['wrong_tone']} "
                f"base_char={err_counts['base_char']} "
                f"extra={err_counts['extra_word']} "
                f"missing={err_counts['missing_word']}"
            )

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(
            json.dumps(
                {
                    "model_id": args.model_id,
                    "device": device,
                    "eval_dir": "spell_correction_eval_real",
                    "warmup_calls": args.warmup,
                    "num_beams": args.num_beams,
                    "prefix": args.prefix,
                    "eval": eval_summary,
                },
                indent=2,
                ensure_ascii=False,
            )
            + "\n"
        )
        print(f"\nResults: {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

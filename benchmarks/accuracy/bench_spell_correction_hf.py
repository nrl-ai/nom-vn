"""Bench an HF seq2seq spell-correction model on the 8-split eval grid.

Runs the model on every `(noisy, clean)` pair in
`benchmarks/data/spell_correction_eval/*.jsonl` and reports word
accuracy + sentence-exact + ms/sentence per split.

Usage::

    python benchmarks/accuracy/bench_spell_correction_hf.py <model_id>
    python benchmarks/accuracy/bench_spell_correction_hf.py \\
        bmd1905/vietnamese-correction-v2 \\
        --json benchmarks/results/baseline_spell_bmd1905_v2.json

Same metric definition as the diacritic bench (NFC + punctuation
normalization on both sides; word_accuracy on `.split()` tokens after
normalization). Skip-on-import-error patterns let CI runs without
torch / transformers installed simply log "skipped".
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

EVAL_REGISTERS = (
    "business_55_light",
    "business_55_heavy",
    "formal_72_light",
    "formal_72_heavy",
    "conversational_300_light",
    "conversational_300_heavy",
    "literary_800_light",
    "literary_800_heavy",
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
        default=REPO / "benchmarks" / "data" / "spell_correction_eval",
    )
    p.add_argument("--max-input-length", type=int, default=256)
    p.add_argument("--max-target-length", type=int, default=256)
    p.add_argument("--num-beams", type=int, default=1)
    p.add_argument(
        "--prefix",
        default="",
        help="Optional input prefix some models expect (e.g. 'fix: ').",
    )
    p.add_argument("--warmup", type=int, default=3)
    p.add_argument("--json", type=Path, default=None)
    p.add_argument("--examples", type=int, default=2)
    p.add_argument(
        "--use-slow-tokenizer",
        action="store_true",
        help="Force the slow Python tokenizer. Some HF cards (e.g. those built "
        "on older bartpho releases) need this when the fast-tokenizer "
        "conversion fails on `add_prefix_space`.",
    )
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
    for name in EVAL_REGISTERS:
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
        mean_ms = sum(latencies) / len(latencies) * 1000
        p50_ms = latencies[len(latencies) // 2] * 1000
        p95_ms = latencies[max(0, int(len(latencies) * 0.95) - 1)] * 1000
        eval_summary[name] = {
            "n_sentences": len(pairs),
            "word_accuracy": round(wa, 4),
            "sentence_exact": round(se, 4),
            "mean_ms_per_sentence": round(mean_ms, 2),
            "p50_ms": round(p50_ms, 2),
            "p95_ms": round(p95_ms, 2),
        }
        print(f"  Word accuracy:   {wa:.4f}")
        print(f"  Sentence exact:  {se:.4f}")
        print(f"  Latency:         mean {mean_ms:.1f} ms · p50 {p50_ms:.1f} · p95 {p95_ms:.1f}")
        if args.examples > 0:
            for (noisy, target), pred in list(zip(pairs, preds, strict=False))[: args.examples]:
                gt = normalize_punct(target)
                pr = normalize_punct(pred)
                tag = "MATCH" if gt == pr else "DIFF "
                print(f"    [{tag}] IN:  {noisy[:120]}")
                print(f"            GT:  {gt[:120]}")
                print(f"            OUT: {pr[:120]}")

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(
            json.dumps(
                {
                    "model_id": args.model_id,
                    "device": device,
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

"""Bench an LLM (Ollama / OpenAI / Anthropic) on a single-register corpus.

Companion to ``bench_diacritic_hf_udvtb.py``: same comparison
methodology (normalize_punct + word_accuracy on `.split()` tokens)
but the restorer is an `nom.llm.LLM` backend invoked through
`nom.text.fix_diacritics(..., llm=...)`.

Fills LLM x per-register cells in ``docs/training_plan_2026q2.md``
and ``docs/tasks/diacritic-restoration.md`` without forcing readers
to extrapolate from the 55-sentence mixed ``diacritic_eval_v0``
corpus.

Supports two corpus formats:

  * ``.conllu`` (UD-VTB) — extracts ``# text =`` lines.
  * Plain text (Tatoeba, UDHR) — one sentence per line, ``#``
    comment headers stripped.

Usage::

    # UD-VTB literary 800
    python benchmarks/accuracy/bench_diacritic_llm_udvtb.py \\
        --backend ollama --model gemma3:4b \\
        --corpus benchmarks/data/ud_vi_vtb/test.conllu \\
        --json benchmarks/results/baseline_diacritic_gemma3_4b_udvtb.json

    # Tatoeba conversational 300
    python benchmarks/accuracy/bench_diacritic_llm_udvtb.py \\
        --backend ollama --model gemma3:4b \\
        --corpus benchmarks/data/tatoeba_vi/diacritic_eval_300.txt \\
        --json benchmarks/results/baseline_diacritic_gemma3_4b_tatoeba.json
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "benchmarks" / "accuracy"))
sys.path.insert(0, str(REPO / "src"))
from bench_diacritic_hf_udvtb import load_sentences, normalize_punct  # noqa: E402

from nom.text import fix_diacritics, strip_diacritics  # noqa: E402


def _word_accuracy(pred: str, gold: str) -> float:
    pred_n = normalize_punct(pred).split()
    gold_n = normalize_punct(gold).split()
    if not gold_n:
        return 1.0 if not pred_n else 0.0
    n = min(len(pred_n), len(gold_n))
    correct = sum(1 for i in range(n) if pred_n[i] == gold_n[i])
    return correct / len(gold_n)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--corpus",
        type=Path,
        default=Path("benchmarks/data/ud_vi_vtb/test.conllu"),
    )
    p.add_argument("--backend", choices=["ollama", "openai"], default="ollama")
    p.add_argument("--model", required=True)
    p.add_argument("--limit", type=int, default=0, help="Cap sentences (0 = full corpus).")
    p.add_argument("--warmup", type=int, default=2)
    p.add_argument("--json", type=Path, default=None)
    args = p.parse_args()

    if args.corpus.suffix == ".conllu":
        sents = load_sentences(args.corpus)
    else:
        sents = [
            line.strip()
            for line in args.corpus.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.startswith("#")
        ]
    if args.limit:
        sents = sents[: args.limit]
    print(f"corpus: {len(sents)} sentences from {args.corpus}")

    if args.backend == "ollama":
        from nom.llm import Ollama

        llm = Ollama(model=args.model, think=False)
    else:
        from nom.llm import OpenAI

        llm = OpenAI(model=args.model)

    print(f"warming up {args.warmup} call(s) ...")
    for _ in range(args.warmup):
        fix_diacritics("Hop dong nay duoc lap", llm=llm)

    accs: list[float] = []
    lats: list[float] = []
    sentence_exact = 0
    print(f"benching {len(sents)} sentences via {args.backend}:{args.model} ...")
    t_start = time.perf_counter()
    for i, gold in enumerate(sents):
        stripped = strip_diacritics(gold)
        t0 = time.perf_counter()
        try:
            pred = fix_diacritics(stripped, llm=llm)
        except Exception:
            pred = stripped
        lats.append(time.perf_counter() - t0)
        acc = _word_accuracy(pred, gold)
        accs.append(acc)
        if normalize_punct(pred) == normalize_punct(gold):
            sentence_exact += 1
        if (i + 1) % 50 == 0:
            elapsed = time.perf_counter() - t_start
            eta = (len(sents) - i - 1) * elapsed / (i + 1)
            print(
                f"  {i + 1}/{len(sents)} ({elapsed:.0f}s elapsed, "
                f"ETA {eta:.0f}s, mean acc {statistics.mean(accs) * 100:.2f}%)"
            )

    word_acc = statistics.mean(accs) * 100 if accs else 0.0
    sent_ex = sentence_exact / len(sents) * 100 if sents else 0.0
    p50 = statistics.median(lats) if lats else 0.0
    print()
    print(f"=== {args.backend}:{args.model} on {len(sents)} sentences ===")
    print(f"  word_accuracy: {word_acc:.2f}%")
    print(f"  sentence_exact: {sent_ex:.2f}%")
    print(f"  latency p50: {p50 * 1000:.0f} ms · mean: {statistics.mean(lats) * 1000:.0f} ms")

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(
            json.dumps(
                {
                    "backend": args.backend,
                    "model": args.model,
                    "corpus": str(args.corpus),
                    "n_sentences": len(sents),
                    "warmup_calls": args.warmup,
                    "word_accuracy": round(word_acc / 100, 4),
                    "sentence_exact": round(sent_ex / 100, 4),
                    "latency_ms_p50": round(p50 * 1000, 1),
                    "latency_ms_mean": round(statistics.mean(lats) * 1000, 1) if lats else 0.0,
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

"""Vietnamese tokenization accuracy benchmark — nom.text vs underthesea.

Measures word-tokenization quality on the same corpus:

  - **nom.text** (pure-Python rule-based, zero deps) — ships in v0.0.2
  - **underthesea** (CRFsuite, Apache 2.0, optional dep) — runs only if installed

Methodology:
  - Reuse the v0 diacritic-eval corpus (55 VN sentences, CC0).
  - Compute three metrics per sentence:
      - boundary_match_rate: how many sentence-internal token boundaries
        agree between the two tokenizers (Jaccard-like over boundary positions)
      - compound_recall (nom only): of compound words present in our table
        that appear in the sentence, how many did nom merge correctly?
      - throughput: tokens/sec end-to-end
  - We do not assert one is "right" — we measure agreement and per-tokenizer
    behavior. underthesea's CRF and our rule-based approach disagree by design.

Run:
    python benchmarks/accuracy/bench_segment.py
    python benchmarks/accuracy/bench_segment.py --json results/segment.json
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from nom.text import word_tokenize as nom_tokenize
from nom.text._compounds import COMPOUNDS

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_PATH = REPO_ROOT / "benchmarks" / "data" / "diacritic_eval_v0.txt"


def _load_corpus(path: Path) -> list[str]:
    sentences: list[str] = []
    with path.open(encoding="utf-8") as f:
        for raw in f:
            line = raw.rstrip("\n")
            if not line.strip() or line.startswith("#"):
                continue
            sentences.append(line)
    return sentences


def _try_underthesea() -> object | None:
    try:
        import underthesea  # type: ignore[import-not-found]
    except ImportError:
        return None
    return underthesea


def _boundary_positions(tokens: list[str], original: str) -> set[int]:
    """Character positions in `original` where one token ends and the next begins.

    For each token sequence, we compute character indices into the original
    string. A "boundary" is the index AFTER each token (except the last).
    Tokens are joined by whitespace in the original, so we walk through.
    """
    positions: set[int] = set()
    pos = 0
    for tok in tokens[:-1]:
        # Find token in original starting at pos
        idx = original.find(tok, pos)
        if idx < 0:
            continue
        end = idx + len(tok)
        positions.add(end)
        pos = end
    return positions


def _jaccard(a: set[int], b: set[int]) -> float:
    if not a and not b:
        return 1.0
    union = a | b
    if not union:
        return 1.0
    return len(a & b) / len(union)


def _compound_recall(tokens: list[str]) -> tuple[int, int]:
    """How many compound entries from our dict appear correctly merged.

    Returns (correct_merges, total_compound_opportunities).
    A "compound opportunity" is a token in `tokens` whose lowercase form
    matches a key in COMPOUNDS — meaning we successfully merged it.
    """
    matched = sum(1 for t in tokens if t.lower() in COMPOUNDS)
    return matched, len(tokens)


@dataclass
class SentenceResult:
    sentence: str
    nom_tokens: list[str]
    underthesea_tokens: list[str] | None
    boundary_jaccard: float | None
    nom_compound_hits: int


@dataclass
class BenchSummary:
    n_sentences: int
    underthesea_available: bool
    avg_boundary_jaccard: float | None
    nom_throughput_tokens_per_sec: float
    underthesea_throughput_tokens_per_sec: float | None
    total_compound_hits: int


def run() -> tuple[list[SentenceResult], BenchSummary]:
    sentences = _load_corpus(DATA_PATH)
    underthesea = _try_underthesea()

    # Time nom
    nom_start = time.perf_counter()
    nom_runs = [nom_tokenize(s) for s in sentences]
    nom_elapsed = time.perf_counter() - nom_start

    # Type checker: we know fmt='list' returns list[str]
    nom_token_lists: list[list[str]] = [r if isinstance(r, list) else [] for r in nom_runs]

    # Time underthesea (if available)
    un_token_lists: list[list[str]] | None = None
    un_elapsed: float | None = None
    if underthesea is not None:
        un_start = time.perf_counter()
        un_token_lists = [underthesea.word_tokenize(s) for s in sentences]  # type: ignore[attr-defined]
        un_elapsed = time.perf_counter() - un_start

    # Per-sentence metrics
    results: list[SentenceResult] = []
    jaccards: list[float] = []
    total_compound_hits = 0

    for i, sent in enumerate(sentences):
        nom_toks = nom_token_lists[i]
        comp_hits, _ = _compound_recall(nom_toks)
        total_compound_hits += comp_hits

        un_toks = un_token_lists[i] if un_token_lists else None
        jacc = None
        if un_toks is not None:
            nom_b = _boundary_positions(nom_toks, sent)
            un_b = _boundary_positions(un_toks, sent)
            jacc = _jaccard(nom_b, un_b)
            jaccards.append(jacc)

        results.append(
            SentenceResult(
                sentence=sent,
                nom_tokens=nom_toks,
                underthesea_tokens=un_toks,
                boundary_jaccard=jacc,
                nom_compound_hits=comp_hits,
            )
        )

    nom_total_tokens = sum(len(t) for t in nom_token_lists)
    un_total_tokens = sum(len(t) for t in un_token_lists) if un_token_lists else 0

    summary = BenchSummary(
        n_sentences=len(sentences),
        underthesea_available=underthesea is not None,
        avg_boundary_jaccard=round(sum(jaccards) / len(jaccards), 4) if jaccards else None,
        nom_throughput_tokens_per_sec=round(nom_total_tokens / nom_elapsed, 0)
        if nom_elapsed
        else 0.0,
        underthesea_throughput_tokens_per_sec=(
            round(un_total_tokens / un_elapsed, 0) if un_elapsed else None
        ),
        total_compound_hits=total_compound_hits,
    )
    return results, summary


def _print_human(summary: BenchSummary, results: list[SentenceResult], n_examples: int) -> None:
    print(f"Corpus: {summary.n_sentences} sentences from diacritic_eval_v0.txt")
    print()
    print(f"{'metric':>40}  {'value':>16}")
    print("-" * 60)
    print(
        f"{'underthesea installed':>40}  "
        f"{('YES' if summary.underthesea_available else 'NO  (run: pip install nom-vn[nlp])'):>16}"
    )
    if summary.avg_boundary_jaccard is not None:
        print(f"{'Avg boundary agreement (Jaccard)':>40}  {summary.avg_boundary_jaccard:>16.2%}")
    print(f"{'nom.text throughput (tok/s)':>40}  {summary.nom_throughput_tokens_per_sec:>16,.0f}")
    if summary.underthesea_throughput_tokens_per_sec is not None:
        print(
            f"{'underthesea throughput (tok/s)':>40}  "
            f"{summary.underthesea_throughput_tokens_per_sec:>16,.0f}"
        )
    print(f"{'nom.text compound merges (total)':>40}  {summary.total_compound_hits:>16,}")

    if n_examples > 0:
        print()
        print(f"Examples ({min(n_examples, len(results))} sentences):")
        for r in results[:n_examples]:
            print(
                f"  [{r.boundary_jaccard or 0:.0%} boundary agreement · {r.nom_compound_hits} merges]"
            )
            print(f"    SENT:  {r.sentence}")
            print(f"    nom:   {r.nom_tokens}")
            if r.underthesea_tokens is not None:
                print(f"    under: {r.underthesea_tokens}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", type=Path, default=None)
    parser.add_argument("--examples", type=int, default=2)
    args = parser.parse_args(argv)

    results, summary = run()
    _print_human(summary, results, args.examples)

    if args.json is not None:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        with args.json.open("w", encoding="utf-8") as f:
            json.dump(
                {
                    "summary": asdict(summary),
                    "results": [asdict(r) for r in results],
                },
                f,
                ensure_ascii=False,
                indent=2,
            )
        print(f"\nResults written to {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

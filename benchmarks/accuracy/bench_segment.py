"""Vietnamese tokenization accuracy benchmark — nom.text vs underthesea.

Measures word-tokenization quality on the same corpus:

  - **nom.text** (pure-Python rule-based, zero deps) — ships in v0.0.2
  - **underthesea** (CRFsuite, Apache 2.0, optional dep) — runs only if installed

Two corpora are supported:

  - ``diacritic_eval`` (default, 55 sentences) — small, no gold segmentation;
    measures inter-tokenizer agreement (Jaccard) and throughput. Useful for
    smoke-testing.
  - ``ud_vtb`` (CC-BY-SA-4.0, 800 test sentences) — Universal Dependencies
    Vietnamese Treebank. Provides **gold word segmentation**, which lets us
    compute proper precision/recall/F1 against the standard VN benchmark
    convention. Fetch with ``benchmarks/data/_fetch_all.py`` or the curl line
    in ``benchmarks/data/README.md``.

Methodology:
  - For ``ud_vtb`` we compare predicted token spans (start..end character
    indices) against gold spans extracted from the CoNLL-U FORM column.
    A predicted span is correct iff it matches a gold span exactly.
  - Throughput uses warmup + best-of-5 (CLAUDE.md §12).

Run:
    python benchmarks/accuracy/bench_segment.py
    python benchmarks/accuracy/bench_segment.py --corpus ud_vtb --split test
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
UD_VTB_DIR = REPO_ROOT / "benchmarks" / "data" / "ud_vi_vtb"


def _load_corpus(path: Path) -> list[str]:
    sentences: list[str] = []
    with path.open(encoding="utf-8") as f:
        for raw in f:
            line = raw.rstrip("\n")
            if not line.strip() or line.startswith("#"):
                continue
            sentences.append(line)
    return sentences


def _load_conllu(path: Path) -> list[tuple[str, list[str]]]:
    """Parse a CoNLL-U file into [(raw_text, gold_tokens), ...].

    Tokens are read from the FORM column (col 2). Multi-word tokens (e.g.
    ``bắt chuyện``) appear with internal spaces. Multi-word *range* rows
    like ``1-2 ... ...`` (used in some treebanks for clitics) are skipped
    because they re-list the same surface form twice.
    """
    sentences: list[tuple[str, list[str]]] = []
    text: str | None = None
    tokens: list[str] = []
    with path.open(encoding="utf-8") as f:
        for raw in f:
            line = raw.rstrip("\n")
            if not line:
                if text is not None and tokens:
                    sentences.append((text, tokens))
                text, tokens = None, []
                continue
            if line.startswith("# text"):
                # Format: "# text = ..." or "# text=..."
                _, _, val = line.partition("=")
                text = val.strip()
                continue
            if line.startswith("#"):
                continue
            cols = line.split("\t")
            if len(cols) < 2:
                continue
            # Skip multi-word range rows: "1-2", "3-4". Their FORM is the
            # span surface form re-listed; the actual word tokens are the
            # numbered rows that follow.
            if not cols[0].isdigit():
                continue
            tokens.append(cols[1])
    if text is not None and tokens:
        sentences.append((text, tokens))
    return sentences


def _gold_spans(text: str, tokens: list[str]) -> set[tuple[int, int]]:
    """Locate each gold token in the raw text; return its (start, end) spans.

    Uses sequential ``str.find`` with monotone advancing cursor — gold tokens
    are emitted in surface order so we never have to backtrack. Returns the
    set of (start, end) char ranges that the gold segmentation defines.
    """
    spans: set[tuple[int, int]] = set()
    cursor = 0
    for tok in tokens:
        idx = text.find(tok, cursor)
        if idx < 0:
            # Some treebank rows escape characters (e.g. quotes) — bail out
            # silently rather than producing fake spans. Caller tolerates
            # missing tokens by treating them as gold-set misses.
            continue
        end = idx + len(tok)
        spans.add((idx, end))
        cursor = end
    return spans


def _predicted_spans(text: str, tokens: list[str]) -> set[tuple[int, int]]:
    """Same algorithm as ``_gold_spans`` for predicted tokens."""
    return _gold_spans(text, tokens)


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
    # Gold-standard metrics (only populated when corpus has gold segmentation,
    # currently UD_Vietnamese-VTB).
    corpus: str = "diacritic_eval"
    nom_precision: float | None = None
    nom_recall: float | None = None
    nom_f1: float | None = None
    underthesea_precision: float | None = None
    underthesea_recall: float | None = None
    underthesea_f1: float | None = None
    n_gold_tokens: int = 0


def _prf(pred: set[tuple[int, int]], gold: set[tuple[int, int]]) -> tuple[float, float, float]:
    if not pred and not gold:
        return 1.0, 1.0, 1.0
    if not pred or not gold:
        return 0.0, 0.0, 0.0
    tp = len(pred & gold)
    p = tp / len(pred)
    r = tp / len(gold)
    f = (2 * p * r / (p + r)) if (p + r) else 0.0
    return p, r, f


def _time_tokenizer(fn, sentences: list[str], *, warmup_calls: int = 3, runs: int = 5) -> float:
    """Return best-of-N elapsed time over the corpus, after warmup.

    Warmup is critical: underthesea (and any model-backed tokenizer) lazy-loads
    weights on first call. Without warmup we'd be measuring model load, not
    steady-state throughput.
    """
    # Warmup: trigger lazy loads, JIT, allocator, branch prediction.
    for _ in range(warmup_calls):
        for s in sentences[:5]:
            fn(s)
    best = float("inf")
    for _ in range(runs):
        start = time.perf_counter()
        for s in sentences:
            fn(s)
        elapsed = time.perf_counter() - start
        if elapsed < best:
            best = elapsed
    return best


def run(
    corpus: str = "diacritic_eval", split: str = "test"
) -> tuple[list[SentenceResult], BenchSummary]:
    if corpus == "ud_vtb":
        path = UD_VTB_DIR / f"{split}.conllu"
        if not path.exists():
            raise FileNotFoundError(
                f"UD_Vietnamese-VTB {split} split not at {path}. "
                "Fetch from https://github.com/UniversalDependencies/UD_Vietnamese-VTB"
            )
        gold = _load_conllu(path)
        sentences = [text for text, _ in gold]
        gold_token_lists: list[list[str]] | None = [toks for _, toks in gold]
    else:
        sentences = _load_corpus(DATA_PATH)
        gold_token_lists = None
    underthesea = _try_underthesea()

    # Steady-state throughput (warmup + best-of-5).
    nom_elapsed = _time_tokenizer(nom_tokenize, sentences)

    # Get token lists (single pass; not used for timing).
    nom_runs = [nom_tokenize(s) for s in sentences]
    nom_token_lists: list[list[str]] = [r if isinstance(r, list) else [] for r in nom_runs]

    # Time underthesea (if available) — same warmup + best-of-5 protocol.
    un_token_lists: list[list[str]] | None = None
    un_elapsed: float | None = None
    if underthesea is not None:
        un_elapsed = _time_tokenizer(underthesea.word_tokenize, sentences)  # type: ignore[attr-defined]
        un_token_lists = [underthesea.word_tokenize(s) for s in sentences]  # type: ignore[attr-defined]

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

    # Gold-standard P/R/F1 — pooled across the whole corpus, not averaged
    # per-sentence. The conventional VLSP / UD reporting style.
    nom_p = nom_r = nom_f = None
    un_p = un_r = un_f = None
    n_gold_total = 0
    if gold_token_lists is not None:
        nom_pred_pool: set[tuple[int, int, int]] = set()  # (sent_idx, start, end)
        un_pred_pool: set[tuple[int, int, int]] = set()
        gold_pool: set[tuple[int, int, int]] = set()
        for i, (sent, gtoks) in enumerate(zip(sentences, gold_token_lists, strict=False)):
            g_spans = _gold_spans(sent, gtoks)
            n_gold_total += len(g_spans)
            for s, e in g_spans:
                gold_pool.add((i, s, e))
            for s, e in _predicted_spans(sent, nom_token_lists[i]):
                nom_pred_pool.add((i, s, e))
            if un_token_lists is not None:
                for s, e in _predicted_spans(sent, un_token_lists[i]):
                    un_pred_pool.add((i, s, e))
        nom_p, nom_r, nom_f = _prf(nom_pred_pool, gold_pool)
        if un_token_lists is not None:
            un_p, un_r, un_f = _prf(un_pred_pool, gold_pool)

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
        corpus="ud_vtb" if gold_token_lists is not None else "diacritic_eval",
        nom_precision=round(nom_p, 4) if nom_p is not None else None,
        nom_recall=round(nom_r, 4) if nom_r is not None else None,
        nom_f1=round(nom_f, 4) if nom_f is not None else None,
        underthesea_precision=round(un_p, 4) if un_p is not None else None,
        underthesea_recall=round(un_r, 4) if un_r is not None else None,
        underthesea_f1=round(un_f, 4) if un_f is not None else None,
        n_gold_tokens=n_gold_total,
    )
    return results, summary


def _print_human(summary: BenchSummary, results: list[SentenceResult], n_examples: int) -> None:
    src = "diacritic_eval_v0.txt" if summary.corpus == "diacritic_eval" else "UD_Vietnamese-VTB"
    print(f"Corpus: {summary.n_sentences} sentences from {src}")
    if summary.corpus == "ud_vtb":
        print(f"Gold tokens: {summary.n_gold_tokens:,}")
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
    if summary.nom_f1 is not None:
        print()
        print(f"{'Gold-standard P/R/F1 vs UD-VTB':>40}")
        print(f"{'nom.text precision':>40}  {(summary.nom_precision or 0):>16.2%}")
        print(f"{'nom.text recall':>40}  {(summary.nom_recall or 0):>16.2%}")
        print(f"{'nom.text F1':>40}  {(summary.nom_f1 or 0):>16.2%}")
        if summary.underthesea_f1 is not None:
            print(f"{'underthesea precision':>40}  {(summary.underthesea_precision or 0):>16.2%}")
            print(f"{'underthesea recall':>40}  {(summary.underthesea_recall or 0):>16.2%}")
            print(f"{'underthesea F1':>40}  {(summary.underthesea_f1 or 0):>16.2%}")

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
    parser.add_argument(
        "--corpus",
        choices=("diacritic_eval", "ud_vtb"),
        default="diacritic_eval",
        help="diacritic_eval: 55 sentences, no gold (Jaccard agreement only). "
        "ud_vtb: UD_Vietnamese-VTB with gold word segmentation (gives P/R/F1).",
    )
    parser.add_argument(
        "--split",
        choices=("test", "dev", "train"),
        default="test",
        help="UD-VTB split (only used with --corpus ud_vtb).",
    )
    args = parser.parse_args(argv)

    results, summary = run(corpus=args.corpus, split=args.split)
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

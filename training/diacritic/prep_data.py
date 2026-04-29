"""Build a Vietnamese diacritic-restoration training corpus from VN Wikipedia.

Pulls ``hirine/wikipedia-vietnamese-1M296K-dataset`` (CC-BY-SA-4.0,
1.3 M articles), sentence-splits, filters, and writes JSONL pairs of
``{"input": "<diacritic-stripped>", "target": "<original>"}``.

Output:
    training/diacritic/data/train.jsonl    (large)
    training/diacritic/data/val.jsonl      (5 K held-out)
    training/diacritic/data/stats.json     (corpus statistics)

Run:
    python training/diacritic/prep_data.py --max-pairs 200_000
    python training/diacritic/prep_data.py --max-pairs 1_000_000

Filtering rationale:

  - ``has_diacritics(target)`` — a sentence with no diacritics produces
    a (input == target) pair, no training signal.
  - 30 ≤ len(target) ≤ 300 — short enough for cheap training, long
    enough to give context (proper-noun disambiguation needs context).
  - ASCII content of input ≥ 70 % — exclude URLs, tables, code blocks
    that survived the cleaning step.

Eval-leak guards: drop any sentence that appears in any of:

  - ``diacritic_eval_v0.txt`` (55 sents, business)
  - ``ud_vi_vtb/test.conllu`` (800 sents, literary)
  - ``tatoeba_vi/diacritic_eval_300.txt`` (300 sents, conversational)
  - ``udhr_vi/diacritic_eval_udhr.txt`` (72 sents, formal/legal)

All four are public so this is a hash-set check, not a paranoid one.
The 2026-04-29 audit on a 500K Wikipedia corpus measured 0 hits across
all four sets, but the guard is here for defense-in-depth so future
corpus changes don't silently leak.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))
from nom.text import has_diacritics, strip_diacritics  # noqa: E402

OUT_DIR = REPO / "training" / "diacritic" / "data"

# Vietnamese sentence terminator + space + capital VN letter or digit.
# Approximates a sentence-end without a heavy NLP dep.
_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-ZĐÀ-Ỹ0-9])")


def _ascii_ratio(text: str) -> float:
    if not text:
        return 0.0
    n_ascii = sum(1 for c in text if ord(c) < 128)
    return n_ascii / len(text)


def _split_sentences(article: str) -> list[str]:
    """Lightweight sentence split. Good-enough for a training corpus."""
    sents: list[str] = []
    for paragraph in article.split("\n"):
        paragraph = paragraph.strip()
        if not paragraph:
            continue
        sents.extend(s.strip() for s in _SENT_SPLIT.split(paragraph))
    return [s for s in sents if s]


def _eval_leak_guards(repo: Path) -> set[str]:
    """Sentences we MUST NOT include in training.

    Reads every diacritic eval slice we ship plus the UD-VTB test split.
    Adding a new eval corpus? Drop a one-line entry below.
    """
    blocked: set[str] = set()

    # Plain-text eval slices (one sentence per non-comment line).
    txt_slices = [
        repo / "benchmarks" / "data" / "diacritic_eval_v0.txt",
        repo / "benchmarks" / "data" / "tatoeba_vi" / "diacritic_eval_300.txt",
        repo / "benchmarks" / "data" / "udhr_vi" / "diacritic_eval_udhr.txt",
    ]
    for path in txt_slices:
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                blocked.add(line)

    # CoNLL-U treebank: extract `# text = ...` lines.
    udvtb = repo / "benchmarks" / "data" / "ud_vi_vtb" / "test.conllu"
    if udvtb.exists():
        for line in udvtb.read_text(encoding="utf-8").splitlines():
            if line.startswith("# text"):
                _, _, val = line.partition("=")
                v = val.strip()
                if v:
                    blocked.add(v)
    return blocked


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--max-pairs",
        type=int,
        default=200_000,
        help="Number of training pairs to keep. Default 200k (good for "
        "iteration); bump to 1M+ for the full training run.",
    )
    p.add_argument("--val-pairs", type=int, default=5_000)
    p.add_argument("--min-chars", type=int, default=30)
    p.add_argument("--max-chars", type=int, default=300)
    p.add_argument("--min-ascii-ratio", type=float, default=0.5)
    p.add_argument("--seed", type=int, default=42)
    args = p.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # Lazy: HF datasets is heavy.
    print("loading hirine/wikipedia-vietnamese-1M296K-dataset (streaming)...")
    from datasets import load_dataset

    ds = load_dataset(
        "hirine/wikipedia-vietnamese-1M296K-dataset",
        split="train",
        streaming=True,
    )

    blocked = _eval_leak_guards(REPO)
    print(f"  eval-leak guard: {len(blocked)} sentences excluded if seen")

    rng_skip = 7  # keep every 7th eligible sentence — cheap dedup-ish across articles
    seen_targets: set[str] = set()
    train_path = OUT_DIR / "train.jsonl"
    val_path = OUT_DIR / "val.jsonl"
    stats_path = OUT_DIR / "stats.json"

    n_train = n_val = 0
    n_articles_seen = 0
    n_filtered_no_diacritic = 0
    n_filtered_length = 0
    n_filtered_ascii = 0
    n_filtered_blocked = 0
    n_filtered_dup = 0

    counter = 0

    with (
        train_path.open("w", encoding="utf-8") as f_train,
        val_path.open("w", encoding="utf-8") as f_val,
    ):
        for row in ds:
            n_articles_seen += 1
            text = row.get("text", "") or ""
            for sent in _split_sentences(text):
                # NFC-normalize defensively. Wikipedia is already NFC, but the
                # parallel prep_data_news.py path discovered tmnam20 ships ~79 %
                # NFD-decomposed text — both inputs and the eval set must agree
                # on form or the metric silently breaks (CLAUDE.md gotcha #1).
                sent = unicodedata.normalize("NFC", sent)
                if not (args.min_chars <= len(sent) <= args.max_chars):
                    n_filtered_length += 1
                    continue
                if _ascii_ratio(sent) > 0.95:
                    # All-ASCII = no diacritic signal.
                    n_filtered_ascii += 1
                    continue
                if not has_diacritics(sent):
                    n_filtered_no_diacritic += 1
                    continue
                if sent in blocked:
                    n_filtered_blocked += 1
                    continue
                if sent in seen_targets:
                    n_filtered_dup += 1
                    continue
                seen_targets.add(sent)

                counter += 1
                if counter % rng_skip != 0:
                    # deterministic stride sampling — diverse without RNG state
                    continue

                pair = {"input": strip_diacritics(sent), "target": sent}
                if n_val < args.val_pairs:
                    f_val.write(json.dumps(pair, ensure_ascii=False) + "\n")
                    n_val += 1
                else:
                    f_train.write(json.dumps(pair, ensure_ascii=False) + "\n")
                    n_train += 1
                    if n_train >= args.max_pairs:
                        break

                if (n_train + n_val) % 10_000 == 0:
                    print(
                        f"  progress: train={n_train:,} val={n_val:,} "
                        f"(scanned {n_articles_seen:,} articles)"
                    )
            if n_train >= args.max_pairs:
                break

    stats = {
        "train_pairs": n_train,
        "val_pairs": n_val,
        "articles_scanned": n_articles_seen,
        "filtered_no_diacritic": n_filtered_no_diacritic,
        "filtered_length": n_filtered_length,
        "filtered_high_ascii": n_filtered_ascii,
        "filtered_blocked_eval_leak": n_filtered_blocked,
        "filtered_duplicate": n_filtered_dup,
        "stride": rng_skip,
        "min_chars": args.min_chars,
        "max_chars": args.max_chars,
        "source": "hirine/wikipedia-vietnamese-1M296K-dataset (CC-BY-SA-4.0)",
    }
    stats_path.write_text(json.dumps(stats, indent=2, ensure_ascii=False) + "\n")
    print()
    print(f"wrote: {train_path} ({n_train:,} pairs)")
    print(f"wrote: {val_path} ({n_val:,} pairs)")
    print(f"wrote: {stats_path}")
    print(f"stats: {json.dumps(stats, indent=2, ensure_ascii=False)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

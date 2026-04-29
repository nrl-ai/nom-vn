"""Generate diacritic-restoration training pairs from a VN news corpus.

Companion to ``prep_data.py``. Streams
[`tmnam20/Vietnamese-News-dedup`](https://huggingface.co/datasets/tmnam20/Vietnamese-News-dedup)
(CC-BY-4.0, ~10-100 M deduped news articles) and emits
``(stripped_input, target)`` pairs to ``data/train_news.jsonl``.

Why a separate script: the existing prep_data.py is hard-pinned to
``hirine/wikipedia-vietnamese-1M296K-dataset`` and applies a
deterministic stride-7 over every Wikipedia article. Adding a second
source needs different streaming semantics (news articles are shorter
on average, no stride needed) and a different default budget.

Used by v0.2.26 mixed-source experiment::

    # 1. Generate news pairs (target 150K)
    python training/diacritic/prep_data_news.py --max-pairs 150_000

    # 2. Subsample the existing Wiki corpus to 350K (deterministic)
    python -c "
    import json, random
    random.seed(42)
    lines = open('training/diacritic/data/train.jsonl').readlines()
    random.shuffle(lines)
    with open('training/diacritic/data/train_wiki_350k.jsonl', 'w') as f:
        f.writelines(lines[:350_000])
    " && wc -l training/diacritic/data/train_wiki_350k.jsonl

    # 3. Concatenate and shuffle to interleave
    cat training/diacritic/data/train_wiki_350k.jsonl \\
        training/diacritic/data/train_news.jsonl \\
      | shuf --random-source=<(head -c 1M /dev/urandom) \\
      > training/diacritic/data/train_mixed.jsonl

The eval-leak guard reads from the same set of held-out corpora as
``prep_data.py``: business / literary / conversational / formal slices.
"""

from __future__ import annotations

import argparse
import json
import sys
import unicodedata
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))
from nom.text import has_diacritics, strip_diacritics  # noqa: E402

# Reuse the eval-leak guard logic — we don't want to double-maintain.
sys.path.insert(0, str(REPO / "training" / "diacritic"))
from prep_data import _ascii_ratio, _eval_leak_guards, _split_sentences  # noqa: E402

OUT_DIR = REPO / "training" / "diacritic" / "data"

# Field names to try when extracting article text from a streamed row.
# tmnam20 deduped uses "text"; older variants use "content" or "article".
_TEXT_FIELDS = ("text", "content", "article", "body")


def _row_text(row: dict) -> str:
    for f in _TEXT_FIELDS:
        v = row.get(f)
        if isinstance(v, str) and v.strip():
            return v
    return ""


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--dataset-id",
        default="tmnam20/Vietnamese-News-dedup",
        help="HF dataset id (default: tmnam20/Vietnamese-News-dedup, CC-BY-4.0).",
    )
    p.add_argument("--split", default="train")
    p.add_argument(
        "--max-pairs",
        type=int,
        default=150_000,
        help="Number of training pairs to keep (target 150K for the v0.2.26 mix).",
    )
    p.add_argument(
        "--output",
        type=Path,
        default=OUT_DIR / "train_news.jsonl",
    )
    p.add_argument("--min-chars", type=int, default=30)
    p.add_argument("--max-chars", type=int, default=300)
    p.add_argument(
        "--stride",
        type=int,
        default=3,
        help="Keep every Nth eligible sentence. News articles are denser than "
        "wiki — stride=3 is good (vs prep_data.py's stride=7 for wiki).",
    )
    args = p.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    print(f"loading {args.dataset_id} (streaming, split={args.split})...")
    from datasets import load_dataset

    ds = load_dataset(args.dataset_id, split=args.split, streaming=True)

    blocked = _eval_leak_guards(REPO)
    print(f"  eval-leak guard: {len(blocked)} sentences excluded if seen")

    seen_targets: set[str] = set()
    n_pairs = 0
    n_articles = 0
    n_filtered_no_diac = 0
    n_filtered_length = 0
    n_filtered_ascii = 0
    n_filtered_blocked = 0
    n_filtered_dup = 0
    n_filtered_empty_row = 0
    counter = 0

    with args.output.open("w", encoding="utf-8") as f:
        for row in ds:
            n_articles += 1
            text = _row_text(row)
            if not text:
                n_filtered_empty_row += 1
                continue
            for sent in _split_sentences(text):
                # NFC-normalize. tmnam20 news ships ~79 % NFD-decomposed text,
                # which silently broke v0.2.26 (caught 2026-04-30 — see
                # CLAUDE.md gotcha #1: NFC vs NFD). The base ViT5 SentencePiece
                # tokenizer is NFC; training on NFD targets makes the model
                # emit decomposed forms that don't byte-match NFC-normalized
                # eval targets.
                sent = unicodedata.normalize("NFC", sent)
                # News corpora often contain timestamps / image captions /
                # boilerplate. Strip whitespace + bullet/separator characters.
                sent = sent.strip().strip("|>:")
                if not (args.min_chars <= len(sent) <= args.max_chars):
                    n_filtered_length += 1
                    continue
                if _ascii_ratio(sent) > 0.95:
                    n_filtered_ascii += 1
                    continue
                if not has_diacritics(sent):
                    n_filtered_no_diac += 1
                    continue
                if sent in blocked:
                    n_filtered_blocked += 1
                    continue
                if sent in seen_targets:
                    n_filtered_dup += 1
                    continue
                seen_targets.add(sent)

                counter += 1
                if counter % args.stride != 0:
                    continue

                pair = {"input": strip_diacritics(sent), "target": sent}
                f.write(json.dumps(pair, ensure_ascii=False) + "\n")
                n_pairs += 1
                if n_pairs >= args.max_pairs:
                    break

                if n_pairs % 10_000 == 0:
                    print(f"  progress: {n_pairs:,} pairs (scanned {n_articles:,} articles)")
            if n_pairs >= args.max_pairs:
                break

    stats_path = args.output.parent / (args.output.stem + "_stats.json")
    stats = {
        "source": args.dataset_id,
        "split": args.split,
        "pairs": n_pairs,
        "articles_scanned": n_articles,
        "filtered_empty_row": n_filtered_empty_row,
        "filtered_no_diacritic": n_filtered_no_diac,
        "filtered_length": n_filtered_length,
        "filtered_high_ascii": n_filtered_ascii,
        "filtered_blocked_eval_leak": n_filtered_blocked,
        "filtered_duplicate": n_filtered_dup,
        "stride": args.stride,
        "min_chars": args.min_chars,
        "max_chars": args.max_chars,
    }
    stats_path.write_text(json.dumps(stats, indent=2, ensure_ascii=False) + "\n")
    print(f"\nwrote {n_pairs:,} pairs to {args.output}")
    print(f"wrote stats to {stats_path}")
    if n_pairs < args.max_pairs:
        print(
            f"  WARNING: requested {args.max_pairs:,} but only got {n_pairs:,} — "
            "increase the dataset size budget or relax the filters."
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())

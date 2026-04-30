"""Generate diacritic-restoration training pairs from a VN legal corpus.

Companion to ``prep_data.py`` and ``prep_data_news.py``. Streams
[`GreenNode/zalo-ai-legal-text-retrieval-vn`](https://huggingface.co/datasets/GreenNode/zalo-ai-legal-text-retrieval-vn)
(MIT license, ~61K legal articles from the Zalo AI Legal Text
Retrieval challenge — circulars, decrees, laws, decisions from the
Vietnamese National Assembly and ministries) and emits
``(stripped_input, target)`` pairs to ``data/train_legal.jsonl``.

Why this dataset (vs ``th1nhng0/vietnamese-legal-documents``): the
th1nhng0 mirror ships HTML in parquet columns that exceed pyarrow's
2 GB cast limit on streaming — the datasets library currently fails on
``th1nhng0/vietnamese-legal-documents`` with
``ArrowInvalid: input array too large``. The Zalo mirror is plain text,
already sized for streaming, MIT-licensed, and we already use it for
RAG benchmarks (so it's a known-trusted source). 61K articles covers
the legal register comfortably for our 100K-pair budget.

Why a separate script: legal Vietnamese has a distinct register
(``căn cứ``, ``điều``, ``khoản``, ``nghị định``, formal address forms)
that neither wiki nor news fully covers — adding it boosts coverage on
business / legal text, where spell correction sees the most production
use.

Used by v0.2.29 multi-register experiment::

    # 1. Generate legal pairs (target 100K)
    python training/diacritic/prep_data_legal.py --max-pairs 100_000

    # 2. Concatenate with existing Wiki + news mixed corpus
    cat training/diacritic/data/train_mixed_nfc.jsonl \\
        training/diacritic/data/train_legal_nfc.jsonl \\
      | shuf --random-source=<(head -c 1M /dev/urandom) \\
      > training/diacritic/data/train_v2_nfc.jsonl

The eval-leak guard reuses the four held-out slices
(``diacritic_eval_v0.txt`` / ``ud_vi_vtb`` / ``tatoeba_vi`` /
``udhr_vi``).
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

sys.path.insert(0, str(REPO / "training" / "diacritic"))
from prep_data import _ascii_ratio, _eval_leak_guards, _split_sentences  # noqa: E402

OUT_DIR = REPO / "training" / "diacritic" / "data"


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--dataset-id",
        default="GreenNode/zalo-ai-legal-text-retrieval-vn",
        help="HF dataset id (default: GreenNode/zalo-ai-legal-text-retrieval-vn, MIT).",
    )
    p.add_argument(
        "--config",
        default="corpus",
        help="Dataset config that contains body text (default: 'corpus').",
    )
    p.add_argument(
        "--split",
        default="test",
        help="Dataset split. Zalo Legal QA only ships a 'test' split for the "
        "corpus config, but it covers all 61K articles.",
    )
    p.add_argument(
        "--max-pairs",
        type=int,
        default=100_000,
        help="Number of training pairs to keep (target 100K for v0.2.29 mix).",
    )
    p.add_argument(
        "--output",
        type=Path,
        default=OUT_DIR / "train_legal.jsonl",
    )
    p.add_argument("--min-chars", type=int, default=30)
    p.add_argument("--max-chars", type=int, default=300)
    p.add_argument(
        "--stride",
        type=int,
        default=2,
        help="Keep every Nth eligible sentence. Legal docs are dense and "
        "highly repetitive (boilerplate phrases) — stride=2 cuts dup rate.",
    )
    args = p.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    print(f"loading {args.dataset_id} (streaming, config={args.config}, split={args.split})...")
    from datasets import load_dataset

    ds = load_dataset(args.dataset_id, args.config, split=args.split, streaming=True)

    blocked = _eval_leak_guards(REPO)
    print(f"  eval-leak guard: {len(blocked)} sentences excluded if seen")

    seen_targets: set[str] = set()
    n_pairs = 0
    n_docs = 0
    n_filtered_no_diac = 0
    n_filtered_length = 0
    n_filtered_ascii = 0
    n_filtered_blocked = 0
    n_filtered_dup = 0
    n_filtered_empty_doc = 0
    counter = 0

    with args.output.open("w", encoding="utf-8") as f:
        for row in ds:
            n_docs += 1
            text = row.get("text") or ""
            title = row.get("title") or ""
            if title:
                # Title is often a separate clause; include it as a sentence.
                text = f"{title}. {text}"
            if not text.strip():
                n_filtered_empty_doc += 1
                continue
            for sent in _split_sentences(text):
                sent = unicodedata.normalize("NFC", sent)
                sent = sent.strip().strip("|>:•·")
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
                    print(f"  progress: {n_pairs:,} pairs (scanned {n_docs:,} docs)")
            if n_pairs >= args.max_pairs:
                break

    stats_path = args.output.parent / (args.output.stem + "_stats.json")
    stats = {
        "source": args.dataset_id,
        "config": args.config,
        "split": args.split,
        "license": "MIT (Zalo AI Legal Text Retrieval challenge)",
        "pairs": n_pairs,
        "docs_scanned": n_docs,
        "filtered_empty_doc": n_filtered_empty_doc,
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
            "the source has ~61K articles, so 100K is the realistic ceiling. "
            "Lower stride or relax filters if you need more."
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())

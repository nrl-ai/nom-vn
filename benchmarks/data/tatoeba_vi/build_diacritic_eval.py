"""Sample a deterministic conversational-register diacritic eval slice.

Reads ``vie_sentences_sample_3k.tsv`` (Tatoeba CC-BY 2.0 FR, seed=42 sample
of the canonical VI dump), filters to sentences with diacritics and a usable
length, dedupes case-insensitively, and writes the first N qualifying lines
to ``diacritic_eval_300.txt`` for the diacritic-restoration benches.

Why a separate slice and not the full 3k sample: the existing benches run a
single sentence at a time (no batching) at ~150 ms / sent on a 3080. 300
sentences ≈ 45 s wall-clock; 3000 ≈ 7.5 min. 300 is enough for a stable
register signal (diacritic_eval_v0 hits register signals at 13-15 sents per
register) without bleeding GPU minutes.
"""

from __future__ import annotations

import argparse
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, "src")
from nom.text import has_diacritics


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--src",
        type=Path,
        default=Path("benchmarks/data/tatoeba_vi/vie_sentences_sample_3k.tsv"),
    )
    p.add_argument(
        "--dst",
        type=Path,
        default=Path("benchmarks/data/tatoeba_vi/diacritic_eval_300.txt"),
    )
    p.add_argument("--n", type=int, default=300)
    p.add_argument("--min-len", type=int, default=20)
    p.add_argument("--max-len", type=int, default=180)
    args = p.parse_args()

    seen: set[str] = set()
    out: list[str] = []
    for raw in args.src.read_text(encoding="utf-8").splitlines():
        if "\t" not in raw:
            continue
        parts = raw.split("\t", 2)
        if len(parts) < 3:
            continue
        sent = unicodedata.normalize("NFC", parts[2].strip())
        if not (args.min_len <= len(sent) <= args.max_len):
            continue
        if not has_diacritics(sent):
            continue
        key = sent.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(sent)
        if len(out) >= args.n:
            break

    args.dst.parent.mkdir(parents=True, exist_ok=True)
    header = (
        "# Tatoeba VI conversational register — diacritic restoration eval slice\n"
        "# Source: vie_sentences_sample_3k.tsv (CC-BY 2.0 FR, Tatoeba)\n"
        f"# Filter: has_diacritics, {args.min_len} <= len <= {args.max_len}, "
        "case-insensitive dedup\n"
        f"# Sample size: {len(out)}\n"
    )
    args.dst.write_text(header + "\n".join(out) + "\n", encoding="utf-8")
    print(f"wrote {len(out)} sentences to {args.dst}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

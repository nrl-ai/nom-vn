"""Sentence-split UDHR Vietnamese into a diacritic-restoration eval slice.

UDHR is the Universal Declaration of Human Rights, public domain, formal /
legal-prose register. ~5 KB body text after stripping the header and
metadata block. Splitting on sentence terminators yields ~70-100 usable
sentences after the same has_diacritics + length filter we apply
elsewhere.

Why a 4th register? Toshiiiii1's published numbers cover modern business
(97.81 %) and classical literary (89.40 %); the 2026-04-29 Tatoeba bench
adds conversational (93.77 %). UDHR sits in formal / legal-prose territory
that none of the others cover well — closer in vocabulary to the legal_vi
corpus we use for retrieval. This closes the 4-register matrix without
introducing a heavy new dependency.
"""

from __future__ import annotations

import argparse
import re
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, "src")
from nom.text import has_diacritics

# Drop the header-block lines (Wikisource boilerplate, bullets, all-caps
# headers, the 24722-token line). Body content begins at the first
# "Lời nói đầu" / numbered-article paragraph.
_NOISE = re.compile(
    r"^(•|TUYÊN NGÔN|VỀ NHÂN QUYỀN|Tuyên ngôn|Lời nói đầu|"
    r"Điều \d+|24722|của Đại hội|—|Do đó,|$)",
)


def split_sentences(text: str) -> list[str]:
    text = unicodedata.normalize("NFC", text)
    out: list[str] = []
    for line in text.splitlines():
        if not line.strip() or _NOISE.match(line.strip()):
            continue
        for s in re.split(r"(?<=[.!?])\s+", line.strip()):
            s = s.strip(" \t")
            if s:
                out.append(s)
    return out


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--src",
        type=Path,
        default=Path("benchmarks/data/udhr_vi/udhr_vi.txt"),
    )
    p.add_argument(
        "--dst",
        type=Path,
        default=Path("benchmarks/data/udhr_vi/diacritic_eval_udhr.txt"),
    )
    p.add_argument("--min-len", type=int, default=30)
    p.add_argument("--max-len", type=int, default=300)
    args = p.parse_args()

    sents = split_sentences(args.src.read_text(encoding="utf-8"))
    seen: set[str] = set()
    out: list[str] = []
    for sent in sents:
        if not (args.min_len <= len(sent) <= args.max_len):
            continue
        if not has_diacritics(sent):
            continue
        key = sent.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(sent)

    args.dst.parent.mkdir(parents=True, exist_ok=True)
    header = (
        "# UDHR Vietnamese — formal/legal-prose register diacritic eval slice\n"
        "# Source: udhr_vi.txt (public domain, Wikisource translation)\n"
        f"# Filter: has_diacritics, {args.min_len} <= len <= {args.max_len}, "
        "case-insensitive dedup\n"
        f"# Sample size: {len(out)}\n"
    )
    args.dst.write_text(header + "\n".join(out) + "\n", encoding="utf-8")
    print(f"wrote {len(out)} sentences to {args.dst}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

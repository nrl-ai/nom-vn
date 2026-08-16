"""Build the document-furniture slice of the real-world spell-correction eval.

Why this slice exists
---------------------

Our spell-correction training corpus is sentence-segmented, so document
furniture (letterheads, all-caps titles, form labels, signature blocks)
was filtered out during construction. The models therefore carry no
correction prior for that surface form and echo it back unchanged. A user
reported exactly this: ``Độc lập - Tự do - Hạnh phục`` came back
uncorrected while the same error in running prose is fixed.

The published eval missed the whole category because only 2 of its 150
sentences are heading-shaped. This generator closes that measurement gap.

Error model
-----------

The slice injects **real-word tone confusion**: a syllable is replaced by a
different tone variant that is *itself* a valid Vietnamese syllable. This is
the hard class, because no dictionary can flag it. Only context can.

Where several substitutions are possible, the generator picks the most
*adverse* one, meaning the wrong form is more frequent in ordinary
Vietnamese than the intended form. That is the condition under which the
failure actually reproduces: an adverse frequency prior AND heading layout
together. Neither alone is enough.

One error per line keeps word accuracy interpretable against sentence
length.

Sources (all committed, no network needed)
------------------------------------------

- Headings: ``benchmarks/data/vn_documents_ocr_v2/metadata.jsonl``.
  9 real signed government scans from chinhphu.vn / hanoi.gov.vn
  (Public Domain, Luật SHTT VN Điều 15) plus CC0 business templates.
- Syllable frequencies: ``benchmarks/data/wiki_vi/articles.jsonl``
  (CC-BY-SA 4.0) and ``benchmarks/data/tatoeba_vi/vie_sentences.tsv.bz2``
  (CC-BY 2.0 FR).

Run::

    python benchmarks/data/furniture_vi/_generate.py

Writes ``benchmarks/data/spell_correction_eval_real/furniture_50.jsonl``.
"""

from __future__ import annotations

import argparse
import bz2
import json
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "src"))

from nom.text.heading import is_heading  # noqa: E402

DOCS_META = REPO / "benchmarks" / "data" / "vn_documents_ocr_v2" / "metadata.jsonl"
WIKI = REPO / "benchmarks" / "data" / "wiki_vi" / "articles.jsonl"
TATOEBA = REPO / "benchmarks" / "data" / "tatoeba_vi" / "vie_sentences.tsv.bz2"
OUT = REPO / "benchmarks" / "data" / "spell_correction_eval_real" / "furniture_50.jsonl"

_TONE_MARKS = frozenset("̣̀́̃̉")
_ALPHA = re.compile(r"^[^\W\d_]+$", re.UNICODE)
_WORD = re.compile(r"[^\W\d_]+", re.UNICODE)

# Minimum corpus count for a surface form to count as a real Vietnamese
# syllable. Filters OCR debris and rare proper nouns.
MIN_FREQ = 20


def nfc(text: str) -> str:
    return unicodedata.normalize("NFC", text)


def detone(word: str) -> str:
    """Strip tone marks only, preserving vowel modifiers and ``đ``."""
    decomposed = unicodedata.normalize("NFD", word)
    return nfc("".join(c for c in decomposed if c not in _TONE_MARKS))


def build_lexicon() -> Counter[str]:
    """Count lowercase Vietnamese syllables across the committed corpora."""
    freq: Counter[str] = Counter()

    if WIKI.exists():
        with WIKI.open(encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue
                text = record.get("text") or record.get("content") or ""
                freq.update(w.lower() for w in _WORD.findall(nfc(text)))

    if TATOEBA.exists():
        with bz2.open(TATOEBA, "rt", encoding="utf-8") as handle:
            for line in handle:
                parts = line.rstrip("\n").split("\t")
                if parts:
                    freq.update(w.lower() for w in _WORD.findall(nfc(parts[-1])))

    return freq


def build_tone_groups(freq: Counter[str]) -> dict[str, list[str]]:
    """Map detoned form -> surface forms sharing it, most frequent first."""
    groups: dict[str, list[str]] = {}
    for word, count in freq.items():
        if count < MIN_FREQ or not _ALPHA.match(word):
            continue
        groups.setdefault(detone(word), []).append(word)
    for key, forms in groups.items():
        groups[key] = sorted(forms, key=lambda w: -freq[w])
    return {k: v for k, v in groups.items() if len(v) > 1}


def load_headings() -> list[tuple[str, str]]:
    """Return (heading, doc_id) for every heading-shaped line, deduplicated."""
    if not DOCS_META.exists():
        raise SystemExit(
            f"missing {DOCS_META}. Generate it first with "
            "`python benchmarks/data/vn_documents_ocr_v2/_generate.py`."
        )
    seen: set[str] = set()
    out: list[tuple[str, str]] = []
    with DOCS_META.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            for raw in (record.get("text") or "").split("\n"):
                heading = nfc(raw.strip())
                if not heading or heading in seen or not is_heading(heading):
                    continue
                seen.add(heading)
                out.append((heading, record.get("doc_id", "?")))
    return out


def inject_error(
    heading: str, groups: dict[str, list[str]], freq: Counter[str]
) -> tuple[str, str] | None:
    """Swap one syllable for a more frequent same-detone variant.

    Returns ``(noisy, replaced_token)`` or None when no adverse substitution
    exists for this heading.
    """
    tokens = heading.split()
    best: tuple[float, int, str] | None = None
    for index, token in enumerate(tokens):
        if not _ALPHA.match(token):
            continue
        lowered = token.lower()
        forms = groups.get(detone(lowered))
        if not forms:
            continue
        own = freq.get(lowered, 0)
        if own <= 0:
            continue
        for candidate in forms:
            if candidate == lowered:
                continue
            ratio = freq[candidate] / own
            # Adverse only: the wrong form must outrank the right one.
            if ratio <= 1.0:
                continue
            if best is None or ratio > best[0]:
                best = (ratio, index, candidate)

    if best is None:
        return None

    _, index, candidate = best
    original = tokens[index]
    if original.isupper() and len(original) > 1:
        replacement = candidate.upper()
    elif original[:1].isupper():
        replacement = candidate[:1].upper() + candidate[1:]
    else:
        replacement = candidate
    noisy = list(tokens)
    noisy[index] = replacement
    return nfc(" ".join(noisy)), original


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max-pairs", type=int, default=50)
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args()

    print("building syllable lexicon from committed corpora...")
    freq = build_lexicon()
    groups = build_tone_groups(freq)
    print(f"  {len(freq):,} surface forms, {len(groups):,} tone-ambiguous groups")

    headings = load_headings()
    print(f"  {len(headings):,} unique heading-shaped lines")

    pairs: list[dict[str, str]] = []
    for heading, doc_id in headings:
        result = inject_error(heading, groups, freq)
        if result is None:
            continue
        noisy, _ = result
        if noisy == heading:
            continue
        pairs.append({"input": noisy, "target": heading, "doc_id": doc_id})
        if len(pairs) >= args.max_pairs:
            break

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as handle:
        for pair in pairs:
            handle.write(json.dumps(pair, ensure_ascii=False) + "\n")

    print(f"\nwrote {args.out} ({len(pairs)} pairs)")
    for pair in pairs[:8]:
        print(f"  {pair['input']!r}")
        print(f"    -> {pair['target']!r}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

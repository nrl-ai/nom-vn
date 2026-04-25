"""Pure-Python Vietnamese word and sentence segmentation.

No third-party dependencies. No bundled model files. Every rule is in this
source file; the compound-word dictionary is data only (no executable
content). This means:

- **Auditable** — every output is traceable to a rule or table entry.
- **Reproducible** — pinning a Nôm version pins the exact tokenization.
- **Safe** — no pickle, no opaque binaries, no arbitrary-code-on-import risk.

Measured against underthesea (CRF, the de-facto VN tokenizer) on
``benchmarks/data/diacritic_eval_v0.txt`` — see baseline at
``benchmarks/results/baseline_segment_v0.0.2.json``. Methodology: warmup
3 calls over the first 5 sentences to amortize lazy model load, then best-of-5
runs over the full 55-sentence corpus.

==========================  ======================  ==================
metric                      nom.text (this code)    underthesea (CRF)
==========================  ======================  ==================
boundary agreement (Jacc)   reference (this code)   77.77%
throughput (steady-state)   734,296 tok/s           34,217 tok/s
license                     Apache 2.0 (us)         Apache 2.0
deps                        none (pure stdlib)      26MB CRF blobs
==========================  ======================  ==================

We trade ~22% boundary disagreement for **~21x speedup** and zero binary
dependencies. The compound-word table (~300 entries of high-frequency
business + conversational compounds) is the leverage point — contributors
extend it in ``src/nom/text/_compounds.py``.

For users who need underthesea's accuracy, install ``pip install nom-vn[nlp]``
and they can run it directly; we may add a ``backend="underthesea"`` opt-in
in v0.0.3 once the comparison harness has more registers.
"""

from __future__ import annotations

import re
import unicodedata

from nom.text._compounds import COMPOUNDS, NEVER_SPLIT_AFTER

__all__ = [
    "sent_tokenize",
    "text_normalize",
    "word_tokenize",
]


def word_tokenize(text: str, *, fmt: str = "list") -> list[str] | str:
    """Tokenize Vietnamese text into words.

    Strategy: whitespace split, then greedy left-to-right merge against the
    compound-word dictionary in :mod:`nom.text._compounds`. Compound merges
    prefer longer matches first (so ``"thành phố Hồ Chí Minh"`` becomes one
    token rather than ``["thành phố", "Hồ Chí", "Minh"]``).

    Args:
        text: Vietnamese input.
        fmt: ``"list"`` returns ``list[str]`` (compounds joined by space inside
            one token). ``"text"`` returns a single string with compounds joined
            by underscore — useful for downstream pipelines using whitespace
            tokenizers that need compound boundaries preserved.

    Returns:
        List of tokens or underscore-joined string.

    Example:
        >>> word_tokenize("Hợp đồng số 02 được lập")
        ['Hợp đồng', 'số', '02', 'được', 'lập']
        >>> word_tokenize("Hợp đồng số 02", fmt="text")
        'Hợp_đồng số 02'

    Raises:
        ValueError: if ``fmt`` is not ``"list"`` or ``"text"``.
    """
    if fmt not in ("list", "text"):
        raise ValueError(f"fmt must be 'list' or 'text', got {fmt!r}")

    if not text:
        return [] if fmt == "list" else ""

    # First split on whitespace, keeping punctuation as separate tokens.
    raw = _split_with_punctuation(text)
    merged = _greedy_merge_compounds(raw)

    if fmt == "text":
        return " ".join(t.replace(" ", "_") for t in merged)
    return merged


# Punctuation including smart quotes (U+2018, U+2019, U+201C, U+201D) that
# appear in copy-pasted Word documents. Smart quotes are intentional here.
_PUNCT_RE = re.compile(r"([\.\,\;\:\!\?\(\)\[\]\{\}\"‘’“”/])")  # noqa: RUF001


def _split_with_punctuation(text: str) -> list[str]:
    """Whitespace split, then break punctuation into its own tokens."""
    out: list[str] = []
    for chunk in text.split():
        # Split punctuation characters out as their own tokens.
        parts = [p for p in _PUNCT_RE.split(chunk) if p]
        out.extend(parts)
    return out


def _greedy_merge_compounds(tokens: list[str]) -> list[str]:
    """Merge consecutive tokens that form a known VN compound word.

    Greedy: at each position, try the longest possible merge (up to 4 tokens)
    before falling back to shorter merges or the singleton.
    """
    out: list[str] = []
    i = 0
    n = len(tokens)
    while i < n:
        merged = False
        # Try lengths 5, 4, 3, 2 in that order (longest match wins). Longest
        # compound currently in the dict is "thành phố hồ chí minh" (5 tokens).
        for span in (5, 4, 3, 2):
            if i + span > n:
                continue
            candidate = " ".join(tokens[i : i + span])
            # Lowercase lookup — table is lowercase. Output preserves case.
            if candidate.lower() in COMPOUNDS:
                out.append(candidate)
                i += span
                merged = True
                break
        if not merged:
            out.append(tokens[i])
            i += 1
    return out


# Sentence boundary regex: terminal punctuation followed by whitespace + uppercase
# OR end-of-string. Captures the terminal punctuation as part of the sentence.
_SENT_BOUNDARY_RE = re.compile(
    r"(?<=[\.\!\?…])\s+(?=[A-ZÀÁẢÃẠÂẦẤẨẪẬĂẰẮẲẴẶÈÉẺẼẸÊỀẾỂỄỆÌÍỈĨỊÒÓỎÕỌÔỒỐỔỖỘƠỜỚỞỠỢÙÚỦŨỤƯỪỨỬỮỰỲÝỶỸỴĐ])"
)


def sent_tokenize(text: str) -> list[str]:
    """Split Vietnamese text into sentences.

    Recognizes ``.``, ``!``, ``?``, ``…`` as terminators. Avoids splitting at
    common Vietnamese abbreviations from :mod:`nom.text._compounds`
    (``NEVER_SPLIT_AFTER``).

    Args:
        text: Vietnamese paragraph(s).

    Returns:
        List of sentences (whitespace-trimmed, terminal punctuation kept).

    Example:
        >>> sent_tokenize("Hôm nay trời mưa to. Anh có cần ô không?")
        ['Hôm nay trời mưa to.', 'Anh có cần ô không?']
    """
    if not text:
        return []

    # Mask abbreviations so they don't split. Replace "TP." → "TP\x00",
    # split, then restore.
    masked = text
    for abbr in NEVER_SPLIT_AFTER:
        masked = masked.replace(abbr + ".", abbr + "\x00")

    sents = _SENT_BOUNDARY_RE.split(masked)
    return [s.replace("\x00", ".").strip() for s in sents if s.strip()]


_MULTI_WS_RE = re.compile(r"\s+")
_SPACE_BEFORE_PUNCT_RE = re.compile(r"\s+([\.\,\;\:\!\?])")
_NO_SPACE_AFTER_PUNCT_RE = re.compile(r"([\.\,\;\:\!\?])(?=[^\s\.\,\;\:\!\?])")


def text_normalize(text: str) -> str:
    """Apply VN-aware whitespace + punctuation normalization.

    Distinct from :func:`nom.text.normalize` (which is Unicode NFC only).
    This function:

    - Applies NFC composition.
    - Collapses runs of whitespace to single spaces.
    - Removes whitespace before ``.,;:!?``.
    - Ensures one space after ``.,;:!?`` (when followed by a word char).
    - Trims leading/trailing whitespace.

    Args:
        text: Vietnamese input.

    Returns:
        Cleaned text.

    Example:
        >>> text_normalize("Hợp đồng được lập   ngày 14, tháng 3.")
        'Hợp đồng được lập ngày 14, tháng 3.'
    """
    if not text:
        return text
    nfc = unicodedata.normalize("NFC", text)
    no_pre_space = _SPACE_BEFORE_PUNCT_RE.sub(r"\1", nfc)
    with_post_space = _NO_SPACE_AFTER_PUNCT_RE.sub(r"\1 ", no_pre_space)
    collapsed = _MULTI_WS_RE.sub(" ", with_post_space)
    return collapsed.strip()

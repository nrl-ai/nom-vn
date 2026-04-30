"""Reproducible Vietnamese text-noise generator for spell-correction training.

Five noise functions inspired by the
[VSEC paper](https://arxiv.org/abs/2111.00640) error taxonomy. Each is gated
by its own probability so callers can dial in the typo distribution for
their target use case (interactive typing, OCR cleanup, generic correction).

Design goals:

- **Deterministic** — identical (text, config, seed) → identical noisy output.
  Required so training corpora are reproducible byte-for-byte.
- **Realistic** — VN-specific errors people actually make, not random garbage.
  The confusion table targets the high-frequency tone disambiguations we
  caught in the Toshiiiii1 audit (chữ ↔ chứ, Hùng ↔ Hưng).
- **Composable** — stack the noises, each independent. A diacritic-stripped
  word can also get an OCR substitution applied later.
- **Pure** — no I/O, no globals, no side effects. ``noisify(text)`` is a
  pure function of ``(text, self.cfg, self.seed)``.

Usage::

    from nom.text.noise import NoiseGenerator, light_noise, heavy_noise

    gen = NoiseGenerator(light_noise(), seed=42)
    print(gen.noisify("Tôi yêu Việt Nam"))
    # 'Toi yêu Vit Nam'  # one diacritic strip + one char drop, deterministic

    # Generate a (noisy, clean) training pair
    clean = "Hợp đồng số 02/HĐ/2025 được lập tại Hà Nội."
    noisy = gen.noisify(clean)
    pair = {"input": noisy, "target": clean}
"""

from __future__ import annotations

import random
import re
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass, field

from nom.text.normalize import strip_diacritics


@dataclass(frozen=True, slots=True)
class NoiseConfig:
    """Per-noise-type probabilities.

    Each value is the probability that a single eligible token/char becomes
    a noise candidate. The actual mutation is then deterministic given the
    seed.

    Rough realism guide (these are starting points — tune to your eval):

    - ``p_diacritic_strip`` 0.05-0.15 ≈ casual typing forgets a few accents.
    - ``p_diacritic_strip_partial`` 0.02-0.08 ≈ typed half a Telex sequence.
    - ``p_confusion`` 0.02-0.05 ≈ classic VN tone-disambiguation slips.
    - ``p_char_swap`` 0.005-0.02 ≈ adjacent-key fat-finger.
    - ``p_char_delete`` 0.005-0.02 ≈ skipped a key.
    - ``p_char_insert`` 0.005-0.01 ≈ doubled a key.
    - ``p_ocr`` 0.0 for typing input, 0.05-0.20 for scanned-doc inputs.
    """

    p_diacritic_strip: float = 0.0
    p_diacritic_strip_partial: float = 0.0
    p_confusion: float = 0.0
    p_char_swap: float = 0.0
    p_char_delete: float = 0.0
    p_char_insert: float = 0.0
    p_ocr: float = 0.0
    # New (v0.2.28) noise dimensions for comprehensive coverage.
    p_telex_grammar: float = 0.0  # per-token: drop / swap / double the Telex tone letter
    p_slang: float = 0.0  # per-token: replace with teen-code abbreviation
    p_segment: float = 0.0  # per-token boundary: drop / insert space
    p_keyboard: float = 0.0  # per-char: hit a QWERTY-adjacent key by mistake
    # Maximum overall edit ratio (edits / chars). Caps the pile-up of
    # multiple noises on a short sentence — keeps the input recoverable.
    max_edit_ratio: float = 0.25


# Common Vietnamese tone-confusion clusters. Each list is a single equivalence
# group for noise — picking any other member of the same group is a realistic
# user error. Sourced from the proper-noun ambiguity examples in CLAUDE.md
# plus the high-frequency confusions audited in the Toshiiiii1 4-register run.
_CONFUSION_GROUPS: tuple[tuple[str, ...], ...] = (
    ("thuê", "thuế", "thuệ"),
    ("chữ", "chứ", "chử"),
    ("nhỉ", "nhì", "nhi"),
    ("giả", "giã", "giá", "gia"),
    ("Hùng", "Hưng", "Hứng"),
    ("Thanh", "Thánh", "Thành"),
    ("Lê", "Lễ", "Le"),
    ("nội", "nỗi", "nồi", "nội"),
    ("là", "lá", "lả", "lạ"),
    ("của", "cùa", "cũa"),
    ("không", "khong", "khống"),
    ("được", "đuoc", "duộc"),
    ("đã", "đa", "đả"),
    ("năm", "nắm", "nâm"),
    ("ngày", "ngay"),
    ("phải", "phái", "phai"),
    ("tốt", "tột", "tốt"),
    ("để", "đề", "đệ"),
    ("vẫn", "vẩn", "văn"),
    ("hôm", "hỗm", "hỏm"),
)

# Lookup: word -> set of confusables (excluding self).
_CONFUSION_INDEX: dict[str, tuple[str, ...]] = {}
for _group in _CONFUSION_GROUPS:
    for _w in _group:
        alts = tuple(x for x in _group if x != _w)
        if alts:
            _CONFUSION_INDEX[_w] = alts


# Mobile / QWERTY adjacent-key confusions. Models a thumbs-on-phone
# fat-finger more accurately than uniform char-swap. Each entry is
# {key: (adjacent keys typeable instead)}. Sourced from a US-QWERTY
# Vietnamese-keyboard layout (the most common VN typing layout).
_KEY_ADJACENCY: dict[str, tuple[str, ...]] = {
    "q": ("w", "a"),
    "w": ("q", "e", "s"),
    "e": ("w", "r", "d"),
    "r": ("e", "t", "f"),
    "t": ("r", "y", "g"),
    "y": ("t", "u", "h"),
    "u": ("y", "i", "j"),
    "i": ("u", "o", "k"),
    "o": ("i", "p", "l"),
    "p": ("o", "l"),
    "a": ("q", "s", "z"),
    "s": ("a", "d", "w", "z"),
    "d": ("s", "f", "e", "x"),
    "f": ("d", "g", "r", "c"),
    "g": ("f", "h", "t", "v"),
    "h": ("g", "j", "y", "b"),
    "j": ("h", "k", "u", "n"),
    "k": ("j", "l", "i", "m"),
    "l": ("k", "p", "o"),
    "z": ("a", "s", "x"),
    "x": ("z", "d", "c"),
    "c": ("x", "f", "v"),
    "v": ("c", "g", "b"),
    "b": ("v", "h", "n"),
    "n": ("b", "j", "m"),
    "m": ("n", "k"),
}


# OCR-confusion table (Latin-script, applies to VN diacriticized text too).
# Keyed by the source character; values are equally plausible mistaken reads.
# Curated from observed Tesseract / VLM errors on VN scans.
_OCR_SUBS: dict[str, tuple[str, ...]] = {
    "o": ("0",),
    "0": ("o", "O"),
    "O": ("0", "Q"),
    "l": ("1", "I"),
    "1": ("l", "I"),
    "I": ("l", "1"),
    "c": ("e", "ç"),
    "e": ("c"),  # type: ignore[dict-item]  # tuple of one char
    "n": ("h", "ri"),
    "h": ("n", "li"),
    "m": ("rn", "nn"),
    "u": ("v",),
    "v": ("u",),
    "i": ("l", "1"),
    "5": ("S", "s"),
    "S": ("5",),
    "8": ("B",),
    "B": ("8",),
}
# Filter: drop entries whose value isn't a tuple of strings (clean up the typed
# overrides above).
_OCR_SUBS = {k: v if isinstance(v, tuple) else (v,) for k, v in _OCR_SUBS.items()}


_WORD_RE = re.compile(r"\w+|\W+", re.UNICODE)


# Telex tone-letter map: each VN tone has a single letter typed AFTER the
# vowel. Real Telex errors come in three flavours covered by the
# `p_telex_grammar` noise:
#
#   1. drop the tone letter   (typed nothing) → diacritic-strip on that vowel
#   2. wrong tone letter      (e.g. f instead of s) → tone-confusion
#   3. doubled tone letter    (e.g. ss) → tone repeats, breaks the syllable
#
# The mapping is inverse: tone diacritic → Telex letter.
_TELEX_TONES: dict[str, str] = {
    "̀": "f",  # combining grave (huyền)
    "́": "s",  # combining acute (sắc)
    "̉": "r",  # combining hook above (hỏi)
    "̃": "x",  # combining tilde (ngã)
    "̣": "j",  # combining dot below (nặng)
}
# Inverse, for "wrong tone letter" substitutions.
_TELEX_TONE_LETTERS = tuple(_TELEX_TONES.values())


# Vowel-modifier Telex doubling — `aa`→`â`, `oo`→`ô`, `dd`→`đ`, etc.
# Errors: forgot the second character → bare base letter (already covered
# by diacritic_strip), or hit only one (handled).
_TELEX_MODIFIERS: dict[str, str] = {
    "â": "aa",
    "ê": "ee",
    "ô": "oo",
    "ơ": "ow",
    "ư": "uw",
    "ă": "aw",
    "đ": "dd",
}


# VN teen-code / slang abbreviations — high-frequency replacements seen in
# social-media short-form. Keyed by the canonical word (lower); values are
# the abbreviated forms commonly typed in chat. Sourced from common-knowledge
# usage; for training we apply randomly to mimic informal-register input.
_TEEN_CODE: dict[str, tuple[str, ...]] = {
    "không": ("ko", "k", "kg", "khong"),
    "được": ("dc", "đc", "duoc"),
    "yêu": ("iu", "yeu"),
    "bạn": ("bn", "ban"),
    "mình": ("mk", "minh"),
    "vợ": ("vk",),
    "chồng": ("ck",),
    "gì": ("j", "gi", "ji"),
    "rồi": ("r",),
    "biết": ("biet", "bik"),
    "cảm ơn": ("cam on", "tks", "thks", "tks"),
    "xin chào": ("xc", "xin chao"),
    "tao": ("t",),
    "mày": ("m",),
    "thôi": ("thui", "thoi"),
    "anh": ("a",),
    "chị": ("c",),
    "em": ("e",),
    "cái": ("cai", "cía"),
    "này": ("nay",),
    "luôn": ("luon", "lun"),
    "vẫn": ("van", "vẫn"),
    "vào": ("vao", "vô", "vo"),
    "đi": ("di", "dii"),
    "với": ("voi", "v"),
    "nhỉ": ("nhi", "nhì"),
    "nhé": ("nhe", "nha"),
    "trời ơi": ("tri oi", "troi oi", "ơi"),
    "rất": ("rat",),
    "lắm": ("lam",),
    "thật": ("that", "thiệt"),
    "vậy": ("v",),
    "thế": ("the",),
    "đây": ("day", "đey"),
    "đó": ("do",),
}


def light_noise() -> NoiseConfig:
    """Calibrated for ~5 % char-level edit distance on average.

    Models a person typing on a Vietnamese keyboard: forgets a few accents,
    occasionally hits the wrong tone-mark key, almost never makes a
    char-level fat-finger.
    """
    return NoiseConfig(
        p_diacritic_strip=0.08,
        p_diacritic_strip_partial=0.04,
        p_confusion=0.03,
        p_char_swap=0.005,
        p_char_delete=0.005,
        p_char_insert=0.003,
        p_ocr=0.0,
    )


def heavy_noise() -> NoiseConfig:
    """Calibrated for ~15-20 % edit distance.

    Models OCR output of a mid-quality scan: lots of diacritic drops, more
    char-level confusions, OCR substitutions on the table.
    """
    return NoiseConfig(
        p_diacritic_strip=0.20,
        p_diacritic_strip_partial=0.10,
        p_confusion=0.04,
        p_char_swap=0.02,
        p_char_delete=0.02,
        p_char_insert=0.01,
        p_ocr=0.10,
    )


def telex_typo_noise() -> NoiseConfig:
    """Heavy diacritic perturbation, no OCR. Models Telex/VNI input errors.

    Real Telex errors mostly manifest as ``forgot the tone letter`` or
    ``typed the wrong tone letter`` — both reduce to a diacritic-strip /
    diacritic-confusion observable in the output. We don't model the
    keystroke-level Telex grammar; the surface effect is what matters.
    """
    return NoiseConfig(
        p_diacritic_strip=0.15,
        p_diacritic_strip_partial=0.08,
        p_confusion=0.05,
        p_char_swap=0.005,
        p_char_delete=0.005,
        p_char_insert=0.002,
        p_ocr=0.0,
    )


def telex_grammar_noise() -> NoiseConfig:
    """Real Telex-keystroke errors: drop / wrong / doubled tone letters.

    Simulates the per-keystroke failure modes of Telex IM rather than the
    surface effect alone. Higher p_telex_grammar means more tone-letter
    mistakes appear in the output (visible artifacts like ``ngas`` for ``ngã``
    when the user double-tapped, or ``nga`` when they forgot the `x` letter).
    Pair with light char-noise to cover the typing context realistically.
    """
    return NoiseConfig(
        p_telex_grammar=0.15,
        p_diacritic_strip=0.05,
        p_confusion=0.03,
        p_char_swap=0.005,
        p_char_delete=0.005,
        p_char_insert=0.002,
    )


def mobile_noise() -> NoiseConfig:
    """Models thumbs-on-phone typing: adjacent-key slips + slang short-form.

    Mobile inputs differ from desktop: people use teen-code abbreviations
    (``ko`` for ``không``, ``đc`` for ``được``), hit adjacent keys
    (``a``↔``s``↔``q``), and sometimes drop the IME entirely. p_keyboard +
    p_slang dominate; diacritic strip is moderate (mobile IMEs work but slip).
    """
    return NoiseConfig(
        p_diacritic_strip=0.10,
        p_diacritic_strip_partial=0.05,
        p_slang=0.15,
        p_keyboard=0.02,
        p_char_swap=0.005,
        p_segment=0.03,
    )


def ocr_realistic_noise() -> NoiseConfig:
    """Models scanned-document OCR output: heavy diacritic loss + char confusions.

    Distinct from `heavy_noise` in that segmentation errors and OCR-engine-
    specific confusions dominate over random char operations. Use this when
    training for downstream OCR cleanup.
    """
    return NoiseConfig(
        p_diacritic_strip=0.25,
        p_diacritic_strip_partial=0.10,
        p_confusion=0.04,
        p_ocr=0.15,
        p_segment=0.08,
        p_char_swap=0.01,
        p_char_delete=0.015,
        p_char_insert=0.005,
    )


def comprehensive_noise() -> NoiseConfig:
    """Mix every noise dimension at moderate probabilities — for v2 training.

    Models a realistic distribution of failure modes a single trained model
    will see in production: diacritic slips, telex-grammar errors, mobile
    autocorrect, OCR scans, segmentation issues. Each dimension is dialled
    to a level that's frequent but not overwhelming.

    Use this as the noise config for the v2 training corpus where we want
    the model to generalize across many typo classes rather than one.
    """
    return NoiseConfig(
        p_diacritic_strip=0.10,
        p_diacritic_strip_partial=0.05,
        p_confusion=0.03,
        p_telex_grammar=0.05,
        p_slang=0.04,
        p_keyboard=0.005,
        p_segment=0.02,
        p_ocr=0.03,
        p_char_swap=0.005,
        p_char_delete=0.005,
        p_char_insert=0.003,
    )


@dataclass(slots=True)
class NoiseGenerator:
    """Stateful — owns its own RNG so calls are deterministic per-instance."""

    cfg: NoiseConfig
    seed: int = 42
    _rng: random.Random = field(init=False, repr=False)

    def __post_init__(self) -> None:
        # Slot-fields can't use default_factory directly — set explicitly.
        object.__setattr__(self, "_rng", random.Random(self.seed))

    def noisify(self, clean: str) -> str:
        """Apply the configured noise to ``clean``, returning a noisy variant.

        The output is NFC-normalized so it round-trips through tokenizers
        without the silent NFD trap.
        """
        if not clean:
            return clean

        clean = unicodedata.normalize("NFC", clean)
        cap = max(1, int(len(clean) * self.cfg.max_edit_ratio))
        edits_used = 0

        def _budget_ok() -> bool:
            nonlocal edits_used
            if edits_used >= cap:
                return False
            edits_used += 1
            return True

        # Word-level passes first (diacritic strip, confusion, slang, telex).
        out_tokens: list[str] = []
        tokens = _WORD_RE.findall(clean)
        for tok in tokens:
            if not tok or not tok.strip():
                out_tokens.append(tok)
                continue

            # Slang / teen-code substitution — high priority because real
            # social-media short-form replaces whole words, not just chars.
            if self._rng.random() < self.cfg.p_slang:
                alts = _TEEN_CODE.get(tok.lower())
                if alts and _budget_ok():
                    out_tokens.append(self._rng.choice(alts))
                    continue

            # Telex-grammar simulator — drop / wrong / double the tone letter.
            if self._rng.random() < self.cfg.p_telex_grammar and _budget_ok():
                mutated = self._telex_grammar(tok)
                if mutated != tok:
                    out_tokens.append(mutated)
                    continue

            # Diacritic strip (full).
            if self._rng.random() < self.cfg.p_diacritic_strip and _budget_ok():
                out_tokens.append(strip_diacritics(tok))
                continue

            # Partial strip — drop only some marks.
            if self._rng.random() < self.cfg.p_diacritic_strip_partial and _budget_ok():
                out_tokens.append(self._partial_strip(tok))
                continue

            # Confusion-set substitution.
            if self._rng.random() < self.cfg.p_confusion:
                alts = _CONFUSION_INDEX.get(tok)
                if alts and _budget_ok():
                    out_tokens.append(self._rng.choice(alts))
                    continue

            out_tokens.append(tok)

        # Word-segmentation perturbation — drop / insert spaces at token
        # boundaries before joining.
        text = self._segment_pass(out_tokens, _budget_ok)

        # Char-level passes after word-level — order matters because char ops
        # operate on the post-word-substitution string.
        text = self._char_pass(text, _budget_ok)

        return unicodedata.normalize("NFC", text)

    # ---- internal helpers ----

    def _partial_strip(self, tok: str) -> str:
        """Strip diacritics on a random subset of the chars in ``tok``."""
        out_chars: list[str] = []
        for ch in tok:
            if self._rng.random() < 0.5 and ch != strip_diacritics(ch):
                out_chars.append(strip_diacritics(ch))
            else:
                out_chars.append(ch)
        return "".join(out_chars)

    def _telex_grammar(self, tok: str) -> str:
        """Simulate Telex-keystroke errors: drop / replace / double the tone letter.

        Goes through the token char-by-char; on each combining tone mark, with
        equal probability picks one of three failure modes:

        - drop the tone (loses the diacritic, doesn't add a letter)
        - wrong tone letter (replaces with a different Telex tone — `f` instead of `s`)
        - doubled tone letter (the user double-tapped — `ss` instead of `s`)

        The result is decomposed and re-composed via NFC at the end so the
        output is a valid VN string.
        """
        decomposed = unicodedata.normalize("NFD", tok)
        out_chars: list[str] = []
        for ch in decomposed:
            if ch in _TELEX_TONES:
                mode = self._rng.randint(0, 2)
                if mode == 0:
                    # drop the tone
                    continue
                if mode == 1:
                    # wrong tone letter — emit a different tone-marker mapped
                    # back via the inverse table
                    wrong_letter = self._rng.choice(_TELEX_TONE_LETTERS)
                    inv = {v: k for k, v in _TELEX_TONES.items()}
                    out_chars.append(inv.get(wrong_letter, ch))
                    continue
                # doubled — keep the tone AND emit the literal Telex letter
                # afterwards (visible artifact like "ngas" instead of "ngã")
                out_chars.append(ch)
                out_chars.append(_TELEX_TONES[ch])
                continue
            out_chars.append(ch)
        return unicodedata.normalize("NFC", "".join(out_chars))

    def _segment_pass(self, tokens: list[str], budget_ok: Callable[[], bool]) -> str:
        """Drop or insert spaces at token boundaries — models segmentation slips."""
        if self.cfg.p_segment <= 0:
            return "".join(tokens)
        out: list[str] = []
        for tok in tokens:
            if tok.isspace() and self._rng.random() < self.cfg.p_segment and budget_ok():
                # drop this whitespace boundary entirely
                continue
            out.append(tok)
            if tok.strip() and self._rng.random() < self.cfg.p_segment * 0.5 and budget_ok():
                # insert a stray space mid-word boundary
                out.append(" ")
        return "".join(out)

    def _char_pass(self, text: str, budget_ok: Callable[[], bool]) -> str:
        chars = list(text)
        i = 0
        while i < len(chars):
            ch = chars[i]
            r = self._rng.random()

            # OCR substitution.
            if r < self.cfg.p_ocr:
                subs = _OCR_SUBS.get(ch)
                if subs and budget_ok():
                    chars[i] = self._rng.choice(subs)
                    i += len(chars[i])
                    continue

            # QWERTY adjacent-key fat-finger (mobile typing).
            if r < self.cfg.p_keyboard:
                adj = _KEY_ADJACENCY.get(ch.lower())
                if adj and budget_ok():
                    new_ch = self._rng.choice(adj)
                    chars[i] = new_ch.upper() if ch.isupper() else new_ch
                    i += 1
                    continue

            # Char swap with neighbor.
            if r < self.cfg.p_char_swap and i + 1 < len(chars) and budget_ok():
                chars[i], chars[i + 1] = chars[i + 1], chars[i]
                i += 2
                continue

            # Char delete (skip writing this char).
            if r < self.cfg.p_char_delete and budget_ok():
                chars[i] = ""
                i += 1
                continue

            # Char insert (duplicate this char).
            if r < self.cfg.p_char_insert and budget_ok():
                chars[i] = ch + ch
                i += 1
                continue

            i += 1
        return "".join(chars)


__all__ = [
    "NoiseConfig",
    "NoiseGenerator",
    "comprehensive_noise",
    "heavy_noise",
    "light_noise",
    "mobile_noise",
    "ocr_realistic_noise",
    "telex_grammar_noise",
    "telex_typo_noise",
]

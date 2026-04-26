"""Vietnamese text normalization — NFC, tone marks, diacritic restoration.

All functions are pure-Python with no external dependencies.

The diacritic-restoration here is rule-based and limited (single-word lookups
plus a small frequency-weighted vocabulary). It's intended for OCR-cleanup-
adjacent use cases, not full natural-language restoration. The v0.1 release
plans an LLM-backed ``fix_diacritics(..., llm=...)`` that handles ambiguity.
"""

from __future__ import annotations

import json
import unicodedata
from typing import Any

__all__ = [
    "fix_diacritics",
    "has_diacritics",
    "is_vietnamese",
    "normalize",
    "strip_diacritics",
]

# Vietnamese alphabet (lowercase + uppercase). Used to detect VN script.
_VN_VOWELS_LOWER = (
    set("aeiouy")
    | set("àáảãạâầấẩẫậăằắẳẵặ")
    | set("èéẻẽẹêềếểễệ")
    | set("ìíỉĩị")
    | set("òóỏõọôồốổỗộơờớởỡợ")
    | set("ùúủũụưừứửữự")
    | set("ỳýỷỹỵ")
)
_VN_VOWELS = _VN_VOWELS_LOWER | {c.upper() for c in _VN_VOWELS_LOWER}

# Characters unique to Vietnamese (đ, Đ + tone-marked vowels).
_VN_UNIQUE_LOWER = (
    set("đ")
    | set("àáảãạâầấẩẫậăằắẳẵặ")
    | set("èéẻẽẹêềếểễệ")
    | set("ìíỉĩị")
    | set("òóỏõọôồốổỗộơờớởỡợ")
    | set("ùúủũụưừứửữự")
    | set("ỳýỷỹỵ")
)
_VN_UNIQUE = _VN_UNIQUE_LOWER | {c.upper() for c in _VN_UNIQUE_LOWER if c.upper() != c}


def normalize(text: str) -> str:
    """Normalize Vietnamese text to canonical NFC.

    Combines decomposed characters (e.g., ``"é"`` → ``"é"``) and applies
    Unicode canonical composition. Leaves non-VN characters untouched.

    Args:
        text: input string, possibly mixing decomposed and composed forms.

    Returns:
        NFC-normalized string.

    Example:
        >>> normalize("cỏ")  # "co" + combining hook above
        'cỏ'
    """
    return unicodedata.normalize("NFC", text)


def strip_diacritics(text: str) -> str:
    """Remove all diacritics from Vietnamese text.

    Useful for ASCII-only contexts (URL slugs, search-key normalization,
    legacy systems). Note: ``đ`` is mapped to ``d`` (and ``Đ`` to ``D``).

    Args:
        text: input Vietnamese string.

    Returns:
        ASCII approximation with diacritics removed.

    Example:
        >>> strip_diacritics("Hợp đồng số 02/HĐ/2025")
        'Hop dong so 02/HD/2025'
    """
    decomposed = unicodedata.normalize("NFD", text)
    stripped = "".join(c for c in decomposed if unicodedata.category(c) != "Mn")
    # Handle đ/Đ specifically — they don't decompose under NFD.
    return stripped.replace("đ", "d").replace("Đ", "D")


def has_diacritics(text: str) -> bool:
    """Return True if text contains any Vietnamese-specific diacritic character.

    Distinct from :func:`is_vietnamese` — pure-ASCII Vietnamese (``"Hop dong"``)
    returns False here, while :func:`is_vietnamese` returns True (the words still
    parse as VN).
    """
    return any(c in _VN_UNIQUE for c in text)


def is_vietnamese(text: str, *, threshold: float = 0.4) -> bool:
    """Heuristically detect whether text is (primarily) Vietnamese.

    Three signals checked in order:

    1. Presence of VN-unique diacritics (definitive).
    2. Presence of stripped-form VN words from our common-word table.
    3. Vowel density typical of Vietnamese (fallback for short text).

    Args:
        text: input string.
        threshold: vowel-density cutoff for the fallback path. Default ``0.4``
            — diacritic-stripped VN drops below the diacritic-bearing density
            because tone-marked vowels collapse onto fewer base letters.

    Returns:
        True if the text appears to be Vietnamese.
    """
    if not text:
        return False
    if has_diacritics(text):
        return True
    # Token-table check: how many words match common VN words (stripped form)?
    tokens = [t.lower() for t in text.split() if t.isalpha()]
    if tokens:
        hits = sum(1 for t in tokens if t in _RESTORE_TABLE)
        if hits >= 2 or (len(tokens) >= 1 and hits / len(tokens) >= 0.4):
            return True
    # Vowel-density fallback.
    alpha = [c for c in text if c.isalpha()]
    if len(alpha) < 4:
        return False
    vowel_ratio = sum(1 for c in alpha if c.lower() in "aeiouy") / len(alpha)
    return vowel_ratio >= threshold


# A small high-frequency Vietnamese vocabulary for diacritic restoration.
# Maps stripped form → most-likely diacritic-bearing form.
#
# Entries are *unique* — no key appears twice. When a stripped form has
# multiple legitimate diacritic forms (e.g., ``ma`` → ``mà``/``má``/``mã``,
# ``ve`` → ``về``/``vẽ``/``vé``), we pick the most-common business-context
# form OR omit the entry. For ambiguous text use the v0.1 LLM-backed path.
#
# Categories below for organization only — Python's dict literal flattens them.
_RESTORE_TABLE: dict[str, str] = {
    # Pronouns
    "toi": "tôi",
    "ban": "bạn",
    "chi": "chị",
    "minh": "mình",
    "ho": "họ",
    "no": "nó",
    "chung": "chúng",
    # Particles / connectives
    "la": "là",
    "co": "có",
    "khong": "không",
    "duoc": "được",
    "se": "sẽ",
    "da": "đã",
    "dang": "đang",
    "cua": "của",
    "tu": "từ",
    "den": "đến",  # also "đèn" (lamp) — picks the more common arrival sense
    "voi": "với",
    "ngoai": "ngoài",
    "tren": "trên",
    "duoi": "dưới",
    "nay": "này",
    "kia": "kia",
    "nao": "nào",
    "gi": "gì",
    "tai": "tại",
    "vi": "vì",
    "ma": "mà",  # also "má" (mother), "mã" (horse) — picks the connective
    "nhung": "nhưng",
    "neu": "nếu",
    "thi": "thì",
    # Common verbs
    "lam": "làm",  # also "lắm" (very) — picks the verb
    "an": "ăn",
    "uong": "uống",
    "noi": "nói",  # also "nội" (internal) — picks the verb
    "nghe": "nghe",
    "thay": "thấy",
    "biet": "biết",
    "hieu": "hiểu",
    "muon": "muốn",
    "can": "cần",
    "phai": "phải",
    "nen": "nên",
    "di": "đi",
    "ra": "ra",
    "vao": "vào",
    "len": "lên",
    "xuong": "xuống",
    "qua": "qua",
    "lai": "lại",
    "hoi": "hỏi",
    "tra": "trả",
    "loi": "lời",  # also "lỗi" (error) — picks word/speech sense
    "dap": "đáp",
    "viet": "viết",  # also "việt" (Vietnam) — picks verb (write)
    "doc": "đọc",
    "hoc": "học",
    "day": "dạy",
    "ngu": "ngủ",
    "thuc": "thức",
    # Numbers / time
    "thang": "tháng",
    "ngay": "ngày",
    "tuan": "tuần",
    "gio": "giờ",
    "phut": "phút",
    "giay": "giây",
    "hai": "hai",
    "bon": "bốn",
    "nam": "năm",  # also "nam" (south) — picks "year"/"five"
    "sau": "sáu",
    "bay": "bảy",
    "tam": "tám",
    "muoi": "mười",
    "tram": "trăm",
    "nghin": "nghìn",
    "trieu": "triệu",
    # Document / business words (high-value for OCR cleanup)
    "hop": "hợp",
    "dong": "đồng",
    "so": "số",
    "ky": "ký",
    "lap": "lập",
    "nhan": "nhận",
    "gui": "gửi",
    "gia": "giá",
    "tri": "trị",
    "tien": "tiền",
    "thanh": "thành",
    "toan": "toán",
    "luong": "lượng",
    "thuoc": "thuộc",
    "thoi": "thời",
    "han": "hạn",
    "cong": "công",
    "van": "văn",
    "quan": "quan",
    "bo": "bộ",
    "phong": "phòng",
    "giam": "giám",
    "truong": "trưởng",
    "pho": "phó",  # also "phố" (street); picks deputy/title sense
    "viec": "việc",
    "tac": "tác",
    "trach": "trách",
    "nhiem": "nhiệm",
    "vu": "vụ",
    # Geography / proper-noun-ish (singletons only)
    "ha": "hà",
    "tha": "tha",
    "thu": "thứ",
    # Greetings / common
    "chao": "chào",
    "cam": "cảm",
    "on": "ơn",
    "xin": "xin",
}


def fix_diacritics(text: str, *, llm: Any = None) -> str:
    """Restore Vietnamese diacritics on a diacritic-stripped string.

    Two backends:

    - **Default (no LLM): rule-based table.** ~41% word accuracy on our
      public corpus (`benchmarks/data/diacritic_eval_v0.txt`). Zero
      dependencies, ~5ms per call. Use for offline/CI/throughput-bound
      use cases where the wrong-mark rate is acceptable.
    - **LLM-backed (``llm=...``): pass any** :class:`nom.llm.LLM` adapter
      and the function asks the model to restore diacritics. ~95%+
      typical word accuracy depending on the model. ~100-500ms per call
      but composable with batching at the caller level. The function
      streams paragraph-by-paragraph so one bad block doesn't poison the
      whole document.

    The rule path uses single-word lookups against a curated high-frequency
    vocabulary. Words not in the table are returned unchanged. Preserves case
    pattern: title-case in → title-case out, upper in → upper out.

    Args:
        text: ASCII-or-mixed Vietnamese text.
        llm: optional :class:`nom.llm.LLM`. When provided, defers to the
            model. When None, uses the rule table.

    Returns:
        String with diacritics restored where confident.

    Example:
        >>> fix_diacritics("Hop dong nay duoc lap ngay 14 thang 3")
        'Hợp đồng này được lập ngày 14 tháng 3'

        >>> from nom.llm import Ollama
        >>> fix_diacritics(
        ...     "Hop dong nay duoc lap ngay 14 thang 3",
        ...     llm=Ollama(model="qwen3:8b"),
        ... )
        'Hợp đồng này được lập ngày 14 tháng 3'
    """
    if not text:
        return text

    if llm is not None:
        return _fix_diacritics_llm(text, llm)

    return _fix_diacritics_rule(text)


def _fix_diacritics_rule(text: str) -> str:
    """Rule-based diacritic restoration via the curated lookup table."""
    out: list[str] = []
    token: list[str] = []

    def flush() -> None:
        if not token:
            return
        word = "".join(token)
        token.clear()
        # Direct hit on lowercase form.
        replacement = _RESTORE_TABLE.get(word.lower())
        if replacement is None:
            out.append(word)
            return
        # Preserve original casing pattern: title-case in, title-case out.
        if word.istitle():
            out.append(replacement.capitalize())
        elif word.isupper() and len(word) > 1:
            out.append(replacement.upper())
        else:
            out.append(replacement)

    for ch in text:
        if ch.isalpha():
            token.append(ch)
        else:
            flush()
            out.append(ch)
    flush()

    return normalize("".join(out))


_DIACRITIC_PROMPT = (
    "Bạn là chuyên gia tiếng Việt. Khôi phục dấu cho đoạn văn bản dưới đây "
    "(chuyển chữ không dấu sang chữ có dấu chuẩn).\n\n"
    "Quy tắc bắt buộc:\n"
    "1. Chỉ thêm dấu, KHÔNG thay đổi từ ngữ, KHÔNG thêm hay bớt bất kỳ ký tự nào.\n"
    "2. Giữ nguyên số, dấu câu, ký tự đặc biệt, khoảng trắng, viết hoa.\n"
    "3. Số token và thứ tự token phải giống y hệt văn bản gốc.\n"
    "4. Nếu một từ vốn đã có dấu thì giữ nguyên.\n"
    "5. CHỈ trả về văn bản đã khôi phục dấu, không thêm tiêu đề, lời giải thích, "
    "hay dấu ngoặc kép.\n\n"
    "Văn bản gốc:\n{text}\n\n"
    "Văn bản đã khôi phục dấu:"
)

# JSON schema for structured output. Used when the LLM adapter advertises
# support via ``llm.complete(prompt, schema=...)``. Constrained decoding
# stops small models (qwen3:4b et al.) from emitting hidden CoT or label
# prose in the content field; the model is forced to fill {"restored": "..."}.
_DIACRITIC_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {"restored": {"type": "string"}},
    "required": ["restored"],
}


def _fix_diacritics_llm(text: str, llm: Any) -> str:
    """LLM-backed restoration; one prompt per paragraph for fault isolation.

    Splits at blank-line boundaries. Each paragraph is sent independently
    so a bad paragraph response doesn't corrupt the whole document. The
    blank-line separators between paragraphs are preserved verbatim from
    the input — the LLM never sees them.
    """
    import re

    # Split into (paragraph, separator) chunks. The pattern matches any
    # run of whitespace containing at least one blank line; everything
    # else is paragraph content.
    parts = re.split(r"(\n[ \t]*\n[ \t\n]*)", text)
    if not parts:
        return text

    out: list[str] = []
    for i, part in enumerate(parts):
        # Even indices are content; odd indices are blank-line separators.
        if i % 2 == 1 or not part.strip():
            out.append(part)
            continue
        prompt = _DIACRITIC_PROMPT.format(text=part)
        # max_tokens budget: VN-with-diacritics is ~1.0x ASCII length in chars,
        # but tokenisers vary. 4x the input character count is a safe ceiling
        # for short paragraphs without truncating mid-sentence. JSON wrapper
        # adds ~30 bytes — bump headroom slightly when going through schema.
        max_t = max(128, min(4096, len(part) * 4 + 64))
        # Try structured output first when the adapter supports it (Ollama
        # via ``format``, OpenAI via ``response_format``, Anthropic via tool
        # use). Falls through to plain prompting on TypeError if the adapter
        # doesn't accept ``schema=``.
        raw: str
        try:
            raw = llm.complete(prompt, schema=_DIACRITIC_SCHEMA, max_tokens=max_t)
            try:
                payload = json.loads(raw)
                if isinstance(payload, dict) and isinstance(payload.get("restored"), str):
                    out.append(payload["restored"])
                    continue
            except json.JSONDecodeError:
                # Schema-supporting adapter returned non-JSON anyway — fall
                # through to defensive cleanup on the raw string.
                pass
        except TypeError:
            raw = llm.complete(prompt, max_tokens=max_t)

        restored = raw.strip()
        # Defensive trim for adapters/models that can't honour the schema:
        #   1) Echo the label "Văn bản đã khôi phục dấu:" before the answer.
        #   2) Wrap the answer in code fences ```...```.
        #   3) Emit a `<think>...</think>` reasoning block (qwen3 etc.).
        if "</think>" in restored:
            restored = restored.split("</think>", 1)[1].lstrip()
        if "\n" in restored and restored.split("\n", 1)[0].endswith(":"):
            restored = restored.split("\n", 1)[1]
        if restored.startswith("```"):
            restored = restored.split("\n", 1)[1] if "\n" in restored else restored[3:]
            if restored.endswith("```"):
                restored = restored[:-3].rstrip()
        out.append(restored)

    return normalize("".join(out))

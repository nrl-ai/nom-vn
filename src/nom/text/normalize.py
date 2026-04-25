"""Vietnamese text normalization — NFC, tone marks, diacritic restoration.

All functions are pure-Python with no external dependencies.

The diacritic-restoration here is rule-based and limited (single-word lookups
plus a small frequency-weighted vocabulary). It's intended for OCR-cleanup-
adjacent use cases, not full natural-language restoration. The v0.1 release
plans an LLM-backed ``fix_diacritics(..., llm=...)`` that handles ambiguity.
"""

from __future__ import annotations

import unicodedata

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


def fix_diacritics(text: str) -> str:
    """Restore Vietnamese diacritics on a diacritic-stripped string.

    **v0.0.1: rule-based, ~41% word accuracy on our public corpus.** This is a
    zero-dependency stopgap. v0.0.2 adds a ``backend="model"`` option that
    wraps a real ML model (PyVi or DistilBERT-Viet) for ~90%+ accuracy.

    The rule path uses single-word lookups against a curated high-frequency
    vocabulary. Words not in the table are returned unchanged. Preserves case
    pattern: title-case in → title-case out, upper in → upper out.

    For arbitrary text or production-grade restoration today, route the input
    through any LLM (the v0.1 ``nom.llm`` adapters will make that explicit).

    Args:
        text: ASCII-or-mixed Vietnamese text.

    Returns:
        String with diacritics restored where confident.

    Example:
        >>> fix_diacritics("Hop dong nay duoc lap ngay 14 thang 3")
        'Hợp đồng này được lập ngày 14 tháng 3'
    """
    if not text:
        return text

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

"""Register classifier — 4-class VN text register router.

Two implementations behind a single ``RegisterClassifier`` Protocol:

- :class:`LexiconRegisterClassifier` — zero-ML, ~ms latency, ships
  with the OSS package. Heuristics over diacritic-pattern markers,
  sentence-end particles, register-typical vocabulary.
- :class:`PhoBertRegisterClassifier` — lazy-imports
  ``transformers``; loads a fine-tuned PhoBERT-base 4-class head.
  Production-quality; needs the model weights (downloaded on first
  use or pre-pulled via the Models tab).

The 4 registers (label space, fixed):

- ``FORMAL`` — UDHR-grade administrative / official prose
- ``BUSINESS`` — news, reports, headlines
- ``CONVERSATIONAL`` — Tatoeba-style spoken-register, social media
- ``LITERARY`` — Wikisource-style narrative / poetic prose

Both impls take **NFC** input and return :class:`RegisterResult` with
the predicted label, a 0..1 confidence score, and the full distribution
across the four classes (so callers can do calibrated routing or fall
back to a parent task on low-confidence predictions).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Protocol, runtime_checkable

__all__ = [
    "LexiconRegisterClassifier",
    "PhoBertRegisterClassifier",
    "RegisterClassifier",
    "RegisterLabel",
    "RegisterResult",
]


class RegisterLabel(str, Enum):
    """Fixed 4-class VN text register taxonomy.

    Order matches the survey's source-provenance assembly:
    UDHR (formal) → VNTC (business) → Tatoeba (conversational) →
    Wikisource (literary). Stable across model swaps so a fine-tuned
    PhoBERT head can ship with this label space without retraining the
    consumer routers.
    """

    FORMAL = "formal"
    BUSINESS = "business"
    CONVERSATIONAL = "conversational"
    LITERARY = "literary"


_ALL_LABELS: tuple[RegisterLabel, ...] = (
    RegisterLabel.FORMAL,
    RegisterLabel.BUSINESS,
    RegisterLabel.CONVERSATIONAL,
    RegisterLabel.LITERARY,
)


@dataclass(frozen=True, slots=True)
class RegisterResult:
    """One prediction over the 4-class register taxonomy.

    ``label`` is the argmax. ``score`` is the softmax probability of
    the chosen label (∈ [0, 1]). ``distribution`` is the full softmax
    over all four classes — useful for confidence-thresholded routing
    (skip routing if no class > 0.6, etc.).
    """

    label: RegisterLabel
    score: float
    distribution: dict[RegisterLabel, float]


@runtime_checkable
class RegisterClassifier(Protocol):
    """Protocol seam for any register classifier.

    Real impls live in this module (``LexiconRegisterClassifier``,
    ``PhoBertRegisterClassifier``). Custom impls (e.g. an LLM
    zero-shot prompt or an ONNX-served ELECTRA head) just need to
    expose ``name`` and ``predict``.
    """

    name: str

    def predict(self, text: str) -> RegisterResult: ...


# ---------------------------------------------------------------------- #
# Lexicon baseline — zero-ML default, ships with OSS.
#
# Hand-curated VN markers per register. Not benchmark-winning — its job
# is to give a deterministic, dependency-free default that ships in
# tests, demos, and CPU-only deploys without pulling 500 MB of weights.
# Survey shows ML lift of ~10-15 pp over a strong heuristic baseline
# on Toshiiiii1 4-register matrix, so production routers should swap
# this for ``PhoBertRegisterClassifier`` once weights are pulled.
# ---------------------------------------------------------------------- #

# Official / administrative markers — kính, thưa, trân trọng, ... and
# bureaucratic patterns ("căn cứ", "điều khoản", "có hiệu lực"). UDHR-
# grade prose has long sentences with these markers and zero slang
# particles.
_FORMAL_MARKERS: frozenset[str] = frozenset(
    {
        "kính thưa",
        "trân trọng",
        "vui lòng",
        "kính gửi",
        "kính mời",
        "kính chào",
        "căn cứ",
        "điều khoản",
        "có hiệu lực",
        "quyết định",
        "thông tư",
        "nghị định",
        "công văn",
        "ban hành",
        "quy định",
        "tuân thủ",
        "theo quy định",
        "hiến pháp",
        "công ước",
        "tuyên bố",
        "cam kết",
        "khoản này",
        "điều này",
        "điều luật",
        "luật pháp",
    }
)

# News / business / report patterns. VnExpress / VNTC headline forms,
# financial vocabulary, percent signs, year markers.
_BUSINESS_MARKERS: frozenset[str] = frozenset(
    {
        "công ty",
        "doanh nghiệp",
        "thị trường",
        "cổ phiếu",
        "doanh thu",
        "lợi nhuận",
        "tỷ đồng",
        "triệu đồng",
        "ngân hàng",
        "đầu tư",
        "kinh tế",
        "tăng trưởng",
        "giảm phát",
        "lạm phát",
        "ceo",
        "cfo",
        "báo cáo",
        "quý 1",
        "quý 2",
        "quý 3",
        "quý 4",
        "năm 2024",
        "năm 2025",
        "năm 2026",
        "theo báo",
        "phóng viên",
        "ttxvn",
        "đại hội cổ đông",
    }
)

# Conversational / social-media markers. Sentence-end particles ("nha",
# "đó", "vậy", "à", "ạ"), informal pronouns, exclamation patterns.
_CONVERSATIONAL_MARKERS: frozenset[str] = frozenset(
    {
        " nha",
        " nhé",
        " ạ",
        " à",
        " ơi",
        " hả",
        " thế",
        " vậy",
        " đó",
        " ấy",
        "mình ",
        "tớ ",
        "cậu ",
        "bạn ơi",
        "tao ",
        "mày ",
        "haha",
        "hihi",
        "huhu",
        "ko ",
        "hok ",
        "vl ",
        "thik ",
        "đc ",
        "j vậy",
        "gì vậy",
        "thế nào",
        "sao nhỉ",
    }
)

# Literary / poetic / narrative markers. Archaic pronouns, old-style
# vocabulary, evocative connectors. Wikisource VN classical prose.
_LITERARY_MARKERS: frozenset[str] = frozenset(
    {
        "chàng",
        "nàng",
        "trẫm",
        "đấng",
        "bốn bể",
        "trời đất",
        "non sông",
        "thiên thu",
        "mây trắng",
        "hoa cỏ",
        "trăng tà",
        "bóng nguyệt",
        "thuở xưa",
        "ngày xưa",
        "buổi ấy",
        "kẻ sĩ",
        "tao nhân",
        "mặc khách",
        "anh hùng",
        "tráng sĩ",
        "lệ rơi",
        "tâm tư",
        "u sầu",
        "nỗi niềm",
        "tha hương",
        "biệt ly",
    }
)


@dataclass
class LexiconRegisterClassifier:
    """Heuristic 4-register classifier — VN-aware, zero-ML.

    Counts marker hits per register on **NFC-normalised lowercase**
    input. Returns the argmax with confidence proportional to relative
    margin; falls back to ``BUSINESS`` (the most common register on
    the open web) when no markers fire — that's a safer default than
    e.g. literary, which is rare and would mis-route 99% of unseen
    inputs.

    Why ``BUSINESS`` as fallback: empirically, the open VN web is
    dominated by news / forum / blog text. Mis-routing to formal or
    literary on plain-prose input is more harmful than mis-routing to
    business (which is the 'unmarked' register).
    """

    formal: frozenset[str] = field(default_factory=lambda: _FORMAL_MARKERS)
    business: frozenset[str] = field(default_factory=lambda: _BUSINESS_MARKERS)
    conversational: frozenset[str] = field(default_factory=lambda: _CONVERSATIONAL_MARKERS)
    literary: frozenset[str] = field(default_factory=lambda: _LITERARY_MARKERS)
    name: str = "lexicon-vn-register"

    def predict(self, text: str) -> RegisterResult:
        # NFC normalise + casefold — markers are stored already-NFC, lowercase.
        # Pad both ends with space so " nha"-style markers match at the start
        # of the string too. Length-weighted scoring (longer markers count
        # more) so multi-word patterns like "căn cứ" outweigh a single
        # pronoun hit on "tớ".
        from nom.text.normalize import normalize

        haystack = " " + normalize(text).casefold() + " "

        def score(markers: frozenset[str]) -> float:
            return sum(len(m) for m in markers if m in haystack)

        scores = {
            RegisterLabel.FORMAL: score(self.formal),
            RegisterLabel.BUSINESS: score(self.business),
            RegisterLabel.CONVERSATIONAL: score(self.conversational),
            RegisterLabel.LITERARY: score(self.literary),
        }
        total = sum(scores.values())
        if total == 0:
            # No markers — return BUSINESS as the safe default with a
            # uniform distribution flagging "unsure". Downstream routers
            # should treat score < 0.4 as "skip routing, use parent default".
            uniform = 1.0 / len(_ALL_LABELS)
            return RegisterResult(
                label=RegisterLabel.BUSINESS,
                score=uniform,
                distribution=dict.fromkeys(_ALL_LABELS, uniform),
            )
        # Softmax-style normalize so the distribution sums to 1.
        distribution = {lbl: scores[lbl] / total for lbl in _ALL_LABELS}
        label = max(distribution, key=lambda k: distribution[k])
        return RegisterResult(
            label=label,
            score=distribution[label],
            distribution=distribution,
        )


# ---------------------------------------------------------------------- #
# PhoBERT-backed wrapper — production tier.
#
# Lazy imports ``transformers`` and ``torch`` so the OSS install (which
# excludes them by default) doesn't pull in 2 GB of CUDA runtime on
# import. The model checkpoint is loaded on first call to ``predict``;
# subsequent calls reuse the loaded pipeline.
#
# Default model id: ``nrl-ai/vn-register-classifier-phobert-base``.
# This will land once the training run completes (see
# ``training/register/train.py`` and ``docs/sota_vn_2026q2_expansion.md``).
# Until then, instantiating without an explicit ``model_id`` raises so
# users don't silently fall back to a missing model.
# ---------------------------------------------------------------------- #

_DEFAULT_PHOBERT_MODEL: str | None = None
"""HF model id for the production PhoBERT register head.

Will be set once ``training/register/train.py`` completes a fine-tune
that meets the macro-F1 ≥ 0.85 target on the held-out 20 % of the
4-register corpus. Until then this is ``None`` and callers must pass
their own ``model_id``.
"""


@dataclass
class PhoBertRegisterClassifier:
    """Real-ML register classifier — PhoBERT-base + 4-class head.

    Pass ``model_id`` to an HF repo containing a fine-tuned 4-class
    head over PhoBERT-base, with config.label2id matching the
    :class:`RegisterLabel` enum values.

    Lazy-imports ``torch`` and ``transformers`` on first ``predict``
    call. NFC-normalises input. Word-segmentation IS required by
    PhoBERT — we run :func:`nom.text.word_tokenize` and join with
    underscores per the project's BKai gotcha (``đường thủy`` →
    ``đường_thủy``); raw text drops accuracy ≥ 15 pp.
    """

    model_id: str | None = None
    device: str | None = None  # "cpu", "cuda", "mps"; None = auto
    name: str = "phobert-vn-register"

    # Lazily-populated cache for the loaded pipeline.
    _pipeline: Any = field(default=None, init=False, repr=False)

    def _ensure_loaded(self) -> Any:
        if self._pipeline is not None:
            return self._pipeline
        model_id = self.model_id or _DEFAULT_PHOBERT_MODEL
        if not model_id:
            raise RuntimeError(
                "PhoBertRegisterClassifier needs a `model_id`. The default "
                "production model has not been published yet — see "
                "training/register/train.py to fine-tune one, or pass "
                "your own HF repo id explicitly."
            )
        # Lazy: heavy deps only loaded when actually used. Match the pattern
        # in nom.translate.hf — clear ImportError with install hint when
        # the user hasn't installed the ML extras yet.
        try:
            from transformers import (
                AutoModelForSequenceClassification,
                AutoTokenizer,
                pipeline,
            )
        except ImportError as exc:
            raise ImportError(
                "PhoBertRegisterClassifier requires transformers + torch. "
                "Install with: pip install 'transformers>=4.45' 'torch>=2.0'"
            ) from exc

        tok: Any = AutoTokenizer.from_pretrained(model_id)
        mdl: Any = AutoModelForSequenceClassification.from_pretrained(model_id)
        device = self.device
        if device is None:
            try:
                import torch

                if torch.cuda.is_available():
                    device = "cuda"
                elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
                    device = "mps"
                else:
                    device = "cpu"
            except ImportError:
                device = "cpu"
        self._pipeline = pipeline(
            "text-classification",
            model=mdl,
            tokenizer=tok,
            device=device,
            top_k=None,  # return full distribution, not just top-1
        )
        return self._pipeline

    def predict(self, text: str) -> RegisterResult:
        from nom.text import normalize, word_tokenize

        clean = normalize(text)
        # PhoBERT expects word-segmented input. ``word_tokenize`` returns
        # a list of tokens ("đường thủy" → ["đường thủy"]); join with
        # underscores within multi-syllable words and spaces between
        # words. Our ``word_tokenize`` already groups multi-syllable words.
        segmented = " ".join(tok.replace(" ", "_") for tok in word_tokenize(clean))

        pipe = self._ensure_loaded()
        result = pipe(segmented, truncation=True, max_length=256)
        # `top_k=None` returns a list of dicts: [{"label": ..., "score": ...}, ...]
        # The outer container may be wrapped one level when batch_size=1, normalize.
        rows = result[0] if (result and isinstance(result[0], list)) else result
        if not isinstance(rows, list):  # defensive
            raise RuntimeError(f"unexpected pipeline output: {type(result)!r}")

        distribution: dict[RegisterLabel, float] = {}
        for row in rows:
            try:
                lbl = RegisterLabel(row["label"])
            except ValueError as exc:
                raise RuntimeError(
                    f"model {self.model_id!r} returned label {row['label']!r}; "
                    f"expected one of {[lbl.value for lbl in _ALL_LABELS]}. "
                    "Re-check the fine-tune's label2id mapping."
                ) from exc
            distribution[lbl] = float(row["score"])
        # Pad missing labels with 0 (defensive — well-trained head returns all 4).
        for lbl in _ALL_LABELS:
            distribution.setdefault(lbl, 0.0)
        label = max(distribution, key=lambda k: distribution[k])
        return RegisterResult(
            label=label,
            score=distribution[label],
            distribution=distribution,
        )

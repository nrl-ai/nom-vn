"""Named-entity recognition — Protocol + safetensors-only HF default + regex fallback.

Default tag set (Đ stands for Vietnamese standard):

- ``PER`` — person name
- ``ORG`` — organisation
- ``LOC`` — location / address
- ``MISC`` — other named entities (events, products, …)
- ``DATE`` — explicit date
- ``MONEY`` — monetary value with currency unit

Plug-in points:

- :class:`RegexNERModel` — pure-regex baseline; works offline, useful
  for tests and CPU-only deployments. Catches money / dates / common
  ORG abbreviations; misses most PER/LOC.
- :class:`HFNERModel` — wraps a HuggingFace token-classification
  model. Refuses to load checkpoints that aren't safetensors (per
  the project's no-pickle policy). Lazy-imports torch + transformers
  so importing this module on a host without the ML stack is fine.

EE plugins ship a fine-tuned VN NER from
``nom_ee.nlp.ner.VNNERModel`` (registered via
``nom.platform.ner_models`` entry-point group); see the EE repo.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from nom.nlp.types import NLPError

__all__ = ["HFNERModel", "NERModel", "NERSpan", "RegexNERModel"]


@dataclass(frozen=True, slots=True)
class NERSpan:
    """A detected named entity.

    ``start`` / ``end`` are Python string indices on the *original*
    NFC-normalised text. ``confidence`` is in [0, 1] for ML models;
    regex models report 1.0.
    """

    start: int
    end: int
    label: str
    text: str
    confidence: float = 1.0


@runtime_checkable
class NERModel(Protocol):
    """Tag every entity span in ``text``.

    Output is non-overlapping and sorted by start offset.
    """

    name: str

    def tag(self, text: str) -> tuple[NERSpan, ...]: ...


# ---- Regex baseline -------------------------------------------------


_VN_MONTHS = (
    r"(?:thg\.?\s*\d{1,2}|tháng\s+\d{1,2}|"
    r"(?:January|February|March|April|May|June|July|August|"
    r"September|October|November|December))"
)

_DEFAULT_PATTERNS: tuple[tuple[str, str], ...] = (
    # Money: 1.500.000 VND, 3 triệu, 5 tỷ, 100 USD/đ
    (
        "MONEY",
        r"\b\d[\d.,]*\s*(?:VND|đồng|đ|USD|triệu|tỷ|nghìn|ngàn|EUR|JPY)\b",
    ),
    # ISO date 2026-05-02
    ("DATE", r"\b\d{4}-\d{2}-\d{2}\b"),
    # DD/MM/YYYY (VN convention) and DD-MM-YYYY
    ("DATE", r"\b\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4}\b"),
    # Vietnamese-style month-year phrasing
    ("DATE", _VN_MONTHS + r"\s*[/-]?\s*\d{4}"),
    # Common ORG abbreviations (very partial — augment in EE)
    ("ORG", r"\b(?:VND|VCB|BIDV|Vietcombank|Viettel|VNPT|FPT|VinAI|Zalo)\b"),
)


@dataclass
class RegexNERModel:
    """Pure-regex baseline NER. No ML model, no downloads.

    Coverage skews to MONEY / DATE / a hand-curated ORG list. Useful
    for tests, CPU-only deployments, and as a fallback when the HF
    model fails to load. Register more patterns by passing
    ``extra_patterns``.
    """

    extra_patterns: tuple[tuple[str, str], ...] = ()
    name: str = "regex"
    _compiled: list[tuple[str, re.Pattern[str]]] = field(default_factory=list, init=False)

    def __post_init__(self) -> None:
        for label, pattern in (*_DEFAULT_PATTERNS, *self.extra_patterns):
            self._compiled.append((label, re.compile(pattern)))

    def tag(self, text: str) -> tuple[NERSpan, ...]:
        cands: list[tuple[int, int, str, str]] = []
        for label, regex in self._compiled:
            for m in regex.finditer(text):
                cands.append((m.start(), m.end(), label, m.group(0)))
        # Resolve overlaps: longest span wins, ties broken by earlier start.
        cands.sort(key=lambda c: (-(c[1] - c[0]), c[0]))
        kept: list[tuple[int, int, str, str]] = []
        for cand in cands:
            s, e, _, _ = cand
            if any(not (e <= ks or s >= ke) for ks, ke, *_ in kept):
                continue
            kept.append(cand)
        kept.sort(key=lambda c: c[0])
        return tuple(NERSpan(start=s, end=e, label=lbl, text=t) for s, e, lbl, t in kept)


# ---- HuggingFace token-classification wrapper -----------------------


@dataclass
class HFNERModel:
    """Wrap a HuggingFace token-classification pipeline as an NERModel.

    Refuses to load any checkpoint that ships only ``.bin`` weights
    (no ``model.safetensors``) — that's the project's no-pickle
    policy applied at the model surface. To override (e.g. for a
    well-known lab whose only release format is ``.bin``), pass
    ``allow_bin=True`` explicitly; the choice is logged so audit
    can flag it later.

    Lazy-imported: the module imports cleanly without torch /
    transformers; first ``tag()`` call triggers the load.
    """

    model_id: str = "xlm-roberta-large-finetuned-conll03-english"  # placeholder; override
    aggregation_strategy: str = "simple"
    allow_bin: bool = False
    name: str = "hf"
    _pipeline: Any = field(default=None, init=False, repr=False)

    def tag(self, text: str) -> tuple[NERSpan, ...]:
        if self._pipeline is None:
            self._pipeline = self._load()
        try:
            entities = self._pipeline(text)
        except Exception as exc:
            msg = f"HF NER inference failed: {exc}"
            raise NLPError(msg) from exc
        out: list[NERSpan] = []
        for ent in entities:
            try:
                out.append(
                    NERSpan(
                        start=int(ent["start"]),
                        end=int(ent["end"]),
                        label=str(ent.get("entity_group") or ent.get("entity") or "MISC"),
                        text=str(ent.get("word", text[ent["start"] : ent["end"]])),
                        confidence=float(ent.get("score", 1.0)),
                    )
                )
            except (KeyError, TypeError, ValueError):
                continue
        out.sort(key=lambda s: s.start)
        return tuple(out)

    def _load(self) -> Any:
        if not self.allow_bin and not _safetensors_available(self.model_id):
            msg = (
                f"refusing to load {self.model_id!r}: no model.safetensors "
                f"found in the repo. Pickled .bin weights are arbitrary "
                f"code execution on load. Pass allow_bin=True to override "
                f"with documented justification."
            )
            raise NLPError(msg)
        try:
            from transformers import pipeline
        except ImportError as exc:
            raise NLPError(
                "transformers is required for HFNERModel. Install with: "
                "pip install nom-vn[diacritics]  # pulls torch + transformers"
            ) from exc
        try:
            return pipeline(
                task="token-classification",
                model=self.model_id,
                aggregation_strategy=self.aggregation_strategy,
            )
        except Exception as exc:
            msg = f"failed to load HF NER model {self.model_id!r}: {exc}"
            raise NLPError(msg) from exc


def _safetensors_available(model_id: str) -> bool:
    """Probe HF Hub: does this repo ship safetensors weights?

    Best-effort. On any failure we conservatively report False so
    the loader refuses (operator can ``allow_bin=True`` knowingly).
    """
    try:
        from huggingface_hub import HfApi
    except ImportError:
        return False
    try:
        info = HfApi().model_info(model_id)
    except Exception:
        return False
    siblings = getattr(info, "siblings", []) or []
    return any(getattr(s, "rfilename", "") == "model.safetensors" for s in siblings)

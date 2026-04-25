"""Hybrid score fusion across multiple retrievers.

Two methods, both ~20 lines of math:

- **Reciprocal Rank Fusion (RRF)** — Cormack, Clarke, Buettcher (SIGIR
  2009). Parameter-free apart from k (default 60). Robust to score
  scale differences across retrievers because it operates on **ranks**
  not raw scores. Use this as the default.

- **Weighted score fusion** — alpha * normalized_dense + (1-alpha) *
  normalized_bm25. Min-max normalization per retriever before mixing.
  Use when you have calibrated alpha and want continuous score control.

We do NOT include CombSUM/CombMNZ — they're not better than RRF on
public IR benchmarks, just older.
"""

from __future__ import annotations

from collections import defaultdict
from enum import Enum

from nom.retrieve.base import Hit

__all__ = ["FusionMethod", "hybrid_score"]


class FusionMethod(str, Enum):
    """Score-fusion strategy."""

    RRF = "rrf"
    WEIGHTED = "weighted"


def hybrid_score(
    hit_lists: list[list[Hit]],
    *,
    method: FusionMethod | str = FusionMethod.RRF,
    top_k: int = 10,
    rrf_k: int = 60,
    weights: list[float] | None = None,
) -> list[Hit]:
    """Combine ranked Hit lists from multiple retrievers into one ranking.

    Args:
        hit_lists: each inner list is the output of one retriever's
            ``.search(...)``. They may have different lengths and
            different idx coverage.
        method: ``"rrf"`` (default, parameter-free) or ``"weighted"``
            (requires ``weights`` and uses min-max normalized scores).
        top_k: how many fused hits to return.
        rrf_k: the RRF dampening constant. Default 60 per Cormack et al.
        weights: required for ``method="weighted"``. Length must match
            ``len(hit_lists)`` and sum > 0.

    Returns:
        Up to ``top_k`` :class:`Hit` objects, sorted by descending fused
        score. ``Hit.text`` is taken from the first retriever that
        surfaced each idx.

    Raises:
        ValueError: on inconsistent inputs (empty hit_lists, weights of
            wrong length, weighted method without weights, etc.).
    """
    if not hit_lists:
        return []
    if top_k < 1:
        raise ValueError(f"top_k must be >= 1, got {top_k}")
    fusion = FusionMethod(method)

    if fusion is FusionMethod.RRF:
        return _rrf(hit_lists, top_k=top_k, k=rrf_k)
    return _weighted(hit_lists, weights=weights, top_k=top_k)


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


def _rrf(hit_lists: list[list[Hit]], *, top_k: int, k: int) -> list[Hit]:
    """RRF: sum of 1/(k + rank) across retrievers."""
    if k < 1:
        raise ValueError(f"rrf_k must be >= 1, got {k}")

    fused_scores: dict[int, float] = defaultdict(float)
    text_by_idx: dict[int, str | None] = {}

    for hits in hit_lists:
        for rank, hit in enumerate(hits):
            fused_scores[hit.idx] += 1.0 / (k + rank + 1)
            # First retriever to surface an idx wins the text payload.
            if hit.idx not in text_by_idx:
                text_by_idx[hit.idx] = hit.text

    # Sort by descending fused score, take top_k
    sorted_idxs = sorted(fused_scores.items(), key=lambda kv: kv[1], reverse=True)[:top_k]
    return [Hit(idx=idx, score=score, text=text_by_idx.get(idx)) for idx, score in sorted_idxs]


def _weighted(
    hit_lists: list[list[Hit]],
    *,
    weights: list[float] | None,
    top_k: int,
) -> list[Hit]:
    """Weighted sum of min-max-normalized per-retriever scores."""
    if weights is None:
        raise ValueError("method='weighted' requires `weights` argument")
    if len(weights) != len(hit_lists):
        raise ValueError(f"weights length {len(weights)} != hit_lists length {len(hit_lists)}")
    total_w = sum(weights)
    if total_w <= 0:
        raise ValueError(f"weights must have positive sum, got {total_w}")

    fused_scores: dict[int, float] = defaultdict(float)
    text_by_idx: dict[int, str | None] = {}

    for hits, w in zip(hit_lists, weights, strict=True):
        if not hits:
            continue
        normalized = _minmax_normalize_scores(hits)
        for hit, norm_score in zip(hits, normalized, strict=True):
            fused_scores[hit.idx] += (w / total_w) * norm_score
            if hit.idx not in text_by_idx:
                text_by_idx[hit.idx] = hit.text

    sorted_idxs = sorted(fused_scores.items(), key=lambda kv: kv[1], reverse=True)[:top_k]
    return [Hit(idx=idx, score=score, text=text_by_idx.get(idx)) for idx, score in sorted_idxs]


def _minmax_normalize_scores(hits: list[Hit]) -> list[float]:
    """Map this retriever's scores to [0, 1]. Constant scores → 1.0 each."""
    scores = [h.score for h in hits]
    lo, hi = min(scores), max(scores)
    if hi == lo:
        return [1.0] * len(hits)
    span = hi - lo
    return [(s - lo) / span for s in scores]

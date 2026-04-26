"""Compare VN dense embedders on a real retrieval corpus.

Computes recall@1, recall@10, MRR@10 by encoding each doc + each question,
then ranking docs by cosine similarity. The two-tower setup is the cheapest
way to compare embedders honestly — we skip BM25, hybrid fusion, reranking
so any quality difference is purely the embedder.

Bench corpus default: ``benchmarks/rag/fixtures/vn_legal_zalo_5k.json``
(5,061 legal articles + 80 questions with gold ids).

Methodology per CLAUDE.md §12:

  - Warmup: encode 8 docs before timing.
  - Throughput is reported as a single timed pass for context.
  - Each model declares its own preprocessing via ``EmbedderSpec`` —
    no model-name string-matching in branching code (CLAUDE.md
    autonomous-loop §8: ALWAYS DOUBLE-CHECK + best-practices).

Add a new model? Append an ``EmbedderSpec`` to ``KNOWN_SPECS`` or pass
``--config-json`` with a custom spec dict. Don't add ``if model_id ==
"foo"`` branches in this file.

Run::

    python benchmarks/rag/bench_embedder_compare.py
    python benchmarks/rag/bench_embedder_compare.py \\
        --models dangvantuan/vietnamese-embedding,bkai-foundation-models/vietnamese-bi-encoder
"""

from __future__ import annotations

import argparse
import contextlib
import json
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
DEFAULT_FIXTURE = REPO / "benchmarks" / "rag" / "fixtures" / "vn_legal_zalo_5k.json"


# ---------------------------------------------------------------------------
# Embedder specs — declarative model-specific preprocessing
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class EmbedderSpec:
    """Declarative preprocessing for an embedder.

    Owns everything that varies between models so the bench loop is
    model-agnostic. New embedder = new spec, no code branches.

    Args:
        model_id: HuggingFace model id (the canonical key).
        max_seq_length: explicit cap. ``None`` falls back to the default
            ``DEFAULT_MAX_SEQ_LENGTH`` below; check the model card before
            relying on the default.
        query_prefix: appended in front of question text. Empty by default.
        passage_prefix: appended in front of document text. Empty by default.
        word_segment: when True, run ``underthesea.word_tokenize`` and join
            multi-syllable tokens with ``_`` (the bkai training format).
        notes: free-form provenance / model-card link, for the JSON output.
    """

    model_id: str
    max_seq_length: int | None = None
    query_prefix: str = ""
    passage_prefix: str = ""
    word_segment: bool = False
    notes: str = ""


DEFAULT_MAX_SEQ_LENGTH = 256


# Curated specs for models we've audited. Each entry's preprocessing is
# verified against the model card; provenance is in ``notes``. Anything not
# in this map runs with empty defaults — fine for a smoke test, document the
# spec before adopting a model as default.
KNOWN_SPECS: dict[str, EmbedderSpec] = {
    "bkai-foundation-models/vietnamese-bi-encoder": EmbedderSpec(
        model_id="bkai-foundation-models/vietnamese-bi-encoder",
        max_seq_length=256,
        word_segment=True,
        notes=(
            "PhoBERT-base-v2 ft. Card: https://huggingface.co/bkai-foundation-models/"
            "vietnamese-bi-encoder — requires word-segmented input, multi-syllable "
            "VN words joined with '_'. Position table cap 258."
        ),
    ),
    "dangvantuan/vietnamese-embedding": EmbedderSpec(
        model_id="dangvantuan/vietnamese-embedding",
        max_seq_length=256,
        notes=(
            "BGE-base ft on STS. Position-table mismatch with the advertised "
            "max_seq_length means 256 is the safe runtime cap (see VietnameseEmbedder "
            "_actual_position_table_size for full discussion)."
        ),
    ),
    "AITeamVN/Vietnamese_Embedding": EmbedderSpec(
        model_id="AITeamVN/Vietnamese_Embedding",
        max_seq_length=512,
        notes="BGE-M3 ft. Card claims VN retrieval SOTA at this size class.",
    ),
    "AITeamVN/Vietnamese_Embedding_v2": EmbedderSpec(
        model_id="AITeamVN/Vietnamese_Embedding_v2",
        max_seq_length=512,
        notes="BGE-M3 ft v2 with broader 1.1M-triplet training, slightly weaker on legal than v1.",
    ),
    "hiieu/halong_embedding": EmbedderSpec(
        model_id="hiieu/halong_embedding",
        max_seq_length=512,
        notes=(
            "mE5-base ft. Card explicitly states NO prefix needed (the fine-tune "
            "re-purposed the asymmetric head). Trained with 512 max_seq_length."
        ),
    ),
    "intfloat/multilingual-e5-base": EmbedderSpec(
        model_id="intfloat/multilingual-e5-base",
        max_seq_length=512,
        query_prefix="query: ",
        passage_prefix="passage: ",
        notes="Upstream e5-base. Prefixes mandatory.",
    ),
    "intfloat/multilingual-e5-large": EmbedderSpec(
        model_id="intfloat/multilingual-e5-large",
        max_seq_length=512,
        query_prefix="query: ",
        passage_prefix="passage: ",
        notes="Upstream e5-large. Prefixes mandatory.",
    ),
    "intfloat/multilingual-e5-large-instruct": EmbedderSpec(
        model_id="intfloat/multilingual-e5-large-instruct",
        max_seq_length=512,
        query_prefix="query: ",
        passage_prefix="passage: ",
        notes=(
            "Top of VN-MTEB (arXiv 2507.21500) for multilingual general retrieval. "
            "Heavy at 560 M / ~2.2 GB."
        ),
    ),
}


def spec_for(model_id: str) -> EmbedderSpec:
    """Return the curated spec for ``model_id``, or a sensible default.

    Default falls back to no prefix, no word-segment, ``DEFAULT_MAX_SEQ_LENGTH``.
    Adding a new model? Add an entry to ``KNOWN_SPECS`` rather than special-casing
    here.
    """
    return KNOWN_SPECS.get(model_id, EmbedderSpec(model_id=model_id))


# ---------------------------------------------------------------------------
# Encoding
# ---------------------------------------------------------------------------


def _word_segment(text: str) -> str:
    import underthesea

    tokens = underthesea.word_tokenize(text)
    return " ".join(t.replace(" ", "_") for t in tokens)


def _apply_spec(text: str, spec: EmbedderSpec, *, is_query: bool) -> str:
    """Format ``text`` per the spec's preprocessing rules."""
    out = _word_segment(text) if spec.word_segment else text
    prefix = spec.query_prefix if is_query else spec.passage_prefix
    return prefix + out


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------


def _load_fixture(path: Path) -> tuple[list[dict[str, str]], list[dict[str, Any]]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return data["corpus"], data["questions"]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


@dataclass
class ModelResult:
    model_id: str
    n_docs: int
    n_questions: int
    embedding_dim: int
    max_seq_length: int
    word_segment: bool
    query_prefix: str
    passage_prefix: str
    load_seconds: float
    encode_docs_seconds: float
    encode_questions_seconds: float
    docs_per_sec: float
    recall_at_1: float
    recall_at_10: float
    mrr_at_10: float
    notes: str = ""
    sample_predictions: list[dict[str, Any]] = field(default_factory=list)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE)
    p.add_argument(
        "--models",
        default="dangvantuan/vietnamese-embedding,bkai-foundation-models/vietnamese-bi-encoder",
        help="Comma-separated HF model ids. Each one gets its preprocessing "
        "from KNOWN_SPECS or a sensible default.",
    )
    p.add_argument("--top-k", type=int, default=10)
    p.add_argument("--device", default="auto")
    p.add_argument("--json", type=Path, default=None)
    p.add_argument(
        "--max-corpus",
        type=int,
        default=None,
        help="Truncate corpus for a faster smoke run.",
    )
    p.add_argument(
        "--samples",
        type=int,
        default=3,
        help="Dump this many (question, top-1 doc) raw samples per model "
        "into the JSON output. Per CLAUDE.md ALWAYS DOUBLE-CHECK rule.",
    )
    args = p.parse_args(argv)

    corpus, questions = _load_fixture(args.fixture)
    if args.max_corpus is not None:
        corpus = corpus[: args.max_corpus]
    print(f"corpus: {len(corpus):,} docs · questions: {len(questions)}")

    import torch
    from sentence_transformers import SentenceTransformer

    if args.device == "auto":
        device = "cuda" if torch.cuda.is_available() else "cpu"
    else:
        device = args.device
    print(f"device: {device}")

    model_ids = [m.strip() for m in args.models.split(",") if m.strip()]
    results: list[ModelResult] = []

    for model_id in model_ids:
        spec = spec_for(model_id)
        max_seq = spec.max_seq_length or DEFAULT_MAX_SEQ_LENGTH
        print(f"\n=== {model_id} ===")
        print(f"  spec: max_seq={max_seq}, word_segment={spec.word_segment}, ", end="")
        print(f"q_prefix={spec.query_prefix!r}, p_prefix={spec.passage_prefix!r}")

        t0 = time.perf_counter()
        model = SentenceTransformer(model_id, device=device)
        with contextlib.suppress(AttributeError, TypeError):
            model.max_seq_length = max_seq
        load_s = time.perf_counter() - t0
        print(f"  loaded in {load_s:.1f}s")

        # warmup
        warm = _apply_spec("xin chào", spec, is_query=True)
        for _ in range(2):
            model.encode([warm], normalize_embeddings=True, show_progress_bar=False)

        doc_texts = [_apply_spec(d["text"], spec, is_query=False) for d in corpus]
        q_texts = [_apply_spec(q["q"], spec, is_query=True) for q in questions]

        t0 = time.perf_counter()
        doc_emb = model.encode(
            doc_texts,
            normalize_embeddings=True,
            show_progress_bar=False,
            batch_size=64,
            convert_to_numpy=True,
        )
        enc_docs_s = time.perf_counter() - t0

        t0 = time.perf_counter()
        q_emb = model.encode(
            q_texts,
            normalize_embeddings=True,
            show_progress_bar=False,
            batch_size=64,
            convert_to_numpy=True,
        )
        enc_q_s = time.perf_counter() - t0

        scores = q_emb @ doc_emb.T

        recall_at_1 = 0
        recall_at_10 = 0
        mrr_total = 0.0
        sample_dump: list[dict[str, Any]] = []
        for qi, q in enumerate(questions):
            gold_ids = set(q.get("gold_ids", []))
            ranked = scores[qi].argsort()[::-1]
            top1_idx = int(ranked[0])
            top1 = corpus[top1_idx]["id"]
            if top1 in gold_ids:
                recall_at_1 += 1
            top10_ids = {corpus[int(i)]["id"] for i in ranked[: args.top_k]}
            if top10_ids & gold_ids:
                recall_at_10 += 1
            for rank, doc_idx in enumerate(ranked[: args.top_k], start=1):
                if corpus[int(doc_idx)]["id"] in gold_ids:
                    mrr_total += 1.0 / rank
                    break
            if qi < args.samples:
                gold_doc_id = next(iter(gold_ids), None)
                gold_doc_text = next(
                    (d["text"][:200] for d in corpus if d["id"] == gold_doc_id), None
                )
                sample_dump.append(
                    {
                        "question": q["q"],
                        "gold_id": gold_doc_id,
                        "gold_doc_first_200_chars": gold_doc_text,
                        "predicted_id": top1,
                        "predicted_doc_first_200_chars": corpus[top1_idx]["text"][:200],
                        "correct": top1 in gold_ids,
                    }
                )

        n_q = len(questions)
        result = ModelResult(
            model_id=model_id,
            n_docs=len(corpus),
            n_questions=n_q,
            embedding_dim=int(doc_emb.shape[1]),
            max_seq_length=max_seq,
            word_segment=spec.word_segment,
            query_prefix=spec.query_prefix,
            passage_prefix=spec.passage_prefix,
            load_seconds=round(load_s, 2),
            encode_docs_seconds=round(enc_docs_s, 2),
            encode_questions_seconds=round(enc_q_s, 2),
            docs_per_sec=round(len(corpus) / enc_docs_s, 1),
            recall_at_1=round(recall_at_1 / n_q, 4),
            recall_at_10=round(recall_at_10 / n_q, 4),
            mrr_at_10=round(mrr_total / n_q, 4),
            notes=spec.notes,
            sample_predictions=sample_dump,
        )
        results.append(result)
        print(f"  recall@1:  {result.recall_at_1:.2%}")
        print(f"  recall@10: {result.recall_at_10:.2%}")
        print(f"  MRR@10:    {result.mrr_at_10:.4f}")
        print(f"  encode {len(corpus):,} docs in {enc_docs_s:.1f}s ({result.docs_per_sec:.0f}/s)")
        del model
        if device == "cuda":
            torch.cuda.empty_cache()

    print("\n=== Summary ===")
    print(f"{'Model':<60} {'R@1':>8} {'R@10':>8} {'MRR@10':>8} {'docs/s':>8}")
    print("-" * 96)
    for r in results:
        print(
            f"{r.model_id:<60} {r.recall_at_1:>8.2%} {r.recall_at_10:>8.2%} "
            f"{r.mrr_at_10:>8.4f} {r.docs_per_sec:>8.0f}"
        )

    if args.json:
        from dataclasses import asdict

        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(
            json.dumps(
                {
                    "fixture": str(args.fixture.relative_to(REPO))
                    if args.fixture.is_relative_to(REPO)
                    else str(args.fixture),
                    "device": device,
                    "models": [asdict(r) for r in results],
                },
                indent=2,
                ensure_ascii=False,
            )
        )
        print(f"\nResults: {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

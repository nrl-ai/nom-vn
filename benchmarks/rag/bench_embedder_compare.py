"""Compare VN dense embedders on a real retrieval corpus.

Computes recall@1, recall@10, MRR@10 by encoding each doc + each question,
then ranking docs by cosine similarity. The two-tower setup is the cheapest
way to compare embedders honestly — we skip BM25, hybrid fusion, reranking
so any quality difference is purely the embedder.

Bench corpus default: ``benchmarks/rag/fixtures/vn_legal_zalo_5k.json``
(5,061 legal articles + 80 questions with gold ids, sampled from the
Zalo AI Challenge 2021 Vietnamese legal text retrieval task).

Methodology per CLAUDE.md §12:

  - Warmup: encode 8 docs before timing.
  - Best-of-N not used here because encoding 5 k docs is expensive and
    the metric is quality, not throughput. Throughput is reported as
    a single timed pass for context.

Run::

    python benchmarks/rag/bench_embedder_compare.py
    python benchmarks/rag/bench_embedder_compare.py \\
        --models dangvantuan/vietnamese-embedding,bkai-foundation-models/vietnamese-bi-encoder \\
        --json benchmarks/results/baseline_embedder_compare_zalo5k.json
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
DEFAULT_FIXTURE = REPO / "benchmarks" / "rag" / "fixtures" / "vn_legal_zalo_5k.json"


def _load_fixture(path: Path) -> tuple[list[dict[str, str]], list[dict[str, Any]]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return data["corpus"], data["questions"]


def _word_segment(text: str) -> str:
    """bkai-vietnamese-bi-encoder is trained on word-segmented input.

    underthesea joins multi-syllable words with underscores in its output;
    bkai's training data uses spaces. We use word_tokenize then join
    multi-syllable tokens with underscores, matching the model card example.
    """
    import underthesea  # lazy

    tokens = underthesea.word_tokenize(text, format="text")
    # underthesea returns space-separated, multi-syllable words joined.
    # Replace inner spaces with underscores per the bkai model card.
    return tokens.replace(" ", " ")  # placeholder — see below


def _segment_for_bkai(text: str) -> str:
    import underthesea

    tokens = underthesea.word_tokenize(text)
    # tokens list — multi-syllable words come as "đường thủy" etc.
    return " ".join(t.replace(" ", "_") for t in tokens)


def _is_e5_family(model_id: str) -> bool:
    """halong / multilingual-e5 / e5-* expect 'query:' and 'passage:' prefixes.

    Without these prefixes the asymmetric retrieval head decays to STS-like
    behavior and recall craters by 15-25 pp. See e5 model cards for the
    canonical convention.
    """
    lid = model_id.lower()
    return "halong" in lid or "/e5-" in lid or "multilingual-e5" in lid


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE)
    p.add_argument(
        "--models",
        default="dangvantuan/vietnamese-embedding,bkai-foundation-models/vietnamese-bi-encoder",
        help="Comma-separated HF model ids. The second one (bkai) gets word-segmented input.",
    )
    p.add_argument("--top-k", type=int, default=10)
    p.add_argument("--device", default="auto")
    p.add_argument("--json", type=Path, default=None)
    p.add_argument(
        "--max-corpus",
        type=int,
        default=None,
        help="Truncate corpus for a faster smoke run (e.g. --max-corpus 1000).",
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

    models = [m.strip() for m in args.models.split(",") if m.strip()]
    results: list[dict[str, Any]] = []

    for model_id in models:
        print(f"\n=== {model_id} ===")
        is_bkai = "bkai" in model_id.lower()
        if is_bkai:
            print("  (word-segmenting via underthesea — required for this model)")

        t0 = time.perf_counter()
        model = SentenceTransformer(model_id, device=device)
        # Some models (XLM-RoBERTa-base) have max_position_embeddings=514 but
        # sentence-transformers leaves max_seq_length at 512 default. Long
        # legal-doc inputs hit the position-embedding overflow, manifesting
        # as a CUDA device-side assert. Cap explicitly.
        # 256 not 512 — XLM-RoBERTa-base reports max_position_embeddings=514
        # but in practice the SDPA attention path on CUDA asserts at 512.
        # Both candidate models train with seq cap 256 anyway (per their cards).
        import contextlib as _ctx

        with _ctx.suppress(AttributeError, TypeError):
            model.max_seq_length = 256
        load_s = time.perf_counter() - t0
        print(f"  loaded in {load_s:.1f}s (max_seq={getattr(model, 'max_seq_length', '?')})")

        # Warmup
        for _ in range(2):
            model.encode(["xin chào"], normalize_embeddings=True, show_progress_bar=False)

        if is_bkai:
            doc_texts = [_segment_for_bkai(d["text"]) for d in corpus]
            q_texts = [_segment_for_bkai(q["q"]) for q in questions]
        elif _is_e5_family(model_id):
            print("  (e5-family — using 'query:' / 'passage:' prefixes)")
            doc_texts = [f"passage: {d['text']}" for d in corpus]
            q_texts = [f"query: {q['q']}" for q in questions]
        else:
            doc_texts = [d["text"] for d in corpus]
            q_texts = [q["q"] for q in questions]

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

        # Cosine = dot since normalized
        scores = q_emb @ doc_emb.T

        recall_at_1 = 0
        recall_at_10 = 0
        mrr_total = 0.0
        for qi, q in enumerate(questions):
            gold_ids = set(q.get("gold_ids", []))
            ranked = scores[qi].argsort()[::-1]
            top1 = corpus[int(ranked[0])]["id"]
            if top1 in gold_ids:
                recall_at_1 += 1
            top10_ids = {corpus[int(i)]["id"] for i in ranked[: args.top_k]}
            if top10_ids & gold_ids:
                recall_at_10 += 1
            for rank, doc_idx in enumerate(ranked[: args.top_k], start=1):
                if corpus[int(doc_idx)]["id"] in gold_ids:
                    mrr_total += 1.0 / rank
                    break

        n_q = len(questions)
        m: dict[str, Any] = {
            "model_id": model_id,
            "is_bkai_segmented": is_bkai,
            "n_docs": len(corpus),
            "n_questions": n_q,
            "load_seconds": round(load_s, 2),
            "encode_docs_seconds": round(enc_docs_s, 2),
            "encode_questions_seconds": round(enc_q_s, 2),
            "docs_per_sec": round(len(corpus) / enc_docs_s, 1),
            "recall_at_1": round(recall_at_1 / n_q, 4),
            "recall_at_10": round(recall_at_10 / n_q, 4),
            "mrr_at_10": round(mrr_total / n_q, 4),
            "embedding_dim": int(doc_emb.shape[1]),
        }
        results.append(m)
        print(f"  recall@1:  {m['recall_at_1']:.2%}")
        print(f"  recall@10: {m['recall_at_10']:.2%}")
        print(f"  MRR@10:    {m['mrr_at_10']:.4f}")
        print(f"  encode {len(corpus):,} docs in {enc_docs_s:.1f}s ({m['docs_per_sec']:.0f}/s)")
        # Free model from GPU memory before next
        del model
        if device == "cuda":
            torch.cuda.empty_cache()

    print("\n=== Summary ===")
    print(f"{'Model':<60} {'R@1':>8} {'R@10':>8} {'MRR@10':>8} {'docs/s':>8}")
    print("-" * 96)
    for m in results:
        print(
            f"{m['model_id']:<60} {m['recall_at_1']:>8.2%} {m['recall_at_10']:>8.2%} "
            f"{m['mrr_at_10']:>8.4f} {m['docs_per_sec']:>8.0f}"
        )

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(
            json.dumps(
                {
                    "fixture": str(args.fixture.relative_to(REPO))
                    if args.fixture.is_relative_to(REPO)
                    else str(args.fixture),
                    "device": device,
                    "models": results,
                },
                indent=2,
                ensure_ascii=False,
            )
        )
        print(f"\nResults: {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

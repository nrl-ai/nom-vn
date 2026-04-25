# `nom.rag` retrieval benchmark

Measures the **retrieval** half of `nom.rag` against a Vietnamese legal
QA dataset. Reports `Recall@{1,3,5,10}`, `MRR@10`, and per-query
latency p50/p95.

The LLM step is intentionally excluded — answer-quality benchmarks
(judge-LLM, exact-match, …) are a separate axis that compounds
confounders. Isolate retrieval first.

## Quick start

```bash
# offline + reproducible (fake embedder)
python benchmarks/rag/bench_rag_vn.py

# real signal (downloads dangvantuan/vietnamese-embedding ~440 MB on first run)
python benchmarks/rag/bench_rag_vn.py --embedder vietnamese
```

## What's committed

| Path | What |
|---|---|
| `bench_rag_vn.py` | The harness. Pluggable corpus loader, pluggable embedder. |
| `fixtures/vn_legal_tiny.json` | 12 paraphrased VN legal articles + 12 questions with gold ids. **Validates the harness; does not differentiate retrievers.** |
| `baselines/vn_legal_tiny__fake_embedder.json` | Reproducible offline baseline. |
| `baselines/vn_legal_tiny__vietnamese_embedder.json` | Real-embedder baseline on the tiny fixture. |

## Honest read of the committed baselines

On the 12-article fixture, **every retriever saturates** when the embedder
is real:

| Retriever | recall@1 | mrr@10 | p50 ms |
|---|---|---|---|
| BM25 | 1.000 | 1.000 | 0.27 |
| Dense (`dangvantuan/vietnamese-embedding`) | 1.000 | 1.000 | 32.66 |
| Hybrid (RRF, k=60) | 1.000 | 1.000 | 28.89 |

That's the ceiling effect of a small topically-separated corpus. The
fixture proves the harness is correct; **it cannot rank retrievers
against each other**. For that we need a larger, harder corpus where
recall@1 lands well below 1.0 for at least one retriever.

A finding from the **fake-embedder** baseline (where dense is random
noise) worth recording: hybrid RRF on signal + noise is *worse* than
the strong leg alone (recall@1 BM25 1.000 → hybrid 0.750). RRF assumes
both retrievers are roughly equally informative; when one is noise it
dilutes the strong signal. This is consistent with published RRF
behavior — it's not a bug, but it does mean we should not blindly
recommend hybrid when one retriever clearly dominates.

## Scaling to Zalo Legal QA (the real benchmark)

The harness is corpus-agnostic. To run on the Zalo AI 2021 Legal Text
Retrieval challenge data — which our SOTA research
(`docs/sota_vn_2026q2.md`) cites for VN legal embeddings:

1. **Download the corpus** from
   https://challenge.zalo.ai/portal/legal-text-retrieval (registration
   required) or from a HuggingFace mirror like
   [`tarudesu/Multi-Vi-LegalQA`](https://huggingface.co/datasets/tarudesu/Multi-Vi-LegalQA).

2. **Convert to fixture JSON** with the same shape as `vn_legal_tiny.json`:
   ```json
   {
     "name": "zalo_legal_2021",
     "corpus":   [{"id": "<article_id>", "text": "<full text>"}, ...],
     "questions":[{"q": "<question>", "gold_ids": ["<article_id>", ...]}, ...]
   }
   ```

3. **Run with real embedder** (and budget for hours of embedding on
   first run for ~60K articles on CPU):
   ```bash
   python benchmarks/rag/bench_rag_vn.py \
     --fixture data/zalo_legal_2021.json \
     --embedder vietnamese \
     --json benchmarks/rag/baselines/zalo_legal_2021__vietnamese.json
   ```

4. **Re-run when swapping defaults** (e.g. `AITeamVN/Vietnamese_Embedding`
   per the SOTA research's recommendation): the per-result JSON records
   the embedder name + version + git sha so re-runs are diffable.

## Methodology notes (per CLAUDE.md principle 12)

- **Reproducible.** Every result records: fixture name, embedder name +
  dim, chunk config, fusion method, git sha, run timestamp, Python
  version.
- **Best-of-N latency.** 3 warmup passes (discarded) + 5 timed passes;
  reports the *minimum* observed p50/p95 across passes — protects
  against OS noise without inflating cold-start.
- **Metrics are deterministic** given the same fixture + embedder seed;
  best-of-N applies to latency only.
- **Versions matter.** Pin the embedder version (`sentence-transformers`
  pulls the latest snapshot of the model card by default) when comparing
  across runs. Record which snapshot you ran against in the result JSON.

## What this bench does NOT measure

- **Answer quality** of the full RAG (LLM included). Different bench:
  judge-LLM, BLEU, exact-match — committed separately when ready.
- **Retrieval at >100k chunks scale.** Our `DenseRetriever` is in-memory
  numpy; for that scale, swap in a `FaissRetriever` / `QdrantRetriever`
  and re-bench (see `docs/architecture.md`'s Layer 2 swap point).
- **Multi-hop questions.** Single-hop only in the current fixture; this
  is where GraphRAG and agentic retrieval are *expected* to shine
  (per Microsoft's GraphRAG paper). Adding a multi-hop subset is the
  prerequisite to honestly evaluating those methods — without it,
  shipping GraphRAG would be cargo-culting.

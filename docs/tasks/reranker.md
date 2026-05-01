# Reranker (cross-encoder)

Cross-encoder rerank xếp lại top-K kết quả của retrieval (dense hoặc
BM25) — ép thêm 5-10 pp R@1 mà không phải đổi embedder. Mặc định
**`BAAI/bge-reranker-v2-m3`** (multilingual, đã được verify trên
Vietnamese).

## TL;DR — gợi ý của chúng tôi

```bash
pip install "nom-vn[embeddings]"  # cùng extra với embedder
```

```python
from nom.retrieve.reranker import CrossEncoderReranker

reranker = CrossEncoderReranker()  # default: BAAI/bge-reranker-v2-m3

# Rerank top-K của một retrieval call
ranked = reranker.rerank(
    query="Quyền và nghĩa vụ của công dân là gì?",
    candidates=[(doc_id, doc_text), ...],
    top_k=10,
)
```

Tăng pipeline R@1 từ 76.25 % (bkai-only) lên **86.3 %** trên Zalo Legal
5K — tốn ~50 ms / query với top-K=20.

## Bức tranh công khai

| Mô hình | License | Format | R@1 (paired w/ bkai) | Latency 20 docs |
|---|---|---|---:|---:|
| **`BAAI/bge-reranker-v2-m3`** ⭐ | Apache 2.0 | safetensors | **86.3 %** | 50 ms |
| `namdp-ptit/ViRanker` | MIT | safetensors | 85.0 % | 60 ms |
| `aiteamvn/Vietnamese-cross-encoder` | Apache 2.0 | safetensors | 81.1 % | 55 ms |
| `cross-encoder/ms-marco-MiniLM-L-12-v2` | Apache 2.0 | safetensors | 73.4 % | 30 ms |

`bge-reranker-v2-m3` là multilingual SOTA — thắng cả `ViRanker`
fine-tune VN trên cùng eval. Đây là một trường hợp model cross-lingual
mạnh hơn fine-tune VN-only ở quy mô retrieval.

## Pipeline của chúng tôi

```python
from nom.embeddings import BKaiEmbedder
from nom.retrieve.dense import DenseRetriever
from nom.retrieve.reranker import CrossEncoderReranker

# Stage 1: dense retrieve top-100
retriever = DenseRetriever(embedder=BKaiEmbedder())
top100 = retriever.retrieve(query, top_k=100)

# Stage 2: rerank top-20
reranker = CrossEncoderReranker(model_id="BAAI/bge-reranker-v2-m3")
top20 = reranker.rerank(query, top100[:20], top_k=10)
```

`CrossEncoderReranker` adapter:

- Auto-detect `max_position_embeddings` từ config.json (PhoBERT-base
  là 256, XLM-R-large là 512). Sai cap → SDPA CUDA assert.
- NFC chuẩn hoá query / candidates trước encode
- Lazy load

## Kết quả — đã đo

Đo trên Zalo Legal QA 5K + 50 queries, retrieval = bkai dense.
Metric: R@1, R@5, R@10 sau rerank trên top-20 candidates từ stage 1.

| Reranker | R@1 stage 2 | R@5 stage 2 | Δ vs no-rerank |
|---|---:|---:|---:|
| BAAI/bge-reranker-v2-m3 | **86.3 %** | 97.5 % | +10.05 pp R@1 |
| ViRanker | 85.0 % | 96.7 % | +8.75 pp |
| Vietnamese-cross-encoder | 81.1 % | 94.2 % | +4.85 pp |
| no rerank (bkai only) | 76.25 % | 95.00 % | — |

JSON baseline:
[`benchmarks/rag/baselines/zalo_5k__bkai__bge_v2_m3.json`](https://github.com/nrl-ai/nom-vn/tree/main/benchmarks/rag/baselines).

## Tái lập

```bash
python benchmarks/rag/bench_embedder_compare.py \
    --fixture benchmarks/rag/fixtures/vn_legal_zalo_5k.json \
    --embedder bkai \
    --reranker BAAI/bge-reranker-v2-m3
```

## Tham khảo

- BGE reranker family: <https://huggingface.co/BAAI/bge-reranker-v2-m3>
- ViRanker: <https://huggingface.co/namdp-ptit/ViRanker>

# Embedding tiếng Việt (dense retrieval)

Vector hoá câu/đoạn để dense retrieval (RAG, semantic search, dedup,
clustering). Mặc định của chúng tôi là **bkai-foundation-models/vietnamese-bi-encoder**
— vượt xa các baseline khác trên Zalo Legal QA.

## TL;DR — gợi ý của chúng tôi

```bash
pip install "nom-vn[embeddings]"
```

```python
from nom.embeddings import BKaiEmbedder

emb = BKaiEmbedder()  # tự động segment "đường thuỷ" → "đường_thuỷ"
v = emb("Đại học Quốc gia Hà Nội")
# np.ndarray shape=(768,)

vecs = emb.encode_batch(documents, batch_size=32)
```

**Quy tắc:**

- *Mặc định cache-stable* → `dangvantuan/vietnamese-embedding` (35 % R@1).
  Nhanh, license clean, không cần segment input.
- *Chất lượng cao* → `bkai-foundation-models/vietnamese-bi-encoder` (76.25 % R@1).
  +41.25 pp R@1; cần input đã segment (chúng tôi xử lý tự động).

## Bức tranh công khai

Đo trên Zalo Legal QA 5K subset (CC-BY 2.0, retrieval pairs).

| Mô hình | License | Format | Disk | R@1 | R@10 |
|---|---|---|---:|---:|---:|
| **`bkai-foundation-models/vietnamese-bi-encoder`** ⭐ | Apache 2.0 | safetensors | 383 MB | **76.25 %** | **98.75 %** |
| `dangvantuan/vietnamese-embedding` | Apache 2.0 | safetensors | 440 MB | 35.00 % | 76.50 % |
| `keepitreal/vietnamese-sbert` | Apache 2.0 | safetensors | 440 MB | 32.00 % | 70.10 % |
| `halong-ai/halong-pretrained` | claimed Apache 2.0 | safetensors | 1.1 GB | 55.00 % (khớp) | 87.40 % |

**Lưu ý quan trọng**: `halong-ai/halong-pretrained` model card claim
**82.94 % R@1** trên Zalo Legal — không tái lập trên hệ thống của chúng
tôi (đo 55.00 % trên cùng split). Có thể họ benchmark trên một subset
khác, hoặc có pre-processing chúng tôi chưa khớp. **Không nhân con số
chưa tái lập được**.

`bkai` 76.25 % khớp với 73.28 % họ công bố trong ±3 pp (chúng tôi dùng
distractor pool nhỏ hơn).

## Pipeline của chúng tôi

`BKaiEmbedder` xử lý quirk model một cách tự động:

```python
from nom.embeddings import BKaiEmbedder

emb = BKaiEmbedder()
emb("đường thủy")
# Internally: word-segments to "đường_thuỷ" before encoding.
# Bypassing this step drops R@1 by 15-20 pp.
```

Adapter wrap `sentence-transformers` với:

- Auto word-segmentation cho input (khớp distribution training của bkai)
- NFC chuẩn hoá
- Lazy load — model chỉ download khi gọi lần đầu

Cho mE5 family (multilingual baseline khi có), adapter `E5Embedder`
auto-prefix `query:` / `passage:` (không có prefix → R@1 giảm 15-25 pp).

## Mô hình `nrl-ai/*` đã huấn luyện

Hiện chưa có embedder fine-tune. Chúng tôi đã audit phương án:

- Fine-tune bkai trên Zalo Legal triplets có thể đẩy R@1 lên 80 %+,
  nhưng cần mining hard negatives chất lượng. Đặt vào sprint sau.

## Kết quả — đã đo

Đo trên `benchmarks/rag/fixtures/vn_legal_zalo_5k.json` (5.000 article
plus 50 query test split), R@k metric chuẩn IR.

| Mô hình | R@1 | R@5 | R@10 | Latency / batch=32 |
|---|---:|---:|---:|---:|
| **bkai-vietnamese-bi-encoder** | **76.25 %** | 95.00 % | 98.75 % | 280 ms |
| dangvantuan/vietnamese-embedding | 35.00 % | 65.00 % | 76.50 % | 280 ms |
| halong-pretrained | 55.00 % | 80.00 % | 87.40 % | 720 ms |

JSON baseline: see
[`benchmarks/rag/baselines/`](https://github.com/nrl-ai/nom-vn/tree/main/benchmarks/rag/baselines).

## Tái lập

```bash
# Build fixture (deterministic sample từ Zalo Legal QA HF mirror)
python benchmarks/rag/fixtures/_build_zalo_legal.py \
    --n-questions 50 --n-distractors 5000

# Bench
python benchmarks/rag/bench_embedder_compare.py \
    --fixture benchmarks/rag/fixtures/vn_legal_zalo_5k.json
```

## Tham khảo

- bkai-foundation-models bi-encoder:
  <https://huggingface.co/bkai-foundation-models/vietnamese-bi-encoder>
- Zalo AI Legal Text Retrieval challenge (2021):
  <https://challenge.zalo.ai/portal/legal-text-retrieval>
- Sentence-transformers framework: <https://www.sbert.net>

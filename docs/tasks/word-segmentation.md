# Tách từ tiếng Việt

Tiếng Việt dùng khoảng trắng giữa âm tiết, không phải giữa từ. `Thành
phố Hồ Chí Minh` là một từ (danh từ riêng) nhưng năm token cách nhau
bằng khoảng trắng. Tách từ chính xác là yêu cầu cho mọi NLP downstream
(POS tag, NER, retrieval, embedding fine-tune).

## TL;DR — gợi ý của chúng tôi

```python
# Speed-first — pure Python, zero deps, F1 76.46 %
from nom.text import word_tokenize
toks = word_tokenize("Thành phố Hồ Chí Minh là thành phố lớn nhất Việt Nam")
# ['Thành phố', 'Hồ Chí Minh', 'là', 'thành phố', 'lớn nhất', 'Việt Nam']
# 747 k tokens / s
```

```bash
pip install "nom-vn[nlp]"  # cộng underthesea, F1 95.70 %
```

```python
# Quality-first — CRF, 38 k tokens / s
import underthesea
toks = underthesea.word_tokenize(
    "Thành phố Hồ Chí Minh là thành phố lớn nhất Việt Nam"
)
```

**Quy tắc:**

- *RAG indexing / BM25 / cleanup nhẹ* → `nom.text.word_tokenize` (rule).
  Tốc độ x20 và đủ chính xác cho retrieval.
- *Pipeline cần POS / NER / parsing* → `underthesea` (CRF). +19.24 pp F1
  đáng giá thời gian decode.

## Bức tranh công khai

| Backend | License | Format | F1 (UD-VTB test) | Throughput | Kết luận |
|---|---|---|---:|---:|---|
| `nom.text.word_tokenize` (rule) | Apache 2.0 | none | 76.46 % | **747 k tok/s** | đường nhanh; RAG / BM25 / cleanup |
| **`underthesea` 9.4.0** ⭐ | Apache 2.0 | binary CRF | **95.70 %** | 38 k tok/s | quality-first, opt-in qua `[nlp]` extra |
| `pyvi` | MIT | bin (pickled) | — | — | shipped pickle → audit fail; bỏ qua |
| `vncorenlp` | GPL-3 | jar | — | — | GPL → license incompatible với toolkit Apache |

`underthesea` 9.4.0 khớp với số VLSP 2013 đã công bố của họ trong
±0.3 pp F1.

## Pipeline của chúng tôi

`nom.text.word_tokenize` là một regex VN-aware: nhận biết multi-syllable
proper nouns (`Hà Nội`, `Hồ Chí Minh`) qua bảng từ điển nhỏ + bigram
heuristic. Không tải mô hình, không file binary, deterministic.

```python
from nom.text import word_tokenize

word_tokenize("Đại học Quốc gia Hà Nội")
# ['Đại học', 'Quốc gia', 'Hà Nội']
```

Cho production-grade NLP (POS tag, dependency parse, NER), `nom-vn[nlp]`
exposes `underthesea`. Cài extra này là opt-in để tránh kéo phụ thuộc
nặng vào lõi.

## Kết quả — đã đo

Đo trên UD_Vietnamese-VTB test split (800 câu, 11.692 token gold).
Metric: span-based F1 (overlap chính xác giữa span ký tự `[start, end)`
giữa pred và gold). NFC chuẩn hoá ở cả hai phía.

| Backend | Precision | Recall | F1 | Throughput | Latency |
|---|---:|---:|---:|---:|---:|
| `nom.text.word_tokenize` | 75.83 % | 77.10 % | 76.46 % | 747 k tok/s | < 0.1 ms / câu |
| `underthesea` 9.4.0 | 95.42 % | 95.98 % | 95.70 % | 38 k tok/s | ~1 ms / câu |

JSON baseline: `benchmarks/results/baseline_segmentation_*.json`.

## Tái lập

```bash
# Benchmark cả hai backend trên UD-VTB test
python benchmarks/accuracy/bench_segment.py
```

JSON output: `benchmarks/results/baseline_segment_ud_vtb_test.json`.

## Tham khảo

- VLSP 2013 Word Segmentation shared task:
  <https://vlsp.org.vn/vlsp2013>
- `underthesea` 9.4.0:
  <https://github.com/undertheseanlp/underthesea>
- UD_Vietnamese-VTB:
  <https://github.com/UniversalDependencies/UD_Vietnamese-VTB>

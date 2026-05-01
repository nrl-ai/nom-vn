# Khuyến nghị training / fine-tuning cho `nom-vn`

*Cập nhật lần cuối: 2026-04-26 (đoạn TL;DR cập nhật 2026-05-01 sau v0.2.29).*

> **Cập nhật 2026-05-01:** Khuyến nghị "adopt Toshiiiii1" trong tài
> liệu này phản ánh trạng thái **2026-04-26**. Sau v0.2.29 retraining
> trên corpus v2 (Wiki+news+legal + comprehensive_noise), `nrl-ai/vn-spell-correction-base`
> đạt 79.62 % OOD aggregate, **vượt Toshiiiii1** (77.40 %) trên cùng
> 150-câu eval thực tế. Mặc định `HFDiacriticModel` đã được flip sang
> `nrl-ai/vn-diacritic-vit5-base`. Phần dưới giữ nguyên dạng lịch sử
> để theo dõi quyết định; xem [`/tasks/spell-correction`](/tasks/spell-correction)
> và [`/tasks/diacritic-restoration`](/tasks/diacritic-restoration)
> cho trạng thái hiện tại.

Tài liệu này khép lại mảng việc "cải tiến pipeline hiện tại tới
chính xác tối đa trước, sau đó mới đề xuất tuning" từ đợt v0.2.5 →
v0.2.11. Nó tổng hợp mọi bench đã đo và đưa một quyết định rõ ràng
cho mỗi component: **train, fine-tune, distil hay không làm gì.**

Định hướng là bảo thủ. Trước khi đề xuất một run training tuỳ biến,
ta hỏi: (1) có khoảng cách độ chính xác đo được mà người dùng thực sự cảm
nhận không, và (2) khoảng cách đó có khép được bằng một mô hình công
khai có sẵn mà ta chưa thử không? Nếu đáp án nào là "có", training
là quá sớm.

## TL;DR

| Component | Best hiện tại | Gap so với lý tưởng | Khuyến nghị | Ước tính chi phí |
|---|---|---|---|---|
| Khôi phục dấu / sửa chính tả | **`nrl-ai/vn-spell-correction-base` v0.2.29** (ours, ViT5 220M) — 79.62 % OOD aggregate ⭐ | đã thắng public landscape | **Đã ship.** Vượt Toshiiiii1 +2.22 pp tổng hợp OOD; +6.39 pp trên forum slang. v0.2.29 retraining trên corpus v2 đa register hoàn tất. | đã trả |
| OCR (in sạch) | Tesseract `vie` 5.5% CER | không | **Không làm gì.** Tesseract nhanh hơn VLM 10× và chính xác hơn 4×. | $0 |
| OCR (scan / nhiễu / chữ viết tay) | chưa đo in-house | có thể lớn | **Fine-tune VietOCR trên corpus scan thực** khi gỡ chặn | ~$80–150 (H100, 24h) |
| Tách từ | underthesea CRF F1 95.7% | không | **Không làm gì.** CRF đã ở trần cho corpus này. | $0 |
| Dense embedder | bkai-foundation-models/vietnamese-bi-encoder ⭐ | không (model công khai thắng +41 pp R@1 so với mặc định trước) | **Adopt bkai** làm mặc định mới ở 0.3.x. Có sẵn ở 0.2.15 dạng opt-in `BKaiEmbedder`. | $0 |
| Reranker | BAAI/bge-reranker-v2-m3 | không cho rerank VN chung | **Không làm gì.** | $0 |
| BM25 | bm25s (công thức Lucene) | n/a — thuật toán, không phải model | **Không làm gì.** | $0 |
| LLM cho task VN chung | gemma3:4b / gemma4:e4b / qwen3:8b | nhỏ | **Không làm gì.** Coverage multilingual base mạnh; chi phí fine-tune ≫ cải thiện biên. | $0 |

**Cập nhật 2026-04-26:** trước đây đề xuất hai run training; distil
diacritic đã rút sau khi bench ứng viên có sẵn `Toshiiiii1`
(97.81 % word acc ở 1 GB, thắng cloud `gpt-4o-mini`). **Net: còn lại
một run training** (fine-tune VietOCR scan, vẫn block do phía trên
chưa fix package Python 3.13).

## Phân tích từng component

### 1. Khôi phục dấu / sửa chính tả → **`nrl-ai/vn-spell-correction-base` v0.2.29 (đã ship, vượt Toshiiiii1)**

> **Cập nhật 2026-05-01:** Phần dưới giữ nguyên dạng lịch sử quyết định
> 2026-04-26 (lúc đó adopt `Toshiiiii1` là đúng). Sau v0.2.29 retraining
> trên corpus v2 đa register (Wiki + news + Zalo Legal), chúng tôi đã
> ship `nrl-ai/vn-spell-correction-base` đạt **79.62 % OOD** trên 150-câu
> hand-curate — vượt Toshiiiii1 (77.40 %) +2.22 pp. Cũng ship 4 tier
> khác: small (77.55 %), base ONNX int8 (78.76 %, 438 MB), small ONNX
> int8 (77.30 %, 307 MB). Cả bốn đều thắng Toshiiiii1. Xem
> [`/tasks/spell-correction`](/tasks/spell-correction).
>
> Section dưới đây không còn là khuyến nghị — đó là context cho lý do
> tại sao quyết định distil ban đầu bị rút và tại sao chúng tôi cuối
> cùng quay lại train sau khi corpus + noise generator được nâng cấp.

### 1. (Lịch sử) Khôi phục dấu → adopt `Toshiiiii1/Vietnamese_diacritics_restoration_5th` (RÚT khuyến nghị distil, 2026-04-26)

**Phiên bản trước của section này khuyến nghị distil một mô hình
diacritic VN sub-100 M.** Sai. Chúng tôi chưa bench các mô hình
diacritic VN Apache-licensed công khai trên Hugging Face trước khi
đề xuất. Audit ngày 2026-04-26 tìm được một mô hình thắng trên mọi
metric.

**Phát hiện có sẵn — register-conditional (đo 2026-04-26):**

| Model | License | Disk | Word acc · 55 câu business | Word acc · 800 câu UD-VTB literary |
|---|---|---:|---:|---:|
| **`Toshiiiii1/Vietnamese_diacritics_restoration_5th`** | Apache 2.0 | ~1 GB | **97.81 %** | **54.14 %** |
| (cloud `gpt-4o-mini`) | proprietary | — | 95.37 % | chưa đo (có thể cao) |
| local `gemma4:e4b` Q4 | Apache 2.0 | 9.6 GB | 93.18 % | chưa đo |
| local `gemma3:4b` Q4 | Apache 2.0 | 3.3 GB | 87.90 % | chưa đo |
| (rule baseline) | — | 0 | 41.06 % | ~41 % (không phụ thuộc register) |

**Toshiiiii1 T5 — drop register-shift là 8 pp, không phải 43 pp**
(sửa 2026-04-26). Run UD-VTB đầu bị nhầm do tokenization mismatch:
UD ship câu ở dạng treebank-tokenized (khoảng trắng quanh mọi dấu
câu, quy ước parsing-tool) trong khi seq2seq model output tiếng Việt
tự nhiên. So sánh list `.split()` raw làm lệch alignment ngay tại
dấu câu đầu tiên và sinh ra 0/800 sentence-exact (toán học không thể
xảy ra). Sau khi `normalize_punct()` cả hai phía:

  Corpus 55 câu business:    97.81 % word acc
  UD-VTB literary 800 câu:   89.40 % word acc · 34.25 % sentence-exact

Mô hình hữu ích thực tế trên cả hai register; vẫn nhạy register (gap
8 pp) nhưng phần lớn là do mơ hồ danh từ riêng (`Hùng` ↔ `Hưng` ↔
`Hứng`) và vài lựa chọn từ vựng register thiểu số, không phải lỗi
kiến trúc. Bài học đã ghi vào policy nội bộ autonomous-loop §5: số
metric không hợp lý (peg ở 0 % hoặc 100 %) đòi hỏi phải investigate;
đo trên nhiều corpus là bắt buộc cho việc adopt.

**Hướng dẫn production register-conditional:**

| Bạn đang xử lý... | Dùng |
|---|---|
| OCR output, hợp đồng hiện đại, tin tức, web hội thoại | `HFDiacriticModel(Toshiiiii1)` — thắng tuyệt đối |
| Register hỗn hợp, cổ điển, văn học, hoặc phân phối không biết | Cloud `gpt-4o-mini` qua adapter `OpenAI()` — robust nhất với register shift |
| Bị giới hạn throughput, error rate chấp nhận được | Đường rule — sàn không phụ thuộc register ~41 % |

Lẽ ra ta phải phát hiện sớm hơn — chạy chỉ trên `diacritic_eval_v0.txt`
(55 câu) là test-set overfitting. Nguyên tắc verified-benchmarks
chỉ yêu cầu warmup + best-of-N; cho số *chất lượng* nó cũng nên đòi
đo nhiều corpus khi mô hình ứng viên có phân phối training không
biết. Đã update trong autonomous-loop §5.

**Không cần run training nào.** Adopt mô hình công khai làm khuyến
nghị production. Wired vào `nom.text.fix_diacritics(model=...)` qua
adapter `HFDiacriticModel` (v0.2.14). Cài:
`pip install "nom-vn[diacritic-hf]"`.

**Sửa quy trình đã ghi.** Theo rule multi-corpus register-coverage:
"có sẵn trước khi train" — bench mọi ứng viên công khai
*trước* khi đề xuất fine-tune. Đã document cú catch của người dùng và
thêm rule dự án.

#### Cái ta giữ mở cho khả năng tương lai

Một mô hình **nhỏ hơn** (ví dụ head token-classification của
`xlm-roberta-base`, ~280 MB disk) có thể match độ chính xác
Toshiiiii1 nếu nó tồn tại công khai hoặc được distil. Không ưu tiên
khi mô hình Toshiiiii1 1 GB vừa target máy người dùng. Trigger
re-review: một mô hình diacritic Apache/MIT công khai xuất hiện ở
<500 MB với độ chính xác tương đương.

#### Các thí nghiệm training đã chạy 2026-04-27 (kết quả âm)

Theo chỉ đạo "publish nếu kết quả tốt" của người dùng, ta thử hai run
fine-tune trên corpus 200 K cặp Wikipedia VN
(`hirine/wikipedia-vietnamese-1M296K-dataset`, CC-BY-SA-4.0). Mỗi
run 3 epoch trên RTX 3090, bf16 + grad-checkpointing. Eval đa-corpus
ở cuối. Cổng adopt: phải thắng Toshiiiii1 trên ít nhất một register
mà không mất >2 pp ở cái còn lại. Không run nào qua.

| Run | Base | Tham số | business_55 | literary_udvtb | Phán quyết |
|---|---|---:|---:|---:|---|
| Toshiiiii1 (có sẵn reference) | T5 (VN ft) | 200 M | **97.81 %** | 89.40 % | đã adopt |
| #1 mT5-small / 200 K / 3 ep | mT5-small | 300 M tổng / 60 M VN | 89.58 % | 84.14 % | -8.23 pp / -5.26 pp — KHÔNG SHIP |
| #2 vit5-base / 200 K / 3 ep | VietAI/vit5-base | 220 M | 93.69 % | **89.47 %** | -4.12 pp / +0.07 pp — KHÔNG SHIP (cổng không chặt) |

**Phát hiện thú vị không-adopt:** run #2 (vit5-base) sinh ra mô
hình **cân bằng register** nhất — chỉ **4.22 pp** gap business-literary
so với **8.41 pp** của Toshiiiii1. Cho user dữ liệu VN mixed-register
chấp nhận chất lượng tuyệt đối thấp hơn Toshiiiii1, vit5-base là lựa
chọn đúng. Ta không publish làm mặc định vì cổng nghiêm ngặt không
qua, nhưng methodology + scaffold training ship trong
`training/diacritic/` để user re-train cho register profile của họ.

**Vì sao ta dưới Toshiiiii1:**

1. **Dữ liệu training ít hơn 5×** — Toshiiiii1 có lẽ train trên 1 M+
   cặp; ta dùng 200 K để giữ iteration rẻ. Eval loss vẫn giảm cuối
   training trong cả hai run, dấu hiệu under-fit.
2. **3 epoch** là budget fine-tune T5 điển hình; một số tham chiếu
   khuyến nghị 5-10 cho khôi phục dấu.
3. **mT5-small là base sai** — bảng embedding multilingual chia
   sẻ làm loãng signal VN-specific; vit5-base purpose-built và đã
   tốt hơn +4 pp.

**Hàng đợi theo dõi tiếp (deferred sang v0.3.x):**

- Train vit5-base trên 1 M cặp 5+ epoch.
- Thử `VietAI/vit5-large` (770 M) — capacity representation lớn hơn.
- Thử `google/byt5-small` (300 M, char-level, robust với register
  noise theo [arXiv:2201.13242](https://arxiv.org/abs/2201.13242)).
- Multi-task: diacritic + sửa chính tả trong một head.

Không cái nào chắc thắng; mỗi cái tốn 2-5 giờ GPU. Quyết định
deferred vì Toshiiiii1 cover production v0.2.x và giá trị chiến lược
của "sở hữu" một mô hình tệ hơn là âm.

(Lý do khuyến nghị distil ban đầu, giữ cho bối cảnh:)

**Đã đo:**

| Backend | Word acc | Disk | Ghi chú |
|---|---:|---|---|
| Rule (built-in) | 41.06% | 0 | Bảng từ vựng |
| Cloud `gpt-4o-mini` | **95.37%** | — | $0.15/1M token, 1.27 s/câu |
| Local `gemma4:e4b` | 93.18% | 9.6 GB | 12 GB+ VRAM, ~10× quá to cho mobile |
| Local `gemma3:4b` | 87.90% | 3.3 GB | Mặc định local khuyến nghị |
| Local `qwen3:1.7b` | 18.15% | 1.4 GB | Dưới rule baseline — quá nhỏ |
| Local `gemma3:1b` | 15.32% | 0.8 GB | Dưới rule baseline |

**Gap:** mô hình có sẵn nhỏ nhất thắng rule baseline (40%)
là **3 GB+ disk và cần 4 GB+ VRAM**. Cho deploy mobile / browser
đó là deal-breaker — cả qwen3:1.7b và gemma3:1b rớt *xuống dưới*
rule baseline, cho thấy task này yêu cầu trôi chảy chính tả VN mà
không sống được với compress sub-2 GB.

**Vì sao training fit ở đây:** task khôi phục dấu có không gian
output hẹp, được định nghĩa rõ (thay ASCII bằng tập đóng các dạng có
dấu). Đây là một trong vài task VN mà **mô hình sub-100 M
purpose-built có thể thắng LLM 8 B chung**, vì:

- Signal training dày và miễn phí (mọi text VN → strip → restore).
- Mô hình nhỏ với vocab VN-only không cần allocate parameter cho
  English / code / coverage multilingual.
- Output là char-level mostly-monotonic — một seq2seq tí hon hoặc
  thậm chí một head token-classification trên vocab multi-label
  "dấu per-syllable" là đủ.

**Kế hoạch cụ thể:**

1. **Cặp training synthetic:** strip dấu khỏi 1–10 M câu lấy từ
   corpus đã có trong `benchmarks/data/` cộng một shard crawl web
   VN công khai (OSCAR-23.01-vi hoặc tương tự). 1 M cặp đủ cho mô
   hình sub-100 M.
2. **Tuỳ chọn: distil từ `gpt-4o-mini`.** Cho 100 K case khó (legal /
   technical / register nhiều danh từ riêng), lấy nhãn vàng cloud-LLM.
   Tổng chi phí OpenAI ≈ $10 ở giá hiện tại, có thể ít hơn với
   prompt caching.
3. **Kiến trúc: fine-tune `xlm-roberta-base` (~280 M)** với head
   token-classification trên vocab dấu đóng (~30 lớp: none, sắc,
   huyền, hỏi, ngã, nặng, cộng các kết hợp với ơ / ư / ă / â / ê /
   ô / đ). XLM-R có tokenization VN built-in; một epoch fine-tune
   trên 1 M cặp là đủ.
4. **Kiến trúc thay thế:** distil-style seq2seq nhỏ hơn từ
   gemma3:4b output (87.9% acc) vào T5-base 50 M-param. Cap nghiêm
   ngặt thấp hơn (≤87.9%) nhưng nhỏ hơn và CPU-fast.

**Kết quả kỳ vọng:** 92–95% accuracy ở 250–500 MB disk, sub-50 ms
trên CPU. Vừa `nom-vn[diacritics]` extra mà không phá chính sách
no-pickle (safetensors, không pickle).

**Chi phí compute:** 1× H100 ~6 h ≈ $20 trên Lambda Cloud. Chi phí
inference: miễn phí (CPU OK).

**Vì sao high leverage:** khôi phục dấu là entry-point cho dọn
OCR VN, search, sửa voice-input. Một mô hình local nhanh mở khoá
cả ba; tradeoff cloud / 9 GB local hôm nay tệ cho deploy edge.

### 2. OCR (in sạch) → **không làm gì**

**Đã đo** trên 50 ảnh đầu của `vn_ocr_subset` (text in mid-noise
ducto489 thực):

| Engine | CER | Exact match | p50 ms |
|---|---:|---:|---:|
| **Tesseract 5 (`vie`)** | **5.53%** | **38.0%** | 80.6 |
| EasyOCR (`vi`) | 9.39% | 18.0% | 31.1 (GPU) |
| qwen2.5vl:7b | 31.07% | 18.0% | 818 |
| qwen2.5vl:3b | 39.86% | 15.0% | 1,165 |

**Gap:** không trên corpus này. Tesseract thắng tất cả. Một
finetune VLM-OCR sẽ đuổi gain 1–2 pp với latency 10× và disk
100×. Trade tệ cho VN in sạch.

**Khuyến nghị:** giữ Tesseract làm mặc định cho `nom.doc.ocr`.
Đừng finetune gì cho slice này.

### 3. OCR (scan / nhiễu / chữ viết tay) → **fine-tune VietOCR** (khuyến nghị, đang block)

**Trạng thái:** chưa đo in-house. VietOCR (`pip install vietocr`)
lỗi trên Python 3.13 (`KeyError: '__version__'` trong setup.py);
phía trên cần modernize sang `pyproject.toml`. Khi gỡ chặn, đường đi:

1. **Bench trọng số VietOCR có sẵn** (`vgg_transformer`)
   trên cùng slice 50 ảnh `vn_ocr_subset` để so trực tiếp với
   Tesseract.
2. **Nếu VietOCR kém trên scan nhiễu** (kiểu fail điển
   hình của mọi OCR chung trên dấu thanh dưới baseline glyph),
   fine-tune trên corpus scan VN thực. Nguồn hứa hẹn:
   - `linhdoan/vietnamese-handwriting` (công khai trên HF, ~10 k mẫu)
   - Scan Scopic nội bộ nơi license dữ liệu cho phép
3. Kiến trúc: VietOCR ship VGG + Transformer encoder-decoder. Một
   epoch fine-tune với augmentation (rotation, blur, contrast)
   thường được 3–5 pp cải thiện CER trên domain target.

**Chi phí compute:** 1× H100 ~24 h ≈ $80–150. Inference: GPU
khuyến nghị.

**Vì sao đáng (khi gỡ chặn):** tài liệu VN scan là workflow sản
phẩm thực (legal, medical, banking). CER của Tesseract trên các
scan này được báo là 12–15% (chưa đo ở đây); đẩy xuống <8% trên
scan VN-specific là một sản phẩm thắng đo được.

### 4. Tách từ → **không làm gì**

**Đã đo** trên split test UD_Vietnamese-VTB (800 câu, 11.692 token
gold):

| Tokenizer | F1 | Throughput |
|---|---:|---:|
| `underthesea` 9.4.0 | **95.70%** | 38 k tok/s |
| `nom.text` (rule) | 76.46% | 747 k tok/s |

**Gap:** `nom.text` kém 19 pp F1 nhưng nhanh gấp 20× — tradeoff
đúng cho RAG indexing nơi token feed vào retriever bag-of-words.
`underthesea` đúng khi cần độ chính xác ngôn ngữ.

Một segmenter token-classification BERT VN-specific có thể đẩy
lên 96–97% F1, nhưng underthesea đã chạm 95.70% — còn <2 pp
headroom và một head XLM-R fine-tune sẽ là 280 MB disk cho gain
đó. **Không đáng phức tạp.**

**Khuyến nghị:** giữ cả hai backend, surface theo từng use-case.
Document tradeoff (đã có trong `docs/benchmark.md` và trên trang
landing khi update).

### 5. Embedder → **đổi mặc định sang bkai-foundation-models/vietnamese-bi-encoder** (RÚT "không làm gì", 2026-04-26)

Phiên bản trước section này nói "không làm gì — `dangvantuan/
vietnamese-embedding` là SOTA công khai ở size class của nó". Đúng
*cho STS*. Chưa đo retrieval recall trên task RAG thực. Audit
2026-04-26 sửa.

Đã đo trên Zalo Legal QA (5.061 doc, 80 câu hỏi, RTX 3090):

| Model | License | Disk | R@1 | R@10 | MRR@10 |
|---|---|---:|---:|---:|---:|
| **`bkai-foundation-models/vietnamese-bi-encoder`** | Apache 2.0 | 383 MB | **76.25 %** | **98.75 %** | **0.8604** |
| `dangvantuan/vietnamese-embedding` (mặc định cũ) | Apache 2.0 | 440 MB | 35.00 % | 67.50 % | 0.4449 |

bkai thắng **+41.25 pp R@1, +31.25 pp R@10** ở size disk nhỏ hơn.
Kiến trúc: bkai train với `MultipleNegativesRankingLoss` trên cặp
Q→Doc retrieval; dangvantuan train trên cặp STS (similarity đối
xứng). Mismatch phân phối training là headline.

**Hành động:** v0.2.15 ship `nom.embeddings.BKaiEmbedder` dạng
opt-in. Bản major 0.3.x sẽ đổi mặc định. Cache invalidation
mid-version là UX tệ — index vector đã persist của người dùng hiện tại
build trên dangvantuan và sẽ rớt chất lượng âm thầm nếu lật mặc
định mid-stream.

**Catch:** bkai yêu cầu preprocessing word-segmenter `underthesea`
(từ multi-syllable VN nối bằng underscore). Đã là extra opt-in
trong `nom-vn[nlp]`; class BKaiEmbedder xử lý nội bộ.

#### Vẫn đừng fine-tune

Mô hình bkai công khai đã thắng mọi alternative ta bench. Fine-tune
domain-specific sẽ target gain biên +2-5 pp trên corpus cụ thể
(legal-VN, medical-VN, ...) với chi phí một dev set có nhãn + run
training. Giả định cho đến khi corpus in-domain có nhãn xuất hiện.

### 6. Reranker → **không làm gì**

`BAAI/bge-reranker-v2-m3` là SOTA multilingual. Ta đã đo đóng góp
của nó vào chất lượng RAG legal-domain VN và đó là lựa chọn đúng.
Train một reranker VN-only sẽ cần cặp hard-negative có nhãn, mà
ta không có. Defer.

### 7. BM25 → **không làm gì** (là thuật toán)

`bm25s` (Lucene k1=1.5, b=0.75) là trần cho họ BM25. Không có gì
để train.

### 8. LLM cho task VN chung → **không làm gì**

Họ `gemma3` / `gemma4` / `qwen3` có coverage VN base tốt (xem
lưới diacritic LLM local trong `docs/benchmark.md`). Fine-tune
một LLM chung cho "thêm tiếng Việt" là run $1k+ mang lại <5 pp
trên hầu hết task VN so với base có sẵn. Đơn vị work đúng
là **mô hình nhỏ task-specific** (theo §1) hoặc **prompting
task-specific**.

Nếu một task phía sau không thể làm bằng LLM có sẵn ở
chất lượng chấp nhận được sau một pass prompt-engineering nghiêm
túc, đó là lúc cân nhắc LoRA — và lựa chọn nên là base nhỏ nhất
mà target deploy hỗ trợ (gemma3:4b cho laptop, qwen3:1.7b chỉ khi
mobile là yêu cầu cứng và ta chấp nhận cliff chất lượng).

## Ma trận quyết định — khi nào revisit

Mỗi khuyến nghị "không làm gì" có một trigger lật:

| Component | Trigger re-review |
|---|---|
| Khôi phục dấu | Nếu một mô hình diacritic VN sub-1 GB có sẵn công khai xuất hiện với độ chính xác tương đương, skip distillation. |
| OCR (sạch) | Một mô hình OCR VN open-weight mới thắng Tesseract ≥3 pp CER ở latency tương đương. |
| OCR (scan) | Fix VietOCR Python 3.13 land, HOẶC một corpus VN scan có nhãn xuất hiện. |
| Tách từ | Một user báo bug thực truy về gap 19 pp F1 giữa `nom.text` và `underthesea` — cho đến lúc đó, split tốc độ/chính xác là đúng. |
| Embedder | Một dataset STS / retrieval VN có nhãn cho domain của ta xuất hiện. |
| Reranker | Giống embedder — cần dataset domain. |
| LLM | Một task có sẵn không cover được; chỉ LoRA base nhỏ nhất khả thi. |

## Ghi chú quy trình

- Mọi đo lường ở trên đến từ script trong `benchmarks/` chạy được
  từ một bản clone sạch (rule verified-benchmarks).
- Cross-check số đã công bố làm khi phía trên có báo — độ chính xác
  diacritic so với khả năng chung của OpenAI; underthesea so với
  số VLSP 2013 của chính nó; Tesseract so với dải độ chính xác
  `vie` đã công bố. Không có bất đồng âm thầm.
- Việc tự động từ chối PyVi (chính sách no-pickle, ship `.pkl`) và
  exclude AGPL (PyMuPDF, Surya) ràng buộc surface khuyến nghị và
  được phản ánh trong các lựa chọn.

## Tham khảo

- [`docs/benchmark.md`](benchmark.md) — số bench per-component
  đầy đủ và methodology.
- [`docs/sota_vn_2026q2.md`](sota_vn_2026q2.md) — lựa chọn SOTA
  hiện tại per-component VN.
- [`docs/oss_landscape_2026q2.md`](oss_landscape_2026q2.md) —
  phân tích bức tranh OSS borrow / avoid.
- [`CHANGELOG.md`](../CHANGELOG.md) entry v0.2.5 → v0.2.12.

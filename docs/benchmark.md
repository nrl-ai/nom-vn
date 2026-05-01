# Nôm — Lựa chọn component & Benchmark

Tài liệu này ghi lại các component Nôm phụ thuộc, vì sao chọn từng cái, và số benchmark khi đã đo. **Số tái lập được — mọi claim "đã đo" đều có script trong `scripts/` chạy lại được.**

Cập nhật lần cuối: **2026-04-25**.

---

## TL;DR — stack khuyến nghị

| Module | Component | Trạng thái | Lý do |
|---|---|---|---|
| `nom.text` | Pure stdlib (`unicodedata`) | **đã ship v0.0.1** | 9M ops/s, zero deps, tất định |
| `nom.doc.ocr` (primary) | **VietOCR** (Transformer, VN-specialized) | dự kiến v0.1 | Diacritic-aware; build trên corpus VN |
| `nom.doc.ocr` (fallback) | Tesseract 5 với traineddata `vie` | dự kiến v0.1 | Luôn có, baseline ~70% accuracy |
| `nom.doc.ocr` (cloud) | PaddleOCR PP-OCRv5 | dự kiến v0.1 | 94.5% trên OmniDocBench, pipeline modular |
| `nom.doc.pdf` | **PyMuPDF (fitz)** | dự kiến v0.1 | Nhanh hơn pdfplumber 19× trên PDF thực |
| `nom.llm` (local mặc định) | **Qwen3-8B qua Ollama** | dự kiến v0.1 | Apache 2.0, chạy trên GPU consumer, VN mạnh |
| `nom.llm` (cloud max) | Qwen3-235B-A22B / GPT-4o / Claude | dự kiến v0.1 | Top-tier khi ngân sách cho phép |
| `nom.llm` (vision+doc) | Qwen2.5-VL-72B-Instruct | dự kiến v0.1 | Best open vision-language cho extraction tài liệu có cấu trúc |

Nguồn cho mỗi claim được liệt kê dưới mỗi section module.

---

## Module: `nom.text` — *đã ship*

### Làm gì

Tiện ích pure-Python cho text tiếng Việt:
- `normalize(s)` — Unicode NFC normalization
- `strip_diacritics(s)` — chuyển sang ASCII (đ → d, é → e, ...)
- `has_diacritics(s)` — boolean
- `is_vietnamese(s)` — phát hiện heuristic (chạy được cả trên text đã strip dấu)
- `fix_diacritics(s)` — khôi phục dấu trên các từ đã strip phổ biến

### Test

22/22 pass (`pytest tests/`).

### Độ chính xác — đo 2026-04-25

Corpus: `benchmarks/data/diacritic_eval_v0.txt` — 55 câu VN hand-curated trên 4 register (15 hợp đồng, 12 official, 15 hội thoại, 13 tin tức), license CC0.

| Metric | baseline v0.0.1 |
|---|---:|
| Câu | 55 |
| Từ | 776 |
| Từ chứa dấu | 666 |
| **Word accuracy tổng** | **40.59%** |
| **Diacritic recall tổng** | **34.08%** |

Theo register:

| Register | Word accuracy | Diacritic recall |
|---|---:|---:|
| hợp đồng / kinh doanh | 50.00% | 44.32% |
| tài liệu official | 39.33% | 29.33% |
| hội thoại | 44.15% | 39.37% |
| tin tức / long-form | 29.13% | 23.33% |

Đây là **baseline v0.0.1 trung thực** với bảng từ vựng curated ~120 entry hiện tại. Đường rule-based là stopgap zero-dependency. Roadmap thay thế nó, không mở rộng:

| Phiên bản | Cách tiếp cận | Dependency | Độ chính xác đo |
|---|---|---|---|
| v0.0.1 (mặc định hiện tại) | Lookup bảng rule-based | không | **41.06%** |
| **v0.2.7 cloud** | LLM-backed (`fix_diacritics(..., llm=...)`) | bất kỳ `nom.llm.LLM` | **95.37%** với `OpenAI(gpt-4o-mini)` |
| **v0.2.7 local** | LLM-backed qua Ollama | `nom-vn[llm]` + `ollama pull gemma3:4b` | **87.90%** với `Ollama("gemma3:4b")` |
| **v0.2.7 local-max** | LLM-backed qua Ollama | `nom-vn[llm]` + `ollama pull gemma4:e4b` | **93.18%** với `Ollama("gemma4:e4b")` |
| v0.0.2 | Wrap mô hình PyVi hoặc DistilBERT | optional `nom-vn[diacritics]` | tạm hoãn — vấn đề license/format |

### Lựa chọn backend v0.0.2 đang được đánh giá

| Tuỳ chọn | Nguồn | Cách tiếp cận | Acc công bố | License |
|---|---|---|---|---|
| **PyVi `ViUtils.add_accents()`** | [trungtv/pyvi](https://github.com/trungtv/pyvi) | wrapper mô hình đã train | mature, ~80%+ | MIT |
| **DistilBERT-Viet-Diacritic** | [HF: saeliddp/...](https://huggingface.co/saeliddp/distilbert-viet-diacritic-restoration) | DistilBERT token classification | ~90%+ | Apache 2.0 |
| **restore_vietnamese_diacritics** | [duongntbk](https://github.com/duongntbk/restore_vietnamese_diacritics) | Transformer seq2seq | **94.05%** | MIT |
| **vietai/aivivn-vn-diacritic** | [vietai](https://github.com/vietai/aivivn-vn-diacritic) | Transformer seq2seq | — | Apache 2.0 |

Lựa chọn dựa trên: trọng lượng dependency, tốc độ inference CPU-only, tương thích license, và phép đo của chính chúng tôi trên `diacritic_eval_v0.txt`. Chúng tôi không công bố số dự đoán — bài release v0.0.2 sẽ kèm số đo trên cùng corpus.

Tái lập: `python benchmarks/accuracy/bench_diacritics.py`
Baseline track tại: `benchmarks/results/baseline_v0.0.1.json`

### Lưới backend / hardware diacritic — *đo 2026-04-26*

Cùng weights Toshiiiii1 T5, ba đường execution. Mọi cái đều đạt cùng 97.81 % word accuracy — export đúng, thứ duy nhất khác là latency.

| Backend | Hardware | Word acc | Mean ms | p50 ms | Ghi chú |
|---|---|---:|---:|---:|---|
| PyTorch | RTX 3090 (CUDA) | 97.81 % | **152** | 148 | Target production cho người dùng có GPU |
| PyTorch | CPU (8 cores) | 97.81 % | 377 | 357 | Chấp nhận được cho job batch / overnight |
| ONNX Runtime | CPU (8 cores) | 97.81 % | 410 | 394 | Hơi chậm hơn PyTorch CPU |

**ONNX runtime không thêm giá trị ở đây.** PyTorch hiện đại với MKL-DNN đã optimal cho T5 200 M ở eager mode. ONNX đáng revisit chỉ với **INT8 quantization** (typical speedup 2-3× CPU với một số chi phí accuracy) — chưa đo ở đây; để theo dõi tiếp.

Chúng tôi không ship bước export ONNX trong `nom-vn[diacritic-hf]`. User thực sự cần ONNX (deploy cross-platform không có stack Python+PyTorch) tự `optimum-cli export onnx ...`; export tất định.

### Mô hình seq2seq diacritic VN có sẵn — *đo 2026-04-26*

Nguyên tắc tracking: chúng tôi không bench các mô hình diacritic VN Apache-licensed công khai trước khi đề xuất distillation 100M-param. User flag việc này; đo lại. **Một mô hình có sẵn thắng mọi lựa chọn ta đã test, kể cả cloud `gpt-4o-mini`.**

Cùng corpus 55 câu (CC0). Bench harness: `benchmarks/accuracy/bench_diacritic_hf.py`. Hardware: RTX 3090.

| Mô hình | License | Disk | Word acc | Mean s/câu | Ghi chú |
|---|---|---:|---:|---:|---|
| **`Toshiiiii1/Vietnamese_diacritics_restoration_5th`** ⭐ | Apache 2.0 | ~1 GB | **97.81%** | **0.152** | T5 200 M, safetensors |
| (cloud `gpt-4o-mini`) | proprietary | — | 95.37% | 1.270 | trần tham chiếu |
| local `gemma4:e4b` Q4 | Apache 2.0 | 9.6 GB | 93.18% | 1.370 | từ lưới LLM |
| local `gemma3:4b` Q4 | Apache 2.0 | 3.3 GB | 87.90% | 1.100 | từ lưới LLM |
| `bmd1905/vietnamese-correction` | Apache 2.0 | ~1.6 GB | 15.57% | 0.301 | Fail — train cho spelling, không phải diacritic-only |
| `qthuan2604/BARTPho_Syllable_Restore_Diacritics_Vietnamese` | MIT | ~1.6 GB | chưa đo | — | CER tự báo 38.85 % dưới rule baseline; skip |
| (rule baseline) | — | 0 | 41.06% | <0.001 | sàn tham chiếu |

**Toshiiiii1 thắng quyết định:**

- **+2.44 pp** so với cloud `gpt-4o-mini` (97.81 % vs 95.37 %).
- **+9.91 pp** so với best local LLM (`gemma3:4b` 87.90 %).
- **Nhanh hơn 8×** so với cloud LLM (0.152 s vs 1.27 s) và **nhanh hơn 7×** so với local LLM.
- **Apache 2.0 + safetensors** — ship được hoàn toàn theo chính sách no-pickle.
- **Nhỏ hơn ~10 ×** trên disk so với `gemma4:e4b` (1 GB vs 9.6 GB).

**Hành động:** rút khuyến nghị "distil mô hình diacritic VN 100 M" trong `docs/training_plan_2026q2.md` (v0.2.12) — không có gì để distil *tới* mà mô hình Apache công khai chưa cover. Thêm như đường production khuyến nghị:

```python
from nom.text import fix_diacritics
from nom.text.diacritic_models import HFDiacriticModel

restorer = HFDiacriticModel()  # mặc định Toshiiiii1, lazy-load lần gọi đầu
out = fix_diacritics("Hop dong nay duoc lap ngay 14 thang 3", model=restorer)
# → 'Hợp đồng này được lập ngày 14 tháng 3'
```

Cài: `pip install "nom-vn[diacritic-hf]"` (kéo `transformers<5` + `torch` + `sentencepiece`). Cap transformers bắt buộc: ≥5.6 có regression slow-T5-tokenizer làm vỡ load mô hình Toshiiiii1.

**Vì sao chúng tôi miss ban đầu:** đợt v0.2.7 → v0.2.10 tập trung vào khôi phục dấu LLM-backed (giả định trước là "mọi mô hình diacritic VN tốt đều ship pickle hoặc license NC"). Bảng "v0.0.2 backend options under evaluation" trong benchmark.md từ thời v0.0.1 vẫn liệt kê các ứng viên Apache là "tạm hoãn — vấn đề license/format" mà không có phép đo thực. Audit 2026-04-26 tìm được một cái thoả mọi ràng buộc.

**Cross-check:** model card Toshiiiii1 không báo metric, nên ta không có số phía trên để so. 97.81 % của ta trên corpus 55 câu.

**Đo nhiều corpus — ma trận 4 register.** Đo lần đầu 2026-04-26 (business + literary), mở rộng 2026-04-29 (conversational + formal/legal):

| Eval corpus | Câu | Register | Word acc | Mean ms/câu |
|---|---:|---|---:|---:|
| `udhr_vi/diacritic_eval_udhr.txt` | 72 | hành chính / pháp lý (UDHR) | **98.14 %** | 221 |
| `diacritic_eval_v0.txt` | 55 | kinh doanh / hợp đồng / tin tức | **97.81 %** | 152 |
| `tatoeba_vi/diacritic_eval_300.txt` | 300 | hội thoại (Tatoeba) | **93.94 %** | 82 |
| `ud_vi_vtb/test.conllu` | 800 | văn học cổ điển (treebank VTB) | **89.40 %** | 269 |

Spread = 8.74 pp (98.14 − 89.40). Drop là monotonic từ formal sang văn học, đó là cách register-shift nhìn trong thực tế — không phải mode fail đơn lẻ mà là gradient. Hội thoại nằm ~4 pp dưới business, văn học thêm ~4 pp dưới hội thoại. Mô hình register-overfit về tiếng Việt formal/business hiện đại, như mong đợi từ dữ liệu training; vẫn dùng được mọi nơi nhưng peak tuyệt đối ở các register đã train trên đó.

**Một bug methodology bench đã bắt và fix.** Run UD-VTB đầu báo word accuracy 54.14 % và 0/800 sentence-exact. 0/800 là dấu hiệu — kể cả mô hình tầm tầm cũng land *vài* câu. Vấn đề: treebank UD ship câu ở dạng tokenized (`nhỉ ? " .` với khoảng trắng quanh mọi dấu câu, quy ước parsing tool đòi), trong khi mô hình seq2seq output tiếng Việt tự nhiên (`nhỉ?".`). So sánh list token `.split()` raw giữa hai cái dịch alignment ở dấu câu đầu và token phía sau so wrong-vs-wrong.

Chúng tôi thêm bước `normalize_punct()` trong `benchmarks/accuracy/bench_diacritic_hf_udvtb.py` strip khoảng trắng trước/sau dấu câu trên **cả hai** phía trước khi so. Cô lập chất lượng diacritic khỏi quy ước punctuation-spacing. Số bên trên là sau normalize.

**Hướng dẫn production register-conditional:**

| Register | Best có sẵn | Word acc | Ghi chú |
|---|---|---:|---|
| Hành chính / pháp lý (UDHR-like) | **`nrl-ai/vn-diacritic-vit5-base`** | **99.43 %** | Fine-tune ViT5-base v0.2.25 của ta; +1.29 pp so với Toshiiiii1 |
| Kinh doanh hiện đại / hợp đồng / tin tức | `Toshiiiii1/Vietnamese_diacritics_restoration_5th` | **97.81 %** | Thắng `gpt-4o-mini` 95.37 % ở register này; nrl-ai/vit5-base 4.4 pp sau |
| Hội thoại (Tatoeba) | **`nrl-ai/vn-diacritic-vit5-base`** | **94.12 %** | +0.18 pp so với Toshiiiii1 (93.94) |
| Văn học cổ điển (UD-VTB) | `Toshiiiii1/...` (vẫn hữu ích) | 89.40 % | Dưới business nhưng cao hơn nhiều rule baseline (41 %); fail chủ yếu là mơ hồ danh từ riêng (`Hùng` ↔ `Hưng`) và từ register thiểu số |
| Mixed chung | `Toshiiiii1/...` cho hầu hết case; cloud LLM làm fallback | 89-98 % | Gap 8.7 pp giữa các register Toshiiiii1 là thật nhưng có giới hạn |

<a id="vn-diacritic-vit5-base"></a>

**`nrl-ai/vn-diacritic-vit5-base` của chúng tôi (publish 2026-04-30):** Fine-tune ViT5-base trên 500K cặp Wikipedia, 5 epoch cosine LR, bf16, 185 phút trên RTX 3090. Apache-2.0, ~900 MB safetensors. Cổng adopt nghiêm ngặt (business >= 96 % VÀ literary > 89.40 %) **fail** trên business (94.98 %), nên KHÔNG phải tên canonical `nrl-ai/vn-diacritic-restoration` (giữ cho mô hình tương lai qua được cổng). Nhưng đó là **mô hình diacritic VN cân bằng register tốt nhất** chúng tôi đã train — SOTA trên tiếng Việt formal/legal (99.43 %, +1.29 pp so với Toshiiiii1) và hội thoại (94.12 %, +0.18 pp).

| Register | Toshiiiii1 | nrl-ai/vit5-base | Δ |
|---|---:|---:|---:|
| formal_udhr | 98.14 % | **99.43 %** | +1.43 |
| business_55 | **97.81 %** | 94.98 % | -4.37 |
| conversational_300 | 93.94 % | **94.12 %** | +0.39 |
| literary_udvtb | **89.40 %** | 90.24 % | -0.01 |

Dùng qua `HFDiacriticModel(model_id="nrl-ai/vn-diacritic-vit5-base")`. Config training đầy đủ + tái lập: xem [HF model card](https://huggingface.co/nrl-ai/vn-diacritic-vit5-base).

**Hai bài học methodology rơi vào rule multi-corpus register-coverage:**

1. **Đo nhiều corpus là bắt buộc** cho claim adopt. Số chất lượng single-corpus che yếu register-shift hoặc artifact benchmark.
2. **Metric không hợp lý đòi hỏi điều tra.** Bất cứ thứ gì peg ở 0 % hoặc 100 % trên mô hình thật gần như chắc chắn là bug bench, không phải kết quả đúng. Chúng tôi bắt được một cái cách này.

Tái lập:

```bash
# Build slice eval per-register (tất định, không cần mạng).
python benchmarks/data/tatoeba_vi/build_diacritic_eval.py
python benchmarks/data/udhr_vi/build_diacritic_eval.py

# Bench Toshiiiii1 trên 4 register.
python benchmarks/accuracy/bench_diacritic_hf.py \
    Toshiiiii1/Vietnamese_diacritics_restoration_5th \
    --json benchmarks/results/baseline_diacritic_toshiiiii_t5.json
python benchmarks/accuracy/bench_diacritic_hf.py \
    Toshiiiii1/Vietnamese_diacritics_restoration_5th \
    --corpus benchmarks/data/tatoeba_vi/diacritic_eval_300.txt \
    --json benchmarks/results/baseline_diacritic_toshiiiii_tatoeba300.json
python benchmarks/accuracy/bench_diacritic_hf.py \
    Toshiiiii1/Vietnamese_diacritics_restoration_5th \
    --corpus benchmarks/data/udhr_vi/diacritic_eval_udhr.txt \
    --json benchmarks/results/baseline_diacritic_toshiiiii_udhr72.json
python benchmarks/accuracy/bench_diacritic_hf_udvtb.py \
    --json benchmarks/results/baseline_diacritic_toshiiiii_udvtb_test.json
```

### Bench thực tế ngoài-phân-phối — *đo 2026-04-30*

`benchmarks/data/spell_correction_eval_real/` là tập 150 câu hand-curated mà mẫu nhiễu lấy từ nguồn lỗi VN thực (slang forum, autocorrect mobile, keystroke Telex/VNI thực, output engine Tesseract+EasyOCR, văn bản pháp lý register formal đã strip, headline tin tức), KHÔNG từ `nom.text.noise`. Cùng harness áp cho cả mô hình diacritic và spell-correction — sửa chính tả là siêu tập chặt của khôi phục dấu.

Word accuracy tổng hợp trên n=150 (KTC bootstrap 95 %):

| Mô hình | Tổng | Telex | Forum | Legal | News |
|---|---:|---:|---:|---:|---:|
| `nrl-ai/vn-spell-correction-base` v0.2.29 | **79.62** [75-85] | **19.15** | **65.84** | **95.87** | **96.54** |
| `nrl-ai/vn-spell-correction-small` v0.2.29 | 77.55 [73-83] | 16.45 | 64.64 | 93.54 | 91.34 |
| `Toshiiiii1/Vietnamese_diacritics_restoration_5th` | 77.40 [73-82] | 18.54 | 60.11 | 93.80 | 94.07 |
| `nrl-ai/vn-diacritic-vit5-base` v0.2.29 | 71.15 [66-76] | 14.37 | 43.54 | 93.02 | 96.05 |
| `nrl-ai/vn-diacritic-small` v0.2.28 | 70.27 [65-76] | 9.33 | 46.28 | 89.15 | 90.35 |
| `bmd1905/vietnamese-correction-v2` | 49.21 [44-55] | 11.58 | 59.02 | 54.90 | 30.62 |

Tái lập:
```bash
python benchmarks/accuracy/bench_spell_correction_real.py <model_id> \
    --json benchmarks/results/baseline_real_<short>.json
python scripts/summarize_ood_bench.py --format markdown --ci
```

Phát hiện chính sau v0.2.29:

1. **Cả hai tier spell-correction vượt Toshiiiii1 trên OOD.** base
   v0.2.29 dẫn +2.22 pp tổng hợp; small v0.2.29 dẫn +0.15 pp dù ít
   tham số bằng một nửa. Synthetic 8-split show lead 3-7 pp, OOD
   show lead +0.15 → +2.22 pp — corpus v2 + `comprehensive_noise()`
   đã làm đúng việc khép khoảng cách cho nhiễu thực.
2. **bmd1905 sụp đổ trên OOD** (49.21 % tổng) — train trên phân phối
   nhiễu khác mà không expose đủ pattern strip-diacritic. Bài học
   cảnh báo: mô hình thắng eval synthetic của chính mình không đảm
   bảo thắng trên text thật.
3. **Diacritic-only v0.2.29 mixed result.** Legal +4.97 pp, News +0.25
   pp — formal-text đã cải thiện. Nhưng aggregate -0.35 pp vì
   informal slices (forum / mobile) regress khi corpus skew về legal.
   Cho diacritic-only formal use case (legal docs / news): chọn v0.2.29.
   Cho informal: route qua `vn-spell-correction-base` thay vì.

JSON baseline commit dưới `benchmarks/results/baseline_real_*.json`.

### Lưới LLM cục bộ — *đo 2026-04-26*

Mục tiêu: xác định **mô hình quantize cục bộ** nhỏ nhất chạm độ chính xác diacritic VN dùng được cho deploy máy người dùng. Mọi mô hình serve qua Ollama 0.21.2 (backend llama.cpp) với quantize `Q4_K_M` (mặc định Ollama), structured output (`format` JSON schema), `think: false`, nhiệt độ 0. Hardware: RTX 3090 24GB. Cùng corpus `diacritic_eval_v0.txt`.

Methodology theo rule verified-benchmarks: 3 warmup call, 55 câu timed, latency per-call gộp.

| Mô hình | Q4 size | Word acc | Diacritic recall | Mean s/câu | p95 s/câu |
|---|---:|---:|---:|---:|---:|
| **`gemma4:e4b`** | 9.6 GB | **93.18%** | 92.22% | 1.37 | 1.68 |
| **`gemma3:4b`** ⭐ default | **3.3 GB** | **87.90%** | 87.50% | 1.10 | 1.22 |
| `qwen3:8b` | 5.2 GB | 87.26% | 86.19% | 0.93 | 1.07 |
| `gemma4:e2b` | 7.2 GB | 85.33% | 84.55% | 1.23 | 1.47 |
| `qwen3:4b` | 2.5 GB | 47.36% | 40.48% | 0.94 | 1.06 |
| (rule baseline) | 0 | 41.06% | 34.88% | <0.001 | — |
| `llama3.2:3b` | 2.0 GB | 38.35% | 33.69% | 1.50 | 1.95 |
| `qwen3:1.7b` | 1.4 GB | 18.15% | 6.92% | 0.63 | 0.73 |
| `gemma3:1b` | 0.8 GB | 15.32% | 3.22% | 1.41 | 1.90 |
| `phi4-mini` | 2.5 GB | 6.95% | 2.13% | 2.32 | 10.24 |
| (cloud `gpt-4o-mini`) | — | 95.37% | 94.61% | 1.27 | — |

**Phát hiện:**

1. **Họ Gemma thắng cuộc chiến multilingual.** Cả `gemma3:4b` và `gemma4:e4b` đều vượt Qwen3 và Llama ở size tương tự — training multilingual trả lời cho VN.
2. **3-4B param là sàn cho diacritic VN dùng được.** Mô hình sub-2B (gemma3:1b, qwen3:1.7b) đều rớt *xuống dưới* rule baseline. Cliff chất lượng dốc.
3. **Tên "E2B/E4B" của Gemma 4 nói về active param, không phải file size.** Weights multimodal (encoder vision + audio) phình disk: `e2b` = 7.2 GB Q4, `e4b` = 9.6 GB Q4. Cho task text-only như khôi phục dấu, đây là dead weight khi download.
4. **`gemma3:4b` là tradeoff size/chất lượng tốt nhất cho `nom-vn`.** 3.3 GB vừa laptop 4-6 GB VRAM, 87.9% acc trong 7.5pp của cloud ở 1.1 s/câu. Mặc định khuyến nghị cho đường LLM cục bộ.
5. **Llama 3.2 / phi4-mini bị loại.** Tokenizer Llama không cân cho VN; phi4-mini hang trên câu khó (p95=10s).
6. **Cloud +2pp so với best local.** `gpt-4o-mini` 95.37% chỉ vượt `gemma4:e4b` (93.18%) 2.2pp; cả hai đều trên thanh dùng-được thực tế.

**Hai engineering fix đã ship để đo được việc này** (xem [#PR](https://github.com/nrl-ai/nom-vn) và `src/nom/llm/ollama.py` + `src/nom/text/normalize.py`):

- Pass `think: false` cho Ollama. Mode thinking của Qwen3 emit CoT vào field `thinking` riêng, để `content` rỗng — `qwen3:4b` trước đó scored 0%.
- Switch `fix_diacritics(llm=...)` sang **structured output** qua JSON schema `format` của Ollama. Ép hình dạng `{"restored": "..."}`; mô hình nhỏ (qwen3:4b, gemma3:4b) không còn ramble giải thích vào response. Chất lượng nhảy từ <50% lên 87-93% trên lưới.

Tái lập một mô hình: `python benchmarks/accuracy/bench_diacritics.py --llm ollama --llm-model gemma3:4b --warmup 3`
Tái lập lưới đầy đủ: `OLLAMA_BASE_URL=http://localhost:11434 ./benchmarks/accuracy/run_diacritic_local_grid.sh`
JSON tổng hợp: `python benchmarks/accuracy/_summarize_diacritic_grid.py`
JSON per-model: `benchmarks/results/local_diacritic_grid/diacritics_*.json`

### Performance — đo 2026-04-25 trên Python 3.13.9

Corpus: 1.000 câu kiểu hợp đồng tiếng Việt (67.600 ký tự).

| Function | Latency (best of 3) | Throughput (ops/s) | Throughput (chars/s) |
|---|---:|---:|---:|
| `normalize` | **0.11 ms** | 9,066,758 | 612,912,817 |
| `has_diacritics` | 0.19 ms | 5,325,466 | 360,001,468 |
| `is_vietnamese` | 0.24 ms | 4,254,631 | 287,613,073 |
| `strip_diacritics` | 5.87 ms | 170,368 | 11,516,906 |
| `fix_diacritics` | 5.12 ms | 195,122 | 13,190,280 |
| **Tham chiếu: stdlib `unicodedata.normalize` NFC** | 0.12 ms | 8,365,051 | 565,477,425 |
| **Tham chiếu: stdlib `unicodedata.normalize` NFD** | 0.48 ms | 2,062,749 | 139,441,817 |

Tái lập: `python benchmarks/perf/bench_text.py`

### Lý do lựa chọn component

**Vì sao pure stdlib (không dep bên thứ ba):**
- `unicodedata` trong CPython core, zero rào cản cài đặt.
- Performance đủ (>500 MB/s trên `normalize`).
- Tất định — không load mô hình, không mạng.
- v0.1 có thể thêm `fix_diacritics(..., llm=...)` LLM-backed cho case mơ hồ, nhưng đường pure-rule giữ.

**Vì sao không `pyvi` hay `underthesea` cho v0?**
- Cả hai xuất sắc cho tokenization/POS-tagging — ngoài phạm vi v0.0.1.
- Sẽ xuất hiện như dep tuỳ chọn trong `nom.text.tokenize` (v0.2+) cho người dùng muốn.

### Tách từ — *đo 2026-04-26*

Hai backend, corpus gold-standard thực:

- `nom.text.word_tokenize` — pure-Python rule + merge bảng compound, zero deps
- `underthesea.word_tokenize` — mô hình CRF, Apache 2.0, opt-in qua `nom-vn[nlp]`

Corpus: **UD_Vietnamese-VTB test split** ([UniversalDependencies/UD_Vietnamese-VTB](https://github.com/UniversalDependencies/UD_Vietnamese-VTB), CC-BY-SA-4.0). 800 câu, 11.692 token gold. Methodology: warmup 3 + best-of-5 throughput; span token đoán so với span gold theo char range (start, end) chính xác.

| Tokenizer | Precision | Recall | **F1** | Throughput | Ghi chú |
|---|---:|---:|---:|---:|---|
| `underthesea==9.4.0` | 95.94% | 95.46% | **95.70%** | 38.102 tok/s | Binary native CRFsuite; ~5 MB disk |
| `nom.text` (rule) | 70.94% | 82.90% | **76.46%** | **747.117 tok/s** | Pure-Python; zero deps; 0 mô hình |

**Phát hiện:**

1. **underthesea +19.24 pp F1 trên `nom.text`** — dữ liệu training CRF thắng quyết định trên boundary compound ngôn ngữ (danh từ riêng nhiều âm tiết, cụm cố định như *mã số*, *địa chỉ*, *Nguyễn Thị Hương*).
2. **`nom.text` nhanh ~20×** (747 k vs 38 k tok/s). Cho RAG indexing, BM25 tokenization, dọn nhẹ — speed thắng; gap F1 không quan trọng khi phía sau là retriever bag-of-words.
3. **`nom.text` recall (82.9 %) > precision (70.9 %)** — over-split. Bảng compound bắt được vài merge (398 hit toàn corpus) nhưng còn xa coverage CRF.

**Cross-check so với số đã công bố** (rule cross-check-against-published-numbers):

- underthesea báo ~94 % F1 trên test set VLSP 2013 [1]; 95.70 % của ta trên UD-VTB test ~1.5 pp trên — có thể do UD-VTB là register dễ hơn VLSP 2013 (văn học prose so với tin tức/business mixed). Cùng order of magnitude — không có divergence methodology cần đuổi.
- Chúng tôi không bench PyVi riêng: tự động từ chối theo chính sách no-pickle (ship file mô hình `.pkl` = arbitrary code execution khi load).

**Khuyến nghị cho `nom-vn`:**

| Use case | Chọn |
|---|---|
| RAG indexing, BM25, search tokenize | `nom.text` — speed dominant |
| NER / dependency parsing / phân tích ngôn ngữ | `nom-vn[nlp]` → `underthesea` — F1 dominant |
| Dọn post-OCR, tokenize khôi phục dấu | `nom.text` — gap F1 chấp nhận; zero deps thắng |

Hai cái bổ sung cho nhau, không thay thế — surface trong API doc để user không pick sai và đổ lỗi cho gap F1.

Tái lập: `python benchmarks/accuracy/bench_segment.py --corpus ud_vtb --split test --json benchmarks/results/baseline_segment_ud_vtb_test.json`
Baseline: `benchmarks/results/baseline_segment_ud_vtb_test.json`

[1]: [README Underthesea](https://github.com/undertheseanlp/underthesea) — số VLSP 2013 báo.

---

## Module: `nom.doc.ocr` — *dự kiến v0.1*

OCR là primitive leverage cao nhất và bị fail nhiều nhất trong AI tiếng Việt. Chúng tôi ship ba backend với cùng interface; default switch theo phần cứng có sẵn.

### So sánh backend (research, chưa test in-house)

| Engine | Acc trên VN | Tốc độ | Xử lý dấu | Setup cost | License |
|---|---|---|---|---|---|
| **Tesseract 5 + `vie`** | ~70-97% (biến động lớn theo chất lượng ảnh) [1] | 9.8 FPS [2] | **Yếu** — nhầm dấu chồng (sắc vs móc trên ô) [3] | apt install | Apache 2.0 |
| **EasyOCR** | ~79% chung (không có số VN-specific tìm được) | 56 FPS [2] | Tốt hơn Tesseract trên nền nhiễu [4] | pip install + ~150MB mô hình | Apache 2.0 |
| **PaddleOCR PP-OCRv5** | ~94.5% trên OmniDocBench [5] | Chậm hơn EasyOCR [2] | Mạnh (training multilingual) | pip install + tải mô hình | Apache 2.0 |
| **VietOCR (Transformer)** | Train đặc biệt cho VN [6] | Chậm hơn (cost Transformer) | **Mạnh nhất** — VN-specialized | pip install + mô hình tuỳ biến | Apache 2.0 |
| **GPT-4o / Claude vision** | ~Best-in-class | Latency API | Best xử lý tone chồng | Cost API | Commercial |

### Khuyến nghị cho `nom.doc`

**Backend mặc định: VietOCR (Transformer)** khi có sẵn, fallback sang **Tesseract** cho tính portable.

```python
# API dự kiến v0.1
from nom.doc import extract
from nom.doc.ocr import VietOCR, Tesseract, PaddleOCR

# Auto: VietOCR nếu cài → PaddleOCR → Tesseract
result = extract("scan.pdf", schema={...})

# Rõ ràng
result = extract("scan.pdf", schema={...}, ocr=PaddleOCR())
```

### Lớp parsing PDF bên dưới — *đo 2026-04-26*

Chúng tôi **không** ship PyMuPDF. License AGPL của nó không tương thích với Apache-2.0 mặc định. Thay vào dùng **pypdfium2** (BSD-3 wrapper trên PDFium của Google, Apache-2.0) làm mặc định trích text nhanh và giữ **pdfplumber** cho tài liệu nhiều bảng.

Corpus: `benchmarks/data/synthetic_pdf_vi/vn_legal.pdf` — PDF VN tổng hợp 7-page xây từ prose VN public-domain thực (UDHR + Wikisource Truyện Kiều prefaces) với lớp text Unicode sạch (DejaVuSans embed). Generator: `benchmarks/data/synthetic_pdf_vi/_generate.py`. Nhãn thật: 18.877 ký tự commit kèm.

`udhr_vi/udhr_vie.pdf` ship sẵn không dùng được ở đây — nó embed font tuỳ biến không có ToUnicode CMap, nên mọi extractor (pdfplumber, pypdfium2, PyMuPDF) trả về CIDs / byte rác. Đã tài liệu hoá trong bench script.

Methodology: warmup 3 + best-of-5 (rule verified-benchmarks). Char-overlap fidelity dùng giao multiset NFC-normalised so với nhãn thật.

| Library | License | Best-of-5 (s) | Throughput | Char overlap |
|---|---|---:|---:|---:|
| **`pypdfium2==5.7.1`** ⭐ default | BSD-3 / Apache-2.0 | **0.0079** | **2.350.431 chars/s** | **99.81%** |
| `pdfplumber==0.11.9` | MIT | 0.3654 | 51.052 chars/s | 99.81% |

**Phát hiện:**

1. **`pypdfium2` nhanh hơn 46×** so với pdfplumber trên trích text-only với fidelity y hệt (99.81% — cả hai miss cùng ~36 ký tự, hầu hết là glyph Hán mà DejaVuSans không render được).
2. **License là headline.** Speedup 19× của PyMuPDF công bố trên `py-pdf/benchmarks` là thật — nhưng AGPL ép mọi dự án phía sau ship dạng AGPL. PDFium dưới pypdfium2 cho ta cùng order-of-magnitude speedup mà không có bẫy license.
3. **pdfplumber giữ trong `nom-vn[doc]`** — vẫn là lựa chọn tốt hơn khi tài liệu có bảng. Pipeline `nom.doc` chọn per-document khi parse.

**Khuyến nghị:**

| Use case | Chọn |
|---|---|
| Trích text thuần (RAG, search indexing) | `pypdfium2` — speed thắng, license sạch |
| Bảng / form / layout có cấu trúc | `pdfplumber` — phát hiện cell tốt hơn |

Tái lập: `python benchmarks/perf/bench_pdf_extract.py`
Baseline: `benchmarks/results/baseline_pdf_extract.json`

Build corpus từ một bản clone sạch: `python benchmarks/data/synthetic_pdf_vi/_generate.py` (cần DejaVuSans — `apt install fonts-dejavu`).

**Lưu ý PyMuPDF / fitz** — chúng tôi giữ chúng hoàn toàn ngoài dependency. User thực sự cần PyMuPDF (ví dụ dự án nội bộ chấp nhận AGPL) tự cài và gọi trực tiếp; chúng tôi không expose wrapper làm mờ ranh giới license.

**Docling (IBM, MIT) — đo 2026-04-26.** Cùng PDF VN, warmup 2 + best-of-3, default `DocumentConverter()`:

| Library | Best (s) | Throughput | Char overlap | Disk |
|---|---:|---:|---:|---:|
| pypdfium2 | **0.0079** | 2.350.431 chars/s | 99.81% | <10 MB |
| pdfplumber | 0.3654 | 51.052 chars/s | 99.81% | <5 MB |
| docling | 1.1889 | 15.703 chars/s | 99.72% | ~1 GB (PyTorch + DocLayNet + TableFormer) |

Docling **chậm hơn pypdfium2 150×** trên PDF text Unicode-clean này và hơi *tệ hơn* về fidelity (99.72% vs 99.81%) — pipeline ML layout không trả lợi tức khi PDF đã có lớp text sạch. Docling kiếm cost của nó trên **layout phức tạp** (multi-column, bảng, công thức, mixed text+ảnh) nơi heuristic của pdfplumber vỡ. Chưa đo in-house trên PDF VN nhiều bảng.

**Khuyến nghị Docling:** giữ NGOÀI `nom-vn[doc]` lúc này. Nếu corpus hướng tới người dùng layout phức tạp xuất hiện (form pháp lý, báo cáo chính phủ), thêm extra `nom-vn[docling]` và surface là `nom.doc.layout_extract()`. Cho đến lúc đó, trọng lượng dependency (~1 GB stack ML + safetensors) không justified cho PDF text thuần.

Bảng landscape trước từ [py-pdf/benchmarks](https://github.com/py-pdf/benchmarks) cho bối cảnh (PDF academic + business mixed):

| Library | Thời gian trung bình per-doc | Ghi chú |
|---|---:|---|
| PyMuPDF (fitz) | 0.5 s | Không ship — AGPL |
| pypdf | 4.2 s | MIT, thao tác cơ bản |
| pdfplumber | 9.5 s | Trích bảng phong phú nhất |

### Nguồn
- [1] [Kết quả test VietOCR / Tesseract VN](https://vietocr.sourceforge.net/)
- [2] [Benchmark PaddleOCR vs EasyOCR vs Tesseract — TildAlice](https://tildalice.io/ocr-tesseract-easyocr-paddleocr-benchmark/)
- [3] [Issue stack-diacritic Tesseract VN](https://github.com/tesseract-ocr/langdata/issues/66)
- [4] [So sánh Tesseract vs EasyOCR](https://ttsforfree.com/en/blogs/image-to-text-python-tesseract-vs-easyocr/)
- [5] [Release note PaddleOCR PP-OCRv5](https://www.tenorshare.com/ocr/paddleocr.html)
- [6] [VietOCR (Transformer) — pbcquoc](https://github.com/pbcquoc/vietocr)
- [7] [Survey on Vietnamese Document Analysis (arXiv 2506.05061)](https://arxiv.org/abs/2506.05061)

---

## Module: `nom.llm` — *dự kiến v0.1*

Nôm không bundle mô hình. Chúng tôi ship class adapter; user chọn mô hình nào để trỏ tới.

### Mô hình khuyến nghị — ba bracket

#### Bracket 1 — local, miễn phí, chạy laptop consumer

**Primary: `Qwen3-8B` qua Ollama**

- License Apache 2.0 — commercial OK
- Chạy ~6GB VRAM (Q4 quant) hoặc 16GB RAM CPU
- VMLU mạnh cho size
- Multilingual gồm tiếng Việt
- Cài một dòng: `ollama pull qwen3:8b`

**Thay thế: `Llama-3.1-8B-Instruct`**
- License Meta (commercial OK với điều kiện)
- VN performance hơi tệ hơn Qwen3 trong review 2026 [1]

**Thay thế: `Vistral-7B-Chat`**
- Đã fine-tune cho tiếng Việt
- License chỉ research (theo VinAI) — *không cho commercial*

#### Bracket 2 — cloud, cost trung bình, chất lượng open top

**`Qwen3-235B-A22B`** qua Together AI / Fireworks / Alibaba Cloud
- Apache 2.0
- 235B MoE (22B active) — VN mạnh
- Khuyến nghị top trong guide best-VN-LLM 2026 [1]
- ~$0.50–1/M input token qua provider

#### Bracket 3 — closed, chất lượng tối đa

| Provider | Mô hình | Vì sao dùng |
|---|---|---|
| OpenAI | `gpt-4o` | Reasoning VN chung tốt nhất, vision-capable |
| Anthropic | `claude-sonnet` | Reasoning long-document mạnh, context lớn |
| Google | `gemini-2.5-pro` | Rẻ nhất ở top tier 2026 |

### Mô hình vision-capable cho `nom.doc` (tài liệu scan)

Cho công việc OCR-grade trực tiếp trên ảnh (bỏ bước OCR hoàn toàn):

| Mô hình | License | Ghi chú |
|---|---|---|
| **Qwen2.5-VL-72B-Instruct** | Apache 2.0 | Top open vision-LLM cho extraction tài liệu có cấu trúc [2] |
| GLM-4.5V | open weights | Mạnh trên chart, bảng, layout phức tạp [2] |
| DeepSeek-VL2 | open weights | Tốt trên doc VN scan theo anecdote |
| GPT-4o (vision) | closed | Best khi latency/cost không phải ràng buộc |

**Khuyến nghị**: `nom.doc.extract` dùng hai đường:
1. PDF native → text → LLM text-only (rẻ nhất, nhanh nhất)
2. Scan/ảnh → vision-LLM trực tiếp (skip OCR, thường chất lượng cao hơn)

### Nguồn
- [1] [Best Open Source LLM for Vietnamese in 2026 — SiliconFlow](https://www.siliconflow.com/articles/en/best-open-source-LLM-for-Vietnamese)
- [2] [Best LLM for Document Screening in 2026 — SiliconFlow](https://www.siliconflow.com/articles/en/best-open-source-LLM-for-Document-screening)
- [3] [Document Data Extraction in 2026: LLMs vs OCRs — Vellum](https://www.vellum.ai/blog/document-data-extraction-llms-vs-ocrs)
- [4] [VMLU Leaderboard](https://vmlu.ai/leaderboard) — xếp hạng LLM VN hiện tại
- [5] [Qwen2.5 release notes](https://qwenlm.github.io/blog/qwen2.5-llm/)

---

## Module: `nom.prompts` — *dự kiến v0.2*

Prompt hệ thống curated, có version cho tài liệu kinh doanh VN. **Chưa có benchmark — giá trị module này nằm ở *prompt nào thắng*, không phải tốc độ raw.**

### Domain sẽ cover

| Domain | Vì sao ưu tiên | Nguồn test set |
|---|---|---|
| **Hợp đồng** | Doc kinh doanh VN tần suất cao nhất | Corpus hợp đồng NRL-curated |
| **Công văn** | Chính phủ/SMB workflow chủ yếu | Corpus VLSP (chỗ license cho phép) |
| **Đơn từ** | Khối lượng cao, input OCR thấp | Synthetic + community submission |
| **Email công sở** | Drafting tone-aware (kính gửi vs cho) | Eval set nội bộ |
| **Hoá đơn / biên lai** | Use-case kế toán | Open OCR datasets |

### Versioning

Prompt có version (`nom.prompts.contracts.v1`). Một khi publish, không bao giờ silently đổi. Pin version là phần của contract tái lập của người dùng.

---

## Benchmark mức module NRL đóng góp (VN-Bench v1)

Đây là việc sẽ đưa số gốc NRL vào `nrl.ai/bench` (so với trang hiện tại tổng hợp VMLU). Xem [VN-Bench v1 roadmap](../www.nrl.ai/app/[locale]/bench/page.tsx) cho danh sách task canonical.

| Task | Mô tả | Eval | Trạng thái |
|---|---|---|---|
| **Trích hợp đồng** | PDF → schema typed | F1 trên field accuracy | đang phát triển |
| **Parse công văn** | Số / ngày / đơn vị / nội dung | Exact match | đang phát triển |
| **Scan OCR → JSON** | Ảnh → có cấu trúc | Char-edit + field accuracy | đang phát triển |
| **Giữ dấu** | Sinh có dấu đúng | Diacritic accuracy trên đoạn dài | đang phát triển |
| **Code-switching EN/VN** | Hiểu hội thoại mixed | Pairwise judge | đang phát triển |
| **QA pháp lý** | Dự đoán điều, trích | Mượn từ VLegal-Bench | partner |

---

## Module: `nom.rag` — *đã ship v0.2.5*

### Làm gì

RAG end-to-end trên tài liệu VN: BM25 + dense (encoder sentence-transformers) hybrid retrieval với RRF fusion, reranking cross-encoder tuỳ chọn, mở rộng HyDE / multi-query tuỳ chọn, sau đó gọi LLM.

Ba dòng từ tài liệu sang câu trả lời — xem docstring `src/nom/rag/pipeline.py` cho ví dụ canonical.

### So sánh reranker trên Zalo Legal QA 5 k — *đo 2026-04-26*

Cùng fixture (5.061 doc / 80 câu hỏi), embedder bkai-vietnamese-bi-encoder, pipeline hybrid+rerank, RTX 3090. So sánh apple-to-apple — chỉ reranker đổi.

| Reranker | License | Disk | Param | R@1 | R@10 | MRR@10 | p50 ms (gồm seg) |
|---|---|---:|---:|---:|---:|---:|---:|
| **`BAAI/bge-reranker-v2-m3`** ⭐ default | Apache 2.0 | ~2.3 GB | 568 M | **86.3 %** | **100.0 %** | **0.929** | 583 |
| `itdainb/PhoRanker` *(word-segmented)* | Apache 2.0 | **~395 MB** | **100 M** | **83.8 %** | 98.8 % | 0.907 | 863 |
| `itdainb/PhoRanker` *(KHÔNG word-segment, BROKEN config)* | Apache 2.0 | ~395 MB | 100 M | 70.0 % | 97.5 % | 0.802 | 295 |

**Bức tranh reranker, framing chính xác.** PhoRanker được báo thắng bge-reranker-v2-m3 trên MMARCO-Vi (NDCG@3 0.6625 vs 0.6087). Trên bench Zalo Legal 5 k của ta, **PhoRanker chỉ kém bge-reranker-v2-m3 2.5 pp ở disk nhỏ hơn 5.7×.** Đây là tradeoff tốt hơn nhiều so với v0.2.17 implied — số 70.0 % R@1 ban đầu là bug methodology (thiếu word segmentation; xem rule ALWAYS DOUBLE-CHECK bên dưới).

**Khuyến nghị:**

- **Default: bge-reranker-v2-m3.** Chất lượng cao nhất (R@1 86.3 %), đơn giản nhất để deploy (không cần preprocessing).
- **Tier light-weight: PhoRanker với word segmentation.** Trong 2.5 pp R@1 của default ở disk nhỏ hơn 5.7× và inference cross-encoder nhanh hơn. Lựa chọn đúng cho laptop nơi 2.3 GB reranker không vừa cùng embedder + LLM. **Cần `nom-vn[nlp]` cho underthesea word segmentation** — pass `word_segment=True` cho `CrossEncoderReranker` hoặc `--reranker-word-segment` cho bench:

  ```python
  CrossEncoderReranker("itdainb/PhoRanker", word_segment=True)
  ```

  863 ms p50 gồm segment underthesea per-query. Trong production cache chunk corpus đã segment ở thời điểm index, drop cost per-query xuống ~300 ms.

**Bài học ALWAYS DOUBLE-CHECK (rule ALWAYS DOUBLE-CHECK của ta).** Số PhoRanker v0.2.17 (70.0 % R@1) sai vì gửi text raw không segment cho mô hình mà card explicitly yêu cầu input đã segment VnCoreNLP. Re-check model card 2026-04-26 bắt được. Khái quát hoá bài học: **cho bất kỳ reranker mới nào, đọc ví dụ usage canonical từ model card trước khi bench.** Preprocessing hardcoded trong bench giờ là kwarg `word_segment=`, không phải giả định ẩn.

**Auto-detect max_length:** `CrossEncoderReranker(...)` giờ tự động phát hiện `max_position_embeddings` của mỗi mô hình từ `config.json` để bạn swap reranker không cần nghĩ. PhoRanker (PhoBERT-base, cap 256) và bge-reranker-v2-m3 (XLM-R-large, cap 512) đều chạy qua cùng call:

```python
from nom.rag import CrossEncoderReranker

# Cả hai chạy — max_length auto-detect
default = CrossEncoderReranker()                         # bge-reranker-v2-m3
lite    = CrossEncoderReranker("itdainb/PhoRanker")     # cap 256, không cần flag tay
```

Override qua `max_length=...` khi heuristic tự động phát hiện sai cho mô hình lạ.

Tái lập: `python benchmarks/rag/bench_rag_vn.py --fixture benchmarks/rag/fixtures/vn_legal_zalo_5k.json --embedder bkai --retrievers hybrid+rerank --reranker itdainb/PhoRanker --json benchmarks/results/baseline_phoranker_zalo5k.json`

Baseline:
`benchmarks/results/baseline_phoranker_zalo5k.json` (PhoRanker),
`benchmarks/results/baseline_bge_reranker_bkai_zalo5k.json` (bge-reranker-v2-m3).

### Retrieval chỉ embedder — *đo 2026-04-26*

So sánh two-tower trực tiếp: encode mọi doc + mọi câu hỏi, rank doc theo cosine. Không BM25, không fusion, không reranker — mọi khác biệt chất lượng đều thuần là embedder. Cách này bắt case mà phân phối training STS-tuned của embedder không transfer sang retrieval (task asymmetric Q→Doc mà pipeline RAG thực sự làm).

Corpus: `benchmarks/rag/fixtures/vn_legal_zalo_5k.json` (5.061 doc / 80 câu hỏi, sample từ Zalo AI 2021 Legal QA, MIT). Hardware: RTX 3090.

| Mô hình | License | Disk | R@1 | R@10 | MRR@10 | docs/s |
|---|---|---:|---:|---:|---:|---:|
| **`bkai-foundation-models/vietnamese-bi-encoder`** ⭐ | Apache 2.0 | ~383 MB | **76.25 %** | **98.75 %** | **0.8604** | 60 |
| `dangvantuan/vietnamese-embedding` (default hiện tại) | Apache 2.0 | ~440 MB | 35.00 % | 67.50 % | 0.4449 | 53 |

bkai thắng **+41.25 pp R@1 và +31.25 pp R@10** ở size disk *nhỏ hơn* và throughput tương tự. Gap là cấu trúc, không tunable:

- `dangvantuan` đã fine-tune trên **STS** (similarity đối xứng) — mạnh trên benchmark như VN-STS nhưng task retrieval câu hỏi→tài liệu asymmetric ngoài phân phối.
- `bkai` đã train với **MultipleNegativesRankingLoss** trên cặp Q→Doc từ MS MARCO + SQuAD v2 + 80 % Zalo Legal — chính xác task ta chạy.

**Catch:** bkai cần preprocessing word-segmenter (từ multi-syllable VN nối bằng underscore). Class `nom.embeddings.BKaiEmbedder` wrap `underthesea` để làm điều này tự động. Cài: `pip install "nom-vn[embeddings,nlp]"`.

**Cross-check:** số Zalo Legal corpus đầy đủ bkai công bố ([model card](https://huggingface.co/bkai-foundation-models/vietnamese-bi-encoder)) báo Acc@1 73.28, Acc@10 93.59, MRR 80.73. Subset 5k của ta (76.25, 98.75, 0.8604) hơi cao hơn vì subset có ít distractor — order of magnitude consistent. Không có divergence methodology.

**Hành động cho v0.2.x:** thêm `BKaiEmbedder` opt-in, KHÔNG đổi default trong `nom.rag` / `nom.retrieve` — sẽ invalidate cache embedding đã persist của mọi người dùng hiện tại. Bản major 0.3.x sẽ lật default; bây giờ opt-in giữ tương thích cache.

```python
from nom.embeddings import BKaiEmbedder
from nom.rag import RAG
rag = RAG(embedder=BKaiEmbedder(device="cuda"))
```

Tái lập: `python benchmarks/rag/bench_embedder_compare.py --json benchmarks/results/baseline_embedder_compare_zalo5k.json`

### Lưới mô hình RAG VN — *đo 2026-04-25*

Hai fixture, đều sample từ [GreenNode/zalo-ai-legal-text-retrieval-vn](https://huggingface.co/datasets/GreenNode/zalo-ai-legal-text-retrieval-vn) (MIT). Hardware: NVIDIA RTX 3080 Laptop, fp16, warmup=1, timed=1-2 (best-of-N theo rule verified-benchmarks).

#### Corpus đầy đủ — `vn_legal_zalo_full.json` (61.068 bài, 82.696 chunk, 788 câu hỏi)

| Retriever | recall@1 | recall@3 | recall@5 | recall@10 | mrr@10 | p50 ms |
|---|---:|---:|---:|---:|---:|---:|
| BM25 | 0.395 | 0.664 | 0.725 | 0.780 | 0.535 | 430 |
| Dense (dangvantuan) | 0.237 | 0.379 | 0.466 | 0.537 | 0.328 | 18 |
| Hybrid (RRF) | 0.368 | 0.602 | 0.690 | 0.783 | 0.505 | 491 |
| **Hybrid + bge-reranker-v2-m3** | **0.572** | **0.802** | **0.846** | **0.868** | **0.688** | 1539 |

#### Corpus subset — `vn_legal_zalo_5k.json` (5.061 bài, 6.833 chunk, 80 câu hỏi)

| Embedder | Retriever | recall@1 | recall@3 | recall@10 | mrr@10 | p50 ms | p95 ms |
|---|---|---:|---:|---:|---:|---:|---:|
| `dangvantuan/vietnamese-embedding` (768-d, ~440 MB) | BM25 only | 0.762 | 0.912 | 0.975 | 0.843 | 27 | 48 |
|  | Dense only | 0.412 | 0.725 | 0.863 | 0.585 | 15 | 25 |
|  | Hybrid (RRF) | 0.650 | 0.875 | 0.975 | 0.780 | 59 | 113 |
|  | + `BAAI/bge-reranker-v2-m3` | **0.863** | **1.000** | **1.000** | **0.931** | 681 | 747 |
|  | + `namdp-ptit/ViRanker` | 0.850 | 0.963 | 1.000 | 0.913 | 687 | 743 |
| `AITeamVN/Vietnamese_Embedding` (1024-d, ~2.3 GB, BGE-M3 base) | BM25 only | 0.762 | 0.912 | 0.950 | 0.843 | 24 | 41 |
|  | Dense only | **0.825** | 0.963 | 0.975 | 0.894 | 47 | 77 |
|  | Hybrid (RRF) | 0.800 | 0.963 | 0.975 | 0.884 | 97 | 131 |
|  | + `BAAI/bge-reranker-v2-m3` | **0.863** | 0.988 | 0.988 | 0.923 | 720 | 786 |
|  | + `namdp-ptit/ViRanker` | **0.863** | 0.963 | 0.988 | 0.914 | 718 | 799 |

Tái lập: `bash benchmarks/rag/run_grid.sh`. JSON baseline per-config dưới `benchmarks/rag/baselines/zalo_5k__*.json` và mirror tới [nrl-ai/vn-rag-bench](https://huggingface.co/datasets/nrl-ai/vn-rag-bench).

### Phát hiện

1. **Lựa chọn embedder quan trọng hơn lựa chọn reranker — cho stage bi-encoder.** Đổi từ `dangvantuan` sang `AITeamVN` gấp đôi dense recall@1 (0.412 → 0.825). Fine-tune BGE-M3 `AITeamVN/Vietnamese_Embedding` đặc biệt tune trên Zalo Legal QA, thể hiện ở số in-domain.
2. **Reranker hội tụ.** Cả `BAAI/bge-reranker-v2-m3` và `namdp-ptit/ViRanker` đưa recall@1 cuối lên ~0.863 bất kể embedder feeder. Reranker dominate ranking cuối khi bài gold đã trong pool top-30.
3. **Chất lượng peak tốt nhất:** `dangvantuan` + `BAAI/bge-reranker-v2-m3` — recall@10 = 1.000 và recall@3 = 1.000 trên fixture này. Affinity BM25 cao hơn của embedder dangvantuan (chân dense yếu nên RRF nghiêng vào BM25) lift trần recall@10.
4. **Tuỳ chọn skip-reranker:** `AITeamVN` dense một mình được recall@1 = 0.825 ở 47 ms p50 — nhanh khoảng **15×** so với +rerank, mất chỉ 4% absolute recall@1. Lựa chọn đúng cho deploy nhạy latency nơi 825/863 chấp nhận được.
5. **BM25 cạnh tranh đến giật mình** trên VN pháp lý — *ở quy mô corpus nhỏ*. Trên subset 5k BM25 chạm recall@1 = 0.762, nhưng trên corpus 61k đầy đủ rớt xuống 0.395. **Hiệu ứng size-corpus dominant** cho retrieval lexical; stage dense / reranker quan trọng hơn khi pool distractor lớn.
6. **Reranker trở nên critical hơn ở quy mô**, không kém. Đi từ hybrid → hybrid+rerank lift recall@1 0.213 absolute trên subset 5k và 0.204 absolute trên corpus 61k đầy đủ — proportionally lift relative lớn hơn nhiều trên corpus đầy đủ (+55% relative vs +33% relative).
7. **BM25 pure-Python là bottleneck ở quy mô.** Trên corpus 61k đầy đủ BM25.search() v0.2.5 chạy 430ms p50 — chậm hơn nhiều dense trên GPU (18ms). v0.2.6 swap sang [`bm25s`](https://github.com/xhluca/bm25s) (MIT, scipy.sparse): cùng recall y hệt bit, **search nhanh hơn 607×** (0.7ms p50). Xem `benchmarks/results/bm25_compare__zalo_full.json` cho bảng đầy đủ. Chân dense giờ là bottleneck per-query.

### Cross-check so với số đã công bố (theo rule cross-check-against-published-numbers)

- **Multi-stage IR cho VN Legal** (PKAW 2022, arXiv:2209.14494): báo F2 = 0.741 trên corpus Zalo đầy đủ với PhoBERT-large + sqrt(BM25)·cos hybrid + 3 round mining hard-negative. recall@10 = 0.868 trên corpus 61k đầy đủ của ta implied F2 tương đương (≈0.6-0.7), đạt được có sẵn với bge-reranker-v2-m3 — không fine-tune. Alignment hợp lý.
- **UIT 2024** (arXiv:2507.14619): Vietnamese-bi-encoder + PhoRanker, MRR@10 cross-encoder = 79.11% trên 261k doc pháp lý. MRR@10 = 0.688 của ta trên corpus 61k đầy đủ — ~10 điểm thấp hơn; giải thích bởi (a) ta dùng bge có sẵn thay PhoRanker đã fine-tune trên dữ liệu pháp lý, và (b) hiệu ứng size-corpus chạy cả hai chiều. Thêm PhoRanker vào lưới là bước tiếp theo hợp lý (excluded đến nay vì dep VnCoreNLP Java).
- **Model card AITeamVN/Vietnamese_Embedding**: claim +27.9% Acc@1 so với BGE-M3 base trên retrieval domain pháp lý. dense Acc@1 = 0.825 của ta trên subset 5k vs BGE-M3 base (chưa test) — cần bench BGE-M3 trên cùng fixture để xác nhận size lift. **Mở: thêm BGE-M3 vào lưới** để verify lợi thế công bố của fine-tune AITeamVN.
- **PhoRanker NDCG@10 = 0.7422 trên MMARCO-VI** ([model card](https://huggingface.co/itdainb/PhoRanker)): chưa đo — PhoRanker cần VnCoreNLP (JVM Java), excluded khỏi lưới này có chủ đích.

### Config khuyến nghị (default trong `nom-vn` v0.2.5)

```python
from nom.rag import RAG, CrossEncoderReranker
rag = RAG.from_documents(
    docs,
    llm=Ollama(model="qwen3:8b"),
    embedder=VietnameseEmbedder(),                  # 440 MB, dim 768
    reranker=CrossEncoderReranker(),                # bge-reranker-v2-m3
)
answer = rag.ask(question, rerank=True, rerank_candidates=30)
```

Cho deploy bound latency không có GPU, drop reranker và dùng `AITeamVNEmbedder()` (dense tốt hơn, không có thuế cross-encoder).

---

## Module: `nom.doc.ocr` — *baseline thật đo 2026-04-26*

### Làm gì

Chạy engine OCR trên ảnh tiếng Việt (page PDF, scan, ảnh) và trả về text thuần. v0.2.x ship đường Tesseract; phiên bản sau sẽ thêm tuỳ chọn VLM và VN-specialised khi chúng kiếm được trọng lượng dependency trên bench.

### Lưới engine OCR tiếng Việt — *đo 2026-04-26*

**Corpus thật:** `vn_ocr_subset` — 478 ảnh sample tất định (seed=42) từ [`ducto489/ocr_datasets`](https://huggingface.co/datasets/ducto489/ocr_datasets) shard 0 (Apache-2.0), filter các hàng chứa dấu VN và ít nhất 8 ký tự ground-truth text. Hầu hết là prose machine-rendered ở các mức nhiễu khác nhau — đại diện cho input OCR tài liệu thực.

Hardware: CPU (8 cores, không có contention GPU với bench RAG), warmup=1, timed=2, p50/p95 báo best-of-N.

| Engine | License | CER | WER | diacritic-CER | exact match | p50 ms | p95 ms |
|---|---|---:|---:|---:|---:|---:|---:|
| **Tesseract 5** (`vie` traineddata) | Apache-2.0 | **0.0819** | **0.3771** | **0.1193** | **0.345** | 447 | 656 |
| EasyOCR 1.7 (`vi`) | Apache-2.0 | 0.1176 | 0.5304 | 0.2052 | 0.218 | **183** | **431** |

JSON baseline dưới `benchmarks/results/ocr_vn_subset__*.json` và mirror tới [nrl-ai/vn-rag-bench](https://huggingface.co/datasets/nrl-ai/vn-rag-bench).

### Phát hiện

1. **Fixture synthetic không phải benchmark.** `synthetic_ocr_vi/clean` cho Tesseract CER = 0.000 / exact = 1.000 — hoàn hảo. `synthetic/noisy` cho CER = 0.0064. Cả hai đều quá dễ để rank engine. Dữ liệu ducto489 thật drop Tesseract xuống CER = 0.082 — đó là baseline trung thực.
2. **Diacritic-CER (11.9%) tệ hơn ~46% so với CER tổng (8.2%)** — xác nhận mode fail mà người đọc tiếng Việt cảm thấy. Dấu thanh (sắc, huyền, hỏi, ngã, nặng) là 1–3 pixel và là thứ đầu tiên OCR mất trên scan nhiễu. Một reranking diacritic-aware hoặc fix post-OCR sẽ giúp ở đây.
3. **Latency ~450 ms per ảnh trên 8 CPU cores.** Tesseract là C++ bên dưới và không parallel trong một page; cải thiện throughput đến từ chạy nhiều page parallel ở mức pipeline, không phải tune internals Tesseract.
4. **Tesseract thắng EasyOCR trên mọi metric chất lượng cho VN.** CER 8.19% vs 11.76%, diacritic-CER 11.93% vs 20.52%, exact-match 34.5% vs 21.8%. EasyOCR nhanh hơn 2.4× (183 ms vs 447 ms p50) nhưng gap accuracy dominate cho use case Q&A tài liệu — mất 13% absolute exact-match cho 264 ms latency là trade tệ. **Default giữ Tesseract.** EasyOCR có thể hữu ích cho use case bulk-indexing throughput cao nơi accuracy đánh đổi được; chúng tôi surface cả hai option trong `bench_ocr_real.py`.

### Engine đã khảo sát nhưng chưa đo

- **VietOCR** (Apache-2.0, Transformer VN-specialised) — `pip install vietocr` lỗi trên Python 3.13 (`KeyError: '__version__'` trong setup.py). Pin cho theo dõi tiếp; phía trên cần `pyproject.toml` tương thích Python-3.13.
- **PaddleOCR PP-OCRv5** (Apache-2.0, lightweight ~150 MB) — ứng viên hứa hẹn nhất tiếp theo. CER báo ~0.94 trên OmniDocBench multilingual; không VN-specific nhưng thường thắng Tesseract trên text rendered.
- **Surya OCR** — code là **GPL-3.0**, mô hình open-RAIL-M. Cả hai license-incompatible với surface mặc định Apache-2.0. Sẽ bench cho so sánh; không thể ship làm default.

### VLM OCR — *đo 2026-04-26*

Test xem Vision-Language Model general-purpose có thể match OCR purpose-built trên transcription line-image VN.

**Engine:** `qwen2.5vl:3b` và `qwen2.5vl:7b` (Apache-2.0) qua Ollama 0.21.2 trên RTX 3090. Quantize Q4_K_M. Prompt: VN tight "transcribe exactly, no chatter" (xem `OllamaVLM` trong `benchmarks/accuracy/bench_ocr_real.py`). Output trim defensive cho think-tag, code-fence, và label echo.

**Corpus:** 50 ảnh đầu từ `vn_ocr_subset` (sample từ [ducto489/ocr_datasets](https://huggingface.co/datasets/ducto489/ocr_datasets), Apache-2.0). Single-line text VN print sạch — cùng ảnh chạy trên Tesseract và EasyOCR cho so sánh trực tiếp.

| Engine | Q4 size | CER | WER | Diacritic CER | Exact match | p50 ms | p95 ms |
|---|---:|---:|---:|---:|---:|---:|---:|
| **Tesseract 5 (vie)** | ~30 MB | **5.53%** | 26.78% | 9.71% | **38.0%** | **80.6** | 110.5 |
| EasyOCR (vi) | ~150 MB | 9.39% | 43.86% | 19.84% | 18.0% | 31.1 (GPU) | 68.3 |
| qwen2.5vl:7b | 6.0 GB | 31.07% | 140.04% | 33.38% | 18.0% | 818.0 | 1332.2 |
| qwen2.5vl:3b | 3.2 GB | 39.86% | 175.43% | 41.82% | 15.0% | 1165.5 | 3993.6 |

**Phát hiện:**

1. **VLM thua quyết định trên OCR single-line sạch.** qwen2.5vl:7b có CER 31% vs Tesseract 5.53% — gap 25 điểm. Mô hình hallucinate: "1892 - Tạp Chí Vogue..." → "1892 92 92 92 92..." (loop token), "XÃ CHIỀNG ƠN" → "CHÍNH XÁC", "churchill và tưởng giới thạch" → "Churchill và tướng Eisenhower cùng được trao giải thưởng" (cả câu plausible-nhưng-bịa).
2. **Tool đúng vẫn là tool đúng.** VLM train trên page đầy đủ; trên crop dòng tight không có context tài liệu, prior ngôn ngữ dominate signal visual và mô hình drift sang mode "complete-the-sentence". Head CTC của Tesseract purpose-built cho alignment glyph trái-sang-phải và không có mode fail này.
3. **Latency: VLM chậm hơn 10×** (818 ms vs 80 ms p50). Cho batch 478 ảnh đây là 6.5 phút vs 39 giây.
4. **Use case của VLM trong OCR là chỗ khác.** Extraction multi-field (field hoá đơn, CCCD, form có checkbox), chữ viết tay scan, và workflow "OCR + hiểu text" là chỗ VLM kiếm cost. Đã document để user không chộp lấy `qwen2.5vl` mong đợi nó thắng Tesseract trên ảnh dòng đơn giản.

**Khuyến nghị:** **OCR mặc định giữ Tesseract.** VLM OCR hợp khi task phía sau là *hiểu* tài liệu, không phải transcribe nó — surface là một đường `nom.doc.vlm_extract()` riêng trong release tương lai, không phải backend OCR swap-in.

Tái lập: `python benchmarks/accuracy/bench_ocr_real.py --corpus benchmarks/data/vn_ocr_subset --variant none --engines ollama_vlm --ollama-model qwen2.5vl:7b --ollama-base-url http://localhost:11434 --limit 50`
Baseline: `benchmarks/results/baseline_ocr_vlm_qwen25vl_7b.json`, `baseline_ocr_tesseract_50.json`, `baseline_ocr_easyocr_50.json`.

### Config khuyến nghị (default v0.2.x)

```python
from nom.doc import Pipeline
# Tesseract đã wire vào nom.doc.OCR mặc định; cài vie traineddata
# qua `apt install tesseract-ocr-vie` (hoặc brew).
pipeline = Pipeline()
text = pipeline.run("scanned.pdf").text
```

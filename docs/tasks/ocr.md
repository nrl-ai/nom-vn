# OCR tiếng Việt

Trích văn bản từ ảnh hoặc PDF scan. Mặc định của chúng tôi là
**Tesseract 5 + traineddata `vie`** — đo nhanh hơn, chính xác hơn các
ứng viên VLM cho dòng chữ in sạch. Khi tài liệu là PDF born-digital
(layer text), dùng [`pdf-extraction`](/tasks/pdf-extraction) thay vì.

## TL;DR — gợi ý theo register (đo 2026-05-01)

| Register | Engine khuyến nghị | CER đã đo | Latency |
|---|---|---:|---:|
| Printed clean (chữ in rõ, nền sạch) | **Tesseract `vie`** | 0.00 % | 80 ms |
| Printed noisy (chữ in nhiễu nhẹ) | **Tesseract `vie`** | 0.70 % | 80 ms |
| Printed hard scan (in chất lượng kém) | **VietOCR** (nhỉnh hơn) | 29.00 % vs Tesseract 30.34 % | 246 ms |
| **Handwriting (chữ viết tay)** | **VietOCR** | **31.82 %** vs Tesseract 69.34 % | 246 ms |

```bash
# Tesseract cho printed clean / noisy
sudo apt install tesseract-ocr tesseract-ocr-vie

# VietOCR cho handwriting (cần install từ source — PyPI bị broken)
pip install git+https://github.com/pbcquoc/vietocr.git
```

```python
# Printed text — Tesseract (nhanh, chính xác trên chữ in sạch)
from nom.doc.ocr import TesseractOCR
ocr = TesseractOCR(lang="vie")
text = ocr.read("scan.png")

# Handwriting — VietOCR (transformer VN-specific, Apache 2.0)
from vietocr.tool.config import Cfg
from vietocr.tool.predictor import Predictor
from PIL import Image
cfg = Cfg.load_config_from_name("vgg_transformer")
cfg["device"] = "cuda"
predictor = Predictor(cfg)
text = predictor.predict(Image.open("handwriting_line.png").convert("RGB"))
```

**Quy tắc:**

- *Chữ in sạch / quét tốt* → Tesseract `vie`. 0-1 % CER, 80 ms/dòng.
- *Chữ viết tay tiếng Việt* → **VietOCR** vgg_transformer. 32 % CER trên
  brianhuster handwriting (so với Tesseract 69 %; **cải thiện 37.5 pp
  tuyệt đối, ~54 % tương đối**).
- *Tài liệu / form / ID card / layout phức tạp* → VLM (Qwen2.5VL,
  Gemma3-Vision) — nhưng chỉ ở mức tài liệu, không ở mức dòng (xem
  cảnh báo bên dưới).
- *PDF có text layer* → `nom.doc.pdf` qua pypdfium2 (không OCR).

## Bức tranh công khai

| Backend | License | CER `synth printed clean` | CER `brianhuster handwriting` | Latency p50 |
|---|---|---:|---:|---:|
| **Tesseract 5 + `vie`** | Apache 2.0 | **0.00 %** ⭐ | 69.34 % | 80 ms |
| **VietOCR vgg_transformer** | Apache 2.0 | 1.41 % | **31.82 %** ⭐ | 240 ms |
| EasyOCR | Apache 2.0 | — | 71.52 % | 60 ms |
| TrOCR base-handwritten (English) | MIT | — | 75.89 % | 248 ms |
| `qwen2.5vl:7b` | Apache 2.0 (model) | 31.07 % | not benched | 1.4 s |
| Surya OCR | open-RAIL-M | — | — | — |

**Phát hiện 2026-05-01:** Tesseract `vie` không train cho handwriting;
hiệu năng sụp 0 % → 69 % CER khi chuyển từ printed sang handwriting.
**VietOCR vgg_transformer** (pbcquoc/vietocr, Apache 2.0, transformer
VN-specific) **giảm CER trên handwriting 37.5 pp tuyệt đối** so với
Tesseract — đây là engine đúng cho register này. Trên printed in sạch
ngược lại: Tesseract giữ ưu thế tốc độ + chính xác.

JSON nguồn:
[`baseline_ocr_engines.json`](https://github.com/nrl-ai/nom-vn/blob/main/benchmarks/results/baseline_ocr_engines.json)
(handwriting, n=200) ·
[`baseline_ocr_engines_per_register.json`](https://github.com/nrl-ai/nom-vn/blob/main/benchmarks/results/baseline_ocr_engines_per_register.json)
(per-register summary).

**VLM hallucination cảnh báo**: trên crop dòng đơn (typical OCR setup),
Qwen2.5VL 7B đạt **31 % CER** — gấp 6 lần Tesseract. Lý do: prior ngôn
ngữ chi phối khi tín hiệu thị giác hẹp. VLM là công cụ đúng cho **hiểu
tài liệu** (form, hoá đơn, ID card, chữ viết tay) chứ không phải dòng
chữ in sạch.

`Surya OCR` fail audit license: code GPL-3 + model open-RAIL-M không
tương thích với mục tiêu phân phối Apache 2.0 của chúng tôi. Chúng tôi
**không ship** Surya — bỏ qua dù số quality cạnh tranh.

## Pipeline của chúng tôi

```python
from nom.doc.ocr import TesseractOCR
from PIL import Image

ocr = TesseractOCR(lang="vie", config="--psm 6")  # PSM 6 = single uniform block
text = ocr.read(Image.open("scan.png"))
```

Adapter wrap `pytesseract` với:

- Pre-process tự động (deskew nhẹ, contrast normalize) khi `auto_preprocess=True`
- NFC chuẩn hoá output
- Rule fallback nếu Tesseract không trả về gì cho dòng (ảnh trắng / quá nhỏ)

## Kết quả — đã đo

Đo trên `benchmarks/data/synthetic_ocr_vi/` (40 ảnh PNG, ground truth chuẩn xác,
clean + noisy mix). Metric: CER (character error rate) tính trên chuỗi
ký tự đã NFC. Diacritic-CER tính riêng cho combining marks (xem
[docs/benchmark.md](/benchmark)).

| Backend | CER | Diacritic-CER | Latency p50 |
|---|---:|---:|---:|
| Tesseract 5 + `vie` | **5.53 %** | 8.21 % | 80 ms |
| EasyOCR | 9.39 % | 14.88 % | 250 ms |
| qwen2.5vl:7b VLM | 31.07 % | 38.45 % | 1.4 s |

JSON baseline: `benchmarks/results/baseline_ocr_*.json`.

## Post-correct với `vn-spell-correction-base` (opt-in)

Một thí nghiệm đã đo: chạy mô hình sửa chính tả trên output Tesseract
để cố gắng giảm CER. **Kết quả mixed** — gain WER ~5 pp tuyệt đối / 8 %
tương đối trên ảnh khó (CER ~30 %), gần wash trên ảnh sạch (Tesseract
< 1 % CER thì post-correct là no-op). Per-image: 11/30 ảnh được giúp,
12/30 bị hại trên ảnh khó.

| Variant | n | CER raw | CER post-correct | Δ CER | Δ WER |
|---|---:|---:|---:|---:|---:|
| `synthetic_ocr_vi/clean` | 20 | 0.00 % | 0.00 % | 0.00 | 0.00 |
| `synthetic_ocr_vi/noisy` | 20 | 0.70 % | 0.60 % | -0.10 | -0.38 |
| `synthetic_ocr_vi/hard` | 30 | 30.34 % | 29.91 % | -0.43 | **-5.22** |

Lý do gain nhỏ hơn literature (ByT5 fine-tune báo cáo 33-67 % giảm CER):
mô hình của ta train trên nhiễu synthetic kiểu typing, không phải lỗi
OCR-specific; tokenizer SentencePiece phân tách output Tesseract bị
corrupt thành garbage. Literature
([Tran et al. 2024](https://arxiv.org/html/2410.13305)) báo cáo
WER 27 % → 18 % khi train trực tiếp trên cặp `(Tesseract, GT)` —
nhưng giả định baseline ~5-30 % CER (printed scan).

### Phân tích sâu thất bại — vì sao post-correct không cứu được handwriting (2026-05-01)

Đã thử fine-tune `nrl-ai/vn-spell-correction-base` trên 9,626 cặp
`(Tesseract output, GT)` từ
[`brianhuster/VietnameseOCRdataset`](https://huggingface.co/datasets/brianhuster/VietnameseOCRdataset)
(Apache 2.0, handwriting). Bench trên 200 ảnh test split (giữ tách
khỏi training):

| Pipeline | CER | WER | helped/hurt |
|---|---:|---:|---|
| Tesseract `vie` baseline | **69.34 %** | 98.95 % | — |
| + base spell-correct (off-the-shelf) | 69.98 % (+0.64) | 98.56 % (-0.40) | 35 / 103 |
| + fine-tuned ocr-correct (3 epochs) | **81.80 % (+12.46)** | 101.26 % (+2.31) | 14 / 173 |

**Cả hai post-correct đều làm tệ hơn.** Fine-tuned phiên bản tệ
nhiều hơn — mô hình học bịa văn bản tiếng Việt plausible từ rác,
không sửa.

Ví dụ thất bại điển hình:
```
GOLD: khung cảnh kinh tế, xã hội và định chế.
RAW : vhuag cảnh kuÄ tố, xá đậu v3 đụnh chế   (CER 33 %)
PP  : và những cảnh sát, xã hội và 3            (CER 51 %)
```

Mô hình bịa "cảnh sát" thay vì "kinh tế".

**Root cause:** Tesseract `vie` không train cho VN handwriting; CER
70 % không đủ tín hiệu để recover. Đây là failure mode "hallucination
over-correction" mà
[Kanerva et al. 2025](https://arxiv.org/html/2502.01205v1) đã báo
cáo trên Finnish (LLM post-OCR -19 % đến -76 % CER, *tệ hơn* baseline).

#### Quantified failure modes (analyze_failure.py)

Diagnostic script `training/ocr_correction/analyze_failure.py` đã phân
tích 200 ảnh test:

| Chỉ báo | Off-the-shelf base | Fine-tuned ocr-correct |
|---|---:|---:|
| **% từ trong post-correct KHÔNG có trong raw OCR** (chỉ số hallucination) | 39.5 % | **91.3 %** |
| Độ dài trung bình output (ký tự, gold = 67) | 46.4 | 39.3 |
| Số output trùng lặp (mode collapse) | 0 | 2 (`. `, ...) |
| Per-bucket Δ CER (50-70 % CER bucket, n=105) | +1.45 pp | **+15.58 pp** |
| Per-bucket Δ CER (70 %+ bucket, n=88) | -0.66 pp | **+7.70 pp** |

**91 % các từ trong output fine-tune không tồn tại trong input gốc**
— mô hình đang sinh tự do thay vì sửa.

#### Inference-time guards giảm regression nhưng không cứu được

Thử thêm guardrails (beam search 4, no-repeat n-gram=3, length-conditioned
generation, confidence gate dựa trên ký tự diacritic VN):

| Pipeline | CER | WER | Δ vs raw |
|---|---:|---:|---:|
| Tesseract raw only | 69.34 % | 98.95 % | baseline |
| + spell-correction-base (greedy) | 69.98 % | 98.56 % | +0.64 / -0.40 |
| + spell-correction-base (guarded) | 70.40 % | 99.19 % | +1.06 / +0.24 |
| + fine-tuned ocr-correct (greedy) | 81.80 % | 101.26 % | +12.46 / +2.31 |
| + fine-tuned ocr-correct (guarded) | 78.32 % | 98.91 % | **+8.98** / **-0.04** |

Guards giảm regression của fine-tune từ +12.46 → +8.98 pp CER (cải thiện
3.5 pp) nhưng không đảo ngược được kết luận: **post-correct trên
Tesseract handwriting không thể net-positive**.

#### Root cause

**OCR baseline 70 % CER là quá xấu để post-correct cứu được.** Khi
7/10 ký tự sai, không còn đủ tín hiệu cho mô hình recover nội dung
gốc. Kết quả tốt nhất là "không làm gì" (raw_only) — bất kỳ post-correct
nào đều thêm risk hallucination.

Literature tham khảo:

- [Tran et al. 2024](https://arxiv.org/html/2410.13305) báo cáo
  WER 27 % → 18 % khi train trực tiếp trên cặp `(Tesseract, GT)` —
  nhưng baseline của họ là **printed scan ~30 % CER**, không phải
  handwriting 70 %.
- [Kanerva et al. 2025](https://arxiv.org/html/2502.01205v1) báo cáo
  LLM post-OCR trên Finnish: CER -19 % đến -76 % (tệ hơn baseline)
  trên một số corpus — chính xác failure mode chúng tôi gặp.

### Future work — đường đi để OCR thật sự cải thiện

Xếp theo ROI giảm dần:

1. **Replace OCR engine với một mô hình handwriting-aware**
   (không phải post-correct).
   - **PaddleOCR PP-OCRv5** với VN handwriting model: literature báo
     cáo CER 15-30 % cho VN handwriting, đủ thấp để post-correct
     có chance.
   - **VietOCR transformer** (cộng đồng pbcquoc/vietocr): VN-specific,
     license Apache 2.0, format `.pth` (PyTorch state dict).
   - **TrOCR fine-tune trên brianhuster** (start from
     `microsoft/trocr-base-handwritten`, replace tokenizer với
     BARTpho-syllable, train ~8 h GPU). Likely best result.
2. **Gate post-correct với confidence proxy** — chỉ áp dụng khi raw
   OCR đạt baseline 5-30 % CER (printed text). Đã có hint từ
   `_confidence_gate_passes()` trong `bench_with_guards.py` —
   chỉ cần thêm một phán đoán "raw đủ tốt để correct" để skip cases
   gibberish.
3. **Train OCR-correction trên printed-VN corpus thay vì handwriting**
   — generate cặp `(Tesseract output trên ảnh print synthetic, GT)`
   với CER 5-15 %. Đây là band post-correct hoạt động được.
4. **Switch base sang ByT5 byte-level** thay vì SentencePiece — robust
   hơn với corruption ký tự cấp byte (literature confirms).
5. **Add copy mechanism** vào architecture (Pointer-Generator) — cho
   phép model copy chữ đúng từ input thay vì phải regenerate. Yêu
   cầu retrain từ đầu.

#### Decision sau phân tích

- **KHÔNG ship `vit5-ocr-correct` model.** Negative-result kể cả với
  guards.
- **KHÔNG enable post-correct mặc định trong `nom.doc.ocr`** — nó
  không cải thiện trên handwriting, neutral trên printed in sạch.
- **Document opt-in path** với confidence gate cho user có printed
  scan với baseline ~5-30 % CER (band post-correct chứng minh hoạt
  động được trong literature).
- **Pivot ưu tiên** sang fix OCR engine — train TrOCR-VN cho
  handwriting hoặc thử PaddleOCR PP-OCRv5 với handwriting model.
  Đây là sprint riêng, sẽ có corpus + bench harness trong repo
  để re-evaluate nhanh khi engine khác có sẵn.

Reproduce postmortem analysis:

```bash
python training/ocr_correction/analyze_failure.py --n-samples 200
python training/ocr_correction/bench_with_guards.py \
    --json benchmarks/results/baseline_ocr_post_correct_real_guarded.json
```

**Quyết định:** không bật mặc định (gain không đáng phức tạp), nhưng
làm sẵn như opt-in cho ai có ảnh quét xấu thực sự (CER ≥ 20 %).

```python
import pytesseract
from PIL import Image
from nom.text.diacritic_models import HFDiacriticModel

tess_text = pytesseract.image_to_string(Image.open("scan.png"), lang="vie")

# Opt-in post-correct (chậm thêm ~150 ms/dòng GPU, ~400 ms CPU)
corrector = HFDiacriticModel(model_id="nrl-ai/vn-spell-correction-base")
clean = corrector(tess_text)
```

Reproduce:

```bash
python benchmarks/data/synthetic_ocr_vi/render_hard.py --n 30
python benchmarks/accuracy/bench_ocr_post_correct.py \
    --variants hard \
    --json benchmarks/results/baseline_ocr_post_correct_hard.json
```

## Mô hình `nrl-ai/*` đã huấn luyện

Hiện chưa có. Chúng tôi đã audit nhiều phương án custom OCR:

- **Train từ đầu** một CRNN VN-only — chi phí cao (~2 ngày GPU trên
  ImageNet-VN synthetic), kết quả khó vượt Tesseract trên dòng in sạch.
- **Fine-tune `microsoft/trocr-small-printed`** — khả thi với ~6 h GPU
  trên synthetic VN, có khả năng thu hẹp khoảng cách Tesseract trên một
  số corner case (bold / italic / vintage form).
- **Fine-tune cho chữ viết tay tiếng Việt** — chỗ trống thật của hệ
  sinh thái; nhưng cần dataset chữ viết tay VN curate được — đó là
  một dự án riêng.

Quyết định hiện tại: **không train custom OCR**. Tesseract đã rất tốt
cho dòng in sạch; chữ viết tay là sprint riêng cần dataset.

## Tái lập

```bash
# Sinh ảnh test (deterministic, không cần mạng)
python benchmarks/data/synthetic_ocr_vi/render.py

# Bench
python benchmarks/accuracy/bench_ocr.py \
    --backend tesseract \
    --json benchmarks/results/baseline_ocr_tesseract.json
```

## Tham khảo

- Tesseract 5: <https://github.com/tesseract-ocr/tesseract>
- `vie` traineddata (best): <https://github.com/tesseract-ocr/tessdata_best>
- EasyOCR: <https://github.com/JaidedAI/EasyOCR>
- TrOCR (Microsoft): <https://huggingface.co/microsoft/trocr-base-printed>

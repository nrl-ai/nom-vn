# Sửa chính tả (tiếng Việt)

Sửa lỗi gõ, dấu thiếu và lỗi ký tự kiểu OCR trên văn bản tiếng Việt
trong một bước: `Toi yu Vit Nam` → `Tôi yêu Việt Nam`. Đây là siêu tập
chặt của khôi phục dấu (chỉ thêm dấu thanh) — sửa chính tả còn xử lý
sai sót cấp ký tự, ký tự thiếu/thừa, và các thay thế kiểu OCR như
`o↔0`, `l↔1`, `m↔rn`.

## TL;DR — gợi ý của chúng tôi

```bash
pip install "nom-vn[diacritic-hf]"   # transformers<5 + torch + sentencepiece
```

```python
# Cùng seam Protocol với khôi phục dấu — truyền mô hình của chúng tôi
# vào fix_diacritics qua model=. (Sửa chính tả là siêu tập chặt của
# khôi phục dấu nên cùng Protocol này hoạt động.)
from nom.text import fix_diacritics
from nom.text.diacritic_models import HFDiacriticModel

restorer = HFDiacriticModel(model_id="nrl-ai/vn-spell-correction-base")
out = fix_diacritics("Hop dong nay duoc lap ngay 14/3/2025", model=restorer)
# 'Hợp đồng này được lập ngày 14/3/2025'
```

## Bức tranh công khai — đo ngày 2026-04-30

| Mô hình | Giấy phép | Format | light avg | heavy avg | Kết luận |
|---|---|---|---:|---:|---|
| [`bmd1905/vietnamese-correction-v2`](https://huggingface.co/bmd1905/vietnamese-correction-v2) | Apache 2.0 | safetensors | 86.7 % | 72.6 % | baseline tốt nhất chưa được fine-tune; mBART 400M |
| [`iAmHieu2012/vit5-vietnamese-spelling-correction`](https://huggingface.co/iAmHieu2012/vit5-vietnamese-spelling-correction) | MIT | safetensors | chưa đo | chưa đo | tokenizer cần convert slow→fast; tạm hoãn |
| [`chamdentimem/ViT5_Vietnamese_Correction`](https://huggingface.co/chamdentimem/ViT5_Vietnamese_Correction) | MIT | safetensors | chưa đo | chưa đo | tương tự iAmHieu, tạm hoãn |
| Quy tắc (không có nhánh sửa chính tả) | — | — | — | — | Nhánh chỉ-quy-tắc trong `nom.text.fix_diacritics` chỉ khôi phục dấu — không sửa cấp ký tự. |

Chi tiết bmd1905 trên 8 split:

| Register | light | heavy |
|---|---:|---:|
| business_55 | 91.18 % | 76.97 % |
| formal_72 | 83.46 % | 73.37 % |
| conversational_300 | 84.72 % | 73.63 % |
| literary_800 | 87.42 % | 66.53 % |

Tái lập: `python benchmarks/accuracy/bench_spell_correction_hf.py
bmd1905/vietnamese-correction-v2 --json benchmarks/results/baseline_spell_bmd1905_v2.json`.
JSON baseline cam kết tại `benchmarks/results/baseline_spell_bmd1905_v2.json`.

## Pipeline của chúng tôi

`nom.text.fix_diacritics` chấp nhận bất kỳ mô hình seq2seq nào qua
`model=`; mô hình sửa chính tả của chúng tôi cắm vào cùng Protocol đó.
`HFDiacriticModel` adapter sẽ lazy-load từ HF Hub.

```python
from nom.text.diacritic_models import HFDiacriticModel

# Mặc định sửa chính tả (sau publish)
spell = HFDiacriticModel(model_id="nrl-ai/vn-spell-correction-base")
spell("Toi yu Vit Nam, dat nuoc tuyet voi")     # 'Tôi yêu Việt Nam, đất nước tuyệt vời'

# Cùng đường suy luận batched cho throughput cao
spell.predict_batch(noisy_sentences, batch_size=16)
```

Cùng giao diện `predict()` / `predict_batch()` như mô hình diacritic.

## Mô hình đã huấn luyện — `nrl-ai/*`

Quy ước base + small tier từ diacritic được áp dụng nguyên: cùng corpus
huấn luyện 500K, cùng số epoch / LR / siêu tham số trên cả hai tier
(mô hình nhỏ KHÔNG ít cần dữ liệu hơn mô hình lớn — Chinchilla scaling
chỉ ra điều ngược lại, nên chúng tôi chủ động huấn luyện cả hai trên
cùng mix lớn).

| Mô hình HF | Giấy phép | Base | Tham số | Disk | Trạng thái |
|---|---|---|---:|---:|---|
| [`nrl-ai/vn-spell-correction-base`](https://huggingface.co/nrl-ai/vn-spell-correction-base) | Apache-2.0 | ViT5-base (MIT) | 220 M | 900 MB | đã ship (v0.2.28) |
| `nrl-ai/vn-spell-correction-small` | Apache-2.0 | BARTpho-syllable (MIT) | 115 M | 530 MB | đang huấn luyện |

### v0.2.28 base — đo trên lưới 8 split

| Split | Word acc | Sentence exact | ms/câu |
|---|---:|---:|---:|
| business_55_light | **98.58 %** | 79.55 % | 147 |
| business_55_heavy | **98.33 %** | 81.82 % | 145 |
| formal_72_light | **99.80 %** | 95.38 % | 288 |
| formal_72_heavy | **99.19 %** | 84.72 % | 274 |
| conversational_300_light | **97.90 %** | 83.24 % | 107 |
| conversational_300_heavy | **96.18 %** | 76.31 % | 103 |
| literary_800_light | **98.02 %** | 77.47 % | 171 |
| literary_800_heavy | **95.71 %** | 61.04 % | 160 |

**Light avg: 98.58 % · Heavy avg: 97.35 %** (cổng: light ≥ 92, heavy ≥ 80 — qua với khoảng cách rộng).

> **Lưu ý trung thực: các con số này là trong-phân-phối.** Lưới đánh
> giá áp cùng các preset `nom.text.noise` lên văn bản sạch mà mô hình
> đã được huấn luyện trên đó (seed khác nhau, cùng generator). Mô hình
> đã ngầm học cách đảo ngược phân phối nhiễu *của chúng tôi*. Lỗi gõ
> tiếng Việt thực tế tuân theo thống kê khác — xem phần đo OOD bên dưới.

### Bench thực tế ngoài-phân-phối (mở rộng, đo ngày 2026-04-30)

`benchmarks/data/spell_correction_eval_real/` là tập **150 câu** được
hand-curate mà mẫu nhiễu lấy từ nguồn lỗi VN thực tế, KHÔNG phải
`nom.text.noise`. Mở rộng từ 4 register lên **6 register** (thêm
`legal_real_25` và `news_real_25`) để có gradient ổn định hơn. Mọi
con số đi kèm khoảng tin cậy bootstrap 95 % (n=1000 resample).

| Slice | Nguồn | spell-correction-base | spell-correction-small | diacritic-vit5-base |
|---|---|---:|---:|---:|
| `forum_25` | Forum / teen-code | 59.45 [45.21-72.01] | 58.73 [44.57-71.28] | 49.31 [37.33-60.45] |
| `mobile_25` | Autocorrect điện thoại | 95.01 [92.98-96.76] | 95.01 [93.18-96.71] | 79.66 [71.59-86.65] |
| `telex_real_25` | Telex/VNI thực | **17.38** [12.20-22.60] | 9.51 [5.28-14.08] | 14.89 [11.73-17.98] |
| `ocr_25` | Tesseract / EasyOCR | 93.62 [89.30-97.27] | 91.16 [86.89-94.74] | 94.53 [90.36-98.14] |
| `legal_real_25` | Văn bản pháp lý thật | **95.09** [91.41-98.19] | 93.56 [89.97-96.46] | 88.05 [80.25-93.92] |
| `news_real_25` | Tiêu đề + tin tức | 96.54 [94.50-98.50] | 91.58 [82.13-97.72] | 95.80 [93.69-98.01] |
| **Tổng hợp** | n=150 | **77.43** [72.57-82.28] | 75.92 [70.60-81.01] | 71.50 [66.49-76.54] |

Tất cả số là word accuracy (%). JSON nguồn:
[base](https://github.com/nrl-ai/nom-vn/blob/main/benchmarks/results/baseline_real_spell_correction_base.json) /
[small](https://github.com/nrl-ai/nom-vn/blob/main/benchmarks/results/baseline_real_spell_correction_small.json) /
[diacritic-vit5-base](https://github.com/nrl-ai/nom-vn/blob/main/benchmarks/results/baseline_real_diacritic_vit5_base.json).

#### Phân tích kiểu lỗi (n=150, tổng hợp)

| Mô hình | missed_diac | wrong_tone | base_char | extra | missing | correct |
|---|---:|---:|---:|---:|---:|---:|
| spell-correction-base | 12 | 63 | 416 | 6 | 15 | 1684 |
| spell-correction-small | 9 | 71 | 432 | 0 | 64 | 1614 |
| diacritic-vit5-base | 7 | 61 | 549 | 2 | 25 | 1548 |

`base_char` (sai gốc chữ — chọn nhầm từ) là loại lỗi chiếm chủ đạo,
đặc biệt với teen-code + Telex. Đây cũng là điều `comprehensive_noise()`
trong corpus v2 nhắm đến.

#### Quan sát chính

1. **Khoảng cách synthetic vs OOD vẫn lớn** — `vn-spell-correction-base`
   đạt 98.58 % light avg trên lưới synthetic 8-split rớt xuống 77.43 %
   tổng hợp OOD. Trên 6 register: legal + news + mobile gần ngưỡng
   in-distribution (88-96 %), forum + telex là điểm yếu nghiêm trọng
   (17-59 %).
2. **spell-base vs spell-small ngang nhau trên tổng hợp** (77.43 vs
   75.92, KTC 95 % chồng nhau). Khác biệt rõ là **spell-small drop
   trên Telex** (-7.87 pp) và mất nhiều token hơn (`missing_word`
   = 64 vs 15 — BARTpho hay bỏ token cuối câu).
3. **Sửa chính tả vẫn thắng diacritic-only** trên 5/6 slice. Khoảng
   cách +5.93 pp tổng hợp (77.43 vs 71.50) — mô hình spell sửa được
   lỗi cấp ký tự mà mô hình diacritic không làm được.
4. **Telex là điểm yếu chung** — 9-17 % trên cả ba mô hình. Đây
   chính là gap mà corpus v2 + `comprehensive_noise()` đang khắc phục
   (thêm `telex_grammar_noise()` cho lỗi keystroke thực + `mobile_noise()`
   cho teen-code + lỗi phím gần). v0.2.29 retrain đang chạy chuỗi
   spell-base → spell-small → diacritic-base trên corpus v2.

Tái lập:
```bash
python benchmarks/accuracy/bench_spell_correction_real.py \
    nrl-ai/vn-spell-correction-base \
    --json benchmarks/results/baseline_real_spell_correction_base.json
```

Khoảng tin cậy ±5-10 pp ở 95 % cho từng slice 25 câu, ±5 pp cho tổng
hợp 150 câu — đủ phân biệt mô hình spell-correction vs diacritic-only,
chưa đủ phân biệt base vs small trên tổng hợp.

Re-eval cục bộ tái lập remote trong ±0.03 pp trên mọi split. Huấn luyện
trên [cùng corpus 500K mixed Wiki+news](https://huggingface.co/datasets/nrl-ai/vn-spell-correction-train)
với `light_noise` / `telex_typo_noise` / `heavy_noise` áp round-robin.
5 epoch cosine LR. 180 phút trên một RTX 3090.

### Δ so với bức tranh công khai (light_avg / heavy_avg)

| Mô hình | light avg | heavy avg | Δ vs base của chúng tôi |
|---|---:|---:|---:|
| **`nrl-ai/vn-spell-correction-base`** (chúng tôi) | **98.58 %** | **97.35 %** | — |
| `bmd1905/vietnamese-correction-v2` (400 M) | 86.95 % | 72.62 % | **-11.6 / -24.7** pp |
| `iAmHieu2012/vit5-vietnamese-spelling-correction` (220 M) | 80.31 % | 56.55 % | **-18.3 / -40.8** pp |

Bản base của chúng tôi thắng mọi split 7-29 pp. Lợi thế kích thước của
bmd1905 (400M vs 220M của chúng tôi) không đáng kể — fine-tune có
chủ đích trên phân phối nhiễu 8-register lấn át mô hình correction
chung chung.

## Bộ dữ liệu — `nrl-ai/*` (đang xếp hàng publish)

Bộ dữ liệu huấn luyện và đánh giá sẽ được publish khi cả hai tier ship
xong, theo cùng quy ước với bộ dữ liệu diacritic:

- `nrl-ai/vn-spell-correction-eval` — 2.098 cặp (noisy, clean) trên
  4 register × 2 mức nhiễu (light + heavy). Sinh tất định từ các slice
  eval diacritic qua `nom.text.noise`.
- `nrl-ai/vn-spell-correction-train` — 459K cặp huấn luyện
  (noisy, clean). Phía clean cùng là 500K mixed Wiki+news như
  `nrl-ai/vn-diacritic-train`; phía noisy đến từ round-robin của các
  preset `light_noise` / `telex_typo_noise` / `heavy_noise`.

## Kết quả — đã đo

Đang chờ. Sẽ điền khi huấn luyện hoàn tất. Đường dẫn JSON baseline:
`training/spell_correction/results/<run-id>_summary.json`.

## Tái lập

```bash
# 1. Build lưới eval (tất định, không cần mạng)
python benchmarks/data/spell_correction_eval/build.py

# 2. Build corpus huấn luyện (dùng nom.text.noise trên corpus diacritic
#    500K mixed sẵn có)
python training/spell_correction/prep_data.py --max-pairs 500_000

# 3. Bench bất kỳ mô hình HF spell-correction sẵn có nào
python benchmarks/accuracy/bench_spell_correction_hf.py \
    bmd1905/vietnamese-correction-v2 \
    --json benchmarks/results/baseline_spell_bmd1905_v2.json

# 4. Huấn luyện base trên GPU remote (TRAIN_HOST trỏ đến host GPU của bạn)
./training/spell_correction/launch_remote_train.sh \
    --model-id VietAI/vit5-base \
    --epochs 5 --batch-size 32 --bf16 \
    --lr 5e-4 --lr-scheduler cosine \
    --warmup-steps 500 --early-stopping-patience 0 \
    --eval-steps 2000 --save-steps 2000 --eval-samples 1000 \
    --output-dir training/spell_correction/checkpoints/vit5-base-500k

# 5. Huấn luyện small trên cùng corpus
./training/spell_correction/launch_remote_train.sh \
    --model-id vinai/bartpho-syllable-base \
    --epochs 5 --batch-size 32 --bf16 \
    --lr 5e-4 --lr-scheduler cosine \
    --warmup-steps 500 --early-stopping-patience 0 \
    --eval-steps 2000 --save-steps 2000 --eval-samples 1000 \
    --output-dir training/spell_correction/checkpoints/bartpho-syllable-500k
```

## Bộ sinh nhiễu hoạt động ra sao

Sửa chính tả cần các cặp `(noisy, clean)` để huấn luyện. Các cặp
license-clean ngoài đời thực hiếm (đa số corpus công khai chỉ phục vụ
nghiên cứu). Chúng tôi tổng hợp từ văn bản sạch dùng `nom.text.noise`
(ship cùng `nom-vn`):

```python
from nom.text.noise import NoiseGenerator, light_noise

gen = NoiseGenerator(light_noise(), seed=42)
print(gen.noisify("Tôi yêu Việt Nam và đất nước này tuyệt vời."))
# 'Toi yêu Viet Nam và đất nước này tuyệt vời.'
```

Mười chiều nhiễu và bảy preset đã hiệu chỉnh:

| Preset | Mô phỏng |
|---|---|
| `light_noise()` | Gõ desktop bình thường; ~5 % edit distance. |
| `heavy_noise()` | OCR chất lượng trung bình; ~15-20 % edit distance. |
| `telex_typo_noise()` | Hiệu ứng bề mặt của lỗi gõ Telex/VNI. |
| `telex_grammar_noise()` | Lỗi keystroke Telex thực (rớt / sai / lặp ký tự thanh). |
| `mobile_noise()` | Gõ ngón cái trên điện thoại: lỗi phím gần + viết tắt teen-code + phân đoạn sai. |
| `ocr_realistic_noise()` | OCR tài liệu scan: mất dấu nặng + nhầm ký tự + phân đoạn sai. |
| `comprehensive_noise()` | Cả mười chiều ở xác suất vừa phải. Dùng làm mặc định cho corpus v2 nơi mô hình cần tổng quát hoá qua nhiều lớp lỗi gõ. |

Tất định qua seed; output NFC-normalize (cạm bẫy NFD đã đầu độc một
run mixed-source diacritic trước đó được khoá ở mọi tầng); ngân sách
edit có giới hạn để các config xác suất cao không huỷ hoại input quá
mức không thể phục hồi. Xem
[`docs/recipes.md`](../recipes.md#synthesize-noisy-vietnamese-text-for-spell-correction-training-data)
để có recipe đầy đủ.

### Corpus huấn luyện đa nguồn v2 (xếp hàng cho v0.2.29)

Corpus v1 chỉ kéo từ Wiki + news; corpus v2
(`training/spell_correction/prep_data_v2.py`) thêm slice register pháp
lý từ `GreenNode/zalo-ai-legal-text-retrieval-vn` (MIT) và áp toàn bộ
bảy preset qua round-robin cộng thêm slot `comprehensive_noise`. Mix
mặc định 600K cặp:

| Slot | Nguồn | Hạn ngạch | Nhiễu |
|---|---|---:|---|
| mixed | Wiki+news (v1 base, NFC) | 65 % | round-robin trên 6 preset |
| legal | Zalo Legal QA corpus, MIT | 25 % | round-robin trên 6 preset |
| comprehensive_only | Wiki+news (NFC) | 10 % | luôn là `comprehensive_noise` |

Việc này mở rộng phạm vi register (tiếng Việt pháp lý có vốn từ vựng
khác mà corpus v1 còn thiếu) và huấn luyện mô hình trên nhiều mode
lỗi hơn mỗi cặp. Chạy lại qua:

```bash
# 1. Build corpus pháp lý (~1 phút stream từ HF, 100K cặp)
python training/diacritic/prep_data_legal.py --max-pairs 100_000
cp training/diacritic/data/train_legal.jsonl \
   training/diacritic/data/train_legal_nfc.jsonl

# 2. Build corpus sửa chính tả v2
python training/spell_correction/prep_data_v2.py --max-pairs 600_000
```

## Tham khảo

- Bài báo VSEC (benchmark + taxonomy lỗi sửa chính tả VN kinh điển):
  Do et al., PRICAI 2021, <https://arxiv.org/abs/2111.00640>
- Bài báo BARTpho: Tran et al., INTERSPEECH 2022,
  <https://aclanthology.org/2022.interspeech-1.45/>
- Bài báo ViT5: Phan et al., NAACL-SRW 2022,
  <https://aclanthology.org/2022.naacl-srw.18>
- Model card bmd1905: <https://huggingface.co/bmd1905/vietnamese-correction-v2>

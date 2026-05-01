# Khôi phục dấu (tiếng Việt)

Khôi phục dấu thanh và biến điệu nguyên âm trên văn bản tiếng Việt được
viết không dấu: `Toi yeu Viet Nam` → `Tôi yêu Việt Nam`. Đây là bước
tiền xử lý phổ biến nhất trên văn bản tiếng Việt nhiễu — kết quả OCR,
gõ từ bàn phím nước ngoài, viết tắt mạng xã hội, chuỗi Telex chưa gõ.

## TL;DR — gợi ý của chúng tôi

```bash
pip install "nom-vn[diacritic-hf]"   # transformers<5 + torch + sentencepiece
```

```python
from nom.text.diacritic_models import HFDiacriticModel
restorer = HFDiacriticModel()  # mặc định Toshiiiii1, lazy-load lần gọi đầu
restorer("Toi yeu Viet Nam")    # 'Tôi yêu Việt Nam'

# Theo lô (nhanh hơn 7.6× trên 3080)
restorer.predict_batch(sentences, batch_size=16)
```

Mô hình mặc định là [`Toshiiiii1/Vietnamese_diacritics_restoration_5th`](https://huggingface.co/Toshiiiii1/Vietnamese_diacritics_restoration_5th)
(Apache 2.0, T5 200 M, safetensors) — SOTA công khai trên ma trận 4
register. Với corpora thiên về tiếng Việt formal / pháp lý / hội thoại,
mô hình của chúng tôi [`nrl-ai/vn-diacritic-vit5-base`](https://huggingface.co/nrl-ai/vn-diacritic-vit5-base)
hơn +1.29 pp trên formal / +0.18 pp trên hội thoại với cùng kích thước
và giấy phép.

## Bức tranh công khai — đo ngày 2026-04-30

| Mô hình | Giấy phép | Format | business 55 | literary 800 | conv 300 | formal 72 | Kết luận |
|---|---|---|---:|---:|---:|---:|---|
| [`Toshiiiii1/Vietnamese_diacritics_restoration_5th`](https://huggingface.co/Toshiiiii1/Vietnamese_diacritics_restoration_5th) | Apache 2.0 | safetensors | **97.81 %** | **89.40 %** | 93.94 % | 98.14 % | ⭐ SOTA công khai, mặc định hiện tại |
| **[`nrl-ai/vn-diacritic-vit5-base`](https://huggingface.co/nrl-ai/vn-diacritic-vit5-base)** (chúng tôi) | Apache 2.0 | safetensors | 94.98 % | 90.24 % | **94.12 %** | **99.43 %** | cân bằng register tốt nhất; chọn cho pháp lý / hội thoại |
| `qthuan2604/ViT5_Restore_Diacritics_Vietnamese` | MIT | bin | 90.59 % | — | — | — | yếu hơn của chúng tôi; bỏ qua |
| `qthuan2604/BARTPho_Syllable_Restore_Diacritics_Vietnamese` | MIT | safetensors | 83.92 % | — | — | — | yếu nhất trong số đã audit; bỏ qua |
| `yammdd/vietnamese-diacritic-restoration-v2` | MIT | tf_model.h5 | chưa đo | — | — | — | chỉ TF; chi phí chuyển đổi cao, để sau |
| Bảng quy tắc (`nom.text.fix_diacritics`) | Apache 2.0 | none | 41.06 % | — | — | — | dự phòng zero-deps |
| LLM cục bộ (`gemma3:4b` Q4 qua Ollama) | Apache 2.0 | gguf | — | — | — | — | 87.90 % trên `diacritic_eval_v0` mixed; ~1 s/câu |
| LLM đám mây (`gpt-4o-mini`) | proprietary | — | 95.37 % | — | — | — | thắng về chi phí chỉ khi batch nhỏ |

Khoảng cách 8.7 pp giữa các register trên Toshiiiii1 xác nhận mô hình
này over-fit về tiếng Việt formal/business hiện đại. Bản fine-tune
`vit5-base` của chúng tôi đánh đổi 4 pp business để được +1.4 pp formal
và ngang điểm literary — lựa chọn đúng cho corpora pháp lý / chat / OCR.

JSON baseline: `benchmarks/results/baseline_diacritic_*.json`.

## Pipeline của chúng tôi

`nom.text.fix_diacritics` là một seam dạng Protocol: bất kỳ callable
nào ánh xạ `str -> str` đều cắm vào được.

```python
from nom.text import fix_diacritics
from nom.text.diacritic_models import HFDiacriticModel

# Mặc định Toshiiiii1
fix_diacritics("Hop dong nay duoc lap", model=HFDiacriticModel())

# Bản fine-tune cân bằng register của chúng tôi
fix_diacritics(
    "Hop dong nay duoc lap",
    model=HFDiacriticModel(model_id="nrl-ai/vn-diacritic-vit5-base"),
)

# Hoặc qua Ollama LLM
from nom.llm import Ollama
fix_diacritics("Hop dong nay duoc lap", llm=Ollama(model="gemma3:4b"))

# Hoặc dự phòng quy tắc zero-deps (chỉ best-effort)
fix_diacritics("Hop dong nay duoc lap")
```

`HFDiacriticModel` cung cấp `predict()` (1 câu) và `predict_batch()`
(suy luận batched có pad, **throughput 7.60×**, đo trên 3080 16 GB
Mobile, 120/120 chất lượng tương đương đường gọi đơn).

## Mô hình đã huấn luyện — `nrl-ai/*`

| Mô hình HF | Giấy phép | Base | Tham số | Disk | Latency (3080) | Khi nào chọn |
|---|---|---|---:|---:|---:|---|
| [`nrl-ai/vn-diacritic-vit5-base`](https://huggingface.co/nrl-ai/vn-diacritic-vit5-base) | Apache-2.0 | ViT5-base (MIT) | 220 M | 900 MB | 100-272 ms/câu | base tier — chất lượng cân bằng register tốt nhất |
| [`nrl-ai/vn-diacritic-small`](https://huggingface.co/nrl-ai/vn-diacritic-small) | Apache-2.0 | BARTpho-syllable (MIT) | 115 M | 530 MB | 38-94 ms/câu | fast tier — nhanh 2.2×, chi phí ~3-4 pp chất lượng trung bình |

Cả hai cùng huấn luyện trên **một corpus 500K mixed Wiki+news** trong
5 epoch cosine LR (mô hình nhỏ huấn luyện trên corpus lớn tổng quát hoá
tốt hơn; cắt dữ liệu huấn luyện cho fast tier là cạm bẫy phổ biến mà
chúng tôi chủ ý tránh).

**Δ so với Toshiiiii1 (SOTA công khai chúng tôi đối chiếu):**

| Register | Toshiiiii1 | base (chúng tôi) | Δ vs Toshi | small (chúng tôi) | Δ vs Toshi |
|---|---:|---:|---:|---:|---:|
| `formal_udhr` | 98.14 % | **99.43 %** | **+1.29 pp** | 91.51 % | -6.63 pp |
| `business_55` | **97.81 %** | 94.98 % | -2.83 pp | 94.44 % | -3.37 pp |
| `conversational_300` | 93.94 % | **94.12 %** | **+0.18 pp** | 90.68 % | -3.26 pp |
| `literary_udvtb` | **89.40 %** | 90.24 % | +0.84 pp | 86.33 % | -3.07 pp |

Bản base thắng 3/4 register so với Toshiiiii1 và hoà ở ngưỡng cổng
chính; cổng nghiêm ngặt cho business (≥ 96 %) vẫn fail 1.02 pp, nên
chưa bản nào nhận tên canonical `nrl-ai/vn-diacritic-restoration` —
cả hai đều xuất xưởng dưới tên mô tả arch. Chọn base tier khi chất
lượng quan trọng nhất; chọn small tier khi latency hoặc VRAM là ràng
buộc và mức rớt ~3-4 pp trung bình chấp nhận được.

**Tier kế hoạch tiếp theo:**

| Tier | Base | Trạng thái |
|---|---|---|
| `nrl-ai/vn-diacritic-nano` | distilled (10-30 M) | tương lai — distillation từ teacher base, đích <50 ms inference CPU |

## Bộ dữ liệu — `nrl-ai/*`

Cả hai đã verify render được + load được qua `datasets.load_dataset`.

| Bộ dữ liệu HF | Giấy phép | Là gì |
|---|---|---|
| [`nrl-ai/vn-diacritic-eval`](https://huggingface.co/datasets/nrl-ai/vn-diacritic-eval) | CC-BY-SA-4.0 (chặt nhất trong các thành phần) | Lưới đánh giá 4 register: business_55 (CC0), formal_72 (PD UDHR), conversational_300 (CC-BY 2.0 Tatoeba), literary_800 (CC-BY-SA 4.0 UD-VTB). Tổng 1.227 cặp câu. |
| [`nrl-ai/vn-diacritic-train`](https://huggingface.co/datasets/nrl-ai/vn-diacritic-train) | CC-BY-SA-4.0 (per-config: `wiki_500k`=CC-BY-SA, `news_150k`=CC-BY-4.0) | 500K cặp Wikipedia + 150K cặp tin tức VN đã sửa NFC. Đã chống rò rỉ với `vn-diacritic-eval`. NFC-normalize tại lúc ghi. |

```python
from datasets import load_dataset

# Đánh giá bất kỳ mô hình nào trên cùng lưới 4 register
ds = load_dataset("nrl-ai/vn-diacritic-eval", "business_55", split="train")

# Tự huấn luyện — cùng dữ liệu chúng tôi dùng cho nrl-ai/vn-diacritic-vit5-base
wiki = load_dataset("nrl-ai/vn-diacritic-train", "wiki_500k", split="train")
news = load_dataset("nrl-ai/vn-diacritic-train", "news_150k", split="train")
```

## Kết quả — đã đo

Mọi con số đều tái lập được trên một bản clone sạch qua các script
bench dưới `benchmarks/accuracy/` và `training/diacritic/eval_checkpoint.py`.
Đo trên RTX 3080 16 GB Mobile / RTX 3090, có NFC + chuẩn hoá dấu câu
ở cả hai phía, warmup 3 lần, num_beams=1.

| Register | Số câu | Toshiiiii1 (ms/câu) | nrl-ai/vit5-base (ms/câu) |
|---|---:|---:|---:|
| `formal_udhr` | 72 | 245 | 272 |
| `business_55` | 55 | 119 | 147 |
| `conversational_300` | 300 | 91 | 101 |
| `literary_udvtb` | 800 | 137 | 156 |

Latency bị decoder ViT5 220 M chi phối; cả hai mô hình cùng họ arch.
Để được 7.6× throughput trên cả hai, dùng `predict_batch`.

### Bench thực tế ngoài-phân-phối (OOD, đo ngày 2026-05-01 sau v0.2.29)

`benchmarks/data/spell_correction_eval_real/` là tập 150 câu hand-curate
mà nhiễu lấy từ nguồn lỗi VN thực tế (forum / mobile / Telex thật / OCR
engine / pháp lý / tin tức) — KHÔNG phải `nom.text.noise`. Cùng eval
áp dụng cho cả khôi phục dấu và sửa chính tả vì sửa chính tả là siêu
tập của khôi phục dấu.

Cả hai tier khôi phục dấu của chúng tôi vs Toshiiiii1 trên OOD:

| Slice | `vit5-base` v0.2.29 | `vit5-base` v0.2.28 | `small` v0.2.28 | Toshiiiii1 |
|---|---:|---:|---:|---:|
| `forum_25` | 43.54 | 49.31 | 46.28 | **60.11** |
| `mobile_25` | 76.99 | 79.66 | 81.51 | **96.95** |
| `telex_real_25` | 14.37 | 14.89 | 9.33 | **18.54** |
| `ocr_25` | **94.83** | 94.53 | 93.29 | 94.22 |
| `legal_real_25` | **93.02** | 88.05 | 89.15 | 93.80 |
| `news_real_25` | **96.05** | 95.80 | 90.35 | 94.07 |
| **Tổng hợp** (n=150) | 71.15 [66-76] | 71.50 [66-77] | 70.27 [65-76] | **77.40** [73-82] |

**Phát hiện chính sau v0.2.29 retrain** (Wiki+news+legal corpus):

1. **Văn bản formal/legal cải thiện rõ.** legal_real_25: 88.05 → 93.02
   (+4.97 pp), news +0.25, OCR +0.30. Đây là chính cái mục tiêu của
   việc thêm 100K cặp legal vào corpus: phủ thêm vocab pháp lý.
2. **Văn bản informal regress.** forum_25: 49.31 → 43.54 (-5.77 pp),
   mobile -2.67. Lý do: mô hình diacritic-only chỉ thấy cặp `(stripped,
   clean)`, nên thêm corpus legal đẩy phân phối nghiêng về formal —
   informal vì thế hơi tệ đi.
3. **Tổng hợp -0.35 pp** (71.50 → 71.15) vì regression informal lớn
   hơn improvement formal trong tỷ lệ slice. Nhưng đây là trade-off
   đúng cho use case thực tế.

**Hệ quả thực tế** (cập nhật sau v0.2.29):

- *Văn bản formal đã strip-dấu* (legal docs, news, OCR text-only): dùng
  `vn-diacritic-vit5-base` v0.2.29. Tốt hơn v0.2.28 trên các slice này.
- *Nhiễu thực tế hỗn hợp* (OCR + người gõ tay + social): dùng
  `vn-spell-correction-base` (siêu tập). Aggregate 79.62 % vs diacritic-only
  71.15 % — chênh lệch +8.47 pp, vượt cả Toshiiiii1.
- *Toshiiiii1 vẫn dẫn đầu trên informal* (forum / mobile / telex slices)
  cho mục đích diacritic-only thuần. Sự lựa chọn giữa Toshiiiii1 và
  vn-diacritic-vit5-base là register-dependent.

JSON nguồn:
[diacritic-vit5-base](https://github.com/nrl-ai/nom-vn/blob/main/benchmarks/results/baseline_real_diacritic_vit5_base.json) /
[diacritic-small](https://github.com/nrl-ai/nom-vn/blob/main/benchmarks/results/baseline_real_diacritic_small.json) /
[Toshiiiii1](https://github.com/nrl-ai/nom-vn/blob/main/benchmarks/results/baseline_real_toshiiiii1.json).

JSON baseline:

- `benchmarks/results/baseline_diacritic_toshiiiii_4register.json` (Toshiiiii1)
- `benchmarks/results/baseline_diacritic_toshiiiii_t5.json`, `..._tatoeba300.json`, `..._udhr72.json`, `..._udvtb_test.json` (per-register)
- `training/diacritic/results/vit5-base-500k-cosine-full_summary.json` (fine-tune của chúng tôi)
- `training/diacritic/results/vit5-base-500k-cosine-full_eval_local.json` (re-eval local, ±0.12 pp tái lập được)
- `benchmarks/results/baseline_diacritic_qthuan_*.json` (các ứng viên đã audit)

## Tái lập

```bash
# 1. Build các slice eval (tất định, không cần mạng)
python benchmarks/data/tatoeba_vi/build_diacritic_eval.py
python benchmarks/data/udhr_vi/build_diacritic_eval.py

# 2. Chạy eval 4 register cho bất kỳ mô hình HF nào
python training/diacritic/eval_checkpoint.py \
    --checkpoint Toshiiiii1/Vietnamese_diacritics_restoration_5th \
    --output-json benchmarks/results/baseline_diacritic_toshiiiii_4register.json

python training/diacritic/eval_checkpoint.py \
    --checkpoint nrl-ai/vn-diacritic-vit5-base \
    --output-json benchmarks/results/baseline_diacritic_vit5_base_4register.json
```

## Huấn luyện

Pipeline huấn luyện đầy đủ ở [`training/diacritic/`](../../training/diacritic/):

- `prep_data.py` — Wikipedia stream → các cặp (input, target) đã lọc (NFC, chống rò eval).
- `prep_data_news.py` — tương tự cho `tmnam20/Vietnamese-News-dedup` (CC-BY-4.0, đã sửa NFC).
- `train.py` — HF `Seq2SeqTrainer` cosine LR, early stopping tuỳ chọn, eval 4 register hậu huấn luyện.
- `eval_checkpoint.py` — re-eval độc lập từ một checkpoint dir hoặc HF repo id.
- `publish_hf.py` — publish HF Hub có gate-check + tự sinh model card.
- `post_train.sh` — rsync từ host GPU → re-eval local (lệch >0.5 pp là fail) → publish chạy thử.

Lịch sử thí nghiệm (đến nay 5 lượt) ở [`training/diacritic/README.md`](../../training/diacritic/README.md).

## Cạm bẫy đặc thù tiếng Việt gặp trong quá trình này

- **NFC vs NFD.** `tmnam20/Vietnamese-News-dedup` ship ~79 % văn bản
  decompose NFD. Một lần huấn luyện mixed-source trước đó đã train trên
  đó; mô hình emit ký tự kết hợp decompose mà eval byte-compare NFC bỏ
  sót → **regression thảm khốc -15.45 pp** trên register business. Hiện
  đã NFC-normalize tại 3 tầng (prep, prep-news, train preprocess).
- **Early stopping trên eval nhỏ nhiễu.** `--early-stopping-patience 3`
  với eval 200 mẫu fire ở epoch 0.96 của v3 — mô hình chưa kịp hội tụ.
  Hiện mặc định `--eval-samples 1000` và khuyến nghị
  `--early-stopping-patience 0` cho các run huấn luyện full-budget.
- **Chuẩn hoá dấu câu để khớp byte câu nguyên.** UD-VTB ship câu có
  khoảng trắng quanh từng dấu (quy ước treebank); đầu ra seq2seq hiện
  đại có dấu dính liền. Bench script nay `normalize_punct()` cả hai
  phía trước so sánh — đã bắt được lỗi "0/800 sentence-exact" giả ở
  v0.2.17.
- **Đa nghĩa danh từ riêng.** `Hung` → `Hùng` / `Hưng` / `Hứng`
  (các tên thật khác nhau). Mô hình chọn theo tần số huấn luyện;
  không phải lúc nào cũng đúng cho input. Cần tài liệu hoá NER+lookup
  riêng cho các use case đòi hỏi danh từ riêng đúng.

## Tham khảo

- Model card Toshiiiii1: <https://huggingface.co/Toshiiiii1/Vietnamese_diacritics_restoration_5th>
- Bản fine-tune của chúng tôi: <https://huggingface.co/nrl-ai/vn-diacritic-vit5-base>
- Bài báo ViT5: Phan et al., NAACL-SRW 2022, <https://aclanthology.org/2022.naacl-srw.18>
- ByT5 (SOTA char-level VN diacritic kinh điển): Xue et al., 2022, <https://arxiv.org/abs/2201.13242>
- Corpus huấn luyện Wikipedia: <https://huggingface.co/datasets/hirine/wikipedia-vietnamese-1M296K-dataset>
- Corpus huấn luyện tin tức: <https://huggingface.co/datasets/tmnam20/Vietnamese-News-dedup>
- Bài VSEC (taxonomy lỗi `nom.text.noise` dùng): Do et al., PRICAI'21, <https://arxiv.org/abs/2111.00640>

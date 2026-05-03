# Recipes — cookbook task-oriented `nom-vn`

*Cập nhật lần cuối: 2026-04-26.*

Mỗi recipe là một mục tự đứng "tôi muốn X, làm Y". Code mẫu copy-paste
sạch từ một cài đặt `nom-vn` mới. Mọi khuyến nghị đều trỏ tới hàng
trong [`docs/benchmark.md`](benchmark.md) đã đo — không recipe nào
giới thiệu lựa chọn chưa đo.

Thứ tự recipe theo trình tự áp dụng điển hình: tiện ích văn bản →
bóc tách tài liệu → tra cứu → RAG → chat. Bỏ qua phần không cần.

---

## Recipe text

### Khôi phục dấu tiếng Việt

Bước tiền xử lý phổ biến nhất trên text VN nhiễu (output OCR, bàn phím
nước ngoài, viết tắt mạng xã hội). Ba backend, chọn theo ngân sách
độ chính xác vs surface dependency:

#### Best accuracy (97.81 % word acc, 1 GB disk, ~150 ms GPU / ~360 ms CPU)

```bash
pip install "nom-vn[diacritic-hf]"   # transformers<5 + torch + sentencepiece
```

```python
from nom.text import fix_diacritics
from nom.text.diacritic_models import HFDiacriticModel

restorer = HFDiacriticModel(device="cuda")  # auto-fallback "cpu"
out = fix_diacritics("Hop dong nay duoc lap ngay 14/3/2025", model=restorer)
# → 'Hợp đồng nay được lập ngày 14/3/2025'
```

Mô hình mặc định là [`nrl-ai/vn-diacritic-vit5-base`](https://huggingface.co/nrl-ai/vn-diacritic-vit5-base)
(ViT5-base 220 M, Apache 2.0). Truyền
`model_id="nrl-ai/vn-diacritic-small"` cho tier latency thấp hơn
(115 M, ~3× nhanh hơn, đánh đổi ~3-4 pp word-acc), hoặc
`model_id="nrl-ai/vn-spell-correction-base"` để có siêu tập chặt
sửa luôn lỗi cấp ký tự và lỗi OCR.

**Coverage register** (ma trận 4 register, đo 2026-04-29 — xem
[`docs/benchmark.md`](benchmark.md) cho bảng đầy đủ):

| Register | Word acc |
|---|---:|
| Hành chính / pháp lý (UDHR) | 98.14 % |
| Kinh doanh / tin tức | 97.81 % |
| Hội thoại (Tatoeba) | 93.94 % |
| Văn học cổ điển (UD-VTB) | 89.40 % |

Spread 8.7 pp, gradient đơn điệu. Mô hình register-overfit về tiếng
Việt formal/business hiện đại (khớp dữ liệu training) nhưng vẫn dùng
được mọi nơi. Lỗi trên văn học chủ yếu là mơ hồ danh từ riêng
(`Hùng` ↔ `Hưng` ↔ `Hứng`) và từ register thiểu số.

#### Đường siêu tập — `nrl-ai/vn-spell-correction-base` (mặc định khuyến nghị)

Nếu input có thể có lỗi cấp ký tự (OCR, người gõ tay, social media,
form data) — không chỉ thiếu dấu — dùng mô hình sửa chính tả thay vì:

```python
from nom.text.diacritic_models import HFDiacriticModel
restorer = HFDiacriticModel(model_id="nrl-ai/vn-spell-correction-base")
restorer("Toi yu Vit Nam, dat nuoc tuyet voi")
# 'Tôi yêu Việt Nam, đất nước tuyệt vời'
```

Là siêu tập chặt của khôi phục dấu (cùng API), nhưng cộng thêm khả năng
vá lỗi ký tự, OCR, gõ Telex, viết tắt teen-code. Trên OOD 150-câu thực
tế: **79.62 %** word accuracy aggregate — vượt Toshiiiii1 (77.40 %) +2.22 pp,
vượt diacritic-only của chúng tôi +8.47 pp.

#### Tier nhanh / quantize edge

| Tier | Repo | Disk | OOD aggregate | Khi nào chọn |
|---|---|---:|---:|---|
| Base PyTorch | `nrl-ai/vn-spell-correction-base` | 900 MB | **79.62 %** | mặc định, có GPU + PyTorch |
| Small PyTorch | `nrl-ai/vn-spell-correction-small` | 530 MB | 77.55 % | latency quan trọng, vẫn có PyTorch |
| **Base ONNX int8** | [`nrl-ai/vn-spell-correction-base-onnx-int8`](https://huggingface.co/nrl-ai/vn-spell-correction-base-onnx-int8) | 438 MB | 78.76 % | CPU-only server, không phụ thuộc PyTorch |
| **Small ONNX int8** | [`nrl-ai/vn-spell-correction-small-onnx-int8`](https://huggingface.co/nrl-ai/vn-spell-correction-small-onnx-int8) | 307 MB | 77.30 % | edge / browser / mobile |

```bash
pip install optimum[onnxruntime]
```

```python
from optimum.onnxruntime import ORTModelForSeq2SeqLM
from transformers import AutoTokenizer

tok = AutoTokenizer.from_pretrained("nrl-ai/vn-spell-correction-small-onnx-int8")
model = ORTModelForSeq2SeqLM.from_pretrained("nrl-ai/vn-spell-correction-small-onnx-int8")
```

Cả 4 tier đều thắng Toshiiiii1 (77.40 %) trên OOD aggregate.

#### Diacritic-only — `nrl-ai/vn-diacritic-vit5-base`

Nếu input thuần ASCII đã strip dấu (legal docs / form / pipe ASCII cũ),
mô hình diacritic-only nhỏ gọn hơn:

| Register (in-distribution) | Word acc |
|---|---:|
| Hành chính / pháp lý (UDHR) | **99.52 %** |
| Kinh doanh / tin tức | 96.14 % |
| Hội thoại | 94.16 % |
| Văn học cổ điển | 89.97 % |

```python
restorer = HFDiacriticModel(model_id="nrl-ai/vn-diacritic-vit5-base")
```

OOD aggregate 71.15 % — kém spell-correction-base 8.47 pp trên text thực
tế hỗn hợp, nhưng nhanh + nhẹ hơn cho input thuần strip-dấu. Xem
[`/tasks/diacritic-restoration`](/tasks/diacritic-restoration) cho phân
tích trade-off đầy đủ.

#### Inference batched cho throughput (speedup 7.6× trên 3080)

Cho pipeline throughput cao (chục nghìn câu), dùng ``predict_batch``
thay vì loop ``predict``:

```python
restorer = HFDiacriticModel(device="cuda")
sentences = ["Toi yeu Viet Nam", "Hop dong so 02", ...]  # nhiều nghìn
restored = restorer.predict_batch(sentences, batch_size=16)
```

Đo được **throughput 7.60×** so với gọi single-call predict() trên
corpus Tatoeba 300 câu (RTX 3080 16 GB Mobile). Batch size 16 vừa
~4 GB VRAM ở input 256-token điển hình; bump lên 32+ trên card có
headroom hơn, drop xuống 4–8 trên GPU nhỏ hơn hoặc cho input dài.
Thứ tự output được giữ; input rỗng/blank pass qua mà không chạm model.

#### Zero-deps (41 % word acc, < 1 ms)

```python
from nom.text import fix_diacritics

out = fix_diacritics("Hop dong nay duoc lap")  # không có model arg → đường rule
# → 'Hợp đồng này được lập' (best-effort)
```

OK cho validate harness, normalize query BM25, dọn low-stakes. Sàn
độ chính xác là thật — chỉ ~41 % word acc trên VN thực.

#### LLM cục bộ (87 – 93 % word acc, ~1 s/câu)

```bash
pip install "nom-vn[llm]"
ollama pull gemma3:4b   # hoặc gemma4:e4b, hoặc qwen3:8b
```

```python
from nom.text import fix_diacritics
from nom.llm import Ollama

out = fix_diacritics(
    "Hop dong nay duoc lap",
    llm=Ollama(model="gemma3:4b"),
)
```

Dùng khi đã ghép một LLM cho tác vụ khác và muốn ít phụ thuộc hơn một bậc.
**Adapter `Ollama` mặc định `think=False`** — bắt buộc cho Qwen3,
vô hại cho mô hình không thinking.

### Tổng hợp text VN nhiễu (cho dữ liệu training sửa chính tả)

`nom.text.noise` cung cấp generator nhiễu tất định biến câu VN sạch
thành phiên bản kiểu typo/OCR thực tế — hữu ích để xây cặp
`(noisy, clean)` training mà không phải trả tiền cho dữ liệu
hand-labeled. Sáu hàm nhiễu tunable (strip dấu, partial strip,
substitution nhầm thanh, swap/insert/delete ký tự, substitution OCR)
và ba preset đã hiệu chỉnh:

```python
from nom.text.noise import NoiseGenerator, light_noise, heavy_noise, telex_typo_noise

# Light noise — mô phỏng người gõ trên bàn phím tiếng Việt.
gen = NoiseGenerator(light_noise(), seed=42)
print(gen.noisify("Tôi yêu Việt Nam và đất nước này tuyệt vời."))
# 'Toi yêu Viet Nam và đất nước này tuyệt vời.'

# Heavy noise — mô phỏng output OCR scan chất lượng trung bình.
gen = NoiseGenerator(heavy_noise(), seed=42)
print(gen.noisify("Hợp đồng số 02/HĐ/2025 được lập ngày 14 tháng 3 năm 2025."))
# 'Hop dong số 02/HĐ/2025 được lập ngya l4 tháng 3 năm 2025.'  # <- '14' -> 'l4'

# Telex typo — perturb dấu nặng, không OCR.
gen = NoiseGenerator(telex_typo_noise(), seed=42)
```

Tính chất:

- **Tất định** — cùng `(text, config, seed)` luôn sinh cùng output
  (tái lập corpus training).
- **Output NFC-normalized** — không bao giờ trả text NFD-decomposed
  (sát thủ thầm lặng của training seq2seq; xem postmortem
  NFD-poisoning v0.2.25 trong [`docs/benchmark.md`][bench]).
- **Cap edit-budget** — `max_edit_ratio` ngăn pile-up để config
  high-p không huỷ hoại input quá khả năng phục hồi.

[bench]: https://github.com/nrl-ai/nom-vn/blob/main/docs/benchmark.md

Dùng bởi dataset `nrl-ai/vn-spell-correction-train` sắp tới. Các hàm
nhiễu theo taxonomy lỗi paper VSEC
([arxiv:2111.00640](https://arxiv.org/abs/2111.00640)) và các nhầm
thanh tần suất cao bắt được trong audit khôi phục dấu của chúng tôi.

### Phân loại văn phong (router 4 lớp)

Định tuyến input theo văn phong (`formal` / `business` / `conversational`
/ `literary`) để các tool downstream (khôi phục dấu, tóm tắt, OCR
rerank) chọn đúng checkpoint chuyên biệt — survey nội bộ đo được spread
~8.7 pp giữa các văn phong, vậy nên router cheap này lift mọi tool khác
5–10 pp tự động.

```python
# Baseline — zero-ML, ~ms latency, ship trong OSS
from nom.classify import LexiconRegisterClassifier

clf = LexiconRegisterClassifier()
res = clf.predict("Căn cứ Luật ban hành văn bản quy phạm pháp luật, …")
# RegisterResult(label=RegisterLabel.FORMAL, score=0.62,
#                distribution={FORMAL: 0.62, BUSINESS: 0.20, …})
```

```python
# Production — PhoBERT-base + 4-class head (cần fine-tune trước)
from nom.classify import PhoBertRegisterClassifier

clf = PhoBertRegisterClassifier(model_id="nrl-ai/vn-register-phobert-base")
res = clf.predict("Doanh thu công ty trong quý 2 năm 2026 đạt 1,2 tỷ đồng …")
# Lazy-loads transformers + torch khi gọi predict() lần đầu.
# Tự word-segment qua nom.text.word_tokenize trước khi tokenize PhoBERT
# (BKai gotcha: raw text drops ≥ 15 pp).
```

Fine-tune checkpoint riêng:

```bash
python training/register/train.py \
    --output-dir checkpoints/register-phobert-base \
    --epochs 4
# Macro-F1 target ≥ 0.85 trên held-out 20 % của assembly UDHR + VNTC +
# Tatoeba + Wikisource. Xem training/register/README.md.
```

**Quy tắc ngón cái:** demo / CPU-only / không-cần-precision → lexicon.
Production routing trong server pipeline → PhoBERT.

### Tách từ tiếng Việt

Hai backend, chọn theo tốc độ vs F1:

```python
# Speed-first — pure Python, zero deps, F1 76 % trên UD_Vietnamese-VTB
from nom.text import word_tokenize
toks = word_tokenize("Thành phố Hồ Chí Minh là thành phố lớn nhất Việt Nam")
# ['Thành phố', 'Hồ Chí Minh', 'là', 'thành phố', 'lớn nhất', 'Việt Nam']
# 747 k tokens/sec
```

```bash
pip install "nom-vn[nlp]"   # thêm underthesea
```

```python
# Quality-first — model CRF, F1 95.7 %
import underthesea
toks = underthesea.word_tokenize(
    "Thành phố Hồ Chí Minh là thành phố lớn nhất Việt Nam"
)
# 38 k tokens/sec
```

**Quy tắc ngón cái:** RAG indexing / BM25 / dọn nhẹ → `nom.text`.
NER / dependency parsing / task ngôn ngữ → `underthesea`.

### Trích xuất thực thể VN — bộ chuẩn + bộ pháp lý

Quy tắc, không cần GPU, deterministic:

```python
from nom.nlp.ner import RegexNERModel

# Bộ chuẩn — PER / ORG / LOC / DATE / MONEY
ner = RegexNERModel()
spans = ner.tag("Vietcombank chuyển 1.500.000 VND vào ngày 14/3/2025 cho FPT.")
# → ('ORG' Vietcombank), ('MONEY' 1.500.000 VND), ('DATE' 14/3/2025), ('ORG' FPT)
```

Bộ pháp lý mở rộng — thêm `LAW_REF`, `ID_VN` (CMND/CCCD), `PHONE_VN`:

```python
from nom.nlp.ner import RegexNERModel
from nom.nlp.ner_legal import legal_ner_patterns

ner = RegexNERModel(extra_patterns=legal_ner_patterns())
spans = ner.tag(
    "Theo Nghị định 13/2023/NĐ-CP và Điều 5 Luật An ninh mạng, "
    "ông Nguyễn Văn A (CMND 012345678, ĐT 0912 345 678) thanh toán "
    "1.500.000 VND vào 14/3/2025."
)
# → 6 spans: 2× LAW_REF, 1× ID_VN, 1× PHONE_VN, 1× MONEY, 1× DATE
```

Hoặc qua API HTTP:

```bash
curl -X POST http://localhost:8080/api/tools/nlp/ner \
  -H 'content-type: application/json' \
  -d '{"text":"...","preset":"legal"}'
```

**Khi nào chọn:**

- **Hồ sơ doanh nghiệp / báo cáo / email** → `preset=standard` (bộ chuẩn).
- **Hợp đồng VN / công văn / biên bản** → `preset=legal` (mở rộng).
- **Cần entity tự custom** (ID nhân viên, mã hợp đồng nội bộ) →
  `RegexNERModel(extra_patterns=[("EMPLOYEE_ID", r"NV\d{6}"), ...])`.

PhoBERT-based NER đầy đủ (PER chính xác, F1 ≥ 90 %) cần fine-tune
trên VLSP-NER + chú thích tay cho `LAW_REF` / `CONTRACT_PARTY` —
đợt sau, chưa làm.

### Tóm tắt văn bản tiếng Việt

```bash
pip install "nom-vn[diacritic-hf]"   # đủ — transformers + torch
```

```python
from nom.summarize import ViT5Summarizer

summ = ViT5Summarizer()  # tải model lần đầu (~3.3 GB)
result = summ.summarize(
    "Việt Nam là một quốc gia nằm ở Đông Nam Á, có dân số khoảng "
    "100 triệu người. Thủ đô của Việt Nam là Hà Nội. Việt Nam có nền "
    "kinh tế đang phát triển nhanh chóng và là một trong những quốc gia "
    "có tốc độ tăng trưởng GDP cao nhất khu vực.",
    register="news",       # hoặc "legal" / "dialogue"
    max_length=128,
    min_length=20,
)
print(result.text)
# → "Việt Nam là một trong những quốc gia có tốc độ tăng trưởng GDP
#    cao nhất khu vực Đông Nam Á..."
```

> **Cảnh báo bịa số liệu:** mô hình ViT5 (và mọi mô hình tóm tắt sinh
> nói chung) có thể thêm số / năm / chỉ số CỤ THỂ không có trong văn
> bản gốc. Đo nội bộ: 1 trong 10 mẫu wiki_vi sinh ra năm "2025"
> không có trong nguồn; một mẫu khác bịa số GDP "6,8 % – 7,0 %".
> **Đừng dùng cho tóm tắt pháp lý / tài chính** mà không đối chiếu
> thủ công từng số.

Cap input ở 1024 token — văn bản dài hơn sẽ bị cắt; cho hợp đồng dài
chia đoạn theo tay hoặc dùng Qwen3-8B + LoRA (chưa ship).

### Giọng nói tiếng Việt → văn bản (STT)

```bash
pip install "nom-vn[stt]"   # transformers + torch + librosa + soundfile
```

```python
from nom.stt import PhoWhisperSTT, WhisperSTT

# Mặc định cho audio thuần VN
stt = PhoWhisperSTT()  # vinai/PhoWhisper-large, ~3 GB lần đầu
result = stt.transcribe("cuoc_hop.mp3")
print(result.text)         # transcript đã NFC-normalize
print(result.language)     # "vi"

# Trả về timestamp theo đoạn (cho phụ đề / đối chiếu)
result = stt.transcribe("cuoc_hop.mp3", return_timestamps=True)
for seg in result.segments:
    print(f"  {seg.start:.1f}s–{seg.end:.1f}s: {seg.text}")
```

Audio lai EN/VN — đổi sang Whisper-large-v3 (đa ngôn ngữ):

```python
stt = WhisperSTT()  # openai/whisper-large-v3
result = stt.transcribe("podcast_tech.mp3", language="vi")
```

Hoặc qua hàng đợi xử lý nền (cho audio dài):

```bash
curl -X POST http://localhost:8080/api/jobs/stt-transcribe \
  -F file=@cuoc_hop.mp3 \
  -F backend=phowhisper \
  -F return_timestamps=true
# → { "id": "<job-id>", "status": "queued", ... }
```

Cảnh báo: PhoWhisper claim WER VIVOS 4,67 % và VLSP T1 13,75 %
nhưng chưa được tái lập trong repo — đo nội bộ chỉ n=3 trên
Speech-MASSIVE (15,2 % WER cả hai mô hình). Bench nghiêm túc trên
ViMD 3 vùng là việc đợt sau.

### Normalize whitespace + Unicode

```python
from nom.text import normalize, has_diacritics, is_vietnamese

clean = normalize("Hợp  đồng   số 02/HĐ/2025  ")
# → 'Hợp đồng số 02/HĐ/2025'  (NFC + collapse whitespace)

has_diacritics("Hợp đồng")  # True
has_diacritics("Hop dong")  # False
is_vietnamese("Hợp đồng số 02")  # True (tỷ lệ chữ-VN trên ngưỡng)
```

Đây là stdlib-only, mức microsecond. Dùng trong tight loop.

---

## Recipe parsing tài liệu

### Trích text từ PDF (đường nhanh)

```bash
pip install "nom-vn[doc]"
```

```python
import pypdfium2 as pdfium

pdf = pdfium.PdfDocument("hop_dong.pdf")
text = "\n".join(p.get_textpage().get_text_range() for p in pdf)
pdf.close()
```

`pypdfium2` (BSD-3 wrapper trên PDFium Apache-2.0) là mặc định trong
`nom-vn[doc]`. **Nhanh hơn pdfplumber 46×** trên PDF text thuần ở
fidelity y hệt. Ship trong extra của chúng tôi đặc biệt vì chúng tôi
không kèm PyMuPDF — giấy phép AGPL kéo mọi phía sau sang AGPL.

### Trích text *kèm bảng* từ PDF

```python
import pdfplumber

with pdfplumber.open("invoice.pdf") as pdf:
    for page in pdf.pages:
        for table in page.extract_tables():
            for row in table:
                print(row)
```

`pdfplumber` chậm hơn (51 k chars/s vs 2.35 M chars/s của pypdfium2)
nhưng phát hiện ô bảng tốt hơn. Cả hai có sẵn trong `nom-vn[doc]`.

### OCR ảnh tiếng Việt (text in)

```bash
sudo apt install tesseract-ocr tesseract-ocr-vie   # Debian/Ubuntu
brew install tesseract tesseract-lang              # macOS
pip install "nom-vn[doc]"
```

```python
import pytesseract
from PIL import Image

text = pytesseract.image_to_string(
    Image.open("scan.png"),
    lang="vie",
    config="--psm 6",
)
```

Tesseract 5 + `vie` chạm **CER 5.53 %** trên ảnh ducto489 mid-noise
thực ở 80 ms p50 trên 8 nhân CPU. Đừng chộp lấy vision-language model
ở đây — `qwen2.5vl:7b` được CER 31 % ở latency 10× trên cùng ảnh
(xem [`docs/benchmark.md` § VLM OCR](benchmark.md)).

VLM *là* tool đúng cho **tài liệu phức tạp** (form, hoá đơn, CCCD,
chữ viết tay — chỗ bạn muốn extraction *và* hiểu). Là tool sai cho
transcription dòng sạch.

### Trích từ DOCX / XLSX / PPTX

```python
from docx import Document
doc = Document("contract.docx")
for para in doc.paragraphs:
    print(para.text)
```

```python
import openpyxl
wb = openpyxl.load_workbook("data.xlsx")
for sheet in wb.sheetnames:
    for row in wb[sheet].iter_rows(values_only=True):
        print(row)
```

```python
from pptx import Presentation
prs = Presentation("deck.pptx")
for slide in prs.slides:
    for shape in slide.shapes:
        if shape.has_text_frame:
            print(shape.text_frame.text)
```

Tất cả MIT/Apache, tất cả pure-Python, tất cả trong `nom-vn[doc]`.

### Một dòng: format bất kỳ → text

```python
from nom.doc import Pipeline

pipeline = Pipeline()  # auto-detect format
result = pipeline.run("anything.pdf").text   # hoặc .docx, .xlsx, .pptx, .png, .html
```

---

## Recipe retrieval

### Build index RAG VN — config chất lượng cao

Lựa chọn embedder chi phối chất lượng retrieval VN. Dùng embedder
được huấn luyện cho retrieval, không dùng default huấn luyện cho STS:

```bash
pip install "nom-vn[embeddings,nlp]"   # thêm sentence-transformers + underthesea
```

```python
from nom.embeddings import BKaiEmbedder
from nom.retrieve import DenseRetriever, BM25Retriever, HybridRetriever

embedder = BKaiEmbedder(device="cuda")   # hoặc "cpu", "mps"
docs = ["Hợp đồng số 02/HĐ/2025...", "Đối tác A: Công ty Cổ phần..."]

dense = DenseRetriever(embedder=embedder)
dense.fit(docs)
hits = dense.search("hợp đồng có phạt vi phạm không?", top_k=5)
```

**Vì sao bkai chứ không phải dangvantuan?** Trên Zalo Legal QA 5 k:

- `bkai-foundation-models/vietnamese-bi-encoder`: R@1 76.25 %, R@10 98.75 %
- `dangvantuan/vietnamese-embedding`: R@1 35.00 %, R@10 67.50 %

bkai train với `MultipleNegativesRankingLoss` trên cặp Q→Doc retrieval;
dangvantuan train trên STS (similarity đối xứng) — sai task. Mô hình
bkai auto-apply word segmentation underthesea (từ multi-syllable nối
bằng `_`) nên bạn không phải làm.

### Retrieval hybrid (BM25 + dense)

```python
from nom.retrieve import BM25Retriever, DenseRetriever, HybridRetriever

bm25 = BM25Retriever()
bm25.fit(docs)

dense = DenseRetriever(embedder=BKaiEmbedder())
dense.fit(docs)

hybrid = HybridRetriever([bm25, dense])
hits = hybrid.search("…", top_k=10)
```

Hybrid dùng Reciprocal Rank Fusion. Trên corpus Zalo Legal 61 k đầy đủ:

| Stage | recall@10 |
|---|---:|
| BM25 đơn | 0.78 |
| Dense đơn (`dangvantuan`) | 0.54 |
| Hybrid RRF | 0.78 |
| **Hybrid + reranker** | **0.87** |

BM25 **cạnh tranh đến giật mình** ở quy mô corpus nhỏ (subset 5 k
chạm R@1 = 0.76) nhưng các stage dense + reranker trở nên quan trọng
hơn khi pool distractor lớn lên.

### Thêm reranking cross-encoder

```bash
pip install "nom-vn[reranker]"
```

```python
from nom.rag import RAG
from nom.embeddings import BKaiEmbedder
from nom.llm import Ollama

rag = RAG.from_documents(
    docs,
    embedder=BKaiEmbedder(device="cuda"),
    llm=Ollama(model="qwen3:8b"),
    rerank=True,            # thêm BAAI/bge-reranker-v2-m3 mặc định
    rerank_candidates=30,   # rerank top-30 từ hybrid
    rerank_keep=5,          # pass top-5 cho LLM
)
answer = rag.ask("Trong các hợp đồng đã ký, có điều khoản phạt nào?")
```

Reranker mặc định là `BAAI/bge-reranker-v2-m3` (Apache, 568 M).
Đưa R@1 lên ~86 % trên Zalo Legal 5 k. `namdp-ptit/ViRanker` (Apache,
600 M, VN-specialized) trong khoảng 1.3 pp — pass `reranker="namdp-ptit/ViRanker"`
nếu muốn variant VN-tuned.

### BM25 nhanh trên corpus lớn

```python
from nom.retrieve import BM25Retriever

bm25 = BM25Retriever()
bm25.fit(corpus_of_60k_docs)   # ~5 giây cho 60k bài viết pháp lý
hits = bm25.search("Trình tự thoả thuận thông số kỹ thuật...", top_k=10)
# 0.7 ms mỗi query — backed bởi bm25s (công thức Lucene, scipy.sparse)
```

Việc đổi v0.2.6 sang `bm25s` cho **tăng tốc 607×** với recall y hệt
bit so với implementation pure-Python v0.2.5. Không tốn chất lượng.

---

## Recipe RAG

### RAG một dòng trên tài liệu local

```python
from nom.rag import RAG
from nom.llm import Ollama

rag = RAG.from_documents(
    ["contract.pdf", "letter.docx", "Hợp đồng số HD-001..."],
    llm=Ollama(model="qwen3:8b"),
)

answer = rag.ask("Có bao nhiêu hợp đồng có phạt vi phạm?")
print(answer.text)
print(answer.citations)   # [(doc_idx, chunk_idx, score, text), ...]
```

Mặc định dùng `dangvantuan/vietnamese-embedding` cho tương thích cache.
**Override sang `BKaiEmbedder` để +41 pp R@1 trên retrieval:**

```python
from nom.embeddings import BKaiEmbedder

rag = RAG.from_documents(
    docs,
    embedder=BKaiEmbedder(device="cuda"),
    llm=Ollama(model="qwen3:8b"),
)
```

Bản major 0.3.x sẽ đổi mặc định sang bkai. Chúng tôi không lật
mid-version vì sẽ âm thầm vô hiệu hoá cache embedding đã persist của
user.

### Trích xuất có cấu trúc (không RAG)

```python
from nom.doc import extract
from nom.llm import Ollama

result = extract(
    "hop_dong.pdf",
    schema={
        "so_hop_dong": str,
        "ngay_ky": "date",
        "tong_gia_tri": "amount_vnd",
        "ben_a": str,
        "ben_b": str,
    },
    llm=Ollama(model="qwen3:8b"),
)

print(result.so_hop_dong, result.ngay_ky, result.tong_gia_tri)
```

`extract` parse → chunk → hỏi LLM với ràng buộc structured-output
(Ollama `format` JSON schema). LLM không bao giờ thấy raw PDF byte;
nó chỉ thấy text đã dọn + schema.

### Dùng provider LLM khác

Protocol `LLM` là một method (`complete(prompt, *, schema=None)`).
Ba adapter có sẵn:

```python
# Ollama (local) — mặc định think=False
from nom.llm import Ollama
llm = Ollama(model="gemma3:4b")

# OpenAI / OpenAI-compatible (DeepSeek, Together, Groq, vLLM…)
from nom.llm import OpenAI
llm = OpenAI(model="gpt-4o-mini")
llm = OpenAI(model="deepseek-chat", base_url="https://api.deepseek.com")

# Anthropic
from nom.llm import Anthropic
llm = Anthropic(model="claude-haiku-4-5")
```

Bất kỳ class nào có `complete(prompt, *, schema, max_tokens) -> str`
đều chạy như một `LLM`. Tự xây cho vLLM, LiteLLM, HTTP tuỳ biến, ...

---

## Recipe chat web app

### Chạy chat app local

```bash
pip install "nom-vn[chat]"
ollama pull qwen3:8b
nom serve
# → http://localhost:8080
```

Upload PDF/Word/Excel/PowerPoint/ảnh, hỏi bằng tiếng Việt, nhận trả
lời với citation click-to-source. Persistent ở `~/.nom`.

### Chạy ephemeral (không persist disk)

```bash
nom serve --in-memory
```

Hữu ích cho demo, CI, hoặc khi không muốn file SQLite. Mọi
space / chat / doc tan khi `Ctrl+C`.

### Port / model tuỳ biến

```bash
nom serve --port 9000 --model phi4
```

### Dùng programmatic cùng store

```python
from nom.chat.stores import MemoryStore   # hoặc SqliteStore("./nom.db")
from nom.embeddings import BKaiEmbedder
from nom.llm import Ollama

store = MemoryStore(embedder=BKaiEmbedder(), llm=Ollama())
space_id = store.create_space("Hợp đồng của tôi")
store.add_document(space_id, "contract.pdf")
answer = store.ask(space_id, "Tóm tắt nội dung hợp đồng?")
```

---

## Recipe vận hành

### Tái lập một số bench

Mọi claim "đã đo" trong doc đều có script chạy được:

```bash
# Khôi phục dấu trên corpus 55 câu công khai
python benchmarks/accuracy/bench_diacritics.py
python benchmarks/accuracy/bench_diacritic_hf.py \
    Toshiiiii1/Vietnamese_diacritics_restoration_5th

# Tách từ trên UD_Vietnamese-VTB test (gold)
python benchmarks/accuracy/bench_segment.py --corpus ud_vtb --split test

# OCR trên corpus ducto489 mid-noise thực
python benchmarks/accuracy/bench_ocr_real.py \
    --corpus benchmarks/data/vn_ocr_subset --variant none \
    --engines tesseract,easyocr --limit 50

# RAG retrieval trên Zalo Legal QA
python benchmarks/rag/bench_rag_vn.py --embedder bkai
python benchmarks/rag/bench_embedder_compare.py
```

Baseline ở `benchmarks/results/baseline_*.json`. Tái lập là rule
verified-benchmarks cứng — mọi số phải đến từ một script chạy được
từ một bản clone sạch, không phải screenshot model card.

### Xem cái gì đổi giữa các release

```bash
git log --oneline v0.2.6..HEAD     # từ lúc đổi BM25
```

CHANGELOG.md có chi tiết per-version với các con số đo dịch chuyển.

### Kiểm tra tuân thủ giấy phép cho phụ thuộc đi kèm

```bash
pip-licenses --format=markdown --packages nom-vn pypdfium2 pdfplumber \
    sentence-transformers underthesea bm25s
```

Chúng tôi từ chối AGPL (PyMuPDF, Surya), GPL (code Surya), và dep
kèm pickle (PyVi). Danh sách này tự động bị từ chối theo chính sách xây dựng component.

---

## Xem thêm

- [`docs/architecture.md`](architecture.md) — model 7 lớp + đường nối Protocol
- [`docs/benchmark.md`](benchmark.md) — mọi con số đo trong tài liệu này, kèm methodology
- [`docs/training_plan_2026q2.md`](training_plan_2026q2.md) — khi nào fine-tune vs adopt có sẵn
- [`docs/sota_vn_2026q2.md`](sota_vn_2026q2.md) — lựa chọn SOTA VN hiện tại theo task có citation
- [`CHANGELOG.md`](../CHANGELOG.md) — chi tiết per-version

### OCR chữ viết tay tiếng Việt

Tesseract trên chữ viết tay đạt CER ~69 % (đã đo trên brianhuster) —
quá cao cho mọi pipeline downstream. Vintern-1B-v3_5 (5CD-AI, MIT,
safetensors) là VLM open duy nhất sub-1 B được train riêng cho chữ tay
tiếng Việt; first-party CER pending nhưng VLM-class vượt Tesseract dễ
dàng trên cùng dataset.

```python
from nom.ocr import VinternHandwritingOcr

clf = VinternHandwritingOcr()  # lazy-loads transformers + torch
result = clf.transcribe("biên_lai.jpg")
print(result.text)
```

```python
# Hoặc qua API + curl:
# POST /api/tools/ocr/handwriting (multipart: file=...)
```

**Cạm bẫy bắt buộc nhớ**: VLMs (Vintern, Qwen-VL, GOT-OCR) ảo trên
**line crops** chiều ngắn < 60 px. Truyền cả trang, không cắt từng
dòng. Wrapper raise `ValueError` trên ảnh nhỏ hơn ngưỡng để chặn
trước khi gọi model.

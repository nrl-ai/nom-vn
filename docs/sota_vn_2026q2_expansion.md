# SOTA cho `nom-vn` — Expansion picks, 2026 Q2

**Phạm vi.** 6 trục mở rộng deeper-VN bổ sung cho `sota_vn_2026q2.md` (đã cover LLM / embedder / OCR-printed): **register classifier, handwriting OCR, spell + grammar, STT + diarization, NER legal, summarization register-aware**.
**Ràng buộc.** Apache-2.0 / MIT / BSD-friendly, file-format trust ladder (safetensors ✅ / HF .bin major lab ⚠️ / pickle ❌ / opaque native ⚠️), verified benchmarks only.
**Ngày.** 2026-05-03. Survey chi tiết per-axis trong `docs/research/2026-05-03-vn-<axis>-survey.md`.

---

## Master matrix

| Trục | Lựa chọn hàng đầu | Giấy phép | Định dạng | Kích thước | Số đo VN (nội bộ, 2026-05-03) | Trạng thái |
|---|---|---|---|---|---|---|
| Phân loại văn phong (cơ sở) | `nom.classify.LexiconRegisterClassifier` (trong cây mã) | Apache 2.0 | — (không học máy) | < 1 KB | chưa đo (quy tắc; tự test mình trên từ-mốc của chính nó) | đã ship |
| Phân loại văn phong (sản xuất) | [`nrl-ai/vn-register-phobert-base`](https://huggingface.co/nrl-ai/vn-register-phobert-base) (PhoBERT-base + 4-class head) | MIT | safetensors | ~540 MB | **macro F1 0,900** trên test n=1234 (formal 0,914 / business 0,906 / conv 0,915 / literary 0,866) | đã ship + đo đầy đủ |
| OCR chữ viết tay | `5CD-AI/Vintern-1B-v3_5` (không cần huấn luyện thêm) | MIT | safetensors | 0,9 B | **CER 0,47 % sạch / 0,37 % nhiễu** (n=20 mỗi loại, `synthetic_ocr_vi`) | đã ship + đã đo |
| Sửa chính tả v0.1 | `nrl-ai/vn-spell-correction-base` (sẵn trong stack) | MIT | .bin | ~900 MB | **78,33 % word-acc tổng hợp / khớp 65 trên 150 câu** (n=150 OOD trên 6 thể loại) | đã ship + đã đo |
| Sửa chính tả v0.1 theo thể loại | cùng mô hình | — | — | — | ocr 97,6 / news 96,5 / mobile 95,8 / legal 95,6 / forum 63,4 / **telex 18,0** | điểm yếu đã biết |
| Sửa chính tả v0.2 (chặn lỗi) | `vinai/phobert-base` head phân loại token | MIT | .bin | 135 M | Tự đo FPR mục tiêu <5 % trên UD-VTB sạch | chưa bắt đầu |
| STT | `VinAI/PhoWhisper-large` | BSD-3 | .bin (VinAI) | 1,5 B | **WER 15,2 %** nội bộ (n=3 Speech-MASSIVE_vie); VinAI công bố: VIVOS 4,67 % WER, VLSP T1 13,75 % | đã ship + đo nhỏ |
| STT (lai EN/VN) | `openai/whisper-large-v3` | MIT | safetensors | 1,5 B | **WER 15,2 %** nội bộ (n=3, ngang PhoWhisper trên tập này) | đã ship + đo nhỏ |
| Phân tách người nói | `pyannote/speaker-diarization-community-1` | CC-BY-4.0 (gated) | .bin | 16 M | VoxConverse DER 11,2 % (đo trên tiếng Anh) — chưa có số VN | chưa tích hợp |
| Phân tách (thời gian thực) | NVIDIA Sortformer v2 | CC-BY-4.0 | TBD | — | RTF 0,093, giới hạn cứng ≤4 người nói | chưa tích hợp |
| NER cơ sở | quy tắc (`nom.nlp.ner_legal`) | Apache 2.0 | — (không học máy) | n/a | test pass trên các mẫu chính tôi viết (tự test mình) | đã ship |
| NER mục tiêu | `vinai/phobert-base` fine-tune + đầu LAW_REF + CONTRACT_PARTY | MIT | .bin | 135 M | F1 94,7 PER/ORG/LOC/MISC (VLSP 2016, upstream); đầu custom cần 70–90 giờ chú thích | chưa bắt đầu |
| Tóm tắt (tin tức) | `VietAI/vit5-large-vietnews-summarization` | MIT | .bin | 866 M | upstream ROUGE-1 63,4 vietnews; 1 mẫu thử **bịa số GDP cụ thể** | đã ship, kèm cảnh báo bịa số |
| Tóm tắt (pháp lý / dài) | `Qwen/Qwen3-8B` + LoRA theo thể loại | Apache 2.0 | safetensors | 8 B | ngữ cảnh 131 k, chưa có số tóm tắt VN | chưa bắt đầu |

**In đậm = số chính chúng tôi đo.** Nguồn JSON đặt tại `benchmarks/accuracy/`:
`spell_correction_real_baseline.json`, `vintern_ocr_clean_baseline.json`,
`vintern_ocr_noisy_baseline.json`, `stt_speech_massive_baseline.json`.
Tái lập bằng cách chạy lại các script đính kèm từ một bản clone sạch.

**Cảnh báo gắn liền với từng con số, không giấu vào chú thích chân:**

- **Sửa chính tả ở thể loại telex 18 %** là điểm yếu thật. Mô hình
  đã chuyển "Toi yu" → "Tới từ" (khác nghĩa hoàn toàn). Thể loại
  forum (viết tắt kiểu chat) đứng thứ hai từ dưới với 63 %. Đừng nói
  "sửa chính tả chạy tốt" mà không nói rõ *thể loại nào* — văn bản
  trang trọng đúng là 95–97 %, telex / forum thì không.
- **Vintern CER 0,47 %** tính ở mức ký tự — phần lớn lỗi còn lại là
  biến thể chính tả VN hợp lệ (`hoà` ↔ `hòa`) mà CER đếm là khác,
  dù về nghĩa thì giống. n=20 còn nhỏ; phải đo trên 200 ảnh trước
  khi công bố để áp dụng.
- **STT n=3 là đo thử, chưa phải kết luận.** Cả PhoWhisper-large
  và Whisper-v3 đều đạt 15,2 % WER trên tập này; lỗi chủ yếu do dấu
  câu / viết hoa và một chỗ nhầm từ đồng âm (`múi giờ` ↔ `mỗi giờ`).
  Phải đo trên ViMD chia 3 vùng trước khi khẳng định bao phủ phương
  ngữ.
- **Tóm tắt bịa số liệu** đã thấy trên một đoạn 234 ký tự duy nhất
  (mô hình tự bịa con số GDP "6,8 % – 7,0 %" không có trong nguồn).
  Một mẫu chưa phải kết luận, nhưng đủ để cảnh báo — đo nhiều mẫu
  là việc của đợt tiếp theo.
- **Phân loại văn phong "có học máy"** đã ship sau lần huấn luyện
  ngày 2026-05-03 — macro F1 0,900 trên test n=1234, qua cả hai cửa
  thẩm định (macro ≥ 0,85, từng class ≥ 0,75). Phiên bản
  [`nrl-ai/vn-register-phobert-base`](https://huggingface.co/nrl-ai/vn-register-phobert-base)
  giờ là mặc định khi gọi `PhoBertRegisterClassifier()`. Phiên bản
  quy tắc vẫn trong OSS như fallback rẻ tiền (~1 ms / câu, không cần
  GPU).

---

## Trust-ladder verdicts đáng flag

- **PhoWhisper / PhoBERT đều là `.bin` pickled, không có safetensors variant.** Acceptable per project policy (VinAI = recognized VN lab) — nhưng **bắt buộc document SHA256 + lý do trong wrapper docstring** mỗi khi load. Không được dùng `pickle` từ unknown publisher; VinAI là exception có lý do.
- **`5CD-AI/Viet-Handwriting-OCR` license unspecified** — không train trước khi confirm với 5CD-AI. Dùng `brianhuster/VietnameseOCRdataset` (Apache 2.0, 7 296 ảnh) cho eval đến khi license confirmed.
- **`pyannote/speaker-diarization-community-1` gated** — cần HF account + contact share; không có commercial restriction nhưng auto-pull không chạy. Cần wrapper thông báo user setup.
- **`X-GENRE` (phân loại văn phong đa ngôn ngữ, không cần huấn luyện) là CC-BY-SA-4.0** — copyleft. Dùng làm điểm so sánh, không dùng làm phụ thuộc lõi.
- **`XLSum VN` (40 k articles) là CC-BY-NC-SA** — non-commercial. Skip cho training; dùng `nam194/vietnews` (143 k, license permissive) thay thế.

---

## Lộ trình đề xuất

### Đợt 1 — Việc nhanh, giá trị cao (~3 tuần với 1 người làm)

| Thứ tự | Công cụ | Công sức | Lý do ưu tiên |
|---|---|---:|---|
| 1 | **Phân loại văn phong** | 3 ngày | Nâng mọi công cụ VN downstream lên 5–10 pp tự động (định tuyến đúng checkpoint khôi phục dấu / tóm tắt / OCR-rerank). Chi phí thấp nhất, đòn bẩy cao nhất. |
| 2 | **OCR chữ viết tay** | 3–7 ngày | Vintern-1B-v3_5 dùng được luôn không cần huấn luyện thêm; chỉ huấn luyện thêm nếu CER chênh > 10 pp. Ghép tốt với trang Chuyển định dạng. |
| 3 | **Sửa chính tả v0.1** | 3–5 ngày | Ai cũng cần, dễ lan toả. Bộ dữ liệu coung21 (978 k cặp, MIT) + BARTpho (đã trong stack) → ship nhanh. |
| 4 | **STT (PhoWhisper-large)** | 3–4 ngày | Whisper-large-v3 dự phòng cho audio lai EN/VN (đo trước rồi định tuyến). Ghép tốt với chat (dán transcript hỏi đáp). |

**Tổng Đợt 1: ~3 tuần.** 4 công cụ mới ship được, mỗi công cụ có
con số đo độc lập.

### Đợt 2 — Chất lượng + bao phủ (~2–3 tuần)

| Thứ tự | Công cụ | Công sức | Phụ thuộc |
|---|---|---:|---|
| 5 | **Sửa chính tả v0.2** (PhoBERT làm rào chắn precision) | +3 ngày | Sau Sửa chính tả v0.1 |
| 6 | **Phân tách người nói** (pyannote community-1) | 2–3 ngày | Sau STT |
| 7 | **Tóm tắt v0.1 tin tức** (ViT5-large dùng luôn) | 1–2 ngày | Độc lập — chỉ cần underthesea tokenizer cho ROUGE |

### Đợt 3 — Việc nặng (~4–6 tuần)

| Công cụ | Công sức | Ghi chú |
|---|---:|---|
| **NER pháp lý** (LAW_REF + CONTRACT_PARTY) | 70–90 giờ chú thích + 2 ngày huấn luyện | Chú thích thủ công là chi phí chính. v0.1 có thể chỉ làm LAW_REF bằng quy tắc; NER đầy đủ chờ pilot doanh nghiệp xác nhận. |
| **Tóm tắt v0.2 theo văn phong** | 5–7 ngày/LoRA × 3 văn phong = 15–21 ngày | Phụ thuộc phân loại văn phong (Đợt 1). |
| **STT thời gian thực** (Sortformer v2) | 3 ngày | Khi có nhu cầu chuyển ghi âm trực tiếp. |

---

## Cạm bẫy chung (áp dụng cho mọi công cụ)

1. **NFC chuẩn hoá trước mọi thứ.** Bộ Vietnamese-News-dedup có 79 %
   NFD, đã gây regression −15 pp một lần. Wikipedia VN cũng có lẫn.
   Mỗi corpus mới phải kiểm bằng `unicodedata.normalize('NFC', t) == t`
   trên một mẫu trước khi đưa vào huấn luyện hay đánh giá.
2. **Tách từ qua VnCoreNLP cho mọi NER + truy hồi.** PhoBERT,
   BKai-bi-encoder, VLSP-NER đều được huấn luyện trên đầu vào đã
   tách từ. Bỏ qua bước này = rớt 15–20 pp. `nom.text.tokenize` đã
   xử lý — đừng cho phép bỏ qua.
3. **VLM ảo trên line crop hẹp.** Vintern, Qwen-VL, GOT-OCR cùng
   chung kiểu lỗi (đã đo qwen2.5vl 33 % CER trên dòng chữ in sạch).
   Truyền cả ảnh + ràng buộc JSON-schema, không cắt từng dòng.
4. **VN ROUGE phải pin `underthesea.word_tokenize`.** ROUGE mặc định
   tách theo dấu cách → cắt nhầm âm tiết, điểm cross-paper không so
   sánh được. Pin tokenizer trong mọi JSON kết quả.
5. **PhoWhisper không công bố WER theo từng vùng giọng.** ViMD đo
   PhoWhisper-base tệ nhất trên giọng Trung (18,26 %) so với Nam
   (13,54 %). PhoWhisper-large vẫn chưa biết — bắt buộc đo trên ViMD
   trước khi đưa vào sản xuất claim "bao phủ phương ngữ".
6. **Register-shift là chuyện ngầm.** Spread 8,7 pp đã đo trên
   diacritic Toshiiiii1 4-register. Hiện tượng tương tự nhiều khả
   năng lặp lại trên tóm tắt, NER, OCR-rerank. Bộ phân loại văn phong
   ở Đợt 1 cắt khoảng cách này tự động.

---

## Khoảng trống có thể là "người đầu tiên" trên thế giới

Ba khoảng trống mà OSS tiếng Việt chưa ai lấp — `nom-vn` có thể là
nơi đầu tiên công bố một bench có thể trích dẫn:

1. **Bộ dữ liệu VN dán nhãn 4 văn phong (~2 000 câu/lớp, CC0, NFC).**
   Các bench đa ngôn ngữ về thể loại (AGILE, X-GINCO) **loại trừ
   tiếng Việt hoàn toàn.** Cách lắp = ghép theo nguồn gốc câu từ
   UDHR + VNTC + Tatoeba + Wikisource đã có sẵn trong
   `benchmarks/data/`.
2. **Bộ chú thích chuẩn về lỗi ngữ pháp VN (tương đương CoNLL-2014).**
   Mọi corpus sửa chính tả VN hiện có chỉ ở mức thay ký tự âm tiết.
   Chú thích ngữ pháp đầy đủ (trật tự từ, lượng từ, hư từ) chưa có
   bộ giấy phép mở nào.
3. **Bench VN form trộn nội dung (chữ in + chữ tay).** Khảo cứu
   arXiv 2506.05061 nêu rõ chưa có bench mở đầu-cuối cho biểu mẫu
   VN (nhãn in + nội dung viết tay + đóng dấu + chữ ký). Đường ống
   Vintern (đọc form) + TrOCR fine-tune (chép văn bản) là vùng đất
   mới chưa ai đặt chân.

Mỗi khoảng trống nếu publish được sẽ thành paper hoặc model card có
trích dẫn — đó là cách xây "moat" thật.

---

## Trỏ đến từng khảo cứu chi tiết (cho ai đọc kỹ từng trục)

- Register classifier: `docs/research/2026-05-03-vn-register-classifier-survey.md`
- Handwriting OCR: `docs/research/2026-05-03-vn-handwriting-ocr-survey.md`
- Spell + grammar: `docs/research/2026-05-03-vn-spell-grammar-survey.md`
- STT + diarization: `docs/research/2026-05-03-vn-stt-diarization-survey.md`
- NER legal: `docs/research/2026-05-03-vn-ner-legal-survey.md`
- Summarization: `docs/research/2026-05-03-vn-summarization-survey.md`

---

## Citation

```bibtex
@misc{nguyen_nom_vn_sota_expansion_2026,
  author = {Nguyen, Viet-Anh and {Neural Research Lab}},
  title  = {{nom-vn SOTA Expansion Picks Q2 2026: register · handwriting OCR · spell · STT · NER · summarization}},
  year   = {2026},
  url    = {https://github.com/nrl-ai/nom-vn/blob/main/docs/sota_vn_2026q2_expansion.md}
}
```

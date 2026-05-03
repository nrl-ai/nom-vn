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
| OCR chữ viết tay | `5CD-AI/Vintern-1B-v3_5` (không cần fine-tune) | MIT | safetensors | 0,9 B | **CER 0,47 % sạch / 0,37 % nhiễu** (n=20 mỗi loại, `synthetic_ocr_vi`) | đã ship + đã đo |
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
- **`X-GENRE` (multilingual register zero-shot) là CC-BY-SA-4.0** — copyleft. Dùng làm baseline, không dùng làm core dependency.
- **`XLSum VN` (40 k articles) là CC-BY-NC-SA** — non-commercial. Skip cho training; dùng `nam194/vietnews` (143 k, license permissive) thay thế.

---

## Sequencing đề xuất

### Tier 1 — Quick wins (~3 tuần wall-clock với 1 dev)

| Order | Tool | Effort | ROI rationale |
|---|---|---:|---|
| 1 | **Register classifier** | 3 days | Lift mọi VN tool downstream 5-10 pp tự động (route đúng diacritic / summarization / OCR-rerank checkpoint). Cost thấp nhất, đòn bẩy cao nhất. |
| 2 | **Handwriting OCR** | 3-7 days | Vintern-1B-v3_5 có thể plug-and-play; chỉ fine-tune nếu zero-shot CER >10 pp gap. Pair tốt với `convert` page existing. |
| 3 | **Spell v0.1** | 3-5 days | Universal need, viral potential. coung21 dataset (978k MIT) + BARTpho (đã trong stack) → ship nhanh. |
| 4 | **STT (PhoWhisper-large)** | 3-4 days | Whisper-large-v3 fallback cho code-switch (đo trước, pick router). Pair với chat (paste transcript hỏi đáp). |

**Tổng Tier 1: ~3 tuần.** 4 tool mới ship được, mỗi cái có verified bench number.

### Tier 2 — Quality + breadth (~2-3 tuần)

| Order | Tool | Effort | Phụ thuộc |
|---|---|---:|---|
| 5 | **Spell v0.2** (PhoBERT precision guard) | +3 days | Sau Tier 1 spell |
| 6 | **Diarization** (pyannote community-1) | 2-3 days | Sau STT |
| 7 | **Summarization v0.1 news** (ViT5-large off-the-shelf) | 1-2 days | Independent — chỉ cần underthesea tokenizer cho ROUGE |

### Tier 3 — Heavy lifts (~4-6 tuần)

| Tool | Effort | Notes |
|---|---:|---|
| **NER cho legal** (LAW_REF + CONTRACT_PARTY) | 70-90 annotator-hours + 2 days train | Annotation chính là cost dominant. v0.1 có thể regex-only LAW_REF, NER full khi enterprise pilot xác nhận. |
| **Summarization v0.2 register-aware** | 5-7 days/LoRA × 3 register = 15-21 days | Phụ thuộc register classifier (Tier 1) |
| **STT streaming** (Sortformer v2) | 3 days | Khi có use-case real-time |

---

## Cross-cutting traps (áp dụng cho mọi tool)

1. **NFC normalize trước mọi thứ.** Vietnamese-News-dedup là 79 % NFD, đã gây regression -15 pp lần trước. Wikipedia VN cũng mix. Audit corpus mới bằng `unicodedata.normalize('NFC', t) == t` trên sample.
2. **Word-segment VnCoreNLP cho mọi NER + retrieval.** PhoBERT, BKai-bi-encoder, VLSP NER ALL train trên word-segmented input. Bypass = -15 đến -20 pp rớt. `nom.text.tokenize` đã làm — không cho phép skip.
3. **VLM hallucinate tight line crops.** Vintern, Qwen-VL, GOT-OCR đều cùng failure mode (đã đo qwen2.5vl 33 % CER trên printed clean line). Pass full image + JSON-schema constraint, không line-crop.
4. **VN ROUGE tokenizer pin = `underthesea.word_tokenize`.** Default whitespace ROUGE chia syllable, scores cross-paper không comparable. Pin tokenizer trong mọi result JSON.
5. **PhoWhisper không công bố per-dialect WER.** ViMD shows base worst on Central (18.26 %) vs Southern (13.54 %). PhoWhisper-large Central performance UNKNOWN — bắt buộc bench với ViMD trước khi production claim.
6. **Register-shift lift implicit.** 8.7 pp spread đã đo trên diacritic Toshiiiii1 4-register. Same likely apply to summarization, NER, OCR-rerank. Tier 1 register classifier cuts this gap automatically.

---

## Gaps có thể ship "first" trên thế giới

3 gaps mà VN OSS field chưa ai làm — `nom-vn` có thể là first publisher với citable benchmark:

1. **4-register VN labelled dataset (~2 000 sentences/class, CC0, NFC).** Multilingual genre benchmarks (AGILE, X-GINCO) **exclude VN entirely**. Build = source-provenance assembly từ UDHR + VNTC + Tatoeba + Wikisource đã có trong `benchmarks/data/`.
2. **VN GEC gold corpus (CoNLL-2014 equivalent).** Mọi VN spell corpus hiện tại là syllable-level character substitution only. Annotated grammar (word order, classifier, particle) không tồn tại open-license.
3. **Mixed-content VN form benchmark.** Survey arXiv 2506.05061 explicitly flag thiếu open end-to-end benchmark cho VN form (printed label + handwritten fill + stamp + signature). Vintern (form) + TrOCR-FT (transcription) pipeline = novel ground.

Mỗi gap publish được = paper hoặc model card có citation, build moat thật.

---

## Cá nhân quotes per-survey (cho ai đọc kỹ từng axis)

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

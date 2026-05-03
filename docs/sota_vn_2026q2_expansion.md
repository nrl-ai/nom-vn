# SOTA cho `nom-vn` — Expansion picks, 2026 Q2

**Phạm vi.** 6 trục mở rộng deeper-VN bổ sung cho `sota_vn_2026q2.md` (đã cover LLM / embedder / OCR-printed): **register classifier, handwriting OCR, spell + grammar, STT + diarization, NER legal, summarization register-aware**.
**Ràng buộc.** Apache-2.0 / MIT / BSD-friendly, file-format trust ladder (safetensors ✅ / HF .bin major lab ⚠️ / pickle ❌ / opaque native ⚠️), verified benchmarks only.
**Ngày.** 2026-05-03. Survey chi tiết per-axis trong `docs/research/2026-05-03-vn-<axis>-survey.md`.

---

## Master matrix

| Trục | Top pick | License | Format | Size | VN bench (in-house, 2026-05-03) | Status |
|---|---|---|---|---|---|---|
| Register classifier (baseline) | `nom.classify.LexiconRegisterClassifier` (in-tree) | Apache 2.0 | — (zero-ML) | < 1 KB | not measured (heuristic; tautological on its own markers) | shipped |
| Register classifier (target) | `vinai/phobert-base` fine-tune | MIT | .bin (VinAI) | 135 M | training script ready; **GPU run pending** | code-complete |
| Handwriting OCR | `5CD-AI/Vintern-1B-v3_5` (zero-shot) | MIT | safetensors | 0.9 B | **CER 0.47 % clean / 0.37 % noisy** (n=20 each, `synthetic_ocr_vi`) | shipped + benched |
| Spell v0.1 | `nrl-ai/vn-spell-correction-base` (in-stack) | MIT | .bin | ~900 MB | **78.33 % word-acc agg / 65 of 150 sent-exact** (n=150 OOD across 6 registers) | shipped + benched |
| Spell v0.1 by register | same | — | — | — | ocr 97.6 / news 96.5 / mobile 95.8 / legal 95.6 / forum 63.4 / **telex 18.0** | known weak spots |
| Spell v0.2 (precision guard) | `vinai/phobert-base` token-class head | MIT | .bin | 135 M | Tự đo FPR target <5 % trên UD-VTB clean | not started |
| STT | `VinAI/PhoWhisper-large` | BSD-3 | .bin (VinAI) | 1.5 B | **15.2 % WER** in-house (n=3 Speech-MASSIVE_vie); upstream: VIVOS 4.67 % WER, VLSP T1 13.75 % | shipped + tiny bench |
| STT (code-switch) | `openai/whisper-large-v3` | MIT | safetensors | 1.5 B | **15.2 % WER** in-house (n=3, identical to PhoWhisper on this set) | shipped + tiny bench |
| Diarization | `pyannote/speaker-diarization-community-1` | CC-BY-4.0 (gated) | .bin | 16 M | VoxConverse DER 11.2 % (EN bench) — VN chưa có | not integrated |
| Diarization (streaming) | NVIDIA Sortformer v2 | CC-BY-4.0 | TBD | — | RTF 0.093, ≤4 speakers hard cap | not integrated |
| NER base | regex baseline (`nom.nlp.ner_legal`) | Apache 2.0 | — (zero-ML) | n/a | tests pass on patterns I designed (tautological) | shipped |
| NER target | `vinai/phobert-base` fine-tune w/ LAW_REF + CONTRACT_PARTY heads | MIT | .bin | 135 M | F1 94.7 PER/ORG/LOC/MISC (VLSP 2016, upstream); custom heads need 70-90 hr annot | not started |
| Summarization (news) | `VietAI/vit5-large-vietnews-summarization` | MIT | .bin | 866 M | upstream ROUGE-1 63.4 vietnews; 1-sample test **hallucinated specific GDP figures** | shipped, hallucination caveat |
| Summarization (legal/long) | `Qwen/Qwen3-8B` + LoRA per register | Apache 2.0 | safetensors | 8 B | 131 k context, no VN summary number | not started |

**Bold = first-party measured.** Bench sources committed under `benchmarks/accuracy/`:
`spell_correction_real_baseline.json`, `vintern_ocr_clean_baseline.json`,
`vintern_ocr_noisy_baseline.json`, `stt_speech_massive_baseline.json`.
Reproduce by re-running the inline scripts from a clean clone.

**Caveats baked into the numbers, not hidden in footnotes:**

- **Spell telex 18 %** is a real failure mode. The model converted
  "Toi yu" → "Tới từ" (different meaning entirely). Forum register
  (chat-style abbreviations) is the second-worst at 63 %. Don't claim
  "spell-correction works" without saying *which register* — formal
  prose is genuinely 95-97 %, telex/forum are not.
- **Vintern 0.47 % CER** is computed at the character level — many of
  the residual errors are valid VN diacritic variants (`hoà` ↔ `hòa`)
  that count as differences but are functionally correct. n=20 only;
  scale to a 200-image set before adoption claims.
- **STT n=3 is a smoke test, not a verdict.** Both PhoWhisper-large
  and Whisper-v3 hit identical WER on this set (15.2 %), with errors
  driven mostly by punctuation/case differences and one shared
  homophone confusion (`múi giờ` ↔ `mỗi giờ`). Bench on ViMD's
  three-region split before claiming dialect coverage.
- **Summarize hallucination** observed on a single 234-char input
  (the model wrote out specific "6,8 % – 7,0 %" GDP figures that
  weren't in the source). Single sample isn't a verdict, but it's
  enough to flag — multi-sample bench is open Tier 2 work.
- **Register-classifier "ML"** isn't shipped yet. The PhoBERT path is
  code-complete with a training script under `training/register/`,
  but the GPU run hasn't happened. The lexicon baseline is what
  actually runs in OSS today.

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

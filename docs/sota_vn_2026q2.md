# SOTA for Local-First Vietnamese AI — 2026 Q2 Snapshot

**Scope.** Three layers of `nom-vn`: local LLM, dense text embedding, document OCR.
**Constraints.** Apache-2.0-friendly, no pickled weights, runs on a laptop or one consumer GPU (≤24 GB VRAM, ideally ≤8 GB at default), VN quality from a citable benchmark.
**Date.** 2026-04-25. Every number below has a working URL; where none exists we say so explicitly.

---

## 1. LLM (local generation)

### Keep `Qwen3-8B`, add `Sailor2-8B` as the VN-tuned alternative

| Tier | Model | License | Disk (BF16 / Q4) | VRAM floor | VN benchmark |
|---|---|---|---:|---:|---|
| **Default** | `Qwen/Qwen3-8B` | Apache 2.0 | ~16 GB / ~5 GB | 6 GB (Q4) / 16 GB (BF16) | No first-party VN number on the model card; not on VMLU leaderboard as of 2026-04-25 |
| **VN-tuned alt** | `sail/Sailor2-8B` | Apache 2.0 | ~18 GB BF16 | ~16 GB | 13 SEA langs incl. VN; authors call it "best multilingual <10 B for SEA" |
| **One down** | `sail/Sailor2-1B` | Apache 2.0 | ~2 GB | ~3 GB / CPU-OK | Same SEA mix at 1 B scale |
| **One up** | `sail/Sailor2-20B` | Apache 2.0 | ~40 GB BF16 / ~12 GB Q4 | 24 GB (Q4) | Authors claim ~50/50 win-rate vs GPT-4o on SEA langs (full table deferred to paper) |

Sources: [Qwen3-8B card](https://huggingface.co/Qwen/Qwen3-8B), [Sailor2 blog](https://sea-sailor.github.io/blog/sailor2/), [Sailor2 paper (arXiv 2502.12982)](https://arxiv.org/abs/2502.12982), [VMLU leaderboard](https://vmlu.ai/leaderboard).

**Other candidates.** **PhoGPT-4B** ([HF](https://huggingface.co/vinai/PhoGPT-4B), BSD-3, 3.7 B, VinAI 2024) — no 2025/2026 update; stale. **Vistral-7B-Chat** ([HF](https://huggingface.co/Viet-Mistral/Vistral-7B-Chat)) — claimed VMLU **50.07** vs ChatGPT 46.33 in the paper, but HF card has no clear commercial license. **Phi-4** (MIT, 14 B) — no published VN benchmark; acceptable headroom only. VMLU top is dominated by closed VN fine-tunes (axis-sovereign 85.75, V-LLM v1 85.11, MISA-AI-1.0 81.26) — irrelevant for local-first.

**Last 6 months.** Qwen3 family (32 K native ctx, 131 K YaRN) replaced Qwen2.5 as the default open SEA-friendly LLM. **Sailor2** (Feb 2025) became the strongest *VN-tuned, redistributable* family at 1 B/8 B/20 B — first credible Apache challenger to PhoGPT/Vistral. PhoGPT and Vistral both effectively dormant.

**VN gotchas.** Tone marks (â/ă/ê/ô/ơ/ư + 5 tones) fragment to 3–6 tokens/word in BPE without VN exposure — Qwen3 and Sailor2 are fine. Legal/finance register thin in pretraining; VMLU "Law" shows the largest open-vs-closed gap. ≤4 B models drop tones on rare proper nouns.

**Recommendation.** Keep `qwen3:8b` default. **Add `sail/Sailor2-8B`** as documented "VN-tuned alternative." Phi-4 and Sailor2-20B Q4 for the accurate tier. Drop Vistral pending license clarity.

---

## 2. Embedding (dense retrieval)

### Swap default from `dangvantuan/vietnamese-embedding` to `AITeamVN/Vietnamese_Embedding`

`dangvantuan/vietnamese-embedding` is a **BGE-base** finetune (~440 MB, 768-d). `AITeamVN/Vietnamese_Embedding` is a **BGE-M3** finetune (~2.3 GB, 1024-d). The latter beats every public VN evaluation we could find. The size jump is acceptable for a default tier.

| Tier | Model | License | Dim / Size | VN benchmark |
|---|---|---|---|---|
| **One down (CPU)** | `dangvantuan/vietnamese-embedding` | Apache 2.0 | 768-d, ~440 MB | Currently shipped default; not in VN-MTEB Table 3 |
| **One down alt** | `hiieu/halong_embedding` | Apache 2.0 | 768-d (Matryoshka 64–768), ~0.3 B | Acc@1 **0.8294**, MRR@10 **0.8799** on Zalo Legal (20 % held-out) |
| **Default** | `AITeamVN/Vietnamese_Embedding` | Apache 2.0 | 1024-d, ~2.3 GB, 2048 ctx | Acc@1 **0.7274 vs 0.5682** for base BGE-M3, MRR@10 **0.8181 vs 0.6822** on Zalo Legal — **+27.9 % Acc@1** |
| **Default ref** | `BAAI/bge-m3` | MIT | 1024-d, ~2.3 GB | VN-MTEB **overall 64.90** (Retr 39.84 / Cls 69.09 / Pair 84.43 / Clust 45.90 / Rerank 71.28 / STS 78.84) |
| **One up** | `intfloat/multilingual-e5-large-instruct` | MIT | 1024-d, ~2.2 GB | VN-MTEB **overall 67.99** — best APE model in the paper |
| **One up alt** | `intfloat/e5-mistral-7b-instruct` | MIT | 4096-d, ~14 GB | VN-MTEB **overall 67.67**, Pair-class **84.01**, STS **81.20** — top RoPE model |

Sources: [VN-MTEB Table 3 (arXiv 2507.21500)](https://arxiv.org/html/2507.21500v1), [AITeamVN HF card](https://huggingface.co/AITeamVN/Vietnamese_Embedding), [halong HF card](https://huggingface.co/hiieu/halong_embedding).

**Contradiction to flag.** Our `BENCHMARK.md` says "BGE-M3 #1 at 64.90 overall" on VN-MTEB. **Actual #1 in Table 3 is `m-e5-large-instruct` at 67.99**, with `e5-mistral-7b-instruct` (67.67) and `gte-Qwen2-7B-instruct` (65.84) above BGE-M3. BGE-M3 is roughly 4th. Fix before users notice.

**Is AITeamVN's model competitive or marketing?** Zalo Legal numbers reproduce from the HF card on a held-out 20 % split (model not trained on it). +27.9 % Acc@1 over base BGE-M3 on a VN legal corpus is real. But it's *not* separately ranked in VN-MTEB Table 3 — the paper's "Vietnamese-Embedding" entry at **63.34** likely points to `dangvantuan/vietnamese-embedding`, not AITeamVN. Treat AITeamVN's gain as verified on legal-domain retrieval, unverified on broader VN-MTEB.

**Last 6 months.** **VN-MTEB paper** (Jul 2025) — first published 41-dataset, 6-task VN benchmark; the reference framework going forward. **`5CD-AI/Vintern-Embedding-1B`** and **`ColVintern-1B-v1`** — multimodal VN retrieval, no VN-MTEB number ([HF org](https://huggingface.co/5CD-AI)). AITeamVN's **Vietnamese_Reranker** (Acc@1 **0.7944** on Zalo Legal) is a strong retrieve+rerank candidate.

**VN gotchas.** BGE-base tokenizes VN noticeably worse than BGE-M3 and is more sensitive to NFC/NFD — always normalize to NFC at ingest (`nom.text` does). Zalo Legal numbers don't transfer linearly to news/conversational; re-measure on your corpus. AITeamVN's 2048 ctx is generous; most VN legal paragraphs are 200–400 tokens — over-chunking costs without recall gain.

**Recommendation.** Promote `AITeamVN/Vietnamese_Embedding` to default; keep current as `lite`. Document `e5-mistral-7b-instruct` as heavy-tier. **Fix the BGE-M3 #1 claim.**

---

## 3. OCR (image / scanned PDF → text)

The messiest layer. **No Apache-licensed VLM-as-OCR has a published VN benchmark we could verify.** We choose on adjacent evidence (multilingual scores, Latin-script subset, language coverage).

| Tier | System | License | Size / hardware | Verified number |
|---|---|---|---|---|
| **One down (CPU)** | Tesseract 5 + `vie` | Apache 2.0 | ~30 MB, CPU | No SOTA number; baseline ~70–97 % depending on input. Stacked-diacritic confusions documented. |
| **Default** | PaddleOCR PP-OCRv5 | Apache 2.0 | <100 MB det+rec, CPU/GPU | VN in 106-language list; **>30 %** multilingual recognition gain over PP-OCRv3, +13 % over PP-OCRv4 (no per-language VN number) |
| **Default alt** | VietOCR (pbcquoc) | Apache 2.0 | ~100 MB, GPU recommended | Trained on **10 M VN images**; no peer-reviewed benchmark; repo dormant in 2025–2026 |
| **Accurate** | `rednote-hilab/dots.ocr` (3 B VLM) | **MIT** | 3 B, safetensors, ~6 GB, fits 8–12 GB VRAM | OmniDocBench-EN edit **0.125** (beats Gemini-2.5-Pro 0.148, MinerU 2 0.139); 100-lang in-house bench **but no per-language VN score** |
| **Accurate alt** | `Qwen/Qwen3-VL-8B-Instruct` | Apache 2.0 | 9 B, safetensors, ~18 GB BF16 / ~6 GB Q4 | Officially supports **32 langs incl. Vietnamese** (up from 19 in Qwen2.5-VL); robust to blur/tilt; no VN-specific OCR number on card |
| **Reference (closed)** | Datalab Chandra ("Accurate") | proprietary | API or self-host | Datalab overall **1798**, vs dots.ocr **1489**, olmOCR 2 **1387**, DeepSeek-OCR **1336** — VN not in visible per-language tables |

Sources: [dots.ocr HF](https://huggingface.co/rednote-hilab/dots.ocr), [dots.ocr blog](https://github.com/rednote-hilab/dots.ocr/blob/master/assets/blog.md), [Qwen3-VL-8B-Instruct](https://huggingface.co/Qwen/Qwen3-VL-8B-Instruct), [PP-OCRv5 multilang docs](https://github.com/PaddlePaddle/PaddleOCR/blob/main/docs/version3.x/algorithm/PP-OCRv5/PP-OCRv5_multi_languages.en.md), [PaddleOCR 3.0 tech report (arXiv 2507.05595)](https://arxiv.org/html/2507.05595v1), [Datalab benchmark](https://www.datalab.to/benchmark/overall), [Tesseract VN issue #66](https://github.com/tesseract-ocr/langdata/issues/66), [pbcquoc/vietocr](https://github.com/pbcquoc/vietocr).

**dots.ocr / dots.mocr.** License **MIT** ✅, format **safetensors** ✅, built on Qwen2.5-VL, 3 B fits 8–12 GB. **dots.ocr-1.5 rebranded to `dots.mocr` on 2026-03-19** with higher scores (OmniDocBench Elo 1059 vs 1027, olmOCR-bench 83.9 vs 79.1) — if starting fresh, use dots.mocr. The 100-language bench doesn't break out Vietnamese; measure ourselves before quoting a VN number.

**Surya.** Datalab's flagship is now Chandra (proprietary). Surya remains open and supports 90+ langs incl. VN but is no longer the headline product.

**VietOCR (pbcquoc).** No commits visible in 2025–2026. Stable but dormant; no value-add over PP-OCRv5 today.

**PaddleOCR PP-OCRv5.** Native format `inference.pdmodel` + `inference.pdiparams` — binary but **not pickle** (passes principle 11). The Hán-Nôm fine-tune paper [arXiv 2510.04003](https://arxiv.org/html/2510.04003v1) (Oct 2025) shows the pipeline is extensible: **37.5 % → 50.0 %** on handwritten Hán-Nôm.

**Last 6 months.** **dots.ocr / dots.mocr** (Jul 2025 + Mar 2026 rebrand) — new default open-weight VLM-OCR; beats Mistral OCR / Nougat / GOT-OCR on OmniDocBench. **Qwen3-VL** (Nov 2025) — 19→32 supported languages; VN now officially in scope of a top open VLM. **PaddleOCR 3.0 tech report** consolidated multi-language story. Datalab pivoted to closed (Chandra). First academic OCR work on historical Hán-Nôm appeared.

**VN gotchas.** **Stacked diacritics** (ố, ự, ặ) are #1 error source — Tesseract worst, PP-OCRv5 and VLMs better. Confusion classes ơ/ô, ư/u, đ/d at low DPI — upsample scans to ≥300 DPI. Mixed-script (VN + EN + numbers + Hán-Nôm) trips language-locked engines; VLMs handle best. Old print / typewriter / handwritten — only VLMs and fine-tuned PaddleOCR work.

---

## Recommended pipeline (April 2026)

| Layer | **Fast** (CPU/4 GB) | **Default** (8–12 GB GPU) | **Accurate** (24 GB GPU) |
|---|---|---|---|
| **LLM** | `sail/Sailor2-1B` (Apache, ~2 GB) — VN-trained, CPU-feasible | **`Qwen/Qwen3-8B`** (Apache, Q4 ~5 GB) | `sail/Sailor2-20B` Q4 (~12 GB) **or** `Qwen3-32B` for monolingual reasoning |
| **Embedding** | `dangvantuan/vietnamese-embedding` (440 MB) **or** `hiieu/halong_embedding` (MRR@10 **0.8799** Zalo Legal) | **`AITeamVN/Vietnamese_Embedding`** (BGE-M3 ft, **+27.9 % Acc@1** vs BGE-M3) | `intfloat/e5-mistral-7b-instruct` (VN-MTEB **67.67**, Pair **84.01**) |
| **OCR** | PaddleOCR PP-OCRv5 (Apache, <100 MB) | **`rednote-hilab/dots.mocr`** (MIT, 3 B, safetensors) — beats Gemini-2.5-Pro on OmniDocBench-EN | `Qwen/Qwen3-VL-8B-Instruct` (Apache, VN officially supported) — joint OCR + reasoning |

### Concrete actions for nom-vn

1. **Embedding swap:** make `AITeamVN/Vietnamese_Embedding` the default; keep current as `lite`. **Fix the "BGE-M3 #1 at 64.90" claim in `BENCHMARK.md`** — actual #1 is m-e5-large-instruct at 67.99.
2. **LLM docs:** add `sail/Sailor2-8B` as documented "VN-tuned alternative." Drop Vistral pending license clarity.
3. **OCR rewrite:** current `BENCHMARK.md` lists VietOCR as default — stale. Replace with PP-OCRv5 → dots.mocr → Qwen3-VL-8B tiers.
4. **Verified-numbers debt:** for both dots.mocr and Qwen3-VL-8B we currently rely on adjacent (multilingual) evidence. Per principle 12, before publishing either as VN-recommended, run a best-of-N benchmark on a committed VN corpus and ship the script in `benchmarks/`.

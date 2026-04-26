# Training / fine-tuning recommendations for `nom-vn`

*Last updated: 2026-04-26.*

This document closes out the "improve current pipelines to maximum
accuracy first, then suggest tuning" workstream from the v0.2.5 → v0.2.11
push. It synthesises every measured bench and makes one clear call
per component: **train, fine-tune, distil, or do nothing.**

The bias is conservative. Before recommending a custom training run we
ask: (1) is there a measurable accuracy gap our users actually feel, and
(2) is that gap closeable with a public off-the-shelf model we haven't
tried yet? If either answer is "yes", training is premature.

## TL;DR

| Component | Current best | Gap to ideal | Recommendation | Cost estimate |
|---|---|---|---|---|
| Diacritic restoration | gemma3:4b 87.9% (local) / gpt-4o-mini 95.4% (cloud) | small (~7pp local→cloud) | **Distil a 100M-param VN diacritic model** | ~$10–30, 100k synthetic pairs |
| OCR (printed clean) | Tesseract `vie` 5.5% CER | none | **Do nothing.** Tesseract is 10× faster than VLM and 4× more accurate. | $0 |
| OCR (scanned / noisy / handwriting) | not measured in-house | likely large | **Fine-tune VietOCR on real scan corpus** when fix is unblocked | ~$80–150 (H100, 24h) |
| Word segmentation | underthesea CRF F1 95.7% | none | **Do nothing.** CRF is at its ceiling for this corpus. | $0 |
| Dense embedder | dangvantuan/vietnamese-embedding | none for general VN STS | **Do nothing.** Hits public SOTA at 440 MB. | $0 |
| Reranker | BAAI/bge-reranker-v2-m3 | none for general VN reranking | **Do nothing.** | $0 |
| BM25 | bm25s (Lucene formula) | n/a — algorithm, not model | **Do nothing.** | $0 |
| LLM for general VN tasks | gemma3:4b / gemma4:e4b / qwen3:8b | small | **Do nothing.** Multilingual base coverage is strong; fine-tuning cost ≫ marginal improvement. | $0 |

**Two training runs are recommended; everything else stays off-the-shelf.**

## Component-by-component analysis

### 1. Diacritic restoration → **distil a small VN model** (recommended)

**Measured:**

| Backend | Word acc | Disk | Notes |
|---|---:|---|---|
| Rule (built-in) | 41.06% | 0 | Vocabulary table |
| Cloud `gpt-4o-mini` | **95.37%** | — | $0.15/1M tokens, 1.27 s/sent |
| Local `gemma4:e4b` | 93.18% | 9.6 GB | 12 GB+ VRAM, ~10× too big for mobile |
| Local `gemma3:4b` | 87.90% | 3.3 GB | Recommended local default |
| Local `qwen3:1.7b` | 18.15% | 1.4 GB | Below rule baseline — too small |
| Local `gemma3:1b` | 15.32% | 0.8 GB | Below rule baseline |

**Gap:** the smallest off-the-shelf model that beats the rule baseline
(40%) is **3 GB+ on disk and needs 4 GB+ VRAM**. For mobile / browser
deployment that's a non-starter — both qwen3:1.7b and gemma3:1b fall
*below* the rule baseline, indicating the task requires VN orthographic
fluency that doesn't survive sub-2 GB compression.

**Why training fits here:** a focused diacritic-restoration task has a
narrow, well-defined output space (replace ASCII with a closed set of
diacritised forms). It's one of the few VN tasks where a **purpose-built
sub-100 M model can beat a general 8 B LLM**, because:

- The training signal is dense and free (any VN text → strip → restore).
- Small models with VN-only vocab don't need to allocate parameters for
  English / code / multilingual coverage.
- The output is character-level mostly-monotonic — a tiny seq2seq or
  even a token-classification head over a multi-label "diacritic mark
  per syllable" vocabulary suffices.

**Concrete plan:**

1. **Synthetic training pairs:** strip diacritics from 1–10 M sentences
   sourced from the corpora already in `benchmarks/data/` plus a public
   VN web crawl shard (OSCAR-23.01-vi or similar). 1 M pairs is enough
   for a sub-100 M model.
2. **Optional: distil from `gpt-4o-mini`.** For 100 K hard cases (legal /
   technical / proper-noun-heavy registers), get cloud-LLM gold labels.
   Total OpenAI cost ≈ $10 at current pricing, possibly less with prompt
   caching.
3. **Architecture: fine-tune `xlm-roberta-base` (~280 M)** with a
   token-classification head over a closed diacritic-mark vocabulary
   (~30 classes: none, acute, grave, hook, tilde, dot, plus combinations
   with ơ / ư / ă / â / ê / ô / đ). XLM-R has VN tokenization built in;
   one fine-tune epoch on 1 M pairs is enough.
4. **Alternative architecture:** distil-style smaller seq2seq from
   gemma3:4b's outputs (87.9% acc) into a 50 M-param T5-base. Strictly
   worse cap (≤87.9%) but smaller and CPU-fast.

**Expected outcome:** 92–95% accuracy at 250–500 MB on disk, sub-50 ms
on CPU. Fits in `nom-vn[diacritics]` extra without violating
CLAUDE.md principle 11 (safetensors, no pickle).

**Compute cost:** 1× H100 for ~6 h ≈ $20 on Lambda Cloud. Inference
cost: free (CPU OK).

**Why it's high leverage:** diacritic restoration is the entry-point for
VN OCR cleanup, search, voice-input correction. A fast local model
unlocks all three; the cloud / 9 GB local tradeoff today is bad for
edge deployment.

### 2. OCR (printed clean) → **do nothing**

**Measured** on first 50 images of `vn_ocr_subset` (real ducto489
mid-noise printed text):

| Engine | CER | Exact match | p50 ms |
|---|---:|---:|---:|
| **Tesseract 5 (`vie`)** | **5.53%** | **38.0%** | 80.6 |
| EasyOCR (`vi`) | 9.39% | 18.0% | 31.1 (GPU) |
| qwen2.5vl:7b | 31.07% | 18.0% | 818 |
| qwen2.5vl:3b | 39.86% | 15.0% | 1,165 |

**Gap:** none on this corpus. Tesseract beats everything. A VLM-OCR
finetune would chase a 1–2 pp gain at 10× more latency and 100× the
disk cost — a bad trade for printed clean VN.

**Recommendation:** keep Tesseract as the default for `nom.doc.ocr`.
Don't finetune anything for this slice.

### 3. OCR (scanned / noisy / handwriting) → **VietOCR fine-tune** (recommended, blocked)

**Status:** not measured in-house yet. VietOCR (`pip install vietocr`)
errors on Python 3.13 (`KeyError: '__version__'` in setup.py); upstream
needs a `pyproject.toml` modernisation. Once unblocked, the path is:

1. **Bench the off-the-shelf VietOCR weights** (`vgg_transformer`) on
   the same 50-image `vn_ocr_subset` slice for direct comparison with
   Tesseract.
2. **If VietOCR underperforms on noisy scans** (typical failure mode
   for any general OCR on tone marks below glyph baselines), fine-tune
   on a real scanned VN corpus. Promising sources:
   - `linhdoan/vietnamese-handwriting` (public on HF, ~10 k samples)
   - Internal Scopic scans where data licensing allows
3. Architecture: VietOCR ships VGG + Transformer encoder-decoder. One
   fine-tune epoch with augmentations (rotation, blur, contrast)
   typically gets 3–5 pp CER improvement on the target domain.

**Compute cost:** 1× H100 for ~24 h ≈ $80–150. Inference: GPU recommended.

**Why it's worth it (when unblocked):** scanned VN documents are a
real product workflow (legal, medical, banking). Tesseract's CER on
these is reportedly 12–15% (not measured here yet); pushing to <8% on
VN-specific scans is a measurable product win.

### 4. Word segmentation → **do nothing**

**Measured** on UD_Vietnamese-VTB test split (800 sentences, 11,692
gold tokens):

| Tokenizer | F1 | Throughput |
|---|---:|---:|
| `underthesea` 9.4.0 | **95.70%** | 38 k tok/s |
| `nom.text` (rule) | 76.46% | 747 k tok/s |

**Gap:** `nom.text` trails by 19 pp F1 but is 20× faster — the right
tradeoff for RAG indexing where tokens feed into a bag-of-words
retriever. `underthesea` is the right call when you need linguistic
accuracy.

A VN-specific BERT token-classification segmenter could push to 96–97%
F1, but underthesea already hits 95.70% — there's <2 pp of headroom and
a fine-tuned XLM-R head would be 280 MB on disk for that gain.
**Not worth the complexity.**

**Recommendation:** keep both backends, surface them per-use-case.
Document the tradeoff (already in `docs/benchmark.md` and on the
landing page once we update it).

### 5. Embedder → **do nothing**

`dangvantuan/vietnamese-embedding` (Apache 2.0, 440 MB, 768-dim) is
the current `nom.embeddings` default. It tops public VN STS leaderboards
at its size class and fine-tuning it on our internal corpus would
over-fit a small handful of registers without a measured benefit.

If we ever need a domain-specific embedder (e.g. legal Vietnamese
where we have a labelled dev set), the cheap path is:

- Mine triplets from the labelled set (anchor / positive / hard
  negative).
- Continue training the public model with `MultipleNegativesRanking
  Loss` for ~1 epoch.

But that's hypothetical until a labelled VN domain dataset materialises
internally. For v0.2.x: nothing to train.

### 6. Reranker → **do nothing**

`BAAI/bge-reranker-v2-m3` is multilingual SOTA. We measured its
contribution to VN legal-domain RAG quality and it's the right pick.
Training a VN-only reranker would require labelled hard-negative pairs,
which we don't have. Defer.

### 7. BM25 → **do nothing** (it's an algorithm)

`bm25s` (Lucene k1=1.5, b=0.75) is the ceiling for the BM25 family.
Nothing to train.

### 8. LLM for general VN tasks → **do nothing**

The `gemma3` / `gemma4` / `qwen3` families have good base VN coverage
(see local-LLM diacritic grid in `docs/benchmark.md`). Fine-tuning a
general LLM for "more Vietnamese" is a $1k+ run that delivers <5 pp
on most VN tasks vs the off-the-shelf base. The right unit of work is
**task-specific small models** (per §1) or **task-specific prompting**.

If a downstream task can't be done by the off-the-shelf LLMs at
acceptable quality after a serious prompt-engineering pass, that's the
moment to consider a LoRA — and the choice should be the smallest base
that the deployment target supports (gemma3:4b for laptops,
qwen3:1.7b only if mobile is a hard requirement and we accept the
quality cliff).

## Decision matrix — when to revisit

Each "do nothing" recommendation has a trigger that flips it:

| Component | Triggers a re-review |
|---|---|
| Diacritic restoration | If a sub-1 GB off-the-shelf VN diacritic model lands publicly with comparable accuracy, skip the distillation. |
| OCR (clean) | A new open-weight VN OCR model beats Tesseract by ≥3 pp CER at comparable latency. |
| OCR (scanned) | VietOCR Python 3.13 fix lands, OR a labelled scanned-VN corpus becomes available. |
| Word segmentation | A user reports a real bug that traces to the 19 pp F1 gap between `nom.text` and `underthesea` — until then, the speed/accuracy split is correct. |
| Embedder | A labelled VN STS / retrieval dataset for our domain emerges. |
| Reranker | Same as embedder — needs a domain dataset. |
| LLM | A task off-the-shelf can't cover; only LoRA the smallest viable base. |

## Process notes

- All measurements above come from scripts in `benchmarks/` runnable
  from a clean clone (CLAUDE.md §12 verified-benchmarks rule).
- Cross-checks against published numbers were done where the upstream
  reported them — diacritic accuracy vs. OpenAI's general
  capabilities; underthesea vs. its own VLSP 2013 numbers; Tesseract
  vs. published `vie` accuracy ranges. No silent disagreements.
- The PyVi auto-rejection (CLAUDE.md principle 11, ships `.pkl`) and
  the AGPL exclusions (PyMuPDF, Surya) constrain the recommendation
  surface and are reflected in the picks.

## References

- [`docs/benchmark.md`](benchmark.md) — full per-component bench
  numbers and methodology.
- [`docs/sota_vn_2026q2.md`](sota_vn_2026q2.md) — current SOTA picks
  per VN component.
- [`docs/oss_landscape_2026q2.md`](oss_landscape_2026q2.md) — OSS
  landscape borrow / avoid analysis.
- [`CHANGELOG.md`](../CHANGELOG.md) v0.2.5 → v0.2.12 entries.

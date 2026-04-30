# Training / fine-tuning recommendations for `nom-vn`

::: tip Tài liệu kỹ thuật
Trang này còn ở bản tiếng Anh — bản gốc dùng cho contributor quốc tế trên GitHub.
Đang được dịch dần sang tiếng Việt. Mọi con số trong trang là chính thức,
có script đo cam kết trong repo.
:::

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
| Diacritic restoration | **Toshiiiii1 T5 200M 97.81% (off-the-shelf) ⭐** | none (beats cloud by +2.44 pp) | **Adopt Toshiiiii1/Vietnamese_diacritics_restoration_5th.** Distil recommendation RETRACTED 2026-04-26. | $0 |
| OCR (printed clean) | Tesseract `vie` 5.5% CER | none | **Do nothing.** Tesseract is 10× faster than VLM and 4× more accurate. | $0 |
| OCR (scanned / noisy / handwriting) | not measured in-house | likely large | **Fine-tune VietOCR on real scan corpus** when fix is unblocked | ~$80–150 (H100, 24h) |
| Word segmentation | underthesea CRF F1 95.7% | none | **Do nothing.** CRF is at its ceiling for this corpus. | $0 |
| Dense embedder | bkai-foundation-models/vietnamese-bi-encoder ⭐ | none (public model wins by +41 pp R@1 over prior default) | **Adopt bkai** as the new default in 0.3.x. Available in 0.2.15 as opt-in `BKaiEmbedder`. | $0 |
| Reranker | BAAI/bge-reranker-v2-m3 | none for general VN reranking | **Do nothing.** | $0 |
| BM25 | bm25s (Lucene formula) | n/a — algorithm, not model | **Do nothing.** | $0 |
| LLM for general VN tasks | gemma3:4b / gemma4:e4b / qwen3:8b | small | **Do nothing.** Multilingual base coverage is strong; fine-tuning cost ≫ marginal improvement. | $0 |

**Updated 2026-04-26:** previously two training runs were recommended;
the diacritic distil was retracted after benching the off-the-shelf
candidate `Toshiiiii1` (97.81 % word acc at 1 GB, beats cloud
`gpt-4o-mini`). **Net: one training run remains** (VietOCR scan fine-tune,
still blocked on upstream Python 3.13 packaging fix).

## Component-by-component analysis

### 1. Diacritic restoration → **adopt `Toshiiiii1/Vietnamese_diacritics_restoration_5th`** (RETRACTED distil recommendation, 2026-04-26)

**The prior version of this section recommended distilling a 100 M-param
VN diacritic model.** That was wrong. We had not benched the public
Apache-licensed VN diacritic models on Hugging Face before making the
recommendation. The 2026-04-26 audit found one that wins on every
metric.

**The off-the-shelf finding — register-conditional (measured 2026-04-26):**

| Model | License | Disk | Word acc · 55-sent business | Word acc · 800-sent UD-VTB literary |
|---|---|---:|---:|---:|
| **`Toshiiiii1/Vietnamese_diacritics_restoration_5th`** | Apache 2.0 | ~1 GB | **97.81 %** | **54.14 %** |
| (cloud `gpt-4o-mini`) | proprietary | — | 95.37 % | not measured (likely high) |
| local `gemma4:e4b` Q4 | Apache 2.0 | 9.6 GB | 93.18 % | not measured |
| local `gemma3:4b` Q4 | Apache 2.0 | 3.3 GB | 87.90 % | not measured |
| (rule baseline) | — | 0 | 41.06 % | ~41 % (register-independent) |

**Toshiiiii1 T5 — 8 pp register-shift drop, not 43 pp** (corrected
2026-04-26). The first UD-VTB run was confounded by a tokenization
mismatch: UD ships sentences in treebank-tokenized form (spaces around
every punctuation mark, the parsing-tool convention) while seq2seq
models output natural Vietnamese. Comparing raw `.split()` lists
shifted the alignment at the first punctuation and produced
mathematically-impossible 0/800 sentence-exact. After
`normalize_punct()` on both sides:

  Business 55-sent corpus:    97.81 % word acc
  UD-VTB literary 800-sent:   89.40 % word acc · 34.25 % sentence-exact

The model is real-world useful on both registers; it's still register-
sensitive (8 pp gap) but mostly because of proper-noun ambiguity
(`Hùng` ↔ `Hưng` ↔ `Hứng`) and a few minor-register lexical choices,
not architectural failure. Lesson logged in our internal policy autonomous-loop
§5: implausible metrics (anything pegged at 0 % or 100 %) demand
investigation; multi-corpus measurement is mandatory for adoption.

**Register-conditional production guidance:**

| You're processing... | Use |
|---|---|
| OCR output, modern contracts, news, conversational web text | `HFDiacriticModel(Toshiiiii1)` — wins outright |
| Mixed register, classical, literary, or unknown distribution | Cloud `gpt-4o-mini` via `OpenAI()` adapter — most robust to register shift |
| Throughput-bound, tolerable error rate | Rule path — register-independent floor at ~41 % |

We should have spotted this earlier — running on `diacritic_eval_v0.txt`
alone (55 sentences) was test-set overfitting. our verified-benchmarks rule only
required warmup + best-of-N; for *quality* numbers it should also
require multi-corpus measurement when the candidate model has unknown
training distribution. Updated in the autonomous-loop §5.

**No training run is required.** Adopt the public model as the
production recommendation. Wired into `nom.text.fix_diacritics(model=...)`
via `HFDiacriticModel` adapter (v0.2.14). Install:
`pip install "nom-vn[diacritic-hf]"`.

**Process correction logged.** Per our multi-corpus register-coverage rule:
"off-the-shelf before training" — exhaustively bench public candidates
*before* recommending a fine-tune. We documented the user's catch and
added a project rule.

#### What we keep open as a future possibility

A **smaller** model (e.g. `xlm-roberta-base` token-classification head,
~280 MB on disk) could match Toshiiiii1's accuracy if it exists publicly
or is distilled. Not a priority while the 1 GB Toshiiiii1 model fits
the user-machine target. Re-review trigger: a public Apache/MIT diacritic
model lands at <500 MB with comparable accuracy.

#### Training experiments we ran 2026-04-27 (negative results)

Per the user's "publish if results look good" directive we tried two
fine-tuning runs on a 200 K-pair VN Wikipedia corpus
(`hirine/wikipedia-vietnamese-1M296K-dataset`, CC-BY-SA-4.0). Each ran
3 epochs on RTX 3090, bf16 + grad-checkpointing. Multi-corpus eval at
the end. Adoption gate: must beat Toshiiiii1 on at least one register
without losing >2 pp on the other. Neither run passed.

| Run | Base | Params | business_55 | literary_udvtb | Verdict |
|---|---|---:|---:|---:|---|
| Toshiiiii1 (off-the-shelf reference) | T5 (VN ft) | 200 M | **97.81 %** | 89.40 % | already adopted |
| #1 mT5-small / 200 K / 3 ep | mT5-small | 300 M total / 60 M VN | 89.58 % | 84.14 % | -8.23 pp / -5.26 pp — DON'T SHIP |
| #2 vit5-base / 200 K / 3 ep | VietAI/vit5-base | 220 M | 93.69 % | **89.47 %** | -4.12 pp / +0.07 pp — DON'T SHIP (gate not strict) |

**The interesting non-adoption finding:** run #2 (vit5-base) produces
the most **register-balanced** model — only **4.22 pp** business-literary
gap vs Toshiiiii1's **8.41 pp**. For users whose VN data is
mixed-register and who can tolerate sub-Toshiiiii1 absolute quality,
vit5-base would be the right pick. We don't publish it as the default
because the strict gate isn't met, but the methodology + training
scaffold ships in `training/diacritic/` so users can re-train for their
own register profile.

**Why we under-perform vs Toshiiiii1:**

1. **5× less training data** — Toshiiiii1 was likely trained on 1 M+
   pairs; we used 200 K to keep iteration cheap. Eval loss was still
   falling at end of training in both runs, indicating under-fit.
2. **3 epochs** is the typical T5 fine-tune budget; some references
   recommend 5-10 for diacritic restoration.
3. **mT5-small is the wrong base** — its shared multilingual embedding
   table dilutes VN-specific signal; vit5-base is purpose-built and
   already +4 pp better.

**Follow-up queue (deferred to v0.3.x):**

- Train vit5-base on 1 M pairs for 5+ epochs.
- Try `VietAI/vit5-large` (770 M) — bigger representation capacity.
- Try `google/byt5-small` (300 M, char-level, robust to register noise
  per [arXiv:2201.13242](https://arxiv.org/abs/2201.13242)).
- Multi-task: diacritic + spelling correction in one head.

None is a sure win; each costs 2-5 hours of GPU. Decision deferred
because Toshiiiii1 covers v0.2.x production and the strategic value of
"owning" a worse model is negative.

(Original distil-recommendation rationale, kept for context:)



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
our no-pickle policy (safetensors, no pickle).

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

### 5. Embedder → **switch default to bkai-foundation-models/vietnamese-bi-encoder** (RETRACTED "do nothing", 2026-04-26)

The prior version of this section said "do nothing — `dangvantuan/
vietnamese-embedding` is public SOTA at its size class". That was
true *for STS*. We had not measured retrieval recall on the actual
RAG task. The 2026-04-26 audit corrected this.

Measured on Zalo Legal QA (5,061 docs, 80 questions, RTX 3090):

| Model | License | Disk | R@1 | R@10 | MRR@10 |
|---|---|---:|---:|---:|---:|
| **`bkai-foundation-models/vietnamese-bi-encoder`** | Apache 2.0 | 383 MB | **76.25 %** | **98.75 %** | **0.8604** |
| `dangvantuan/vietnamese-embedding` (was default) | Apache 2.0 | 440 MB | 35.00 % | 67.50 % | 0.4449 |

bkai wins by **+41.25 pp R@1, +31.25 pp R@10** in smaller disk size.
Architectural: bkai trained with `MultipleNegativesRankingLoss` on
Q→Doc retrieval pairs; dangvantuan trained on STS pairs (symmetric
similarity). The training distribution mismatch is the headline.

**Action:** v0.2.15 ships `nom.embeddings.BKaiEmbedder` as opt-in. The
0.3.x major release will switch the default. Mid-version cache
invalidation is bad UX — existing users' persisted vector indexes were
built on dangvantuan and would silently drop in quality if we flipped
the default mid-stream.

**Catch:** bkai requires `underthesea` word-segmenter preprocessing
(multi-syllable VN words joined with underscores). Already an opt-in
extra in `nom-vn[nlp]`; the BKaiEmbedder class handles this internally.

#### Still don't fine-tune

The public bkai model already beats every alternative we benched.
Domain-specific finetuning would target a marginal +2-5 pp gain on a
specific corpus (legal-VN, medical-VN, etc.) at the cost of a labelled
dev set + training run. Hypothetical until a labelled in-domain corpus
materialises.

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
  from a clean clone (our verified-benchmarks rule verified-benchmarks rule).
- Cross-checks against published numbers were done where the upstream
  reported them — diacritic accuracy vs. OpenAI's general
  capabilities; underthesea vs. its own VLSP 2013 numbers; Tesseract
  vs. published `vie` accuracy ranges. No silent disagreements.
- The PyVi auto-rejection (our no-pickle policy, ships `.pkl`) and
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

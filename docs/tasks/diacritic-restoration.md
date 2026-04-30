# Diacritic restoration (Vietnamese)

Restore tone marks and vowel modifiers on Vietnamese text written
without them: `Toi yeu Viet Nam` → `Tôi yêu Việt Nam`. The single most
common pre-processing step on noisy VN text (OCR output, foreign
keyboards, social-media short-form, untyped Telex sequences).

## TL;DR — our recommendation

```bash
pip install "nom-vn[diacritic-hf]"   # transformers<5 + torch + sentencepiece
```

```python
from nom.text.diacritic_models import HFDiacriticModel
restorer = HFDiacriticModel()  # Toshiiiii1 default, lazy-loads on first call
restorer("Toi yeu Viet Nam")    # 'Tôi yêu Việt Nam'

# Batched (7.6× throughput on a 3080)
restorer.predict_batch(sentences, batch_size=16)
```

The default model is `Toshiiiii1/Vietnamese_diacritics_restoration_5th`
(Apache 2.0, T5 200 M, safetensors) — public SOTA on the 4-register
matrix. For corpora skewed toward formal / legal-prose / conversational
Vietnamese, our [`nrl-ai/vn-diacritic-vit5-base`](https://huggingface.co/nrl-ai/vn-diacritic-vit5-base)
is +1.43 pp on formal / +0.22 pp on conversational at the same arch
size + license.

## Public landscape — measured 2026-04-30

| Model | License | Format | business 55 | literary 800 | conv 300 | formal 72 | Verdict |
|---|---|---|---:|---:|---:|---:|---|
| [`Toshiiiii1/Vietnamese_diacritics_restoration_5th`](https://huggingface.co/Toshiiiii1/Vietnamese_diacritics_restoration_5th) | Apache 2.0 | safetensors | **97.81 %** | **89.40 %** | 93.94 % | 98.14 % | ⭐ public SOTA, current default |
| **[`nrl-ai/vn-diacritic-vit5-base`](https://huggingface.co/nrl-ai/vn-diacritic-vit5-base)** (ours) | Apache 2.0 | safetensors | 93.44 % | 89.39 % | **94.16 %** | **99.57 %** | best register-balanced; pick for legal / conversational |
| `qthuan2604/ViT5_Restore_Diacritics_Vietnamese` | MIT | bin | 90.59 % | — | — | — | weaker than ours; skip |
| `qthuan2604/BARTPho_Syllable_Restore_Diacritics_Vietnamese` | MIT | safetensors | 83.92 % | — | — | — | weakest of audited; skip |
| `yammdd/vietnamese-diacritic-restoration-v2` | MIT | tf_model.h5 | not benched | — | — | — | TF-only; conversion overhead, defer |
| Rule-based table (`nom.text.fix_diacritics`) | Apache 2.0 | none | 41.06 % | — | — | — | zero-deps fallback |
| Local LLM (`gemma3:4b` Q4 via Ollama) | Apache 2.0 | gguf | — | — | — | — | 87.90 % on `diacritic_eval_v0` mixed; ~1 s/sentence |
| Cloud LLM (`gpt-4o-mini`) | proprietary | — | 95.37 % | — | — | — | beats cost only when batch is small |

8.7 pp register-spread on Toshiiiii1 confirms it's register-overfit
toward modern formal/business Vietnamese. Our `vit5-base` fine-tune
trades 4 pp of business for ~1.4 pp gain on formal and a tied
literary score — the right choice for legal / chat / OCR corpora.

JSON baselines: `benchmarks/results/baseline_diacritic_*.json`.

## Our pipeline

`nom.text.fix_diacritics` is a Protocol-based seam: any callable
mapping `str -> str` plugs in.

```python
from nom.text import fix_diacritics
from nom.text.diacritic_models import HFDiacriticModel

# Default Toshiiiii1
fix_diacritics("Hop dong nay duoc lap", model=HFDiacriticModel())

# Our register-balanced fine-tune
fix_diacritics(
    "Hop dong nay duoc lap",
    model=HFDiacriticModel(model_id="nrl-ai/vn-diacritic-vit5-base"),
)

# Or via Ollama LLM
from nom.llm import Ollama
fix_diacritics("Hop dong nay duoc lap", llm=Ollama(model="gemma3:4b"))

# Or zero-deps rule-based (best-effort only)
fix_diacritics("Hop dong nay duoc lap")
```

`HFDiacriticModel` exposes `predict()` (single sentence) and
`predict_batch()` (padded batched inference, **7.60× throughput**
measured on a 3080 16 GB Mobile, 120/120 quality match against the
single-call path).

## Trained models — `nrl-ai/*`

| HF model | License | Params | Disk | When to pick |
|---|---|---|---:|---|
| [`nrl-ai/vn-diacritic-vit5-base`](https://huggingface.co/nrl-ai/vn-diacritic-vit5-base) | Apache-2.0 | 220 M (ViT5-base) | 900 MB | register-balanced — best for formal / conversational corpora |

**Δ vs Toshiiiii1 (the public SOTA we benchmark against):**

| Register | Toshiiiii1 | nrl-ai/vit5-base | Δ |
|---|---:|---:|---:|
| `formal_udhr` | 98.14 % | **99.57 %** | **+1.43 pp** |
| `business_55` | **97.81 %** | 93.44 % | -4.37 pp |
| `conversational_300` | 93.94 % | **94.16 %** | **+0.22 pp** |
| `literary_udvtb` | **89.40 %** | 89.39 % | -0.01 pp (tied) |

Strict adoption gate (business ≥ 96 % AND literary > 89.40 %) **fails**
on business — so this is **not** the canonical name `nrl-ai/vn-diacritic-restoration`
(that's reserved for a future gate-passing model). It's published under
its arch-explicit name as the register-balanced alternative for users
who care about formal / conversational accuracy.

**Planned tiers** (see [training README](../../training/diacritic/README.md)):

| Tier | Base | Status |
|---|---|---|
| `nrl-ai/vn-diacritic-base` | ViT5-base or larger | TBD — pending v6 / v7 mixed-source experiment |
| `nrl-ai/vn-diacritic-small` | ViT5-small (60 M) | queued — same recipe, ~3× faster |
| `nrl-ai/vn-diacritic-nano` | distilled (10-30 M) | future, after base+small are validated |

## Datasets — `nrl-ai/*`

Both verified renderable + loadable via `datasets.load_dataset`.

| HF dataset | License | What it is |
|---|---|---|
| [`nrl-ai/vn-diacritic-eval`](https://huggingface.co/datasets/nrl-ai/vn-diacritic-eval) | CC-BY-SA-4.0 (most restrictive of constituents) | 4-register evaluation grid: business_55 (CC0), formal_72 (PD UDHR), conversational_300 (CC-BY 2.0 Tatoeba), literary_800 (CC-BY-SA 4.0 UD-VTB). 1,227 sentence pairs total. |
| [`nrl-ai/vn-diacritic-train`](https://huggingface.co/datasets/nrl-ai/vn-diacritic-train) | CC-BY-SA-4.0 (per-config per `wiki_500k`=CC-BY-SA, `news_150k`=CC-BY-4.0) | 500K Wikipedia + 150K NFC-fixed VN news training pairs. Eval-leak guarded against `vn-diacritic-eval`. NFC-normalized at write time. |

```python
from datasets import load_dataset

# Evaluate any model against the same 4-register grid
ds = load_dataset("nrl-ai/vn-diacritic-eval", "business_55", split="train")

# Train your own — the same data we used for nrl-ai/vn-diacritic-vit5-base
wiki = load_dataset("nrl-ai/vn-diacritic-train", "wiki_500k", split="train")
news = load_dataset("nrl-ai/vn-diacritic-train", "news_150k", split="train")
```

## Results — measured

All numbers reproducible on a clean clone via the bench scripts under
`benchmarks/accuracy/` and `training/diacritic/eval_checkpoint.py`.
RTX 3080 16 GB Mobile / RTX 3090 measurements, NFC + punctuation
normalization on both sides of comparison, 3-call warmup, num_beams=1.

| Register | Sentences | Toshiiiii1 (ms/sent) | nrl-ai/vit5-base (ms/sent) |
|---|---:|---:|---:|
| `formal_udhr` | 72 | 245 | 272 |
| `business_55` | 55 | 119 | 147 |
| `conversational_300` | 300 | 91 | 101 |
| `literary_udvtb` | 800 | 137 | 156 |

Latency dominated by ViT5's 220 M decoder; both models run on the same
arch family. For 7.6× throughput on either, use `predict_batch`.

JSON baselines:

- `benchmarks/results/baseline_diacritic_toshiiiii_4register.json` (Toshiiiii1)
- `benchmarks/results/baseline_diacritic_toshiiiii_t5.json`, `..._tatoeba300.json`, `..._udhr72.json`, `..._udvtb_test.json` (per-register)
- `training/diacritic/results/vit5-base-500k-cosine-full_summary.json` (our fine-tune)
- `training/diacritic/results/vit5-base-500k-cosine-full_eval_local.json` (local re-eval, ±0.12 pp reproducible)
- `benchmarks/results/baseline_diacritic_qthuan_*.json` (audited candidates)

## Reproduce

```bash
# 1. Build eval slices (deterministic, no network)
python benchmarks/data/tatoeba_vi/build_diacritic_eval.py
python benchmarks/data/udhr_vi/build_diacritic_eval.py

# 2. Run the 4-register eval against any HF model
python training/diacritic/eval_checkpoint.py \
    --checkpoint Toshiiiii1/Vietnamese_diacritics_restoration_5th \
    --output-json benchmarks/results/baseline_diacritic_toshiiiii_4register.json

python training/diacritic/eval_checkpoint.py \
    --checkpoint nrl-ai/vn-diacritic-vit5-base \
    --output-json benchmarks/results/baseline_diacritic_vit5_base_4register.json
```

## Training

The full training pipeline is under [`training/diacritic/`](../../training/diacritic/):

- `prep_data.py` — Wikipedia stream → filtered (input, target) pairs (NFC, eval-leak guarded).
- `prep_data_news.py` — same for `tmnam20/Vietnamese-News-dedup` (CC-BY-4.0, NFC-fixed).
- `train.py` — HF `Seq2SeqTrainer` with cosine LR, optional early stopping, 4-register post-training eval.
- `eval_checkpoint.py` — standalone re-eval given a checkpoint dir or HF repo id.
- `publish_hf.py` — gate-checked HF Hub publishing with auto-generated model card.
- `post_train.sh` — rsync from the GPU training box → local re-eval (>0.5 pp divergence fails) → publish dry-run.

Experiment history (5 runs to date) in [`training/diacritic/README.md`](../../training/diacritic/README.md).

## Vietnamese-specific gotchas hit during this work

- **NFC vs NFD.** `tmnam20/Vietnamese-News-dedup` ships ~79 % NFD-decomposed
  text. An earlier mixed-source run trained on it; the model emitted
  decomposed combining marks that NFC eval byte-compare missed →
  **-15.45 pp catastrophic regression** on business register. Now
  NFC-normalized at three layers (prep, prep-news, train preprocess).
- **Early stopping on noisy small eval.** `--early-stopping-patience 3`
  with 200-sample eval set fired at epoch 0.96 of v3 — the model never
  converged. Now default `--eval-samples 1000` and recommend
  `--early-stopping-patience 0` for full-budget training runs.
- **Punctuation normalization for byte-equal sentence-match.**
  UD-VTB ships sentences with spaces around every punctuation mark
  (treebank convention); modern seq2seq output has attached punctuation.
  Bench scripts now `normalize_punct()` both sides before comparison —
  caught a "0/800 sentence-exact" false negative in v0.2.17.
- **Proper-noun ambiguity.** `Hung` → `Hùng` / `Hưng` / `Hứng`
  (different real names). The model picks training-frequency winner;
  not always right for the input. Document NER+lookup separately for
  use cases that need the gold proper noun.

## References

- Toshiiiii1 model card: <https://huggingface.co/Toshiiiii1/Vietnamese_diacritics_restoration_5th>
- Our fine-tune: <https://huggingface.co/nrl-ai/vn-diacritic-vit5-base>
- ViT5 paper: Phan et al., NAACL-SRW 2022, <https://aclanthology.org/2022.naacl-srw.18>
- ByT5 (canonical char-level VN diacritic SOTA in literature): Xue et al., 2022, <https://arxiv.org/abs/2201.13242>
- Wikipedia training corpus: <https://huggingface.co/datasets/hirine/wikipedia-vietnamese-1M296K-dataset>
- News training corpus: <https://huggingface.co/datasets/tmnam20/Vietnamese-News-dedup>
- VSEC paper (error taxonomy used by `nom.text.noise`): Do et al., PRICAI'21, <https://arxiv.org/abs/2111.00640>

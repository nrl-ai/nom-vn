# Spell correction (Vietnamese)

Fix typos, missed accents, and OCR-style char errors in Vietnamese
text in one pass: `Toi yu Vit Nam` → `Tôi yêu Việt Nam`. Strictly more
than diacritic restoration (which only adds tone marks) — spell
correction also fixes letter-level mistakes, missing/extra characters,
and common OCR substitutions like `o↔0`, `l↔1`, `m↔rn`.

## TL;DR — our recommendation

```bash
pip install "nom-vn[diacritic-hf]"   # transformers<5 + torch + sentencepiece
```

```python
# Same Protocol seam as diacritic restoration — pass our trained model
# to fix_diacritics with model=. (Spell correction is a strict superset
# of diacritic restoration, so the same Protocol works.)
from nom.text import fix_diacritics
from nom.text.diacritic_models import HFDiacriticModel

restorer = HFDiacriticModel(model_id="nrl-ai/vn-spell-correction-base")
out = fix_diacritics("Hop dong nay duoc lap ngay 14/3/2025", model=restorer)
# 'Hợp đồng này được lập ngày 14/3/2025'
```

## Public landscape — measured 2026-04-30

| Model | License | Format | light avg | heavy avg | Verdict |
|---|---|---|---:|---:|---|
| [`bmd1905/vietnamese-correction-v2`](https://huggingface.co/bmd1905/vietnamese-correction-v2) | Apache 2.0 | safetensors | 86.7 % | 72.6 % | best non-trained baseline; mBART 400M |
| [`iAmHieu2012/vit5-vietnamese-spelling-correction`](https://huggingface.co/iAmHieu2012/vit5-vietnamese-spelling-correction) | MIT | safetensors | not benched | not benched | tokenizer needs slow→fast conversion; deferred |
| [`chamdentimem/ViT5_Vietnamese_Correction`](https://huggingface.co/chamdentimem/ViT5_Vietnamese_Correction) | MIT | safetensors | not benched | not benched | similar to iAmHieu, deferred |
| Rule-based (no spell-correct path) | — | — | — | — | The rule-only path in `nom.text.fix_diacritics` does diacritic restoration only — no letter-level fixes. |

bmd1905 details across 8 splits:

| Register | light | heavy |
|---|---:|---:|
| business_55 | 91.18 % | 76.97 % |
| formal_72 | 83.46 % | 73.37 % |
| conversational_300 | 84.72 % | 73.63 % |
| literary_800 | 87.42 % | 66.53 % |

Reproduce: `python benchmarks/accuracy/bench_spell_correction_hf.py
bmd1905/vietnamese-correction-v2 --json benchmarks/results/baseline_spell_bmd1905_v2.json`.
JSON baseline committed at `benchmarks/results/baseline_spell_bmd1905_v2.json`.

## Our pipeline

`nom.text.fix_diacritics` accepts any seq2seq model via `model=`; our
spell-correction models drop in under that same Protocol. The
`HFDiacriticModel` adapter loads them lazily from HF Hub.

```python
from nom.text.diacritic_models import HFDiacriticModel

# Spell-correction default (after publish)
spell = HFDiacriticModel(model_id="nrl-ai/vn-spell-correction-base")
spell("Toi yu Vit Nam, dat nuoc tuyet voi")     # 'Tôi yêu Việt Nam, đất nước tuyệt vời'

# Same batched inference path for high throughput
spell.predict_batch(noisy_sentences, batch_size=16)
```

Same `predict()` / `predict_batch()` interface as the diacritic models.

## Trained models — `nrl-ai/*`

The base + small tier convention from diacritic carries over: same
500K training corpus, same epochs / LR / hyperparameters across both
tiers (small models are NOT less data-hungry than big ones — Chinchilla
scaling shows the opposite, so we deliberately train both on the same
big mix).

| HF model | License | Base | Params | Disk | Status |
|---|---|---|---:|---:|---|
| [`nrl-ai/vn-spell-correction-base`](https://huggingface.co/nrl-ai/vn-spell-correction-base) | Apache-2.0 | ViT5-base (MIT) | 220 M | 900 MB | shipped (v0.2.28) |
| `nrl-ai/vn-spell-correction-small` | Apache-2.0 | BARTpho-syllable (MIT) | 115 M | 530 MB | training |

### v0.2.28 base — measured on the 8-split grid

| Split | Word acc | Sentence exact | ms/sent |
|---|---:|---:|---:|
| business_55_light | **98.58 %** | 79.55 % | 147 |
| business_55_heavy | **98.33 %** | 81.82 % | 145 |
| formal_72_light | **99.80 %** | 95.38 % | 288 |
| formal_72_heavy | **99.19 %** | 84.72 % | 274 |
| conversational_300_light | **97.90 %** | 83.24 % | 107 |
| conversational_300_heavy | **96.18 %** | 76.31 % | 103 |
| literary_800_light | **98.02 %** | 77.47 % | 171 |
| literary_800_heavy | **95.71 %** | 61.04 % | 160 |

**Light avg: 98.58 % · Heavy avg: 97.35 %** (gate: light ≥ 92, heavy ≥ 80 — passes with wide margin).

> **Honest caveat: these numbers are in-distribution.** The eval grid
> applies the same `nom.text.noise` presets to clean text that the
> model was trained on (different seeds, same generator). The model
> has implicitly learned the inverse of *our* noise distribution.
> Real-world Vietnamese typos follow different statistics — see the
> OOD measurements below.

### Out-of-distribution real-world bench (measured 2026-04-30)

`benchmarks/data/spell_correction_eval_real/` is a 100-sentence
hand-curated set whose noise patterns come from real VN error sources,
NOT `nom.text.noise`. v0.2.28 base measured against it:

| Slice | Source of noise | Word acc | Sent. exact |
|---|---|---:|---:|
| `forum_25` | Forum/social-media teen-code | 59.45 % | 0.0 % |
| `mobile_25` | Phone autocorrect mishaps | 95.01 % | 40.0 % |
| `telex_real_25` | Real Telex/VNI keystrokes | **17.38 %** | 0.0 % |
| `ocr_25` | Tesseract/EasyOCR engine output | 93.62 % | 60.0 % |
| **aggregate** | n=100 | **66.88 %** | 25.0 % |

The synthetic eval shows 98.58 % (light avg). The real-world OOD eval
shows 66.88 % aggregate. **The 32 pp gap is the overfit cost** — the
v1 corpus trained the model to invert `light_noise` /
`telex_typo_noise` / `heavy_noise`, which capture the *surface* of
Vietnamese typos but not the keystroke artefacts of real Telex (`dduwojc`
for `được`) or the abbreviation-heavy syntax of forum slang (`ko bt`
for `không biết`). On those, the model has near-zero training signal
and collapses.

OCR and mobile-autocorrect slices stay close to in-distribution (94 %
and 95 %), because those error patterns are well-represented by
`heavy_noise` and the diacritic-strip distribution.

**This is exactly what the v2 corpus + `comprehensive_noise()` fixes**
— adding `telex_grammar_noise()` (real keystroke errors) and
`mobile_noise()` (teen-code + adjacent-key) to the training mix should
close most of this gap. v0.2.29 retraining on the v2 corpus is queued.

Reproduce:
```bash
python benchmarks/accuracy/bench_spell_correction_real.py \
    nrl-ai/vn-spell-correction-base \
    --json benchmarks/results/real_spell_correction_base.json
```

Confidence intervals on the smaller splits (business_55, formal_72) are
±3-4 pp at 95 %. The 25-sentence real-world slices are even noisier
(±9 pp at 95 %) — treat them as a directional smell-test.

Local re-eval reproduces remote within ±0.03 pp on every split. Trained on
the [same 500K mixed Wiki+news corpus](https://huggingface.co/datasets/nrl-ai/vn-spell-correction-train)
with `light_noise` / `telex_typo_noise` / `heavy_noise` round-robin
applied. 5 epochs cosine LR. 180 min on a single RTX 3090.

### Δ vs the public landscape (light_avg / heavy_avg)

| Model | light avg | heavy avg | Δ vs ours base |
|---|---:|---:|---:|
| **`nrl-ai/vn-spell-correction-base`** (ours) | **98.58 %** | **97.35 %** | — |
| `bmd1905/vietnamese-correction-v2` (400 M) | 86.95 % | 72.62 % | **-11.6 / -24.7** pp |
| `iAmHieu2012/vit5-vietnamese-spelling-correction` (220 M) | 80.31 % | 56.55 % | **-18.3 / -40.8** pp |

Our base wins every split by 7-29 pp. The size advantage of bmd1905
(400M vs our 220M) doesn't matter — the targeted fine-tune on the
8-register noise distribution dominates a generic correction model.

## Datasets — `nrl-ai/*` (queued)

The training and eval datasets will be published once both tiers ship,
following the same convention as the diacritic datasets:

- `nrl-ai/vn-spell-correction-eval` — 2,098 (noisy, clean) pairs
  across 4 registers × 2 noise levels (light + heavy). Generated
  deterministically from the diacritic eval slices via
  `nom.text.noise`.
- `nrl-ai/vn-spell-correction-train` — 459K (noisy, clean) training
  pairs. The clean side is the same 500K mixed Wiki+news as
  `nrl-ai/vn-diacritic-train`; the noisy side comes from the
  round-robin `light_noise` / `telex_typo_noise` / `heavy_noise`
  presets.

## Results — measured

Pending. Will be filled in when training completes. JSON baseline path:
`training/spell_correction/results/<run-id>_summary.json`.

## Reproduce

```bash
# 1. Build the eval grid (deterministic, no network)
python benchmarks/data/spell_correction_eval/build.py

# 2. Build the training corpus (uses nom.text.noise on the existing
#    500K diacritic-training mixed corpus)
python training/spell_correction/prep_data.py --max-pairs 500_000

# 3. Bench any off-the-shelf HF spell-correction model
python benchmarks/accuracy/bench_spell_correction_hf.py \
    bmd1905/vietnamese-correction-v2 \
    --json benchmarks/results/baseline_spell_bmd1905_v2.json

# 4. Train base on the remote GPU (TRAIN_HOST=genpc2 default)
./training/spell_correction/launch_genpc2.sh \
    --model-id VietAI/vit5-base \
    --epochs 5 --batch-size 32 --bf16 \
    --lr 5e-4 --lr-scheduler cosine \
    --warmup-steps 500 --early-stopping-patience 0 \
    --eval-steps 2000 --save-steps 2000 --eval-samples 1000 \
    --output-dir training/spell_correction/checkpoints/vit5-base-500k

# 5. Train small on the same corpus
./training/spell_correction/launch_genpc2.sh \
    --model-id vinai/bartpho-syllable-base \
    --epochs 5 --batch-size 32 --bf16 \
    --lr 5e-4 --lr-scheduler cosine \
    --warmup-steps 500 --early-stopping-patience 0 \
    --eval-steps 2000 --save-steps 2000 --eval-samples 1000 \
    --output-dir training/spell_correction/checkpoints/bartpho-syllable-500k
```

## How the noise generator works

Spell correction needs `(noisy, clean)` training pairs. License-clean
real-world pairs are scarce (most public corpora are research-only).
We synthesize from clean text using `nom.text.noise` (shipped as part
of `nom-vn`):

```python
from nom.text.noise import NoiseGenerator, light_noise

gen = NoiseGenerator(light_noise(), seed=42)
print(gen.noisify("Tôi yêu Việt Nam và đất nước này tuyệt vời."))
# 'Toi yêu Viet Nam và đất nước này tuyệt vời.'
```

Ten noise dimensions and seven calibrated presets:

| Preset | Models |
|---|---|
| `light_noise()` | Casual desktop typing; ~5 % edit distance. |
| `heavy_noise()` | Mid-quality OCR; ~15-20 % edit distance. |
| `telex_typo_noise()` | Surface effects of Telex/VNI input slips. |
| `telex_grammar_noise()` | Real Telex-keystroke errors (drop / wrong / doubled tone letters). |
| `mobile_noise()` | Phone thumbs typing: adjacent-key slips + teen-code abbreviations + segmentation. |
| `ocr_realistic_noise()` | Scanned-document OCR: heavy diacritic loss + char confusion + segmentation. |
| `comprehensive_noise()` | All ten dimensions at moderate probabilities. Used as the default for v2 corpora where the model needs to generalize across many typo classes. |

Deterministic via seed; NFC-normalized output (the silent-killer NFD
trap that poisoned an earlier mixed-source diacritic run is locked out
at every layer); edit budget capped so high-probability configs don't
mangle inputs beyond recoverability. See
[`docs/recipes.md`](../recipes.md#synthesize-noisy-vietnamese-text-for-spell-correction-training-data)
for the full recipe.

### v2 multi-source training corpus (queued for v0.2.29)

The v1 corpus pulls only from Wiki + news; the v2 corpus
(`training/spell_correction/prep_data_v2.py`) adds a legal-register
slice from `GreenNode/zalo-ai-legal-text-retrieval-vn` (MIT) and
applies all seven presets via round-robin plus a `comprehensive_noise`
slot. Default mix at 600K pairs:

| Slot | Source | Quota | Noise |
|---|---|---:|---|
| mixed | Wiki+news (v1 base, NFC) | 65 % | round-robin over 6 presets |
| legal | Zalo Legal QA corpus, MIT | 25 % | round-robin over 6 presets |
| comprehensive_only | Wiki+news (NFC) | 10 % | always `comprehensive_noise` |

This widens register coverage (legal Vietnamese has distinct vocabulary
the v1 corpus underexposed) and trains the model on more failure
modes per pair. Re-run via:

```bash
# 1. Build legal corpus (~1 min stream from HF, 100K pairs)
python training/diacritic/prep_data_legal.py --max-pairs 100_000
cp training/diacritic/data/train_legal.jsonl \
   training/diacritic/data/train_legal_nfc.jsonl

# 2. Build the v2 spell-correction corpus
python training/spell_correction/prep_data_v2.py --max-pairs 600_000
```

## References

- VSEC paper (canonical VN spell-correction benchmark + error taxonomy):
  Do et al., PRICAI 2021, <https://arxiv.org/abs/2111.00640>
- BARTpho paper: Tran et al., INTERSPEECH 2022,
  <https://aclanthology.org/2022.interspeech-1.45/>
- ViT5 paper: Phan et al., NAACL-SRW 2022,
  <https://aclanthology.org/2022.naacl-srw.18>
- bmd1905 model card: <https://huggingface.co/bmd1905/vietnamese-correction-v2>

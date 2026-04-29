# Training a Vietnamese diacritic-restoration model

## Why we're training

The 2026-04-29 4-register audit measured
[`Toshiiiii1/Vietnamese_diacritics_restoration_5th`](https://huggingface.co/Toshiiiii1/Vietnamese_diacritics_restoration_5th)
(Apache 2.0, T5 200 M, safetensors) at:

| Eval corpus | Sents | Word acc |
|---|---:|---:|
| `udhr_vi/diacritic_eval_udhr.txt` (formal/legal-prose) | 72 | 98.14 % |
| `diacritic_eval_v0.txt` (business/news) | 55 | 97.81 % |
| `tatoeba_vi/diacritic_eval_300.txt` (conversational) | 300 | 93.77 % |
| `ud_vi_vtb/test.conllu` (classical literary) | 800 | 89.40 % |

8.74 pp spread, monotonic gradient. Toshiiiii1 is the strongest
off-the-shelf option but it's register-overfit toward modern
formal/business Vietnamese. Training a model that closes the gap on
literary while not regressing on business is the goal.

## Experiment history

| Run | Base | Pairs | Epochs | LR sched | Business | Literary | Verdict |
|---|---|---|---|---|---:|---:|---|
| v0.2.22 | google/mt5-small (300 M) | 200 K | 3 | linear | 89.58 | 84.14 | failed gate by wide margin |
| v0.2.23 | VietAI/vit5-base (220 M) | 200 K | 3 | linear | 93.69 | 89.47 | most register-balanced, sub-gate on business |
| **v0.2.24 (running)** | VietAI/vit5-base | **500 K** | **5** | **cosine** | TBD | TBD | data + schedule scaled |

Adoption gate (both required):

- `business_55.word_accuracy >= 0.96` (within 2 pp of Toshiiiii1)
- `literary_udvtb.word_accuracy > 0.8940` (strictly above Toshiiiii1)

Eval covers the full 4-register matrix per CLAUDE.md autonomous-loop §5
(Tatoeba conversational + UDHR formal added 2026-04-29).

## Architecture choice

For the active v0.2.24 run we use [`VietAI/vit5-base`](https://huggingface.co/VietAI/vit5-base)
(MIT, safetensors, ~220 M params). Reasons:

1. **Best register-balance from prior runs.** v0.2.23 hit a 4.22 pp
   business-literary gap vs Toshiiiii1's 8.41 pp — the smallest gap of
   any candidate we benched.
2. **VN-specialized.** ViT5 is pre-trained on the same 1.5 TB CC100
   Vietnamese corpus that Toshiiiii1 ultimately benefits from too.
3. **Smaller dependency surface.** mT5's multilingual embedding table
   is dead weight for VN-only inference.

ByT5-small (300 M, char-level, robust to typos per
[arXiv:2201.13242](https://arxiv.org/abs/2201.13242)) is the canonical
SOTA for VN diacritic restoration in the literature, but needs ~4× longer
sequences (it's byte-level) and is queued for v0.2.25 only if v0.2.24
fails the gate.

## Data

`benchmarks/data/diacritic_eval_v0.txt` and
`benchmarks/data/ud_vi_vtb/test.conllu` are **held out** — both are
public eval corpora and we MUST NOT include their sentences in
training. `prep_data.py` enforces this via a hash-set check.

Source: [`hirine/wikipedia-vietnamese-1M296K-dataset`](https://huggingface.co/datasets/hirine/wikipedia-vietnamese-1M296K-dataset)
(CC-BY-SA-4.0, ~1.3 M Wikipedia articles, light cleaning applied
upstream — wiki templates and `<ref>` tags removed).

Pipeline:

1. Stream the dataset (don't download all 1.5 GB).
2. Sentence-split each article (regex on terminator + capital VN letter).
3. Filter:
   - 30 ≤ len(sent) ≤ 300 chars (training-friendly length).
   - `has_diacritics(sent)` (no signal otherwise).
   - ASCII ratio ≤ 95 % (drop tables / URL blocks).
   - Not in eval-leak guard set.
   - Deduplicate against earlier emissions.
4. Stride-sample every 7th eligible sentence — diverse without RNG.
5. Generate `(stripped, target)` pairs.

Run::

    python training/diacritic/prep_data.py --max-pairs 500_000  # v0.2.24
    python training/diacritic/prep_data.py --max-pairs 1_000_000  # v0.2.25 if needed

## Training

`train.py` uses HF `Seq2SeqTrainer`. v0.2.24 defaults:

- `epochs=5`, `batch_size=32`, `lr=5e-4`
- `lr_scheduler=cosine`, `warmup_steps=500`
- `early_stopping_patience=3` (on `eval_loss`)
- bf16 mixed precision (recommended on Ampere+ GPUs)
- `eval_steps=1000`, `save_steps=1000` (must be aligned for
  `load_best_model_at_end=True`)
- `metric_for_best_model="eval_loss"` for the inner loop
- After training, runs the multi-corpus 4-register eval and saves
  `training_summary.json` with full hyperparameters

Run on the GPU box (genpc2 in our setup)::

    ./training/diacritic/launch_genpc2.sh \
        --model-id VietAI/vit5-base \
        --epochs 5 --batch-size 32 --bf16 \
        --lr 5e-4 --lr-scheduler cosine \
        --warmup-steps 500 --early-stopping-patience 3 \
        --eval-steps 1000 --save-steps 1000 --logging-steps 100 \
        --output-dir training/diacritic/checkpoints/vit5-base-500k-cosine

The launcher rsyncs code+data to genpc2, kicks off `python train.py`
under `nohup`, and returns the PID. Monitoring::

    ssh genpc2 'tail -f ~/nom-vn-train/training/diacritic/run.log'
    ssh genpc2 'cat ~/nom-vn-train/training/diacritic/run.pid'

## Multi-corpus evaluation

Per CLAUDE.md autonomous-loop §5, single-corpus eval is not enough.
`train.py` evaluates on **all 4 registers** at the end of training and
reports word-accuracy + sentence-exact + ms/sentence for each:

```json
{
  "eval": {
    "business_55":         {"word_accuracy": 0.???, "sentence_exact": 0.???, "mean_ms_per_sentence": 0},
    "literary_udvtb":      {"word_accuracy": 0.???, "sentence_exact": 0.???, "mean_ms_per_sentence": 0},
    "conversational_300":  {"word_accuracy": 0.???, "sentence_exact": 0.???, "mean_ms_per_sentence": 0},
    "formal_udhr":         {"word_accuracy": 0.???, "sentence_exact": 0.???, "mean_ms_per_sentence": 0}
  }
}
```

For re-eval after rsyncing a checkpoint back, use the standalone
[`eval_checkpoint.py`](eval_checkpoint.py) — same metric definition,
no Trainer dependency.

## Adoption gate

We adopt the trained checkpoint **only if** both:

- `business_55.word_accuracy >= 0.96` (within 2 pp of Toshiiiii1's 97.81 %)
- `literary_udvtb.word_accuracy > 0.8940` (strictly improves on Toshiiiii1's 89.40 %)

That is: the model must be *at least* register-balanced, even if it
loses some absolute peak quality on business.

Publishing is done via [`publish_hf.py`](publish_hf.py), which
auto-generates a model card with the 4-register table, license
attribution (Apache-2.0 derivative of ViT5 MIT), and reproduction
instructions:

    python training/diacritic/publish_hf.py \
        --checkpoint-dir training/diacritic/checkpoints/vit5-base-500k-cosine/final \
        --summary-json training/diacritic/checkpoints/vit5-base-500k-cosine/training_summary.json \
        --repo-id nrl-ai/vn-diacritic-restoration

The script enforces the gate (refuse to publish unless both numbers
clear bar; `--force` overrides with a gate-fail note baked into the
model card).

If the gate is not met, archive the checkpoint, document why in the
CHANGELOG, and queue a follow-up:

- **More data** (1 M+ pairs).
- **Bigger arch** (`VietAI/vit5-large`, 770 M, MIT, safetensors).
- **Char-level** (`google/byt5-small`, 300 M, robust to typos).
- **Mixed-source corpus** — verified license-clean candidates audited
  2026-04-29 (the leading hypothesis if v0.2.25 lands close to v0.2.23
  numbers, which would mean Wikipedia-only is the fundamental ceiling):

  | Dataset | License | Size | Register |
  |---|---|---|---|
  | `BlossomsAI/vietnamese-corpus` | Apache-2.0 | ~13 M articles (news-heavy) | news |
  | `tmnam20/Vietnamese-News-dedup` | CC-BY-4.0 | 10-100 M articles | news |
  | `th1nhng0/vietnamese-legal-documents` | CC-BY-4.0 | 518 K docs | legal/formal |
  | `HuggingFaceFW/fineweb-2 (vie_Latn)` | ODC-BY-1.0 | multi-GB | web-mixed (news/blog tilted) |
  | `52100303-TranPhuocSang/vietnamese-legal-corpus-20k-raw` | MIT | 20 K docs | legal |

  Recommended starting mix for register-balanced training: 60-70 %
  Wikipedia (current corpus) + 20-25 % BlossomsAI news + 10-15 %
  th1nhng0 legal. Extend `prep_data.py` to round-robin between sources
  with explicit per-source quotas; keep eval-leak guards across all
  inputs.

## Reproducibility

End-to-end: corpus → train → re-eval → publish:

```bash
# 1. Build the 500K-pair corpus (deterministic stride, eval-leak guarded)
python training/diacritic/prep_data.py --max-pairs 500_000 --seed 42

# 2. Launch on genpc2 (~3h on RTX 3090)
./training/diacritic/launch_genpc2.sh \
    --model-id VietAI/vit5-base \
    --epochs 5 --batch-size 32 --bf16 \
    --lr 5e-4 --lr-scheduler cosine \
    --warmup-steps 500 --early-stopping-patience 3 \
    --eval-steps 1000 --save-steps 1000 --logging-steps 100 \
    --output-dir training/diacritic/checkpoints/vit5-base-500k-cosine

# 3. Once the run completes, rsync the final checkpoint back
rsync -av --progress \
    genpc2:nom-vn-train/training/diacritic/checkpoints/vit5-base-500k-cosine/final \
    training/diacritic/checkpoints/vit5-base-500k-cosine/
rsync -av \
    genpc2:nom-vn-train/training/diacritic/checkpoints/vit5-base-500k-cosine/training_summary.json \
    training/diacritic/checkpoints/vit5-base-500k-cosine/

# 4. Re-eval locally to confirm numbers reproduce within ±0.5 pp
python training/diacritic/eval_checkpoint.py \
    --checkpoint training/diacritic/checkpoints/vit5-base-500k-cosine/final \
    --output-json training/diacritic/results/vit5-base-500k_eval_local.json

# 5. Publish (gate-checked). Auto-generates the model card.
python training/diacritic/publish_hf.py \
    --checkpoint-dir training/diacritic/checkpoints/vit5-base-500k-cosine/final \
    --summary-json training/diacritic/checkpoints/vit5-base-500k-cosine/training_summary.json \
    --repo-id nrl-ai/vn-diacritic-restoration \
    --commit-message "v0.1: vit5-base 500k cosine (initial release)"
```

Every script pins its data source
([`hirine/wikipedia-vietnamese-1M296K-dataset`](https://huggingface.co/datasets/hirine/wikipedia-vietnamese-1M296K-dataset))
and stride/seed so a clean clone produces the same splits and numbers.

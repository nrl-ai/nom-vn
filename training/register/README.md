# Register classifier — VN 4-class router

Source-provenance labelled corpus + PhoBERT-base fine-tune to produce a
text-register router (formal / business / conversational / literary).
Used by downstream nom tools (diacritic, summarization, OCR-rerank) to
pick the right register-conditional checkpoint per input.

## Why

Surveys (`docs/sota_vn_2026q2_expansion.md`, Tier 1 #1) flagged that
no public 4-register VN-labelled dataset exists, and that VN models
spread 5-10 pp accuracy across registers. A cheap router that lifts
every other tool 5-10 pp is the highest-ROI single training run we can
ship for the project.

## Corpus

Source-provenance labelling — no human annotators needed. Each labelled
sentence comes verbatim from the corpus its source genre dictates:

| Label          | Sources                                                                                               | License             | Available    |
| -------------- | ----------------------------------------------------------------------------------------------------- | ------------------- | -----------: |
| formal         | `udhr_vi/udhr_vi.txt` + `udhr_vi/diacritic_eval_udhr.txt`                                             | Public Domain       |   ~170 sents |
| business       | `wiki_vi/articles.jsonl`                                                                              | CC-BY-SA-4.0        | ~7 800 sents |
| conversational | `tatoeba_vi/vie_sentences_sample_3k.tsv` + `tatoeba_vi/diacritic_eval_300.txt`                        | CC-BY 2.0 FR        | ~3 300 sents |
| literary       | `wikisource_vi/*.txt` + `ud_vi_vtb/{train,dev,test}.conllu`                                           | PD + CC-BY-SA-4.0   | ~3 400 sents |

Each source contributes up to `--max-samples-per-class` (default 2 000)
sentences. Stratified 70/10/20 train/val/test split per register, seed-
reproducible.

> **Class imbalance**: `formal` is the bottleneck at ~170 sentences vs
> 2 000-cap for the others. The first run uses cross-entropy without
> class weights — accept that formal F1 will be ~5-10 pp below the
> other classes. To balance, pass `--max-samples-per-class 170`; you
> get a balanced ~680-sample set at the cost of throwing away most of
> the larger classes' data. The honest path is bumping `formal` with a
> permissive legal corpus once we find one (audit pending).
>
> Wikipedia is a rough proxy for "modern factual prose" — not pure news.
> Honest tag, documented on the model card. Future iteration: swap in a
> permissively-licensed VN news corpus when available.

## Run

```bash
# Smoke test — 1 epoch, 200 samples/class, 50 max steps.
python training/register/train.py \
    --output-dir /tmp/register-smoke \
    --epochs 1 \
    --max-steps 50 \
    --max-samples-per-class 200

# Full run — 4 epochs, 2 000 samples/class.
python training/register/train.py \
    --output-dir checkpoints/register-phobert-base \
    --epochs 4 \
    --batch-size 32

# On the remote GPU host:
TRAIN_HOST="${TRAIN_HOST:-the-gpu-host}"  # set per your environment
ssh "$TRAIN_HOST" "cd nom-vn && python training/register/train.py \
    --output-dir checkpoints/register-phobert-base \
    --epochs 4 \
    --batch-size 32"
```

## Output

`checkpoints/register-phobert-base/` — tokenizer + model weights
(safetensors via Trainer.save_model) + `result.json` with config + test
metrics.

## Adoption gate

Per the project's verified-benchmarks rule, the model adopts only when:

1. `macro_f1 ≥ 0.85` on test split.
2. **Every** per-class F1 ≥ 0.75 (no register left behind — register
   imbalance is exactly what we're fighting).
3. The bench number lands in the same commit as the
   `docs/sota_vn_2026q2_expansion.md` row update.

## History

| Date | Args | macro_F1 | f1_formal | f1_business | f1_conv | f1_literary | Notes |
| ---- | ---- | -------: | --------: | ----------: | ------: | ----------: | ----- |
| TBD  | epochs=4, bs=32, max=2000 | — | — | — | — | — | First run pending |

When the first run lands, fill the row in the same commit as the
`result.json` (per the docs-sync rule) and bump the model card.

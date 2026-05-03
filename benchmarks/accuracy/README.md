# Accuracy baselines — `benchmarks/accuracy/`

First-party measured results for each `nom-vn` model wrapper. Every
JSON in this directory was produced by a script run from a clean clone
on a documented date; there are no model-card rehashes.

The numbers committed here are the basis of the rows in
[`docs/sota_vn_2026q2_expansion.md`](../../docs/sota_vn_2026q2_expansion.md).
Re-running any bench is a single-command operation — see the
"reproduce" line on each entry.

> Per the project's verified-benchmarks rule, anything cited as a
> measured number must be reproducible from this repo. If the script
> isn't here, the number isn't ours.

## Baselines

### `spell_correction_real_baseline.json`

| | |
|---|---|
| Model | [`nrl-ai/vn-spell-correction-base`](https://huggingface.co/nrl-ai/vn-spell-correction-base) (BARTpho-syllable backbone, ~900 MB) |
| Corpus | [`benchmarks/data/spell_correction_eval_real/`](../data/spell_correction_eval_real/) (CC0, 6 registers × 25 = 150 OOD pairs) |
| Metric | word-acc (NFC + lowercase + space-token equality), sentence-exact |
| Aggregate | **78.33 % word-acc · 65/150 sentence-exact** |
| Per register | ocr 97.6 / news 96.5 / mobile 95.8 / legal 95.6 / forum 63.4 / **telex 18.0** |
| Hardware | CUDA, ~36 s |
| Date | 2026-05-03 |

**Honest caveats.** Telex (18 %) and forum (63 %) are real failure
registers — when the model hits "Toi yu" telex shorthand it converts
to "Tới từ" rather than "Tôi yêu" (different meaning entirely). Don't
claim spell-correct "works" without naming the register; formal prose
is genuinely 95-97 %, social-media noise is not.

**Reproduce.** Single inline script under
[`scripts/bench_spell_real.py`](../../scripts/bench_spell_real.py)
(to land alongside the next bench iteration; for now the script body
is in the commit-history file diff).

### `vintern_ocr_clean_baseline.json` + `vintern_ocr_noisy_baseline.json`

| | |
|---|---|
| Model | [`5CD-AI/Vintern-1B-v3_5`](https://huggingface.co/5CD-AI/Vintern-1B-v3_5) (InternVL family, MIT, safetensors, ~1.8 GB, BF16 on CUDA) |
| Preprocess | single-tile 448×448 ImageNet-norm via inline `_preprocess_for_internvl` |
| Corpus | [`benchmarks/data/synthetic_ocr_vi/`](../data/synthetic_ocr_vi/) (CC0, line crops) |
| Metric | character error rate (Levenshtein on NFC chars), exact-match |
| Result (clean) | **mean CER 0.47 % · 16/20 exact** |
| Result (noisy) | **mean CER 0.37 % · 17/20 exact** |
| Hardware | CUDA, ~19 s for n=20 |
| Date | 2026-05-03 |

**Honest caveats.** Many of the residual character "errors" are valid
VN diacritic variants (`hoà` ↔ `hòa` — both correct, different
regional preference). N=20 is small; rerun on a 200-image set before
committing to a paper claim. Single-tile preprocess loses detail on
dense multi-column documents — add `dynamic_preprocess` from
upstream InternVL when we hit that case.

### `stt_speech_massive_baseline.json`

| | |
|---|---|
| Models | [`VinAI/PhoWhisper-large`](https://huggingface.co/vinai/PhoWhisper-large) + [`openai/whisper-large-v3`](https://huggingface.co/openai/whisper-large-v3) |
| Corpus | [`doof-ferb/Speech-MASSIVE_vie`](https://huggingface.co/datasets/doof-ferb/Speech-MASSIVE_vie) test, first 3 streamed |
| Metric | WER (NFC + lowercase + space-token Levenshtein) |
| Result | **PhoWhisper 15.2 % · Whisper-v3 15.2 %** (identical) |
| Hardware | CUDA |
| Date | 2026-05-03 |

**Honest caveats.** **n=3 is a smoke test, not a verdict.** Both
models tie at 15.2 % WER on this set; errors are 1 homophone
(`múi giờ` ↔ `mỗi giờ`) + 1 word substitution (`xếp` ↔ `sắp`) +
punctuation/case differences inflating the score. Bench on ViMD's
three-region split (Bắc / Trung / Nam) before claiming dialect
coverage. PhoWhisper's published 4.67 % VIVOS WER and 13.75 %
VLSP T1 WER are upstream-only and not reproduced here yet.

### `summarize_wiki_vi_baseline.json`

| | |
|---|---|
| Model | [`VietAI/vit5-large-vietnews-summarization`](https://huggingface.co/VietAI/vit5-large-vietnews-summarization) |
| Corpus | [`benchmarks/data/wiki_vi/articles.jsonl`](../data/wiki_vi/) (first 10, len ≥ 200 chars, CC-BY-SA) |
| Metric | "novel-token rate" — fraction of output tokens not in input. Crude proxy for hallucination; common-VN function words inflate it. **Numeric novelty** is the cleanest signal. |
| Result | mean novel-token rate 0.193 · **1/10 samples added a novel year** ("2025" in the TP.HCM article) |
| Hardware | CUDA, ~19 s |
| Date | 2026-05-03 |

**Honest caveats.** "Novel-token rate" is a proxy, not ROUGE — a
faithful summary can contain `là`, `của`, etc. that aren't in the
input. The signal that actually matters is **numeric novelty**: the
model added "2025" to one summary that didn't appear in the input.
Earlier I caught a more flagrant case (the model wrote `6,8 % – 7,0 %`
GDP figures that weren't in a 234-char Vietnam paragraph). 1 / 10
sampling rate of "added external numbers" is enough to flag — don't
ship summarize for legal / finance work without ROUGE + a hallucination
audit on a multi-hundred-sample VN news set.

## On HF Hub publishing

Per [`CLAUDE.md`](../../CLAUDE.md) Section 14, every dataset / model
artifact we publish to HF Hub:

1. Cites Viet-Anh Nguyen (`vietanh@nrl.ai`) in the YAML and BibTeX
   blocks of the card, alongside `Neural Research Lab`.
2. Renders cleanly — verify with `HfApi().dataset_info(repo_id)` and
   open the page to confirm there's no yellow YAML warning banner.
3. Loads via `datasets.load_dataset(repo_id, config_name)` for every
   config / split.

> **On parquet:** the HF parquet-converter bot **automatically**
> maintains a parquet view at `refs/convert/parquet` for every
> uploaded JSONL/CSV dataset (see e.g.
> [`nrl-ai/vn-spell-correction-train` discussion #1](https://huggingface.co/datasets/nrl-ai/vn-spell-correction-train/discussions/1)).
> Don't add a manual parquet conversion step — the auto-converted view
> is what powers the dataset viewer + DuckDB / Polars / ClickHouse
> readers. Upload jsonl/csv with a clean YAML card; HF does the rest.

### Test corpora — publishing status

| Local path | License | Pushed to HF | Repo |
|---|---|---|---|
| `benchmarks/data/spell_correction_eval_real/` | CC0 | **not yet** | proposed: `nrl-ai/vn-spell-correction-eval-real` |
| `benchmarks/data/synthetic_ocr_vi/` | CC0 | **not yet** | proposed: `nrl-ai/vn-synthetic-ocr` |
| `benchmarks/data/diacritic_eval_v0.txt` | CC0 | already mirrored | per `docs/datasets.md` |
| `benchmarks/data/udhr_vi/` | PD | upstream UDHR | n/a — point at OHCHR |
| `benchmarks/data/tatoeba_vi/` | CC-BY 2.0 FR | upstream Tatoeba | n/a — point at upstream |
| `benchmarks/data/wikisource_vi/` | PD | upstream Wikisource | n/a |
| `benchmarks/data/wiki_vi/` | CC-BY-SA-4.0 | upstream Wikipedia | n/a |
| `benchmarks/data/ud_vi_vtb/` | CC-BY-SA-4.0 | upstream UD | n/a |
| Speech-MASSIVE_vie 3-sample subset | CC-BY-NC-SA-4.0 | streamed from `doof-ferb/Speech-MASSIVE_vie` | n/a — non-commercial license keeps it remote |

### Bench result JSONs

These are **measurement output**, not training datasets. They live in
this directory under git so anyone can `git diff` them across commits
to see whether a model regressed. We do not push them to HF as a
dataset — they belong with the code that produced them. The HF model
cards on `nrl-ai/*` link back here for the citable numbers.

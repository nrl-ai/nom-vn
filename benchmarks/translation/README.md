# Translation benchmarks — VN ↔ EN

Purpose: produce verified chrF / BLEU / latency numbers for the
shortlisted local translation models so we can pick a default and
ship it with cited measurements.

## Candidate shortlist (May 2026)

Five models that pass our license + format + size filter (Apache/MIT/BSD
or commercial-OK custom; safetensors or `.bin` from a major lab; ≤ 30 B
for local realism):

| Model | License | Format | Params | Why on the list |
|---|---|---|---|---|
| `google/madlad400-3b-mt` | apache-2.0 | safetensors | 3 B | T5-class MT specialist, 200+ langs, deterministic |
| `sail/Sailor2-8B-Chat` | apache-2.0 | safetensors | 9 B | Qwen2.5-based, SEA-tuned (15 langs incl. VN) |
| `SeaLLMs/SeaLLMs-v3-7B-Chat` | seallms (custom — read in full) | safetensors | ~8 B | Only candidate with a published VN chrF (43.78 on FLORES) — anchors the bench against an external claim |
| `Qwen/Qwen3-8B` | apache-2.0 | safetensors | 8.2 B | Already in Nôm's stack — the "we already run this for chat" baseline |
| `facebook/m2m100_418M` | mit | `.bin` (Meta carve-out) | 418 M | Smallest viable specialist, CPU-realistic floor |

**Auto-rejects** (do not add to the bench): `facebook/nllb-200-*`
(CC-BY-NC), Cohere `Aya-23-*` (CC-BY-NC),
`VietAI/envit5-translation` (OpenRAIL — not MIT as some sources claim;
also no safetensors).

## Setup

```bash
# Bench-only deps. transformers MUST be <5 — transformers 5.x mishandles
# MADLAD-400's tied-weights config (input/output embeddings stay
# de-tied) and the model emits "10000000000000♠0.00..." for every
# input regardless of prompt. Verified on transformers 5.7.0, fixed
# by downgrading to 4.x.
pip install 'transformers<5' torch>=2.0 sacrebleu>=2.4 sentencepiece>=0.1.99
```

For Ollama-backed runs (Qwen3-8B, etc.):

```bash
ollama pull qwen3:8b
```

For HF seq2seq (MADLAD, m2m100):

```bash
# Auto-downloaded on first run via transformers; cached in HF_HOME.
# Pre-warm if you want:
python -c "from transformers import AutoTokenizer, AutoModelForSeq2SeqLM; \
    AutoTokenizer.from_pretrained('google/madlad400-3b-mt'); \
    AutoModelForSeq2SeqLM.from_pretrained('google/madlad400-3b-mt')"
```

## Corpora

We run each candidate on ≥ 2 registers (multi-corpus requirement —
single-register results overfit and we have repeatedly burnt ourselves
trusting one number).

| Corpus | Register | License | Path | Sentences |
|---|---|---|---|---|
| FLORES-200 vie_Latn devtest | News / wiki | CC-BY-SA-4.0 | `benchmarks/data/flores_vi/devtest/` (gated — see that folder's README) | 1012 |
| Tatoeba VN slice | Conversational | CC-BY 2.0 FR | `benchmarks/data/tatoeba_vi/vie_sentences_sample_3k.tsv` | 300 (slice) |
| UDHR VN | Formal / declarative | Public Domain | `benchmarks/data/udhr_vi/udhr_vie.txt` | ~72 |

FLORES is the headline number; Tatoeba and UDHR catch register-shift
collapse (we have repeatedly seen >5 chrF spread between formal and
conversational on the same model).

## Run

```bash
# HF seq2seq specialist — MADLAD on FLORES, EN→VN
python benchmarks/translation/bench_translation_flores.py \
    --backend hf --model google/madlad400-3b-mt \
    --direction en2vi \
    --corpus benchmarks/data/flores_vi/devtest/eng_Latn.jsonl \
    --reference benchmarks/data/flores_vi/devtest/vie_Latn.jsonl \
    --json benchmarks/results/baseline_translation_madlad3b_flores_en2vi.json

# Same script, Ollama-backed prompted translator — Qwen3-8B
python benchmarks/translation/bench_translation_flores.py \
    --backend ollama --model qwen3:8b \
    --direction en2vi \
    --corpus benchmarks/data/flores_vi/devtest/eng_Latn.jsonl \
    --reference benchmarks/data/flores_vi/devtest/vie_Latn.jsonl \
    --json benchmarks/results/baseline_translation_qwen3_8b_flores_en2vi.json

# VN → EN
python benchmarks/translation/bench_translation_flores.py \
    --backend hf --model google/madlad400-3b-mt \
    --direction vi2en \
    --corpus benchmarks/data/flores_vi/devtest/vie_Latn.jsonl \
    --reference benchmarks/data/flores_vi/devtest/eng_Latn.jsonl \
    --json benchmarks/results/baseline_translation_madlad3b_flores_vi2en.json
```

For `.txt` corpora (Tatoeba, UDHR) you need a parallel reference file
in the other language. UDHR ships parallel; Tatoeba VN slice does not
ship paired EN by default — pull the matching EN sentences from
`tatoeba.org` and commit alongside (same TSV row order). Out of scope
for v0.1 of the harness.

## Result schema

Written to `benchmarks/results/baseline_translation_<model>_<corpus>_<dir>.json`:

```json
{
  "task": "translation",
  "direction": "en2vi",
  "backend": "hf",
  "model": "google/madlad400-3b-mt",
  "model_revision": "refs/pr/3@abc1234",
  "precision": "fp16",
  "corpus": "benchmarks/data/flores_vi/devtest/eng_Latn.jsonl",
  "reference": "benchmarks/data/flores_vi/devtest/vie_Latn.jsonl",
  "n_sentences": 1012,
  "warmup_calls": 3,
  "best_of_n": 3,
  "chrf": 0.5421,
  "bleu": 31.7,
  "diacritic_recall": 0.987,
  "cjk_bleed_chars": 0,
  "latency_ms_p50": 142.0,
  "latency_ms_mean": 158.4,
  "transformers_version": "4.45.2",
  "sacrebleu_version": "2.4.3",
  "run_date": "2026-05-02"
}
```

## Reading the numbers

- **chrF primary** — better correlation with human VN MT judgment than
  BLEU; matches what SeaLLMs publishes (we want to compare like for
  like). SeaLLMs-v3-7B-Chat reports 43.78 on FLORES VN-target —
  that's the number to validate against on its own bench row.
- **BLEU secondary** — keep for paper-comparability.
- **Diacritic recall** — % of VN diacritic-bearing characters in the
  reference that appear correctly in the hypothesis. Word-level
  metrics underweight the failure VN readers feel most.
- **CJK bleed** — count of CJK Unified Ideograph characters in EN→VN
  output. Should be 0 for a healthy model. Qwen2-era variants leaked
  Chinese characters; Qwen3 reportedly fixed this — verify.

## Honest gaps

- COMET-22 not yet wired — implementation is straightforward via the
  `unbabel-comet` package but adds a 2 GB model download. Add when
  bench infrastructure has GPU budget.
- No fine-grained register stratification yet (legal vs medical vs
  business). Add a Zalo Legal slice + a clinical-VN slice if the
  general FLORES number doesn't match user-reported quality.
- Quantization runs (Q4_K_M GGUF) need a separate code path through
  `llama.cpp` — not in this script. Track as TODO once fp16 baseline
  is established.

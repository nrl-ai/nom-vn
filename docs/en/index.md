# Introduction

**Nôm** is an open-source Vietnamese AI toolkit. This documentation
site collects design notes, measured benchmarks, recipes, and
contribution guides.

> The name *Nôm* draws from chữ Nôm (the historical Vietnamese
> script), but the project's scope is **modern Vietnamese in chữ Quốc
> Ngữ**. We do not target Hán-Nôm corpora.

## What's inside

1. **Diacritic restoration** (`nom.text.fix_diacritics`) —
   `Toi yu Vit Nam` → `Tôi yêu Việt Nam`. The `nrl-ai/vn-diacritic-vit5-base`
   model averages 97.4 % word accuracy across 4 registers.
2. **Spell correction** (`nrl-ai/vn-spell-correction-*`) — superset of
   diacritic restoration with extra capacity for character-level
   typos, Telex/VNI input slips, OCR engine output, and teen-code
   abbreviations. Light avg 98.58 % / heavy avg 97.35 % on the
   8-split grid.
3. **OCR + document extraction** — pipeline for Vietnamese
   PDF / DOCX / image with Tesseract `vie` and an optional VLM
   fallback.
4. **Local-first RAG** — embed, retrieve, BM25 hybrid, cross-encoder
   rerank, local LLM via Ollama. Full pipeline runs offline.

## Principles

* **Measure first, publish second.** Every number on this site has a
  committed `benchmarks/...` script that runs from a clean clone.
* **No supply-chain landmines.** Reject `.pkl` / `.pickle` model
  files; prefer `safetensors` with SHA256 pinning when third-party
  weights are loaded.
* **Privacy-first.** No mandatory subscription APIs; sensitive data
  stays on the user's machine.
* **Multi-register evaluation.** Every model is benchmarked on at
  least two distinct registers so register-overfit can't hide.

## Get started

* [Quickstart](/en/quickstart)
* [Trained models](/en/models)
* [Benchmark summary](/benchmark)

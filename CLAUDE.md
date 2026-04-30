# CLAUDE.md — nom-vn project notes for AI assistants

This file is auto-loaded by Claude Code when working inside `nom-vn/`. It points
to durable project context. For the broader Atlas operating manual see the
parent `PPlanning/CLAUDE.md`.

## Vietnamese benchmark datasets

Test corpora live under [`benchmarks/data/`](benchmarks/data/). The full
catalogue, license notes, and intended-use map are in
[`docs/datasets.md`](docs/datasets.md).

When you need Vietnamese text, PDF, or image fixtures for tests or benchmarks,
prefer these over hand-curating new examples:

- **Sentences (4 registers)** → `benchmarks/data/diacritic_eval_v0.txt` (CC0)
- **Declarative prose** → `benchmarks/data/udhr_vi/` (CC-BY-SA / PD)
- **Classical literary** → `benchmarks/data/wikisource_vi/` (PD content)
- **Encyclopedia long-form** → `benchmarks/data/wiki_vi/articles.jsonl` (CC-BY-SA)
- **Conversational sentences** → `benchmarks/data/tatoeba_vi/` (CC-BY)
- **Born-digital PDF** → `benchmarks/data/udhr_vi/udhr_vie.pdf` (PD)
- **OCR images (with ground truth)** → `benchmarks/data/synthetic_ocr_vi/` (CC0)
- **Vietnamese legal / governance** → `benchmarks/data/legal_vi/` (PD per Luật SHTT §15)
- **Synthetic Office (DOCX/XLSX/PPTX)** → `benchmarks/data/office_vi/` (PD, generator-built)

All datasets are regeneratable via:

```bash
python benchmarks/data/_fetch_all.py
python benchmarks/data/synthetic_ocr_vi/render.py
```

When adding a new dataset, follow the rules in `benchmarks/data/README.md` and
update `docs/datasets.md` so the catalogue stays current.

## Component build workflow — real models, real data, VN-specific research

When building or refining any pipeline component (retriever, reranker, embedder,
chunker, parser, generator), follow this loop. Skipping stages produces brittle
or untruthful results.

1. **Research the lightweight VN-specific options first.** Survey Hugging Face
   and recent papers (2024-2026) for the smallest open-source model that gets
   close to SOTA on Vietnamese. Record license, file format, reported VN
   benchmark numbers from a public source, and base architecture.
   General-multilingual baselines (BGE, mE5, Qwen3) are valid candidates but
   prefer VN-finetuned variants when license + audit pass and the gap is
   measurable. Document the survey in
   `research/<YYYY-MM-DD>-<topic>/report.md` or the relevant
   `docs/sota_*` page with citations.

   **File-format trust ladder** (refines parent CLAUDE.md principle 11):

   | Format | Status | Why |
   |---|---|---|
   | `safetensors` | ✅ **always preferred** | Deterministic, zero code execution on load. |
   | HF `.bin` / `pytorch_model.bin` | ⚠️ acceptable from a major lab when no safetensors variant exists | These are pickled too, *but* they're audited at scale and downloaded with a SHA256 checksum from a known-trusted host (HuggingFace Hub). Bias: prefer the safetensors revision when both exist (most BAAI / Meta / Google / Mistral / Qwen models now ship both). When only `.bin` is offered (older models, some research repos), accept *only* if the publisher is a major institution with reproducible weights. Document the choice in the model wrapper docstring with a one-line "no safetensors variant published — trusting HF SHA256 + publisher" note. |
   | `.pkl` / `.pickle` | ❌ **auto-reject regardless of source** | Same RCE surface as `.bin`, but without the HF checksum infrastructure or publisher accountability. We caught PyVi shipping these in v0.1 — never again. |
   | Opaque native binaries (CRFsuite `lCRF…`, etc.) | ⚠️ acceptable when license + format are documented and the format spec is public | Deterministic but opaque. Prefer in-tree reimplementation if accuracy gap is small. |

   The parent rule "prefer in-tree reimplementation when feasible" still
   applies — but it's a tradeoff, not an absolute. Reimplementing a
   1B-param transformer is not feasible; reimplementing a 5kb CRF
   tokenizer is.
2. **Build the smallest dependency surface that meets the quality goal.** Lazy
   imports, Protocol seams, frozen dataclasses on hot paths.
3. **Test with real models, not just fakes.** Unit tests use fakes for speed —
   that's correct. But before claiming a feature ships, write at least one
   integration test or benchmark run against the actual model the user will
   download (`pytest -k integration` or `python benchmarks/.../bench_*.py
   --embedder vietnamese --reranker BAAI/bge-reranker-v2-m3`). Skip-on-import
   patterns are fine for CI environments without the model cache.
4. **Benchmark on real Vietnamese datasets, not toy fixtures.** Tiny synthetic
   fixtures are useful for harness validation but cannot show component value
   when every retriever scores 1.000. Pull from a real public VN corpus
   (Zalo Legal QA mirror, ViQuAD, MIRACL-vi, or a Wikipedia sample of similar
   size). Commit a baseline JSON under `benchmarks/.../baselines/` so the next
   change re-measures cleanly.
5. **Iterate components and pipelines as a grid, not one at a time.** Try
   each candidate model under the same fixture, same metrics, same warmup +
   best-of-N protocol. Report the table with explicit `embedder`, `reranker`,
   `chunk_max_tokens`, etc., in the result JSON config block — silent
   defaults will desync from claims later.
6. **Honest empties beat fake numbers.** Quality cells without a
   committed-and-runnable bench script must be left empty / TBD per parent
   CLAUDE.md principle 12. Disclaimers like "preliminary" do not rescue
   fabricated metrics.
7. **Cross-check our numbers against the model's published benchmarks.** After
   running a real-model bench, find the model card / paper for each component
   and compare. If our number is materially different from the public number
   (say >10% relative on the same metric), **stop and investigate** before
   shipping or claiming. Common causes:
   - Different test corpus (ours is harder/easier or different register).
   - Wrong tokenization (model expects word-segmented input but we pass raw).
   - Wrong sequence length / truncation cap (model card says 512, we cap at
     256; or position-table off-by-one; see VietnameseEmbedder docstring for
     the XLM-RoBERTa quirk).
   - fp16/fp32 mismatch, wrong device (CPU vs GPU), missing normalization.
   - Cold-start artefacts (no warmup, lazy model load inflating first-pass
     latency — caught the 135× → 21× ratio incident on 2026-04-25).
   - Wrong metric variant (NDCG vs MAP, @10 vs @20, micro vs macro average).
   Either fix the issue and re-measure, or document the divergence honestly
   in `docs/benchmark.md` with the explanation. **Do not ship a number that
   silently disagrees with the upstream's published number** — readers will
   compare and lose trust.

## Autonomous improvement loop

When the user says any of: "continue until done", "don't stop", "improve until done",
"work as ML expert engineer until done", or any open-ended "keep improving" directive,
operate in autonomous mode:

1. **Build a checklist of concrete improvements** based on (a) the current state of
   benchmarks/results and docs/, (b) any tasks marked pending in the task system, and
   (c) the user's latest question or steering. Use TaskCreate to track each item.
2. **Decide the next item automatically.** Pick by ROI = (user-visible impact) /
   (engineering cost). If two items tie, prefer the one that closes a measurement
   gap (we shipped a recommendation without bench-data) over greenfield work.
3. **Execute. Don't ask for confirmation.** The user has already asked you to keep
   going. Asking "should I proceed?" between tasks wastes their attention.
4. **If genuinely blocked** (missing dependency, contradictory data, an external
   API down), research first — web search, HF Hub, GitHub issues, model cards.
   If after a single round of research you still can't decide, write a one-line
   summary of the blocker, mark the task pending with the reason, move to the next.
   Don't stop.
5. **Off-the-shelf before training.** Before recommending a fine-tune or distillation
   run, exhaustively bench public Apache/MIT/BSD/safetensors candidates on the
   exact same corpus you'd evaluate the trained model on. We caught one of these
   on 2026-04-26: a "distil a 100M-param VN diacritic model" recommendation was
   shipped without first benching `Toshiiiii1/Vietnamese_diacritics_restoration_5th`
   (Apache, safetensors, 200M) and similar. The user correctly flagged it.

   **Multi-corpus measurement is mandatory for adoption claims.** A second
   incident on 2026-04-26: Toshiiiii1 hit 97.81 % word acc on the 55-sentence
   `diacritic_eval_v0.txt` (business/news register) but only 54.14 % on the
   800-sentence `ud_vi_vtb/test.conllu` (classical literary). Same model, 43 pp
   gap. Single-corpus claims hide register-shift weakness. Before adopting a
   model as default, bench on **at least two distinct registers** drawn from
   different sources (e.g. one business + one literary, or one in-domain + one
   out-of-domain). If the spread is >10 pp, the model is register-overfit —
   document that honestly and pick a register-conditional default.
6. **Each item ends in a commit.** No long-running uncommitted state. After each
   improvement: lint, run tests, commit with a focused message. Bump the patch
   version when the change is user-visible (new bench numbers, new dep, new API).
7. **Trust the trust ladder.** Per principle 11 + the file-format trust ladder in
   the component-build workflow: safetensors ≫ HF .bin from major labs ≫ opaque
   native ≫ pickle (auto-reject). When evaluating a new candidate model, the
   *first* check is the format / license, not the metric.

8. **ALWAYS DOUBLE-CHECK before claiming a number.** Every benchmark result
   needs three sanity checks before going into a doc, README, or commit
   message:

   - **Implausible metric check.** 0 % or 100 % on a real model is almost
     always a bench bug. Sub-30 % on a model whose card claims 90 %+ means
     a preprocessing step is wrong (input prefix, word segmentation, max
     length). 99 % on a small eval is suspect of overfit-to-test.
   - **Cross-reference upstream numbers.** Find the model card / paper.
     If our number is materially different (>10 % relative on the same
     metric), pause and investigate before shipping. Common causes are
     listed in the component-build workflow §1.7. Document divergences
     honestly in `docs/benchmark.md`.
   - **Dump 5 raw I/O samples** from the benched model and read them.
     If the predictions look obviously wrong but the metric looks fine,
     the metric is broken. We caught a 0/800 sentence-exact bug this way
     on 2026-04-26: the predictions were nearly perfect, the metric was
     comparing pre-tokenized treebank punctuation against natural seq2seq
     output and the alignment shifted at the first comma.

   Skipping any of these is how silent quality regressions ship. The cost
   of one extra console-print of `(input, prediction, gold)` for the first
   five samples is two minutes; the cost of a wrong number in the README
   is a week.

The aim of autonomous mode is sustained throughput, not "many small commits".
Skip work that doesn't move a measurable number; focus on the items that close
a real gap surfaced by the latest benches.

## Vietnamese language — gotchas we've hit, encoded so we don't hit them again

This section documents real failure modes from working on Vietnamese
NLP in this codebase. Read it before designing a benchmark, picking a
model, or claiming a quality number. Most of these are subtle in
ASCII but devastating in production.

### Encoding & normalization

- **NFC vs NFD.** Vietnamese diacritics decompose: "ề" (U+1EC1) ↔ "e" + combining-grave + combining-circumflex (U+0065 U+0300 U+0302). Two strings can be visually identical and byte-different. **Always NFC-normalize before comparing**. Our `nom.text.normalize` does this; tests assert it. Skipping NFC is the single most common cause of silent bench-metric noise. **2026-04-30 training repro:** the v5 mixed-source training catastrophically regressed business register (-15.45 pp) because `tmnam20/Vietnamese-News-dedup` ships ~79 % of sentences in NFD form, the ViT5 SentencePiece tokenizer is NFC-trained, the model learned to emit decomposed combining marks, and the NFC eval set byte-compared against decomposed outputs. **Audit every new training corpus** with `unicodedata.normalize('NFC', t) == t` on a sample before kicking off the run. The `has_diacritics` filter does NOT catch NFD because U+0111 ('đ' as a distinct codepoint) waves NFD-mixed text through.
- **đ has a stroke, not a diacritic.** "đ" (U+0111) is a distinct codepoint, not "d" + combining stroke. `strip_diacritics` must replace it explicitly — character-class regexes won't.
- **Stacked diacritics.** "ờ" stacks a tone mark on a vowel modifier (ơ + grave). Two precomposed forms exist, plus the decomposed forms. Our `normalize` function canonicalises all of them; do not roll your own without test coverage of every combination.
- **Sự-class characters.** `ơ`, `ư`, `ă`, `â`, `ê`, `ô`, `đ` are *modifiers* (vowel/consonant variants) that combine with five *tone marks* (acute, grave, hook above, tilde, dot below). 6 vowels × 5 tones × 2 modifiers = ~60 vowel forms. A diacritic-restoration model has to predict modifier *and* tone correctly for each syllable.

### Tokenization & word boundaries

- **Vietnamese spaces between syllables, not words.** "thành phố Hồ Chí Minh" is one word in linguistic terms (a proper noun) but five space-separated tokens. The VN-MTEB / UD treebank conventions join multi-syllable words with single spaces inside the *FORM* column.
- **bkai-vietnamese-bi-encoder needs underscored input.** "đường thủy" → "đường_thủy" before encoding. The model was trained on this format; raw text drops R@1 by 15-20 pp. We handle it in `BKaiEmbedder._segment` automatically — don't bypass.
- **`.split()` is wrong for measuring quality.** UD treebank ships sentences with spaces around punctuation (`nhỉ ? " .` for parsing-tool conventions). Modern seq2seq models output natural VN with attached punctuation (`nhỉ?".`). Comparing raw `.split()` lists shifts the alignment at the first punctuation mark and produces 0 % sentence-exact match even on a perfect model. **Always `normalize_punct()` both sides before token-level comparison** — see `benchmarks/accuracy/bench_diacritic_hf_udvtb.py` for the canonical implementation.
- **Sub-word vs character vs syllable tokenizers all have VN failure modes.** XLM-R's SentencePiece tokenizer handles VN well; PhoBERT's BPE tokenizer is VN-specific and tighter; ByT5's byte-level is robust to noise but slower. Pick by task: byte-level for typo tolerance, BPE for speed, SentencePiece for cross-lingual.

### Datasets — registers, traps, and reproducibility

- **Register-shift is the #1 hidden quality failure** for VN models. A model trained on modern business/news Vietnamese will collapse on classical-literary register and vice versa. The 4-register Toshiiiii1 matrix (measured 2026-04-26 → 2026-04-29) shows a *gradient*, not a cliff: UDHR formal/legal 98.14 % (72) → business/news 97.81 % (55) → conversational/Tatoeba 93.77 % (300) → literary/UD-VTB 89.40 % (800). 8.7 pp spread. Two registers is the floor; three or four cornering distinct genres gives the gradient and is what you want before adopting.
- **Public VN evaluation datasets we trust** (license + format + register breakout):
  - `diacritic_eval_v0.txt` — 55 hand-curated sentences, 4 registers, CC0. Tiny but deterministic.
  - `UD_Vietnamese-VTB` test split — 800 literary sentences, gold word segmentation, CC-BY-SA-4.0.
  - `Zalo Legal QA` (via GreenNode mirror) — 61k articles + 788 questions, MIT, legal register.
  - `udhr_vi.txt` — UN human-rights declaration, 19 KB, formal register, public domain. Use `benchmarks/data/udhr_vi/build_diacritic_eval.py` to extract the 72-sentence diacritic eval slice.
  - `tatoeba_vi/vie_sentences_sample_3k.tsv` — 3 k conversational sentences, CC-BY 2.0 FR. Use `benchmarks/data/tatoeba_vi/build_diacritic_eval.py` to extract the 300-sentence diacritic eval slice.
- **Public VN datasets that fail our trust ladder** (DO NOT USE without explicit user opt-in):
  - `VLSP 2013` segmentation — gated, requires registration. Cite reported numbers from papers; do not redistribute.
  - `Surya OCR` corpora — code is GPL-3, models are open-RAIL-M. License-incompatible for default ship.
  - `Vintern handwriting` — license unclear at top of HF page; verify verbatim.
- **Cross-checking against the public number** is mandatory. Toshiiiii1's model card published no metric. bkai's 73.28 R@1 on Zalo Legal 20% reproduces (76.25 on our 5k subset — a tighter distractor pool, +3 pp expected). halong's claimed 82.94 R@1 did *not* reproduce (we measured 55.00). Always run on our corpus before adopting.

### Metrics — what each one really measures

- **Word accuracy** ≠ diacritic recall. A function word like "và" or "của" stays unchanged when stripped, so it's "correct" in any restoration metric without the model doing anything. Always also report **diacritic recall** (of words that *had* a diacritic in gold, how many did we restore?) — that's the meaningful signal.
- **Sentence-exact match** is brutal: one missed proper noun fails the whole sentence. Include it as a stress test, not the headline.
- **CER** (character error rate) for OCR — Levenshtein over normalised char sequences, NFC. **Diacritic-CER** computes CER on just the combining marks (after NFD decompose) — captures the failure mode VN readers feel most: base letter right, tone wrong.
- **F1 for word segmentation** is calculated on token spans (start, end) char ranges, not on token strings. A 100 % token-string match is impossible if the segmenter joins multi-syllable tokens differently than gold; span-based F1 is invariant to that.
- **Implausible metrics demand investigation.** 0 % or 100 % on a real model is almost always a bench bug. Sub-30 % accuracy on a published model whose card claims 90 %+ means we're missing a preprocessing step (see bkai underscore segmentation, e5 prefix conventions).

### Model output traps

- **Qwen3 thinking mode** silently emits CoT to a separate `thinking` field on Ollama 0.21+, leaving `content` empty. We default `Ollama(think=False)` for terse extraction tasks. Set `think=True` only when you actually want CoT.
- **Generic LLMs ramble even when told not to.** "Restore diacritics: ..." gets explanations + headers + quotes. Use **structured output** (`{"restored": "..."}` JSON schema) on the Ollama `format` field to constrain the response.
- **VLM OCR hallucinates on tight line crops.** `qwen2.5vl:7b` got 31 % CER on clean printed VN line images (vs Tesseract's 5 %) because the language prior dominates the visual signal in the absence of document context. VLMs are the right tool for *understanding* documents (forms, invoices, ID cards, handwriting); wrong tool for transcribing clean lines.
- **mE5 family expects `query:` and `passage:` prefixes.** Without them, retrieval craters by 15-25 pp. Our `bench_embedder_compare.py` auto-detects the e5 family and prefixes accordingly.
- **PhoBERT-base position table is 256 (not 514).** XLM-R-large is 512. Sending a 512-cap sequence to PhoBERT trips the SDPA CUDA assert. Our `CrossEncoderReranker` auto-detects from `config.json max_position_embeddings`; don't bypass without setting `max_length=` explicitly.

### Proper nouns are hard

Vietnamese proper nouns have multiple plausible diacritisations from the same ASCII form:
- `Hung` → `Hùng` (hook), `Hưng` (modifier+grave), `Hứng` (modifier+acute)
- `Thanh` → `Thanh`, `Thành`, `Thánh`
- `Le` → `Le`, `Lê`, `Lễ`

A diacritic-restoration model picks the most-frequent in training data; that's not always right for the input sentence. Most of Toshiiiii1's UD-VTB errors are this class. Don't claim a model is "broken" because it picked `Hưng` when gold says `Hùng` — they're both real names; the failure is disambiguation, not restoration.

When a workflow really requires the gold proper noun (legal docs, forms with named entities), it's a separate **NER + lookup** problem, not a diacritic-restoration problem. Tag NEs first, restore the rest.

## Scope clarification

`nom-vn` is named after **chữ Nôm** (the historical Vietnamese script) but the
OCR target and processing pipeline are **modern Vietnamese in chữ Quốc Ngữ** —
Latin script with diacritics. Do not prioritize Hán-Nôm corpora or features
when scoping training data, benchmarks, or modules.

## Research and citations

Any document under `docs/research/` (and SOTA / landscape docs in `docs/`) must
back factual claims with verifiable citations:

- Inline links or numbered footnotes for every dataset size, license, benchmark
  number, and model detail.
- A "References" section at the end listing every URL.
- If a claim cannot be cited, write **"no published source"** or **"unverified"**
  explicitly. Do not guess.

This enforces CLAUDE.md principle 12 (verified benchmarks only) at the
documentation layer.

## Publishing to Hugging Face Hub — author + verification rules

Whenever we push a model or dataset to `nrl-ai/*` on the Hub:

1. **Cite Viet-Anh Nguyen on every artifact.** Per parent CLAUDE.md
   principle 13. The principal's name + `vietanh@nrl.ai` must appear in the
   citation block on every model card and dataset card we ship. Format:
   `author={Nguyen, Viet-Anh and {Neural Research Lab}}` in BibTeX,
   alongside any organizational attribution. Apply retroactively when
   patching old cards.

2. **Verify the page after every push.** Per parent CLAUDE.md principle 14.
   `huggingface_hub.upload_*` returning success only means the bytes
   transferred — the YAML metadata could still be invalid:

   - Run `HfApi().model_info(repo_id)` (or `dataset_info`) and read back
     `pipeline_tag`, `library_name`, `tags`, `siblings`.
   - For datasets, run `datasets.load_dataset(repo_id, config)` to confirm
     each config parses. A README that *renders* but doesn't *load*
     defeats the purpose.
   - Open `https://huggingface.co/<repo_id>` once before declaring done
     and look for the yellow YAML warning banner.

   Known traps:

   - **`pipeline_tag: text2text-generation` is NOT valid** (caught 2026-04-30).
     Use `text-generation` for seq2seq diacritic / spell-correction models.
     The full valid list ships in the warning itself when it fires.
   - Per-config license overrides don't exist at the YAML level — the
     repo-level `license:` is the only field. Document per-config
     differences in the README body (e.g. CC-BY for news subset, CC-BY-SA
     for wiki subset, repo-level = CC-BY-SA = most restrictive).
   - **Fix-only pushes:** when only the YAML / README changes, use
     `HfApi().upload_file(path_in_repo="README.md", ...)` — re-pushing the
     full folder re-uploads the weights (slow + wasteful). One file,
     one commit message describing the fix.

## Docs stay in sync with results — every commit, not "later"

When a result lands (new bench number, new published model, new shipped
module, new gotcha caught, new tool added), update the relevant docs in
the **same commit** (or the next one) — never accumulate a backlog of
"docs to refresh." A model card without a measurement, a `docs/recipes.md`
without the new helper, or a README still showing the previous-quarter
status is a regression in the user-facing surface even when the code is
fine.

The minimum propagation matrix:

| Trigger | Update in same commit |
|---|---|
| New bench number | `docs/benchmark.md` table row (or the relevant `docs/tasks/*.md` page once migrated), plus the affected register-conditional production guidance table |
| New published model on HF | `docs/recipes.md` (subsection with the new model + when to use), `docs/sota_vn_2026q2.md` or `docs/tasks/<task>.md` (recommended-stack row), **`README.md` AND `README.vi.md`** (status badge / recommended-stack table when relevant — both must stay in lockstep) |
| New shipped module under `nom.*` | `docs/recipes.md` (new section with copy-paste code), `docs/architecture.md` (layer / Protocol seam), **`README.md` AND `README.vi.md`** "Recommended stack" if user-facing |
| New gotcha caught (NFC bug, ES-fired-too-early, etc.) | This file's "Vietnamese language gotchas" section, plus a paragraph in the relevant module docstring |
| New training experiment outcome | `training/<task>/README.md` experiment-history table, `CHANGELOG.md` if version-bumping |
| Version bump | `pyproject.toml`, `CHANGELOG.md`, **`README.md` AND `README.vi.md`** status badges |

**`README.vi.md` is a first-class peer of `README.md`** — Vietnamese
is the project's primary user community. The two files must stay in
content-parity within the same commit (sections in the same order,
same recommended-stack table rows, same status badges with the same
version, same code snippets — the prose can be translated freely
provided the structure matches). Drifting them is a regression in
the user-facing surface for a major user segment.

## Fast / small / nano tiers train on the SAME corpus as the base

When we train a smaller variant of a model (`-small`, `-nano`,
`-distilled`) for a "fast tier", it must use **at least as much
training data and at least as many epochs as the `-base` sibling**.
The instinct to think "smaller model = smaller corpus to save
compute" is exactly backwards:

- **Chinchilla scaling** (Hoffmann et al., 2022) shows compute-optimal
  training pairs *more* tokens per parameter as model size shrinks
  — small models trained on big corpora generalize better than small
  models trained on small corpora.
- Less capacity = less ability to memorize spurious patterns, *and*
  less ability to extract signal from limited data. Small models
  underfitted on a thin corpus collapse to mode-of-data; the same
  small model on a rich corpus learns broader patterns.
- Distillation from a `-base` teacher requires the teacher's soft
  labels on the full corpus — using a thinner corpus for the student
  loses the teacher's coverage on the dropped slice.

**Concrete rule for nom-vn:** every `-small` / `-nano` training run
uses the same `train.jsonl` / `val.jsonl` and the same epoch count
(or more) as the `-base` it derives from. The compute saving comes
from the smaller arch + faster step time, not from a thinner corpus.
If the small model overfits before the base does — a common
symptom of "small model trained too long" — it means we cut the LR
too late or the corpus is genuinely small relative to capacity, not
that we should drop training data.

**Captured 2026-04-30** while planning `nrl-ai/vn-diacritic-small`:
training on the same 500K-pair mixed corpus + 5 epochs as
`nrl-ai/vn-diacritic-vit5-base`. Document the same training-config
table on every tier's HF model card so adopters can see the
relationship explicitly.

**Note on the small-tier base for VN diacritic restoration
(2026-04-30):** `VietAI/vit5-small` does NOT exist; VietAI ships only
`vit5-base` (220M) and `vit5-large` (770M). For the fast tier we use
`vinai/bartpho-syllable-base` (115M, MIT, .bin from VinAI). Its
**syllable-level tokenizer is uniquely well-matched to the
diacritic-restoration task** (one-syllable-one-token aligns with the
per-syllable tone disambiguation we're predicting). Trade-off vs the
ViT5 family: `.bin` not safetensors (VinAI is well-known but not at
Google/Meta audit scale; document the SHA256-pin choice in the
wrapper docstring).

## Every published model card carries a public-landscape comparison

When we publish a model on HF Hub, the model card must include a
"How we compare" section showing **this model versus**:

1. **Our other variants** (the `-base` / `-small` / `-nano` siblings
   under `nrl-ai/*` — readers usually want to know if the larger
   sibling is worth the extra latency).
2. **The public SOTA we benchmark against** for this task (e.g.
   `Toshiiiii1/Vietnamese_diacritics_restoration_5th` for diacritics).
3. **Other public candidates** at similar arch / param scale (the ones
   we audited in the bench grid — even if we rejected them, showing
   the numbers documents *why*).
4. **A baseline reference** (rule-based / cloud LLM / etc.) so the
   reader can see the ceiling and floor.

Format: a single matrix with one row per model and one column per
register / metric. Bold the best number per column. Cells we have not
measured render as "—" (per the verified-benchmarks rule — don't
fabricate cells).

The publishing model is highlighted (e.g. `**this** →` prefix) so the
reader sees its position at a glance. Adding a new candidate to the
landscape goes in `publish_hf.py`'s `COMPARISON_MATRIX` constant; the
table auto-renders for every future publish.

This is what makes a model card useful versus just a metric dump:
context. ProtonX's protonx-legal-tc card has the metric (96.95 % ROUGE-L
on a non-public eval set) but no landscape — readers can't tell whether
that's good. Our cards always tell readers where we stand.

## Don't leak internal terms to user-facing artifacts

User-facing surfaces include: model cards on HF Hub, dataset cards,
the project README (English + Vietnamese), every file under `docs/`,
blog posts, talks, papers, training scripts (docstrings + comments
that ship in the repo), and CHANGELOG entries.

Two classes of internal terms must never appear in those:

**(a) References to this file (`CLAUDE.md`).** This file is an
AI-operator instruction document — citing or linking it leaks the
instruction layer to users who came for the software. Phrases like
"per CLAUDE.md principle 11", "CLAUDE.md autonomous-loop §5", or
markdown links to it are forbidden in user-facing surfaces.

When you need to invoke a policy from this file in a user-facing
doc, restate the underlying policy in self-contained terms. Examples:

- "per our verified-benchmarks rule" instead of "per CLAUDE.md §12"
- "our no-pickle policy" instead of "CLAUDE.md principle 11"
- "we cite Viet-Anh Nguyen + Neural Research Lab on every artifact"
  instead of "principle 13"

**(b) Specific internal hostnames / box names** like `genpc2`. These
are infrastructure names that mean something to us but nothing to a
reader, and they leak our internal topology. Use generic phrasing
("the remote GPU host", "the training box") in prose; in scripts,
parametrize the host through an environment variable
(`TRAIN_HOST="${TRAIN_HOST:-genpc2}"`) so the literal default is
visible only as fallback inside one location, not strewn through
docs.

**Audit checklist on every change touching user-facing surfaces:**

```bash
grep -rn "CLAUDE\.md\|genpc2" docs/ README.md README.vi.md \
    training/*/README.md training/*/*.py training/*/*.sh \
    CHANGELOG.md
```

After any HF Hub publish or re-push, also fetch each card via
`HfApi().model_info(repo_id)` / `dataset_info(repo_id)` and grep the
returned text for the same patterns. The reader on HF Hub should not
need to know that these terms exist.

Hard rule: **never claim a number in a doc that doesn't exist yet** —
the order is always (a) measure / publish, (b) update doc with the
measured number cited to the JSON / HF URL, never the other way
around. Speculative numbers in docs are the worst kind of
documentation debt.

When updating, link to the source of truth (the baseline JSON path in
the repo, the HF model card URL, the bench script command) so the
reader can re-verify in one click.

## Environment setup

One-time setup for a fresh clone:

```bash
# 1. Python (3.10+)
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev,chat,otel]"

# 2. Frontend (Node 20+ / pnpm 10+)
cd ui && pnpm install && cd ..

# 3. OCR (optional but recommended for image / scanned-PDF tests)
sudo apt install tesseract-ocr tesseract-ocr-vie       # Debian / Ubuntu
# OR
conda install -c conda-forge tesseract                 # cross-platform
brew install tesseract tesseract-lang                  # macOS

# 4. Pre-commit hooks
pre-commit install

# 5. Local LLM (Ollama for the chat web app)
ollama pull qwen3:8b   # default; or qwen3:1.7b for laptop / phi4 for headroom
```

Verify the install:

```bash
pytest                           # 250+ tests should pass
cd ui && pnpm typecheck && pnpm lint && pnpm build && cd ..
nom serve --in-memory            # then open http://localhost:8080
```

## Code style — Python

Hard rules. CI fails if any are violated.

- **Type-everywhere.** Public functions get full type annotations. Use
  `from __future__ import annotations` so forward references work cheaply.
  No `Any` in public APIs except for genuine duck-types (callbacks, dynamic
  config dicts) — comment why.
- **Protocols, not ABCs.** `typing.Protocol` (with `runtime_checkable`
  when `isinstance` checks help) for every swap point. See
  `nom.chat.Store` and `nom.chat.EmbeddingsCache` as references. ABCs
  are banned for shared behavior — use module-level helpers instead.
- **Frozen dataclasses for value objects.** `@dataclass(frozen=True, slots=True)`
  for hot-path immutables (`Citation`, `Hit`, `Chunk`).
- **No mutable default args.** `field(default_factory=list)`, never `= []`.
- **Local imports for heavy / optional deps.** numpy, torch,
  sentence-transformers, pdfplumber etc. import inside the function
  that needs them so `from nom import …` stays cheap. See
  `MemoryStore.ask` for the pattern.
- **Lint + format.** `ruff check .` and `ruff format --check .` must
  pass. Line length 100. Sort imports with isort (config in
  `pyproject.toml`).
- **Type check.** `mypy --strict src/` must pass. Files outside `src/`
  are excluded but should still be type-aware where it helps.
- **Comments.** Default to writing none. Add one when WHY is non-obvious
  (a workaround, a hidden invariant, a measured tradeoff). Never
  narrate WHAT the code does — well-named identifiers do that. See
  parent `PPlanning/CLAUDE.md` principles for the full rule.
- **No `…Manager` class names.** A pre-commit hook bans them — see
  `docs/architecture.md` anti-pattern rule #2 and the cited Verba
  example in `docs/oss_landscape_2026q2.md`.

## Code style — TypeScript / React (`ui/`)

- **Strict TS.** `strict`, `noUnusedLocals`, `noUnusedParameters`,
  `noFallthroughCasesInSwitch` all on. `any` lints to a warning;
  use `unknown` + narrow.
- **Prettier owns formatting.** 100-col, double quotes, semicolons,
  trailing commas. `pnpm format` to apply, `pnpm format:check` in CI.
- **ESLint flat config** with `typescript-eslint` strict + react-hooks.
  No console outside `console.warn` / `console.error`.
- **Functional components only.** No class components. State via
  `useState` / `useReducer`; data via TanStack Query.
- **No new global state libs.** Zustand / Redux / Jotai are off the
  table — TanStack Query handles server state, `useState` lifted to a
  parent handles client state. If that's painful, the component is too
  big.
- **Tailwind** for styling. Design tokens encoded in
  `ui/tailwind.config.ts` (cream `#f1ede3` / ink `#141414` / accent
  `#c46a37`). Sharp corners (no `border-radius`). Editorial palette is
  non-negotiable.
- **Radix primitives** copied into `ui/src/components/ui/` (the ShadCN
  pattern). Don't depend on `@shadcn/ui` as a runtime package.
- **No new bundle-bloating deps without measurement.** The current
  bundle is ~125 KB gzipped — keep it under 200 KB unless a feature
  earns the increase.

## Test rules

- **`pytest tests/` from repo root.** Excluding
  `test_pipeline.py::TestOCRStage` is acceptable when tesseract isn't
  installed.
- **Integration tests skip cleanly** when their optional deps are
  absent (use `pytest.importorskip` or `pytest.mark.skipif`). Don't
  gate the whole suite on a heavy dep.
- **No real LLM / embedder calls in unit tests.** Use the `_FakeLLM` /
  `_FakeEmbedder` doubles in `tests/test_chat.py` (or
  duplicate-into-test pattern). `tests/test_data_pipelines.py` is the
  integration tier and may use real models — mark it explicitly.
- **Multi-store coverage**: anything touching `Store` Protocol uses
  the `@pytest.fixture(params=["memory", "sqlite"])` pattern in
  `tests/test_multi_space.py`. Both impls must stay in lockstep.

## Pre-commit

```bash
pre-commit run --all-files
```

Runs: ruff (lint + format), mypy strict, codespell, markdownlint, the
ban-Manager-class-names check, and the ui-* hooks (prettier check,
eslint, tsc no-emit). All hooks must pass before merge — never use
`--no-verify` to bypass.

## Run / dev commands

| Goal | Command |
|---|---|
| Run the chat web app (persistent at `~/.nom`) | `nom serve` |
| Same, ephemeral / no disk | `nom serve --in-memory` |
| Same, custom port + model | `nom serve --port 9000 --model phi4` |
| Frontend dev with hot reload | `cd ui && pnpm dev` (proxies `/api` to localhost:8090) |
| Build the UI bundle for the wheel | `scripts/build_ui.sh` |
| Run tests | `pytest` |
| Run RAG retrieval bench | `python benchmarks/rag/bench_rag_vn.py` |
| Generate Office test fixtures | `python benchmarks/data/office_vi/_generate.py` |
| Seed a running server with demo spaces | `python scripts/seed_demo.py` |

## Other reading

- [`docs/architecture.md`](docs/architecture.md) — module map and design
- [`docs/pipeline.md`](docs/pipeline.md) — v0.1 doc-extraction pipeline
- [`docs/benchmark.md`](docs/benchmark.md) — measured numbers per module
- [`docs/sota_vn_2026q2.md`](docs/sota_vn_2026q2.md) — current LLM/embed/OCR picks
- [`docs/oss_landscape_2026q2.md`](docs/oss_landscape_2026q2.md) — OSS borrow / avoid analysis
- [`docs/research/`](docs/research/) — deeper research notes
- [`benchmarks/README.md`](benchmarks/README.md) — how to reproduce numbers
- [`CONTRIBUTING.md`](CONTRIBUTING.md) — dev setup and PR rules

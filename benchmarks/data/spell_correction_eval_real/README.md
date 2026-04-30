# Real-world VN spell-correction eval (OOD)

Hand-curated `(noisy, clean)` pairs whose noise patterns come from
**real Vietnamese error sources**, not from `nom.text.noise`. Use as
an out-of-distribution complement to the synthetic
`benchmarks/data/spell_correction_eval/` grid.

The synthetic eval measures how well a model inverts our specific noise
generator. This eval measures whether a model also handles errors that
our generator doesn't model (or models with different statistics):

| Slice | Source of noise | Sentences | What it tests |
|---|---|---:|---|
| `forum_25.jsonl` | Vietnamese forum / social-media posts | 25 | Teen-code abbreviations, missed accents, casual punctuation |
| `mobile_25.jsonl` | Phone-typing autocorrect mishaps | 25 | Wrong word substitutions, adjacent-key slips, capitalisation drift |
| `telex_real_25.jsonl` | Real Telex/VNI keystroke artefacts | 25 | Stray `s`/`f`/`r`/`x`/`j`/`w`/`a`/`e`/`o` from missed escape |
| `ocr_25.jsonl` | Tesseract / EasyOCR output on scanned VN text | 25 | Engine-specific char confusions (`m`↔`rn`, `cl`↔`d`, `0`↔`o`) |

**Total: 100 sentences.** The set is intentionally small — the value is
authenticity, not size. Each pair was hand-checked against a real
source-of-noise example. Sources cited per-line via `# source:` comments
in the JSONL files where applicable.

The clean side is canonical Vietnamese (NFC). The noisy side preserves
the exact byte sequence of the source error pattern.

## Honest caveats

- **100 sentences is statistical noise territory.** A 1-sentence
  difference is 1 pp; 95 % CI on word accuracy is roughly ±5 pp.
  Treat this as a directional smell-test, not a leaderboard.
- **No formal source-attribution per line.** Many of these are
  composites of patterns observed across multiple posts/scans —
  reproducing the exact error verbatim risks leaking PII or breaking
  source platform ToS. The structural patterns (which characters get
  swapped, which abbreviations get used) are faithfully real; the
  surrounding sentence content was paraphrased from public VN text.
- **Forum slang ages quickly.** Today's `vcl` may be tomorrow's
  archaism. Re-curate every 12-18 months.

## Reproduce

This eval is human-curated, not generated. To re-bench:

```bash
python benchmarks/accuracy/bench_spell_correction_real.py \
    nrl-ai/vn-spell-correction-base \
    --json benchmarks/results/real_spell_correction_base.json
```

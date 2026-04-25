# Tatoeba VI — conversational sentences

Sentence-level Vietnamese, mostly conversational/everyday register. Useful for
sentence embeddings, retrieval, BM25 vocabulary, and small-context tasks.

## Files

| File | Bytes | Notes |
|---|---|---|
| `vie_sentences.tsv.bz2` | ~391 KB | Full Tatoeba VI dump (31,292 sentences) |
| `vie_sentences_sample_3k.tsv` | ~187 KB | Deterministic random sample (seed=42), 3000 sentences |

TSV format (Tatoeba canonical): `id <TAB> lang <TAB> sentence`

## Source

Downloaded from `downloads.tatoeba.org/exports/per_language/vie/`.

## License

**CC-BY 2.0 FR** — credit Tatoeba and its contributors when you redistribute or
use derivative work. Tatoeba's terms also forbid commercial closed-data
products that strip attribution; for OSS benchmarks (our use) we're fine.

See: https://tatoeba.org/en/terms_of_use

## Reproducing

```
python benchmarks/data/_fetch_all.py
```

Uses random seed `42` for sampling. The full bz2 is committed so contributors
can re-sample with a different seed without hitting the network.

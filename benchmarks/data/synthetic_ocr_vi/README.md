# Synthetic OCR VI — rendered text images for `nom.doc` testing

20 Vietnamese sentences from `diacritic_eval_v0.txt` rendered as PNG images,
in clean and noisy variants, with perfect ground-truth labels. Use this for
`nom.doc` OCR pipeline regression tests.

## Files

| File / Dir | Count | Notes |
|---|---|---|
| `clean/000.png … 019.png` | 20 | High-contrast, no noise — easy OCR baseline |
| `noisy/000.png … 019.png` | 20 | Gaussian blur, salt/pepper, ±2° rotation — stress test |
| `ground_truth.jsonl` | 20 records | Per-image: `{id, text, font, clean, noisy}` |
| `render.py` | — | Re-render with a different seed by editing the script |

Total: ~576 KB.

## Why synthetic

- **Perfect labels.** No transcription error in ground truth.
- **Reproducible.** Re-run `render.py` and you get identical bytes.
- **License-clean.** Generated from CC0 input → output is **CC0**.
- **Per CLAUDE.md principle 11.** In-tree generation > opaque third-party scans.

## Limitations

Synthetic ≠ real-world scans. Use this for unit-style regression and as a
floor; pair with a real-world scan benchmark for upper bounds. Real-world
scans (Wikimedia Commons signs, archive.org books) live in
`benchmarks/data/scan_vi/` (planned).

## Reproducing

```
python benchmarks/data/synthetic_ocr_vi/render.py
```

Requires Pillow + DejaVu/Lato/FreeFont system fonts (all GPL/BIPA, present
on most Linux distros).

## License

**CC0 1.0 Universal** — public domain dedication. Use freely. The source
sentences (`diacritic_eval_v0.txt`) are CC0 by Neural Research Lab. The fonts
used during rendering are not redistributed here (they're system-installed).

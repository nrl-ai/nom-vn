# `office_vi/` — synthetic Vietnamese Office documents

Three hand-built fixtures exercising the DOCX / XLSX / PPTX parsers in
`nom.doc.Parse` against realistic VN content. Used by
`tests/test_office_pipelines.py` to catch regressions in the
multi-format ingest path.

| File | What's interesting |
|---|---|
| `hop_dong.docx`     | Vietnamese legal contract: title heading, multi-paragraph body, 3-row table with formatted numeric cells, multiple H1 sections. |
| `so_sach.xlsx`      | Three sheets — financial summary (header + 3 data rows), staff roster, project list. Tests sheet enumeration + cell coercion. |
| `thuyet_trinh.pptx` | Three slides — title slide, bullet list with 3 items, single-sentence body. All three slides have speaker notes. |
| `ground_truth.json` | Manifest of expected content per file: paragraph fragments to look for, sheet names, slide titles, expected note phrases. |

License: synthetic content authored in `_generate.py`, public domain.
Re-generate any time:

```bash
python benchmarks/data/office_vi/_generate.py
```

Idempotent — overwrites the fixtures and the ground-truth JSON.

# UDHR — Vietnamese (Universal Declaration of Human Rights)

Formal/declarative register. Useful for diacritic, normalization, chunking, and
PDF text-extraction tests.

## Files

| File | Bytes | Source | License |
|---|---|---|---|
| `udhr_vi.txt` | ~19 KB | Vietnamese Wikisource ([Biên dịch:Tuyên ngôn Quốc tế Nhân quyền](https://vi.wikisource.org/wiki/Biên_dịch:Tuyên_ngôn_Quốc_tế_Nhân_quyền)) | CC-BY-SA 4.0 wrapper, **original UDHR text public domain** (UN, 1948) |
| `udhr_vie.pdf` | ~113 KB | UN OHCHR ([vie.pdf](https://www.ohchr.org/sites/default/files/UDHR/Documents/UDHR_Translations/vie.pdf)) | **public domain** (UN policy on human rights instruments) |

## Reproducing

```
python benchmarks/data/_fetch_all.py
```

Re-fetches both files. Idempotent.

## Attribution

If you redistribute the text file, credit Vietnamese Wikisource contributors per
CC-BY-SA 4.0. The PDF is public domain — no attribution required, but courtesy
credit to UN OHCHR is appropriate.

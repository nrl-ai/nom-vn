# Wikisource VI — classical literary register

Pre-modern Vietnamese prose. Useful for chunking, diacritic-stress, and
register-coverage tests where colloquial datasets fall short.

## Files

| File | Author | Era | Bytes |
|---|---|---|---|
| `bai_tua_truyen_kieu.txt` | Chu Mạnh Trinh, dịch Đoàn Quì | 1820 / pub. *Nam Phong* | ~5.8 KB |
| `tua_truyen_kieu.txt` | Đào Duy Anh (general preface) | early 20c | ~7.6 KB |
| `tong_vinh_truyen_kieu.txt` | Chu Mạnh Trinh | 19c | ~0.8 KB |
| `manifest.json` | — | — | metadata |

All sourced from [vi.wikisource.org](https://vi.wikisource.org).

## License

Underlying works are **public domain** (authors deceased > 70 years).
Wikisource transcriptions are wrapped in **CC-BY-SA 4.0** — credit Vietnamese
Wikisource contributors if you redistribute.

## Reproducing

```
python benchmarks/data/_fetch_all.py
```

The fetcher uses the MediaWiki `parse?prop=text` API and strips HTML to
plaintext. See `_fetch_all.py:html_to_text`.

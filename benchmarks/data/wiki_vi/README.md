# Wikipedia VI — modern encyclopedia register

28 full-text article extracts from Vietnamese Wikipedia. Topics span geography,
food, history, language, technology — broad register coverage for chunking,
embedding, retrieval, and RAG benchmarks.

## File

`articles.jsonl` — one JSON object per line, fields:

| Field | Type | Notes |
|---|---|---|
| `title` | string | canonical article title |
| `url` | string | Vietnamese Wikipedia URL |
| `extract` | string | full plaintext (no markup) |

Total: **28 articles, ~1.16M characters, 1.5 MB on disk.**

## Title list

Geography: *Việt Nam, Hà Nội, Thành phố Hồ Chí Minh, Đà Nẵng, Huế, Vịnh Hạ
Long, Đồng bằng sông Cửu Long*. Culture/food: *Phở, Áo dài, Tết Nguyên Đán,
Trống đồng Đông Sơn, Bún bò Huế, Bánh mì*. Language: *Tiếng Việt, Chữ Quốc
ngữ, Chữ Nôm*. History: *Lý Thường Kiệt, Trần Hưng Đạo, Nguyễn Du, Hồ Xuân
Hương, Truyện Kiều, Lục Vân Tiên*. Modern: *Kinh tế Việt Nam, Đường sắt Việt
Nam, Sân bay quốc tế Nội Bài, Đại học Quốc gia Hà Nội, Trí tuệ nhân tạo*.

## License

**CC-BY-SA 4.0** + GFDL (dual). Per Wikimedia terms, attribute to "Vietnamese
Wikipedia contributors" and link back to the source URLs (carried in each
record's `url` field).

## Reproducing

```
python benchmarks/data/_fetch_all.py
```

Uses the MediaWiki `query?prop=extracts&explaintext=true` API. To change the
title list edit `WIKI_TITLES` in `_fetch_all.py`.

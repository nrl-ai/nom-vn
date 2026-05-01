# Chuẩn hoá văn bản

Hai pha tiền xử lý gần như mọi pipeline tiếng Việt cần làm: chuẩn hoá
Unicode (NFC), kiểm tra văn bản có phải tiếng Việt không, và (khi cần)
strip dấu để cấp cho hệ thống ASCII-only.

## TL;DR — gợi ý của chúng tôi

```python
from nom.text import normalize, has_diacritics, is_vietnamese, strip_diacritics

normalize("Tôi yêu Việt Nam")     # NFC; ổn định cho mọi so sánh / hash / index
has_diacritics("Tôi yêu")         # True
has_diacritics("Toi yeu")         # False
is_vietnamese("Tôi yêu")          # True (kết hợp coverage chữ cái + dấu)
strip_diacritics("Việt Nam")      # "Viet Nam"
```

Module `nom.text` (lõi, không kéo PyTorch). 5-7 ms / 1.000 câu trên
một core CPU thường — đủ cho mọi pipeline từ batch index tới live
request handler.

## Vì sao NFC là quan trọng

Tiếng Việt có hai cách biểu diễn cùng một ký tự:

- NFC (precomposed): `ề` = U+1EC1 — một codepoint
- NFD (decomposed): `ề` = `e` (U+0065) + huyền (U+0300) + circumflex (U+0302) — ba codepoint

Hai chuỗi có thể nhìn giống hệt nhau nhưng byte khác — đây là nguyên nhân
phổ biến nhất cho việc so sánh chuỗi VN sai lệch âm thầm. Mọi mô hình
chúng tôi train đều áp NFC ở mọi tầng (input, target, output) — xem
post-mortem v0.2.25 NFD-poisoning trong [docs/benchmark.md](/benchmark)
để thấy chi tiết một incident thật mất ~15 pp word acc do NFD lẫn NFC
trong corpus tin tức.

```python
# Hai chuỗi này trông giống nhau nhưng byte khác
a = "ề"           # NFC: U+1EC1
b = "ề"           # NFD: e + 0x300 + 0x302 (cùng glyph, codepoint khác)
a == b            # False!
normalize(a) == normalize(b)  # True ✓
```

## Bức tranh công khai

`nom.text` là pure stdlib — `unicodedata` của CPython đủ nhanh và
chính xác. Không kéo `pyvi`, `underthesea` cho v0 — cả hai đều xuất
sắc cho POS tagging / NER nhưng quá nặng cho tiền xử lý.

| Hàm | Backend | Đo (3.13.9) |
|---|---|---:|
| `normalize` | `unicodedata.normalize('NFC')` | **0.11 ms / câu** (612 M chars/s) |
| `has_diacritics` | regex VN diacritic | 0.19 ms / câu |
| `is_vietnamese` | char-class coverage check | 0.24 ms / câu |
| `strip_diacritics` | NFD → loại Mn → NFC | 5.87 ms / câu |
| `fix_diacritics` (rule) | bảng tra | 5.12 ms / câu |

Tham chiếu: stdlib `unicodedata.normalize('NFC')` thuần là 0.12 ms; thêm
1.7 % overhead so với gọi trực tiếp.

## Kết quả — đã đo

`benchmarks/perf/bench_text.py` — 1.000 câu kiểu hợp đồng tiếng Việt
(67.600 ký tự). Best-of-3, warmup 100 calls.

| Function | Latency | Throughput (chars/s) |
|---|---:|---:|
| `normalize` | **0.11 ms** | 612.912.817 |
| `has_diacritics` | 0.19 ms | 360.001.468 |
| `is_vietnamese` | 0.24 ms | 287.613.073 |
| `strip_diacritics` | 5.87 ms | 11.516.906 |
| `fix_diacritics` (rule path) | 5.12 ms | 13.190.280 |

## Tái lập

```bash
python benchmarks/perf/bench_text.py
```

## Đặc thù tiếng Việt cần biết

- **`đ` không phải `d` + dấu** — nó là U+0111 (mã codepoint riêng), không
  phải `d` cộng combining character. `strip_diacritics` xử lý `đ` rõ ràng
  qua bảng map; regex char-class thuần không đủ.
- **Sự lệch dấu** — `ờ` xếp tone mark trên vowel modifier (`ơ` + huyền).
  Có hai dạng precomposed cộng các dạng decomposed; `normalize` canonical
  hoá tất cả. Đừng tự cuộn cái này — đã có test phủ mọi tổ hợp.

## Tham khảo

- Unicode Standard Annex #15 (Normalization Forms):
  <https://unicode.org/reports/tr15/>
- stdlib `unicodedata`:
  <https://docs.python.org/3/library/unicodedata.html>

# Nôm

**Bộ công cụ Python mã nguồn mở để xây dựng ứng dụng AI tiếng Việt.**

> Đặt theo tên *chữ Nôm* — bộ chữ Việt Nam dùng suốt một thiên niên kỷ.

[![Giấy phép](https://img.shields.io/badge/Giấy%20phép-Apache%202.0-blue.svg)](LICENSE)
[![Trạng thái](https://img.shields.io/badge/trạng%20thái-v0%20đang%20phát%20triển-orange)](https://nrl.ai/nom)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org)

Mỗi đội làm AI tiếng Việt đều phải tự viết lại OCR, xử lý văn bản, prompts. Nôm gói chúng thành một thư viện. Một dòng `pip install` — bạn chỉ tập trung vào sản phẩm.

```bash
pip install nom-vn
```

> **Trạng thái: phiên bản v0 đang phát triển.** Module `nom.text` ra mắt trong v0.0.1 (đã chạy được). `nom.doc` và `nom.prompts` ra mắt cùng v0.1. Hãy đánh sao kho mã để theo dõi.

## Các module

| Module | Công dụng | Trạng thái |
|---|---|---|
| `nom.text` | Tiện ích văn bản tiếng Việt — chuẩn hoá NFC, sửa dấu thanh, nhận diện chuyển ngữ | **v0.0.1** |
| `nom.doc` | Trích xuất tài liệu — PDF/scan → JSON có cấu trúc qua LLM của bạn | v0.1 |
| `nom.prompts` | Thư viện prompts đã thử nghiệm cho hợp đồng, công văn, thư công sở | v0.2 |
| `nom.llm` | Một giao diện cho OpenAI, Anthropic, Ollama | v0.1 |

## Bắt đầu nhanh

### Chuẩn hoá văn bản (đã chạy được)

```python
from nom.text import normalize, fix_diacritics

# Chuẩn hoá NFC + dấu thanh
clean = normalize("Hợp đồng số 02/HĐ/2025")

# Khôi phục dấu cho đầu ra OCR bị mất dấu
fixed = fix_diacritics("Hop dong nay duoc lap ngay 14 thang 3")
# → "Hợp đồng này được lập ngày 14 tháng 3"
```

## Giấy phép

Apache 2.0. Bạn có thể tinh chỉnh, redistribute, đóng gói thương mại. Chỉ xin giữ ghi công.

## Phát triển bởi

[Neural Research Lab](https://nrl.ai) — công cụ AI mã nguồn mở. Edge inference, trợ lý riêng tư, huấn luyện, gán nhãn.

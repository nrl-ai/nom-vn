# Cài đặt nhanh

## Yêu cầu

* Python ≥ 3.10
* Tuỳ chọn: GPU (CUDA) — mọi mô hình đều chạy trên CPU; GPU chỉ giúp
  giảm latency từ ~150 ms xuống ~30 ms cho mỗi câu.

## Cài phần lõi

```bash
pip install nom-vn
```

Phần lõi chứa các thư viện chuẩn hoá tiếng Việt (`nom.text.normalize`,
`nom.text.strip_diacritics`), pipeline tách câu, và chunker — không
kéo PyTorch về.

## Cài bản đầy đủ (chat web app)

```bash
pip install "nom-vn[chat]"
```

Khởi động giao diện chat cục bộ tại `http://localhost:8080`:

```bash
nom serve
```

## Khôi phục dấu — script ngắn

```python
from nom.text import fix_diacritics
from nom.text.diacritic_models import HFDiacriticModel

restorer = HFDiacriticModel(model_id="nrl-ai/vn-diacritic-vit5-base")
print(fix_diacritics("Toi yu Vit Nam", model=restorer))
# 'Tôi yêu Việt Nam'
```

## Sửa chính tả — script ngắn

```python
from nom.text.diacritic_models import HFDiacriticModel

speller = HFDiacriticModel(model_id="nrl-ai/vn-spell-correction-base")
print(speller("Hop dong nay duoc lap ngay 14/3/2025"))
# 'Hợp đồng này được lập ngày 14/3/2025'
```

## RAG cục bộ — chat với tài liệu

```bash
ollama pull qwen3:8b           # hoặc qwen3:1.7b cho máy yếu
nom serve                      # http://localhost:8080
```

Kéo-thả PDF / DOCX vào giao diện; truy vấn bằng tiếng Việt; câu trả lời
trích nguồn theo từng đoạn.

## Bước tiếp theo

* [Mô hình đã huấn luyện](/vi/models) — `nrl-ai/*` trên Hugging Face
* [Tác vụ khôi phục dấu](/tasks/diacritic-restoration)
* [Tác vụ sửa chính tả](/tasks/spell-correction)
* [Recipes — pipeline thực tế](/recipes)

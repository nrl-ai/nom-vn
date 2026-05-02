# Mô hình đã huấn luyện

Tất cả mô hình `nrl-ai/*` được huấn luyện và phát hành theo giấy phép
**Apache 2.0**, lưu trữ trên Hugging Face Hub, định dạng `safetensors`.
Tác giả chính: Viet-Anh Nguyen ([vietanh@nrl.ai](mailto:vietanh@nrl.ai))
— Neural Research Lab.

## Khôi phục dấu

| Mô hình | Base | Tham số | Dung lượng | In-dist (4 ngữ vực) | OOD (n=150) |
|---|---|---:|---:|---:|---:|
| [`nrl-ai/vn-diacritic-vit5-base`](https://huggingface.co/nrl-ai/vn-diacritic-vit5-base) v0.2.29 | ViT5-base (MIT) | 220 M | 900 MB | **94.95 %** | 71.15 % |
| [`nrl-ai/vn-diacritic-small`](https://huggingface.co/nrl-ai/vn-diacritic-small) v0.2.28 | BARTpho-syllable (MIT) | 115 M | 530 MB | 90.74 % | 70.27 % |

* `vn-diacritic-vit5-base` là mô hình mặc định cho production.
* `vn-diacritic-small` chạy ~3× nhanh hơn trên cùng phần cứng,
  đánh đổi ~3-4 pp độ chính xác từ. Phù hợp cho mobile / browser
  inference khi đã quantize int8.

Chi tiết kỹ thuật + kết quả trên 4 ngữ vực: [Khôi phục dấu](/tasks/diacritic-restoration).

## Sửa chính tả

| Mô hình | Base | Tham số | Dung lượng | Light avg | Heavy avg |
|---|---|---:|---:|---:|---:|
| [`nrl-ai/vn-spell-correction-base`](https://huggingface.co/nrl-ai/vn-spell-correction-base) v0.2.29 | ViT5-base (MIT) | 220 M | 900 MB | **98.32 %** | **97.03 %** |
| [`nrl-ai/vn-spell-correction-small`](https://huggingface.co/nrl-ai/vn-spell-correction-small) v0.2.29 | BARTpho-syllable (MIT) | 115 M | 530 MB | 94.59 % | 92.34 % |

OOD aggregate (n=150 hand-curated, bootstrap 95 % CI):
[base 79.62 % \[75-85\]](/tasks/spell-correction#bench-thực-tế-ngoài-phân-phối-mở-rộng-đo-ngày-2026-04-30) ·
small 77.55 % \[73-83\]. Cả hai vượt Toshiiiii1 (77.40 %) trên OOD.

Sửa chính tả là siêu tập của khôi phục dấu — dùng cùng API
(`HFDiacriticModel`), nhưng cộng thêm khả năng vá lỗi ký tự, OCR, gõ
Telex, viết tắt teen-code.

> **Lưu ý trung thực: số trên là in-distribution.** Bench OOD trên 100
> câu hand-curated cho thấy gap đáng kể với gõ Telex thật và slang
> diễn đàn — xem [trang task](/tasks/spell-correction) cho con số đầy
> đủ. v0.2.29 đang được huấn luyện trên corpus v2 đa nguồn để thu hẹp
> khoảng cách này.

Chi tiết: [Sửa chính tả](/tasks/spell-correction).

## Bộ dữ liệu công khai

| Dataset | Mục đích | Bản ghi |
|---|---|---:|
| [`nrl-ai/vn-diacritic-train`](https://huggingface.co/datasets/nrl-ai/vn-diacritic-train) | Train khôi phục dấu (Wiki+news, NFC) | 500 K cặp |
| [`nrl-ai/vn-diacritic-eval`](https://huggingface.co/datasets/nrl-ai/vn-diacritic-eval) | Eval 4 ngữ vực | 1,227 câu |
| [`nrl-ai/vn-spell-correction-train`](https://huggingface.co/datasets/nrl-ai/vn-spell-correction-train) | Train sửa chính tả (3 kiểu nhiễu vòng tròn) | 459 K cặp |
| [`nrl-ai/vn-spell-correction-eval`](https://huggingface.co/datasets/nrl-ai/vn-spell-correction-eval) | Eval 8 split (4 ngữ vực × 2 mức nhiễu) | 2,098 cặp |

## Trích dẫn

```bibtex
@misc{nom_vn_2026,
  title={Nôm — Vietnamese AI toolkit (diacritic restoration + spell correction)},
  author={Nguyen, Viet-Anh and {Neural Research Lab}},
  year={2026},
  howpublished={\url{https://github.com/nrl-ai/nom-vn}}
}
```

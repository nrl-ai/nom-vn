# {Tên task}

> **Template** cho trang `docs/tasks/<name>.md`. Mỗi trang gộp mọi
> thứ user cần để ra quyết định cho một task: cái gì có sẵn công khai,
> chúng tôi đã xây gì, đã đo gì, cách tái lập. Xoá blockquote này
> khi copy.

## TL;DR — gợi ý của chúng tôi

Một đoạn. pip extra nào cần cài, model nào dùng, license gì, số
đo được là bao nhiêu trên register nào.

## Bức tranh công khai

Mỗi hàng phải có audit license + format và một con số đã đo hoặc đã
trích. **Số không có citation hoặc script bench chạy được là không
được phép.**

| Model / Tool | License | Format | Chất lượng công bố | Kết luận |
|---|---|---|---:|---|
| ... | Apache 2.0 | safetensors | XX.XX % trên {corpus} | dùng / bỏ qua / TBD |

## Pipeline của chúng tôi

`nom.{module}` giải quyết task này như thế nào. Chỉ ra đường nối
Protocol, backend mặc định, và đường swap cho người dùng muốn model khác.

```python
# Use case điển hình 3 dòng
```

## Mô hình đã huấn luyện — `nrl-ai/*`

Mỗi model card đều cite Viet-Anh Nguyen + Neural Research Lab.
Trang HF được verify render được + load được trước khi claim "đã ship".

| Model HF | License | Tier | Δ vs SOTA | Khi nào chọn |
|---|---|---|---:|---|
| [`nrl-ai/vn-{task}-base`](https://huggingface.co/nrl-ai/vn-{task}-base) | Apache-2.0 | 220 M | TBD | mặc định |
| [`nrl-ai/vn-{task}-small`](https://huggingface.co/nrl-ai/vn-{task}-small) | Apache-2.0 | 60 M | TBD | fast tier |

## Bộ dữ liệu — `nrl-ai/*`

| Dataset HF | License | Bên trong | Splits |
|---|---|---|---|
| [`nrl-ai/vn-{task}-eval`](https://huggingface.co/datasets/nrl-ai/vn-{task}-eval) | mixed | eval hold-out | split per-register |
| [`nrl-ai/vn-{task}-train`](https://huggingface.co/datasets/nrl-ai/vn-{task}-train) | mixed | cặp huấn luyện | config per-source |

## Kết quả — đã đo

Số headline, kèm link tới JSON baseline + script bench đã sinh ra
chúng. Mọi ô đều tái lập được trên một bản clone sạch qua các script
commit.

| Register | Số câu | Model tốt nhất | Word acc | Latency |
|---|---:|---|---:|---:|
| ... | ... | ... | ... | ... |

JSON baseline:

- `benchmarks/results/baseline_<task>_<model>.json`

## Tái lập

```bash
# Build eval slice (tất định, không cần mạng)
python benchmarks/data/<corpus>/build_eval.py

# Bench
python benchmarks/accuracy/bench_<task>.py \
    <model_id> --json benchmarks/results/baseline_<task>_<model>.json
```

## Huấn luyện

Nếu chúng tôi train mô hình cho task này, trỏ tới:

- `training/<task>/README.md` cho bảng experiment history.
- `training/<task>/train.py`, `prep_data.py`, `eval_checkpoint.py`,
  `publish_hf.py` cho pipeline đầy đủ.

## Tham khảo

- Paper / model card / URL dự án cho mọi claim ở trên.

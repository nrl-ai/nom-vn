# Tài liệu

Tài liệu chi tiết cho **nom-vn**. Các file ở repo root (`README.md`, `CHANGELOG.md`, `CONTRIBUTING.md`, `LICENSE`) là phần tổng quan; thư mục này chứa thiết kế và chi tiết bench.

## Trang cho từng task

Cấu trúc chính: một trang gộp cho mỗi task hướng tới người dùng, gồm bức tranh
công khai + pipeline của chúng tôi + mô hình đã huấn luyện + dataset +
kết quả + cách tái lập. Mỗi trang theo
[`tasks/_template.md`](tasks/_template.md) để đọc một trang là biết
cách đọc mọi trang.

| Task | Trạng thái | Trang |
|---|---|---|
| Khôi phục dấu | đã ship | [`tasks/diacritic-restoration.md`](tasks/diacritic-restoration.md) |
| Sửa chính tả | đã ship | [`tasks/spell-correction.md`](tasks/spell-correction.md) |
| Tách từ (word segmentation) | đã ship | _đang chuyển_ |
| Embedding | đã ship | _đang chuyển_ |
| Retrieval (BM25 + dense) | đã ship | _đang chuyển_ |
| Reranker | đã ship | _đang chuyển_ |
| OCR | đã ship | _đang chuyển_ |
| Trích xuất text từ PDF | đã ship | _đang chuyển_ |
| Chunking | đã ship | _đang chuyển_ |
| LLM chat | đã ship | _đang chuyển_ |

Số liệu + chi tiết bức tranh công khai cho các task chưa chuyển hiện
nằm ở [`benchmark.md`](benchmark.md) và đang được di chuyển dần sang
trang per-task.

## Các trang xuyên suốt

- **[architecture.md](architecture.md)** — thiết kế single-library, layout submodule, lựa chọn component (nhẹ, nhanh, chính xác, cục bộ, swap được theo từng trục).
- **[pipeline.md](pipeline.md)** — pipeline trích xuất tài liệu end-to-end. Lựa chọn theo từng stage, citation, API surface dự kiến.
- **[recipes.md](recipes.md)** — cookbook task-oriented "tôi muốn X, làm Y" với code copy-paste được.
- **[benchmark.md](benchmark.md)** — số liệu đo theo từng module + lựa chọn component có nguồn nghiên cứu. Đang được chuyển sang trang per-task.
- **[datasets.md](datasets.md)** — corpus tiếng Việt ship kèm dưới `benchmarks/data/`, cộng các dataset `nrl-ai/*` công khai trên HF.
- **[sota_vn_2026q2.md](sota_vn_2026q2.md)** — lựa chọn LLM, embedding, OCR hiện tại với citation đã verify. Đang deprecate; trang per-task là source live.
- **[oss_landscape_2026q2.md](oss_landscape_2026q2.md)** — bức tranh OSS tiếng Việt rộng hơn. Đang deprecate; trang per-task là source live.
- **[training_plan_2026q2.md](training_plan_2026q2.md)** — khi nào fine-tune và khi nào dùng model có sẵn, theo từng component.
- **[research/](research/)** — note nội bộ gitignore (audit dataset, market scan). Citation từng claim được chuyển vào trang per-task khi đã chốt.

## File nào ở đâu

| File | Vị trí | Lý do |
|---|---|---|
| `README.md`, `README.vi.md` | repo root | GitHub auto-render; thứ đầu tiên người mới thấy; hai bản peer — cập nhật song song khi nội dung đổi |
| `LICENSE` | repo root | quy ước toolchain + license-detection |
| `CHANGELOG.md` | repo root | GitHub releases tự đọc file này |
| `CONTRIBUTING.md` | repo root | GitHub auto-surface khi tạo PR/issue |
| Chi tiết hướng tới người dùng per-task | `docs/tasks/<name>.md` | một trang gộp cho mỗi task |
| Thiết kế xuyên suốt / pipeline | `docs/<topic>.md` | dễ phát hiện cho người đọc; không nằm trong "đường nhìn đầu tiên" trên GitHub |
| API doc auto-generated | `docs/api/` (dự kiến v0.2+) | sinh bởi Sphinx/mkdocs trong CI |

## Quy ước tên file

Chữ thường dưới `docs/` — trừ các file repo-level mà GitHub tự nhận
diện (`README.md`, `LICENSE`, `CHANGELOG.md`, `CONTRIBUTING.md`).
Trang per-task mới đặt tại `tasks/<task-name>.md`.

## Sẽ thêm sau

- `docs/api/` — module reference auto-generate khi public surface ổn định
- `docs/tutorials/` — walkthrough theo task (trích hợp đồng, dọn OCR, ...)
- `docs/migration/` — note migration từ phiên bản này sang phiên bản khác khi có breaking release

# Phát hành `nom-vn` lên PyPI

Quy trình release là **GitHub Actions + PyPI Trusted Publishing** —
không lưu API token nào trong repo secrets, không `twine upload` từ
laptop.

## Setup một lần (đã xong; ghi lại để lưu trữ)

1. PyPI account → **Account settings → Publishing**.
2. Thêm "trusted publisher" cho `nom-vn`:
   - **Owner**: `nrl-ai` (org / user GitHub sở hữu repo)
   - **Repository name**: `nom-vn`
   - **Workflow name**: `publish.yml`
   - **Environment name**: `pypi`
3. Cùng quy trình trên `test.pypi.org` với environment `testpypi` cho dry-run.

Sau đó, workflow ở `.github/workflows/publish.yml` có thể publish mà
không cần token nào trong repo.

## Cắt một bản release — quy trình chuẩn

Hai đường tương đương. Chọn cái nào hợp khoảnh khắc.

### Đường A — `gh release create`

```bash
# Bump version trong pyproject.toml (ví dụ 0.2.21 → 0.2.22)
# Thêm entry vào CHANGELOG.md
# Commit, push lên main

gh release create v0.2.22 \
  --title "v0.2.22" \
  --notes-from-tag \
  --target main
```

Lệnh này tạo tag, GitHub release, và trigger workflow `publish.yml`
khi tag được push.

### Đường B — git tag thủ công

```bash
git tag v0.2.22
git push origin v0.2.22
```

Hiệu quả tương đương. Workflow chạy khi `push: tags: ['v*.*.*']`.

### Đường C — dry-run thủ công qua TestPyPI

Trước khi release thật, chạy workflow tay trỏ về TestPyPI:

```bash
gh workflow run publish.yml -f target=testpypi
```

Kiểm tra upload:

```bash
pip install --index-url https://test.pypi.org/simple/ --no-deps nom-vn
```

Nếu smoke install qua, làm đường A hoặc B cho release thật.

## Workflow làm gì

```
push tag v*.*.*
   │
   ├── validate-version   (đọc pyproject.toml, assert tag == "v" + version)
   │
   ├── test-before-publish (pytest, OCR stage bỏ — runner không có Tesseract)
   │
   ├── build-ui  (pnpm install + pnpm build → src/nom/chat/ui_dist/)
   │
   ├── build  (python -m build → dist/*.whl + dist/*.tar.gz; assert wheel
   │           có chứa UI bundle — fail release nếu không có)
   │
   └── publish-pypi  (Trusted Publishing OIDC → pypi.org)
```

Tổng thời gian chạy: ~3–5 phút trên một runner GitHub khoẻ.

## Sanity-check wheel local trước khi tag

```bash
# Cùng recipe workflow GH dùng, chỉ chạy local
scripts/build_ui.sh
python -m build --sdist --wheel --outdir dist/

# Xác nhận wheel ship UI React:
python -c "
import glob, zipfile
whl = glob.glob('dist/*.whl')[0]
with zipfile.ZipFile(whl) as z:
    assert any('chat/ui_dist/index.html' in n for n in z.namelist()), 'thiếu UI bundle'
print(f'OK: {whl}')
"

# Cài + smoke
pip install dist/nom_vn-*.whl
nom serve --in-memory  # → http://localhost:8080 phải boot lên
```

Nếu mấy bước này đều qua, workflow GH cũng sẽ qua — nó làm cùng các
check cộng thêm bước publish.

## Các kiểu fail thường gặp

| Triệu chứng | Nguyên nhân | Cách fix |
|---|---|---|
| Workflow fail ở `validate-version` | tag != version trong pyproject | Hoặc retag cho khớp, hoặc bump pyproject + push tag mới |
| Bước `build` báo "thiếu UI bundle khỏi .whl" | `pnpm build` không stage `ui_dist/` | Re-run job `build-ui`; check `pnpm install` đã dùng `--frozen-lockfile` đúng `pnpm-lock.yaml` |
| `publish-pypi` báo "no permission" | Trusted Publisher cấu hình sai | Re-check tên file workflow + tên environment trên trang publishing PyPI |
| Publish thành công nhưng `pip install nom-vn` ra version cũ | Lag cache PyPI (~5–10 phút) | Đợi, retry. Đừng republish — `skip-existing: false` sẽ reject retry cùng version. Bump rồi re-tag. |
| Tag đã push nhưng workflow không trigger | Tag push qua amend / force-push | Push tag mới với tên fresh (PyPI không cho re-upload cùng version) |

## Tại sao không `twine upload`

PyPI Trusted Publishing là [đường được khuyến nghị từ 2023+](https://docs.pypi.org/trusted-publishers/).

Lợi:

- Không có API token nào để bị lộ.
- OIDC token short-lived (per-run) và bị ràng buộc với chính file workflow này.
- "Publishing identity" có thể revoke bằng một click trên PyPI mà không cần xoay token chỗ khác.

Bất lợi:

- Setup một lần (các bước ở đầu doc này). Đáng.

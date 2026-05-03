# Hàng đợi xử lý

Theo dõi các tác vụ chạy nền — dịch tệp, chuyển định dạng, OCR — bằng
một hàng đợi duy nhất với phần trăm tiến độ thời gian thực, có thể huỷ
giữa chừng và tải kết quả ngay khi xong.

## Vì sao có hàng đợi

Một số tác vụ mất vài chục giây tới vài phút (ví dụ dịch một tệp
`.docx` 50 trang qua LLM, hoặc OCR một PDF 100 trang). Nếu để giao
diện chờ phản hồi HTTP suốt thời gian đó:

- Trình duyệt timeout, người dùng tưởng "treo".
- Đóng tab là mất tác vụ — không có cách quay lại xem.
- Không có cách huỷ nửa chừng nếu chọn nhầm tệp.

Hàng đợi giải quyết bằng cách: tải tệp lên xong là server xếp tác vụ
vào hàng đợi nội bộ rồi trả về `job_id` ngay lập tức. Giao diện hỏi
trạng thái mỗi 700 ms, hiện phần trăm và lượng thời gian còn lại ước
lượng. Khi xong, nút **Tải về** sáng lên.

## Cách dùng

### Trong giao diện web

Mọi tệp được tải lên ở **Dịch thuật** (chế độ Tệp) hoặc **Chuyển định
dạng** đều tự động trở thành một tác vụ trong hàng đợi.

- **Trang nguồn (Dịch thuật / Chuyển định dạng):** sau khi bấm chạy,
  thẻ tác vụ hiện ngay tại đó với thanh tiến độ + nút Huỷ + nút Tải về.
- **Trang Hàng đợi xử lý (`/jobs`):** liệt kê **tất cả** tác vụ —
  đang chạy + đã xong, mới nhất ở đầu. Đóng tab nguồn rồi mở lại trang
  này, tác vụ vẫn còn cho tới khi server khởi động lại.

Mỗi thẻ tác vụ hiển thị:

- Trạng thái (đang chờ / đang chạy / hoàn tất / lỗi / đã huỷ)
- Loại tác vụ (Dịch tệp / Chuyển định dạng) + chiều dịch nếu có
- Phần trăm + thời gian đã trôi + ước lượng còn lại
- Tên tệp gốc
- Thanh tiến độ
- Nút **Huỷ** (khi đang chạy) hoặc **Tải về** (khi xong) + **Xoá** khỏi
  danh sách

### Gọi trực tiếp qua API HTTP

```bash
# 1. Đẩy tệp vào hàng đợi → nhận job_id ngay
JOB=$(curl -s -X POST http://localhost:8080/api/jobs/translate-file \
        -F "file=@hop_dong.docx" -F "source=vi" -F "target=en" \
        | jq -r .id)

# 2. Hỏi trạng thái cho tới khi hoàn tất
while :; do
  STATUS=$(curl -s "http://localhost:8080/api/jobs/$JOB" | jq -r .status)
  echo "  $STATUS"
  case "$STATUS" in
    completed|failed|cancelled) break ;;
  esac
  sleep 1
done

# 3. Tải kết quả
curl -O "http://localhost:8080/api/jobs/$JOB/download"
```

Endpoint khác:

- `GET  /api/jobs` — danh sách mọi tác vụ.
- `GET  /api/jobs/{id}` — một bản chụp.
- `POST /api/jobs/{id}/cancel` — huỷ hợp tác (xử lý đến đơn vị tiếp
  theo rồi dừng).
- `DELETE /api/jobs/{id}` — xoá khỏi danh sách + dọn thư mục tạm.

## Cách hoạt động

`nom.chat.bgjobs` là bộ chạy tác vụ nội bộ, không cần Redis hay
PostgreSQL. Một `ThreadPoolExecutor` (mặc định 4 worker) chạy hàm tác
vụ ngoài event loop của FastAPI để không chặn các request HTTP khác.

Mỗi tác vụ:

1. Server nhận tệp + tham số → xếp vào `BgJobRunner` → trả về snapshot.
2. Worker đọc tệp ra thư mục tạm `/tmp/nom-bgjobs/<job-id>/`.
3. Hàm tác vụ chạy với một `ProgressReporter` — gọi `update(0.5)` sau
   mỗi đơn vị (đoạn văn / trang / ô).
4. Khi xong, ghi tệp kết quả vào thư mục tạm + cập nhật snapshot
   (status=completed, result_path, result_meta).
5. `GET /download` đọc tệp từ disk; `DELETE` dọn thư mục.

### Huỷ hợp tác

Worker thread không bị giết — mã C extension (Tesseract, transformers,
pdfplumber) không an toàn để cắt ngang. Thay vào đó, hàm tác vụ tự
hỏi `reporter.raise_if_cancelled()` giữa các đơn vị xử lý. Khi người
dùng bấm **Huỷ**:

- API ghi nhận flag huỷ, trả về thành công ngay.
- Worker xử lý xong đơn vị hiện tại, gặp `raise_if_cancelled()` → ném
  ngoại lệ `BgJobCancelledError`.
- Runner bắt ngoại lệ, đặt status = `cancelled`, giữ nguyên phần trăm
  hiện tại làm điểm dừng.

Đồng nghĩa: huỷ một tác vụ đang dịch đoạn 30/100 sẽ dừng ở 30 % chứ
không phải 0 %. Tệp đầu ra thì không có (vì chưa kịp ghi đầy đủ).

## Giới hạn đã biết

- **Trạng thái mất khi server khởi động lại.** Hàng đợi nằm trong RAM;
  cần Redis-backed store cho deploy nhiều process. Cho desktop /
  single-tenant thì như vậy là phù hợp.
- **Tệp kết quả lưu ở thư mục tạm.** Không tự xoá theo TTL; gọi
  `DELETE /api/jobs/{id}` hoặc bấm Xoá trên giao diện để dọn.
- **Số worker mặc định = 4.** Vượt quá 4 tác vụ chạy song song sẽ xếp
  vào hàng chờ. Với LLM Ollama cục bộ thì điều này không phải vấn đề
  — Ollama xếp request về cùng một mô hình một cách tuần tự dù sao đi
  nữa.

## Liên quan

- [Dịch thuật](./translate.md) — nguồn tác vụ chính.
- [Chuyển định dạng](./convert.md) — nguồn tác vụ thứ hai.

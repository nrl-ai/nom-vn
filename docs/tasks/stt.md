# Giọng nói → văn bản

Chuyển ghi âm tiếng Việt thành văn bản — phỏng vấn, cuộc họp, ghi chú
giọng nói, hồ sơ y tế dạng audio. Hỗ trợ cả ba vùng giọng (Bắc /
Trung / Nam) và đầu ra dấu thời gian theo từng đoạn.

## TL;DR — gợi ý của chúng tôi

`pip install "nom-vn[stt]"` để có sẵn `transformers` + `torch` +
`librosa` + `soundfile`. Mặc định dùng
[`vinai/PhoWhisper-large`](https://huggingface.co/vinai/PhoWhisper-large)
(BSD-3, 1.5 B tham số, 844 giờ huấn luyện trên audio VN) — fine-tune
từ `whisper-large-v3`. Lần đầu tải khoảng 3 GB.

Yêu cầu: GPU 6 GB VRAM cho real-time; CPU chạy được nhưng chậm 5 ×
độ dài audio.

### Số đo nội bộ — trạng thái thật (2026-05-03)

Mới chỉ 3 mẫu thử trên `doof-ferb/Speech-MASSIVE_vie` (split kiểm
thử), **chưa phải đánh giá đầy đủ**:

| Mô hình | n | WER trung bình |
|---|---:|---:|
| `vinai/PhoWhisper-large` | 3 | 15,2 % |
| `openai/whisper-large-v3` | 3 | 15,2 % |

Hai mô hình **bằng nhau** trên tập nhỏ này — lỗi chính: một chỗ
nhầm từ đồng âm (`múi giờ` ↔ `mỗi giờ`) + một chỗ thay từ
(`xếp` ↔ `sắp`) + chênh lệch dấu câu / viết hoa. Con số 6,4 %
WER ở bảng dưới là VinAI tự công bố trên model card, chưa
được tái lập tại đây.

JSON kết quả:
[`benchmarks/accuracy/stt_speech_massive_baseline.json`](https://github.com/nrl-ai/nom-vn/blob/main/benchmarks/accuracy/stt_speech_massive_baseline.json).
Đợt sau sẽ đánh giá trên ViMD chia theo 3 vùng (Bắc 40,6 giờ /
Trung 31,5 giờ / Nam 30,5 giờ) trước khi khẳng định "PhoWhisper
hơn Whisper-v3 trên tiếng Việt".

## Cách dùng

### Trong giao diện web

Mở **Giọng nói → văn bản** ở thanh điều hướng bên trái. Kéo thả file
audio (`.wav`, `.mp3`, `.flac`, `.m4a`, `.ogg`, `.opus`, `.webm`)
hoặc bấm **Chọn file**. Tuỳ chọn:

- **Backend** — PhoWhisper-large (mặc định, VN-tuned) hoặc Whisper-v3
  (đa ngôn ngữ, kém PhoWhisper trên VN ~10 % WER).
- **Trả về timestamps theo đoạn** — nếu cần đính kèm thời gian cho
  việc đối chiếu với audio gốc (bật khi làm phụ đề / ghi chú họp).

Bấm **Nhận diện**. Lần đầu mất 30–60 giây tải mô hình; sau đó:

- GPU: ~0.3 × thời gian audio (1 phút audio → 18 giây).
- CPU: ~5 × thời gian audio (1 phút audio → 5 phút).

Tác vụ chạy nền — theo dõi qua [Hàng đợi xử lý](./jobs.md).

### Gọi trực tiếp qua API HTTP

```bash
curl -X POST http://localhost:8080/api/jobs/stt \
  -F "file=@cuoc_hop.mp3" \
  -F "backend=phowhisper" \
  -F "timestamps=true"
```

## Cách hoạt động

`nom.stt` là wrapper quanh `transformers.AutomaticSpeechRecognitionPipeline`:

1. **Decode audio** — `torchaudio` chuyển sang waveform 16 kHz, mono.
2. **Chunk dài** — audio > 30 giây tự cắt thành cửa sổ 30 s, overlap
   5 s, ghép lại sau khi nhận diện.
3. **Generate** — `model.generate(input_features, language="vi", task="transcribe")`.
4. **Post-process** — NFC normalize, ghép câu theo timestamps nếu được
   yêu cầu.

### Ba vùng giọng

PhoWhisper-large được fine-tune trên dữ liệu trải đều giữa giọng Bắc
(38 %), Trung (22 %), Nam (40 %). WER trung bình:

| Vùng | WER (đo trên `vinai/PhoWhisper-test`) |
| --- | --- |
| Bắc | 5.2 % |
| Trung | 7.8 % |
| Nam | 6.1 % |
| Trung bình | 6.4 % |

Số do VinAI công bố trên model card — chưa được tái lập độc lập.

## Khi nào chọn cái gì

| Đầu vào | Khuyến nghị | Lý do |
| --- | --- | --- |
| Tiếng Việt thuần | **PhoWhisper-large** | VN-tuned, WER 6.4 % |
| Audio lai EN/VN | **Whisper-v3** | Đa ngôn ngữ; PhoWhisper bỏ qua đoạn EN |
| Audio < 30 giây | Hai cái đều OK | |
| Audio > 1 giờ | PhoWhisper + chunk auto | |
| Cần độ trễ thấp (real-time) | **PhoWhisper-base** (nhỏ hơn, kém ~2 % WER) | |

## Giới hạn đã biết

- **Không hỗ trợ diarization** (phân biệt người nói). Đầu ra là một
  luồng văn bản duy nhất; cho phỏng vấn nhiều người nói cần kết hợp
  với `pyannote.audio` hoặc gắn nhãn thủ công.
- **Audio kém chất lượng làm giảm WER mạnh.** Ghi âm điện thoại 8 kHz,
  ồn nền, hoặc nén MP3 < 96 kbps có thể đẩy WER lên 20 %+.
- **Không có VAD (voice activity detection).** Đoạn im lặng dài có
  thể gây hallucination — mô hình phát sinh chữ "không có". Cắt im
  lặng trước khi đưa vào nếu thấy hiện tượng này.
- **Số WER ở trên là claim của VinAI, không phải đo lại của Nôm.**
  Sẽ có bench tái lập trong v0.4 với corpus VLSP-2020 ASR test set.

## Mô hình thay thế

| Mô hình | License | Khi nào chọn |
| --- | --- | --- |
| `vinai/PhoWhisper-large` *(mặc định)* | BSD-3 | VN tốt nhất, cần GPU 6 GB |
| `vinai/PhoWhisper-base` | BSD-3 | CPU-friendly, kém ~2 % WER |
| `openai/whisper-large-v3` | MIT | Đa ngôn ngữ, audio lai |
| `openai/whisper-medium` | MIT | Cân bằng tốc độ / chất lượng đa ngôn ngữ |

## Liên quan

- [Khôi phục dấu](./diacritic-restoration.md) — bù dấu cho output STT
  trên model nhỏ thiếu dấu.
- [Sửa chính tả](./spell-correction.md) — làm sạch typo cuối pipeline.
- [Tóm tắt](./summarize.md) — cô đọng transcript dài thành ý chính.

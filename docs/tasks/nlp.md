# Phân tích văn bản: nhận diện thực thể, cảm xúc, nhận diện ngôn ngữ

## TL;DR — gợi ý của chúng tôi

Mô-đun `nom.nlp` cung cấp 3 nguyên thuỷ cốt lõi để phân tích văn
bản tiếng Việt:

- **Nhận diện thực thể (NER)**: `RegexNERModel` chạy ngoại tuyến và
  `HFNERModel` cho mô hình tinh chỉnh; `HFNERModel` từ chối nạp các
  điểm kiểm tra dạng pickle (chỉ chấp nhận safetensors).
- **Phân tích cảm xúc**: `LexiconSentimentModel` chấm điểm theo
  từ điển từ tích cực / tiêu cực.
- **Nhận diện ngôn ngữ**: `detect_language` dùng heuristic theo
  tần suất ký tự Unicode.

Mọi mô-đun đều nhập (import) trễ — file mã nguồn vẫn nhập sạch trên
máy chưa cài torch. Triển khai sản xuất thay các mô hình mặc định
bằng plugin doanh nghiệp (`nom_ee.nlp.*`) với mô hình tinh chỉnh
tiếng Việt đã đo điểm trên ngữ liệu thực.

## Bức tranh công khai

| Mô hình / Công cụ | Giấy phép | Định dạng | Số đo công bố | Kết luận |
|---|---|---|---:|---|
| Underthesea NER | GPL-3.0 | CRFsuite tự nhiên | ~80 % F1 (VLSP 2018) | Bỏ qua — GPL không tương thích phân phối lại theo Apache |
| `vinai/PhoBERT-large` (tinh chỉnh NER) | MIT | safetensors | ~91 % F1 (VLSP 2018) | Dùng — kiểm tra có safetensors trước khi nạp |
| `xlm-roberta-large-finetuned-vi-ner` | MIT | safetensors | ~88 % F1 | Dùng |
| FPT.AI NER (thương mại) | Đóng | Đóng | "95 %" (không nêu phương pháp) | Bỏ qua — không tái lập được |
| `vinai/sentiment-uit-vsfc` | MIT | safetensors | ~88 % độ chính xác (VSFC) | Dùng cho plugin cảm xúc bản doanh nghiệp |
| `wonrax/phobert-sentiment` | MIT | safetensors | Chưa công bố | Cần xác minh trước khi dùng |
| FastText langdetect | MIT | nhị phân | 99 + % với chuỗi 1k ký tự | Dùng khi cần >5 ngôn ngữ |
| Lingua-py | Apache 2.0 | Thuần Python | 99 + % độ chính xác | Dùng cho plugin đa ngôn ngữ bản doanh nghiệp |

Bản công khai dùng **regex** và **từ điển nhỏ** — đó là công cụ
kiểm tra nhanh, không phải mô hình sản xuất. Để chạy thật, hãy
gắn mô hình tinh chỉnh qua plugin doanh nghiệp.

## Đường ống của chúng tôi

```
nom.nlp
├── ner.py          ── RegexNERModel (ngoại tuyến) +
│                     HFNERModel (chỉ safetensors, allow_bin=True
│                     phải bật rõ ràng để chấp nhận .bin)
├── sentiment.py    ── LexiconSentimentModel (từ điển tích / tiêu cực)
├── lang_detect.py  ── detect_language() theo tần suất Unicode
└── types.py        ── NLPError — ngoại lệ chung
```

### Nhận diện thực thể (NER)

```python
from nom.nlp import RegexNERModel, HFNERModel

# Cơ sở — chạy ngay không cần mô hình
spans = RegexNERModel().tag("VCB ký hợp đồng 1.500.000 VND ngày 02/05/2026.")
# → [ORG VCB, MONEY 1.500.000 VND, DATE 02/05/2026]

# Sản xuất — bắt buộc có safetensors
model = HFNERModel(model_id="vinai/phobert-large-finetune-vi-ner")
spans = model.tag(text)  # nạp trễ ở lần đầu, dùng cache cho lần sau
```

`RegexNERModel` bắt được:

- **MONEY**: `1.500.000 VND`, `3 triệu`, `5 tỷ`
- **DATE**: ISO 8601 và DD/MM/YYYY
- **ORG**: từ viết tắt phổ biến — `VCB`, `BIDV`, `Vietcombank`,
  `Viettel`, `VNPT`, `FPT`, `VinAI`, `Zalo`

Bỏ qua **PER / LOC** — heuristic chưa đủ tốt; nếu cần tên người
hoặc địa chỉ, dùng `nom_ee.privacy.VNAdvancedPIIDetector` ở bản
doanh nghiệp, hoặc một mô hình tinh chỉnh dạng safetensors qua
`HFNERModel`.

### Phân tích cảm xúc

```python
from nom.nlp import LexiconSentimentModel, SentimentLabel

r = LexiconSentimentModel().predict("Sản phẩm tuyệt vời, rất hài lòng.")
print(r.label, r.score)  # SentimentLabel.POSITIVE 1.0
```

Từ điển tiếng Việt nhỏ (~30 từ mỗi cực). Triển khai sản xuất nên
thay bằng mô hình tinh chỉnh `vinai/sentiment-uit-vsfc` (plugin
doanh nghiệp).

### Nhận diện ngôn ngữ

```python
from nom.nlp import detect_language

d = detect_language("Đây là tiếng Việt.")
print(d.code, d.confidence)  # 'vi' 0.68
```

Heuristic theo tần suất Unicode, hỗ trợ vi/en/zh/ja/ko/und. Đủ để
chuyển hướng đầu vào nhiều ngôn ngữ; nếu cần độ chính xác cao
hơn, gắn FastText hoặc Lingua-py qua entry point.

## API HTTP

Các điểm cuối `/api/tools/nlp/*` đi kèm sẵn trong lệnh `nom serve`:

```bash
curl -X POST localhost:8080/api/tools/nlp/ner \
  -H 'content-type: application/json' \
  -d '{"text":"VCB ngày 02/05/2026"}'

curl -X POST localhost:8080/api/tools/nlp/sentiment \
  -d '{"text":"Sản phẩm tuyệt vời"}'

curl -X POST localhost:8080/api/tools/nlp/language \
  -d '{"text":"Đây là tiếng Việt"}'
```

## Tích hợp MCP và tác tử

Mọi nguyên thuỷ NLP cũng ra mắt như công cụ MCP qua `nom mcp-serve --include nlp`:

```json
// Cấu hình Claude Desktop:
{
  "mcpServers": {
    "nom-vn-nlp": {
      "command": "nom",
      "args": ["mcp-serve", "--include", "nlp"]
    }
  }
}
```

Hoặc gọi trực tiếp qua tác tử:

```python
from nom.agents.recipes import vn_doc_analyser

agent = vn_doc_analyser(llm=my_llm)
result = agent.run("Khách hàng VCB rất hài lòng với gói tín dụng…")
```

Bản trình diễn: `examples/nlp_demo.py`.

## Bẫy thường gặp

- **Điểm kiểm tra chỉ có pickle / `.bin`** — `HFNERModel` từ chối
  nạp. Muốn ép, đặt `allow_bin=True` và ghi rõ lý do trong tài liệu
  của lớp bao bọc.
- **HuggingFace Hub không truy cập được** — hàm `_safetensors_available()`
  rơi về phía an toàn (trả về `False`, từ chối nạp). Nhà vận hành
  có thể đặt `allow_bin=True` để buộc nạp.
- **Chuẩn hoá NFC** — đưa văn bản về NFC trước khi truyền vào công
  cụ; mô-đun `nom.text.normalize` xử lý việc này. `RegexNERModel`
  không tự chuẩn hoá.
- **Từ điển cảm xúc không phát hiện được mỉa mai / ngữ cảnh** —
  đây chỉ là kiểm tra sơ bộ; sản xuất nên thay bằng mô hình tinh
  chỉnh.
- **Văn bản ngắn (<3 chữ cái)** thì độ tin cậy nhận diện ngôn ngữ
  rất thấp; giao diện nên hiển thị độ tin cậy để người dùng biết.

## Đọc thêm

- `examples/nlp_demo.py` — bản trình diễn nhận diện ngôn ngữ, nhận
  diện thực thể, cảm xúc và tác tử kết hợp.
- [Trang tác tử](/tasks/agents) — cách dùng các nguyên thuỷ NLP
  bên trong tác tử.

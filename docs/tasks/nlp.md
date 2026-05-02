# NLP analysis: NER, sentiment, language detection

## TL;DR — gợi ý của chúng tôi

`nom.nlp` cung cấp 3 primitive cốt lõi cho phân tích văn bản tiếng
Việt: NER (`RegexNERModel` baseline + `HFNERModel` cho fine-tunes
mạnh hơn, refuse pickle-only checkpoints), sentiment
(`LexiconSentimentModel`), language detection (`detect_language`
heuristic Unicode-frequency). Tất cả import lazy — module
import sạch trên host không có torch. Production deployments thay
baseline bằng EE plugin (`nom_ee.nlp.*`) cho fine-tune VN có
benchmark đo trên register thực.

## Bức tranh công khai

| Model / Tool | License | Format | Số đo công bố | Kết luận |
|---|---|---|---:|---|
| Underthesea NER | GPL-3.0 | CRFsuite native | ~80 % F1 (VLSP 2018) | Bỏ qua — GPL không tương thích Apache redistribution |
| `vinai/PhoBERT-large` (fine-tune NER) | MIT | safetensors | ~91 % F1 (VLSP 2018) | Dùng — verify safetensors trước khi load |
| `xlm-roberta-large-finetuned-vi-ner` | MIT | safetensors | ~88 % F1 | Dùng |
| FPT.AI NER (commercial) | Closed | Closed | "95 %" (no protocol) | Bỏ qua — không reproducible |
| `vinai/sentiment-uit-vsfc` | MIT | safetensors | ~88 % accuracy (VSFC) | Dùng cho EE sentiment plugin |
| `wonrax/phobert-sentiment` | MIT | safetensors | TBD | Cần verify benchmark |
| FastText langdetect | MIT | binary | 99+ % @ 1k chars | Dùng nếu cần >5 ngôn ngữ |
| Lingua-py | Apache 2.0 | Pure-Python | 99+ % accuracy | Dùng cho EE multi-language plugin |

OSS baseline regex/lexicon **không** dán nhãn benchmark — chúng là
sanity-check tool, không phải production-grade. EE plugin với
fine-tune model là path cho production.

## Pipeline của chúng tôi

```
nom.nlp
├── ner.py          ── RegexNERModel (offline) + HFNERModel
│                     (safetensors-only, allow_bin=True opt-in)
├── sentiment.py    ── LexiconSentimentModel (VN positive/negative seed)
├── lang_detect.py  ── detect_language() Unicode-frequency
└── types.py        ── NLPError shared exception
```

### NER

```python
from nom.nlp import RegexNERModel, HFNERModel

# Baseline — chạy ngay không cần model
spans = RegexNERModel().tag("VCB ký hợp đồng 1.500.000 VND ngày 02/05/2026.")
# → [ORG VCB, MONEY 1.500.000 VND, DATE 02/05/2026]

# Production — phải có safetensors
model = HFNERModel(model_id="vinai/phobert-large-finetune-vi-ner")
spans = model.tag(text)  # lazy load lần đầu, cache sau đó
```

`RegexNERModel` bắt: MONEY (`1.500.000 VND`, `3 triệu`, `5 tỷ`),
DATE (ISO 8601 và DD/MM/YYYY), ORG abbrev (`VCB`, `BIDV`,
`Vietcombank`, `Viettel`, `VNPT`, `FPT`, `VinAI`, `Zalo`). Bỏ
PER/LOC — heuristic không tốt; dùng `nom_ee.privacy.VNAdvancedPIIDetector`
(EE) nếu cần PER hoặc một fine-tune HF safetensors qua `HFNERModel`.

### Sentiment

```python
from nom.nlp import LexiconSentimentModel, SentimentLabel

r = LexiconSentimentModel().predict("Sản phẩm tuyệt vời, rất hài lòng.")
print(r.label, r.score)  # SentimentLabel.POSITIVE 1.0
```

VN seed lexicon nhỏ (~30 từ mỗi cực). Production deployments swap
fine-tune vinai/sentiment-uit-vsfc (EE plugin).

### Language detection

```python
from nom.nlp import detect_language

d = detect_language("Đây là tiếng Việt.")
print(d.code, d.confidence)  # 'vi' 0.68
```

Heuristic Unicode-frequency, hỗ trợ vi/en/zh/ja/ko/und. Đủ để route
input đa ngôn ngữ; cần độ chính xác cao hơn → swap FastText hoặc
Lingua-py qua entry point.

## REST API

`/api/tools/nlp/*` ship sẵn trong `nom serve`:

```bash
curl -X POST localhost:8080/api/tools/nlp/ner \
  -H 'content-type: application/json' \
  -d '{"text":"VCB ngày 02/05/2026"}'

curl -X POST localhost:8080/api/tools/nlp/sentiment \
  -d '{"text":"Sản phẩm tuyệt vời"}'

curl -X POST localhost:8080/api/tools/nlp/language \
  -d '{"text":"Đây là tiếng Việt"}'
```

## MCP & agent integration

Mọi NLP primitive cũng ship như MCP tool qua `nom mcp-serve --include
nlp`:

```json
// Claude Desktop config:
{
  "mcpServers": {
    "nom-vn-nlp": {
      "command": "nom",
      "args": ["mcp-serve", "--include", "nlp"]
    }
  }
}
```

Hoặc dùng trực tiếp qua agent:

```python
from nom.agents.recipes import vn_doc_analyser

agent = vn_doc_analyser(llm=my_llm)
result = agent.run("Khách hàng VCB rất hài lòng với gói tín dụng…")
```

Demo: `examples/nlp_demo.py`.

## Bẫy thường gặp

- **Pickle / `.bin` only checkpoint** — `HFNERModel` refuse load.
  Override: `allow_bin=True` + ghi rõ lý do trong wrapper docstring.
- **Hugging Face Hub không reachable** — `_safetensors_available()`
  fail-closed (return False, refuse load). Operator có thể
  `allow_bin=True` để force load.
- **NFC normalization** — chuẩn hoá NFC trước khi pass vào tool;
  `nom.text.normalize` xử lý. `RegexNERModel` không tự normalize.
- **Sentiment lexicon không bắt được sarcasm / ngữ cảnh** — đây là
  sanity-check, swap fine-tune cho production.
- **Language detection trên text quá ngắn** (<3 letter) trả về
  confidence thấp; UI nên hiển thị confidence để user biết.

## Đo và benchmark

23 unit test + 7 REST API test. Benchmark VN production-grade là
TODO — sẽ thêm khi có VLSP NER corpus committed (cần verify
license trước).

## Đọc thêm

- `examples/nlp_demo.py` — demo language + NER + sentiment + agent
- `tests/test_nlp.py` — contract tests
- `docs/tasks/agents.md` — cách dùng các NLP primitive trong agent

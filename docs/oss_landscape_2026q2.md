# Bức tranh OSS Local-First AI / RAG — 2026 Q2

**Đối tượng:** team kiến trúc nom-vn. Tài liệu tham chiếu xem pattern nào nên mượn, pattern nào nên tránh, và chỗ nào chúng tôi đang cố ý đi khác.

**Phạm vi:** ~12 dự án dẫn đầu trải rộng các lớp framework RAG, ứng dụng chat local-first, model serving, hạ tầng vector, doc parsing, eval và observability — sample tháng 4/2026, không phải 2024.

**Tiêu chuẩn verify:** mọi claim đều có URL hoạt động. Số star, loại license và chi tiết kiến trúc được trích từ nguồn nếu có. Chỗ nào không verify công khai được, chúng tôi nói rõ.

---

## 1. Khảo sát từng dự án

Cho mỗi dự án: license, pattern đáng mượn, cạm bẫy nên tránh, URL.

### LlamaIndex (`run-llama/llama_index`)
- **License:** MIT. Repo: <https://github.com/run-llama/llama_index> ("42k+ stars" theo tutorial bên thứ ba; chưa verify riêng).
- **Mượn:** Đóng gói module-per-integration. Mỗi LLM/embedder/vectorstore là một package cài riêng (`llama-index-llms-ollama`, `llama-index-vector-stores-qdrant`); 300+ integration nằm ngoài core.
- **Tránh:** Singleton toàn cục `Settings` (và tiền nhiệm `ServiceContext`). Doc migration của chính họ thừa nhận "passing in an entire service_context container to any module made it hard to reason about which component was actually getting used." <https://docs.llamaindex.ai/en/stable/module_guides/supporting_modules/service_context_migration/> — bản thay thế Settings vẫn là toàn cục. Giữ DI qua constructor.

### LangChain + LangGraph
- **License:** MIT. Repo: <https://github.com/langchain-ai/langchain>, <https://github.com/langchain-ai/langgraph>.
- **Mượn:** Hình dạng interface `Runnable` — mọi element trong chain implement `invoke / stream / batch / ainvoke`. <https://www.pinecone.io/learn/series/langchain/langchain-expression-language/> Mượn hình dạng method thống nhất, không phải DSL pipe `|`.
- **Tránh:** Lớp abstraction xếp chồng. HN: "inherently flawed... 5 layers of abstraction to change a minute detail." <https://news.ycombinator.com/item?id=36648272> Bài học: đừng ship abstraction mà bạn không thể giữ ổn định 12+ tháng — sự thay đổi API v0.1 → v1 của LangGraph đang trên cùng track.

### Haystack v2
- **License:** Apache 2.0. Repo: <https://github.com/deepset-ai/haystack>
- **Mượn:** Component IO có type — "Every Component declares its input and output types." <https://github.com/deepset-ai/haystack/blob/main/haystack/core/pipeline/pipeline.py> Việc viết lại v1→v2 được drive bởi việc pipeline không có type trở nên không thể bảo trì. Giữ chặt input/output type của Protocol; không có hatch `dict[str, Any]`.
- **Tránh:** Runner `Pipeline` directed-multigraph với loop/branch. Hầu hết RAG flow là tuyến tính; runner đồ thị thêm phức tạp mà 90% user không cần (discussion #7623 của họ cho thấy user xây graph-of-graph). `nom.doc.Pipeline` của chúng tôi là một list — cố ý.

### DSPy
- **License:** MIT. Repo: <https://github.com/stanfordnlp/dspy> ("160k monthly downloads, 16k stars" theo <https://dspy.ai/roadmap/>).
- **Mượn:** Signature-as-contract — `signature = "question -> answer: str"` là spec I/O có type, không phải prompt template. <https://dspy.ai/learn/programming/signatures/> Khi `nom.llm` chính thức hoá extraction có type, đây là hình dạng sạch hơn.
- **Tránh:** Hướng tự sự "optimizer là mặc định". `BootstrapFewShot` / `MIPROv2` / `GEPA` mang lại win thật trên benchmark họ tune cho, nhưng nặng cho "trả lời một câu hỏi pháp lý VN". Ship không có optimizer; thêm chỉ khi có eval set hold-out (theo nguyên tắc verified-benchmarks).

### txtai
- **License:** Apache 2.0. Repo: <https://github.com/neuml/txtai> — peer gần nhất với lập trường của chúng tôi ("Local laptop: zero-config, runs on CPU"). Đáng đọc class `Embeddings` làm tham chiếu cho API vector index in-process.
- **Mượn:** Khung "Embedded by default" — giống sàn laptop-first của chúng tôi.
- **Tránh:** Class `Embeddings` của họ làm quá nhiều việc (index + storage + graph + agent trong một class). Cách tách của chúng tôi — Embedder / Retriever / Index / Store là Protocol riêng — sạch hơn.

### Onyx (trước là Danswer)
- **License:** MIT CE. Repo: <https://github.com/onyx-dot-app/onyx>, doc <https://docs.onyx.app/welcome>.
- **Mượn:** Pattern connector (40+ nguồn: Slack, Confluence, Jira, GitHub). Mỗi connector là "iterator yields document có metadata" — đường nối đúng nếu/khi nom-vn lớn hơn file local.
- **Tránh:** Stack ops đầy đủ — Postgres + Vespa + Redis + MinIO + worker queue + nginx. Đúng cho enterprise multi-tenant search, sai cho laptop. Giữ Tier 0 single-process; scale-out là Protocol impl bổ sung, không phải compose 6 service.

### RAGFlow
- **License:** Apache 2.0 (đã verify <https://github.com/infiniflow/ragflow/blob/main/LICENSE>).
- **Mượn:** Tách lớp: doc-parsing → retrieval → agent. Parsing nhận biết bảng của họ là điều `nom.doc` nên hướng tới cho PDF VN.
- **Tránh:** Triển khai "everything in one Docker compose" — minio + mysql + elasticsearch đều bắt buộc. Local-first nghĩa là không có external bắt buộc.

### Ollama
- **License:** MIT (đã verify <https://github.com/ollama/ollama/blob/main/LICENSE>).
- **Mượn:** Server Go single-binary wrap engine C++ (llama.cpp qua CGo), REST OpenAI-compatible, registry Modelfile. <https://medium.com/@laiso/ollama-under-the-hood-f8ed0f14d90c> Mức UX: "install, pull, serve — inference dưới hai phút." Tiêu chuẩn vàng cho "thứ khó, một lệnh."
- **Tránh:** Bind chặt vào một engine. Ollama về cốt lõi là wrapper llama.cpp; khi llama.cpp chậm, Ollama chậm. Giữ Ollama là một adapter, không phải sàn.

### llama.cpp / vLLM / LiteLLM
- **llama.cpp** (MIT, <https://github.com/ggml-org/llama.cpp>): GGUF là format "weights as data, mmap-able, deterministic" đúng — khớp chính sách no-pickle của chúng tôi. Đừng bind trực tiếp; nói chuyện qua Ollama hoặc adapter `llama-cpp-python`. ABI C++ hay đổi.
- **vLLM** (Apache 2.0, <https://github.com/vllm-project/vllm>, "~75K stars"): mượn PagedAttention *như khái niệm* — bố cục bộ nhớ chi phối chi phí inference. Tránh làm mặc định — kiến trúc V1 multi-process / ZeroMQ là cho serve Llama-405B, không phải một user Mac.
- **LiteLLM** (MIT, <https://github.com/BerriAI/litellm>): mượn wire format OpenAI-compatible làm lingua franca. <https://docs.litellm.ai/docs/simple_proxy> Ship `nom.llm.OpenAICompatible` một lần là adopt được catalogue LiteLLM miễn phí. Tránh dạng proxy-server — sản phẩm khác.

### Chroma / Qdrant / LanceDB / sqlite-vec
- **Chroma** (Apache 2.0, <https://github.com/chroma-core/chroma>): mặc định trong nhiều tutorial; rewrite Rust-core 2025 cho 4x writes theo benchmark bên thứ ba. Mặc định hợp lý cho `nom.index.ChromaIndex`.
- **Qdrant** (Apache 2.0, <https://github.com/qdrant/qdrant>): server Rust production-grade, "20–30 ms query times with ~95% recall." Adapter đúng cho tier multi-host.
- **LanceDB** (Apache 2.0, <https://github.com/lancedb/lancedb>): in-process, columnar (format Lance), zero-copy, friendly cho dữ liệu lớn hơn bộ nhớ. Phù hợp về triết lý nhất với nom-vn — không cần server, dạng file, query được. **Ứng viên mạnh để làm mặc định `nom.index` thay Chroma**, đáng có một ADR riêng.
- **sqlite-vec** (Apache 2.0, <https://github.com/asg017/sqlite-vec>): kế nhiệm sqlite-vss (đã chết — xem <https://github.com/asg017/sqlite-vss>). Mozilla tài trợ, "stable v1 in the next year, then maintenance mode." Nếu muốn vector search trong cùng file SQLite với `Store`, đây là đường.

**Pattern đáng mượn:** mọi cái trong số này chạy như thư viện in-process — không cần server. Đó là sàn đúng cho local-first.
**Cạm bẫy:** chọn một quá sớm. Protocol `Index` của chúng tôi để user chọn; chúng tôi ship một mặc định và document các lựa chọn khác.

### Doc parsing — Unstructured / Marker / Docling / PaddleOCR
- **Unstructured** (Apache 2.0 core, <https://github.com/Unstructured-IO/unstructured>): "ranks #1" trong benchmark bên thứ ba về chất lượng nhưng "51s for 1 page, 141s for 50 pages" — không dùng được cho ingestion ở quy mô.
- **Marker** (GPL-3.0 / commercial, <https://github.com/datalab-to/marker>): "500 PDFs in 2 hours, 1-2s per page." Batch nhanh. **License GPL — chúng tôi có thể nghiên cứu nhưng không copy code, và phải giữ là adapter user tự cài, không bundle.**
- **Docling** (MIT, IBM, <https://github.com/docling-project/docling>): "better for complex documents needing metadata... TableFormer model handled merged cells correctly." Đây là partner OSS đúng cho parsing tài liệu của nom-vn trên PDF kỹ thuật/pháp lý. Paper arXiv: <https://arxiv.org/pdf/2501.17887>.
- **PaddleOCR** (Apache 2.0, <https://github.com/PaddlePaddle/PaddleOCR>): đã có trong roadmap như một option OCR nặng.

**Pattern đáng mượn:** model tài liệu có type của Docling (Document → Section → Paragraph → Table với provenance) gần với cái `nom.doc.Document` nên là hơn cái chúng tôi có hôm nay.
**Cạm bẫy:** đuổi theo chất lượng parser mà bỏ qua tốc độ. Marker chứng minh có thể nhanh, GPL chứng minh license cắn — chọn adapter MIT/Apache làm mặc định.

### Eval — RAGAS / TruLens / DeepEval / Promptfoo
- **RAGAS** (Apache 2.0, <https://github.com/explodinggradients/ragas>): "five core metrics – Faithfulness, Contextual Relevancy, Answer Relevancy, Contextual Recall, Contextual Precision." Reference-free; LLM-as-judge.
- **TruLens** (MIT, <https://github.com/truera/trulens>): "highest discrimination ratio... 4.2:1 ratio" theo nghiên cứu AImultiple. <https://research.aimultiple.com/rag-evaluation-tools/>
- **DeepEval** (Apache 2.0, <https://github.com/confident-ai/deepeval>): pytest-native, 50+ metric, friendly với CI.
- **Promptfoo** (MIT, <https://github.com/promptfoo/promptfoo>): "51,000 developers" theo AImultiple, A/B testing YAML/CLI.

**Phát hiện trung thực** (đã trích): "all tools separate relevant from irrelevant contexts more than 91% of the time, but **none verify factual accuracy** — a passage with the right entities and wrong answer scores high across every tool tested." <https://research.aimultiple.com/rag-evaluation-tools/>
**Mượn:** tên metric của RAGAS làm contract (để user plug judge của riêng họ), tích hợp pytest của DeepEval làm developer ergonomics. **Đừng chọn một cái làm mặc định blessed của chúng tôi** — `benchmarks/rag/` của chúng tôi nên tự tính metric để chúng tôi sở hữu phép toán.
**Cạm bẫy:** tin LLM-as-judge dashboard làm ground truth. Luôn ghép với example human-labeled hold-out.

### Observability — OpenInference / OpenLLMetry / Phoenix
- **Phoenix** (Elastic v2, <https://github.com/Arize-ai/phoenix>): "fully open source and self-hostable — no feature gates." Build trên OpenTelemetry.
- **OpenInference** (Apache 2.0, <https://github.com/Arize-ai/openinference>): convention (semantic attribute) cho LLM span trên OTel.
- **OpenLLMetry** (Apache 2.0, <https://github.com/traceloop/openllmetry>): thư viện instrumentation cho OpenAI, Anthropic, Chroma, Pinecone, Qdrant, Weaviate.

**Mượn:** convention span OpenTelemetry + OpenInference. Đây là khoảnh khắc chuẩn hoá — mọi player nghiêm túc đều export OTel bây giờ. Thêm hỗ trợ env var `OTEL_*` vào `nom.chat` là một buổi chiều và miễn phí integration với Phoenix, Langfuse, Helicone, Datadog, ...
**Tránh:** Khoá vào SDK vendor (LangSmith — closed source — hoặc bất kỳ model "trace = us"). OpenTelemetry là đường moat-free.

### Local-first chat — AnythingLLM / Open WebUI / Khoj / Continue / Quivr / Verba
- **AnythingLLM** (MIT, <https://github.com/Mintplex-Labs/anything-llm>): all-in-one. Tránh cạm bẫy all-in-one — bề rộng tính năng kéo lùi roadmap vĩnh viễn.
- **Open WebUI** (permissive, <https://github.com/open-webui/open-webui>): pattern FastAPI + Svelte + plugin. Validate stack chúng tôi chọn.
- **Khoj** (AGPL-3.0, <https://github.com/khoj-ai/khoj>): chỉ nghiên cứu — AGPL không tương thích với redistribution Apache 2.0.
- **Continue** (Apache 2.0, <https://github.com/continuedev/continue>): mượn chia ba thành phần (`core` business logic / `extensions/<ide>` IDE shim / `gui` React) với protocol message-passing — cùng hình dạng với separation `nom.rag` ↔ `nom.chat.server` ↔ `ui/` của chúng tôi. Tránh `config.json`-as-API; một dataclass Config là đủ.
- **Quivr** (Apache 2.0, <https://github.com/QuivrHQ/quivr>): tránh khoá quan điểm — cách tiếp cận stack-or-fork của họ.
- **Verba** (BSD-3-Clause, <https://github.com/weaviate/Verba>): tránh tuyệt đối — `ReaderManager`, `ChunkerManager`, `EmbeddingManager`, `RetrieveManager`, `GenerationManager` chính xác là Manager Class Disease mà rule #2 trong `ARCHITECTURE.md` của chúng tôi cấm.

---

## 2. Mượn các pattern này

1. **Đóng gói module-per-integration** (LlamaIndex). Đã có một phần qua các extra `[index-chroma]`/`[index-qdrant]`/`[index-pgvector]`. Mở rộng cùng hình dạng nếu/khi LLM nở rộ (`nom-vn[llm-openai]`, `nom-vn[llm-anthropic]`).
2. **Component IO có type** (Haystack v2). Giữ Protocol `Stage`, `Embedder`, `LLM`, `Retriever` chặt — input/output type khai báo, không có hatch `dict[str, Any]`. Việc rewrite v1→v2 của họ chính xác là vì họ không làm thế.
3. **Signature-as-contract cho gọi LLM** (DSPy). Khi `nom.llm` lớn lên với extraction có type, khai báo `signature = "question, context -> answer: str, citations: list[int]"` thay vì xây thêm một DSL prompt-template nữa.
4. **Tương thích wire format OpenAI** (LiteLLM). Đảm bảo `nom.llm.LLM.complete()` chấp nhận hình dạng request OpenAI-compatible để toàn bộ catalogue của LiteLLM cách chúng tôi một adapter.
5. **Convention span OpenTelemetry + OpenInference** (Phoenix / OpenLLMetry). Một buổi chiều làm trong `nom.chat.server` mở cửa cho Phoenix, Langfuse, Datadog, Honeycomb.
6. **Pattern connector, khi cần** (Onyx). `Connector` là "iterator yields document có metadata" — Protocol nhỏ khi đến lúc; hôm nay không cần.
7. **UX single-binary** (Ollama). Dù chúng tôi là wheel Python, `pip install "nom-vn[chat]" && nom serve` nên cảm giác one-shot như `ollama pull && ollama serve`. Chúng tôi đang gần. Giữ mức đó.
8. **Kỷ luật "weights as data" kiểu GGUF** (llama.cpp). Đã encode trong chính sách no-pickle (không pickle). Giữ chặt.
9. **Connector / IO dạng iterator + provenance** (Docling). Một `Document` mang `provenance` (page, section, bbox) end-to-end để citation hoạt động. Chúng tôi đã làm citation; siết chặt data class.

---

## 3. Tránh các cạm bẫy này

1. **Lớp abstraction xếp chồng** (LangChain). HN id 36648272 ghi lại sự hối hận. Constructor args > Builder lồng nhau.
2. **Singleton Settings toàn cục** (LlamaIndex `Settings` / `ServiceContext` cũ). Doc migration của chính họ thừa nhận thiết kế đau đớn. Giữ DI rõ ràng qua constructor.
3. **Class Manager** (Verba: ReaderManager, ChunkerManager, EmbeddingManager, RetrieveManager, GenerationManager). Đã bị rule #2 trong `ARCHITECTURE.md` cấm — verify định kỳ rằng ta vẫn không có cái nào.
4. **Mega-class all-in-one** (`Embeddings` của txtai). Tách của chúng tôi (Embedder / Retriever / Index / Store) sạch hơn; đừng gộp dưới áp lực "đơn giản".
5. **Service ngoài bắt buộc cho tier local** (Onyx, RAGFlow). Postgres + ES + Redis + MinIO ổn cho tier production; không thể là mặc định laptop.
6. **Dep AGPL/GPL bundled** (Marker, PyMuPDF — đã document trong ARCHITECTURE.md, Khoj). Nghiên cứu, không copy. Chỉ adapter, opt-in.
7. **Optimizer / agent loop làm mặc định** (DSPy `BootstrapFewShot`, ReAct chung). Demoware trừ khi ghép với eval hold-out chứng minh win. Theo nguyên tắc verified-benchmarks, chỉ thêm khi số bench dịch chuyển.
8. **SDK observability khoá vendor** (LangSmith, Helicone proprietary mode). OpenTelemetry tồn tại; dùng nó.
9. **YAML/JSON-as-API** (`config.json` của Continue, định nghĩa flow của Flowise). Code là API. Một dataclass Config là đủ.
10. **ORM trong đường data core** — đã bị cấm rõ trong rule #6 của `ARCHITECTURE.md`. Giữ.
11. **Marketplace plugin / registry động** — không một lead nào trong số chúng tôi khảo sát làm thành công; chiến lược split-package của LangChain là gần nhất, và đó là *Python imports*, không phải marketplace. Đừng xây.

---

## 4. Chúng tôi đã ở đó (và chỗ chúng tôi cố ý đi khác)

| Lĩnh vực | Sự đồng thuận của ngành | nom-vn | Bảo vệ được? |
|---|---|---|---|
| Đường nối hình Protocol | Component Haystack, module DSPy, Runnable LangChain | Protocol `Embedder`, `LLM`, `Retriever`, `Stage`, `Store`, `EmbeddingsCache` | Có — type chặt, không `Any`. |
| Module-per-integration | 300+ package LlamaIndex | Extra-per-backend (`[index-chroma]`...) | Có — cùng hình, surface nhỏ hơn. |
| Observability OTel | Phoenix / OpenInference / OpenLLMetry | Chưa có — đề xuất là hành động ngắn hạn | Khoảng trống cần khép. |
| Vector mặc định embedded | Chroma, LanceDB, txtai | numpy `DenseRetriever` cho <100k; Chroma ở v0.1 | Có; revisit LanceDB. |
| UX single-binary | Ollama Go binary | Wheel Python + UI dist build sẵn bundled | Bảo vệ được — hệ sinh thái Python; UX tương đương. |
| Wire format OpenAI-compatible | LiteLLM | Một phần — chỉ adapter Ollama | Đáng siết trên Protocol LLM. |
| Model parsing tài liệu có type | Docling, Unstructured | `nom.doc.Stage` tồn tại; model `Document` có thể giàu hơn | Hợp hướng, sharpen. |
| Anti-Manager-class | Hầu hết org thất bại; chúng tôi cấm | Rule #2 trong `ARCHITECTURE.md` | Bảo vệ được — Verba là tale cảnh báo. |
| Không ORM | sqlite-vec direct, txtai direct, SqliteStore của chúng tôi | `sqlite3` direct | Bảo vệ được — phê bình của Eshwaran Venkat <https://eash98.medium.com/why-sqlalchemy-should-no-longer-be-your-orm-of-choice-for-python-projects-b823179fd2fb> ủng hộ ta. |
| Không framework DI | LlamaIndex hối hận ServiceContext, LangChain hối hận globals | Constructor args + dataclass Config | Bảo vệ được — mọi lead introduce một cái sau đó đều viết doc migration. |
| Không event bus | Ollama, llama.cpp, txtai không có | Ta không có | Bảo vệ được — call stack là event log. |
| Single repo (không phải monorepo of services) | LlamaIndex tách thành 300+ pkg nhưng core là monorepo | Single `nom-vn` | Bảo vệ được ở quy mô của ta; revisit nếu `nom.chat` quá nặng cho user `nom.text`. |
| Apache 2.0, không carve-out | Hầu hết lead; Dify và Verba bẻ | Pure Apache 2.0 | Bảo vệ được — chúng tôi cược vào open source bền vững. |

---

## 5. Hành động cụ thể cho nom-vn

Xếp theo impact / cost.

### Tier S — nhỏ, impact cao, làm sớm

1. **Thêm instrumentation OTel + OpenInference trong `nom.chat.server`.** Một buổi chiều. Mở cửa Phoenix, Langfuse, Datadog, Honeycomb miễn phí. Nguồn: <https://github.com/Arize-ai/openinference>, <https://github.com/traceloop/openllmetry>.
2. **Siết `LLM.complete` chấp nhận subset kwargs hình dạng OpenAI** (`messages`, `tools`, `response_format`, `stream`). Cho ta tự do wrap LiteLLM sau như một adapter. Cost: vài giờ; thay đổi additive backwards-compatible.
3. **Thêm class `Document` trong `nom.doc` với `provenance` rõ ràng** (file, page, bbox, đường dẫn section). Mirror Docling. Citation chính xác hơn; không cost cho caller hiện tại. <https://github.com/docling-project/docling>
4. **Audit class `…Manager` mới mọc.** Rule grep CI. Verba là tale cảnh báo.

### Tier M — lớn hơn, làm ở v0.1 hoặc v0.2

5. **Đánh giá LanceDB làm `nom.index` mặc định thay Chroma.** "format file in-process columnar zero-copy" của LanceDB gần với luận đề local-first của chúng tôi hơn "embedded server" của Chroma. Ship benchmark trong `benchmarks/index/` (recall + latency trên corpus VN) trước khi quyết định. <https://github.com/lancedb/lancedb>
6. **Adopt sqlite-vec cho tier SQLite của `nom.chat`** để vector sống cùng file với `Store`. Một file = một backup. Theo dõi v1 stable. <https://github.com/asg017/sqlite-vec>
7. **Ship `nom.eval` như module metric mỏng** (faithfulness, citation-precision, recall@k) — sở hữu phép toán, trích tên metric của RAGAS làm contract. **Không** dependency TruLens/DeepEval. Phát hiện của AImultiple "none verify factual accuracy" có nghĩa chúng tôi sẽ vẫn cần set human-labeled VN của riêng mình. <https://research.aimultiple.com/rag-evaluation-tools/>
8. **Signature kiểu DSPy cho `nom.doc.extract`** — đã có hình dạng đó (bạn truyền schema), chính thức hoá contract và document như vậy. Không optimizer; chúng tôi không cần.

### Tier L — ghi nhận, không phải bây giờ

9. **Protocol Connector** (set plugin 40-source kiểu Onyx). Ngoài phạm vi cho đến khi user thực sự có nguồn ngoài file.
10. **Optimizer / agent loop iterative-retrieval.** DSPy `BootstrapFewShot`, retry kiểu ReAct. Demoware trừ khi có eval set chứng minh win. Theo nguyên tắc verified-benchmarks, gate bằng số bench.
11. **Câu chuyện multi-tenant.** `ARCHITECTURE.md` đã liệt kê trong bảng scaling; đường nối Protocol đã đặt đúng. Không hành động code cho đến khi customer thứ hai hỏi.
12. **Adapter vLLM.** Đáp án đúng cho `nom.llm.VLLM` tương lai; mặc định sai. Protocol `LLM` nghĩa là additive khi đến lúc.

---

## 6. Tham khảo (chỉ URL đã verify)

- LlamaIndex: <https://github.com/run-llama/llama_index>, migration Settings <https://docs.llamaindex.ai/en/stable/module_guides/supporting_modules/service_context_migration/>
- LangChain & LangGraph: <https://github.com/langchain-ai/langchain>, <https://github.com/langchain-ai/langgraph>, doc LCEL <https://www.pinecone.io/learn/series/langchain/langchain-expression-language/>, phê bình HN <https://news.ycombinator.com/item?id=36648272>
- Haystack: <https://github.com/deepset-ai/haystack>, source pipeline <https://github.com/deepset-ai/haystack/blob/main/haystack/core/pipeline/pipeline.py>, thảo luận thiết kế v2 <https://github.com/deepset-ai/haystack/discussions/5568>
- DSPy: <https://github.com/stanfordnlp/dspy>, signature <https://dspy.ai/learn/programming/signatures/>, optimizer <https://dspy.ai/learn/optimization/optimizers/>
- txtai: <https://github.com/neuml/txtai>
- Onyx: <https://github.com/onyx-dot-app/onyx>, doc <https://docs.onyx.app/welcome>
- RAGFlow: <https://github.com/infiniflow/ragflow>, license <https://github.com/infiniflow/ragflow/blob/main/LICENSE>
- Ollama: <https://github.com/ollama/ollama>, license <https://github.com/ollama/ollama/blob/main/LICENSE>, internals <https://medium.com/@laiso/ollama-under-the-hood-f8ed0f14d90c>
- llama.cpp: <https://github.com/ggml-org/llama.cpp>
- vLLM: <https://github.com/vllm-project/vllm>
- LiteLLM: <https://github.com/BerriAI/litellm>, doc proxy <https://docs.litellm.ai/docs/simple_proxy>
- Chroma: <https://github.com/chroma-core/chroma>; Qdrant: <https://github.com/qdrant/qdrant>; LanceDB: <https://github.com/lancedb/lancedb>; sqlite-vec: <https://github.com/asg017/sqlite-vec>; sqlite-vss (deprecated): <https://github.com/asg017/sqlite-vss>
- Unstructured: <https://github.com/Unstructured-IO/unstructured>; Marker: <https://github.com/datalab-to/marker>; Docling: <https://github.com/docling-project/docling>, paper <https://arxiv.org/pdf/2501.17887>; PaddleOCR: <https://github.com/PaddlePaddle/PaddleOCR>
- Eval — RAGAS: <https://github.com/explodinggradients/ragas>; TruLens: <https://github.com/truera/trulens>; DeepEval: <https://github.com/confident-ai/deepeval>; Promptfoo: <https://github.com/promptfoo/promptfoo>; nghiên cứu AImultiple: <https://research.aimultiple.com/rag-evaluation-tools/>
- Observability — Phoenix: <https://github.com/Arize-ai/phoenix>; OpenInference: <https://github.com/Arize-ai/openinference>; OpenLLMetry: <https://github.com/traceloop/openllmetry>
- AnythingLLM: <https://github.com/Mintplex-Labs/anything-llm>; Open WebUI: <https://github.com/open-webui/open-webui>; Khoj (AGPL): <https://github.com/khoj-ai/khoj>
- Continue: <https://github.com/continuedev/continue>
- Quivr: <https://github.com/QuivrHQ/quivr>; Verba: <https://github.com/weaviate/Verba>

---

## 7. Cảnh báo về chất lượng dữ liệu

- **Số star** trích trong doc này từ blog bên thứ ba hoặc doc dự án; chúng tôi không tự resolve mọi badge GitHub stars. Chỗ không verify được, chúng tôi nói. Số star di chuyển; sự thật kiến trúc thì không.
- **Không có số benchmark bịa.** Mọi số chất lượng / latency trích đều từ nguồn công khai có URL trích. Nghiên cứu eval-tool của AImultiple (trích trên) là so sánh công khai nghiêm ngặt nhất chúng tôi tìm được.
- **Audit license** là best-effort từ file LICENSE đã trích. Trước khi vendor code, re-check ở commit bạn vendor từ.
- **Cố ý không đào sâu** (intentionally): Milvus, Weaviate-the-DB (vs Verba), Helicone, Langfuse, LangSmith, LM Studio (closed), Cortex/Jan, Flowise, PrivateGPT, h2oGPT — đều khảo sát qua, không cái nào đổi khuyến nghị của chúng tôi. Nếu ADR tương lai cần một cái, kéo lên sau.

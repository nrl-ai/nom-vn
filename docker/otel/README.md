# Local OpenTelemetry stack

A one-command Jaeger all-in-one for testing the OTel instrumentation in
`nom.chat.server` (see `src/nom/chat/observability.py`).

## Start the collector + UI

```bash
cd docker/otel
docker compose up -d
docker compose ps      # confirm jaeger is healthy
```

Endpoints exposed:
- **Jaeger UI** — http://localhost:16686
- **OTLP gRPC** — `localhost:4317`
- **OTLP HTTP** — `localhost:4318`

## Point Nôm at it

In a fresh terminal at the repo root:

```bash
pip install -e ".[chat,otel]"

export OTEL_SERVICE_NAME=nom-chat
export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318
export OTEL_TRACES_EXPORTER=otlp

nom serve --in-memory --port 8090
```

The CLI prints `· otel: jaeger @ http://localhost:4318` when the
instrumentation activates.

## Generate some traces

Either click around the UI at http://localhost:8090, or run the
included verifier (no extra deps):

```bash
python docker/otel/verify_traces.py
```

It creates a space, uploads a small VN document, indexes, asks a
question, then queries the Jaeger API to confirm spans landed.

## See the spans in Jaeger

Open http://localhost:16686 → "Service" dropdown → `nom-chat` → **Find
Traces**. You'll see one trace per HTTP request, with durations and
the standard FastAPI span tree (route + middleware + handler).

When OpenInference attributes land in v0.3 we'll also tag the `ask`
span with `openinference.span.kind=RETRIEVER`, `input.value=<question>`,
`output.value=<answer>`, `retrieval.documents.count=N` — making the
trace readable in Phoenix / Langfuse without per-tool config.

## Tear down

```bash
docker compose down -v
```

The `-v` removes the in-memory storage volume too — fresh slate next
time.

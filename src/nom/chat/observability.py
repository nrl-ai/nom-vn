"""OpenTelemetry instrumentation for ``nom.chat.server``.

When ``OTEL_EXPORTER_OTLP_ENDPOINT`` (or ``OTEL_SERVICE_NAME``) is set,
:func:`maybe_install_otel` wires:

- FastAPI HTTP request spans (status, route, latency).
- A custom ``ask`` span around the RAG call, tagged with OpenInference
  semantic conventions (`openinference.span.kind`, `input.value`,
  `output.value`, `retrieval.documents`) so traces show up cleanly in
  Phoenix / Langfuse / Datadog without per-tool config.

If OTel deps aren't installed the function is a no-op — instrumentation
is opt-in via the ``[otel]`` extra. This keeps the default
``pip install nom-vn[chat]`` install footprint small.

The OTel SDK reads its config from standard env vars:

  OTEL_SERVICE_NAME=nom-chat
  OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318
  OTEL_TRACES_EXPORTER=otlp

— meaning users can drop in any OTel-compatible backend without
re-deploying. We don't ship any vendor SDK directly. See the
recommendation in ``docs/oss_landscape_2026q2.md`` for why this matters
(every serious LLM observability tool now consumes OTel + the
OpenInference semantic conventions).
"""

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from fastapi import FastAPI

__all__ = ["maybe_install_otel"]

_log = logging.getLogger(__name__)


def _otel_enabled() -> bool:
    """Honor user intent: only auto-install when an OTel env var is set.

    The OTel SDK falls back to a no-op exporter if neither
    ``OTEL_EXPORTER_OTLP_ENDPOINT`` nor ``OTEL_SERVICE_NAME`` is set,
    so probing for those is the standard pattern for "user actually
    wants traces."
    """
    return any(
        os.environ.get(k)
        for k in ("OTEL_EXPORTER_OTLP_ENDPOINT", "OTEL_SERVICE_NAME", "OTEL_TRACES_EXPORTER")
    )


def maybe_install_otel(app: FastAPI) -> bool:
    """Install OpenTelemetry on a FastAPI app, no-op when disabled.

    Returns ``True`` if instrumentation was installed, ``False``
    otherwise (no env vars, or ``[otel]`` extra not installed).

    Sets up a TracerProvider + OTLP exporter explicitly — the SDK
    doesn't auto-init from env vars unless you run via the
    ``opentelemetry-instrument`` CLI, and we want a one-import path.
    """
    if not _otel_enabled():
        return False
    try:
        from opentelemetry import trace
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
    except ImportError:
        print(
            "[otel] OTEL_* env var set but [otel] extra not installed. "
            "Install with: pip install nom-vn[otel]"
        )
        return False

    # Wire the SDK only once — instrument_app + a global TracerProvider
    # are process-global. Repeated calls would stack span processors.
    if isinstance(trace.get_tracer_provider(), TracerProvider):
        FastAPIInstrumentor.instrument_app(app)
        return True

    # Pick exporter: HTTP for endpoints ending in 4318 / containing /v1/,
    # gRPC otherwise (4317 default). Lets users toggle by changing the
    # endpoint without re-installing deps.
    endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "")
    use_http = endpoint.endswith("4318") or "/v1/" in endpoint
    if use_http:
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
            OTLPSpanExporter as _HTTPExporter,
        )

        exporter: Any = _HTTPExporter()
    else:
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
            OTLPSpanExporter as _GRPCExporter,
        )

        exporter = _GRPCExporter(insecure=True)

    service_name = os.environ.get("OTEL_SERVICE_NAME", "nom-chat")
    resource = Resource.create(
        {
            "service.name": service_name,
            "service.version": _nom_version(),
        }
    )
    provider = TracerProvider(resource=resource)
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    FastAPIInstrumentor.instrument_app(app)

    # Flush spans on shutdown so short-lived test runs don't lose traces.
    import atexit

    atexit.register(provider.shutdown)

    print(
        f"[otel] traces → {endpoint or '<default>'}  "
        f"(service={service_name}, exporter={'http' if use_http else 'grpc'})"
    )
    return True


def _nom_version() -> str:
    try:
        from nom import __version__

        return str(__version__)
    except Exception:
        return "0"


def get_tracer() -> Any:
    """Return the OTel tracer for ``nom.chat``, or a no-op if disabled.

    Modules that want to record custom spans (e.g. a custom ``ask``
    span around the RAG call) call this and use it like::

        tracer = get_tracer()
        with tracer.start_as_current_span("ask") as span:
            span.set_attribute("openinference.span.kind", "RETRIEVER")
            ...

    When OTel isn't installed the returned tracer is the standard SDK
    no-op, so call sites don't need to branch.
    """
    try:
        from opentelemetry import trace
    except ImportError:
        from contextlib import nullcontext

        class _NoopTracer:
            def start_as_current_span(self, _name: str, **_kw: Any) -> Any:
                return nullcontext(_NoopSpan())

        class _NoopSpan:
            def set_attribute(self, _k: str, _v: Any) -> None: ...
            def set_status(self, *_a: Any, **_kw: Any) -> None: ...
            def record_exception(self, *_a: Any, **_kw: Any) -> None: ...

        return _NoopTracer()
    return trace.get_tracer("nom.chat")


def annotate_ask_span(
    span: Any,
    *,
    space_id: str,
    question: str,
    answer_text: str | None = None,
    n_retrieved: int = 0,
    n_citations: int = 0,
    error: str | None = None,
) -> None:
    """Tag a span with OpenInference RAG attributes.

    See https://github.com/Arize-ai/openinference/blob/main/spec/semantic_conventions.md
    for the canonical attribute names. Using these keys (vs. ad-hoc names)
    means Phoenix / Langfuse / Arize parse our traces without manual
    field mapping.
    """
    try:
        span.set_attribute("openinference.span.kind", "RETRIEVER")
        span.set_attribute("nom.space.id", space_id)
        span.set_attribute("input.value", question)
        span.set_attribute("input.mime_type", "text/plain")
        if answer_text is not None:
            span.set_attribute("output.value", answer_text)
            span.set_attribute("output.mime_type", "text/plain")
        span.set_attribute("retrieval.documents.count", int(n_retrieved))
        span.set_attribute("retrieval.citations.count", int(n_citations))
        if error:
            span.set_attribute("error.message", error)
    except Exception:  # pragma: no cover - tracer always cooperates
        # Defensive — never let observability break the request path.
        pass

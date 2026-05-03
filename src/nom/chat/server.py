"""FastAPI app for the Nôm chat web service.

Routes (see OpenAPI at ``/docs`` once running):

- ``GET  /``                              — minimal HTML UI
- ``GET  /api/spaces``                    — list spaces
- ``POST /api/spaces``                    — create space
- ``GET  /api/spaces/{id}``               — space + materials
- ``DELETE /api/spaces/{id}``             — delete space
- ``POST /api/spaces/{id}/materials``     — upload a material (multipart)
- ``GET  /api/spaces/{id}/materials``     — list materials
- ``POST /api/spaces/{id}/ask``           — ask a question, returns Answer

The minimal HTML UI ships in this file as a string constant — vanilla
fetch + handful of CSS rules. The proper React + ShadCN UI lands in
v0.2.1; this app layout is designed so swapping the ``GET /`` route
to a ``StaticFiles`` mount over the built ``dist/`` is one line.
"""

from pathlib import Path
from typing import TYPE_CHECKING, Any

# NOTE: deliberately NO `from __future__ import annotations` — FastAPI
# resolves request-handler type hints at runtime to wire up dependency
# injection (UploadFile, Form, etc.). Stringized annotations break that.
if TYPE_CHECKING:
    from nom.chat.store import Store
    from nom.embeddings import Embedder
    from nom.llm import LLM


__all__ = ["build_app"]


def build_app(
    *,
    llm: "LLM | None" = None,
    embedder: "Embedder | None" = None,
    store: "Store | None" = None,
) -> Any:
    """Construct the FastAPI app.

    Args:
        llm: any LLM adapter; defaults to ``nom.llm.Ollama(model="qwen3:8b")``.
            Required by the Store.
        embedder: optional ``Embedder``; defaults to ``VietnameseEmbedder``
            (lazy-loaded inside the Store).
        store: optional pre-built ``Store``. When provided, ``llm`` and
            ``embedder`` are ignored. Useful for tests.

    Returns:
        A FastAPI application instance.
    """
    try:
        from fastapi import FastAPI, File, Form, HTTPException, UploadFile
        from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
        from fastapi.staticfiles import StaticFiles
    except ImportError as exc:
        raise ImportError(
            "nom.chat requires fastapi. Install with: pip install nom-vn[chat]"
        ) from exc

    if store is None:
        if llm is None:
            from nom.llm import Ollama

            llm = Ollama()
        from nom.chat.store import MemoryStore

        store = MemoryStore(embedder=embedder, llm=llm)

    app = FastAPI(
        title="Nôm",
        version="0.2.2",
        description="Vietnamese document Q&A — local-first, open-source.",
    )

    # Authentication: routed through the ``nom.platform.Authenticator``
    # Protocol. The env-var paths kept for backward compatibility:
    #
    #   NOM_AUTH_TOKEN=<token>       → built-in BearerTokenAuth
    #   NOM_AUTH_PLUGIN=<name>       → load via entry-point group
    #                                  ``nom.platform.authenticators``
    #                                  (used by EE OIDC/SAML/LDAP)
    #
    # When neither is set the API is open (preserves the local-first
    # behaviour `nom serve` had since v0.1).
    _authenticator = _resolve_authenticator()
    if _authenticator is not None:
        from nom.chat.auth_middleware import install_auth_middleware

        install_auth_middleware(app, authenticator=_authenticator)

    # OpenTelemetry — opt-in via env vars. No-op when OTEL_* unset or
    # the [otel] extra isn't installed. Wires FastAPI HTTP spans;
    # custom RAG spans are added at the route level if useful later.
    from nom.chat.observability import maybe_install_otel

    maybe_install_otel(app)

    # Stateless playground tools (/api/tools/*) — independent of the
    # spaces / materials store. Reuses the chat LLM for the optional
    # llm-backed diacritic restorer.
    from nom.chat.tools_api import register_tool_routes

    register_tool_routes(app, llm=getattr(store, "_llm", None))

    # /api/agents/* — optional. Registers built-in demo agents only when
    # ``NOM_DEMO_AGENTS=1`` is set, so production deployments stay
    # silent until the operator wires their own agent registry. The
    # routes mount unconditionally so the UI's "(no agents)" state
    # works even on a fresh install.
    _register_agent_routes(app, store=store)

    # /api/compliance/* — risk classification API for the compliance
    # console UI. Always mounted; pure-Python, no extras required.
    _register_compliance_routes(app)

    # /api/models/* — Ollama tag listing + HF cache scan + async pulls
    # with progress tracking. Powers the desktop Models tab.
    from nom.chat.models_api import register_models_routes

    register_models_routes(app)

    # /api/jobs/* — long-running translate / convert as background jobs
    # with progress reporting. UI uses this to show a queue + % bar
    # instead of holding an HTTP connection open for minutes.
    from nom.chat.jobs_api import register_jobs_routes

    register_jobs_routes(app, llm=getattr(store, "_llm", None))

    # /api/admin/* — opt-in EE feature, auto-mounted when
    # ``nom-vn-enterprise`` is installed in the same environment.
    # Silently skipped otherwise so the OSS server still works.
    _register_admin_routes_if_available(app)

    # ------------------------------------------------------------------
    # Static UI
    # ------------------------------------------------------------------
    # Two paths:
    # 1. The React+ShadCN app built by `pnpm build` lands at ui/dist/.
    #    When that exists we mount it as the root and serve index.html
    #    for any non-API path (SPA fallback).
    # 2. If dist doesn't exist (dev install of the Python package
    #    without building the UI, or chat-only install), fall back to
    #    the embedded HTML so the server still has *something* to show.

    _ui_dist = _find_ui_dist()

    if _ui_dist is not None:
        _assets = _ui_dist / "assets"
        if _assets.is_dir():
            app.mount(
                "/assets",
                StaticFiles(directory=str(_assets)),
                name="assets",
            )

        # Per-file routes for top-level static files (favicon etc.)
        for static_file in _ui_dist.iterdir():
            if static_file.is_file() and static_file.name not in {"index.html"}:
                _register_static_file(app, static_file)

        @app.get("/", response_class=HTMLResponse)
        def index_dist() -> Any:
            return FileResponse(_ui_dist / "index.html")
    else:

        @app.get("/", response_class=HTMLResponse)
        def index_fallback() -> str:
            return _FALLBACK_UI

    # ------------------------------------------------------------------
    # Health / version probe — also feeds the UI header
    # ------------------------------------------------------------------

    @app.get("/api/llm/backends")
    def llm_backends() -> dict[str, Any]:
        """Probe which LLM backends are importable in this server process.

        Used by the Settings UI to render an availability matrix and to
        generate the right launch command for the user's environment.
        Probing is import-time only — it does NOT contact any service or
        download a model.
        """
        import importlib.util as _imp

        def _has(mod: str) -> bool:
            return _imp.find_spec(mod) is not None

        return {
            "active": {
                "name": _safe_attr(getattr(store, "_llm", None), "name"),
                "class": type(getattr(store, "_llm", None)).__name__
                if getattr(store, "_llm", None) is not None
                else None,
                "model": _safe_attr(getattr(store, "_llm", None), "model")
                or _safe_attr(getattr(store, "_llm", None), "model_id"),
            },
            "available": [
                {
                    "id": "ollama",
                    "label": "Ollama (local daemon)",
                    "kind": "local-http",
                    "available": True,  # adapter has no hard import dep beyond httpx
                    "model_hint": "qwen3:8b · or hf.co/<repo>:<tag> for HF GGUFs",
                    "needs": [],
                },
                {
                    "id": "llamacpp",
                    "label": "llama.cpp via llama-server (HTTP)",
                    "kind": "local-http",
                    "available": True,
                    "model_hint": "label only — GGUF chosen by llama-server -m",
                    "needs": ["llama-server running externally"],
                },
                {
                    "id": "llamacpp-python",
                    "label": "llama.cpp via llama-cpp-python (in-process)",
                    "kind": "local-inproc",
                    "available": _has("llama_cpp"),
                    "model_hint": "GGUF path · or hf:<repo>:<filename>",
                    "needs": ['pip install "nom-vn[llamacpp-python]"'],
                },
                {
                    "id": "huggingface",
                    "label": "HuggingFace transformers (in-process)",
                    "kind": "local-inproc",
                    "available": _has("torch") and _has("transformers"),
                    "model_hint": "<owner>/<repo> on HF Hub",
                    "needs": ['pip install "nom-vn[llm-hf]"'],
                },
                {
                    "id": "openai",
                    "label": "OpenAI (or any compatible HTTP)",
                    "kind": "cloud",
                    "available": True,
                    "model_hint": "gpt-4o-mini · OPENAI_API_KEY required",
                    "needs": ["OPENAI_API_KEY"],
                },
                {
                    "id": "anthropic",
                    "label": "Anthropic Claude",
                    "kind": "cloud",
                    "available": True,
                    "model_hint": "claude-haiku-4-5-20251001",
                    "needs": ["ANTHROPIC_API_KEY"],
                },
            ],
        }

    @app.get("/api/health")
    def health() -> dict[str, Any]:
        """Lightweight version + capabilities probe.

        Used by the React header to surface the active model name, by
        monitoring tools (k8s liveness / OTel collector), and by the
        seed script to detect whether the server is up before posting.
        Never raises — best-effort introspection only.
        """
        import shutil

        from nom import __version__ as nom_version

        return {
            "status": "ok",
            "version": nom_version,
            "store": type(store).__name__,
            "llm": _safe_attr(getattr(store, "_llm", None), "name"),
            "llm_class": type(getattr(store, "_llm", None)).__name__
            if getattr(store, "_llm", None) is not None
            else None,
            "embedder": _safe_attr(getattr(store, "_embedder", None), "name")
            or "VietnameseEmbedder (lazy)",
            "ocr_available": shutil.which("tesseract") is not None,
            "auth_required": _authenticator is not None,
        }

    # ------------------------------------------------------------------
    # Spaces
    # ------------------------------------------------------------------

    @app.get("/api/spaces")
    def list_spaces() -> list[dict[str, Any]]:
        return [_space_to_dict(s) for s in store.list_spaces()]

    @app.post("/api/spaces", status_code=201)
    def create_space(payload: dict[str, str]) -> dict[str, Any]:
        name = payload.get("name", "")
        if not name.strip():
            raise HTTPException(status_code=400, detail="`name` is required")
        try:
            space = store.create_space(name)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return _space_to_dict(space)

    @app.get("/api/spaces/{space_id}")
    def get_space(space_id: str) -> dict[str, Any]:
        space = store.get_space(space_id)
        if space is None:
            raise HTTPException(status_code=404, detail="space not found")
        return _space_to_dict(space)

    @app.delete("/api/spaces/{space_id}", status_code=204)
    def delete_space(space_id: str) -> None:
        if not store.delete_space(space_id):
            raise HTTPException(status_code=404, detail="space not found")

    # ------------------------------------------------------------------
    # Materials
    # ------------------------------------------------------------------

    @app.post("/api/spaces/{space_id}/materials", status_code=201)
    async def upload_material(
        space_id: str,
        file: UploadFile = File(...),
        name: str | None = Form(default=None),
    ) -> dict[str, Any]:
        try:
            content = await file.read()
            mat = store.add_material(
                space_id,
                name or file.filename or "upload",
                content,
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return _material_to_dict(mat)

    @app.get("/api/spaces/{space_id}/materials")
    def list_materials(space_id: str) -> list[dict[str, Any]]:
        space = store.get_space(space_id)
        if space is None:
            raise HTTPException(status_code=404, detail="space not found")
        return [_material_to_dict(m) for m in space.materials]

    @app.get("/api/spaces/{space_id}/materials/{material_id}/raw")
    def material_raw(space_id: str, material_id: str) -> Any:
        """Stream the original uploaded bytes back, content-type sniffed."""
        from fastapi.responses import Response

        result = store.get_material_content(space_id, material_id)
        if result is None:
            raise HTTPException(status_code=404, detail="material not found")
        name, blob = result
        mime = _mime_for(name)
        # `inline` so PDFs / images render in-browser; filename preserved
        # for the case where the user clicks the link to download.
        return Response(
            content=blob,
            media_type=mime,
            headers={"Content-Disposition": f'inline; filename="{name}"'},
        )

    @app.get("/api/spaces/{space_id}/materials/{material_id}/text")
    def material_text(space_id: str, material_id: str) -> dict[str, Any]:
        """Return both the structural Parse output and the indexed chunks.

        - ``pages``: original Parse output — DOCX paragraphs, XLSX sheets,
          PPTX slides, PDF pages. Used by the **Original** tab to render
          structured previews of formats the browser can't natively show.
        - ``chunks``: persisted post-chunker units (what the embedder
          saw). Used by the **Extracted** tab. Empty if not yet indexed.
        """
        pages_result = store.get_material_pages(space_id, material_id)
        if pages_result is None:
            raise HTTPException(status_code=404, detail="material not found")
        name, pages = pages_result
        chunks_result = store.get_material_chunks(space_id, material_id)
        chunks = chunks_result[1] if chunks_result else []
        text = "\n\n".join(pages)
        return {
            "name": name,
            "text": text,
            "pages": pages,
            "chunks": chunks,
            "n_pages": len(pages),
            "n_chunks": len(chunks),
            "n_chars": len(text),
        }

    @app.post("/api/spaces/{space_id}/index")
    def index_space(space_id: str) -> dict[str, Any]:
        """Eagerly process all pending materials in a space.

        Synchronous — UI should keep a loading indicator visible until
        this returns. No LLM call (just parse + chunk + embed).

        Returns ``{"n_indexed": int, "n_total": int}``.
        """
        try:
            n_indexed = store.index_pending(space_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        space = store.get_space(space_id)
        return {
            "n_indexed": n_indexed,
            "n_total": len(space.materials) if space else 0,
        }

    # ------------------------------------------------------------------
    # Ask
    # ------------------------------------------------------------------

    @app.post("/api/spaces/{space_id}/ask")
    def ask(space_id: str, payload: dict[str, Any]) -> JSONResponse:
        question = payload.get("question", "")
        top_k = int(payload.get("top_k", 5))
        if not question.strip():
            raise HTTPException(status_code=400, detail="`question` is required")
        try:
            answer = store.ask(space_id, question, top_k=top_k)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except Exception as exc:
            # Catch httpx.HTTPStatusError (Ollama 404 / connection refused etc.)
            # and any other LLM transport failure. We don't import httpx at
            # the top of the file so the chat module stays cheap; recognise
            # the error by class name OR by message content (the LlamaCpp
            # adapter wraps ConnectError into a RuntimeError with a
            # "Could not reach llama-server" hint — same idea applies).
            cls = type(exc).__name__
            msg_l = str(exc).lower()
            transport = (
                "HTTPStatusError" in cls
                or "ConnectError" in cls
                or "Timeout" in cls
                or "could not reach" in msg_l
                or "llama-server" in msg_l
                or "ollama" in msg_l
                or "11434" in str(exc)
            )
            if transport:
                raise _llm_error_to_503(exc) from exc
            raise

        return JSONResponse(
            {
                "text": answer.text,
                "citations": [
                    {
                        "doc_idx": c.doc_idx,
                        "chunk_idx": c.chunk_idx,
                        "score": c.score,
                        "text": c.text,
                    }
                    for c in answer.citations
                ],
                "n_retrieved": answer.n_retrieved,
            }
        )

    if _ui_dist is not None:
        # SPA catch-all — registered LAST so every concrete /api/* and
        # /assets/* route wins by FastAPI's first-match-wins routing.
        # Any other path serves index.html so the client router (App.tsx)
        # handles deep links like /dich-thuat, /chuyen-doi, /mo-hinh.
        from fastapi.responses import FileResponse as _FileResponse
        from fastapi.responses import HTMLResponse as _HTMLResponse

        @app.get("/{path:path}", response_class=_HTMLResponse, include_in_schema=False)
        def spa_fallback(path: str) -> Any:
            # Unknown /api/* paths must stay 404, not silently serve the
            # SPA shell — otherwise client fetch() bugs would render as
            # parse errors instead of HTTP failures.
            if path.startswith("api/"):
                raise HTTPException(status_code=404, detail=f"not found: /{path}")
            return _FileResponse(_ui_dist / "index.html")

    return app


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _resolve_authenticator() -> Any:
    """Pick the active ``Authenticator`` from environment.

    Priority: an explicit plugin name beats the bearer-token shortcut.
    Returns ``None`` when the operator hasn't asked for any auth — in
    that case ``build_app`` skips middleware entirely (open API,
    matches single-user local-first deployments).
    """
    import os

    plugin_name = os.environ.get("NOM_AUTH_PLUGIN") or None
    if plugin_name:
        from nom.platform import load_plugin

        cls = load_plugin("auth", plugin_name)
        # The plugin is responsible for reading its own config from
        # env vars or a config file; we just instantiate.
        return cls()

    token = os.environ.get("NOM_AUTH_TOKEN") or None
    if token:
        from nom.platform import BearerTokenAuth

        # Optional role override for quick demos / single-tenant ops
        # who want the bearer user to also hold tenant.admin /
        # compliance.officer (gates the EE admin + audit endpoints).
        roles_env = os.environ.get("NOM_AUTH_ROLES", "").strip()
        roles: tuple[str, ...] = (
            tuple(r.strip() for r in roles_env.split(",") if r.strip())
            if roles_env
            else ("workspace.editor",)
        )
        return BearerTokenAuth(
            token=token,
            user_id=os.environ.get("NOM_AUTH_USER_ID", "anonymous"),
            tenant_id=os.environ.get("NOM_AUTH_TENANT_ID", "default"),
            roles=roles,
        )

    return None


def _register_agent_routes(app: Any, *, store: Any) -> None:
    """Mount /api/agents/* with an optional demo registry.

    Registry sources, in priority order:

    1. ``NOM_DEMO_AGENTS=1`` — register the built-in `vn_doc_analyser`
       recipe wired to the chat LLM. Useful for quick-start demos.
    2. Empty registry otherwise — the routes still mount so the UI's
       "(no agents)" state works.

    Production deployments build their own registry and call
    ``register_agent_routes(app, agents=…)`` directly from a wrapper
    around ``build_app``.
    """
    import os

    from nom.agents_api import register_agent_routes

    agents: dict[str, Any] = {}
    if os.environ.get("NOM_DEMO_AGENTS") == "1":
        try:
            from nom.agents.recipes import vn_doc_analyser

            llm = getattr(store, "_llm", None)
            if llm is not None:
                agents["vn_doc_analyser"] = vn_doc_analyser(llm=llm)
        except Exception:
            pass

    register_agent_routes(app, agents=agents)


def _register_admin_routes_if_available(app: Any) -> None:
    """Mount /api/admin/* iff the nom-vn-enterprise package is
    installed AND a valid licence is reachable. Silently no-ops
    otherwise — OSS deployments don't get admin endpoints.
    """
    try:
        from nom_ee.admin import (  # type: ignore[import-untyped, unused-ignore]
            register_admin_routes,
        )
    except ImportError:
        return  # nom-vn-enterprise not installed; skip.
    try:
        register_admin_routes(app)
    except Exception:
        return


def _register_compliance_routes(app: Any) -> None:
    """Mount POST /api/compliance/classify — feed a SystemSpec, get a
    RiskTier + applicable articles + reasoning back. Drives the
    compliance console UI.
    """
    from fastapi import HTTPException

    from nom.compliance.risk import RiskClassifier, SystemSpec

    @app.post("/api/compliance/classify")  # type: ignore[misc, untyped-decorator, unused-ignore]
    def classify(payload: dict[str, Any]) -> dict[str, Any]:
        try:
            spec = SystemSpec(
                purpose=str(payload.get("purpose", "")).strip(),
                sector=str(payload.get("sector", "other")),  # type: ignore[arg-type]
                automation_level=str(payload.get("automation_level", "advisory")),  # type: ignore[arg-type]
                user_scope=str(payload.get("user_scope", "individual")),  # type: ignore[arg-type]
                handles_personal_data=bool(payload.get("handles_personal_data", False)),
                affects_vulnerable_groups=bool(payload.get("affects_vulnerable_groups", False)),
                can_generate_synthetic_content=bool(
                    payload.get("can_generate_synthetic_content", False)
                ),
                interacts_directly_with_users=bool(
                    payload.get("interacts_directly_with_users", True)
                ),
            )
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=422, detail=f"invalid spec: {exc}") from exc

        if not spec.purpose:
            raise HTTPException(status_code=422, detail="`purpose` is required")

        result = RiskClassifier().classify(spec)
        return {
            "tier": result.tier.value,
            "applicable_articles": list(result.applicable_articles),
            "reasoning": list(result.reasoning),
            "fired_rule_ids": list(result.fired_rule_ids),
            "law_id": result.law_id,
            "law_version": result.law_version,
        }


def _space_to_dict(space: Any) -> dict[str, Any]:
    return {
        "id": space.id,
        "name": space.name,
        "created_at": space.created_at,
        "n_materials": len(space.materials),
    }


def _llm_error_to_503(exc: BaseException) -> Any:
    """Translate an LLM transport error into a clean 503 with a hint.

    The Ollama / OpenAI / Anthropic adapters all raise ``httpx.HTTPStatusError``
    when the upstream returns a non-2xx. The most common case in
    development is a 404 because the chosen model isn't pulled. Surfacing
    that as a 500 leaks an httpx stack trace; surfacing it as a generic
    "LLM call failed" loses the actionable hint. This helper rewrites
    common-cause errors into a 503 with a concrete remediation step.

    Returns an HTTPException ready to ``raise``.
    """
    from fastapi import HTTPException

    msg = str(exc)
    msg_l = msg.lower()
    looks_like_ollama = "ollama" in msg_l or "11434" in msg
    detail: str
    if "404" in msg and looks_like_ollama:
        detail = (
            "LLM model not available on the local Ollama server. "
            "Pull it first: `ollama pull qwen3:8b` "
            "(or set NOM_LLM_MODEL to a model you've already pulled)."
        )
    elif ("ConnectError" in type(exc).__name__) or ("connection" in msg_l and looks_like_ollama):
        detail = (
            "Could not reach the local Ollama server. "
            "Start it with `ollama serve` in another terminal."
        )
    elif "404" in msg or "not found" in msg_l:
        detail = f"LLM endpoint returned 404 — model not available. Detail: {msg}"
    elif "ConnectError" in type(exc).__name__:
        detail = "Could not reach the LLM service."
    else:
        detail = f"LLM call failed: {msg}"
    return HTTPException(status_code=503, detail=detail)


def _safe_attr(obj: Any, attr: str) -> Any:
    """Best-effort attribute access for /api/health introspection.

    Some attributes (like `Embedder.name` for the lazy `VietnameseEmbedder`)
    are properties that may trigger work. We don't want a probe call to
    download a model, so wrap the access defensively.
    """
    if obj is None:
        return None
    try:
        return getattr(obj, attr)
    except Exception:
        return None


def _find_ui_dist() -> Path | None:
    """Locate the built React UI bundle, if present.

    Search order (first match wins):
    1. ``$NOM_UI_DIST`` env override (for dev / packaging tests).
    2. Inside the installed wheel: ``nom/chat/ui_dist/``.
    3. Repo dev layout: ``ui/dist/`` relative to the repo root.

    Returns None when no bundle is found — caller falls back to the
    embedded HTML.
    """
    import os

    env = os.environ.get("NOM_UI_DIST")
    if env:
        p = Path(env)
        if (p / "index.html").is_file():
            return p

    here = Path(__file__).resolve().parent
    bundled = here / "ui_dist"
    if (bundled / "index.html").is_file():
        return bundled

    # walk up looking for a sibling ui/dist (repo dev layout)
    for parent in here.parents:
        candidate = parent / "ui" / "dist"
        if (candidate / "index.html").is_file():
            return candidate
        if (parent / "pyproject.toml").is_file():
            break  # don't escape the project root
    return None


def _register_static_file(app: Any, path: Path) -> None:
    """Mount a single top-level static file under its filename.

    For files like ``favicon.svg`` / ``robots.txt`` that Vite drops at
    the root of dist/. Avoids the SPA-fallback handler swallowing them.
    """
    from fastapi.responses import FileResponse

    route = f"/{path.name}"

    @app.get(route, include_in_schema=False)  # type: ignore
    def _serve() -> Any:
        return FileResponse(path)


def _material_to_dict(mat: Any) -> dict[str, Any]:
    return {
        "id": mat.id,
        "space_id": mat.space_id,
        "name": mat.name,
        "n_bytes": mat.n_bytes,
        "n_chunks": mat.n_chunks,
        "uploaded_at": mat.uploaded_at,
    }


# Extension → MIME for inline serving. Stays narrow on purpose: only
# the formats the upload pipeline accepts get a real type so the browser
# can preview them. Everything else falls back to octet-stream so the
# user still gets a download link.
_MIME_BY_EXT: dict[str, str] = {
    ".pdf": "application/pdf",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".tif": "image/tiff",
    ".tiff": "image/tiff",
    ".bmp": "image/bmp",
    ".txt": "text/plain; charset=utf-8",
    ".md": "text/markdown; charset=utf-8",
    ".markdown": "text/markdown; charset=utf-8",
    ".csv": "text/csv; charset=utf-8",
    ".tsv": "text/tab-separated-values; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".jsonl": "application/x-jsonlines; charset=utf-8",
    ".html": "text/html; charset=utf-8",
    ".htm": "text/html; charset=utf-8",
    ".xml": "application/xml; charset=utf-8",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
}


def _mime_for(name: str) -> str:
    ext = Path(name).suffix.lower()
    return _MIME_BY_EXT.get(ext, "application/octet-stream")


# ---------------------------------------------------------------------------
# Fallback HTML UI — served when the React+ShadCN bundle (ui/dist) isn't
# available. Useful for chat-only installs and dev sanity checks. Build
# the real UI with: cd ui && pnpm install && pnpm build
# ---------------------------------------------------------------------------

_FALLBACK_UI = """<!doctype html>
<html lang="vi">
<head>
  <meta charset="utf-8">
  <title>Nôm — Vietnamese AI document Q&A</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <style>
    :root {
      --bg: #f1ede3;
      --ink: #141414;
      --ink-soft: #2a2a28;
      --accent: #c46a37;
      --line: rgba(20,20,20,.15);
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font: 15px/1.6 -apple-system, BlinkMacSystemFont, "Inter", system-ui, sans-serif;
      background: var(--bg);
      color: var(--ink);
    }
    header {
      border-bottom: 1px solid var(--ink);
      padding: 18px 28px;
      display: flex;
      align-items: baseline;
      gap: 12px;
    }
    header h1 {
      margin: 0;
      font: 700 24px/1 "Space Grotesk", system-ui;
      letter-spacing: -.025em;
    }
    header .vn { color: var(--accent); font-weight: 400; opacity: .7; }
    header .tag {
      font: 500 11px/1 ui-monospace, monospace;
      letter-spacing: .12em;
      text-transform: uppercase;
      color: var(--ink-soft);
    }
    main { max-width: 980px; margin: 0 auto; padding: 28px; }
    section { margin-bottom: 36px; }
    section h2 {
      font: 600 13px/1 ui-monospace, monospace;
      letter-spacing: .12em;
      text-transform: uppercase;
      color: var(--ink-soft);
      margin: 0 0 14px;
    }
    .row { display: flex; gap: 8px; flex-wrap: wrap; }
    button, input[type="text"], textarea, select {
      font: inherit;
      border: 1px solid var(--ink);
      background: white;
      color: var(--ink);
      padding: 9px 14px;
      border-radius: 0;
    }
    button {
      background: var(--ink);
      color: var(--bg);
      cursor: pointer;
      font-weight: 500;
    }
    button.ghost { background: transparent; color: var(--ink); }
    button.accent { background: var(--accent); color: #1a0f06; }
    .card {
      border: 1px solid var(--line);
      background: white;
      padding: 14px 16px;
      margin-bottom: 8px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 12px;
    }
    .card.active { border-color: var(--ink); box-shadow: 4px 4px 0 var(--ink); }
    .card .meta { font: 500 11px/1 ui-monospace, monospace; color: var(--ink-soft); }
    .answer {
      padding: 18px 20px;
      background: white;
      border-left: 4px solid var(--accent);
      margin-top: 14px;
      white-space: pre-wrap;
    }
    .citations { margin-top: 14px; }
    .citation {
      padding: 10px 14px;
      background: white;
      border: 1px solid var(--line);
      margin-bottom: 6px;
      font-size: 13.5px;
    }
    .citation .head {
      font: 500 11px/1 ui-monospace, monospace;
      color: var(--accent);
      letter-spacing: .08em;
      margin-bottom: 4px;
    }
    .empty { color: var(--ink-soft); font-style: italic; }
    label { display: block; margin: 8px 0 4px; font-size: 13px; color: var(--ink-soft); }
    .hidden { display: none; }
    .grid { display: grid; grid-template-columns: 320px 1fr; gap: 28px; }
    @media (max-width: 760px) { .grid { grid-template-columns: 1fr; } }
  </style>
</head>
<body>
  <header>
    <h1>Nôm <span class="vn">喃</span></h1>
    <span class="tag">công cụ ai tiếng việt</span>
  </header>

  <main>
    <div class="grid">
      <section>
        <h2>§ spaces</h2>
        <div class="row" style="margin-bottom:12px;">
          <input id="space-name" type="text" placeholder="New space name" style="flex:1;">
          <button class="accent" id="create-space">Create</button>
        </div>
        <div id="space-list"></div>
      </section>

      <section id="space-panel" class="hidden">
        <h2 id="space-title">§ space</h2>

        <h2 style="margin-top:18px;">§ materials</h2>
        <div id="material-list" style="margin-bottom:14px;"></div>
        <div class="row">
          <input id="upload-file" type="file" style="flex:1;">
          <button id="upload" class="ghost">Upload</button>
        </div>

        <h2 style="margin-top:24px;">§ ask</h2>
        <textarea id="question" rows="3" style="width:100%;"
          placeholder="Đặt câu hỏi về tài liệu trong space này..."></textarea>
        <div class="row" style="margin-top:8px;">
          <button class="accent" id="ask">Ask</button>
        </div>
        <div id="answer-area"></div>
      </section>
    </div>
  </main>

  <script>
    const $ = (id) => document.getElementById(id);
    let activeSpace = null;

    async function api(path, opts = {}) {
      const res = await fetch(path, opts);
      if (!res.ok) {
        const detail = await res.text();
        throw new Error(`${res.status}: ${detail}`);
      }
      return res.status === 204 ? null : res.json();
    }

    async function refreshSpaces() {
      const spaces = await api('/api/spaces');
      const list = $('space-list');
      list.innerHTML = '';
      if (!spaces.length) {
        list.innerHTML = '<div class="empty">No spaces yet. Create one above.</div>';
        return;
      }
      for (const s of spaces) {
        const d = document.createElement('div');
        d.className = 'card' + (activeSpace === s.id ? ' active' : '');
        d.innerHTML = `<span><strong>${s.name}</strong> <span class="meta">· ${s.n_materials} materials</span></span>`;
        const del = document.createElement('button');
        del.className = 'ghost';
        del.textContent = '✕';
        del.style.padding = '4px 8px';
        del.onclick = async (e) => {
          e.stopPropagation();
          if (!confirm(`Delete space "${s.name}"?`)) return;
          await api(`/api/spaces/${s.id}`, { method: 'DELETE' });
          if (activeSpace === s.id) { activeSpace = null; $('space-panel').classList.add('hidden'); }
          refreshSpaces();
        };
        d.appendChild(del);
        d.onclick = () => selectSpace(s.id, s.name);
        list.appendChild(d);
      }
    }

    async function selectSpace(id, name) {
      activeSpace = id;
      $('space-title').textContent = `§ ${name}`;
      $('space-panel').classList.remove('hidden');
      $('answer-area').innerHTML = '';
      await refreshMaterials();
      refreshSpaces();
    }

    async function refreshMaterials() {
      if (!activeSpace) return;
      const mats = await api(`/api/spaces/${activeSpace}/materials`);
      const list = $('material-list');
      list.innerHTML = '';
      if (!mats.length) {
        list.innerHTML = '<div class="empty">No materials uploaded yet.</div>';
        return;
      }
      for (const m of mats) {
        const d = document.createElement('div');
        d.className = 'card';
        d.innerHTML = `<span><strong>${m.name}</strong>
          <span class="meta">· ${(m.n_bytes/1024).toFixed(1)} KB · ${m.n_chunks || '—'} chunks</span></span>`;
        list.appendChild(d);
      }
    }

    $('create-space').onclick = async () => {
      const name = $('space-name').value.trim();
      if (!name) return;
      $('space-name').value = '';
      const space = await api('/api/spaces', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name }),
      });
      selectSpace(space.id, space.name);
    };

    $('upload').onclick = async () => {
      if (!activeSpace) return;
      const f = $('upload-file').files[0];
      if (!f) return;
      const fd = new FormData();
      fd.append('file', f);
      fd.append('name', f.name);
      await api(`/api/spaces/${activeSpace}/materials`, { method: 'POST', body: fd });
      $('upload-file').value = '';
      refreshMaterials();
      refreshSpaces();
    };

    $('ask').onclick = async () => {
      if (!activeSpace) return;
      const q = $('question').value.trim();
      if (!q) return;
      const area = $('answer-area');
      area.innerHTML = '<div class="answer empty">Thinking…</div>';
      try {
        const ans = await api(`/api/spaces/${activeSpace}/ask`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ question: q, top_k: 5 }),
        });
        let html = `<div class="answer">${escapeHtml(ans.text)}</div>`;
        if (ans.citations && ans.citations.length) {
          html += '<div class="citations">';
          ans.citations.forEach((c, i) => {
            html += `<div class="citation">
              <div class="head">[${i+1}] doc ${c.doc_idx} · chunk ${c.chunk_idx} · score ${c.score.toFixed(3)}</div>
              <div>${escapeHtml(c.text)}</div>
            </div>`;
          });
          html += '</div>';
        }
        area.innerHTML = html;
      } catch (err) {
        area.innerHTML = `<div class="answer" style="border-left-color:#c0392b;">${escapeHtml(err.message)}</div>`;
      }
    };

    function escapeHtml(s) {
      return String(s).replace(/[&<>"']/g, m => ({
        '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'
      }[m]));
    }

    refreshSpaces();
  </script>
</body>
</html>
"""

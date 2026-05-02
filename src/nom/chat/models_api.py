"""Model inventory + pull management — ``/api/models/*``.

Read-only listing of installed models (Ollama tags + HuggingFace
disk cache), plus async background pulls with progress tracking.
Designed for the desktop-app Models tab — one server process, one
in-memory pull tracker, ≤ a few concurrent downloads.

For multi-worker production deployments the pull tracker would need a
durable backing store (SQLite / Redis); v0 uses a process-local dict.
"""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from fastapi import FastAPI


__all__ = ["register_models_routes"]


# In-process tracker. Key = pull_id (uuid).
_PULLS: dict[str, _PullState] = {}
# Strong refs to background pull tasks so they don't get GC'd mid-run
# (asyncio.create_task only weak-refs them).
_PULL_TASKS: set[asyncio.Task[None]] = set()
# Bound how many pulls run concurrently — Ollama serializes downloads
# server-side anyway, but the API can queue. v0: one slot per source.
_MAX_CONCURRENT_PULLS = 3
_PULL_RETENTION_SECONDS = 600  # garbage-collect completed pulls after 10 min


@dataclass
class _PullState:
    pull_id: str
    source: str  # "ollama"
    model: str
    status: str = "pending"  # pending | downloading | success | error | cancelled
    downloaded_bytes: int = 0
    total_bytes: int = 0
    error: str | None = None
    started_at: float = field(default_factory=time.time)
    completed_at: float | None = None
    layers: dict[str, dict[str, int]] = field(default_factory=dict)
    cancel_event: asyncio.Event = field(default_factory=asyncio.Event)

    def to_dict(self) -> dict[str, Any]:
        progress = self.downloaded_bytes / self.total_bytes if self.total_bytes > 0 else 0.0
        return {
            "pull_id": self.pull_id,
            "source": self.source,
            "model": self.model,
            "status": self.status,
            "downloaded_bytes": self.downloaded_bytes,
            "total_bytes": self.total_bytes,
            "progress": round(progress, 4),
            "error": self.error,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
        }


def register_models_routes(
    app: FastAPI,
    *,
    ollama_url: str = "http://localhost:11434",
) -> None:
    """Mount /api/models/* on ``app``."""
    from fastapi import HTTPException

    @app.get("/api/models")
    async def list_models() -> dict[str, Any]:
        """Installed models from Ollama tags + HF disk cache."""
        ollama_models, ollama_reachable = await _list_ollama_models(ollama_url)
        hf_models = _list_hf_cache()
        return {
            "ollama": {
                "url": ollama_url,
                "reachable": ollama_reachable,
                "models": ollama_models,
            },
            "hf_cache": hf_models,
            "catalog": _CURATED_CATALOG,
        }

    @app.post("/api/models/pull")
    async def start_pull(payload: dict[str, Any]) -> dict[str, Any]:
        """Start one model pull. Source = ``ollama`` only in v0."""
        source = str(payload.get("source", "ollama"))
        model = str(payload.get("model", "")).strip()
        if not model:
            raise HTTPException(status_code=422, detail="`model` is required")
        if source != "ollama":
            raise HTTPException(
                status_code=422,
                detail=f"unsupported source {source!r}; v0 supports 'ollama'",
            )
        if _count_active_pulls() >= _MAX_CONCURRENT_PULLS:
            raise HTTPException(
                status_code=429,
                detail=(
                    f"too many concurrent pulls ({_MAX_CONCURRENT_PULLS}); "
                    f"wait for one to finish or cancel it"
                ),
            )

        pull_id = str(uuid.uuid4())
        state = _PullState(pull_id=pull_id, source=source, model=model)
        _PULLS[pull_id] = state
        _spawn_pull_task(state, ollama_url)
        return {"pull_id": pull_id, "model": model, "status": "started"}

    @app.post("/api/models/pull/batch")
    async def start_pull_batch(payload: dict[str, Any]) -> dict[str, Any]:
        """Start multiple pulls at once. Body: ``{"models": ["qwen3:8b", ...]}``.

        Useful for first-run setup wizards. Respects
        ``_MAX_CONCURRENT_PULLS`` — extra requests get a 429 detail in
        their response slot but the rest still kick off.
        """
        models = payload.get("models")
        if not isinstance(models, list) or not models:
            raise HTTPException(status_code=422, detail="`models` must be a non-empty list")
        results: list[dict[str, Any]] = []
        for model_id in models:
            model_str = str(model_id).strip()
            if not model_str:
                results.append({"model": model_id, "status": "rejected", "error": "empty id"})
                continue
            if _count_active_pulls() >= _MAX_CONCURRENT_PULLS:
                results.append(
                    {
                        "model": model_str,
                        "status": "rejected",
                        "error": "concurrency limit reached",
                    }
                )
                continue
            pull_id = str(uuid.uuid4())
            state = _PullState(pull_id=pull_id, source="ollama", model=model_str)
            _PULLS[pull_id] = state
            _spawn_pull_task(state, ollama_url)
            results.append(
                {
                    "model": model_str,
                    "status": "started",
                    "pull_id": pull_id,
                }
            )
        return {"results": results}

    @app.get("/api/models/pulls")
    async def list_pulls() -> dict[str, Any]:
        """Active + recently completed pulls."""
        _gc_old_pulls()
        return {"pulls": [s.to_dict() for s in _PULLS.values()]}

    @app.post("/api/models/pull/{pull_id}/cancel")
    async def cancel_pull(pull_id: str) -> dict[str, Any]:
        state = _PULLS.get(pull_id)
        if state is None:
            raise HTTPException(status_code=404, detail="pull_id not found")
        if state.status not in ("pending", "downloading"):
            return state.to_dict()
        state.cancel_event.set()
        return state.to_dict()

    @app.delete("/api/models/ollama/{model:path}")
    async def delete_ollama_model(model: str) -> dict[str, Any]:
        """Uninstall an Ollama model."""
        import httpx

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                r = await client.request(
                    "DELETE",
                    f"{ollama_url}/api/delete",
                    json={"name": model},
                )
        except httpx.HTTPError as exc:
            raise HTTPException(status_code=503, detail=f"ollama unreachable: {exc}") from exc
        if r.status_code not in (200, 204):
            raise HTTPException(
                status_code=r.status_code,
                detail=f"ollama delete failed: {r.text}",
            )
        return {"deleted": model}


# ---------------------------------------------------------------------------
# Internals


def _spawn_pull_task(state: _PullState, ollama_url: str) -> None:
    """Kick off a pull as a background task with strong-ref retention."""
    task = asyncio.create_task(_run_ollama_pull(state, ollama_url))
    _PULL_TASKS.add(task)
    task.add_done_callback(_PULL_TASKS.discard)


async def _list_ollama_models(ollama_url: str) -> tuple[list[dict[str, Any]], bool]:
    import httpx

    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            r = await client.get(f"{ollama_url}/api/tags")
            if r.status_code != 200:
                return [], False
            data = r.json()
            models = [
                {
                    "name": m["name"],
                    "size_bytes": m.get("size", 0),
                    "modified_at": m.get("modified_at"),
                    "digest": m.get("digest"),
                }
                for m in data.get("models", [])
            ]
            return models, True
    except (httpx.HTTPError, OSError):
        return [], False


def _list_hf_cache() -> list[dict[str, Any]]:
    try:
        from huggingface_hub import scan_cache_dir
    except ImportError:
        return []
    try:
        cache = scan_cache_dir()
    except Exception:
        return []
    out: list[dict[str, Any]] = []
    for repo in cache.repos:
        out.append(
            {
                "repo_id": repo.repo_id,
                "repo_type": repo.repo_type,
                "size_bytes": repo.size_on_disk,
                "last_accessed": repo.last_accessed,
                "n_revisions": len(repo.revisions),
            }
        )
    return out


def _count_active_pulls() -> int:
    return sum(1 for s in _PULLS.values() if s.status in ("pending", "downloading"))


def _gc_old_pulls() -> None:
    now = time.time()
    expired = [
        pid
        for pid, s in _PULLS.items()
        if s.completed_at is not None and (now - s.completed_at) > _PULL_RETENTION_SECONDS
    ]
    for pid in expired:
        _PULLS.pop(pid, None)


async def _run_ollama_pull(state: _PullState, ollama_url: str) -> None:
    import httpx

    state.status = "downloading"
    try:
        async with (
            httpx.AsyncClient(timeout=None) as client,
            client.stream(
                "POST",
                f"{ollama_url}/api/pull",
                json={"name": state.model, "stream": True},
            ) as response,
        ):
            if response.status_code != 200:
                state.status = "error"
                state.error = f"ollama returned HTTP {response.status_code}"
                state.completed_at = time.time()
                return

            async for line in response.aiter_lines():
                if state.cancel_event.is_set():
                    state.status = "cancelled"
                    state.completed_at = time.time()
                    return
                if not line.strip():
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                _apply_pull_event(state, event)
                if event.get("status") == "success":
                    state.status = "success"
                    state.completed_at = time.time()
                    return
            # Stream ended without explicit success — assume success
            if state.status == "downloading":
                state.status = "success"
                state.completed_at = time.time()
    except (httpx.HTTPError, OSError) as exc:
        state.status = "error"
        state.error = str(exc)
        state.completed_at = time.time()


def _apply_pull_event(state: _PullState, event: dict[str, Any]) -> None:
    """Update ``state`` from one Ollama pull-progress JSON event.

    Ollama events look like:
    - ``{"status": "downloading manifest"}``
    - ``{"status": "downloading", "digest": "sha256:abc", "total": 4711, "completed": 1234}``
    - ``{"status": "verifying sha256 digest"}``
    - ``{"status": "writing manifest"}``
    - ``{"status": "success"}``
    """
    digest = event.get("digest")
    if digest and "total" in event:
        state.layers[digest] = {
            "total": int(event["total"]),
            "completed": int(event.get("completed", 0)),
        }
        state.total_bytes = sum(layer["total"] for layer in state.layers.values())
        state.downloaded_bytes = sum(layer["completed"] for layer in state.layers.values())


# ---------------------------------------------------------------------------
# Curated catalog — the UI's "Recommended for VN" list.


_CURATED_CATALOG: list[dict[str, Any]] = [
    {
        "id": "qwen3:1.7b",
        "label": "Qwen3 1.7B (siêu nhẹ)",
        "tier": "light",
        "size_gb": 1.4,
        "needs_ram_gb": 4,
        "use_cases": ["chat", "diacritic", "translate"],
        "license": "Apache 2.0",
    },
    {
        "id": "qwen3:8b",
        "label": "Qwen3 8B (mặc định)",
        "tier": "standard",
        "size_gb": 5.1,
        "needs_ram_gb": 8,
        "use_cases": ["chat", "diacritic", "translate", "rag"],
        "license": "Apache 2.0",
    },
    {
        "id": "qwen3:14b",
        "label": "Qwen3 14B (chất lượng cao)",
        "tier": "power",
        "size_gb": 9.0,
        "needs_ram_gb": 16,
        "use_cases": ["chat", "rag"],
        "license": "Apache 2.0",
    },
    {
        "id": "gemma3:4b",
        "label": "Gemma3 4B",
        "tier": "light",
        "size_gb": 3.3,
        "needs_ram_gb": 6,
        "use_cases": ["chat", "diacritic"],
        "license": "Gemma",
    },
    {
        "id": "gemma3:12b",
        "label": "Gemma3 12B",
        "tier": "power",
        "size_gb": 8.0,
        "needs_ram_gb": 16,
        "use_cases": ["chat", "rag"],
        "license": "Gemma",
    },
]

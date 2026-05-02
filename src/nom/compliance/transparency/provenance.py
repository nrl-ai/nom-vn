"""Đ11.2 — machine-readable marking for AI-generated content.

The law's text says marking is "định dạng máy đọc theo quy định của
Chính phủ" — Government will detail the format. Until that decree
publishes (estimated Q3-Q4 2026), we ship a stable JSON sidecar
schema that's compatible in spirit with C2PA / Content Authenticity
Initiative claims, plus a tiny HTML helper for web-rendered text.

When the official decree publishes:
- :data:`PROVENANCE_VERSION` bumps.
- A translator from this schema → the official format goes into a
  ``v2`` submodule.
- Old sidecars stay readable; new ones target both the legacy nom
  schema and the official format.

This module deliberately does not depend on ``c2pa-python`` (heavy
ImageMagick / Rust toolchain). When a deployer wants full C2PA
provenance they install ``c2pa-python`` themselves and use a
:func:`mark_image` adapter — the JSON sidecar we produce is the
``manifest`` blob C2PA's CLI accepts.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

__all__ = [
    "PROVENANCE_VERSION",
    "ProvenanceManifest",
    "mark_image",
    "mark_text_html",
    "write_sidecar",
]


PROVENANCE_VERSION = "nom-1"
"""Schema version. Bumps when the official Đ11.2 decree publishes."""


@dataclass(frozen=True, slots=True)
class ProvenanceManifest:
    """A single machine-readable record of "this content is AI-generated".

    Mirrors the shape of a C2PA claim closely enough that the same
    record can be embedded as a C2PA manifest assertion when the
    deployer opts into ``c2pa-python``.
    """

    version: str
    asset: str
    """Original asset reference — filename / URL / DOI / etc."""

    media_type: str
    """MIME type, e.g. "image/png", "audio/wav", "text/html"."""

    model: str
    """Model identifier — "ollama:qwen3:8b", "stable-diffusion-3.5", etc."""

    created_at: str
    """ISO-8601 UTC. Always set by :func:`mark_image` etc."""

    is_ai_generated: bool = True
    is_synthetic: bool = False
    """When True triggers Đ11.4 deepfake-labeling obligation
    (simulating real persons or reenacting actual events)."""

    prompt_summary: str | None = None
    """Optional public-safe summary; full prompt should NOT go here
    by default (privacy + trade secret). Use the audit log for full
    traceability."""

    extra: dict[str, Any] = field(default_factory=dict)
    """Free-form for deployer-specific metadata (style preset, license,
    licensee, etc.)."""

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False, indent=2)


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def mark_image(
    path: str | Path,
    *,
    model: str,
    prompt_summary: str | None = None,
    is_synthetic: bool = False,
    extra: dict[str, Any] | None = None,
) -> ProvenanceManifest:
    """Build a manifest for an AI-generated image. Pair with
    :func:`write_sidecar` to write it next to the file."""
    return ProvenanceManifest(
        version=PROVENANCE_VERSION,
        asset=str(path),
        media_type=_guess_media_type(path),
        model=model,
        created_at=_now_iso(),
        is_ai_generated=True,
        is_synthetic=is_synthetic,
        prompt_summary=prompt_summary,
        extra=dict(extra or {}),
    )


def write_sidecar(manifest: ProvenanceManifest, *, sidecar_path: str | Path | None = None) -> Path:
    """Write the manifest as a ``<asset>.nom-provenance.json`` sidecar.

    Override ``sidecar_path`` when you need a non-standard location
    (e.g., S3-side companion object). Returns the written path.
    """
    if sidecar_path is None:
        sidecar = Path(manifest.asset).with_suffix(
            Path(manifest.asset).suffix + ".nom-provenance.json"
        )
    else:
        sidecar = Path(sidecar_path)
    sidecar.parent.mkdir(parents=True, exist_ok=True)
    sidecar.write_text(manifest.to_json(), encoding="utf-8")
    return sidecar


def mark_text_html(
    html: str,
    *,
    model: str,
    is_synthetic: bool = False,
) -> str:
    """Inject a ``<meta name="ai-generated">`` tag into an HTML document.

    Idempotent: calling again replaces the existing tag with a fresh
    timestamp rather than stacking duplicates. Returns the patched
    HTML.
    """
    tag = (
        f'<meta name="ai-generated" content="true" '
        f'data-nom-version="{PROVENANCE_VERSION}" '
        f'data-model="{_html_attr(model)}" '
        f'data-is-synthetic="{"true" if is_synthetic else "false"}" '
        f'data-created-at="{_now_iso()}">'
    )
    # Naive: replace any prior tag, then insert before </head> or at top.
    cleaned = _strip_existing_tag(html)
    if "</head>" in cleaned:
        return cleaned.replace("</head>", f"  {tag}\n</head>", 1)
    return f"{tag}\n{cleaned}"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


_MEDIA_BY_SUFFIX: dict[str, str] = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".gif": "image/gif",
    ".wav": "audio/wav",
    ".mp3": "audio/mpeg",
    ".mp4": "video/mp4",
    ".webm": "video/webm",
    ".html": "text/html",
    ".htm": "text/html",
    ".txt": "text/plain",
}


def _guess_media_type(path: str | Path) -> str:
    suffix = Path(path).suffix.lower()
    return _MEDIA_BY_SUFFIX.get(suffix, "application/octet-stream")


def _html_attr(value: str) -> str:
    return value.replace("&", "&amp;").replace('"', "&quot;").replace("<", "&lt;")


def _strip_existing_tag(html: str) -> str:
    """Remove any existing ``<meta name="ai-generated">`` tag.

    Cheap pattern match — assumes a well-formed tag we ourselves
    produced. A previous call by a different tool with non-matching
    attribute order won't be detected; that's fine, browsers will
    just see two meta tags and the latter wins by convention.
    """
    marker_open = '<meta name="ai-generated"'
    idx = html.find(marker_open)
    if idx == -1:
        return html
    end = html.find(">", idx)
    if end == -1:
        return html
    # Strip the tag plus any trailing whitespace / newline.
    after = end + 1
    while after < len(html) and html[after] in " \t\n":
        after += 1
    return html[:idx] + html[after:]

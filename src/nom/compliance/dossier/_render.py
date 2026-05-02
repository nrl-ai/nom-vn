"""Shared Jinja2 environment + helpers for dossier rendering.

Templates live next to this module under ``../templates/`` and are
loaded via :class:`PackageLoader`. Renders are deterministic — same
context dict in, same byte output. That property matters for hash
verification when a dossier is referenced from the audit log.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

__all__ = ["render_template"]


def _env() -> Any:
    """Return a configured Jinja2 environment.

    Lazy-imported because Jinja2 only ships in the [compliance] extra.
    Re-creating per call is fine — environments are cheap and dossier
    rendering isn't hot-path.
    """
    from jinja2 import Environment, FileSystemLoader, select_autoescape

    template_dir = Path(__file__).parent.parent / "templates"
    return Environment(
        loader=FileSystemLoader(str(template_dir)),
        autoescape=select_autoescape(default=False),
        keep_trailing_newline=True,
        trim_blocks=False,
        lstrip_blocks=False,
    )


def render_template(name: str, context: dict[str, Any]) -> str:
    """Load + render the named template against ``context``.

    Template filenames follow ``<artifact>.<lang>.md.j2`` so callers
    pass the language-specific name (e.g. ``"classification.vi.md.j2"``).
    Returns the rendered Markdown string; the caller decides whether
    to write to disk, zip, or convert to .docx.
    """
    return str(_env().get_template(name).render(**context))

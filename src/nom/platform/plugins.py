"""Plugin discovery via ``importlib.metadata.entry_points``.

Concrete EE implementations live in a separate distribution
(``nom-vn-enterprise``) and register themselves via entry points in
their ``pyproject.toml``::

    [project.entry-points."nom.platform.authenticators"]
    oidc = "nom_ee.auth.oidc:OIDCAuthenticator"

Once installed, ``load_plugin("auth", "oidc")`` returns the class
without OSS code importing the EE module — the seam stays clean and
``nom-vn`` keeps its small dependency surface.

Group names live in :data:`ENTRY_POINT_GROUPS`. Add new ones here
when introducing a new Protocol seam — never as ad-hoc strings at
call sites.
"""

from __future__ import annotations

from importlib.metadata import EntryPoint, entry_points
from typing import Any

__all__ = [
    "ENTRY_POINT_GROUPS",
    "PluginNotFoundError",
    "list_plugins",
    "load_plugin",
]


ENTRY_POINT_GROUPS: dict[str, str] = {
    "auth": "nom.platform.authenticators",
    "rbac": "nom.platform.rbac",
    "pii": "nom.platform.pii_detectors",
    "redactor": "nom.platform.redactors",
    "forwarder": "nom.platform.audit_forwarders",
}


class PluginNotFoundError(LookupError):
    """No entry point matched the requested category + name."""


def list_plugins(category: str) -> list[EntryPoint]:
    """Enumerate every plugin registered for a category.

    Useful for admin UIs ("which auth backends are installed?")
    and for tests that assert the right plugin set is wired.
    """
    group = _group(category)
    return list(entry_points(group=group))


def load_plugin(category: str, name: str | None = None) -> Any:
    """Load a plugin class by category + optional name.

    ``category`` is one of the keys in :data:`ENTRY_POINT_GROUPS`.
    ``name`` selects a specific entry point inside the group; when
    omitted, the first registered plugin wins (deterministic only
    when exactly one is installed — production code should always
    pass an explicit name).

    Raises:
        PluginNotFoundError: no matching entry point.
    """
    group = _group(category)
    eps = list(entry_points(group=group))
    if not eps:
        msg = f"no plugins registered for {category!r} (group {group!r})"
        raise PluginNotFoundError(msg)
    if name is None:
        return eps[0].load()
    for ep in eps:
        if ep.name == name:
            return ep.load()
    available = sorted(ep.name for ep in eps)
    msg = f"plugin {name!r} not found in {category!r} (group {group!r}); available: {available}"
    raise PluginNotFoundError(msg)


def _group(category: str) -> str:
    try:
        return ENTRY_POINT_GROUPS[category]
    except KeyError as exc:
        valid = sorted(ENTRY_POINT_GROUPS)
        msg = f"unknown plugin category {category!r} (valid: {valid})"
        raise ValueError(msg) from exc

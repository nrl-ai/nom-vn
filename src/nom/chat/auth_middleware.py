"""FastAPI middleware that turns a ``nom.platform.Authenticator`` into
a request gate.

Usage from ``build_app``::

    if (auth := _resolve_authenticator()) is not None:
        install_auth_middleware(app, authenticator=auth)

The middleware:

1. Extracts ``Credentials`` from the ``Authorization`` header.
2. Calls ``authenticator.authenticate(credentials=...)``.
3. On success, sets ``nom.platform.current_user`` for the duration
   of the request handler so downstream code (``AuditedLLM``,
   workspace lookups) sees the authenticated identity.
4. On any ``AuthError``, returns 401 with a clean JSON body.

Public-by-design routes (``/api/health``) are exempt — the UI needs
``/api/health`` to render the "log in" prompt without being logged
in yet.

The middleware is decoupled from any specific Authenticator
implementation: the same code path serves the OSS bearer token, an
EE OIDC plugin, or a future SAML adapter.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from nom.platform import Authenticator, AuthError, Credentials, set_current_user

if TYPE_CHECKING:
    from fastapi import FastAPI

__all__ = ["install_auth_middleware"]


# Routes that stay reachable without auth — primarily the health
# endpoint so an unauthenticated UI can detect the gated state.
_PUBLIC_API_PATHS: frozenset[str] = frozenset({"/api/health"})


def install_auth_middleware(app: FastAPI, *, authenticator: Authenticator) -> None:
    """Install an HTTP middleware that gates ``/api/*`` via the given
    Authenticator.

    Idempotent? No. Calling twice stacks two middlewares — caller is
    responsible for invoking once per app.
    """
    from fastapi import Request
    from fastapi.responses import JSONResponse

    @app.middleware("http")
    async def _auth_middleware(request: Request, call_next: Any) -> Any:
        if not request.url.path.startswith("/api/"):
            return await call_next(request)
        if request.url.path in _PUBLIC_API_PATHS:
            return await call_next(request)

        credentials = _extract_credentials(request)
        try:
            user = authenticator.authenticate(credentials=credentials)
        except AuthError as exc:
            return JSONResponse(
                status_code=401,
                content={"detail": f"Authentication required: {exc}"},
            )

        token = set_current_user_token(user)
        try:
            return await call_next(request)
        finally:
            reset_current_user(token)


def _extract_credentials(request: Any) -> Credentials:
    """Pull the bits an Authenticator might want out of the request.

    Today this is only the bearer token; SAML / cookie sessions /
    API-key headers slot in here without changing the middleware
    contract.
    """
    auth_header = request.headers.get("authorization", "")
    bearer_token: str | None = None
    if auth_header.lower().startswith("bearer "):
        bearer_token = auth_header[7:].strip() or None
    return Credentials(
        bearer_token=bearer_token,
        raw_headers=dict(request.headers),
    )


def set_current_user_token(user: Any) -> Any:
    """Set the ContextVar and return its reset token.

    Wrapping ``ContextVar.set`` in a small helper keeps the
    middleware free of imports the type-checker doesn't need at
    runtime, and is the seam tests poke when asserting per-request
    cleanup."""
    from nom.platform.context import current_user

    return current_user.set(user)


def reset_current_user(token: Any) -> None:
    from nom.platform.context import current_user

    current_user.reset(token)


# Re-export for callers that prefer the helper over importing the
# ContextVar directly.
__all__ += ["reset_current_user", "set_current_user", "set_current_user_token"]

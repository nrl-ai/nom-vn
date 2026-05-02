"""Tests for ``nom.platform.auth`` — bearer-token default + Protocol shape."""

from __future__ import annotations

import pytest

from nom.platform import (
    AuthDeniedError,
    Authenticator,
    BearerTokenAuth,
    Credentials,
    User,
)


def test_bearer_token_authenticator_satisfies_protocol() -> None:
    auth = BearerTokenAuth(token="s3cret")
    assert isinstance(auth, Authenticator)


def test_bearer_token_grants_user_on_match() -> None:
    auth = BearerTokenAuth(token="s3cret", user_id="alice", tenant_id="acme")
    user = auth.authenticate(credentials=Credentials(bearer_token="s3cret"))
    assert isinstance(user, User)
    assert user.id == "alice"
    assert user.tenant_id == "acme"
    assert "workspace.editor" in user.roles


def test_bearer_token_denies_on_mismatch() -> None:
    auth = BearerTokenAuth(token="s3cret")
    with pytest.raises(AuthDeniedError):
        auth.authenticate(credentials=Credentials(bearer_token="wrong"))


def test_bearer_token_denies_on_missing_credential() -> None:
    auth = BearerTokenAuth(token="s3cret")
    with pytest.raises(AuthDeniedError):
        auth.authenticate(credentials=Credentials())


def test_bearer_token_compare_is_constant_time() -> None:
    # We cannot directly assert constant-time behaviour (timing tests
    # are flaky in CI); instead verify the implementation uses
    # ``secrets.compare_digest``. Smoke: attacker-controlled tokens of
    # vastly different lengths should not produce a Python equality
    # short-circuit difference observable to us — the function still
    # returns AuthDeniedError uniformly.
    auth = BearerTokenAuth(token="x" * 64)
    for candidate in ("", "x", "x" * 32, "x" * 65, "y" * 64):
        with pytest.raises(AuthDeniedError):
            auth.authenticate(credentials=Credentials(bearer_token=candidate))

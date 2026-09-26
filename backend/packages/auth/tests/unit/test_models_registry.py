"""Every model of auth is registered in its metadata."""

from __future__ import annotations

from vld.auth.infrastructure import AuthBase


def test_every_model_module_is_imported() -> None:
    """Every table of the domain is registered in its metadata."""
    assert set(AuthBase.metadata.tables) == {
        "auth.users",
        "auth.verification_tokens",
        "auth.outbox",
    }

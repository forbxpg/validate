"""Пригодность секрета подписи проверяется на сборке настроек."""

from __future__ import annotations

import os

import pytest
from pydantic import SecretStr, ValidationError

from vld.core.config import MIN_JWT_SECRET_BYTES, SecuritySettings


@pytest.fixture(autouse=True)
def security_env_is_isolated(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(SecuritySettings.model_config, "env_file", None)
    for name in [name for name in os.environ if name.startswith("SECURITY_")]:
        monkeypatch.delenv(name)


def test_empty_secret_is_rejected() -> None:
    with pytest.raises(ValidationError, match="at least 256 bits"):
        _ = SecuritySettings(jwt_secret=SecretStr(""))


def test_short_secret_is_rejected() -> None:
    short = SecretStr("x" * (MIN_JWT_SECRET_BYTES - 1))
    with pytest.raises(ValidationError, match="at least 256 bits"):
        _ = SecuritySettings(jwt_secret=short)


def test_secret_of_exactly_the_minimum_is_accepted() -> None:
    settings = SecuritySettings(jwt_secret=SecretStr("x" * MIN_JWT_SECRET_BYTES))
    assert settings.jwt_secret.get_secret_value()


def test_session_lifecycle_defaults_are_pinned() -> None:
    settings = SecuritySettings(jwt_secret=SecretStr("x" * MIN_JWT_SECRET_BYTES))
    assert settings.access_ttl_seconds == 15 * 60
    assert settings.refresh_ttl_seconds == 30 * 24 * 60 * 60
    assert settings.session_ttl_seconds == 90 * 24 * 60 * 60

"""Settings read the doi-arxiv-app variable names from the environment only."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import pytest
from pydantic import ValidationError

from vld.core.config import (
    CorsSettings,
    DatabaseSettings,
    ObservabilitySettings,
    RedisSettings,
)

if TYPE_CHECKING:
    from pathlib import Path

    from pydantic_settings import BaseSettings

DATABASE_URL = "postgresql+asyncpg://validate:secret@db:5432/validate"
_OWN_PREFIXES = ("DATABASE_", "REDIS_", "MIDDLEWARE_", "LOG_", "SENTRY_")

pytestmark = pytest.mark.usefixtures("clean_environment")


def _read[S: BaseSettings](settings_class: type[S]) -> S:
    return settings_class()


@pytest.fixture
def clean_environment(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Run every test in an empty directory without any settings variable."""
    for name in [name for name in os.environ if name.startswith(_OWN_PREFIXES)]:
        monkeypatch.delenv(name)
    monkeypatch.chdir(tmp_path)


def test_database_settings_read_database_url(monkeypatch: pytest.MonkeyPatch) -> None:
    """`DATABASE_URL` and the pool variables keep their doi-arxiv-app names."""
    monkeypatch.setenv("DATABASE_URL", DATABASE_URL)
    monkeypatch.setenv("DATABASE_POOL_SIZE", "5")

    settings = _read(DatabaseSettings)

    assert str(settings.url) == DATABASE_URL
    assert settings.pool_size == 5


def test_redis_settings_read_host_port_db_and_password(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`REDIS_HOST`, `REDIS_PORT`, `REDIS_DB` and `REDIS_PASSWORD` keep their names."""
    monkeypatch.setenv("REDIS_HOST", "redis")
    monkeypatch.setenv("REDIS_PORT", "6380")
    monkeypatch.setenv("REDIS_DB", "2")
    monkeypatch.setenv("REDIS_PASSWORD", "secret")

    settings = _read(RedisSettings)

    assert (settings.host, settings.port, settings.db) == ("redis", 6380, 2)
    assert settings.password is not None
    assert settings.password.get_secret_value() == "secret"


def test_log_level_is_read_without_a_prefix(monkeypatch: pytest.MonkeyPatch) -> None:
    """`LOG_LEVEL` is the doi-arxiv-app name, with no settings prefix in front."""
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")

    assert _read(ObservabilitySettings).log_level == "DEBUG"


@pytest.mark.parametrize(
    "settings_class",
    [DatabaseSettings, RedisSettings, CorsSettings],
)
def test_a_missing_required_variable_stops_the_start(
    settings_class: type[BaseSettings],
) -> None:
    """A lost variable must fail at startup, not fall back to localhost."""
    with pytest.raises(ValidationError):
        _ = _read(settings_class)


def test_a_dotenv_file_is_not_read(tmp_path: Path) -> None:
    """Only the process environment counts: whoever starts the process loads `.env`."""
    _ = (tmp_path / ".env").write_text(f"DATABASE_URL={DATABASE_URL}\n")

    with pytest.raises(ValidationError):
        _ = _read(DatabaseSettings)


def test_cors_origins_are_a_json_list_in_lower_case(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Origins compare exactly with the `Origin` header, which browsers lower-case."""
    monkeypatch.setenv(
        "MIDDLEWARE_CORS_ALLOWED_ORIGINS",
        '["https://Validate.Example", "http://localhost:3000/"]',
    )

    assert _read(CorsSettings).allowed_origins == [
        "https://validate.example",
        "http://localhost:3000",
    ]


@pytest.mark.parametrize(
    "origin",
    [
        "validate.example",
        "ftp://validate.example",
        "https://",
        "https://validate.example/app",
        "https://validate.example?next=/",
    ],
)
def test_an_entry_that_is_not_a_bare_origin_is_refused(origin: str) -> None:
    """An origin with a path would never match the `Origin` header."""
    with pytest.raises(ValidationError):
        _ = CorsSettings(allowed_origins=[origin])

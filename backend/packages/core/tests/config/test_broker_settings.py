"""Адрес брокера разбирается на сборке настроек, а не на первой публикации."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from vld.core.config import BrokerSettings, get_broker_settings


@pytest.mark.parametrize(
    "given",
    [
        "redis://localhost:6379",
        "http://localhost:5672",
        "amqp",
        "localhost:5672",
        "",
    ],
)
def test_broker_settings_refuse_a_non_amqp_address(given: str) -> None:
    """Адрес брокера обязан быть amqp, иначе ошибка приедет в рантайме."""
    with pytest.raises(ValidationError):
        _ = BrokerSettings(dsn=given)  # pyright: ignore[reportArgumentType]


@pytest.mark.parametrize("given", ["amqp://guest:guest@rabbit:5672/", "amqps://rabbit"])
def test_broker_settings_accept_both_amqp_schemes(given: str) -> None:
    """TLS-вариант — тот же брокер, и отвергать его валидатору нечего."""
    assert str(BrokerSettings(dsn=given).dsn).startswith("amqp")  # pyright: ignore[reportArgumentType]


def test_broker_settings_have_no_default_address(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Пропавшая переменная обязана валить старт, а не подставлять localhost."""
    monkeypatch.setitem(BrokerSettings.model_config, "env_file", None)
    monkeypatch.delenv("BROKER_DSN", raising=False)
    get_broker_settings.cache_clear()
    with pytest.raises(ValidationError):
        _ = get_broker_settings()
    get_broker_settings.cache_clear()

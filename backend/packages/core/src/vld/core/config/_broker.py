"""Настройки брокера задач (RabbitMQ)."""

from __future__ import annotations

from functools import lru_cache
from typing import ClassVar

from pydantic import AmqpDsn
from pydantic_settings import BaseSettings, SettingsConfigDict

from ._base import settings_config


class BrokerSettings(BaseSettings):
    """Настройки брокера задач.

    Attributes:
        dsn: AmqpDsn - Адрес RabbitMQ.

    """

    dsn: AmqpDsn

    model_config: ClassVar[SettingsConfigDict] = settings_config("BROKER_")


@lru_cache
def get_broker_settings() -> BrokerSettings:
    """Получить настройки брокера задач.

    Returns:
        BrokerSettings - Синглтон на процесс.

    """
    return BrokerSettings()  # pyright: ignore[reportCallIssue]  # ty:ignore[missing-argument]

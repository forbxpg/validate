"""Settings of the task broker."""

from __future__ import annotations

from typing import ClassVar

from pydantic import AmqpDsn
from pydantic_settings import BaseSettings, SettingsConfigDict

from vld.core.config import settings_config


class BrokerSettings(BaseSettings):
    """Where the task broker lives.

    Attributes:
        url: AmqpDsn - RabbitMQ address, `amqp://user:password@host:5672/vhost`.

    """

    model_config: ClassVar[SettingsConfigDict] = settings_config("BROKER_")

    url: AmqpDsn

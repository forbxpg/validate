"""Settings of the worker: the task broker and the metrics port."""

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


class MetricsSettings(BaseSettings):
    """Where the worker serves its metrics.

    Attributes:
        host: str - Address to bind; a container binds every interface.
        port: int - Port Prometheus scrapes.

    """

    model_config: ClassVar[SettingsConfigDict] = settings_config("WORKER_METRICS_")

    host: str = "127.0.0.1"
    port: int = 9100

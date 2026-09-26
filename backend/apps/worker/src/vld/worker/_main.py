"""Composition root of the worker: container, broker, signals, two loops."""

from __future__ import annotations

import asyncio
import signal
from typing import TYPE_CHECKING

from dishka import make_async_container
from taskiq.acks import AcknowledgeType
from taskiq.api import run_receiver_task

from vld.auth.di import AUTH_PROVIDERS
from vld.core.config import ObservabilitySettings
from vld.core.di import CONTAINER_VALIDATION, CoreProvider
from vld.core.obs import configure_logging, configure_sentry

from ._broker import create_broker
from ._relay import run
from ._settings import BrokerSettings
from ._tasks import register

if TYPE_CHECKING:
    from dishka import AsyncContainer


def build_container() -> AsyncContainer:
    """Build the worker container from the providers the API uses too.

    Returns:
        AsyncContainer - The container; the caller closes it.

    """
    return make_async_container(
        CoreProvider(),
        *AUTH_PROVIDERS,
        validation_settings=CONTAINER_VALIDATION,
    )


async def _serve() -> None:
    """Relay the outbox and send letters until SIGTERM or SIGINT."""
    observability = ObservabilitySettings()
    configure_logging(observability)
    configure_sentry(observability)
    broker = create_broker(BrokerSettings())  # pyright: ignore[reportCallIssue] -- required, read from the environment
    container = build_container()
    publish_task = register(broker, container)
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stop.set)
    try:
        await broker.startup()
        async with asyncio.TaskGroup() as group:
            receiver = group.create_task(
                run_receiver_task(broker, ack_time=AcknowledgeType.WHEN_SAVED),
            )
            await run(container, publish_task, stop)
            _ = receiver.cancel()
    finally:
        await broker.shutdown()
        await container.close()


def main() -> None:
    """Run the worker: `vld-worker`."""
    asyncio.run(_serve())

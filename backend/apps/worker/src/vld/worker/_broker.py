"""Queue of the worker: TaskIQ over RabbitMQ."""

from __future__ import annotations

from typing import TYPE_CHECKING

from taskiq.middlewares import SmartRetryMiddleware
from taskiq_aio_pika import AioPikaBroker
from taskiq_aio_pika.exchange import Exchange
from taskiq_aio_pika.queue import Queue

if TYPE_CHECKING:
    from ._settings import BrokerSettings


EXCHANGE_NAME = "validate"
QUEUE_NAME = "validate.worker"
DEAD_LETTER_QUEUE_NAME = "validate.dead_letter"
DELAY_QUEUE_NAME = "validate.worker.delay"


_MAX_RETRIES = 10

_RETRY_DELAY = 60.0
_MAX_RETRY_DELAY = 600.0


def create_broker(settings: BrokerSettings) -> AioPikaBroker:
    """Build the worker broker on its own exchange and queues.

    Args:
        settings: BrokerSettings - Address of RabbitMQ.

    Returns:
        AioPikaBroker - The broker; it connects on `startup`, not here.

    """
    broker = AioPikaBroker(
        url=str(settings.url),
        exchange=Exchange(name=EXCHANGE_NAME),
        task_queues=[Queue(name=QUEUE_NAME)],
        dead_letter_queue=Queue(name=DEAD_LETTER_QUEUE_NAME),
        delay_queue=Queue(name=DELAY_QUEUE_NAME),
    ).with_middlewares(
        SmartRetryMiddleware(
            default_retry_count=_MAX_RETRIES,
            default_delay=_RETRY_DELAY,
            use_delay_exponent=True,
            max_delay_exponent=_MAX_RETRY_DELAY,
        ),
    )
    broker.is_worker_process = True
    return broker

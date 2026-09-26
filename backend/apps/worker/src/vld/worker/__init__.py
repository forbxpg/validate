"""Worker: relays the transactional outbox to RabbitMQ and sends the letters."""

from __future__ import annotations

from ._main import build_container, main

__all__ = ("build_container", "main")

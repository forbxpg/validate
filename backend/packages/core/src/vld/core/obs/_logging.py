"""Настройка логирования из ``ObservabilitySettings``."""

from __future__ import annotations

import logging
import sys
from typing import TYPE_CHECKING

import structlog

from ._redaction import SecretRedactingFilter

if TYPE_CHECKING:
    from vld.core.config import ObservabilitySettings

# The logger that uvicorn writes a string for each request. The name is a literal:
# uvicorn sets it up with its `dictConfig`, and there are no constants for import.
_ACCESS_LOGGER = "uvicorn.access"


def configure_logging(settings: ObservabilitySettings) -> None:
    """Configure structlog and stdlib logging by observability settings.

    Args:
        settings: ObservabilitySettings - Logging level and JSON format.

    """
    level = logging.getLevelNamesMapping()[settings.log_level]
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=level,
        force=True,
    )

    redaction = SecretRedactingFilter()
    for handler in logging.getLogger().handlers:
        handler.addFilter(redaction)

    access = logging.getLogger(_ACCESS_LOGGER)
    access.filters = [
        existing
        for existing in access.filters
        if not isinstance(existing, SecretRedactingFilter)
    ]
    access.addFilter(redaction)

    renderer: structlog.typing.Processor = (
        structlog.processors.JSONRenderer()
        if settings.log_json
        else structlog.dev.ConsoleRenderer()
    )
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=False,
    )

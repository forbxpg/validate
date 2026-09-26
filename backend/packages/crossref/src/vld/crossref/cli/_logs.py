"""Logs of the command line: to stderr, so stdout carries only data."""

from __future__ import annotations

import logging
import sys

import structlog


def configure_logs(*, verbose: bool) -> None:
    """Send the logs of the library to stderr: warnings, or everything with `-v`.

    An unconfigured structlog prints to stdout, debug included, which would break
    `vld-crossref ... | jq`.

    Args:
        verbose: bool - Also show debug lines.

    """
    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.dev.ConsoleRenderer(colors=sys.stderr.isatty()),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.DEBUG if verbose else logging.WARNING,
        ),
        logger_factory=structlog.PrintLoggerFactory(sys.stderr),
        cache_logger_on_first_use=False,
    )

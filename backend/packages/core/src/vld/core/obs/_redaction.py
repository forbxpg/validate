"""Redaction of secrets that go in the address segment in observability."""

from __future__ import annotations

import logging
import re
from typing import override

SECRET_PATH_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"(/calendar/feed/)[^/?\s]+?(\.ics)"),
)
"""Addresses, where the path segment is a secret, and its place in the string."""

_MASK = r"\1***\2"


def redact_secrets(text: str) -> str:
    """Redact secrets in a string, where it is printed.

    Args:
        text: str - String with a possible secret.

    Returns:
        str - The same string with `*` instead of secret segments.

    """
    for pattern in SECRET_PATH_PATTERNS:
        text = pattern.sub(_MASK, text)
    return text


class SecretRedactingFilter(logging.Filter):
    """Filter, redaction secrets in the record before it is formatted."""

    @override
    def filter(self, record: logging.LogRecord) -> bool:
        """Redact secrets in the record.

        Args:
            record: logging.LogRecord - Record going to the handler.

        Returns:
            bool - Always `True`.

        """
        if isinstance(record.args, tuple):
            record.args = tuple(
                redact_secrets(arg) if isinstance(arg, str) else arg
                for arg in record.args
            )
        if isinstance(record.msg, str):
            record.msg = redact_secrets(record.msg)
        return True

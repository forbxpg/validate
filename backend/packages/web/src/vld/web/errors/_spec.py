"""Description of how an error looks outside, and the registry of such descriptions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, NamedTuple

if TYPE_CHECKING:
    from collections.abc import Mapping


class ErrorSpec(NamedTuple):
    """How one specific error looks in the HTTP response.

    Attributes:
        status: int - HTTP status of the response.
        code: str - Machine error code.
        message: str - Text for a human.
        retry_after: int | None - The value of the ``Retry-After`` header in seconds, if
            the response invites to retry.

    """

    status: int
    code: str
    message: str
    retry_after: int | None = None


@dataclass(frozen=True, slots=True)
class ErrorRegistry:
    """A table «type of exception -> how it looks outside» for one module.

    Attributes:
        base: type[Exception] - The common ancestor of the module's exceptions.
        mapping: Mapping[type[Exception], ErrorSpec] - The table itself.
        fallback_code: str - The code that is returned when there is no record.

    """

    base: type[Exception]
    mapping: Mapping[type[Exception], ErrorSpec]
    fallback_code: str

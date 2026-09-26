"""Errors of the Crossref client: what went wrong, never what to tell a user."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ValidationProblem:
    """One complaint of a Crossref validation failure.

    Attributes:
        type: str - Machine type, such as ``filter-not-available``.
        value: str - The offending value as Crossref echoes it.
        message: str - Explanation from Crossref.

    """

    type: str
    value: str
    message: str


class CrossrefError(Exception):
    """Base of every error the library raises.

    Attributes:
        url: str | None - Request URL without `mailto`, when a request was made.

    """

    def __init__(self, message: str, *, url: str | None = None) -> None:
        super().__init__(message)
        self.url: str | None = url


class CrossrefQueryError(CrossrefError):
    """A query that cannot be sent: refused before any request."""


class CrossrefBadRequestError(CrossrefError):
    """Crossref answered 400 and listed what it refused.

    Attributes:
        problems: tuple[ValidationProblem, ...] - The complaints of Crossref.

    """

    def __init__(
        self,
        message: str,
        *,
        problems: tuple[ValidationProblem, ...],
        url: str | None = None,
    ) -> None:
        super().__init__(message, url=url)
        self.problems: tuple[ValidationProblem, ...] = problems


class CrossrefRateLimitedError(CrossrefError):
    """Crossref kept answering 429 until the retries ran out.

    Attributes:
        retry_after: float | None - Seconds Crossref asked to wait, if it said.

    """

    def __init__(
        self,
        message: str,
        *,
        retry_after: float | None,
        url: str | None = None,
    ) -> None:
        super().__init__(message, url=url)
        self.retry_after: float | None = retry_after


class CrossrefBlockedError(CrossrefError):
    """Crossref answered 403: the client is blocked by hand; retrying is useless."""


class CrossrefUnavailableError(CrossrefError):
    """Crossref failed with 5xx, a timeout or a broken connection after the retries.

    Attributes:
        status: int | None - HTTP status, or None when no response came.

    """

    def __init__(
        self,
        message: str,
        *,
        status: int | None,
        url: str | None = None,
    ) -> None:
        super().__init__(message, url=url)
        self.status: int | None = status


class CrossrefSchemaError(CrossrefError):
    """The envelope of a response is broken: there is nothing to return.

    Attributes:
        route: str - Path of the request, such as `/works`.
        detail: str - What is wrong with the envelope.

    """

    def __init__(
        self,
        *,
        route: str,
        detail: str,
        url: str | None = None,
    ) -> None:
        super().__init__(f"broken Crossref response on {route}: {detail}", url=url)
        self.route: str = route
        self.detail: str = detail


class CrossrefCursorExpiredError(CrossrefError):
    """The cursor of a walk expired between two pages."""

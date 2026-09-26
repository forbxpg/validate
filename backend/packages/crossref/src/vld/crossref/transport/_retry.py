"""How long to wait before another attempt, and which failures deserve one."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime
from typing import TYPE_CHECKING, Literal

from vld.crossref.errors import (
    CrossrefError,
    CrossrefRateLimitedError,
    CrossrefUnavailableError,
)

if TYPE_CHECKING:
    from collections.abc import Callable


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    """How many attempts a request gets and how long it waits between them.

    Attributes:
        attempts: int - Attempts in total, the first included.
        base_wait: timedelta - Wait before the second attempt without `Retry-After`.
        max_wait: timedelta - Ceiling of any wait.

    """

    attempts: int = 5
    base_wait: timedelta = timedelta(seconds=1)
    max_wait: timedelta = timedelta(seconds=30)

    def __post_init__(self) -> None:
        """Refuse a policy that cannot work.

        Raises:
            ValueError: If there is no attempt or a wait is not positive.

        """
        if self.attempts < 1:
            msg = f"at least one attempt is needed, got {self.attempts}"
            raise ValueError(msg)
        if self.base_wait <= timedelta(0) or self.max_wait < self.base_wait:
            msg = f"unusable waits: {self.base_wait} up to {self.max_wait}"
            raise ValueError(msg)


DEFAULT_RETRY = RetryPolicy()


class TransientFailure(Exception):  # ruff: ignore[error-suffix-on-exception-name] -- internal signal
    """A failure worth another attempt; turned into a public error when they run out.

    Attributes:
        kind: Literal["rate_limited", "unavailable"] - What failed.
        status: int | None - HTTP status, or None without a response.
        retry_after: float | None - Seconds Crossref asked to wait.
        url: str - Request URL without ``mailto``.

    """

    def __init__(
        self,
        kind: Literal["rate_limited", "unavailable"],
        *,
        status: int | None,
        retry_after: float | None,
        url: str,
    ) -> None:
        super().__init__(f"{kind} ({status})")
        self.kind: Literal["rate_limited", "unavailable"] = kind
        self.status: int | None = status
        self.retry_after: float | None = retry_after
        self.url: str = url

    def public(self) -> CrossrefError:
        """Give the error the caller sees once the attempts ran out.

        Returns:
            CrossrefError - Rate limited or unavailable.

        """
        if self.kind == "rate_limited":
            return CrossrefRateLimitedError(
                "Crossref kept answering 429",
                retry_after=self.retry_after,
                url=self.url,
            )
        return CrossrefUnavailableError(
            f"Crossref is unavailable (status {self.status})",
            status=self.status,
            url=self.url,
        )


def retry_after_seconds(value: str | None, now: datetime | None = None) -> float | None:
    """Read ``Retry-After``: seconds or an HTTP date.

    Args:
        value: str | None - The header.
        now: datetime | None - Current moment for an HTTP date; now by default.

    Returns:
        float | None - Seconds to wait, not negative, or None when unreadable.

    """
    if value is None:
        return None
    text = value.strip()
    if text.isdigit():
        return float(text)
    try:
        moment = parsedate_to_datetime(text)
    except (TypeError, ValueError):
        return None
    current = now or datetime.now(UTC)
    return max(0.0, (moment - current).total_seconds())


def wait_seconds(
    policy: RetryPolicy,
    attempt: int,
    retry_after: float | None,
    rng: Callable[[], float],
) -> float:
    """Seconds to wait after a failed attempt.

    ``Retry-After`` wins when present; otherwise exponential backoff with full
    jitter. Both are capped by ``max_wait``.

    Args:
        policy: RetryPolicy - The policy.
        attempt: int - Number of the attempt that failed, from 1.
        retry_after: float | None - Seconds Crossref asked to wait.
        rng: Callable[[], float] - Random number in [0, 1).

    Returns:
        float - Seconds to wait.

    """
    ceiling = policy.max_wait.total_seconds()
    if retry_after is not None:
        return min(retry_after, ceiling)
    backoff = min(policy.base_wait.total_seconds() * (1 << (attempt - 1)), ceiling)
    return backoff * rng()

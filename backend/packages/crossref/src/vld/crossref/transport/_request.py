"""The only code that talks HTTP: throttle, retries and the meaning of each status."""

from __future__ import annotations

from http import HTTPStatus
from typing import TYPE_CHECKING, cast, final

from httpx import URL, Timeout, TransportError
from structlog.stdlib import get_logger as structlog_get_logger
from tenacity import (
    AsyncRetrying,
    RetryCallState,
    retry_if_exception_type,
    stop_after_attempt,
)

from vld.crossref.errors import (
    CrossrefBadRequestError,
    CrossrefBlockedError,
    CrossrefUnavailableError,
)
from vld.crossref.throttle import parse_limits

from ._envelope import Envelope
from ._retry import TransientFailure, retry_after_seconds, wait_seconds

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Mapping

    from httpx import AsyncClient, Response

    from vld.crossref.throttle import Throttle

    from ._identity import Identity
    from ._retry import RetryPolicy


BASE_URL = "https://api.crossref.org"

_log = structlog_get_logger("vld.crossref")


@final
class Transport:
    """Sends one GET or HEAD to Crossref and tells what the answer means."""

    _identity: Identity
    _throttle: Throttle
    _retry: RetryPolicy
    _timeout: Timeout
    _clock: Callable[[], float]
    _sleep: Callable[[float], Awaitable[None]]
    _rng: Callable[[], float]
    _headers: dict[str, str]
    _http: AsyncClient | None
    pool: str | None

    def __init__(  # ruff: ignore[too-many-arguments] -- every knob of a request, all named
        self,
        *,
        identity: Identity,
        throttle: Throttle,
        retry: RetryPolicy,
        timeout: float,
        clock: Callable[[], float],
        sleep: Callable[[float], Awaitable[None]],
        rng: Callable[[], float],
    ) -> None:
        self._identity = identity
        self._throttle = throttle
        self._retry = retry
        self._timeout = Timeout(timeout)
        self._clock = clock
        self._sleep = sleep
        self._rng = rng
        self._headers = identity.headers()
        self._http = None
        self.pool = None

    @property
    def clock(self) -> Callable[[], float]:
        """Monotonic clock of the transport, shared with cursor walks.

        Returns:
            Callable[[], float] - The clock.

        """
        return self._clock

    def open(self, http: AsyncClient) -> None:
        """Start sending through a client.

        Args:
            http: AsyncClient - The HTTP client.

        """
        self._http = http

    def close(self) -> None:
        """Stop sending; the HTTP client is closed by its owner."""
        self._http = None

    async def get_json(self, path: str, params: Mapping[str, str]) -> Envelope | None:
        """GET a path and read its envelope.

        Args:
            path: str - Escaped path, such as ``/works/10.1000/abc``.
            params: Mapping[str, str] - Query parameters without ``mailto``.

        Returns:
            Envelope | None - The envelope, or None on 404.

        """
        response = await self._send("GET", path, params)
        if response is None:
            return None
        return Envelope.from_response(
            response,
            route=path,
            url=self._safe_url(path, params),
        )

    async def head(self, path: str) -> bool:
        """HEAD a path.

        Args:
            path: str - Escaped path.

        Returns:
            bool - True on 200, False on 404.

        """
        return await self._send("HEAD", path, {}) is not None

    async def _send(
        self,
        method: str,
        path: str,
        params: Mapping[str, str],
    ) -> Response | None:
        response: Response | None = None
        retrying = AsyncRetrying(
            stop=stop_after_attempt(self._retry.attempts),
            retry=retry_if_exception_type(TransientFailure),
            wait=self._wait,
            sleep=self._sleep,
            before_sleep=self._log_retry,
            reraise=True,
        )
        try:
            async for attempt in retrying:
                with attempt:
                    response = await self._attempt(
                        method,
                        path,
                        params,
                        attempt.retry_state.attempt_number,
                    )
        except TransientFailure as failure:
            raise failure.public() from failure
        return response

    async def _attempt(
        self,
        method: str,
        path: str,
        params: Mapping[str, str],
        number: int,
    ) -> Response | None:
        http = self._http
        if http is None:
            msg = "use CrossrefClient as an async context manager"
            raise RuntimeError(msg)
        url = self._safe_url(path, params)
        async with self._throttle.slot():
            started = self._clock()
            try:
                response = await http.request(
                    method,
                    BASE_URL + path,
                    params={**params, **self._identity.params()},
                    headers=self._headers,
                    timeout=self._timeout,
                )
            except TransportError as error:
                failure = TransientFailure(
                    "unavailable",
                    status=None,
                    retry_after=None,
                    url=url,
                )
                _log.debug(
                    "crossref_request",
                    method=method,
                    path=path,
                    status=None,
                    attempt=number,
                    error=type(error).__name__,
                )
                raise failure from error
        limits = parse_limits(response.headers)
        if limits is not None:
            self.pool = limits.pool or self.pool
            await self._throttle.observe(limits)
        _log.debug(
            "crossref_request",
            method=method,
            path=path,
            status=response.status_code,
            elapsed_ms=round((self._clock() - started) * 1000),  # milliseconds
            attempt=number,
            pool=self.pool,
        )
        return self._classify(response, url)

    def _wait(self, state: RetryCallState) -> float:
        outcome = state.outcome
        error = None if outcome is None else outcome.exception()
        retry_after = error.retry_after if isinstance(error, TransientFailure) else None
        return wait_seconds(self._retry, state.attempt_number, retry_after, self._rng)

    @staticmethod
    def _classify(response: Response, url: str) -> Response | None:
        status = response.status_code
        if status == HTTPStatus.OK:
            return response
        if status == HTTPStatus.NOT_FOUND:
            return None
        if status == HTTPStatus.BAD_REQUEST:
            problems = Envelope.parse_problems(response)
            detail = "; ".join(problem.message for problem in problems)
            msg = f"Crossref refused the request: {detail}"
            raise CrossrefBadRequestError(msg, problems=problems, url=url)
        if status == HTTPStatus.FORBIDDEN:
            msg = "Crossref blocked this client (403)"
            raise CrossrefBlockedError(msg, url=url)
        retry_after = retry_after_seconds(
            cast("str | None", response.headers.get("retry-after")),
        )
        if status == HTTPStatus.TOO_MANY_REQUESTS:
            failure = TransientFailure(
                "rate_limited",
                status=status,
                retry_after=retry_after,
                url=url,
            )
            raise failure
        if status >= HTTPStatus.INTERNAL_SERVER_ERROR:
            failure = TransientFailure(
                "unavailable",
                status=status,
                retry_after=retry_after,
                url=url,
            )
            raise failure
        msg = f"unexpected Crossref status {status}"
        raise CrossrefUnavailableError(msg, status=status, url=url)

    @staticmethod
    async def _log_retry(state: RetryCallState) -> None:
        outcome = state.outcome
        error = None if outcome is None else outcome.exception()
        _log.warning(
            "crossref_retry",
            reason=getattr(error, "kind", None),
            status=getattr(error, "status", None),
            attempt=state.attempt_number,
            wait_s=None if state.next_action is None else state.next_action.sleep,
        )

    @staticmethod
    def _safe_url(path: str, params: Mapping[str, str]) -> str:
        return str(URL(BASE_URL + path, params=dict(params)))
